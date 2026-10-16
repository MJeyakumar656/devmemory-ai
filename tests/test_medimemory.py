import os
import pytest
from medimemory.agents.orchestrator import MediMemoryOrchestrator
from medimemory.graph_store import MediGraphStore
from medimemory.schema import FactSource, SafetyLevel


@pytest.fixture
def clean_store(tmp_path):
    storage_path = str(tmp_path / "test_graph.json")
    store = MediGraphStore(
        graph_name="test_medimemory",
        storage_file=storage_path,
    )
    store.reset_patient("patient_001")
    return store


def test_session_1_remember_diet(clean_store):
    orchestrator = MediMemoryOrchestrator(graph_store=clean_store)

    # Day 1: Patient reports diet change
    state1 = orchestrator.run(
        user_message="I started a ketogenic diet today.",
        patient_id="patient_001",
        session_id="session_1",
        session_date="2026-10-01",
    )

    assert state1.extracted_lifestyle is not None
    assert "Ketogenic" in state1.extracted_lifestyle.name
    assert state1.extracted_lifestyle.start_date == "2026-10-01"
    assert state1.extracted_lifestyle.source == FactSource.PATIENT_REPORT
    assert state1.safety_level == SafetyLevel.ROUTINE

    # Check graph persistence
    history = clean_store.get_patient_history("patient_001")
    assert len(history["lifestyles"]) == 1
    assert "Ketogenic" in history["lifestyles"][0]["name"]


def test_session_2_connect_headache_and_temporal_reasoning(clean_store):
    orchestrator = MediMemoryOrchestrator(graph_store=clean_store)

    # Session 1: Day 1
    orchestrator.run(
        user_message="I started a ketogenic diet today.",
        patient_id="patient_001",
        session_id="session_1",
        session_date="2026-10-01",
    )

    # Session 2: Day 21 (21 days later)
    state2 = orchestrator.run(
        user_message="I've had a headache since this morning.",
        patient_id="patient_001",
        session_id="session_2",
        session_date="2026-10-22",
    )

    assert state2.extracted_symptom is not None
    assert state2.extracted_symptom.name.lower() == "headache"

    # Verify temporal reasoning
    assert len(state2.temporal_relations) == 1
    rel = state2.temporal_relations[0]
    assert rel.days_apart == 21
    assert "not proven cause" in rel.explanation.lower()

    # Verify guidance & evidence
    assert state2.assessment is not None
    assert state2.assessment.confidence_score > 70
    assert len(state2.assessment.possibilities) > 0
    assert len(state2.medical_facts) > 0

    # Verify response safety: contains reference to diet, hydration, and emergency warning signs
    response_lower = state2.final_response.lower()
    assert "ketogenic diet" in response_lower
    assert "three weeks ago" in response_lower or "21 days" in response_lower
    assert "hydration" in response_lower
    assert "seek" in response_lower
    assert "stiff neck" in response_lower


def test_safety_agent_catches_emergency_red_flags(clean_store):
    orchestrator = MediMemoryOrchestrator(graph_store=clean_store)

    # Patient reports sudden thunderclap headache with stiff neck and high fever
    state = orchestrator.run(
        user_message="I have the worst headache of my life, sudden thunderclap onset, high fever and a stiff neck.",
        patient_id="patient_001",
        session_id="session_redflag",
        session_date="2026-10-22",
    )

    assert state.safety_level == SafetyLevel.EMERGENCY
    assert state.requires_urgent_care is True
    assert len(state.red_flags) >= 2
    assert "urgent medical notice" in state.final_response.lower()


def test_persistent_memory_across_restarts(tmp_path):
    storage_path = str(tmp_path / "persistent_graph.json")

    # Instance 1 stores Session 1
    store1 = MediGraphStore(storage_file=storage_path)
    orchestrator1 = MediMemoryOrchestrator(graph_store=store1)
    orchestrator1.run(
        user_message="I started a ketogenic diet today.",
        patient_id="patient_001",
        session_id="session_1",
        session_date="2026-10-01",
    )

    # Simulate app restart: New instance pointing to same persistence
    store2 = MediGraphStore(storage_file=storage_path)
    orchestrator2 = MediMemoryOrchestrator(graph_store=store2)

    # Session 2: Day 21
    state2 = orchestrator2.run(
        user_message="I've had a headache since this morning.",
        patient_id="patient_001",
        session_id="session_2",
        session_date="2026-10-22",
    )

    assert len(state2.temporal_relations) == 1
    assert state2.temporal_relations[0].days_apart == 21
    assert "ketogenic diet" in state2.final_response.lower()


def test_fastapi_web_endpoints():
    from starlette.testclient import TestClient
    from web.app import app

    client = TestClient(app)

    # 1. Test index page
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "MediMemory AI" in res_index.text

    # 2. Test demo Session 1
    res_s1 = client.post("/api/demo/session1")
    assert res_s1.status_code == 200
    data_s1 = res_s1.json()
    assert data_s1["scenario"] == "session1"
    assert "Ketogenic Diet" in data_s1["response"]

    # 3. Test demo Session 2
    res_s2 = client.post("/api/demo/session2")
    assert res_s2.status_code == 200
    data_s2 = res_s2.json()
    assert data_s2["scenario"] == "session2"
    assert "three weeks ago" in data_s2["response"].lower() or "21 days" in data_s2["response"].lower()
    assert len(data_s2["graph"]["nodes"]) >= 5

    # 4. Test demo Red Flag
    res_rf = client.post("/api/demo/redflag")
    assert res_rf.status_code == 200
    data_rf = res_rf.json()
    assert "urgent medical notice" in data_rf["response"].lower()

