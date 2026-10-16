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

app = FastAPI(
    title="MediMemory AI — A Persistent Health Companion",
    description="FalkorDB Track 2 Hackathon Project: Multi-Agent Persistent Graph Health Memory",
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

graph_store = MediGraphStore(storage_file=STORAGE_FILE)
orchestrator = MediMemoryOrchestrator(graph_store=graph_store)

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
