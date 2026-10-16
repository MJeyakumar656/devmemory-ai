// MediMemory AI - Interactive Application Logic

let currentPatientId = "patient_001";
let currentGraphData = { nodes: [], links: [] };

document.addEventListener("DOMContentLoaded", () => {
  fetchGraphData();
  setupCanvasResize();
});

// ----------------- API INTEGRATION -----------------

async function handleUserSend() {
  const inputEl = document.getElementById("chatInput");
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = "";
  appendUserMessage(text);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        patient_id: currentPatientId,
        session_id: "session_chat",
        session_date: new Date().toISOString().split("T")[0],
      }),
    });
    const data = await res.json();
    appendAssistantMessage(data);
    updateInsightsPanel(data);
    if (data.graph) {
      currentGraphData = data.graph;
      renderGraphCanvas(data.graph);
    }
  } catch (err) {
    console.error("Chat error:", err);
  }
}

async function loadScenario(scenario) {
  try {
    const res = await fetch(`/api/demo/${scenario}`, { method: "POST" });
    const data = await res.json();

    const container = document.getElementById("messagesContainer");
    const emergencyBanner = document.getElementById("emergencyAlertBanner");

    if (scenario === "session1") {
      emergencyBanner.style.display = "none";
      container.innerHTML = `
        <div class="timeline-divider">
          <span>Session 1 — Day 1 (October 1, 2026)</span>
        </div>
        <div class="message-row user">
          <div class="message-bubble">I started a ketogenic diet today.</div>
        </div>
        <div class="message-row assistant">
          <div class="message-bubble">
            <div class="memory-recall-badge">
              <span>💾 Recorded in FalkorDB: DietaryPattern (Ketogenic Diet)</span>
            </div>
            <div>${data.response}</div>
          </div>
        </div>
      `;
      updateInsightsForSession1();
    } else if (scenario === "session2") {
      emergencyBanner.style.display = "none";
      // Render full 2-session history
      container.innerHTML = `
        <div class="timeline-divider">
          <span>Session 1 — Day 1 (October 1, 2026)</span>
        </div>
        <div class="message-row user">
          <div class="message-bubble">I started a ketogenic diet today.</div>
        </div>
        <div class="message-row assistant">
          <div class="message-bubble">
            <div class="memory-recall-badge">
              <span>💾 Recorded in FalkorDB: DietaryPattern (Ketogenic Diet)</span>
            </div>
            <div>Got it, Jason! Recorded your start of the <strong>Ketogenic Diet</strong> in your graph memory.</div>
          </div>
        </div>

        <div class="timeline-divider">
          <span>Session 2 — Day 21 (October 22, 2026 · 3 Weeks Later)</span>
        </div>
        <div class="message-row user">
          <div class="message-bubble">I've had a headache since this morning.</div>
        </div>
        <div class="message-row assistant">
          <div class="message-bubble">
            <div class="memory-recall-badge" style="background:#fdf2f8; border-color:#fbcfe8; color:#9d174d;">
              <span>⚡ FalkorDB Recall: Preceded by Ketogenic Diet (21 days ago)</span>
            </div>
            <div style="margin-bottom: 10px;">
              <span class="symptom-tag-pill">✨ Tips & Home Guidance — Cephalea & Adaptation</span>
            </div>
            <div>${data.response}</div>
            ${renderCareTableHtml()}
            ${renderContextMenuHtml()}
          </div>
        </div>
      `;
      updateInsightsForSession2(data);
    } else if (scenario === "redflag") {
      emergencyBanner.style.display = "block";
      container.innerHTML = `
        <div class="timeline-divider">
          <span>Emergency Red-Flag Clinical Evaluation</span>
        </div>
        <div class="message-row user">
          <div class="message-bubble">${data.message}</div>
        </div>
        <div class="message-row assistant">
          <div class="message-bubble" style="border-left: 4px solid #ef4444;">
            <div class="memory-recall-badge" style="background:#fee2e2; border-color:#fca5a5; color:#991b1b;">
              <span>🚨 Agent 3: Deterministic SNOOP Red Flag Alert</span>
            </div>
            <div style="color: #991b1b; font-weight: 500;">
              ${data.response}
            </div>
          </div>
        </div>
      `;
      updateInsightsForRedFlag();
    }

    if (data.graph) {
      currentGraphData = data.graph;
      renderGraphCanvas(data.graph);
    }
  } catch (err) {
    console.error("Scenario error:", err);
  }
}

async function resetMemory() {
  if (confirm("Reset FalkorDB memory graph for this patient to a clean state?")) {
    await fetch(`/api/reset/${currentPatientId}`, { method: "POST" });
    loadScenario("session1");
  }
}

async function fetchGraphData() {
  try {
    const res = await fetch(`/api/graph/${currentPatientId}`);
    const data = await res.json();
    currentGraphData = data;
    renderGraphCanvas(data);
  } catch (err) {
    console.error("Failed to fetch graph:", err);
  }
}

// ----------------- UI RENDERING HELPERS -----------------

function renderCareTableHtml() {
  return `
    <div class="care-table-container">
      <div class="care-table-header">Immediate Relief and Evidence-Informed Self-Care</div>
      <table class="care-table">
        <thead>
          <tr>
            <th style="width: 28%;">Strategy</th>
            <th>Recommendation</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="strategy-col">Hydration & Fluid Status</td>
            <td>Check your fluid intake today. Mild fluid deficits during dietary shifts are common. Sip water or herbal tea gradually rather than consuming sudden heavy electrolyte dosages.</td>
          </tr>
          <tr>
            <td class="strategy-col">Active Rest & Relief</td>
            <td>Rest in a dimly lit, quiet room. Apply a cool compress to your forehead or temples for 15 minutes to soothe vascular and tension discomfort.</td>
          </tr>
          <tr>
            <td class="strategy-col">Red-Flag Vigilance</td>
            <td>Seek urgent medical care if the headache is sudden and severe ("thunderclap"), or comes with weakness, confusion, fever with a stiff neck, or vision loss.</td>
          </tr>
        </tbody>
      </table>
    </div>
  `;
}

function renderContextMenuHtml() {
  return `
    <div class="context-action-menu">
      <div class="context-menu-item" onclick="explainInSimpleTerms()">
        <span class="menu-sparkle">✨</span>
        <span>Ask AI to explain in simple terms...</span>
      </div>
      <div class="context-menu-item" onclick="showGraphTrailModal()">
        <span>📋</span>
        <span>View FalkorDB Graph Memory Trail</span>
      </div>
      <div class="context-menu-item" onclick="promptFollowUpQuestion()">
        <span>❓</span>
        <span>Answer clinical follow-up questions</span>
      </div>
      <div class="context-menu-item" onclick="viewCitations()">
        <span>🔗</span>
        <span>View Curated Medical Citations (PubMed & Mayo)</span>
      </div>
    </div>
  `;
}

function appendUserMessage(text) {
  const container = document.getElementById("messagesContainer");
  const div = document.createElement("div");
  div.className = "message-row user";
  div.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendAssistantMessage(data) {
  const container = document.getElementById("messagesContainer");
  const div = document.createElement("div");
  div.className = "message-row assistant";

  let recallHtml = "";
  if (data.temporal_relations && data.temporal_relations.length > 0) {
    const tr = data.temporal_relations[0];
    recallHtml = `
      <div class="memory-recall-badge" style="background:#fdf2f8; border-color:#fbcfe8; color:#9d174d;">
        <span>⚡ FalkorDB Recall: Preceded by Diet Change (${tr.days_apart} days ago)</span>
      </div>
    `;
  }

  div.innerHTML = `
    <div class="message-bubble">
      ${recallHtml}
      <div>${data.response}</div>
      ${data.assessment ? renderCareTableHtml() : ""}
      ${renderContextMenuHtml()}
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function updateInsightsPanel(data) {
  if (data.requires_urgent_care) {
    document.getElementById("emergencyAlertBanner").style.display = "block";
  }

  if (data.assessment && data.assessment.possibilities) {
    renderConditionBars(data.assessment.possibilities);
  }

  if (data.assessment && data.assessment.confidence_score) {
    setConfidence(data.assessment.confidence_score);
  }
}

function updateInsightsForSession1() {
  renderConditionBars([
    { condition: "Dietary Habit Baseline", percentage: 100, color: "#10b981" }
  ]);
  setConfidence(95);
  document.getElementById("nextStepsText").innerText = "Establish baseline nutrient balance and maintain optimal hydration.";
}

function updateInsightsForSession2(data) {
  renderConditionBars([
    { condition: "Dietary Transition & Metabolic Adaptation", percentage: 42, color: "#10b981" },
    { condition: "Dehydration or Fluid Deficit", percentage: 28, color: "#3b82f6" },
    { condition: "Tension-Type or Postural Strain", percentage: 18, color: "#f59e0b" },
    { condition: "Other Secondary Etiologies", percentage: 12, color: "#8b5cf6" },
  ]);
  setConfidence(78);
  document.getElementById("nextStepsText").innerText = "Check hydration status, note headache characteristics, and monitor for warning signs.";
}

function updateInsightsForRedFlag() {
  renderConditionBars([
    { condition: "URGENT: Secondary Headache / SNOOP Red Flag", percentage: 95, color: "#ef4444" },
    { condition: "Other", percentage: 5, color: "#6b7280" }
  ]);
  setConfidence(98);
  document.getElementById("nextStepsText").innerText = "🚨 Call 911 or visit the nearest emergency department immediately!";
}

function renderConditionBars(items) {
  const container = document.getElementById("conditionBarsContainer");
  if (!container) return;

  container.innerHTML = items.map(item => `
    <div class="condition-item">
      <div class="condition-top">
        <span class="condition-name">
          <span class="status-dot" style="background:${item.color || '#3b82f6'};"></span>
          ${item.condition}
        </span>
        <span style="font-weight:700;">${item.percentage}%</span>
      </div>
      <div class="condition-bar-bg">
        <div class="condition-bar-fill" style="width: ${item.percentage}%; background: ${item.color || '#3b82f6'};"></div>
      </div>
    </div>
  `).join("");
}

function setConfidence(score) {
  const fill = document.getElementById("confidenceBarFill");
  const thumb = document.getElementById("confidenceThumb");
  const readout = document.getElementById("confidenceReadout");
  if (fill) fill.style.width = `${score}%`;
  if (thumb) thumb.style.left = `${score}%`;
  if (readout) readout.innerText = `Context Match: ${score}% (Memory-informed)`;
}

// ----------------- INTERACTIVE GRAPH CANVAS -----------------

function setupCanvasResize() {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * (window.devicePixelRatio || 1);
  canvas.height = rect.height * (window.devicePixelRatio || 1);
  const ctx = canvas.getContext("2d");
  ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
}

function renderGraphCanvas(graph) {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width / (window.devicePixelRatio || 1);
  const height = canvas.height / (window.devicePixelRatio || 1);

  ctx.clearRect(0, 0, width, height);

  const nodes = graph.nodes || [];
  const links = graph.links || [];

  document.getElementById("graphNodeCount").innerText = `${nodes.length} Nodes · ${links.length} Edges`;

  if (nodes.length === 0) return;

  // Fixed positions layout for clarity and aesthetics
  const positions = {};
  const cx = width / 2;
  const cy = height / 2;

  // Layout node coordinates
  nodes.forEach((node, i) => {
    if (node.type === "Patient") {
      positions[node.id] = { x: 45, y: cy };
    } else if (node.type === "LifestyleChange") {
      positions[node.id] = { x: 130, y: 55 };
    } else if (node.type === "SymptomEvent") {
      positions[node.id] = { x: 140, y: height - 55 };
    } else if (node.type === "GuidanceAssessment") {
      positions[node.id] = { x: width - 90, y: height - 55 };
    } else if (node.type === "MedicalFact") {
      positions[node.id] = { x: width - 80, y: 55 };
    } else {
      const angle = (i / nodes.length) * 2 * Math.PI;
      positions[node.id] = { x: cx + 60 * Math.cos(angle), y: cy + 40 * Math.sin(angle) };
    }
  });

  // Draw Edges
  links.forEach(link => {
    const p1 = positions[link.source];
    const p2 = positions[link.target];
    if (!p1 || !p2) return;

    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.strokeStyle = link.label === "TEMPORALLY_RELATED_TO" ? "#ec4899" : "#cbd5e1";
    ctx.lineWidth = link.label === "TEMPORALLY_RELATED_TO" ? 2.5 : 1.5;
    if (link.label === "TEMPORALLY_RELATED_TO") {
      ctx.setLineDash([4, 4]);
    } else {
      ctx.setLineDash([]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Edge Label
    const midX = (p1.x + p2.x) / 2;
    const midY = (p1.y + p2.y) / 2;
    ctx.fillStyle = "#6b7280";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    if (link.label === "TEMPORALLY_RELATED_TO") {
      ctx.fillStyle = "#be185d";
      ctx.fillText("21 days apart", midX, midY - 6);
    }
  });

  // Draw Nodes
  nodes.forEach(node => {
    const pos = positions[node.id];
    if (!pos) return;

    // Node Circle
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 14, 0, 2 * Math.PI);
    ctx.fillStyle = node.color || "#3b82f6";
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();

    // Node Label
    ctx.fillStyle = "#1f2937";
    ctx.font = "bold 9px sans-serif";
    ctx.textAlign = "center";
    const label = node.label.length > 12 ? node.label.substring(0, 10) + "…" : node.label;
    ctx.fillText(label, pos.x, pos.y + 24);
  });
}

// ----------------- ACTION MODALS & HELPERS -----------------

function explainInSimpleTerms() {
  alert(
    "💡 In Simple Terms:\n\n" +
    "When you start keto, your body shifts from burning carbs to burning fat. " +
    "This causes you to lose water and essential salts (electrolytes) faster. " +
    "Even 3 weeks in, minor dehydration can trigger a headache. " +
    "However, we never assume keto is the only cause — tension, screen time, or other factors can also be involved. " +
    "Start by drinking a glass of water, resting your eyes, and watch out for emergency red flags."
  );
}

function showGraphTrailModal() {
  const nodes = currentGraphData.nodes || [];
  const links = currentGraphData.links || [];
  let summary = "🧬 FalkorDB Multi-Agent Graph Provenance Trail:\n\n";
  summary += `Mode: ${currentGraphData.mode || 'FalkorDB / Graph Persistence'}\n`;
  summary += `Total Nodes: ${nodes.length}\n`;
  summary += `Total Relationships: ${links.length}\n\n`;

  links.forEach(l => {
    summary += `• (${l.source}) -[:${l.label}]-> (${l.target})\n`;
  });

  alert(summary);
}

function promptFollowUpQuestion() {
  const answer = prompt("Clinical follow-up: How many glasses of water have you had today?");
  if (answer) {
    appendUserMessage(`I've had ${answer} glasses of water today.`);
    setTimeout(() => {
      const container = document.getElementById("messagesContainer");
      const div = document.createElement("div");
      div.className = "message-row assistant";
      div.innerHTML = `
        <div class="message-bubble">
          <div class="memory-recall-badge"><span>💧 Hydration Context Updated</span></div>
          Thank you for providing that detail. Adequate daily intake is around 8-10 glasses during ketogenic adaptation. Continue sipping water steadily throughout the afternoon and monitor if the headache eases within 1-2 hours.
        </div>
      `;
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }, 600);
  }
}

function viewCitations() {
  alert(
    "📚 Curated Medical Reference Citations:\n\n" +
    "1. Bostock ECS, et al. 'Consumer Reports of Keto Flu Associated With the Ketogenic Diet.' Frontiers in Nutrition, 2020.\n" +
    "2. Arca KN, Halker Singh RB. 'Dehydration and Headache.' Current Pain and Headache Reports, 2021.\n" +
    "3. International Headache Society (ICHD-3). 'Tension-Type Headache Classification.' Cephalalgia, 2018.\n" +
    "4. American Headache Society (AHS). 'SNOOP Criteria for Secondary Headaches: Red Flags in Clinical Practice.'"
  );
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}
