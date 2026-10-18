from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from ..memory import MemoryStore
from ..schema import AgentProfile, AgentResponse, HandoffEvent, Task, TaskStatus
from .memory_agent import MemoryAgent
from .task_agent import TaskAgent


class AgentCoordinator:
    """
    Step 6: Coordinator for Multi-Agent Collaboration.
    Assigns tasks, manages shared memory state in FalkorDB, and tracks handoffs
    between specialized AI agents (Coordinator, Memory Agent, Bug Investigator, Code Fixer).
    """

    def __init__(self, memory_store: Optional[MemoryStore] = None):
        self.memory_store = memory_store or MemoryStore(use_local_fallback=True)
        self.memory_agent = MemoryAgent(self.memory_store)
        self.task_agent = TaskAgent(self.memory_store)

        # Registered team agents
        self.agents: Dict[str, AgentProfile] = {
            "coordinator": AgentProfile(
                id="coordinator", name="Coordinator", role="Task Dispatcher & Orchestrator"
            ),
            "memory_agent": AgentProfile(
                id="memory_agent", name="Memory Agent", role="Knowledge Extractor & Graph Persistence"
            ),
            "bug_investigator": AgentProfile(
                id="bug_investigator", name="Bug Investigator", role="Root Cause Analysis via Graph Memory"
            ),
            "code_fixer": AgentProfile(
                id="code_fixer", name="Code Fixer", role="Solution Implementation & Verification"
            ),
        }

        self.activity_logs: List[Dict[str, Any]] = []

    def log_activity(self, agent_name: str, action: str, details: str) -> None:
        """Appends to the shared multi-agent activity stream."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "agent": agent_name,
            "action": action,
            "details": details,
        }
        self.activity_logs.append(entry)

    def handle_request(
        self,
        user_message: str,
        project_name: str = "Job Portal",
        session_name: str = "Current Session",
        conversation_context: str = "",
    ) -> Dict[str, Any]:
        """
        Orchestrates user requests:
        1. Checks if it's a query about past events -> retrieves memory via Task Agent.
        2. Checks if it's new information to remember -> stores via Memory Agent.
        3. Checks if it requires a multi-agent task execution and handoff.
        """
        plan = [
            {"step": "Understand the request", "status": "completed"},
            {"step": "Extract and store new project knowledge", "status": "skipped"},
            {"step": "Retrieve relevant graph memories", "status": "pending"},
            {"step": "Reason over evidence and respond", "status": "pending"},
            {"step": "Evaluate answer grounding", "status": "pending"},
        ]
        tools_used: List[Dict[str, str]] = []
        self.log_activity(
            "Coordinator",
            "Plan Created",
            "Understand the request, check for knowledge to save, retrieve graph evidence, answer, and evaluate grounding.",
        )
        self.log_activity("Coordinator", "Received Message", f'"{user_message}"')

        # Check for knowledge extraction (e.g. "We fixed X by Y" or "Decided to use...")
        extracted = self.memory_agent.extract_from_conversation(
            user_message,
            project_default=project_name,
            session_default=session_name,
        )
        plan[1]["status"] = "completed" if extracted.get("stored") else "skipped"
        tools_used.append(
            {
                "name": "MemoryAgent.extract_from_conversation",
                "purpose": "Detect and persist a bug fix or architectural decision.",
                "status": "stored" if extracted.get("stored") else "no_facts_detected",
            }
        )
        if extracted.get("stored"):
            self.log_activity(
                "Memory Agent",
                "Graph Memory Stored",
                f"Persisted node in FalkorDB for project {project_name}",
            )

        # Retrieve knowledge and formulate answer
        self.log_activity(
            "Task Agent",
            "Graph Memory Retrieval",
            f"Querying FalkorDB for connected entities: '{user_message}'",
        )
        plan[2]["status"] = "in_progress"
        agent_resp: AgentResponse = self.task_agent.process_query(
            question=user_message,
            project_name=project_name,
            conversation_context=conversation_context,
        )
        if extracted.get("stored") and extracted.get("issue") and extracted.get("fix"):
            agent_resp = agent_resp.model_copy(
                update={
                    "answer": (
                        f"Saved to graph memory for **{project_name}**: "
                        f"**{extracted['issue']}** was resolved by **{extracted['fix']}**. "
                        f"Recorded in **{session_name}**. You can ask about this fix in a later chat."
                    )
                }
            )
        plan[2]["status"] = "completed"
        plan[3]["status"] = "completed"
        tools_used.append(
            {
                "name": "MemoryStore.retrieve_context_with_evidence",
                "purpose": "Retrieve project incidents, decisions, and provenance from the active graph space.",
                "status": f"{len(agent_resp.retrieved_records)} records retrieved",
            }
        )

        has_evidence = bool(agent_resp.evidence)
        has_answer = bool(agent_resp.answer.strip())
        evaluation_passed = has_evidence or bool(extracted.get("stored"))
        evaluation = {
            "passed": evaluation_passed,
            "answer_generated": has_answer,
            "answer_grounded": has_evidence,
            "memory_saved": bool(extracted.get("stored")),
            "feedback": (
                "The answer is supported by retrieved project memory."
                if has_evidence
                else (
                    "New project knowledge was saved; no separate prior evidence was needed."
                    if extracted.get("stored")
                    else "No matching evidence was found. The response explains this limitation and suggests saving a memory."
                )
            ),
        }
        plan[4]["status"] = "completed"
        self.log_activity(
            "Feedback & Evaluation",
            "Answer Grounding Checked",
            evaluation["feedback"],
        )

        return {
            "response": agent_resp.answer,
            "answer": agent_resp.answer,
            "evidence": [e.model_dump() for e in agent_resp.evidence],
            "retrieved_records": agent_resp.retrieved_records,
            "confidence": agent_resp.confidence,
            "backend_mode": self.memory_store.mode,
            "plan": plan,
            "tools_used": tools_used,
            "evaluation": evaluation,
            "reasoning_mode": agent_resp.reasoning_mode,
            "reasoning_warning": agent_resp.reasoning_warning,
            "activity_logs": list(self.activity_logs[-10:]),
        }

    def execute_multi_agent_workflow(
        self,
        task_title: str,
        project_name: str,
        description: str,
        session_name: str = "Investigation Session",
    ) -> Dict[str, Any]:
        """
        Demonstrates Step 6 / Milestone 4:
        Agent 1 (Bug Investigator) creates a task and searches FalkorDB for past context.
        Agent 1 hands off to Agent 2 (Code Fixer) with retrieved memory context.
        Agent 2 resolves the task and verifies the fix.
        Memory Agent persists the completed solution.
        """
        task_id = f"task_{int(datetime.now().timestamp())}"

        # 1. Coordinator initiates task
        self.log_activity(
            "Coordinator",
            "Task Created",
            f"Created {task_id}: '{task_title}' for project '{project_name}'",
        )
        self.memory_store.record_task(
            task_id=task_id,
            title=task_title,
            project_name=project_name,
            description=description,
            assigned_to="bug_investigator",
            created_by="coordinator",
            status=TaskStatus.IN_PROGRESS,
        )

        # 2. Bug Investigator analyzes FalkorDB memory
        self.log_activity(
            "Bug Investigator",
            "Graph Context Analysis",
            f"Searching FalkorDB for related past incidents in '{project_name}'",
        )
        related_memories = self.memory_store.search(f"{project_name} {task_title}")
        context_notes = ""
        if related_memories:
            top_rec = related_memories[0]
            context_notes = (
                f"Found historical fix: {top_rec.get('fix')} (Session: {top_rec.get('session')})"
            )
            self.log_activity(
                "Bug Investigator",
                "Historical Match Found",
                f"Matched prior resolution: {top_rec.get('fix')}",
            )

        # 3. Handoff from Bug Investigator to Code Fixer
        handoff_reason = f"Diagnostic complete. Identified prior resolution: {context_notes or 'Proceed with fix'}"
        self.log_activity(
            "Bug Investigator",
            "Agent Handoff",
            f"Handing off {task_id} to Code Fixer. Reason: {handoff_reason}",
        )
        handoff_event = self.memory_store.record_handoff(
            task_id=task_id,
            from_agent="bug_investigator",
            to_agent="code_fixer",
            reason=handoff_reason,
            context_summary=context_notes,
        )

        # 4. Code Fixer executes task using retrieved context
        self.log_activity(
            "Code Fixer",
            "Executing Solution",
            f"Applying fix using context from FalkorDB: {context_notes}",
        )
        self.memory_store.record_task(
            task_id=task_id,
            title=task_title,
            project_name=project_name,
            description=description,
            assigned_to="code_fixer",
            created_by="bug_investigator",
            status=TaskStatus.COMPLETED,
            context={"diagnosis": context_notes, "completed_by": "code_fixer"},
        )

        # 5. Memory Agent records the resolution
        self.log_activity(
            "Memory Agent",
            "Memory Updated",
            f"Task {task_id} marked COMPLETED and recorded in FalkorDB",
        )

        return {
            "task_id": task_id,
            "title": task_title,
            "status": "completed",
            "handoff": handoff_event.model_dump(),
            "context_shared": context_notes,
            "activity_logs": list(self.activity_logs[-10:]),
        }
