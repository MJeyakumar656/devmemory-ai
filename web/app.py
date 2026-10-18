from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from medimemory.agents.orchestrator import MediMemoryOrchestrator
from medimemory.graph_store import MediGraphStore
from medimemory.schema import Patient

from devmemory.agents.coordinator import AgentCoordinator
from devmemory.agents.memory_agent import MemoryAgent
from devmemory.agents.task_agent import TaskAgent
from devmemory.memory import MemoryStore as DevMemoryStore

app = FastAPI(
    title="DevMemory AI & MediMemory AI — Persistent Graph Teammate",
    description="FalkorDB Track 2 Hackathon Project: Multi-Agent Persistent Graph Memory",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize graph store and orchestrator
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_FILE = str(DATA_DIR / "graph_persistence.json")
DEVMEMORY_STORAGE = str(DATA_DIR / "devmemory_graph.json")

graph_store = MediGraphStore(storage_file=STORAGE_FILE)
orchestrator = MediMemoryOrchestrator(graph_store=graph_store)

# DevMemory Store & Coordinator
dev_store = DevMemoryStore(storage_file=DEVMEMORY_STORAGE, use_local_fallback=True)
dev_coordinator = AgentCoordinator(memory_store=dev_store)

# Seed initial DevMemory if empty
if not dev_store.search("Vite failed to start"):
    dev_store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop conflicting background process on port 5173",
        session="October 12",
        evidence="Port 5173 was locked by a stale node.js background task.",
    )
    dev_mem_agent = MemoryAgent(dev_store)
    dev_mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Webpack Bundler",
        rationale="Initial legacy bundler in 2021",
        session="Legacy Setup",
        date="2021-06-10",
    )
    dev_mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Vite Bundler",
        rationale="Instant HMR and native ESM tooling",
        session="October 12",
        supersedes_title="Use Webpack Bundler",
        date="2026-10-12",
    )


# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatRequest(BaseModel):
    message: str
    patient_id: str = "patient_001"
    session_id: str = "session_2"
    session_date: str = "2026-10-22"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    template_path = Path(__file__).parent / "templates" / "devmemory.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.get("/medimemory", response_class=HTMLResponse)
async def serve_medimemory():
    template_path = Path(__file__).parent / "templates" / "index.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Processes patient message through the 3-agent pipeline."""
    state = orchestrator.run(
        user_message=req.message,
        patient_id=req.patient_id,
        session_id=req.session_id,
        session_date=req.session_date,
    )

    # Get updated graph visualization data
    graph_data = graph_store.export_graph_visualization(req.patient_id)

    return {
        "response": state.final_response,
        "session_id": state.session_id,
        "session_date": state.session_date,
        "safety_level": state.safety_level.value,
        "requires_urgent_care": state.requires_urgent_care,
        "red_flags": state.red_flags,
        "temporal_relations": [
            {
                "days_apart": tr.days_apart,
                "relationship_type": tr.relationship_type,
                "explanation": tr.explanation,
            }
            for tr in state.temporal_relations
        ],
        "assessment": state.assessment.model_dump() if state.assessment else None,
        "graph_trail": state.graph_trail,
        "graph": graph_data,
        "backend_mode": graph_store.mode,
    }


@app.get("/api/graph/{patient_id}")
async def get_graph(patient_id: str):
    """Returns nodes and links for interactive graph visualization."""
    return graph_store.export_graph_visualization(patient_id)


@app.get("/api/patient/{patient_id}")
async def get_patient_profile(patient_id: str):
    """Returns patient profile and historical events."""
    patient = graph_store.get_patient(patient_id) or Patient(id=patient_id)
    history = graph_store.get_patient_history(patient_id)
    return {
        "patient": patient.model_dump(),
        "history": history,
        "backend_mode": graph_store.mode,
    }


@app.post("/api/reset/{patient_id}")
async def reset_patient(patient_id: str):
    """Resets memory graph for the specified patient to allow clean demos."""
    graph_store.reset_patient(patient_id)
    # Re-initialize standard patient
    graph_store.save_patient(
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
    return {"status": "success", "message": f"Reset memory graph for patient {patient_id}"}


@app.post("/api/demo/{scenario}")
async def run_demo_scenario(scenario: str):
    """
    Executes one of the hackathon demonstration milestones:
    - 'session1': Day 1 diet report ("I started a ketogenic diet today.")
    - 'session2': Day 21 headache report ("I've had a headache since this morning.")
    - 'redflag': Emergency red flag test ("Sudden thunderclap headache with stiff neck")
    """
    patient_id = "patient_001"

    if scenario == "session1":
        # Reset and run Day 1
        graph_store.reset_patient(patient_id)
        graph_store.save_patient(
            Patient(id=patient_id, name="Jason Franklin", age=30, gender="Male")
        )
        state = orchestrator.run(
            user_message="I started a ketogenic diet today.",
            patient_id=patient_id,
            session_id="session_1",
            session_date="2026-10-01",
        )
        return {
            "scenario": "session1",
            "message": "I started a ketogenic diet today.",
            "response": state.final_response,
            "session_date": "2026-10-01",
            "graph": graph_store.export_graph_visualization(patient_id),
            "state": state.model_dump(),
        }

    elif scenario == "session2":
        # Make sure session 1 is present in graph
        history = graph_store.get_patient_history(patient_id)
        if not history.get("lifestyles"):
            # Preload Session 1 if not already there
            orchestrator.run(
                user_message="I started a ketogenic diet today.",
                patient_id=patient_id,
                session_id="session_1",
                session_date="2026-10-01",
            )

        # Run Day 21
        state = orchestrator.run(
            user_message="I've had a headache since this morning.",
            patient_id=patient_id,
            session_id="session_2",
            session_date="2026-10-22",
        )
        return {
            "scenario": "session2",
            "message": "I've had a headache since this morning.",
            "response": state.final_response,
            "session_date": "2026-10-22",
            "graph": graph_store.export_graph_visualization(patient_id),
            "state": state.model_dump(),
        }

    elif scenario == "redflag":
        state = orchestrator.run(
            user_message="I have a sudden thunderclap headache with a stiff neck and high fever.",
            patient_id=patient_id,
            session_id="session_emergency",
            session_date="2026-10-22",
        )
        return {
            "scenario": "redflag",
            "message": "I have a sudden thunderclap headache with a stiff neck and high fever.",
            "response": state.final_response,
            "session_date": "2026-10-22",
            "graph": graph_store.export_graph_visualization(patient_id),
            "state": state.model_dump(),
        }

    raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario}")


# =============================================================
# DEVMEMORY AI ROUTES (TRACK 2: PERSISTENT GRAPH TEAMMATE)
# =============================================================

class DevChatRequest(BaseModel):
    message: str
    project: str = "Job Portal"
    session: str = "October 18 Session"


class DevWorkflowRequest(BaseModel):
    task_title: str
    project: str = "Job Portal"
    description: str = ""


@app.get("/devmemory", response_class=HTMLResponse)
async def serve_devmemory():
    template_path = Path(__file__).parent / "templates" / "devmemory.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.post("/api/devmemory/chat")
async def devmemory_chat(req: DevChatRequest):
    """Processes developer questions or records fixes through DevMemory coordinator."""
    result = dev_coordinator.handle_request(
        user_message=req.message,
        project_name=req.project,
        session_name=req.session,
    )
    return result


@app.get("/api/devmemory/graph")
async def get_devmemory_graph(project: Optional[str] = None):
    """Exports DevMemory graph nodes and links for visualization."""
    return dev_store.export_graph_visualization(project)


@app.post("/api/devmemory/workflow")
async def trigger_devmemory_workflow(req: DevWorkflowRequest):
    """Triggers Bug Investigator -> Code Fixer collaborative workflow and handoff."""
    return dev_coordinator.execute_multi_agent_workflow(
        task_title=req.task_title,
        project_name=req.project,
        description=req.description,
    )


@app.get("/api/devmemory/tasks")
async def get_devmemory_tasks(project: Optional[str] = None):
    """Returns tasks, handoffs, and activity logs."""
    return {
        "tasks": dev_store.get_tasks(project),
        "handoffs": dev_store.get_handoffs(),
        "logs": dev_coordinator.activity_logs,
    }


@app.get("/api/devmemory/evidence")
async def get_devmemory_evidence(project: Optional[str] = None):
    """Returns verified answer evidence records."""
    ctx = dev_store.retrieve_context_with_evidence("Vite failed to start", project)
    return {
        "evidence": [e.model_dump() for e in ctx["evidence"]],
        "incidents": ctx["incidents"],
        "decisions": ctx["decisions"],
    }


@app.post("/api/devmemory/reset")
async def reset_devmemory():
    """Resets DevMemory graph."""
    dev_store.reset(clear_persistent_file=True)
    dev_coordinator.activity_logs.clear()
    return {"status": "success", "message": "DevMemory reset"}


class CreateSpaceRequest(BaseModel):
    name: str
    description: str = ""


class SwitchSpaceRequest(BaseModel):
    space: str


class SaveMemoryRequest(BaseModel):
    memory_type: str = "incident"  # incident, decision, task, fact
    project: str = "Job Portal"
    title: str
    details: str
    session: str = "Session Oct 18"
    evidence: str = ""
    supersedes: Optional[str] = None
    assigned_to: str = "task_agent"


@app.get("/api/devmemory/spaces")
async def get_spaces():
    """Returns list of all available memory spaces."""
    return {
        "active_space": dev_store.active_space,
        "spaces": dev_store.list_spaces(),
    }


@app.post("/api/devmemory/spaces/create")
async def create_new_space(req: CreateSpaceRequest):
    """Creates a new isolated memory space."""
    res = dev_store.create_space(req.name, req.description)
    dev_store.switch_space(req.name)
    return {
        "status": "success",
        "space": res,
        "active_space": dev_store.active_space,
    }


@app.post("/api/devmemory/spaces/switch")
async def switch_active_space(req: SwitchSpaceRequest):
    """Switches active memory space."""
    active = dev_store.switch_space(req.space)
    return {
        "status": "success",
        "active_space": active,
    }


@app.post("/api/devmemory/save")
async def save_custom_memory_endpoint(req: SaveMemoryRequest):
    """Saves custom memory (incident, decision, task, fact) to active FalkorDB space."""
    result = dev_store.save_custom_memory(
        memory_type=req.memory_type,
        project=req.project,
        title=req.title,
        details=req.details,
        session=req.session,
        evidence=req.evidence,
        supersedes_title=req.supersedes,
        assigned_to=req.assigned_to,
    )
    dev_coordinator.log_activity(
        "Memory Agent",
        f"Saved {req.memory_type.capitalize()}",
        f"'{req.title}' for {req.project} (Space: {dev_store.active_space})",
    )
    return {
        "status": "success",
        "data": result,
        "active_space": dev_store.active_space,
    }


