from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FactSource(str, Enum):
    PATIENT_REPORT = "patient_report"
    MEDICALLY_VERIFIED = "medically_verified"
    AI_HYPOTHESIS = "ai_hypothesis"
    TRUSTED_REFERENCE = "trusted_reference"


class SafetyLevel(str, Enum):
    ROUTINE = "routine"
    MODERATE = "moderate"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class Patient(BaseModel):
    id: str = "patient_001"
    name: str = "Jason Franklin"
    age: int = 30
    gender: str = "Male"
    existing_conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)


class LifestyleChange(BaseModel):
    id: str
    patient_id: str
    name: str
    change_type: str = "diet"
    start_date: str
    details: str
    source: FactSource = FactSource.PATIENT_REPORT
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SymptomEvent(BaseModel):
    id: str
    patient_id: str
    name: str
    severity: str = "mild"
    reported_date: str
    onset: str = "this morning"
    duration: str = "hours"
    source: FactSource = FactSource.PATIENT_REPORT
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MedicalFact(BaseModel):
    id: str
    category: str
    title: str
    description: str
    citation: str
    url: Optional[str] = None
    red_flags: List[str] = Field(default_factory=list)
    relevant_symptoms: List[str] = Field(default_factory=list)


class TemporalRelation(BaseModel):
    from_node_id: str
    to_node_id: str
    days_apart: int
    relationship_type: str = "preceded_by"
    explanation: str


class GuidanceAssessment(BaseModel):
    id: str
    patient_id: str
    session_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    reasoning: str
    recommendation: str
    possibilities: List[Dict[str, Any]] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    red_flags_detected: List[str] = Field(default_factory=list)
    safety_level: SafetyLevel = SafetyLevel.ROUTINE
    confidence_score: int = 75
    evidence_sources: List[Dict[str, str]] = Field(default_factory=list)


class AgentState(BaseModel):
    patient_id: str
    session_id: str
    session_date: str
    user_message: str
    extracted_lifestyle: Optional[LifestyleChange] = None
    extracted_symptom: Optional[SymptomEvent] = None
    retrieved_memories: List[Dict[str, Any]] = Field(default_factory=list)
    temporal_relations: List[TemporalRelation] = Field(default_factory=list)
    medical_facts: List[MedicalFact] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    safety_level: SafetyLevel = SafetyLevel.ROUTINE
    requires_urgent_care: bool = False
    assessment: Optional[GuidanceAssessment] = None
    final_response: str = ""
    graph_trail: List[Dict[str, Any]] = Field(default_factory=list)
