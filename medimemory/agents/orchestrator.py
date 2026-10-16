from __future__ import annotations

from typing import Optional
from ..graph_store import MediGraphStore
from ..schema import AgentState, Patient
from .guidance_agent import ContextGuidanceAgent
from .memory_agent import HealthMemoryAgent
from .safety_agent import SafetyCoordinationAgent


class MediMemoryOrchestrator:
    """
    Multi-Agent Orchestrator (LangGraph pattern)
    Coordinates:
      1. Health Memory Agent (Agent 1)
      2. Safety and Coordination Agent (Agent 3)
      3. Context and Guidance Agent (Agent 2)
    Maintains a single unified AgentState across all agents and ensures shared memory.
    """

    def __init__(self, graph_store: Optional[MediGraphStore] = None):
        self.graph_store = graph_store or MediGraphStore()
        self.memory_agent = HealthMemoryAgent(self.graph_store)
        self.safety_agent = SafetyCoordinationAgent()
        self.guidance_agent = ContextGuidanceAgent(self.graph_store)

    def run(
        self,
        user_message: str,
        patient_id: str = "patient_001",
        session_id: str = "session_1",
        session_date: str = "2026-10-01",
    ) -> AgentState:
        # Ensure base patient exists in graph
        existing_patient = self.graph_store.get_patient(patient_id)
        if not existing_patient:
            self.graph_store.save_patient(
                Patient(
                    id=patient_id,
                    name="Jason Franklin",
                    age=30,
                    gender="Male",
                    existing_conditions=[],
                    allergies=[],
                    medications=[],
                )
            )

        # Initialize shared agent state
        state = AgentState(
            patient_id=patient_id,
            session_id=session_id,
            session_date=session_date,
            user_message=user_message,
        )

        # Step 1: Health Memory Agent (Intake, parse, persist, retrieve)
        state = self.memory_agent.process(state)

        # Step 2: Safety & Coordination Agent (Deterministic clinical safety check)
        state = self.safety_agent.process(state)

        # Step 3: Context & Guidance Agent (Temporal reasoning, medical references, guidance)
        state = self.guidance_agent.process(state)

        return state
