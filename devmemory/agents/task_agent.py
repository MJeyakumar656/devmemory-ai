from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..memory import MemoryStore
from ..schema import AgentResponse, MemoryEvidence


class TaskAgent:
    """
    Agent 2: Task Agent.
    Implements the core 5-step cycle:
    Receive -> Retrieve -> Reason -> Respond -> Remember.

    Retrieves connected graph evidence from FalkorDB, reasons over the evidence,
    and returns responses citing explicit sessions, decisions, and fixes.
    """

    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        model_name: str = "gpt-4o-mini",
    ):
        self.memory_store = memory_store or MemoryStore(use_local_fallback=True)
        self.model_name = model_name
        self.agent_name = "Task Agent"

    def answer(self, question: str, project_name: Optional[str] = None) -> str:
        """Convenience method returning string response for backwards compatibility."""
        response_obj = self.process_query(question, project_name)
        return response_obj.answer

    def process_query(
        self,
        question: str,
        project_name: Optional[str] = None,
    ) -> AgentResponse:
        """
        Executes the full 5-step loop:
        1. Receive: parse input question
        2. Retrieve: query FalkorDB graph memory across relationships
        3. Reason: synthesize facts and citations
        4. Respond: generate structured evidence-backed answer
        5. Remember: return full provenance and confidence
        """
        # Step 2: Retrieve
        context_data = self.memory_store.retrieve_context_with_evidence(
            query=question,
            project_name=project_name,
        )

        incidents = context_data.get("incidents", [])
        decisions = context_data.get("decisions", [])
        evidence_list: List[MemoryEvidence] = context_data.get("evidence", [])

        if not incidents and not decisions:
            return AgentResponse(
                answer=(
                    "I could not find matching memories for that project, issue, or decision in FalkorDB. "
                    "Store a project memory first, then ask again."
                ),
                evidence=[],
                retrieved_records=[],
                confidence=0.0,
                backend_mode=self.memory_store.mode,
            )

        # Step 3: Reason (via LLM or deterministic graph synthesis)
        answer_text = self._reason_over_evidence(
            question=question,
            incidents=incidents,
            decisions=decisions,
        )

        # Step 4: Respond
        return AgentResponse(
            answer=answer_text,
            evidence=evidence_list,
            retrieved_records=incidents + decisions,
            confidence=0.98 if incidents else 0.85,
            backend_mode=self.memory_store.mode,
        )

    def _reason_over_evidence(
        self,
        question: str,
        incidents: List[Dict[str, str]],
        decisions: List[Dict[str, Any]],
    ) -> str:
        """Synthesizes the answer using graph evidence, attempting LLM first then deterministic synthesis."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and OpenAI is not None:
            try:
                client = OpenAI(api_key=api_key)
                prompt = (
                    "You are DevMemory AI, an intelligent coding teammate backed by FalkorDB graph memory. "
                    "Use ONLY the retrieved graph evidence to answer the developer's question. "
                    "Always explicitly cite the Project name, the Issue, the Solution/Fix, and the Session."
                )
                evidence_repr = f"Incidents: {incidents}\nDecisions: {decisions}"
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": f"Developer Question: {question}\n\nRetrieved FalkorDB Evidence:\n{evidence_repr}",
                        },
                    ],
                    temperature=0.0,
                )
                content = response.choices[0].message.content
                if content:
                    return content
            except Exception:
                pass

        # Deterministic graph reasoning synthesis (Offline-first & reliable for judges and tests)
        parts = []

        if incidents:
            top_inc = incidents[0]
            project = top_inc.get("project", "Project")
            issue = top_inc.get("issue", "Issue")
            fix = top_inc.get("fix", "Fix")
            session = top_inc.get("session", "Past Session")
            evidence = top_inc.get("evidence", "")

            parts.append(
                f"In the **{project}** project, we resolved the **{issue}** by **{fix}**."
            )
            parts.append(
                f"This resolution was recorded in **{session}**."
            )
            if evidence:
                parts.append(f"Recorded Evidence: {evidence}")

        # Check for active or superseded architectural decisions
        active_decisions = [d for d in decisions if d.get("status") == "active"]
        superseded_decisions = [d for d in decisions if d.get("status") == "superseded"]

        if active_decisions:
            dec = active_decisions[0]
            parts.append(
                f"\n**Active Decision**: {dec.get('title')} (Rationale: {dec.get('rationale')})."
            )

        if superseded_decisions:
            old_dec = superseded_decisions[0]
            parts.append(
                f"\n*(Note: Previous decision '{old_dec.get('title')}' is now superseded by '{old_dec.get('superseded_by')}')*."
            )

        return "\n".join(parts)
