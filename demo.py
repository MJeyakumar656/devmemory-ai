from __future__ import annotations

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from devmemory.agents.coordinator import AgentCoordinator
from devmemory.agents.memory_agent import MemoryAgent
from devmemory.agents.task_agent import TaskAgent
from devmemory.memory import MemoryStore


def run_milestone_demo() -> None:
    print("=" * 75)
    print("   DevMemory AI -- Persistent Knowledge Graph Teammate")
    print("   FalkorDB Track 2: Multi-Agent AI Teammate with Graph Memory")
    print("=" * 75)

    storage_path = str(Path(__file__).parent / "data" / "devmemory_graph.json")
    store = MemoryStore(
        graph_name="devmemory_demo",
        storage_file=storage_path,
        auto_reset=True,
    )

    print(f"\n[Backend Mode]: {store.mode.upper()}")
    if store.mode == "falkordb":
        print(" Connected to live FalkorDB instance (Redis protocol on port 6379)")
    else:
        print(" Using Persistent Graph Fallback (Cypher-ready & JSON persistent)")
    print("-" * 75)

    # -------------------------------------------------------------
    # MILESTONE 1: Connect Python to FalkorDB
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" MILESTONE 1: Connect Python to FalkorDB / Graph Memory Engine")
    print("=" * 75)
    rec1 = store.record_project_memory(
        project="Job Portal",
        issue="Vite failed to start",
        fix="Stop conflicting background process on port 5173",
        session="October 12",
        evidence="Port 5173 was locked by a stale node.js background task.",
    )
    print(f" [+] Created Project node:    {rec1['project']}")
    print(f" [+] Created Error node:      {rec1['issue']}")
    print(f" [+] Created Solution node:   {rec1['fix']}")
    print(f" [+] Connected to Session:    {rec1['session']}")
    print(" [+] Cypher Relationship:     (:Project)-[:HAS_INCIDENT]->(:Error)-[:RESOLVED_BY]->(:Solution)-[:RECORDED_IN]->(:Session)")

    read_back = store.search("Vite failed to start")
    print(f" [+] Read back successfully: {len(read_back)} record(s) retrieved.")

    # -------------------------------------------------------------
    # MILESTONE 2: Save and retrieve memory across restart
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" MILESTONE 2: Save and Retrieve Memory (Persistence Across Restart)")
    print("=" * 75)
    print(" Simulating application restart... Initializing new store instance...")
    store_restarted = MemoryStore(
        graph_name="devmemory_demo",
        storage_file=storage_path,
        auto_reset=False,
    )
    cached_results = store_restarted.search("Vite failed to start")
    print(f" [+] Memories survived restart: {len(cached_results)} found.")
    print(f" [+] Restored Fix: {cached_results[0]['fix']}")
    print(f" [+] Restored Session: {cached_results[0]['session']}")

    # -------------------------------------------------------------
    # MILESTONE 3: Connect the LLM / Graph Reasoning (Receive -> Retrieve -> Reason -> Respond -> Remember)
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" MILESTONE 3: Task Agent Reasoning with Graph Evidence")
    print("=" * 75)
    task_agent = TaskAgent(memory_store=store_restarted)
    question = "My React project had a Vite startup error last week. What did we do to fix it?"
    print(f" User: \"{question}\"")
    print("\n [Workflow Execution]:")
    print("   1. Receive:  Ingested query from developer")
    print("   2. Retrieve: Queried FalkorDB graph for connected incident, solution, and session")
    print("   3. Reason:   Synthesized verified fix with citation and confidence score")
    print("   4. Respond:  Generated evidence-backed answer")
    print("   5. Remember: Provenance attached")

    agent_resp = task_agent.process_query(question)
    print(f"\n DevMemory AI Response:\n{agent_resp.answer}")
    print("\n [Answer Evidence]:")
    for ev in agent_resp.evidence:
        print(f"   * [{ev.source_type}: {ev.source_name}] --[{ev.relation}]--> [{ev.target_type}: {ev.target_name}] (Session: {ev.session})")
    print(f"   * Confidence: {agent_resp.confidence * 100:.0f}%")

    # -------------------------------------------------------------
    # MILESTONE 4: Add Multi-Agent Coordination & Task Handoff
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" MILESTONE 4: Multi-Agent Coordination & Task Handoff")
    print("=" * 75)
    coordinator = AgentCoordinator(memory_store=store_restarted)

    print(" Initiating collaborative diagnostic task across agents:")
    print("   Coordinator -> Bug Investigator -> Code Fixer -> Memory Agent")

    workflow = coordinator.execute_multi_agent_workflow(
        task_title="Diagnose & Fix Vite Port 5173 Collision",
        project_name="Job Portal",
        description="Check if port 5173 is locked and release the port",
        session_name="October 18 Session",
    )

    print(f"\n [+] Task ID:           {workflow['task_id']}")
    print(f" [+] Status:            {workflow['status'].upper()}")
    print(f" [+] Shared Context:    {workflow['context_shared']}")
    print(f" [+] Handoff From:      {workflow['handoff']['from_agent']}")
    print(f" [+] Handoff To:        {workflow['handoff']['to_agent']}")
    print(f" [+] Handoff Reason:    {workflow['handoff']['reason']}")

    # -------------------------------------------------------------
    # MILESTONE 5: Architectural Decisions & Outdated Decision Handling
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" MILESTONE 5: Outdated Decision Tracking (SUPERSEDES Edge) & Graph Export")
    print("=" * 75)
    mem_agent = MemoryAgent(memory_store=store_restarted)

    # Decision 1
    mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Webpack Bundler",
        rationale="Industry standard bundler in legacy setup",
        session="Initial Setup Session",
        date="2022-03-15",
    )
    # Decision 2: Supersedes Decision 1
    mem_agent.record_architectural_decision(
        project="Job Portal",
        title="Use Vite Bundler",
        rationale="Sub-second hot module replacement and native ESM",
        session="Migration Session",
        supersedes_title="Use Webpack Bundler",
        date="2026-10-18",
    )

    decisions = store_restarted.get_decisions("Job Portal")
    for d in decisions:
        status_tag = "[ACTIVE]" if d.get("status") == "active" else f"[SUPERSEDED by {d.get('superseded_by')}]"
        print(f" * Decision: {d.get('title')} {status_tag} -- Rationale: {d.get('rationale')}")

    # Graph export
    graph_vis = store_restarted.export_graph_visualization("Job Portal")
    print(f"\n [+] Graph Export for UI: {graph_vis['total_nodes']} Nodes, {graph_vis['total_edges']} Edges")
    print("=" * 75)
    print(" [✓] DevMemory AI Milestone Demonstration Completed Successfully!")
    print("=" * 75)


if __name__ == "__main__":
    run_milestone_demo()
