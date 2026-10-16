from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from falkordb import FalkorDB
except ImportError:  # pragma: no cover - import is optional for storage fallback
    FalkorDB = None


class MemoryStore:
    """A FalkorDB-backed memory store with an in-memory fallback for local demos."""

    def __init__(
        self,
        graph_name: str = "devmemory",
        host: str = "localhost",
        port: int = 6379,
        use_local_fallback: bool = True,
        auto_reset: bool = False,
    ):
        self.graph_name = graph_name
        self.host = host
        self.port = port
        self.use_local_fallback = use_local_fallback
        self.auto_reset = auto_reset
        self._db: Any = None
        self._graph: Any = None
        self._local_memory: List[Dict[str, str]] = []
        self._connection_error: Optional[str] = None
        self._mode = "local"
        self._connect()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def connection_error(self) -> Optional[str]:
        return self._connection_error

    def _connect(self) -> None:
        if FalkorDB is None:
            self._mode = "local"
            self._local_memory = []
            return

        try:
            self._db = FalkorDB(host=self.host, port=self.port)
            self._graph = self._db.select_graph(self.graph_name)
            self._mode = "falkordb"
            if self.auto_reset:
                self._graph.query("MATCH (n) DETACH DELETE n")
        except Exception as exc:  # pragma: no cover - environment can be offline
            self._connection_error = str(exc)
            if self.use_local_fallback:
                self._mode = "local"
                self._local_memory = []
                return
            raise

    def record_project_memory(
        self,
        project: str,
        issue: str,
        fix: str,
        session: str,
        evidence: str,
    ) -> Dict[str, str]:
        record = {
            "project": project,
            "issue": issue,
            "fix": fix,
            "session": session,
            "evidence": evidence,
        }

        if self._mode == "falkordb":
            query = """
            MERGE (project:Project {name: $project})
            MERGE (issue:Issue {title: $issue})
            MERGE (fix:Fix {summary: $fix})
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
                rows = self._graph.query(query, params=params).result_set
                if rows:
                    row = rows[0]
                    if isinstance(row, (list, tuple)) and row:
                        return {
                            "project": row[0],
                            "issue": row[1],
                            "fix": row[2],
                            "session": row[3],
                            "evidence": row[4],
                        }
            except Exception:
                pass

        self._local_memory.append(record)
        return record

    def search(self, question: str) -> List[Dict[str, str]]:
        if self._mode == "falkordb":
            query = """
            MATCH (project:Project)-[:HAS_INCIDENT]->(issue:Issue)-[:RESOLVED_BY]->(fix:Fix)-[:RECORDED_IN]->(session:Session)
            WHERE toLower(project.name) CONTAINS toLower($term)
               OR toLower(issue.title) CONTAINS toLower($term)
               OR toLower(fix.summary) CONTAINS toLower($term)
               OR toLower(issue.evidence) CONTAINS toLower($term)
            RETURN project.name AS project, issue.title AS issue, fix.summary AS fix, session.name AS session, issue.evidence AS evidence
            ORDER BY project.name, session.name
            LIMIT 5
            """
            params = {"term": question}
            try:
                rows = self._graph.query(query, params=params).result_set
                results = []
                for row in rows:
                    if isinstance(row, (list, tuple)) and len(row) >= 5:
                        results.append(
                            {
                                "project": row[0],
                                "issue": row[1],
                                "fix": row[2],
                                "session": row[3],
                                "evidence": row[4],
                            }
                        )
                if results:
                    return results
            except Exception:
                pass

        search_term = self._normalize(question)
        matches: List[Dict[str, str]] = []
        for item in self._local_memory:
            haystack = " ".join(
                [
                    item.get("project", ""),
                    item.get("issue", ""),
                    item.get("fix", ""),
                    item.get("session", ""),
                    item.get("evidence", ""),
                ]
            )
            if search_term in self._normalize(haystack):
                matches.append(item)

        if matches:
            return matches

        return [record for record in self._local_memory if record.get("project")]

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value).lower().split())
