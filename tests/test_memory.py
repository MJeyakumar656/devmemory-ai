from devmemory.agent import DevMemoryAgent
from devmemory.memory import MemoryStore


def test_memory_store_round_trip():
    store = MemoryStore(graph_name="devmemory_test", use_local_fallback=True, auto_reset=True)

    store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop the conflicting process",
        session="October 12",
        evidence="The app was blocked by a stale port process.",
    )

    results = store.search("Vite startup error")
    assert any("Job Portal" in item["project"] for item in results)
    assert any("Stop the conflicting process" in item["fix"] for item in results)


def test_agent_uses_memory_context():
    store = MemoryStore(graph_name="devmemory_agent_test", use_local_fallback=True, auto_reset=True)
    store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop the conflicting process",
        session="October 12",
        evidence="The app was blocked by a stale port process.",
    )

    agent = DevMemoryAgent(memory_store=store)
    answer = agent.answer("What did we do to fix the Vite startup error in the Job Portal project?")

    assert "conflicting process" in answer.lower()
    assert "job portal" in answer.lower()
