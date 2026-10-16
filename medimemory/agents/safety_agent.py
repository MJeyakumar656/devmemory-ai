from __future__ import annotations

from typing import List
from ..medical_kb import scan_for_red_flags
from ..schema import AgentState, SafetyLevel


class SafetyCoordinationAgent:
    """
    Agent 3: Safety and Coordination Agent
    Evaluates clinical red flags deterministically (SNOOP criteria for headaches).
    Enforces non-prescriptive guidance (never blindly prescribe sodium or medications).
    Coordinates safety levels and ensures patient is directed to urgent care when appropriate.
    """

    def process(self, state: AgentState) -> AgentState:
        user_text = state.user_message.strip()

        # 1. Deterministic clinical red-flag scan
        detected_flags = scan_for_red_flags(user_text)

        # Also check if symptom is reported as severe or sudden
        if state.extracted_symptom:
            sym_name = state.extracted_symptom.name.lower()
            if "severe" in state.extracted_symptom.severity.lower() and "headache" in sym_name:
                if not any("sudden" in f.get("description", "").lower() for f in detected_flags):
                    detected_flags.append({
                        "pattern": "severe_headache",
                        "description": "Headache characterized by high severity",
                        "clinical_concern": "Secondary headache or vascular etiology needing medical review",
                        "urgency": "URGENT - Evaluation recommended if sudden or worsening",
                    })

        # 2. Assign safety levels based on deterministic findings
        if any(f.get("urgency", "").startswith("EMERGENCY") for f in detected_flags):
            state.safety_level = SafetyLevel.EMERGENCY
            state.requires_urgent_care = True
        elif any(f.get("urgency", "").startswith("URGENT") for f in detected_flags):
            state.safety_level = SafetyLevel.URGENT
            state.requires_urgent_care = True
        elif state.extracted_symptom:
            state.safety_level = SafetyLevel.MODERATE
            state.requires_urgent_care = False
        else:
            state.safety_level = SafetyLevel.ROUTINE
            state.requires_urgent_care = False

        state.red_flags = [f["description"] for f in detected_flags]

        # 3. Log agent action in shared state
        state.graph_trail.append({
            "agent": "Safety & Coordination Agent",
            "action": "SAFETY_ASSESSMENT_COMPLETED",
            "safety_level": state.safety_level.value,
            "red_flags_count": len(detected_flags),
            "urgent_care_required": state.requires_urgent_care,
        })

        return state

    def generate_safety_warnings(self, state: AgentState) -> List[str]:
        """Provides standard clinical red-flag warnings that must accompany headache assessments."""
        warnings = [
            "Sudden and severe 'thunderclap' onset (reaching peak intensity within seconds or minutes)",
            "Neurological deficits such as weakness on one side, numbness, confusion, or speech difficulty",
            "High fever accompanied by a stiff neck and sensitivity to light",
            "New changes in vision (such as sudden blurriness or double vision)",
        ]
        return warnings
