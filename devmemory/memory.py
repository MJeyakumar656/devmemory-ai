from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from falkordb import FalkorDB
except ImportError:
    FalkorDB = None

from .schema import (
    AgentProfile,
    Decision,
    DecisionStatus,
    ErrorIncident,
    HandoffEvent,
    MemoryEvidence,
    Project,
    Session,
    Solution,
    Task,
    TaskStatus,
)


class MemoryStore:
    """
    FalkorDB-backed persistent memory store with local JSON fallback.
    Maintains developer memories: Projects, Sessions, Incidents, Solutions,
    Decisions, Tasks, Agents, and multi-agent handoffs across isolated Memory Spaces.
    """

    def __init__(
        self,
        graph_name: str = "devmemory",
        host: str = "localhost",
        port: int = 6379,
        use_local_fallback: bool = True,
        auto_reset: bool = False,
        storage_file: Optional[str] = None,
        active_space: str = "default",
    ):
        self.graph_name = graph_name
        self.host = os.getenv("FALKORDB_HOST", host)
        self.port = int(os.getenv("FALKORDB_PORT", str(port)))
        self.use_local_fallback = use_local_fallback
        self.auto_reset = auto_reset
        self.active_space = self._slugify(active_space or "default")

        base_dir = Path(__file__).parent.parent
        self.storage_file = storage_file or str(base_dir / "data" / "devmemory_graph.json")

        self._db: Any = None
        self._graph: Any = None
        self._mode = "local"
        self._connection_error: Optional[str] = None

        # Multi-Space Storage: { space_name: { "description": str, "nodes": {}, "edges": [], "handoffs": [] } }
        self._spaces: Dict[str, Dict[str, Any]] = {}

        self._load_local_storage()
        self._connect()

        if self.auto_reset:
            self.reset(clear_persistent_file=True, allow_default=True)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def connection_error(self) -> Optional[str]:
        return self._connection_error

    # Pointers to active space data
    @property
    def _nodes(self) -> Dict[str, Dict[str, Any]]:
        self._ensure_space(self.active_space)
        return self._spaces[self.active_space]["nodes"]

    @_nodes.setter
    def _nodes(self, val: Dict[str, Dict[str, Any]]) -> None:
        self._ensure_space(self.active_space)
        self._spaces[self.active_space]["nodes"] = val

    @property
    def _edges(self) -> List[Dict[str, Any]]:
        self._ensure_space(self.active_space)
        return self._spaces[self.active_space]["edges"]

    @_edges.setter
    def _edges(self, val: List[Dict[str, Any]]) -> None:
        self._ensure_space(self.active_space)
        self._spaces[self.active_space]["edges"] = val

    @property
    def _handoffs(self) -> List[Dict[str, Any]]:
        self._ensure_space(self.active_space)
        return self._spaces[self.active_space]["handoffs"]

    @_handoffs.setter
    def _handoffs(self, val: List[Dict[str, Any]]) -> None:
        self._ensure_space(self.active_space)
        self._spaces[self.active_space]["handoffs"] = val

    # -------------------------------------------------------------
    # MEMORY SPACE MANAGEMENT
    # -------------------------------------------------------------

    def _ensure_space(self, space_name: str, description: str = "") -> None:
        s = self._slugify(space_name)
        if s not in self._spaces:
            self._spaces[s] = {
                "name": space_name,
                "description": description or f"Memory workspace: {space_name}",
                "nodes": {},
                "edges": [],
                "handoffs": [],
            }

    def list_spaces(self) -> List[Dict[str, Any]]:
        """Returns all registered memory spaces with node and relationship metrics."""
        res = []
        for s_key, s_data in self._spaces.items():
            res.append(
                {
                    "id": s_key,
                    "name": s_data.get("name", s_key),
                    "description": s_data.get("description", ""),
                    "node_count": len(s_data.get("nodes", {})),
                    "edge_count": len(s_data.get("edges", [])),
                    "task_count": sum(
                        1 for n in s_data.get("nodes", {}).values() if n.get("label") == "Task"
                    ),
                    "is_active": (s_key == self.active_space),
                }
            )
        return res

    def create_space(self, space_name: str, description: str = "") -> Dict[str, Any]:
        """Creates a new isolated memory space in FalkorDB and persistent storage."""
        s = self._slugify(space_name)
        if not s:
            s = "default"
        self._ensure_space(s, description)
        self._save_local_storage()
        return {
            "id": s,
            "name": space_name,
            "description": self._spaces[s]["description"],
            "status": "created",
        }

    def switch_space(self, space_name: str) -> str:
        """Switches the active memory space."""
        s = self._slugify(space_name)
        self._ensure_space(s)
        self.active_space = s
        if self._mode == "falkordb" and self._db:
            try:
                graph_id = f"{self.graph_name}_{s}"
                self._graph = self._db.select_graph(graph_id)
                self._create_indices()
            except Exception:
                pass
        self._save_local_storage()
        return self.active_space

    def delete_space(self, space_name: str) -> bool:
        """Deletes a memory space (except default)."""
        s = self._slugify(space_name)
        if s == "default" or s not in self._spaces:
            return False
        if self._mode == "falkordb" and self._db:
            graph_id = f"{self.graph_name}_{s}"
            graph = self._db.select_graph(graph_id)
            graph.query("MATCH (n) DETACH DELETE n")
        del self._spaces[s]
        if self.active_space == s:
            self.switch_space("default")
        else:
            self._save_local_storage()
        return True

    # -------------------------------------------------------------
    # CONNECTION & PERSISTENCE
    # -------------------------------------------------------------

    def _connect(self) -> None:
        """Connects to FalkorDB if available, otherwise activates persistent fallback."""
        if FalkorDB is None:
            self._mode = "local"
            return

        try:
            self._db = FalkorDB(host=self.host, port=self.port)
            graph_id = (
                f"{self.graph_name}_{self.active_space}"
                if self.active_space != "default"
                else self.graph_name
            )
            self._graph = self._db.select_graph(graph_id)
            self._graph.query("RETURN 1")
            self._mode = "falkordb"
            self._create_indices()
        except Exception as exc:
            self._connection_error = str(exc)
            if self.use_local_fallback:
                self._mode = "local"
            else:
                raise

    def _create_indices(self) -> None:
        """Sets up Cypher indices in FalkorDB."""
        if self._mode != "falkordb" or not self._graph:
            return
        queries = [
            "CREATE INDEX FOR (p:Project) ON (p.name)",
            "CREATE INDEX FOR (e:Error) ON (e.title)",
            "CREATE INDEX FOR (s:Session) ON (s.name)",
            "CREATE INDEX FOR (d:Decision) ON (d.title)",
            "CREATE INDEX FOR (t:Task) ON (t.id)",
        ]
        for q in queries:
            try:
                self._graph.query(q)
            except Exception:
                pass

    def _save_local_storage(self) -> None:
        """Saves local graph state across all memory spaces to disk."""
        try:
            path = Path(self.storage_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "active_space": self.active_space,
                        "spaces": self._spaces,
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    def _load_local_storage(self) -> None:
        """Loads persisted graph state from previous sessions with backwards-compatibility."""
        try:
            path = Path(self.storage_file)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "spaces" in data:
                        self._spaces = data.get("spaces", {})
                        self.active_space = data.get("active_space", "default")
                    else:
                        # Migrate legacy single-space format into default space
                        self._spaces = {
                            "default": {
                                "name": "Default Workspace",
                                "description": "Primary project workspace",
                                "nodes": data.get("nodes", {}),
                                "edges": data.get("edges", []),
                                "handoffs": data.get("handoffs", []),
                            }
                        }
                        self.active_space = "default"
        except Exception:
            self._spaces = {}

        self._ensure_space(self.active_space)

    def reset(
        self,
        clear_persistent_file: bool = False,
        allow_default: bool = False,
    ) -> None:
        """Clears memory graph for active space, protecting default unless explicitly allowed."""
        if self.active_space == "default" and not allow_default:
            raise ValueError("The default memory space is protected from reset.")

        if self._mode == "falkordb" and self._graph:
            self._graph.query("MATCH (n) DETACH DELETE n")

        if self.active_space in self._spaces:
            self._spaces[self.active_space]["nodes"] = {}
            self._spaces[self.active_space]["edges"] = []
            self._spaces[self.active_space]["handoffs"] = []

        if clear_persistent_file:
            path = Path(self.storage_file)
            if path.exists():
                path.unlink()
        else:
            self._save_local_storage()

    def create_chat_thread(self, project_name: str = "Job Portal") -> Dict[str, str]:
        """Creates a persistent chat thread node in the active graph space."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        thread_id = f"chat_{uuid.uuid4().hex}"
        thread = {
            "id": thread_id,
            "title": "New conversation",
            "project": project_name,
            "created_at": now,
            "updated_at": now,
            "message_count": "0",
        }
        project_id = f"project_{self._slugify(project_name)}"
        self._add_node(project_id, "Project", {"name": project_name, "id": project_id})
        self._add_node(thread_id, "ChatThread", thread)
        self._add_edge(project_id, thread_id, "HAS_CONVERSATION")

        if self._mode == "falkordb" and self._graph:
            self._graph.query(
                """
                MERGE (p:Project {name: $project})
                MERGE (c:ChatThread {id: $id})
                SET c.title = $title,
                    c.project = $project,
                    c.created_at = $created_at,
                    c.updated_at = $updated_at,
                    c.message_count = 0
                MERGE (p)-[:HAS_CONVERSATION]->(c)
                """,
                params={
                    "id": thread_id,
                    "title": thread["title"],
                    "project": project_name,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        self._save_local_storage()
        return thread

    def list_chat_threads(self) -> List[Dict[str, str]]:
        """Returns chat threads for the active graph space, newest first."""
        threads = [
            dict(node.get("properties", {}))
            for node in self._nodes.values()
            if node.get("label") == "ChatThread"
        ]
        return sorted(
            threads,
            key=lambda thread: thread.get("updated_at", ""),
            reverse=True,
        )

    def get_chat_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Returns a chat thread and its exchanges from the active graph space."""
        node = self._nodes.get(thread_id)
        if not node or node.get("label") != "ChatThread":
            return None
        exchanges = []
        for edge in self._edges:
            if edge.get("source") != thread_id or edge.get("type") != "HAS_EXCHANGE":
                continue
            exchange_node = self._nodes.get(edge.get("target", ""), {})
            if exchange_node.get("label") == "Conversation":
                exchanges.append(dict(exchange_node.get("properties", {})))
        exchanges.sort(key=lambda exchange: exchange.get("created_at", ""))
        return {
            **node.get("properties", {}),
            "exchanges": exchanges,
        }

    def list_recent_chat_exchanges(
        self,
        exclude_conversation_id: Optional[str] = None,
        limit: int = 8,
    ) -> List[Dict[str, str]]:
        """Returns recent saved exchanges from other threads in the active space."""
        bounded_limit = max(0, min(limit, 50))
        if not bounded_limit:
            return []

        if self._mode == "falkordb" and self._graph:
            rows = self._graph.query(
                """
                MATCH (exchange:Conversation)
                WHERE ($exclude_id = '' OR exchange.conversation_id <> $exclude_id)
                RETURN exchange.project AS project,
                       exchange.user_message AS user_message,
                       exchange.assistant_response AS assistant_response,
                       exchange.session AS session,
                       exchange.conversation_id AS conversation_id,
                       exchange.created_at AS created_at
                ORDER BY exchange.created_at DESC
                LIMIT $limit
                """,
                params={
                    "exclude_id": exclude_conversation_id or "",
                    "limit": bounded_limit,
                },
            ).result_set
            return [
                {
                    "project": row[0] or "",
                    "user_message": row[1] or "",
                    "assistant_response": row[2] or "",
                    "session": row[3] or "",
                    "conversation_id": row[4] or "",
                    "created_at": row[5] or "",
                }
                for row in rows
                if isinstance(row, (list, tuple)) and len(row) >= 6
            ]

        exchanges = [
            dict(node.get("properties", {}))
            for node in self._nodes.values()
            if node.get("label") == "Conversation"
            and node.get("properties", {}).get("conversation_id") != exclude_conversation_id
        ]
        exchanges.sort(key=lambda exchange: exchange.get("created_at", ""), reverse=True)
        return exchanges[:bounded_limit]

    def record_conversation(
        self,
        project_name: str,
        user_message: str,
        assistant_response: str,
        session_name: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Persists a chat exchange and attaches it to its conversation thread."""
        thread_id = conversation_id
        if thread_id and self.get_chat_thread(thread_id) is None:
            raise ValueError("The requested chat conversation does not exist in the active space.")
        exchange_id = f"conversation_{uuid.uuid4().hex}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        project_id = f"project_{self._slugify(project_name)}"
        session_id = f"session_{self._slugify(session_name)}"
        properties = {
            "id": exchange_id,
            "conversation_id": thread_id or "",
            "project": project_name,
            "user_message": user_message,
            "assistant_response": assistant_response,
            "session": session_name,
            "created_at": now,
        }

        if self._mode == "falkordb" and self._graph:
            self._graph.query(
                """
                MERGE (p:Project {name: $project})
                MERGE (s:Session {name: $session})
                MERGE (c:Conversation {id: $id})
                SET c.project = $project,
                    c.user_message = $user_message,
                    c.assistant_response = $assistant_response,
                    c.session = $session,
                    c.conversation_id = $conversation_id,
                    c.created_at = $created_at
                MERGE (p)-[:HAS_CONVERSATION]->(c)
                MERGE (c)-[:RECORDED_IN]->(s)
                """,
                params={
                    "project": project_name,
                    "session": session_name,
                    "id": exchange_id,
                    "user_message": user_message,
                    "assistant_response": assistant_response,
                    "conversation_id": thread_id or "",
                    "created_at": now,
                },
            )

        self._add_node(project_id, "Project", {"name": project_name, "id": project_id})
        self._add_node(session_id, "Session", {"name": session_name, "id": session_id})
        self._add_node(exchange_id, "Conversation", properties)
        self._add_edge(project_id, exchange_id, "HAS_CONVERSATION")
        self._add_edge(exchange_id, session_id, "RECORDED_IN")
        if thread_id:
            self._add_edge(thread_id, exchange_id, "HAS_EXCHANGE")
            thread = self._nodes[thread_id]["properties"]
            exchange_count = int(thread.get("message_count", "0")) + 1
            thread_title = thread.get("title", "")
            if exchange_count == 1 and thread_title == "New conversation":
                thread_title = user_message[:64]
            thread.update(
                {
                    "title": thread_title,
                    "updated_at": now,
                    "last_message": user_message[:160],
                    "message_count": str(exchange_count),
                }
            )
            if self._mode == "falkordb" and self._graph:
                self._graph.query(
                    """
                    MATCH (thread:ChatThread {id: $thread_id})
                    MATCH (exchange:Conversation {id: $exchange_id})
                    MERGE (thread)-[:HAS_EXCHANGE]->(exchange)
                    SET thread.updated_at = $updated_at,
                        thread.last_message = $last_message,
                        thread.message_count = $message_count,
                        thread.title = CASE WHEN thread.title = 'New conversation'
                                            THEN $title ELSE thread.title END
                    """,
                    params={
                        "thread_id": thread_id,
                        "exchange_id": exchange_id,
                        "updated_at": now,
                        "last_message": user_message[:160],
                        "message_count": exchange_count,
                        "title": user_message[:64],
                    },
                )
        self._save_local_storage()
        return properties

    def search_conversations(
        self,
        query: str,
        project_name: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Finds saved conversation memories relevant to the query."""
        terms = self._retrieval_terms(query)
        if not terms:
            return []

        if self._mode == "falkordb" and self._graph:
            graph_query = """
            MATCH (p:Project)-[:HAS_CONVERSATION]->(c:Conversation)-[:RECORDED_IN]->(s:Session)
            WHERE ($project = '' OR toLower(p.name) = toLower($project))
              AND any(term IN $terms WHERE
                  toLower(c.user_message) CONTAINS term OR
                  toLower(c.assistant_response) CONTAINS term)
            RETURN p.name AS project, c.user_message AS user_message,
                   c.assistant_response AS assistant_response, s.name AS session
            ORDER BY c.created_at DESC
            LIMIT 50
            """
            rows = self._graph.query(
                graph_query,
                params={"project": project_name or "", "terms": terms},
            ).result_set
            matches = [
                {
                    "project": row[0] or "",
                    "user_message": row[1] or "",
                    "assistant_response": row[2] or "",
                    "session": row[3] or "",
                }
                for row in rows
                if isinstance(row, (list, tuple)) and len(row) >= 4
            ]
        else:
            matches = []
            for node in self._nodes.values():
                if node.get("label") != "Conversation":
                    continue
                props = node.get("properties", {})
                if project_name and props.get("project", "").lower() != project_name.lower():
                    continue
                matches.append(
                    {
                        "project": props.get("project", ""),
                        "user_message": props.get("user_message", ""),
                        "assistant_response": props.get("assistant_response", ""),
                        "session": props.get("session", ""),
                    }
                )

        ranked = []
        for conversation in matches:
            user_terms = set(self._retrieval_terms(conversation.get("user_message", "")))
            assistant_terms = set(self._retrieval_terms(conversation.get("assistant_response", "")))
            score = sum(2 for term in terms if term in user_terms)
            score += sum(1 for term in terms if term in assistant_terms)
            if score >= 2:
                ranked.append((score, conversation))
        ranked.sort(key=lambda match: match[0], reverse=True)
        return [conversation for _, conversation in ranked[:10]]

    # -------------------------------------------------------------
    # STRUCTURED CUSTOM MEMORY SAVE (FOR UI & APIS)
    # -------------------------------------------------------------

    def save_custom_memory(
        self,
        memory_type: str,
        project: str,
        title: str,
        details: str,
        session: str = "Current Session",
        evidence: str = "",
        supersedes_title: Optional[str] = None,
        assigned_to: str = "task_agent",
    ) -> Dict[str, Any]:
        """
        Unified method to save any memory type into the active FalkorDB space:
        - "incident" (bug/error + resolution)
        - "decision" (architectural choice + optional superseding)
        - "task" (assignable collaborative task)
        - "fact" (verified technical fact/note)
        """
        m_type = memory_type.lower()
        if m_type in ["incident", "error", "bug"]:
            rec = self.record_project_memory(
                project=project,
                issue=title,
                fix=details,
                session=session,
                evidence=evidence or "Developer manual entry",
            )
            return {
                "type": "incident",
                "record": rec,
                "summary": f"Recorded bug fix for {project}: '{title}' solved by '{details}'",
            }

        elif m_type in ["decision", "architecture"]:
            rec = self.record_decision(
                project_name=project,
                title=title,
                rationale=details,
                session_name=session,
                supersedes_title=supersedes_title,
            )
            return {
                "type": "decision",
                "record": rec,
                "summary": f"Recorded decision for {project}: '{title}' (Rationale: {details})",
            }

        elif m_type in ["task", "todo"]:
            task_id = f"task_{self._slugify(title[:20])}_{int(Path(__file__).stat().st_mtime)}"
            rec = self.record_task(
                task_id=task_id,
                title=title,
                project_name=project,
                description=details,
                assigned_to=assigned_to,
                status=TaskStatus.PENDING,
            )
            return {
                "type": "task",
                "record": rec,
                "summary": f"Created task for {project}: '{title}' assigned to {assigned_to}",
            }

        else:
            # General fact
            rec = self.record_project_memory(
                project=project,
                issue=title,
                fix=details,
                session=session,
                evidence=evidence or "Recorded technical fact",
            )
            return {
                "type": "fact",
                "record": rec,
                "summary": f"Recorded knowledge for {project}: '{title}'",
            }

    # -------------------------------------------------------------
    # CORE RECORDING & CYPHER PERSISTENCE
    # -------------------------------------------------------------

    def record_project_memory(
        self,
        project: str,
        issue: str,
        fix: str,
        session: str,
        evidence: str,
    ) -> Dict[str, str]:
        """
        Records an incident, resolution, and recorded session for a project.
        Supports both FalkorDB Cypher and persistent local fallback.
        """
        record = {
            "project": project,
            "issue": issue,
            "fix": fix,
            "session": session,
            "evidence": evidence,
        }

        if self._mode == "falkordb" and self._graph:
            query = """
            MERGE (project:Project {name: $project})
            MERGE (issue:Error {title: $issue})
            MERGE (fix:Solution {summary: $fix})
            MERGE (session:Session {name: $session})
            MERGE (project)-[:HAS_INCIDENT]->(issue)
            MERGE (issue)-[:RESOLVED_BY]->(fix)
            MERGE (fix)-[:RECORDED_IN]->(session)
            SET issue.evidence = $evidence,
                issue.project = $project,
                fix.project = $project
            RETURN project.name AS project, issue.title AS issue, fix.summary AS fix, session.name AS session, issue.evidence AS evidence
            """
            params = {
                "project": project,
                "issue": issue,
                "fix": fix,
                "session": session,
                "evidence": evidence,
            }
            try:
                res = self._graph.query(query, params=params).result_set
                if res and len(res) > 0:
                    row = res[0]
                    record = {
                        "project": row[0],
                        "issue": row[1],
                        "fix": row[2],
                        "session": row[3],
                        "evidence": row[4],
                    }
            except Exception:
                pass

        proj_id = f"project_{self._slugify(project)}"
        err_id = f"error_{self._slugify(issue)}"
        fix_id = f"sol_{self._slugify(fix)}"
        sess_id = f"session_{self._slugify(session)}"

        self._add_node(proj_id, "Project", {"name": project, "id": proj_id})
        self._add_node(
            err_id,
            "Error",
            {"title": issue, "evidence": evidence, "project": project, "id": err_id},
        )
        self._add_node(
            fix_id,
            "Solution",
            {"summary": fix, "project": project, "id": fix_id},
        )
        self._add_node(sess_id, "Session", {"name": session, "id": sess_id})

        self._add_edge(proj_id, err_id, "HAS_INCIDENT")
        self._add_edge(err_id, fix_id, "RESOLVED_BY")
        self._add_edge(fix_id, sess_id, "RECORDED_IN")

        self._save_local_storage()
        return record

    def record_decision(
        self,
        project_name: str,
        title: str,
        rationale: str,
        session_name: str,
        supersedes_title: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records an architectural decision. Handles outdated decisions by linking
        the new decision to the previous one with a [:SUPERSEDES] edge.
        """
        proj_id = f"project_{self._slugify(project_name)}"
        dec_id = f"decision_{self._slugify(title)}"
        sess_id = f"session_{self._slugify(session_name)}"

        self._add_node(proj_id, "Project", {"name": project_name, "id": proj_id})
        self._add_node(sess_id, "Session", {"name": session_name, "id": sess_id})

        dec_props = {
            "id": dec_id,
            "title": title,
            "rationale": rationale,
            "project": project_name,
            "session": session_name,
            "date": date or "2026-10-18",
            "status": DecisionStatus.ACTIVE.value,
            "superseded_by": None,
        }
        self._add_node(dec_id, "Decision", dec_props)
        self._add_edge(proj_id, dec_id, "HAS_DECISION")
        self._add_edge(dec_id, sess_id, "MADE_IN")

        if supersedes_title:
            old_id = f"decision_{self._slugify(supersedes_title)}"
            if old_id in self._nodes:
                self._nodes[old_id]["properties"]["status"] = DecisionStatus.SUPERSEDED.value
                self._nodes[old_id]["properties"]["superseded_by"] = title
                self._add_edge(dec_id, old_id, "SUPERSEDES")

        if self._mode == "falkordb" and self._graph:
            cypher = """
            MERGE (p:Project {name: $project})
            MERGE (d:Decision {title: $title})
            MERGE (s:Session {name: $session})
            MERGE (p)-[:HAS_DECISION]->(d)
            MERGE (d)-[:MADE_IN]->(s)
            SET d.rationale = $rationale,
                d.status = 'active',
                d.date = $date
            """
            params = {
                "project": project_name,
                "title": title,
                "rationale": rationale,
                "session": session_name,
                "date": date or "2026-10-18",
            }
            try:
                self._graph.query(cypher, params=params)
                if supersedes_title:
                    sup_cypher = """
                    MATCH (d_new:Decision {title: $title})
                    MATCH (d_old:Decision {title: $old_title})
                    MERGE (d_new)-[:SUPERSEDES]->(d_old)
                    SET d_old.status = 'superseded',
                        d_old.superseded_by = $title
                    """
                    self._graph.query(
                        sup_cypher,
                        params={"title": title, "old_title": supersedes_title},
                    )
            except Exception:
                pass

        self._save_local_storage()
        return dec_props

    def get_decisions(self, project_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all decisions for a project, noting active vs superseded status."""
        results: List[Dict[str, Any]] = []
        for nid, node in self._nodes.items():
            if node.get("label") == "Decision":
                props = node.get("properties", {})
                if not project_name or props.get("project", "").lower() == project_name.lower():
                    results.append(props)
        return results

    # -------------------------------------------------------------
    # TASK MANAGEMENT & MULTI-AGENT HANDOFFS
    # -------------------------------------------------------------

    def record_task(
        self,
        task_id: str,
        title: str,
        project_name: str,
        description: str = "",
        assigned_to: str = "task_agent",
        created_by: str = "coordinator",
        status: TaskStatus = TaskStatus.PENDING,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates or updates a task and assigns it to an agent in the graph."""
        task_props = {
            "id": task_id,
            "title": title,
            "project": project_name,
            "description": description,
            "assigned_to": assigned_to,
            "created_by": created_by,
            "status": status.value if hasattr(status, "value") else str(status),
            "context": context or {},
        }

        tid = f"task_{self._slugify(task_id)}"
        pid = f"project_{self._slugify(project_name)}"
        aid = f"agent_{self._slugify(assigned_to)}"
        cid = f"agent_{self._slugify(created_by)}"

        self._add_node(tid, "Task", task_props)
        self._add_node(pid, "Project", {"name": project_name, "id": pid})
        self._add_node(aid, "Agent", {"name": assigned_to, "id": aid})
        self._add_node(cid, "Agent", {"name": created_by, "id": cid})

        self._add_edge(pid, tid, "HAS_TASK")
        self._add_edge(tid, aid, "ASSIGNED_TO")
        self._add_edge(tid, cid, "CREATED_BY")

        if self._mode == "falkordb" and self._graph:
            cypher = """
            MERGE (p:Project {name: $project})
            MERGE (t:Task {id: $task_id})
            MERGE (a:Agent {name: $assigned_to})
            MERGE (p)-[:HAS_TASK]->(t)
            MERGE (t)-[:ASSIGNED_TO]->(a)
            SET t.title = $title,
                t.description = $description,
                t.status = $status
            """
            params = {
                "project": project_name,
                "task_id": task_id,
                "title": title,
                "description": description,
                "assigned_to": assigned_to,
                "status": task_props["status"],
            }
            try:
                self._graph.query(cypher, params=params)
            except Exception:
                pass

        self._save_local_storage()
        return task_props

    def record_handoff(
        self,
        task_id: str,
        from_agent: str,
        to_agent: str,
        reason: str,
        context_summary: str = "",
    ) -> HandoffEvent:
        """Records an agent-to-agent task handoff in the graph memory."""
        handoff = HandoffEvent(
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            context_summary=context_summary,
        )

        tid = f"task_{self._slugify(task_id)}"
        from_id = f"agent_{self._slugify(from_agent)}"
        to_id = f"agent_{self._slugify(to_agent)}"

        self._add_node(from_id, "Agent", {"name": from_agent, "id": from_id})
        self._add_node(to_id, "Agent", {"name": to_agent, "id": to_id})
        self._add_edge(
            tid,
            to_id,
            "HANDED_OFF_TO",
            {"reason": reason, "from": from_agent, "timestamp": handoff.timestamp},
        )

        if tid in self._nodes:
            self._nodes[tid]["properties"]["status"] = TaskStatus.HANDED_OFF.value
            self._nodes[tid]["properties"]["assigned_to"] = to_agent

        self._handoffs.append(handoff.model_dump())

        if self._mode == "falkordb" and self._graph:
            cypher = """
            MATCH (t:Task {id: $task_id})
            MERGE (to_a:Agent {name: $to_agent})
            MERGE (from_a:Agent {name: $from_agent})
            MERGE (t)-[r:HANDED_OFF_TO]->(to_a)
            SET r.reason = $reason,
                r.timestamp = $timestamp,
                t.status = 'handed_off',
                t.assigned_to = $to_agent
            """
            params = {
                "task_id": task_id,
                "to_agent": to_agent,
                "from_agent": from_agent,
                "reason": reason,
                "timestamp": handoff.timestamp,
            }
            try:
                self._graph.query(cypher, params=params)
            except Exception:
                pass

        self._save_local_storage()
        return handoff

    def get_tasks(self, project_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns tasks from memory."""
        results: List[Dict[str, Any]] = []
        for nid, node in self._nodes.items():
            if node.get("label") == "Task":
                props = node.get("properties", {})
                if not project_name or props.get("project", "").lower() == project_name.lower():
                    results.append(props)
        return results

    def get_handoffs(self) -> List[Dict[str, Any]]:
        """Returns recorded agent handoffs."""
        return list(self._handoffs)

    # -------------------------------------------------------------
    # RETRIEVAL & GRAPH TRAVERSAL
    # -------------------------------------------------------------

    def search(self, question: str) -> List[Dict[str, str]]:
        """
        Backwards-compatible search returning project incident/fix records.
        Executes FalkorDB Cypher or graph traversals across relationships.
        """
        if self._mode == "falkordb" and self._graph:
            query = """
            MATCH (project:Project)-[:HAS_INCIDENT]->(issue:Error)-[:RESOLVED_BY]->(fix:Solution)-[:RECORDED_IN]->(session:Session)
            WHERE any(term IN $terms WHERE
                  toLower(issue.title) CONTAINS term
                  OR toLower(fix.summary) CONTAINS term
                  OR toLower(issue.evidence) CONTAINS term)
            RETURN project.name AS project, issue.title AS issue, fix.summary AS fix, session.name AS session, issue.evidence AS evidence
            ORDER BY session.name DESC
            LIMIT 50
            """
            params = {"terms": self._retrieval_terms(question)}
            try:
                rows = self._graph.query(query, params=params).result_set
                results = []
                query_terms = self._retrieval_terms(question)
                for row in rows:
                    if isinstance(row, (list, tuple)) and len(row) >= 5:
                        candidate = {
                            "project": row[0],
                            "issue": row[1],
                            "fix": row[2],
                            "session": row[3],
                            "evidence": row[4],
                        }
                        issue_terms = set(self._retrieval_terms(candidate["issue"] or ""))
                        fix_terms = set(self._retrieval_terms(candidate["fix"] or ""))
                        evidence_terms = set(self._retrieval_terms(candidate["evidence"] or ""))
                        score = sum(3 for term in query_terms if term in issue_terms)
                        score += sum(1 for term in query_terms if term in fix_terms | evidence_terms)
                        if score >= 3:
                            results.append((score, candidate))
                if results:
                    results.sort(key=lambda match: match[0], reverse=True)
                    return [candidate for _, candidate in results[:5]]
            except Exception:
                pass

        return self._search_local_incidents(question)

    def retrieve_context_with_evidence(
        self,
        query: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full graph multi-hop retrieval: finds incidents, resolutions, decisions,
        tasks, and formats them into structured Answer Evidence.
        """
        query_terms = set(self._retrieval_terms(query))
        decision_intent = bool(
            query_terms
            & {"decision", "decided", "choice", "bundler", "architecture", "strategy"}
        )
        incidents = [] if decision_intent else self.search(query)
        decisions = self.get_decisions(project_name) if decision_intent else []
        tasks = self.get_tasks(project_name)
        conversations = (
            [] if incidents or decisions else self.search_conversations(query, project_name)
        )

        evidence_items: List[MemoryEvidence] = []

        for inc in incidents:
            evidence_items.append(
                MemoryEvidence(
                    source_type="Project",
                    source_name=inc["project"],
                    relation="HAS_INCIDENT -> RESOLVED_BY",
                    target_type="Solution",
                    target_name=inc["fix"],
                    session=inc["session"],
                    date="Recorded in session",
                    confidence=0.98,
                    notes=f"Issue: '{inc['issue']}'. Evidence: {inc['evidence']}",
                )
            )

        q_norm = query.lower()
        for dec in decisions:
            if (
                dec.get("title", "").lower() in q_norm
                or any(w in dec.get("title", "").lower() for w in q_norm.split() if len(w) > 3)
            ):
                evidence_items.append(
                    MemoryEvidence(
                        source_type="Project",
                        source_name=dec.get("project", "Unknown"),
                        relation="HAS_DECISION",
                        target_type="Decision",
                        target_name=dec.get("title", ""),
                        session=dec.get("session", ""),
                        date=dec.get("date", ""),
                        confidence=0.92,
                        notes=(
                            f"Status: {dec.get('status')}. Rationale: {dec.get('rationale')}."
                            + (
                                f" Superseded by {dec.get('superseded_by')}."
                                if dec.get("superseded_by")
                                else ""
                            )
                        ),
                    )
                )

        for conversation in conversations:
            evidence_items.append(
                MemoryEvidence(
                    source_type="Project",
                    source_name=conversation.get("project", "Unknown"),
                    relation="HAS_CONVERSATION -> RECORDED_IN",
                    target_type="Conversation",
                    target_name=conversation.get("user_message", "Saved conversation")[:120],
                    session=conversation.get("session", ""),
                    confidence=0.9,
                    notes=f"Saved assistant response: {conversation.get('assistant_response', '')}",
                )
            )

        return {
            "incidents": incidents,
            "decisions": decisions,
            "tasks": tasks,
            "conversations": conversations,
            "evidence": evidence_items,
            "active_space": self.active_space,
        }

    def _search_local_incidents(self, question: str) -> List[Dict[str, str]]:
        """Traverses local node/edge graph to find matching incident-solution paths."""
        search_terms = self._retrieval_terms(question)
        matches: List[tuple[int, Dict[str, str]]] = []

        for edge in self._edges:
            if edge["type"] == "RESOLVED_BY":
                err_id = edge["source"]
                sol_id = edge["target"]

                err_node = self._nodes.get(err_id, {})
                sol_node = self._nodes.get(sol_id, {})

                proj_node = {}
                for pe in self._edges:
                    if pe["type"] == "HAS_INCIDENT" and pe["target"] == err_id:
                        proj_node = self._nodes.get(pe["source"], {})
                        break

                sess_node = {}
                for se in self._edges:
                    if se["type"] == "RECORDED_IN" and se["source"] == sol_id:
                        sess_node = self._nodes.get(se["target"], {})
                        break

                project_name = proj_node.get("properties", {}).get("name", "Unknown")
                issue_title = err_node.get("properties", {}).get("title", "Unknown")
                fix_summary = sol_node.get("properties", {}).get("summary", "Unknown")
                session_name = sess_node.get("properties", {}).get("name", "Session")
                evidence_text = err_node.get("properties", {}).get("evidence", "")

                candidate = {
                    "project": project_name,
                    "issue": issue_title,
                    "fix": fix_summary,
                    "session": session_name,
                    "evidence": evidence_text,
                }

                issue_terms = set(self._retrieval_terms(issue_title))
                fix_terms = set(self._retrieval_terms(fix_summary))
                evidence_terms = set(self._retrieval_terms(evidence_text))
                score = sum(3 for term in search_terms if term in issue_terms)
                score += sum(1 for term in search_terms if term in fix_terms)
                score += sum(1 for term in search_terms if term in evidence_terms)
                if score >= 3:
                    matches.append((score, candidate))

        if matches:
            matches.sort(key=lambda match: match[0], reverse=True)
            return [candidate for _, candidate in matches[:5]]

        if search_terms:
            return []

        fallback_list = []
        for edge in self._edges:
            if edge["type"] == "RESOLVED_BY":
                err_node = self._nodes.get(edge["source"], {})
                sol_node = self._nodes.get(edge["target"], {})
                fallback_list.append(
                    {
                        "project": err_node.get("properties", {}).get("project", "Job Portal"),
                        "issue": err_node.get("properties", {}).get("title", ""),
                        "fix": sol_node.get("properties", {}).get("summary", ""),
                        "session": "Recorded Session",
                        "evidence": err_node.get("properties", {}).get("evidence", ""),
                    }
                )
        return fallback_list

    @staticmethod
    def _retrieval_terms(text: str) -> List[str]:
        """Tokenizes queries consistently and drops common conversational filler."""
        stop_words = {
            "about", "after", "again", "and", "are", "did", "does", "for", "from",
            "have", "help", "how", "into", "last", "make", "memory", "need", "our",
            "please", "project", "remember", "that", "the", "then", "there", "this",
            "week", "what", "when", "where", "which", "with", "would", "you", "your",
            "can", "could", "was", "were", "will", "would", "has", "had", "user",
            "tell", "started", "starting", "mention", "mentioned", "three", "weeks",
        }
        aliases = {"startup": "start", "failed": "fail", "failure": "fail"}
        terms = re.findall(r"[a-z0-9]+", str(text).lower())
        return [
            aliases.get(term, term)
            for term in terms
            if len(term) > 2 and term not in stop_words
        ]

    # -------------------------------------------------------------
    # GRAPH VISUALIZATION EXPORT
    # -------------------------------------------------------------

    def export_graph_visualization(
        self,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exports the memory graph in D3 / UI-friendly format.
        Includes node categories, colors, sizes, and edge relationships.
        """
        type_colors = {
            "Project": "#38bdf8",  # Sky blue
            "Error": "#f87171",    # Coral red
            "Solution": "#34d399", # Emerald green
            "Session": "#a855f7",  # Purple
            "Decision": "#fbbf24", # Amber
            "Task": "#06b6d4",     # Cyan
            "Agent": "#ec4899",    # Pink
            "ChatThread": "#8b5cf6",  # Violet
            "Conversation": "#f472b6",  # Pink
            "User": "#94a3b8",     # Slate
        }

        nodes_list = []
        for nid, node in self._nodes.items():
            lbl = node.get("label", "Node")
            props = node.get("properties", {})
            name = (
                props.get("name")
                or props.get("title")
                or (
                    props.get("user_message", "")[:64]
                    if lbl == "Conversation"
                    else ""
                )
                or props.get("summary")
                or props.get("id")
                or nid
            )
            nodes_list.append(
                {
                    "id": nid,
                    "label": name,
                    "type": lbl,
                    "color": type_colors.get(lbl, "#94a3b8"),
                    "properties": props,
                }
            )

        links_list = []
        for edge in self._edges:
            links_list.append(
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "label": edge["type"],
                    "properties": edge.get("properties", {}),
                }
            )

        return {
            "nodes": nodes_list,
            "links": links_list,
            "backend_mode": self._mode,
            "active_space": self.active_space,
            "total_nodes": len(nodes_list),
            "total_edges": len(links_list),
        }

    # -------------------------------------------------------------
    # INTERNAL GRAPH HELPERS
    # -------------------------------------------------------------

    def _add_node(self, node_id: str, label: str, properties: Dict[str, Any]) -> None:
        if node_id not in self._nodes:
            self._nodes[node_id] = {"id": node_id, "label": label, "properties": properties}
        else:
            self._nodes[node_id]["properties"].update(properties)

    def _add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        for e in self._edges:
            if e["source"] == source and e["target"] == target and e["type"] == edge_type:
                if properties:
                    e.setdefault("properties", {}).update(properties)
                return
        self._edges.append(
            {
                "source": source,
                "target": target,
                "type": edge_type,
                "properties": properties or {},
            }
        )

    @staticmethod
    def _slugify(text: str) -> str:
        s = re.sub(r"[^\w\s-]", "", str(text)).strip().lower()
        return re.sub(r"[-\s]+", "_", s)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value).lower().split())
