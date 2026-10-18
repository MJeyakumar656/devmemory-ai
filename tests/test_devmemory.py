import os
import pytest
from devmemory.agents.coordinator import AgentCoordinator
from devmemory.agents.memory_agent import MemoryAgent
from devmemory.agents.task_agent import TaskAgent
from devmemory.memory import MemoryStore
from devmemory.schema import DecisionStatus, TaskStatus


@pytest.fixture
def clean_memory_store(tmp_path):
    storage_file = str(tmp_path / "test_devmemory_graph.json")
    store = MemoryStore(
        graph_name="test_devmemory",
        use_local_fallback=True,
        auto_reset=True,
        storage_file=storage_file,
    )
    return store


def test_milestone_1_connect_and_round_trip(clean_memory_store):
    """Milestone 1: Connect Python to FalkorDB / Graph Engine and round trip node creation."""
    store = clean_memory_store
    assert store.mode in ["falkordb", "local"]

    record = store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop the conflicting process on port 5173",
        session="October 12",
        evidence="Port 5173 was locked by a stale node background process.",
    )

    assert record["project"] == "Job Portal"
    assert record["issue"] == "Vite failed to start"

    results = store.search("Vite failed to start")
    assert len(results) >= 1
    assert results[0]["project"] == "Job Portal"
    assert "conflicting process" in results[0]["fix"].lower()


def test_milestone_2_persistence_across_restart(tmp_path):
    """Milestone 2: Save and retrieve memory after restarting the application."""
    storage_file = str(tmp_path / "persist_test.json")

    # Instance 1 records the incident
    store1 = MemoryStore(storage_file=storage_file, auto_reset=True)
    store1.record_project_memory(
        project="Job Portal",
        issue="Vite startup error",
        fix="Kill process using port 5173",
        session="Session A",
        evidence="Process ID 8492 held the socket open.",
    )

    # Instance 2 simulates application restart pointing to the same storage
    store2 = MemoryStore(storage_file=storage_file, auto_reset=False)
    results = store2.search("Vite startup error")

    assert len(results) >= 1
    assert results[0]["project"] == "Job Portal"
    assert "port 5173" in results[0]["fix"]


def test_milestone_3_task_agent_reasons_with_graph_evidence(clean_memory_store):
    """Milestone 3: Task Agent answers questions using retrieved graph evidence."""
    store = clean_memory_store
    store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop the conflicting process on port 5173",
        session="October 12",
        evidence="Stale background dev server was hogging port 5173.",
    )

    agent = TaskAgent(memory_store=store)
    response = agent.process_query("My React project had a Vite startup error last week. What did we do to fix it?")

    assert "Job Portal" in response.answer
    assert "conflicting process" in response.answer.lower() or "5173" in response.answer
    assert "October 12" in response.answer
    assert len(response.evidence) >= 1
    assert response.confidence > 0.9


def test_milestone_4_multi_agent_coordination_and_handoff(clean_memory_store):
    """Milestone 4: Coordinator dispatches task, Bug Investigator analyzes graph, hands off to Code Fixer."""
    store = clean_memory_store
    coordinator = AgentCoordinator(memory_store=store)

    # Seed prior memory
    store.record_project_memory(
        project="Job Portal",
        issue="Port 5173 conflict",
        fix="Run npx kill-port 5173",
        session="Session 10",
        evidence="Kill-port clears the stuck socket.",
    )

    workflow_result = coordinator.execute_multi_agent_workflow(
        task_title="Fix Vite Port 5173 conflict",
        project_name="Job Portal",
        description="Diagnose Vite dev server port binding issue",
        session_name="Session 11",
    )

    assert workflow_result["status"] == "completed"
    assert workflow_result["handoff"]["from_agent"] == "bug_investigator"
    assert workflow_result["handoff"]["to_agent"] == "code_fixer"
    assert "kill-port" in workflow_result["context_shared"].lower()

    # Verify task in graph
    tasks = store.get_tasks("Job Portal")
    assert len(tasks) >= 1
    assert any(t["id"] == workflow_result["task_id"] for t in tasks)

    handoffs = store.get_handoffs()
    assert len(handoffs) >= 1


def test_outdated_decisions_supersedes(clean_memory_store):
    """Tests architectural decision superseding (Webpack -> Vite)."""
    store = clean_memory_store
    mem_agent = MemoryAgent(memory_store=store)

    # Decision 1: Use Webpack
    mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Webpack Bundler",
        rationale="Standard bundler in 2021",
        session="Session Jan 2021",
    )

    # Decision 2: Switch to Vite (supersedes Webpack)
    mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Vite Bundler",
        rationale="Instant HMR and fast ESM startup",
        session="Session Oct 2026",
        supersedes_title="Use Webpack Bundler",
    )

    decisions = store.get_decisions("Job Portal")
    assert len(decisions) == 2

    webpack_dec = next(d for d in decisions if "Webpack" in d["title"])
    vite_dec = next(d for d in decisions if "Vite" in d["title"])

    assert webpack_dec["status"] == DecisionStatus.SUPERSEDED.value
    assert webpack_dec["superseded_by"] == "Use Vite Bundler"
    assert vite_dec["status"] == DecisionStatus.ACTIVE.value


def test_project_isolation(clean_memory_store):
    """Tests that memories and decisions are isolated across different projects."""
    store = clean_memory_store

    store.record_project_memory(
        project="Project Alpha",
        issue="Database Timeout",
        fix="Increase pool size to 20",
        session="Session A1",
        evidence="Postgres max connection limit reached.",
    )

    store.record_project_memory(
        project="Project Beta",
        issue="CSS Grid Overlap",
        fix="Set grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))",
        session="Session B1",
        evidence="Mobile viewport bug.",
    )

    res_alpha = store.search("Database Timeout")
    assert all(r["project"] == "Project Alpha" for r in res_alpha)

    res_beta = store.search("CSS Grid Overlap")
    assert all(r["project"] == "Project Beta" for r in res_beta)


def test_graph_visualization_export(clean_memory_store):
    """Tests that the graph can be exported for D3 or Streamlit visualization."""
    store = clean_memory_store
    store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop conflicting process",
        session="October 12",
        evidence="Port collision",
    )

    export = store.export_graph_visualization("Job Portal")
    assert "nodes" in export
    assert "links" in export
    assert export["total_nodes"] >= 4
    assert export["total_edges"] >= 3
    node_types = {n["type"] for n in export["nodes"]}
    assert "Project" in node_types
    assert "Error" in node_types
    assert "Solution" in node_types
    assert "Session" in node_types


def test_devmemory_fastapi_endpoints():
    """Tests the web UI endpoints and chat workflow via FastAPI TestClient."""
    from starlette.testclient import TestClient
    from web.app import app

    client = TestClient(app)

    # 1. DevMemory dashboard page
    res_page = client.get("/devmemory")
    assert res_page.status_code == 200
    assert "DevMemory AI" in res_page.text

    # 2. Graph export API
    res_graph = client.get("/api/devmemory/graph")
    assert res_graph.status_code == 200
    g_data = res_graph.json()
    assert "nodes" in g_data
    assert "links" in g_data

    # 3. Chat API
    res_chat = client.post(
        "/api/devmemory/chat",
        json={
            "message": "My React project had a Vite startup error last week. What did we do to fix it?",
            "project": "Job Portal",
            "session": "Session Oct 18",
        },
    )
    assert res_chat.status_code == 200
    c_data = res_chat.json()
    assert "response" in c_data
    assert "evidence" in c_data
    assert "conflicting" in c_data["response"].lower() or "port" in c_data["response"].lower()

    # 4. Multi-agent workflow trigger API
    res_wf = client.post(
        "/api/devmemory/workflow",
        json={
            "task_title": "Resolve Port 5173 Socket Lock",
            "project": "Job Portal",
            "description": "Kill stale process on port 5173",
        },
    )
    assert res_wf.status_code == 200
    wf_data = res_wf.json()
    assert wf_data["status"] == "completed"
    assert "handoff" in wf_data

    # 5. Spaces API
    res_spaces = client.get("/api/devmemory/spaces")
    assert res_spaces.status_code == 200
    sp_data = res_spaces.json()
    assert "active_space" in sp_data
    assert len(sp_data["spaces"]) >= 1

    # 6. Create New Space API
    res_new_space = client.post(
        "/api/devmemory/spaces/create",
        json={"name": "Mobile Gateway", "description": "Mobile services workspace"},
    )
    assert res_new_space.status_code == 200
    assert res_new_space.json()["space"]["name"] == "Mobile Gateway"

    # 7. Save Custom Memory API
    res_save = client.post(
        "/api/devmemory/save",
        json={
            "memory_type": "incident",
            "project": "Mobile App",
            "title": "Flutter build crash",
            "details": "Upgrade Gradle to 8.2",
            "session": "Session Oct 18",
            "evidence": "Incompatible Kotlin compiler daemon",
        },
    )
    assert res_save.status_code == 200
    assert res_save.json()["status"] == "success"


def test_memory_spaces_isolation(tmp_path):
    """Tests that separate memory spaces maintain completely isolated graphs."""
    storage_file = str(tmp_path / "spaces_test.json")
    store = MemoryStore(storage_file=storage_file, auto_reset=True)

    # Space 1: default
    store.record_project_memory(
        project="Web App",
        issue="Vite error",
        fix="Kill port",
        session="Session 1",
        evidence="Port collision",
    )
    assert len(store.search("Vite error")) == 1

    # Space 2: mobile_space
    store.create_space("mobile_space", "Flutter and iOS workspace")
    store.switch_space("mobile_space")
    assert len(store.search("Vite error")) == 0  # Web App memory not in mobile space!

    # Record in mobile_space
    store.record_project_memory(
        project="Mobile App",
        issue="Cocoapods build fail",
        fix="Run pod install --repo-update",
        session="Session 2",
        evidence="Outdated spec repo",
    )
    assert len(store.search("Cocoapods")) == 1

    # Switch back to default
    store.switch_space("default")
    assert len(store.search("Cocoapods")) == 0
    assert len(store.search("Vite error")) == 1


