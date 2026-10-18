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
    title="DevMemory AI — Persistent Graph Teammate",
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

# Always ensure demo seed data exists in the 'default' space
_current_space = dev_store.active_space
dev_store.switch_space("default")
_default_demo_incidents = (
    (
        "Vite failed to start",
        "Stop conflicting background process on port 5173",
        "October 12",
        "Port 5173 was locked by a stale node.js background task.",
    ),
    (
        "CSS styles not loading in production build",
        "Added postcss and autoprefixer to vite.config.js build plugins",
        "October 14",
        "Missing postcss config caused Tailwind purge to strip all classes.",
    ),
    (
        "API calls failing with CORS error on deployment",
        "Set VITE_API_URL env variable and added CORS headers in FastAPI backend",
        "October 15",
        "Frontend was calling localhost:8000 instead of the deployed API URL.",
    ),
)
for _issue, _fix, _session, _evidence in _default_demo_incidents:
    if not dev_store.search(_issue):
        dev_store.record_project_memory(
            project="Job Portal",
            issue=_issue,
            fix=_fix,
            session=_session,
            evidence=_evidence,
        )

_mem_agent = MemoryAgent(dev_store)
_existing_decisions = {
    decision.get("title") for decision in dev_store.get_decisions("Job Portal")
}
if "Use Webpack Bundler" not in _existing_decisions:
    _mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Webpack Bundler",
        rationale="Initial legacy bundler in 2021",
        session="Legacy Setup",
        date="2021-06-10",
    )
if "Use Vite Bundler" not in _existing_decisions:
    _mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Vite Bundler",
        rationale="Instant HMR and native ESM tooling — replaces Webpack",
        session="October 12",
        supersedes_title="Use Webpack Bundler",
        date="2026-10-12",
    )
# Restore whatever space was active before
dev_store.switch_space(_current_space)


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
    conversation_id: Optional[str] = None


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
    active_space = dev_store.active_space
    conversation_id = req.conversation_id
    if conversation_id is None:
        conversation = dev_store.create_chat_thread(req.project)
        conversation_id = conversation["id"]
    thread = dev_store.get_chat_thread(conversation_id)
    if thread is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found in the active memory space.",
        )
    current_thread_context = "\n".join(
        f"Earlier user message: {exchange.get('user_message', '')}\n"
        f"Earlier assistant response: {exchange.get('assistant_response', '')[:500]}"
        for exchange in thread["exchanges"][-5:]
    )
    shared_space_context = "\n".join(
        f"Earlier saved conversation from {exchange.get('session') or 'a previous session'} "
        f"(project: {exchange.get('project') or 'unspecified'}):\n"
        f"User: {exchange.get('user_message', '')}\n"
        f"Assistant: {exchange.get('assistant_response', '')[:500]}"
        for exchange in dev_store.list_recent_chat_exchanges(
            exclude_conversation_id=conversation_id,
            limit=8,
        )
    )
    conversation_context = "\n\n".join(
        context for context in (current_thread_context, shared_space_context) if context
    )
    result = dev_coordinator.handle_request(
        user_message=req.message,
        project_name=req.project,
        session_name=req.session,
        conversation_context=conversation_context,
    )

    # If active space has no relevant memory, transparently search the default space
    answer = result.get("response", "")
    if "could not find matching memories" in answer.lower():
        _saved_space = dev_store.active_space
        if _saved_space != "default":
            try:
                dev_store.switch_space("default")
                fallback_result = dev_coordinator.handle_request(
                    user_message=req.message,
                    project_name=req.project,
                    session_name=req.session,
                    conversation_context=conversation_context,
                )
            finally:
                dev_store.switch_space(_saved_space)
            fallback_answer = fallback_result.get("answer", "")
            if "could not find matching memories" not in fallback_answer.lower():
                fallback_result["space_note"] = (
                    f"ℹ️ Retrieved from **default** space — current space '{_saved_space}' has no memories yet."
                )
                result = fallback_result

    if dev_store.active_space != active_space:
        dev_store.switch_space(active_space)
    dev_store.record_conversation(
        project_name=req.project,
        user_message=req.message,
        assistant_response=result.get("answer", result.get("response", "")),
        session_name=req.session,
        conversation_id=conversation_id,
    )
    result["conversation_id"] = conversation_id
    result["active_space"] = active_space

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
    """Resets the active custom space, including its graph-backed conversations."""
    if dev_store.active_space == "default":
        raise HTTPException(
            status_code=403,
            detail="The default memory space and its chat history are protected from reset.",
        )
    dev_store.reset()
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


class SaveConversationRequest(BaseModel):
    space_id: str
    project: str
    user_message: str
    assistant_response: str
    session: str = "Current Session"


class CreateChatConversationRequest(BaseModel):
    project: str = "Job Portal"


@app.get("/api/devmemory/spaces")
async def get_spaces():
    """Returns list of all available memory spaces."""
    return {
        "active_space": dev_store.active_space,
        "spaces": dev_store.list_spaces(),
    }


@app.get("/api/devmemory/conversations")
async def get_chat_conversations():
    """Returns persistent chat conversations in the active memory space."""
    return {
        "active_space": dev_store.active_space,
        "conversations": dev_store.list_chat_threads(),
    }


@app.post("/api/devmemory/conversations")
async def create_chat_conversation(req: CreateChatConversationRequest):
    """Creates a persistent conversation thread in the active memory space."""
    project = req.project.strip()
    if not project:
        raise HTTPException(status_code=422, detail="A project is required.")
    conversation = dev_store.create_chat_thread(project)
    return {
        "status": "success",
        "conversation": conversation,
        "active_space": dev_store.active_space,
    }


@app.get("/api/devmemory/conversations/{conversation_id}")
async def get_chat_conversation(conversation_id: str):
    """Returns a conversation and its saved exchanges from the active space."""
    conversation = dev_store.get_chat_thread(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"conversation": conversation, "active_space": dev_store.active_space}


@app.post("/api/devmemory/spaces/create")
async def create_new_space(req: CreateSpaceRequest):
    """Creates a new isolated memory space."""
    existing_ids = {space["id"] for space in dev_store.list_spaces()}
    res = dev_store.create_space(req.name, req.description)
    dev_store.switch_space(req.name)
    return {
        "status": "success",
        "space": res,
        "created": res["id"] not in existing_ids,
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


@app.delete("/api/devmemory/spaces/{space_id}")
async def delete_memory_space(space_id: str):
    """Deletes a user-created memory space and its graph data."""
    if space_id == "default":
        raise HTTPException(status_code=400, detail="The default memory space cannot be deleted.")
    if not dev_store.delete_space(space_id):
        raise HTTPException(status_code=404, detail="Memory space not found.")
    return {
        "status": "success",
        "active_space": dev_store.active_space,
    }


@app.post("/api/devmemory/conversations/save")
async def save_chat_conversation(req: SaveConversationRequest):
    """Persists a user-selected chat exchange in its active memory space."""
    if req.space_id != dev_store.active_space:
        raise HTTPException(
            status_code=409,
            detail="The active memory space changed. Switch back and save the conversation again.",
        )
    user_message = req.user_message.strip()
    assistant_response = req.assistant_response.strip()
    project = req.project.strip()
    if not user_message or not assistant_response or not project:
        raise HTTPException(
            status_code=422,
            detail="A project, user message, and assistant response are required.",
        )
    record = dev_store.record_conversation(
        project_name=project,
        user_message=user_message,
        assistant_response=assistant_response,
        session_name=req.session.strip() or "Current Session",
    )
    dev_coordinator.log_activity(
        "Memory Agent",
        "Conversation Saved",
        f"Saved a chat exchange for {project} in space {req.space_id}.",
    )
    return {"status": "success", "conversation": record, "active_space": dev_store.active_space}


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
