from __future__ import annotations

import sys

# Ensure UTF-8 output in Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from medimemory.agents.orchestrator import MediMemoryOrchestrator
from medimemory.graph_store import MediGraphStore
from medimemory.schema import Patient


def run_milestone_demo() -> None:
    print("=" * 70)
    print("  MediMemory AI -- A Persistent Health Companion")
    print("  FalkorDB Track 2 Hackathon: Multi-Agent Graph Memory Demo")
    print("=" * 70)

    store = MediGraphStore(graph_name="medimemory_demo")
    store.reset_patient("patient_001")
    store.save_patient(
        Patient(id="patient_001", name="Jason Franklin", age=30, gender="Male")
    )
    orchestrator = MediMemoryOrchestrator(graph_store=store)

    print(f"\n[Backend Mode]: {store.mode.upper()}")
    print("-" * 70)

    # ---------------------------------------------------------
    # SESSION 1 (Day 1 - October 1, 2026): REMEMBER
    # ---------------------------------------------------------
    print("\n[+] SESSION 1 -- Day 1: October 1, 2026")
    msg1 = "I started a ketogenic diet today."
    print(f'User: "{msg1}"')

    state1 = orchestrator.run(
        user_message=msg1,
        patient_id="patient_001",
        session_id="session_1",
        session_date="2026-10-01",
    )

    print("\n[Agent 1: Health Memory Agent Output]")
    print(f"  * Extracted Node: {state1.extracted_lifestyle.name}")
    print(f"  * Start Date:     {state1.extracted_lifestyle.start_date}")
    print(f"  * Provenance:     {state1.extracted_lifestyle.source.value}")
    print("  * FalkorDB Cypher: MERGE (p:Patient)-[:REPORTED]->(:LifestyleChange)")
    print(f'\nAI Response: "{state1.final_response}"')

    # ---------------------------------------------------------
    # SESSION 2 (Day 21 - October 22, 2026 / 3 Weeks Later): CONNECT
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("[+] SESSION 2 -- Day 21: October 22, 2026 (3 Weeks Later)")
    msg2 = "I've had a headache since this morning."
    print(f'User: "{msg2}"')

    state2 = orchestrator.run(
        user_message=msg2,
        patient_id="patient_001",
        session_id="session_2",
        session_date="2026-10-22",
    )

    print("\n[Agent 1: Health Memory Agent Output]")
    print(f"  * Extracted Symptom: {state2.extracted_symptom.name}")
    print(f"  * Reported Date:     {state2.extracted_symptom.reported_date}")

    print("\n[Agent 2: Context & Guidance Agent (Temporal & Graph Reasoning)]")
    if state2.temporal_relations:
        tr = state2.temporal_relations[0]
        print("  * Temporal Edge Created: [:TEMPORALLY_RELATED_TO]")
        print(f"  * Time Distance:         {tr.days_apart} days ({tr.days_apart // 7} weeks)")
        print("  * Causal Guardrail:      Temporal precedence != Proven causation")
        print(f"  * Medical References:    {len(state2.medical_facts)} matched (PubMed, Mayo Clinic)")
        print(f"  * Assessment Confidence: {state2.assessment.confidence_score}%")

    print("\n[Agent 3: Safety & Coordination Agent]")
    print(f"  * SNOOP Red Flags Detected: {len(state2.red_flags)} (Routine monitoring)")
    print(f"  * Urgent Care Required:     {state2.requires_urgent_care}")
    print("  * Prescriptive Guardrail:   No blind sodium or medication prescription")

    print(f"\nAI Response:\n{state2.final_response}")

    print("\n" + "-" * 70)
    print("Graph Export for D3 / UI:")
    graph_data = store.export_graph_visualization("patient_001")
    print(f"  Nodes ({len(graph_data['nodes'])}): {[n['label'] for n in graph_data['nodes']]}")
    print(f"  Edges ({len(graph_data['links'])}): {[e['label'] for e in graph_data['links']]}")

    # ---------------------------------------------------------
    # EMERGENCY RED-FLAG TEST
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("[!] EMERGENCY RED-FLAG SAFETY DEMO")
    msg_redflag = "I have a sudden thunderclap headache with a stiff neck and fever."
    print(f'User: "{msg_redflag}"')

    state_rf = orchestrator.run(
        user_message=msg_redflag,
        patient_id="patient_001",
        session_id="session_emergency",
        session_date="2026-10-22",
    )

    print("\n[Agent 3: Safety Agent Red Flag Trigger]")
    print(f"  * Safety Level:         {state_rf.safety_level.value.upper()}")
    print(f"  * Flags Detected:       {state_rf.red_flags}")
    print(f"  * Urgent Care Required: {state_rf.requires_urgent_care}")
    print(f"\nAI Emergency Response:\n{state_rf.final_response}")
    print("=" * 70)


if __name__ == "__main__":
    run_milestone_demo()
