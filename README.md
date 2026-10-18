# DevMemory AI & MediMemory AI — Persistent Graph Teammates
> **FalkorDB Hackathon (Track 2: AI Agents with Persistent Memory)**  
> *Two graph-memory experiences: a persistent developer teammate and a safety-focused health companion.*

---

## 🌟 Overview

This project demonstrates how persistent graph memory can carry useful context between sessions. It includes two experiences:

- **DevMemory AI** remembers project conversations, bug fixes, and architectural decisions, and connects them to projects, sessions, and evidence in a graph.
- **MediMemory AI** remembers health events and their timing, and provides cautious, evidence-informed guidance with explicit safety guardrails.

Both use FalkorDB when available and support local JSON graph persistence as a fallback. The default browser route opens DevMemory AI; MediMemory AI is available at `/medimemory`.

## 💬 DevMemory AI

DevMemory is the main application at `http://127.0.0.1:8000/`. It provides an AI chat backed by graph memory, with graph exploration, answer evidence, and agent activity views.

### Persistent conversations and spaces

- The chat opens with a greeting and lets you start a new conversation or continue an earlier one.
- Exchanges are saved as graph nodes connected to their chat thread, project, and session.
- Follow-up chat can use relevant earlier exchanges in the same memory space, including across conversations. Spaces are isolated from one another.
- The protected `default` space cannot be reset or deleted. New spaces start empty and can be used for separate projects or topics.
- Bug-fix and architectural-decision statements can be extracted from chat and saved to graph memory. Answers show retrieved evidence when available.
- The Graph Memory Explorer visualizes connected project memories; Answer Evidence & Citations shows supporting records; Agent Activity & Handoffs surfaces workflow events.
- When FalkorDB is unavailable, the app uses local JSON persistence.

### Try the persistent-memory flow

1. In one conversation, tell DevMemory: *“I started a keto diet three weeks ago.”*
2. Start a new conversation in the same memory space and ask: *“I have a headache. What medicine can I take?”*
3. DevMemory can recall the earlier statement as potentially relevant context. It should not diagnose “keto flu” or recommend salt water or medication based only on that memory; it should clearly explain uncertainty, suggest checking with a clinician or pharmacist, and identify urgent warning signs.

This example demonstrates context recall, not a medical diagnosis or treatment recommendation. For health-related guidance, see the separate MediMemory AI experience below.

---

## 🩺 MediMemory AI — Persistent Health Companion

MediMemory AI is a separate health-oriented experience available at `/medimemory`. It connects health events over time and uses explicit provenance and safety guardrails; temporal order does not establish that one event caused another.

### Interface

- **Left Navigation**: Session history, patient timeline, and active graph-backend indicator.
- **Center Chat Workspace**: AI Scribe status, memory recall indicators, self-care guidance, and clinical action shortcuts.
- **Right Insights Panel**: Next steps, non-diagnostic possibilities, care triage, assessment confidence, and a live graph trail.

---

## 🧠 The 3 AI Agents (Multi-Agent Architecture)

MediMemory AI employs a coordinated multi-agent pipeline using a shared agent state:

```mermaid
flowchart TD
    User([Patient Input]) --> MemoryAgent[Agent 1: Health Memory Agent]
    
    subgraph FalkorDB_Engine [FalkorDB Graph Memory]
        PatientNode[(:Patient)]
        DietNode[(:LifestyleChange)]
        SymptomNode[(:SymptomEvent)]
        TemporalEdge{[:TEMPORALLY_RELATED_TO]}
        AssessmentNode[(:GuidanceAssessment)]
        MedicalFactNode[(:MedicalFact)]
        
        PatientNode -->|REPORTED| DietNode
        PatientNode -->|EXPERIENCES| SymptomNode
        DietNode -.->|days_apart: 21| TemporalEdge -.-> SymptomNode
        SymptomNode -->|ASSESSED_USING| AssessmentNode
        AssessmentNode -->|GROUNDED_IN| MedicalFactNode
    end
    
    MemoryAgent -->|MERGE Nodes & Provenance| FalkorDB_Engine
    MemoryAgent --> SafetyAgent[Agent 3: Safety & Coordination Agent]
    
    SafetyAgent -->|Deterministic SNOOP Red Flag Check| GuidanceAgent[Agent 2: Context & Guidance Agent]
    FalkorDB_Engine -->|Traverse Graph Context| GuidanceAgent
    
    GuidanceAgent -->|Evidence & Traceability| SafeResponse([Evidence-Informed Safe Guidance])
```

### 1. Agent 1: Health Memory Agent
- Extracts and persists patient-reported health information, dietary changes, symptoms, medications, and dates into FalkorDB.
- Preserves explicit provenance: distinguishes `patient_report` from `medically_verified_fact` and `ai_hypothesis`.
- Updates graph nodes and properties when the patient provides corrections.

### 2. Agent 2: Context & Guidance Agent
- Traverses FalkorDB to retrieve historical context across sessions.
- Performs **temporal reasoning**: calculates time deltas (e.g., 21 days elapsed) and creates `[:TEMPORALLY_RELATED_TO]` edges.
- Enforces the medical principle: **temporal precedence $\neq$ proven causation** (*Post hoc ergo propter hoc* avoidance).
- Grounds recommendations in curated medical literature (Mayo Clinic, PubMed, American Headache Society).
- Calculates condition possibility breakdowns and assessment confidence.

### 3. Agent 3: Safety & Coordination Agent
- **Deterministic Red-Flag Verification**: Uses clinical SNOOP criteria (sudden severe "thunderclap" onset, focal neurologic weakness/confusion, fever with neck stiffness, vision changes).
- Ensures safety does not depend purely on an LLM's subjective judgment.
- Enforces strict non-prescriptive guardrails: **never blindly recommends high-sodium water or medications** based solely on a remembered diet.
- Directs patients to urgent care or emergency services when red flags are triggered.

---

## 🏆 The 5 Standout Features (Track 2 Criteria)

| Feature | How MediMemory AI Implements It |
|---|---|
| **1. Persistent Memory** | Full graph persistence in FalkorDB (with local fallback). Details survive restarts. |
| **2. Temporal Reasoning** | Evaluates day deltas between past events and new symptoms (e.g. 21 days), modeling acute adaptation windows vs persistent fluid shifts. |
| **3. Shared Agent State** | Unified `AgentState` passed between Memory, Safety, and Guidance agents with synchronized updates. |
| **4. Evidence & Traceability** | Every guidance point links directly to specific FalkorDB nodes and PubMed/Mayo citations. |
| **5. Safety-Aware Guidance** | Hardcoded red flag triage, follow-up inquiry generation, and clear non-diagnostic framing. |

## DevMemory AI Agent Capabilities

The developer assistant applies the same five-part cycle to project knowledge:

1. **Brain (LLM):** Uses the configured OpenAI model to reason over retrieved evidence; if the model call fails, it returns a deterministic evidence-based answer and reports the fallback.
2. **Memory:** Extracts supported bug fixes and architectural decisions from messages and persists them in the active FalkorDB or local graph space.
3. **Planning and reasoning:** Tracks request understanding, memory extraction, retrieval, evidence-based response, and grounding evaluation as explicit plan steps.
4. **Tools and actions:** Reports the memory extraction and graph retrieval operations used for each chat request; the existing coordinator also supports multi-agent task handoffs.
5. **Feedback and evaluation:** Returns whether evidence grounded the answer, whether new knowledge was saved, and a clear note when no matching memory was available.

---

## 🚀 Quick Start

### 1. Requirements & Setup
Make sure Python 3.10+ is installed, then install the project dependencies:
```bash
pip install -r requirements.txt
```

FalkorDB is optional. To use the graph server instead of the local JSON fallback, start it with Docker:
```bash
docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest
```

### 2. Run the Interactive Web Dashboard
```bash
python main.py
```
Open **DevMemory AI** at `http://127.0.0.1:8000/` or **MediMemory AI** at `http://127.0.0.1:8000/medimemory`.

### 3. Run the CLI Terminal Demonstration
To run the health companion's multi-agent demonstration in the terminal:
```bash
python demo.py
```
*(or `python main.py --cli`)*

### 4. Run the Automated Test Suite
```bash
pytest -v
```

---

## 🎬 MediMemory Demonstration Flow (The 2-Session Milestone)

1. **Session 1 — Day 1: Remember**
   - User: *"I started a ketogenic diet today."*
   - MediMemory records the diet pattern, start date (`2026-10-01`), and provenance in FalkorDB.
2. **Session 2 — Day 21: Connect**
   - User: *"I've had a headache since this morning."*
   - MediMemory retrieves the diet event from 3 weeks prior, calculates the 21-day time delta, links `[:TEMPORALLY_RELATED_TO]`, matches medical literature on hydration and keto adaptation, and guides the user safely.
3. **Emergency SNOOP Red Flag Demo**
   - User: *"I have a sudden thunderclap headache with a stiff neck and fever."*
   - Safety Agent detects emergency red flags deterministically, elevates safety level to `EMERGENCY`, and directs the user to immediate emergency care.

---

## 📊 FalkorDB Cypher Queries Used

```cypher
// 1. Record Patient and Lifestyle Change
MERGE (p:Patient {id: $patient_id})
MERGE (l:LifestyleChange {id: $id})
SET l.name = $name, l.start_date = $start_date, l.source = 'patient_report'
MERGE (p)-[:REPORTED]->(l);

// 2. Record Symptom Event
MERGE (p:Patient {id: $patient_id})
MERGE (s:SymptomEvent {id: $id})
SET s.name = $name, s.reported_date = $reported_date, s.source = 'patient_report'
MERGE (p)-[:EXPERIENCES]->(s);

// 3. Establish Temporal Connection across Sessions
MATCH (l:LifestyleChange {id: $from_id}), (s:SymptomEvent {id: $to_id})
MERGE (l)-[r:TEMPORALLY_RELATED_TO]->(s)
SET r.days_apart = $days_apart,
    r.relationship_type = 'preceded_by',
    r.causal_assumption = false;

// 4. Ground Assessment in Curated Medical Facts
MATCH (a:GuidanceAssessment {id: $assessment_id}), (m:MedicalFact {id: $fact_id})
MERGE (a)-[:GROUNDED_IN]->(m);
```

---

## 📁 Repository Structure

```
repository-root/
  ├── devmemory/
  │    ├── memory.py           # FalkorDB/local graph memory and spaces
  │    ├── schema.py           # Graph models and agent response schemas
  │    └── agents/
  │         ├── memory_agent.py    # Extracts and stores project knowledge
  │         ├── task_agent.py      # Retrieves evidence and answers questions
  │         └── coordinator.py     # Coordinates chat and agent workflows
  ├── medimemory/
  │    ├── __init__.py
  │    ├── schema.py            # Pydantic graph models & multi-agent state
  │    ├── graph_store.py       # FalkorDB client with Cypher & persistence
  │    ├── medical_kb.py        # Curated medical citations & SNOOP red flags
  │    ├── temporal.py          # Temporal distance & plausibility engine
  │    └── agents/
  │         ├── memory_agent.py      # Agent 1: Health Memory Agent
  │         ├── guidance_agent.py    # Agent 2: Context & Guidance Agent
  │         ├── safety_agent.py      # Agent 3: Safety & Coordination Agent
  │         └── orchestrator.py      # Multi-Agent StateGraph Coordinator
  ├── web/
  │    ├── app.py               # FastAPI backend; DevMemory at /, MediMemory at /medimemory
  │    ├── static/
  │    │    ├── css/style.css   # MediMemory dashboard styles
  │    │    └── js/app.js       # MediMemory graph canvas and dashboard interactions
  │    └── templates/
  │         ├── devmemory.html  # DevMemory chat, graph, activity, and evidence views
  │         └── index.html      # MediMemory health companion dashboard
  ├── tests/
  │    ├── test_devmemory.py    # Developer memory, chat, graph, and API tests
  │    ├── test_medimemory.py   # Health agents, temporal reasoning, and API tests
  │    └── test_memory.py       # Core memory tests
  ├── demo.py                   # One-click terminal milestone demonstration
  ├── main.py                   # Web dashboard / CLI entrypoint
  ├── requirements.txt          # Python dependencies
  └── README.md                 # Complete hackathon documentation
```

---
*Built with ❤️ for FalkorDB Track 2: AI Agents with Persistent Memory.*
