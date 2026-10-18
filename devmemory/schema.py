from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    USER = "User"
    PROJECT = "Project"
    SESSION = "Session"
    ERROR = "Error"
    SOLUTION = "Solution"
    DECISION = "Decision"
    TASK = "Task"
    AGENT = "Agent"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    HANDED_OFF = "handed_off"
    COMPLETED = "completed"
    FAILED = "failed"


class DecisionStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class User(BaseModel):
    id: str = "user_001"
    name: str = "Developer"
    role: str = "Software Engineer"


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    tech_stack: List[str] = Field(default_factory=lambda: ["React", "Vite", "Node.js"])


class Session(BaseModel):
    id: str
    name: str
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    user_id: str = "user_001"
    project_id: str = "project_001"


class ErrorIncident(BaseModel):
    id: str
    title: str
    project_id: str
    symptoms: str = ""
    stack_trace: str = ""
    session_id: str = ""
    resolved: bool = True


class Solution(BaseModel):
    id: str
    summary: str
    error_id: str
    steps: List[str] = Field(default_factory=list)
    code_snippet: str = ""
    session_id: str = ""
    verified: bool = True


class Decision(BaseModel):
    id: str
    title: str
    rationale: str
    project_id: str
    session_id: str = ""
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    status: DecisionStatus = DecisionStatus.ACTIVE
    superseded_by: Optional[str] = None


class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    project_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_by: str = "coordinator"
    assigned_to: str = "task_agent"
    context: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class AgentProfile(BaseModel):
    id: str
    name: str
    role: str
    status: str = "idle"


class HandoffEvent(BaseModel):
    task_id: str
    from_agent: str
    to_agent: str
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    reason: str
    context_summary: str = ""


class MemoryEvidence(BaseModel):
    source_type: str
    source_name: str
    relation: str
    target_type: str
    target_name: str
    session: str = ""
    date: str = ""
    confidence: float = 0.95
    notes: str = ""


class AgentResponse(BaseModel):
    answer: str
    evidence: List[MemoryEvidence] = Field(default_factory=list)
    retrieved_records: List[Dict[str, Any]] = Field(default_factory=list)
    tasks_involved: List[Task] = Field(default_factory=list)
    handoffs: List[HandoffEvent] = Field(default_factory=list)
    confidence: float = 0.95
    backend_mode: str = "falkordb"
    reasoning_mode: str = "deterministic"
    reasoning_warning: Optional[str] = None
