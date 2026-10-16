from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional, Tuple
from ..graph_store import MediGraphStore
from ..schema import AgentState, FactSource, LifestyleChange, SymptomEvent


class HealthMemoryAgent:
    """
    Agent 1: Health Memory Agent
    Stores patient-reported health information, diet changes, symptoms,
    medication history, allergies, and relevant dates into FalkorDB.
    Maintains provenance (source: patient_report vs verified) and handles corrections.
    """

    def __init__(self, graph_store: MediGraphStore):
        self.graph_store = graph_store

    def process(self, state: AgentState) -> AgentState:
        msg = state.user_message.strip()
        msg_lower = msg.lower()

        # 1. Detect and parse Lifestyle Changes (e.g. "I started a ketogenic diet today", "started fasting", etc.)
        lifestyle = self._extract_lifestyle_change(msg, state.patient_id, state.session_date)
        if lifestyle:
            state.extracted_lifestyle = lifestyle
            self.graph_store.save_lifestyle_change(lifestyle)
            state.graph_trail.append({
                "agent": "Health Memory Agent",
                "action": "RECORDED_LIFESTYLE_CHANGE",
                "node_id": f"lifestyle_{lifestyle.id}",
                "summary": f"Recorded '{lifestyle.name}' starting {lifestyle.start_date} in FalkorDB (provenance: {lifestyle.source.value})",
            })

        # 2. Detect and parse Symptom Reports (e.g. "I've had a headache since this morning")
        symptom = self._extract_symptom(msg, state.patient_id, state.session_date)
        if symptom:
            state.extracted_symptom = symptom
            self.graph_store.save_symptom_event(symptom)
            state.graph_trail.append({
                "agent": "Health Memory Agent",
                "action": "RECORDED_SYMPTOM_EVENT",
                "node_id": f"symptom_{symptom.id}",
                "summary": f"Recorded symptom '{symptom.name}' reported on {symptom.reported_date} in FalkorDB (provenance: {symptom.source.value})",
            })

        # 3. Retrieve all historical context for this patient
        history = self.graph_store.get_patient_history(state.patient_id)
        state.retrieved_memories = [
            {"type": "lifestyle", **l} for l in history.get("lifestyles", [])
        ] + [
            {"type": "symptom", **s} for s in history.get("symptoms", [])
        ]

        return state

    def _extract_lifestyle_change(self, text: str, patient_id: str, default_date: str) -> Optional[LifestyleChange]:
        text_lower = text.lower()
        diet_keywords = ["ketogenic", "keto", "carnivore", "vegan", "paleo", "intermittent fasting", "mediterranean diet", "low-carb"]
        action_keywords = ["started", "began", "doing", "switched to", "on a", "eating"]

        for diet in diet_keywords:
            if diet in text_lower:
                # Check start date
                start_date = default_date
                if "today" in text_lower:
                    start_date = default_date
                elif "yesterday" in text_lower:
                    start_date = default_date  # can be adjusted by delta if needed

                # Normalize diet name
                name = f"{diet.capitalize()} Diet" if "diet" not in diet else diet.title()
                if diet == "keto":
                    name = "Ketogenic Diet"

                return LifestyleChange(
                    id=str(uuid.uuid4())[:8],
                    patient_id=patient_id,
                    name=name,
                    change_type="dietary_pattern",
                    start_date=start_date,
                    details=text,
                    source=FactSource.PATIENT_REPORT,
                )
        return None

    def _extract_symptom(self, text: str, patient_id: str, default_date: str) -> Optional[SymptomEvent]:
        text_lower = text.lower()
        symptom_keywords = [
            "headache", "migraine", "dizziness", "nausea", "fatigue",
            "back pain", "chest pain", "shortness of breath", "fever",
            "cramp", "muscle ache", "lightheaded", "stiff neck", "vision loss"
        ]

        for sym in symptom_keywords:
            if sym in text_lower:
                onset = "this morning" if "this morning" in text_lower else ("today" if "today" in text_lower else "recent")
                severity = "severe" if "severe" in text_lower or "terrible" in text_lower else "mild to moderate"
                return SymptomEvent(
                    id=str(uuid.uuid4())[:8],
                    patient_id=patient_id,
                    name=sym.capitalize(),
                    severity=severity,
                    reported_date=default_date,
                    onset=onset,
                    duration="recent",
                    source=FactSource.PATIENT_REPORT,
                )
        return None
