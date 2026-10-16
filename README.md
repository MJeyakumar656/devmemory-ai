# MediMemory AI — A Persistent Health Companion
> **FalkorDB Hackathon (Track 2: AI Agents with Persistent Memory)**  
> *Connecting health events across weeks and months using FalkorDB graph memory, multi-agent coordination, temporal reasoning, and deterministic clinical safety guardrails.*

---

## 🌟 Overview

Conventional healthcare chatbots suffer from a critical limitation: **statelessness**. When a user reports a symptom today, the AI has forgotten what the user reported three weeks ago. Standard vector databases merely compute semantic similarity, completely missing chronological order, causal distinctions, and relationship graphs.

**MediMemory AI** turns **FalkorDB** into the persistent cognitive backbone of a safe, multi-agent personal health companion. It remembers lifestyle changes, dietary shifts, medications, and symptoms across weeks or months, using graph reasoning to explore potential connections while strictly adhering to evidence-based medical safety.

---

## 📸 Interface Design (Inspired by Modern Clinical UI)

The user experience features a calming, clinical-grade interface designed after top-tier healthcare UI patterns:
- **Left Navigation**: Session history, patient timeline, and active FalkorDB backend indicator.
- **Center Chat Workspace**: AI Scribe status, memory recall indicators ("Preceded by Ketogenic Diet 21 days ago"), interactive **Immediate Relief & Self-Care** table, and clinical action shortcuts.
- **Right Insights Panel**: Next Steps, non-diagnostic **Condition Possibilities** breakdown (e.g. 42% Dietary Transition / Fluid Shift, 28% Dehydration, 18% Tension-Type), **When to Seek Care** triage timeline, **Assessment Confidence** meter, and a live **FalkorDB Graph Trail Canvas**.

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

---

## 🚀 Quick Start

### 1. Requirements & Setup
Make sure Python 3.10+ is installed:
```bash
pip install -r requirements.txt
```

*(Optional) Start FalkorDB via Docker if you want the native Redis-based graph server:*
```bash
docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest
```
> *Note: If FalkorDB is not running locally, MediMemory AI automatically uses its robust, persistent graph engine fallback with full Cypher and JSON persistence.*

### 2. Run the Interactive Web Dashboard
```bash
python main.py
```
Open your browser to: **`http://127.0.0.1:8000`**

### 3. Run the CLI Terminal Demonstration
To see the complete multi-agent workflow in the terminal:
```bash
python demo.py
```
*(or `python main.py --cli`)*

### 4. Run the Automated Test Suite
```bash
pytest -v
```

---

## 🎬 Demonstration Flow (The 2-Session Milestone)

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
c:\Graph Hacks\
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
  │    ├── app.py               # FastAPI backend with REST endpoints
  │    ├── static/
  │    │    ├── css/style.css   # Pixel-accurate modern healthcare UI styles
  │    │    └── js/app.js       # Graph canvas, interactive tables, demo runner
  │    └── templates/
  │         └── index.html      # Complete dashboard matching Dribbble inspiration
  ├── tests/
  │    ├── test_medimemory.py   # Unit tests for agents, temporal reasoning & API
  │    └── test_memory.py       # Core memory tests
  ├── demo.py                   # One-click terminal milestone demonstration
  ├── main.py                   # Web dashboard / CLI entrypoint
  ├── requirements.txt          # Python dependencies
  └── README.md                 # Complete hackathon documentation
```

---
*Built with ❤️ for FalkorDB Track 2: AI Agents with Persistent Memory.*
