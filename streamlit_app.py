import json
import os
from datetime import datetime
from pathlib import Path
import streamlit as st

from devmemory.agents.coordinator import AgentCoordinator
from devmemory.agents.memory_agent import MemoryAgent
from devmemory.agents.task_agent import TaskAgent
from devmemory.memory import MemoryStore
from devmemory.schema import TaskStatus

# -------------------------------------------------------------
# PAGE CONFIGURATION
# -------------------------------------------------------------
st.set_page_config(
    page_title="DevMemory AI — Persistent Graph Teammate",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 1.2rem;
    }
    .badge-falkordb {
        background-color: #ecfdf5;
        color: #059669;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #a7f3d0;
    }
    .badge-local {
        background-color: #eff6ff;
        color: #2563eb;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #bfdbfe;
    }
    .workflow-box {
        background: linear-gradient(90deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-left: 5px solid #3b82f6;
        padding: 12px 18px;
        border-radius: 8px;
        margin-bottom: 16px;
        font-size: 0.9rem;
    }
    .evidence-card {
        background-color: #f8fafc;
        border-left: 4px solid #10b981;
        padding: 12px 16px;
        margin-bottom: 10px;
        border-radius: 0 6px 6px 0;
    }
    .activity-row {
        padding: 8px 12px;
        border-bottom: 1px solid #e2e8f0;
        font-size: 0.88rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------
# INITIALIZE STATE & STORES
# -------------------------------------------------------------
@st.cache_resource
def get_memory_store():
    storage_path = str(Path(__file__).parent / "data" / "devmemory_graph.json")
    store = MemoryStore(
        graph_name="devmemory_app",
        storage_file=storage_path,
        use_local_fallback=True,
    )
    if not store.search("Vite failed to start"):
        store.record_project_memory(
            project="Job Portal",
            issue="Vite failed to start",
            fix="Stop conflicting background process on port 5173",
            session="October 12",
            evidence="Port 5173 was locked by a stale node.js background task.",
        )
        mem_agent = MemoryAgent(store)
        mem_agent.record_architectural_decision(
            project="Job Portal",
            title="Use Webpack Bundler",
            rationale="Initial legacy bundler in 2021",
            session="Legacy Setup",
            date="2021-06-10",
        )
        mem_agent.record_architectural_decision(
            project="Job Portal",
            title="Use Vite Bundler",
            rationale="Instant HMR and native ESM tooling",
            session="October 12",
            supersedes_title="Use Webpack Bundler",
            date="2026-10-12",
        )
    return store


store = get_memory_store()
coordinator = AgentCoordinator(memory_store=store)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": (
                "👋 Hello! I am **DevMemory AI**, your persistent coding teammate powered by **FalkorDB**.\n\n"
                "I remember past bugs, fixes, sessions, and architectural decisions across days and weeks.\n"
                "- Use the **💾 Save New Memory** expander to store new bug fixes or decisions.\n"
                "- Create or switch **🌐 Memory Spaces** in the sidebar."
            ),
            "evidence": [],
        }
    ]

# -------------------------------------------------------------
# SIDEBAR: MEMORY SPACES & ACTIONS
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🧠 DevMemory AI")
    backend_badge = (
        '<span class="badge-falkordb">● FalkorDB Live</span>'
        if store.mode == "falkordb"
        else '<span class="badge-local">● Persistent Local Graph</span>'
    )
    st.markdown(f"**Backend Status**: {backend_badge}", unsafe_allow_html=True)
    st.markdown("---")

    # MEMORY SPACES
    st.markdown("#### 🌐 Memory Spaces")
    spaces_list = store.list_spaces()
    space_ids = [s["id"] for s in spaces_list]
    space_names = [f"{s['name']} ({s['node_count']} nodes)" for s in spaces_list]

    current_idx = 0
    if store.active_space in space_ids:
        current_idx = space_ids.index(store.active_space)

    selected_space_str = st.selectbox(
        "Active Memory Space",
        space_names,
        index=current_idx,
    )
    chosen_id = space_ids[space_names.index(selected_space_str)]
    if chosen_id != store.active_space:
        store.switch_space(chosen_id)
        st.rerun()

    with st.expander("➕ Create New Memory Space"):
        new_space_name = st.text_input("Space Name", placeholder="e.g. Mobile App, Payment Gateway")
        new_space_desc = st.text_area("Description", placeholder="Describe repository or scope")
        if st.button("Create Space", use_container_width=True):
            if new_space_name:
                store.create_space(new_space_name, new_space_desc)
                store.switch_space(new_space_name)
                st.success(f"Space '{new_space_name}' created!")
                st.rerun()

    st.markdown("---")
    st.markdown("#### 📁 Active Project Scope")
    selected_project = st.selectbox(
        "Select Project",
        ["Job Portal", "E-Commerce Microservice", "Auth API"],
        index=0,
    )

    st.markdown("#### ⚡ Quick Demo Prompts")
    prompt_pills = [
        "My React project had a Vite startup error last week. What did we do to fix it?",
        "What bundler decision did we make for Job Portal?",
        "We fixed the React hydration mismatch by disabling SSR on the modal component.",
    ]
    for p in prompt_pills:
        if st.button(p, key=f"btn_{p[:20]}"):
            st.session_state.selected_prompt = p

    st.markdown("---")
    if st.button("🔄 Reset Current Space", use_container_width=True):
        store.reset(clear_persistent_file=True)
        st.session_state.chat_history = []
        st.success("Space cleared. Reloading...")
        st.rerun()

# -------------------------------------------------------------
# MAIN APP HEADER & UNDERSTANDING BANNER
# -------------------------------------------------------------
st.markdown('<div class="main-header">DevMemory AI — Persistent Knowledge Graph Teammate</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">FalkorDB Hackathon Track 2: Multi-Agent AI Teammate with Graph Memory</div>',
    unsafe_allow_html=True,
)

# Visual Workflow Explainer Banner
st.markdown(
    f"""
    <div class="workflow-box">
        <b>HOW DEVMEMORY WORKS:</b> &nbsp;
        1️⃣ <b>Developer Input</b> &nbsp;➔&nbsp; 
        2️⃣ <b>FalkorDB Graph Traversal</b> <i>((:Project)-[:HAS_INCIDENT]->(:Error)...)</i> &nbsp;➔&nbsp; 
        3️⃣ <b>Multi-Agent Reasoning</b> &nbsp;➔&nbsp; 
        4️⃣ <b>Evidence-Backed Response & Memory Commit</b>
        <br><span style="color:#64748b; font-size:0.8rem;">Active Workspace Space: <b>{store.active_space}</b></span>
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------
# FORM: SAVE NEW MEMORY
# -------------------------------------------------------------
with st.expander("💾 Save New Memory to FalkorDB (Click to expand form)"):
    col_m1, col_m2 = st.columns([1, 1])
    with col_m1:
        mem_cat = st.selectbox(
            "Memory Type",
            ["🐞 Bug Fix / Error Resolution", "📐 Architectural Decision", "📋 Collaborative Task", "💡 Technical Fact"],
        )
        mem_proj = st.text_input("Project", value=selected_project)
        mem_title = st.text_input("Title / Issue", placeholder="e.g. Vite failed to start")
    with col_m2:
        mem_session = st.text_input("Session Anchor", value=f"Session {datetime.now().strftime('%b %d')}")
        mem_details = st.text_area("Details / Solution / Rationale", placeholder="e.g. Kill conflicting process on port 5173")
        mem_evidence = st.text_input("Evidence / Root Cause", placeholder="e.g. Stale node process PID 8192 held the port")

    supersedes_text = None
    if "Decision" in mem_cat:
        supersedes_text = st.text_input("Supersedes Previous Decision (Optional [:SUPERSEDES])", placeholder="e.g. Use Webpack Bundler")

    if st.button("Commit Memory to FalkorDB Graph", use_container_width=True):
        if mem_title and mem_details:
            t_key = "incident" if "Bug" in mem_cat else ("decision" if "Decision" in mem_cat else ("task" if "Task" in mem_cat else "fact"))
            res = store.save_custom_memory(
                memory_type=t_key,
                project=mem_proj,
                title=mem_title,
                details=mem_details,
                session=mem_session,
                evidence=mem_evidence,
                supersedes_title=supersedes_text,
            )
            st.success(f"Saved! {res['summary']}")
            st.rerun()
        else:
            st.error("Please fill in both Title and Details.")

# -------------------------------------------------------------
# THE 4 MAIN SCREENS
# -------------------------------------------------------------
tab_chat, tab_graph, tab_activity, tab_evidence = st.tabs(
    ["💬 AI Chat", "🕸️ Graph Memory Explorer", "🤖 Agent Activity & Handoffs", "🔍 Answer Evidence & Citations"]
)

# =============================================================
# SCREEN 1: AI CHAT
# =============================================================
with tab_chat:
    chat_container = st.container(height=420)

    for msg in st.session_state.chat_history:
        with chat_container.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("evidence"):
                with st.expander("🔍 View Retrieved Graph Evidence from FalkorDB"):
                    for ev in msg["evidence"]:
                        st.markdown(
                            f"- **{ev['source_type']} ({ev['source_name']})** "
                            f"→ `[:{ev['relation']}]` → "
                            f"**{ev['target_type']} ({ev['target_name']})** "
                            f"*(Session: {ev.get('session', 'N/A')})*"
                        )

    user_query = st.chat_input("Ask a question, continue earlier tasks, or record a fix...")
    if getattr(st.session_state, "selected_prompt", None):
        user_query = st.session_state.selected_prompt
        st.session_state.selected_prompt = None

    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with chat_container.chat_message("user"):
            st.markdown(user_query)

        with chat_container.chat_message("assistant"):
            with st.spinner("Traversing FalkorDB graph memory..."):
                result = coordinator.handle_request(
                    user_message=user_query,
                    project_name=selected_project,
                    session_name=f"Session {datetime.now().strftime('%b %d')}",
                )
                st.markdown(result["response"])
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": result["response"],
                        "evidence": result["evidence"],
                        "last_result": result,
                    }
                )
                st.session_state.latest_evidence = result["evidence"]
                st.rerun()

# =============================================================
# SCREEN 2: GRAPH MEMORY EXPLORER
# =============================================================
with tab_graph:
    st.markdown("##### FalkorDB Connected Memory Graph")
    graph_data = store.export_graph_visualization(selected_project)

    col_stats1, col_stats2, col_stats3 = st.columns(3)
    col_stats1.metric("Graph Nodes", graph_data["total_nodes"])
    col_stats2.metric("Connected Edges", graph_data["total_edges"])
    col_stats3.metric("Storage Engine", f"{graph_data['backend_mode'].upper()} ({store.active_space})")

    st.markdown("---")
    sub_col1, sub_col2 = st.columns([1.5, 1])
    with sub_col1:
        st.markdown("###### Graph Entities (Nodes)")
        for node in graph_data["nodes"]:
            badge_color = node.get("color", "#64748b")
            props_str = ", ".join(f"{k}: {v}" for k, v in node["properties"].items() if k != "id")
            st.markdown(
                f"<div style='border-left: 4px solid {badge_color}; padding: 6px 12px; margin-bottom: 6px; background: #f8fafc; border-radius: 4px;'>"
                f"<b>[{node['type']}]</b> {node['label']} <span style='color: #64748b; font-size: 0.8rem;'>({props_str})</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with sub_col2:
        st.markdown("###### Cypher Relationships (Edges)")
        for edge in graph_data["links"]:
            st.markdown(
                f"`{edge['source']}` ➔ **[:{edge['label']}]** ➔ `{edge['target']}`"
            )

# =============================================================
# SCREEN 3: AGENT ACTIVITY & HANDOFFS
# =============================================================
with tab_activity:
    st.markdown("##### Multi-Agent Task Board & Handoffs")
    st.info("Demonstrates Step 6: Coordinator assigns tasks, agents share FalkorDB memory, and execute handoffs.")

    col_act1, col_act2 = st.columns([1, 1])

    with col_act1:
        st.markdown("###### Trigger Multi-Agent Task Handoff")
        task_name = st.text_input("Task Title", value="Resolve Port 5173 Socket Lock")
        task_desc = st.text_area("Task Description", value="Check if stale process locks Vite default port, verify release, and log fix.")
        if st.button("🚀 Execute Collaborative Workflow", use_container_width=True):
            with st.spinner("Agents coordinating across FalkorDB memory..."):
                wf = coordinator.execute_multi_agent_workflow(
                    task_title=task_name,
                    project_name=selected_project,
                    description=task_desc,
                    session_name=f"Session {datetime.now().strftime('%b %d')}",
                )
                st.success(f"Task {wf['task_id']} Completed!")
                st.markdown(f"**Shared Memory Context**: {wf['context_shared']}")
                st.markdown(f"**Handoff**: `{wf['handoff']['from_agent']}` ➔ `{wf['handoff']['to_agent']}`")

    with col_act2:
        st.markdown("###### Registered Team Agents")
        for aid, agent in coordinator.agents.items():
            st.markdown(
                f"- **{agent.name}** (`{agent.id}`): *{agent.role}* (Status: `{agent.status}`)"
            )

    st.markdown("---")
    st.markdown("###### Live Multi-Agent Activity Log")
    for act in reversed(coordinator.activity_logs):
        st.markdown(
            f"<div class='activity-row'>"
            f"<span style='color: #64748b;'>[{act['timestamp']}]</span> "
            f"<b>{act['agent']}</b> — <i>{act['action']}</i>: {act['details']}"
            f"</div>",
            unsafe_allow_html=True,
        )

# =============================================================
# SCREEN 4: ANSWER EVIDENCE
# =============================================================
with tab_evidence:
    st.markdown("##### Deep Answer Evidence & Graph Provenance")
    st.write("Inspect how DevMemory AI verifies answers using connected graph paths from FalkorDB.")

    evidence_items = getattr(st.session_state, "latest_evidence", [])
    if not evidence_items:
        ctx = store.retrieve_context_with_evidence("Vite failed to start", selected_project)
        evidence_items = [e.model_dump() for e in ctx["evidence"]]

    if evidence_items:
        for idx, ev in enumerate(evidence_items, start=1):
            st.markdown(
                f"""
                <div class="evidence-card">
                    <h4>Evidence Record #{idx}</h4>
                    <p><b>Graph Path:</b> <code>({ev['source_type']}: {ev['source_name']})</code> ➔ <code>[:{ev['relation']}]</code> ➔ <code>({ev['target_type']}: {ev['target_name']})</code></p>
                    <p><b>Recorded Session:</b> {ev.get('session', 'N/A')} | <b>Confidence:</b> {int(ev.get('confidence', 0.95)*100)}%</p>
                    <p><b>Notes:</b> {ev.get('notes', 'Verified outcome stored in FalkorDB.')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No evidence records to display yet. Ask a question in the AI Chat tab to view provenance!")
