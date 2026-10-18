from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from ..memory import MemoryStore
from ..schema import DecisionStatus, TaskStatus


class MemoryAgent:
    """
    Agent 1: Memory Agent.
    Extracts facts, errors, solutions, architectural decisions, and tasks from developer
    interactions. Deduplicates records and persists them into the FalkorDB graph memory.
    """

    def __init__(self, memory_store: Optional[MemoryStore] = None):
        self.memory_store = memory_store or MemoryStore(use_local_fallback=True)
        self.agent_name = "Memory Agent"

    def record_incident_and_fix(
        self,
        project: str,
        issue: str,
        fix: str,
        session: str,
        evidence: str,
    ) -> Dict[str, Any]:
        """
        Deduplicates against existing issues and stores in FalkorDB graph.
        """
        # Deduplication check
        existing = self.memory_store.search(f"{project} {issue}")
        is_duplicate = any(
            e.get("project", "").lower() == project.lower()
            and e.get("issue", "").lower() == issue.lower()
            for e in existing
        )

        record = self.memory_store.record_project_memory(
            project=project,
            issue=issue,
            fix=fix,
            session=session,
            evidence=evidence,
        )
        return {
            "record": record,
            "deduplicated": is_duplicate,
            "status": "updated" if is_duplicate else "created",
            "agent": self.agent_name,
        }

    def record_architectural_decision(
        self,
        project: str,
        title: str,
        rationale: str,
        session: str,
        supersedes_title: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records an architectural decision. Handles outdated decisions by linking
        the new decision to the previous one with a [:SUPERSEDES] edge.
        """
        record = self.memory_store.record_decision(
            project_name=project,
            title=title,
            rationale=rationale,
            session_name=session,
            supersedes_title=supersedes_title,
            date=date,
        )
        return {
            "record": record,
            "superseded": supersedes_title,
            "status": "superseded_previous" if supersedes_title else "active_decision",
            "agent": self.agent_name,
        }

    def extract_from_conversation(
        self,
        text: str,
        project_default: str = "Job Portal",
        session_default: str = "Current Session",
    ) -> Dict[str, Any]:
        """
        Parses developer text for error mentions, fixes, and decisions.
        Extracts structured graph entities.
        """
        extracted = {
            "project": project_default,
            "issue": None,
            "fix": None,
            "decision": None,
            "stored": False,
        }

        # Check for error / fix pattern (e.g., "fixed X by Y" or "error X solved by Y")
        fix_match = re.search(
            r"(?:fixed|resolved|solved)\s+(?:the\s+)?(.+?)\s+by\s+(.+?)(?:\.|$)",
            text,
            re.IGNORECASE,
        )
        if fix_match:
            issue = fix_match.group(1).strip()
            fix = fix_match.group(2).strip()
            extracted["issue"] = issue
            extracted["fix"] = fix

            res = self.record_incident_and_fix(
                project=project_default,
                issue=issue,
                fix=fix,
                session=session_default,
                evidence=f"Extracted from developer conversation: '{text}'",
            )
            extracted["stored"] = True
            extracted["details"] = res
            return extracted

        # Check for decision pattern (e.g., "decided to use Vite instead of Webpack")
        decision_match = re.search(
            r"decided to\s+(.+?)(?:\s+instead of\s+(.+?))?(?:\s+because\s+(.+?))?(?:\.|$)",
            text,
            re.IGNORECASE,
        )
        if decision_match:
            new_choice = decision_match.group(1).strip()
            old_choice = decision_match.group(2).strip() if decision_match.group(2) else None
            rationale = decision_match.group(3).strip() if decision_match.group(3) else "Chosen by team"

            extracted["decision"] = new_choice
            res = self.record_architectural_decision(
                project=project_default,
                title=f"Use {new_choice}",
                rationale=rationale,
                session=session_default,
                supersedes_title=f"Use {old_choice}" if old_choice else None,
            )
            extracted["stored"] = True
            extracted["details"] = res

        return extracted
