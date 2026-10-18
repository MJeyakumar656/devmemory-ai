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


def test_coordinator_plans_uses_memory_tools_and_evaluates_grounding(clean_memory_store, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = clean_memory_store
    store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop the conflicting process on port 5173",
        session="October 12",
        evidence="A stale server held port 5173.",
    )

    result = AgentCoordinator(memory_store=store).handle_request(
        "What did we do to fix the Vite startup error?",
        project_name="Job Portal",
    )

    assert result["answer"] == result["response"]
    assert [step["status"] for step in result["plan"]] == [
        "completed",
        "skipped",
        "completed",
        "completed",
        "completed",
    ]
    assert {tool["name"] for tool in result["tools_used"]} == {
        "MemoryAgent.extract_from_conversation",
        "MemoryStore.retrieve_context_with_evidence",
    }
    assert result["evaluation"]["passed"] is True
    assert result["evaluation"]["answer_grounded"] is True
    assert result["reasoning_mode"] == "deterministic"


def test_quick_demo_prompts_return_relevant_distinct_answers(clean_memory_store, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = clean_memory_store
    store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop the conflicting process on port 5173",
        session="Session Oct 12",
        evidence="A stale background server was using port 5173.",
    )
    memory_agent = MemoryAgent(memory_store=store)
    memory_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Webpack Bundler",
        rationale="Existing project setup",
        session="Session Jan 2021",
    )
    memory_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Vite Bundler",
        rationale="Instant HMR and fast ESM startup",
        session="Session Oct 2026",
        supersedes_title="Use Webpack Bundler",
    )
    coordinator = AgentCoordinator(memory_store=store)

    incident = coordinator.handle_request(
        "My React project had a Vite startup error last week. What did we do to fix it?",
        project_name="Job Portal",
    )
    decision = coordinator.handle_request(
        "What bundler decision did we make for Job Portal?",
        project_name="Job Portal",
    )
    saved = coordinator.handle_request(
        "We resolved the React hydration error by adding suppressHydrationWarning to layout.tsx in Session Oct 18.",
        project_name="Job Portal",
        session_name="Session Oct 18",
    )

    assert "port 5173" in incident["answer"]
    assert "Active Decision" in decision["answer"]
    assert "superseded" in decision["answer"].lower()
    assert "conflicting process" not in decision["answer"].lower()
    assert "Saved to graph memory" in saved["answer"]
    assert "suppressHydrationWarning" in saved["answer"]
    assert len({incident["answer"], decision["answer"], saved["answer"]}) == 3
    assert any(
        record["issue"] == "React hydration error"
        for record in store.search("React hydration error")
    )


def test_coordinator_reports_when_no_memory_evidence_exists(clean_memory_store):
    result = AgentCoordinator(memory_store=clean_memory_store).handle_request(
        "What fixed the unknown issue?"
    )

    assert result["evaluation"]["passed"] is False
    assert result["evaluation"]["answer_grounded"] is False
    assert "No matching evidence" in result["evaluation"]["feedback"]


def test_chat_falls_back_to_default_space_and_restores_active_space(clean_memory_store, monkeypatch):
    from starlette.testclient import TestClient
    import web.app as web_app

    store = clean_memory_store
    store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop the conflicting process on port 5173",
        session="October 12",
        evidence="A stale server held port 5173.",
    )
    store.create_space("Empty Space")
    store.switch_space("Empty Space")
    monkeypatch.setattr(web_app, "dev_store", store)
    monkeypatch.setattr(web_app, "dev_coordinator", AgentCoordinator(memory_store=store))

    response = TestClient(web_app.app).post(
        "/api/devmemory/chat",
        json={
            "message": "What did we do to fix the Vite startup error?",
            "project": "Job Portal",
        },
    )

    assert response.status_code == 200
    assert "space_note" in response.json()
    assert store.active_space == "empty_space"


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
    assert c_data["answer"] == c_data["response"]
    assert "plan" in c_data
    assert "tools_used" in c_data
    assert "evaluation" in c_data
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


def test_delete_memory_space_clears_data_and_protects_default(tmp_path):
    store = MemoryStore(storage_file=str(tmp_path / "delete_space_test.json"))
    store.record_project_memory(
        project="Mobile App",
        issue="Build failure",
        fix="Update the build tools",
        session="Session 1",
        evidence="The build failed with an incompatible toolchain.",
    )
    store.create_space("Temporary Space")
    store.switch_space("Temporary Space")
    store.record_project_memory(
        project="Temporary App",
        issue="Temporary issue",
        fix="Temporary fix",
        session="Session 2",
        evidence="Temporary test evidence.",
    )

    assert store.delete_space("temporary-space")
    assert store.active_space == "default"
    assert [space["id"] for space in store.list_spaces()] == ["default"]
    assert len(store.search("Build failure")) == 1
    assert not store.delete_space("default")


def test_delete_memory_space_api(tmp_path, monkeypatch):
    from starlette.testclient import TestClient
    import web.app as web_app

    store = MemoryStore(storage_file=str(tmp_path / "api_delete_space_test.json"))
    store.create_space("Temporary Space")
    store.switch_space("Temporary Space")
    monkeypatch.setattr(web_app, "dev_store", store)
    client = TestClient(web_app.app)

    deleted = client.delete("/api/devmemory/spaces/temporary_space")
    assert deleted.status_code == 200
    assert deleted.json()["active_space"] == "default"
    assert client.delete("/api/devmemory/spaces/default").status_code == 400
    assert client.delete("/api/devmemory/spaces/missing").status_code == 404


def test_saved_conversations_are_retrievable_from_their_space(tmp_path):
    store = MemoryStore(storage_file=str(tmp_path / "conversation_memory_test.json"))
    store.create_space("Personal Project")
    store.switch_space("Personal Project")
    store.record_conversation(
        project_name="Personal Project",
        user_message="The dashboard uses a blue and charcoal color palette.",
        assistant_response="I will remember that visual preference for this project.",
        session_name="Session 1",
    )

    matches = store.search_conversations("What color palette did I choose?", "Personal Project")
    assert len(matches) == 1
    assert "blue and charcoal" in matches[0]["user_message"]

    response = TaskAgent(store).process_query(
        "What color palette did I choose?",
        "Personal Project",
    )
    assert "blue and charcoal" in response.answer
    assert response.evidence[0].target_type == "Conversation"


def test_default_space_cannot_be_reset_but_custom_space_can(tmp_path):
    store = MemoryStore(storage_file=str(tmp_path / "protected_default_test.json"))
    store.record_project_memory(
        project="Default Project",
        issue="Default issue",
        fix="Default fix",
        session="Session 1",
        evidence="Must remain protected.",
    )
    with pytest.raises(ValueError, match="default memory space is protected"):
        store.reset()
    assert len(store.search("Default issue")) == 1

    store.create_space("Custom Project")
    store.switch_space("Custom Project")
    store.record_conversation(
        project_name="Custom Project",
        user_message="Remember this custom chat.",
        assistant_response="Saved custom conversation.",
        session_name="Session 2",
    )
    store.reset()
    assert not store.search_conversations("custom chat", "Custom Project")
    store.switch_space("default")
    assert len(store.search("Default issue")) == 1


def test_conversation_save_and_default_reset_api(tmp_path, monkeypatch):
    from starlette.testclient import TestClient
    import web.app as web_app

    store = MemoryStore(storage_file=str(tmp_path / "conversation_api_test.json"))
    store.create_space("Chat Space")
    store.switch_space("Chat Space")
    monkeypatch.setattr(web_app, "dev_store", store)
    client = TestClient(web_app.app)

    saved = client.post(
        "/api/devmemory/conversations/save",
        json={
            "space_id": "chat_space",
            "project": "Chat Space",
            "user_message": "We prefer Python for the prototype.",
            "assistant_response": "I will remember this project preference.",
            "session": "Session 3",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["conversation"]["project"] == "Chat Space"

    store.switch_space("default")
    store.record_project_memory(
        project="Protected Project",
        issue="Protected default memory",
        fix="Keep this memory",
        session="Session 4",
        evidence="Default space is immutable from the reset action.",
    )
    assert client.post("/api/devmemory/reset").status_code == 403
    assert len(store.search("Protected default memory")) == 1


def test_chat_threads_persist_exchanges_and_supply_follow_up_context(tmp_path, monkeypatch):
    from starlette.testclient import TestClient
    import web.app as web_app

    store = MemoryStore(storage_file=str(tmp_path / "chat_threads_test.json"))
    store.create_space("Chat Threads")
    store.switch_space("Chat Threads")
    earlier_thread = store.create_chat_thread("Chat Threads")
    store.record_conversation(
        project_name="Chat Threads",
        user_message="I started a keto diet three weeks ago.",
        assistant_response="I will keep this health context in mind.",
        session_name="Earlier Session",
        conversation_id=earlier_thread["id"],
    )

    class CoordinatorStub:
        def __init__(self):
            self.contexts = []

        def handle_request(self, user_message, **kwargs):
            self.contexts.append(kwargs.get("conversation_context", ""))
            return {"answer": f"Reply to: {user_message}"}

    coordinator = CoordinatorStub()
    monkeypatch.setattr(web_app, "dev_store", store)
    monkeypatch.setattr(web_app, "dev_coordinator", coordinator)
    client = TestClient(web_app.app)

    created = client.post(
        "/api/devmemory/conversations",
        json={"project": "Chat Threads"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]

    for message in ("Remember the blue dashboard", "What color was the dashboard?"):
        response = client.post(
            "/api/devmemory/chat",
            json={
                "message": message,
                "project": "Chat Threads",
                "conversation_id": conversation_id,
            },
        )
        assert response.status_code == 200

    assert "I started a keto diet three weeks ago." in coordinator.contexts[0]
    assert "Earlier Session" in coordinator.contexts[0]
    conversation = client.get(
        f"/api/devmemory/conversations/{conversation_id}"
    ).json()["conversation"]
    assert len(conversation["exchanges"]) == 2
    assert conversation["title"] == "Remember the blue dashboard"
    assert "Remember the blue dashboard" in coordinator.contexts[1]
    listed_ids = {
        item["id"]
        for item in client.get("/api/devmemory/conversations").json()["conversations"]
    }
    assert conversation_id in listed_ids
    graph = store.export_graph_visualization()
    assert any(node["type"] == "ChatThread" for node in graph["nodes"])
    exchanges = [node for node in graph["nodes"] if node["type"] == "Conversation"]
    assert len(exchanges) == 3
    assert {exchange["label"] for exchange in exchanges} >= {
        "I started a keto diet three weeks ago.",
        "Remember the blue dashboard",
    }
    assert all(exchange["color"] == "#f472b6" for exchange in exchanges)
    assert sum(
        link["source"] == conversation_id and link["label"] == "HAS_EXCHANGE"
        for link in graph["links"]
    ) == 2


def test_chat_connects_keto_memory_to_headache_with_safe_guidance(tmp_path):
    store = MemoryStore(storage_file=str(tmp_path / "health_chat_context_test.json"))
    earlier_thread = store.create_chat_thread("Health Companion")
    store.record_conversation(
        project_name="Health Companion",
        user_message="I started a keto diet three weeks ago.",
        assistant_response="I'll remember that context.",
        session_name="Three weeks ago",
        conversation_id=earlier_thread["id"],
    )
    shared_context = "\n".join(
        f"Earlier saved conversation from {exchange['session']} "
        f"(project: {exchange['project']}):\n"
        f"User: {exchange['user_message']}\n"
        f"Assistant: {exchange['assistant_response']}"
        for exchange in store.list_recent_chat_exchanges(
            exclude_conversation_id="new_thread",
        )
    )

    response = TaskAgent(store).process_query(
        "I have a headache, what medicine can I take?",
        project_name="Health Companion",
        conversation_context=shared_context,
    )

    assert "keto diet" in response.answer
    assert "Three weeks ago" in response.answer
    assert "I started a keto diet three weeks ago." in response.answer
    assert "can't tell whether it is causing your headache" in response.answer
    assert "clinician or pharmacist" in response.answer
    assert "salt water is appropriate" in response.answer
    assert "drink salt water" not in response.answer
    assert response.evidence[0].target_type == "Conversation"
    assert response.evidence[0].session == "Three weeks ago"


def test_prior_chat_context_does_not_pollute_unrelated_graph_retrieval(tmp_path):
    store = MemoryStore(storage_file=str(tmp_path / "unrelated_chat_context_test.json"))
    previous_thread = store.create_chat_thread("Health Companion")
    store.record_conversation(
        project_name="Health Companion",
        user_message="My React app has a Vite startup error.",
        assistant_response="The issue was a process using port 5173.",
        session_name="Earlier coding chat",
        conversation_id=previous_thread["id"],
    )
    response = TaskAgent(store).process_query(
        "What is a good pasta sauce?",
        project_name="Health Companion",
        conversation_context=(
            "Earlier saved conversation from Earlier coding chat "
            "(project: Health Companion):\n"
            "User: My React app has a Vite startup error.\n"
            "Assistant: The issue was a process using port 5173."
        ),
    )

    assert "matching memories" in response.answer
    assert "Vite" not in response.answer
