// ═══════════════════════════════════════════════════════════════════════════
// WarrantyMind AI v3.1 — Premium Frontend Engine
// ═══════════════════════════════════════════════════════════════════════════

let authToken = null;
let currentUser = null;
let currentCase = null;
let openSlots = [];
let activeCaseId = null;

// ── SECURITY: HTML Escaping ──────────────────────────────────────────────────
function esc(value) {
  if (typeof value === "string") {
    return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }
  if (Array.isArray(value)) return value.map(esc);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, esc(v)]));
  }
  return value;
}

// ── TOAST NOTIFICATIONS ──────────────────────────────────────────────────────
function toast(type, title, msg = "") {
  const icons = { success: "✅", error: "❌", warn: "⚠️", info: "ℹ️" };
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `
    <div class="toast-icon">${icons[type] || "ℹ️"}</div>
    <div class="toast-body">
      <div class="toast-title">${esc(title)}</div>
      ${msg ? `<div class="toast-msg">${esc(msg)}</div>` : ""}
    </div>
  `;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), 5200);
}

// ── LOADING OVERLAY ───────────────────────────────────────────────────────────
function showLoading(text = "Processing...") {
  document.getElementById("loading-text").textContent = text;
  document.getElementById("loading-overlay").classList.add("active");
}
function hideLoading() {
  document.getElementById("loading-overlay").classList.remove("active");
}

// ── FILE UPLOAD LABEL ─────────────────────────────────────────────────────────
function updateFileLabel() {
  const files = document.getElementById("photo-files").files;
  const label = document.getElementById("file-label");
  if (files.length === 0) { label.textContent = ""; return; }
  label.textContent = `${files.length} file${files.length > 1 ? "s" : ""} selected: ${Array.from(files).map(f => f.name).join(", ")}`;
}

// ── DRAG & DROP ────────────────────────────────────────────────────────────────
const uploadZone = document.getElementById ? (() => {
  window.addEventListener("DOMContentLoaded", () => {
    const zone = document.getElementById("upload-zone");
    if (!zone) return;
    zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("dragover"); });
  });
})() : null;

// ── FETCH UTILITY ────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  const resp = await fetch(path, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return resp.json();
}

// ── DEMO MODE CONFIG ─────────────────────────────────────────────────────────
fetch("/api/config/client")
  .then((r) => r.json())
  .then((cfg) => {
    if (!cfg.demo_mode) {
      document.getElementById("demo-accounts")?.remove();
      document.getElementById("login-username").value = "";
      document.getElementById("login-password").value = "";
    }
  })
  .catch(() => {});

function fillLogin(u, p) {
  document.getElementById("login-username").value = u;
  document.getElementById("login-password").value = p;
}

function prefillSymptomSample() {
  const s = document.getElementById("symptom-select").value;
  const area = document.getElementById("complaint-text");
  if (s.includes("Green")) {
    area.value = "My phone suddenly developed a bright vertical green line down the OLED screen. Never dropped or exposed to water.";
  } else if (s.includes("flickering")) {
    area.value = "My Pixelbook display flickers intermittently. Please help me identify what information is needed before a technician checks it.";
  } else if (s.includes("Cracked")) {
    area.value = "Dropped the device on concrete; front glass is cracked and there is a visible corner chassis dent.";
  } else {
    area.value = "Battery drops from 80% to 15% in two hours and the back enclosure feels warm during charging.";
  }
}

// ── AUTH ─────────────────────────────────────────────────────────────────────
async function doLogin() {
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  const errMsg = document.getElementById("login-error-msg");
  const btn = document.getElementById("login-btn");
  errEl.classList.remove("visible");

  if (!username || !password) {
    errMsg.textContent = "Please enter username and password.";
    errEl.classList.add("visible");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<div class="spinner"></div> Signing in...`;

  try {
    const res = await apiFetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    authToken = res.token;
    currentUser = res;

    document.getElementById("login-view").style.display = "none";
    document.getElementById("app-view").style.display = "block";
    document.getElementById("user-bar").style.display = "flex";

    const initials = (res.full_name || res.username || "?").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
    document.getElementById("user-avatar").textContent = initials;
    document.getElementById("user-badge").textContent = `${res.full_name} · ${res.role.toUpperCase()}`;

    if (res.role === "customer") {
      document.getElementById("customer-intake-card").style.display = "block";
    }
    document.getElementById("sidebar-new-case").hidden = res.role !== "customer";
    document.querySelectorAll(".side-nav-link").forEach((item) => item.classList.remove("active"));
    document.querySelector('.side-nav-link[onclick*="workspace-overview"]')?.classList.add("active");

    toast("success", "Signed in", `Welcome back, ${res.full_name}`);
    await loadWorkspace();
  } catch (e) {
    errMsg.textContent = e.message;
    errEl.classList.add("visible");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Sign In</span> <span>→</span>`;
  }
}

function logout() {
  authToken = null; currentUser = null; currentCase = null; activeCaseId = null; openSlots = [];
  document.getElementById("login-view").style.display = "flex";
  document.getElementById("app-view").style.display = "none";
  document.getElementById("user-bar").style.display = "none";
  document.getElementById("ollama-status-pill").style.display = "none";
  document.getElementById("login-username").value = currentUser?.username || "customer1";
  document.getElementById("login-password").value = "";
}

// ── WORKSPACE LOAD ───────────────────────────────────────────────────────────
function goToWorkspaceSection(sectionId, trigger) {
  const section = document.getElementById(sectionId);
  if (!section) return;
  document.querySelectorAll(".side-nav-link").forEach((item) => item.classList.remove("active"));
  trigger?.classList.add("active");
  section.closest(".card")?.classList.add("section-highlight");
  section.scrollIntoView({ behavior: "smooth", block: "start" });
  window.setTimeout(() => section.closest(".card")?.classList.remove("section-highlight"), 1200);
}

function updateWorkspaceOverview(cases, health) {
  const firstName = (currentUser?.full_name || "there").trim().split(/\s+/)[0];
  document.getElementById("welcome-name").textContent = firstName;
  document.getElementById("workspace-date").textContent = new Intl.DateTimeFormat(undefined, {
    weekday: "long", month: "long", day: "numeric",
  }).format(new Date());
  document.getElementById("metric-cases").textContent = String(cases.length);
  const waiting = cases.filter((item) => String(item.current_interrupt || "").startsWith("await_")).length;
  document.getElementById("metric-actions").textContent = String(waiting);
  const vision = health.vision_model || {};
  document.getElementById("metric-vision").textContent = vision.status === "ready" ? "Ready" : "Check";
  document.getElementById("metric-vision-copy").textContent = vision.status === "ready"
    ? `${vision.model || "Vision model"} is connected`
    : `Vision service ${vision.status || "unavailable"}`;
}

async function loadWorkspace() {
  try {
    const [orders, slots, cases, mcpInfo, health] = await Promise.all([
      apiFetch("/api/orders"),
      apiFetch("/api/slots"),
      apiFetch("/api/cases"),
      apiFetch("/api/mcp/discovery"),
      apiFetch("/api/health/components"),
    ]);
    openSlots = slots;

    // Populate order select
    const safeOrders = esc(orders);
    const orderSel = document.getElementById("order-select");
    if (orderSel) {
      orderSel.innerHTML = safeOrders
        .map((o) => `<option value="${o.order_id}">${o.order_id} — ${o.product_model} (${o.enrolled_plan}, Exp: ${o.warranty_expiry})</option>`)
        .join("");
    }

    // Render Ollama / health status pill
    renderHealthPill(health);
    renderMCPRegistry(mcpInfo, health);
    renderCasesList(cases);
    updateWorkspaceOverview(cases, health);

    if (cases.length > 0 && !activeCaseId) {
      await selectCase(cases[0].case_id);
    } else if (activeCaseId) {
      await selectCase(activeCaseId);
    }
  } catch (e) {
    toast("error", "Workspace Load Failed", e.message);
  }
}

function renderHealthPill(health) {
  const pill = document.getElementById("ollama-status-pill");
  const txt = document.getElementById("ollama-status-text");
  pill.style.display = "flex";
  const vis = health.vision_model || {};
  if (vis.status === "ready") {
    pill.className = "status-pill ready";
    txt.textContent = `Ollama · ${vis.model} ✓`;
  } else if (vis.status === "unreachable") {
    pill.className = "status-pill error";
    txt.textContent = "Ollama · Unreachable";
  } else if (vis.status === "model_not_installed") {
    pill.className = "status-pill warn";
    txt.textContent = `Ollama · ${vis.model} not found`;
  } else if (vis.status === "disabled") {
    pill.className = "status-pill";
    txt.textContent = "Ollama · Disabled";
  } else {
    pill.className = "status-pill warn";
    txt.textContent = `Ollama · ${vis.status}`;
  }
}

function renderMCPRegistry(mcpInfo, health) {
  const el = document.getElementById("mcp-registry-view");
  const vis = health.vision_model || {};
  const text = health.text_model || {};
  const search = health.external_research || {};
  const statusPill = (label, status) => {
    const cls = status === "ready" || status === "configured" || status === "connected" ? "ready" : status === "unreachable" ? "error" : "warn";
    return '<span class="status-pill ' + cls + '" style="display:inline-flex;"><span class="dot"></span>' + esc(label) + ' · ' + esc(status || "unknown") + '</span>';
  };
  const statusHtml = '<div class="health-bar">'
    + statusPill("Vision · " + (vis.model || "Ollama"), vis.status)
    + statusPill("Reasoning · " + (text.model || "Ollama"), text.status)
    + statusPill("Web research", search.status)
    + statusPill("MCP protocol", mcpInfo.mcp_protocol_connected ? "connected" : "not connected")
    + '</div><p class="trace-summary">Local workflow tools run in-process. Web research uses Brave Search HTTPS when configured; it is not an MCP connection.</p>';
  const serversHtml = (mcpInfo.servers || []).map((s) => {
    const toolsHtml = (s.tools || []).map((tool) => '<span class="mcp-tool-badge">' + esc(tool.tool_name) + '()</span>').join("");
    return '<div class="mcp-server-block"><div class="mcp-server-name">⚡ ' + esc(s.server_name) + '</div><div class="mcp-tools">' + toolsHtml + '</div></div>';
  }).join("");
  el.innerHTML = statusHtml + serversHtml;
}
function renderCasesList(cases) {
  const el = document.getElementById("cases-list");
  cases = esc(cases);
  if (!cases.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">No cases yet. Submit a complaint above.</div></div>`;
    return;
  }
  el.innerHTML = cases.map((c) => `
    <div class="case-item ${activeCaseId === c.case_id ? 'active' : ''}" onclick="selectCase('${c.case_id}')">
      <div class="case-item-header">
        <span class="case-item-id">${c.case_id}</span>
        <span class="badge ${getInterruptBadgeClass(c.current_interrupt)}">${fmtInterrupt(c.current_interrupt)}</span>
      </div>
      <div class="case-item-product">${c.order_record?.product_model || ""}</div>
      <div class="case-item-symptom">${c.reported_symptom || ""}</div>
    </div>
  `).join("");
}

function getInterruptBadgeClass(interrupt) {
  if (!interrupt) return "green";
  if (interrupt.includes("human")) return "red";
  if (interrupt.includes("await_diagnostic")) return "amber";
  if (interrupt.includes("slot_consent")) return "blue";
  if (interrupt.includes("technician")) return "violet";
  if (interrupt.includes("repair_consent")) return "amber";
  if (interrupt.includes("support")) return "red";
  if (interrupt.includes("completed")) return "green";
  return "amber";
}

function fmtInterrupt(interrupt) {
  if (!interrupt) return "COMPLETED";
  return interrupt.replace(/_/g, " ").toUpperCase();
}

// ── CASE SUBMIT ───────────────────────────────────────────────────────────────
async function submitNewCase() {
  const fd = new FormData();
  fd.append("order_id", document.getElementById("order-select").value);
  fd.append("reported_symptom", document.getElementById("symptom-select").value);
  fd.append("complaint_description", document.getElementById("complaint-text").value);
  fd.append("invoice_text_or_json", document.getElementById("invoice-json").value || "");
  const files = document.getElementById("photo-files").files;
  for (let i = 0; i < files.length; i++) fd.append("photos", files[i]);

  const btn = document.getElementById("submit-case-btn");
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner"></div> Analyzing with AI...`;
  showLoading("Running multi-agent investigation…");

  try {
    const created = await apiFetch("/api/cases", { method: "POST", body: fd });
    activeCaseId = created.case_id;
    toast("success", "Case Created", `${created.case_id} — Diagnostic interview ready`);
    await loadWorkspace();
  } catch (e) {
    toast("error", "Case Creation Failed", e.message);
  } finally {
    hideLoading();
    btn.disabled = false;
    btn.innerHTML = `🔍 Analyze Complaint &amp; Start Diagnostic Interview`;
  }
}

// ── CASE SELECT ───────────────────────────────────────────────────────────────
async function selectCase(caseId) {
  activeCaseId = caseId;
  // Update active state in list
  document.querySelectorAll(".case-item").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("onclick")?.includes(caseId));
  });
  try {
    currentCase = await apiFetch(`/api/cases/${caseId}`);
    openSlots = await apiFetch("/api/slots");
    renderCaseDetail(currentCase);
  } catch (e) {
    toast("error", "Failed to load case", e.message);
  }
}

// ── CASE DETAIL RENDER ────────────────────────────────────────────────────────
function renderCaseDetail(c) {
  c = esc(c);
  const el = document.getElementById("case-detail-card");
  const vis = c.visual_observations || {};
  const diag = c.diagnostic_interview || {};
  const pol = c.policy_assessment || {};
  const pricing = c.pricing_proposal || {};
  const deviceResearch = c.device_research || {};
  const booking = c.booking_record;
  const tech = c.technician_report;
  const finalAdj = c.final_adjudication;

  const visionVerified = vis.vlm_status === "available" && vis.product_relevance === "consistent";
  const uploadedPhotoCount = (c.uploaded_files || []).length;

  const displayedPhotoFeedback = visionVerified
    ? (vis.vlm_Direct_customer_feedback || "The image was checked.")
    : (uploadedPhotoCount
        ? "Photo uploaded but not visually verified. Assessment uses written complaint only."
        : "No photo provided. Assessment based on written complaint.");

  const displayedDamage = visionVerified ? vis.visible_external_damage : "unverified";
  const displayedProductMatch = visionVerified ? vis.product_relevance : "unverified";
  const displayedSuspicion = visionVerified ? vis.vlm_suspected_origin : "not assessed";
  const displayedReasoning = visionVerified ? (vis.vlm_suspicion_reasoning || "") : "No image-based reasoning available.";

  // Pixel badges
  const pixelImages = (vis.pixel_inspection_telemetry?.images) || [];
  const pixelBadges = pixelImages.map((im) =>
    `<span class="badge teal">📊 ${im.file} · ${im.resolution || "img"} · ${im.file_size_kb || 0}KB · Green: ${im.green_emission_spike_pct ?? "?"}%</span>`
  ).join(" ");

  // Photo warning
  const photoWarningHtml = uploadedPhotoCount && !visionVerified
    ? `<div class="clause-box warn">⚠️ Uploaded photo has no completed image relevance check. Policy and repair estimates are based on the written complaint only.</div>`
    : "";

  // Workflow steps
  const workflowHtml = buildWorkflowSteps(c);

  // VLM Section
  const vlmHtml = `
    <h3>📸 Evidence &amp; VLM Inspection</h3>
    <div class="vlm-speech-box">
      <div class="vlm-label">
        Vision Status: <span class="badge ${vis.vlm_status === 'available' ? 'green' : 'amber'}">${vis.vlm_status || 'not_attempted'}</span>
        &nbsp;Mode: <span class="badge blue">${vis.analysis_mode || 'text_fallback'}</span>
        &nbsp;Product Match: <span class="badge ${displayedProductMatch === 'consistent' ? 'green' : 'amber'}">${displayedProductMatch}</span>
      </div>
      <div style="margin-bottom:8px; color:var(--text-secondary); font-style:italic;">"${displayedPhotoFeedback}"</div>
      <div style="display:flex; gap:8px; flex-wrap:wrap; font-size:0.78rem; color:var(--text-secondary);">
        <span>🔍 Suspicion: <span class="badge amber">${displayedSuspicion.replace(/_/g,' ')}</span></span>
        <span>🏠 Damage: <span class="badge ${displayedDamage==='none_visible'?'green':'red'}">${displayedDamage.replace(/_/g,' ')}</span></span>
      </div>
      ${(vis.observable_symptoms||[]).length ? `<div style="margin-top:8px;"><span style="font-size:0.74rem;color:var(--text-muted);">OBSERVED SYMPTOMS:</span><div class="chip-group">${(vis.observable_symptoms||[]).map(s=>`<span class="chip selected">${s.replace(/_/g,' ')}</span>`).join('')}</div></div>` : ''}
      ${displayedReasoning ? `<div style="font-size:0.78rem; color:var(--text-muted); margin-top:8px; font-style:italic;">🧠 ${displayedReasoning}</div>` : ''}
      ${pixelBadges ? `<div style="margin-top:8px;">${pixelBadges}</div>` : ''}
    </div>
    ${photoWarningHtml}
  `;

  // Diagnostic Interview Section
  const diagnosticHtml = buildDiagnosticSection(c, diag);
  const researchHtml = buildResearchSection(c);

  // Internal guidance and official policy status
  const clausesHtml = (pol.retrieved_clauses || []).map((cl) =>
    '<div class="clause-box"><div style="display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap;margin-bottom:6px;">'
    + '<strong>[' + cl.clause_id + '] ' + cl.title + '</strong><span class="badge">' + cl.program_type + '</span></div>'
    + '<div style="color:var(--text-secondary);font-size:0.8rem;">' + cl.text + '</div></div>'
  ).join("");
  const policyHtml = '<h3>Google Warranty Review</h3>'
    + '<div style="margin-bottom:10px;"><span style="font-size:0.8rem;color:var(--text-secondary);">Coverage status:</span>'
    + '<span class="badge" style="margin-left:6px;">' + (pol.preliminary_eligibility || "REQUIRES_OFFICIAL_POLICY_VERIFICATION") + '</span></div>'
    + '<div class="clause-box" style="margin-bottom:10px;font-size:0.82rem;">' + (pol.policy_explanation || "Coverage has not been determined.") + '</div>'
    + '<p class="trace-summary">Order record warranty field: ' + (c.order_record?.warranty_expiry || "unverified") + '. This is not an official coverage determination.</p>'
    + clausesHtml;
  // Repair pricing is hidden until an approved Pixel source exists.
  const scenariosHtml = (pricing.preliminary_scenarios || []).map((scenario) =>
    '<tr><td><strong>' + scenario.component_name + '</strong><br><span class="mono">' + scenario.component_code + '</span></td>'
    + '<td>' + Number(scenario.diagnostic_fee_inr || 0).toLocaleString() + '</td>'
    + '<td>' + Number(scenario.repair_min_inr || 0).toLocaleString() + ' – ' + Number(scenario.repair_max_inr || 0).toLocaleString() + '</td>'
    + '<td>' + (scenario.notes || "") + '</td></tr>'
  ).join("");
  const pricingHtml = '<h3>Repair pricing</h3><p class="trace-summary">' + (pricing.message || "No approved price source is configured.") + '</p>'
    + '<table class="data-table"><thead><tr><th>Component</th><th>Diagnostic fee</th><th>Repair range</th><th>Conditions</th></tr></thead>'
    + '<tbody>' + (scenariosHtml || '<tr><td colspan="4">No verified Pixel quote is available.</td></tr>') + '</tbody></table>';
  // Booking
  const bookingHtml = booking ? `
    <div class="booking-confirmed">
      <div class="booking-confirmed-header">✅ Appointment Confirmed</div>
      <div class="booking-id">${booking.booking_id}</div>
      <div style="font-size:0.82rem;color:var(--text-secondary);margin-top:6px;">
        📍 ${booking.center_name} (${booking.city}) — ${booking.slot_window}
      </div>
    </div>
  ` : "";

  // Final Adjudication
  const adjHtml = finalAdj ? `
    <div class="clause-box ${finalAdj.final_outcome?.includes('APPROVED')||finalAdj.final_outcome?.includes('NO_FAULT')?'success':finalAdj.final_outcome?.includes('REJECTED')?'danger':'warn'}">
      <div style="font-size:0.74rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">
        🔬 Post-Inspection Final Adjudication
      </div>
      <span class="badge ${finalAdj.final_outcome?.includes('APPROVED')?'green':finalAdj.final_outcome?.includes('PAID')?'amber':'red'}">${finalAdj.final_outcome}</span>
      <div style="margin-top:8px;font-size:0.82rem;color:var(--text-secondary);">${finalAdj.adjudication_explanation}</div>
      ${finalAdj.final_repair_cost_inr > 0 ? `<div style="margin-top:8px;font-size:1rem;font-weight:700;color:var(--accent-amber);">Final Quote: ₹${Number(finalAdj.final_repair_cost_inr).toLocaleString()}</div>` : ''}
    </div>
  ` : "";

  // Role Actions
  const roleActionHtml = buildRoleActions(c, pricing, finalAdj, booking, tech);

  // Support Thread
  const supportHtml = buildSupportSection(c);

  // Trace
  const traceHtml = `
    <h3>🔄 Case agent trace</h3>
    <div class="trace-list">
      ${(c.agent_trace || []).map((t) => `
        <div class="trace-item">
          <div class="trace-step">
            <span>${t.step}</span>
            <span class="badge blue">${(t.agent || t.source || t.mcp_server || "Workflow")}</span>
            ${(t.tools_called || []).map(tc => `<span class="badge teal">${tc}()</span>`).join("")}
          </div>
          <div class="trace-summary">${t.summary}</div>
        </div>
      `).join("")}
    </div>
  `;

  // Job Sheet
  const displayedJobSheet = JSON.parse(JSON.stringify(c.job_sheet || {}));
  if (!visionVerified && displayedJobSheet.section_4_vlm_observations_and_diagnostic_interview) {
    displayedJobSheet.section_4_vlm_observations_and_diagnostic_interview.visible_external_damage = "unverified";
    displayedJobSheet.section_4_vlm_observations_and_diagnostic_interview.vlm_direct_customer_feedback = displayedPhotoFeedback;
    displayedJobSheet.section_4_vlm_observations_and_diagnostic_interview.vlm_suspected_origin = "not_assessed_from_image";
  }

  el.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px; margin-bottom:16px;">
      <div>
        <h2 style="margin-bottom:4px;"><span class="icon blue">🔬</span>${c.case_id} — ${c.order_record?.product_model || ""}</h2>
        <div style="font-size:0.78rem;color:var(--text-muted);">Order: <span class="mono">${c.order_record?.order_id || ""}</span></div>
      </div>
      <span class="badge ${getInterruptBadgeClass(c.current_interrupt)}" style="font-size:0.74rem;padding:5px 14px;">${fmtInterrupt(c.current_interrupt)}</span>
    </div>

    ${workflowHtml}
    <div class="section-divider"></div>

    ${vlmHtml}
    <div class="section-divider"></div>

    ${researchHtml}
    <div class="section-divider"></div>

    ${diagnosticHtml}
    <div class="section-divider"></div>

    ${policyHtml}
    <div class="section-divider"></div>

    ${pricingHtml}
    ${bookingHtml}
    ${adjHtml}

    ${roleActionHtml}

    <div class="section-divider"></div>
    ${supportHtml}

    <div class="section-divider"></div>
    ${traceHtml}

    <div class="section-divider"></div>
    <h3>📋 Live 7-Section Service Job Sheet (${(c.job_sheet?.job_sheet_version || "v1").toUpperCase()})</h3>
    <pre class="jobsheet-json">${JSON.stringify(displayedJobSheet, null, 2)}</pre>
  `;
}

function buildWorkflowSteps(c) {
  const interrupt = c.current_interrupt;
  const steps = [
    { key: "vlm", label: "VLM Intake", done: true },
    { key: "await_diagnostic_interview", label: "Diagnostic Interview", done: interrupt !== "await_diagnostic_interview" },
    { key: "await_customer_slot_consent", label: "Slot Booking", done: c.booking_record != null },
    { key: "await_technician_inspection", label: "Technician Inspection", done: c.technician_report != null },
    { key: "await_human_policy_review", label: "Human warranty review", done: !c.final_adjudication?.human_review_required },
    { key: "await_human_support_resolution", label: "Human support", done: !c.support_handoff },
    { key: "await_customer_repair_consent", label: "Repair Consent", done: c.repair_consent != null },
    { key: "done", label: "Completed", done: !interrupt },
  ];

  return `<div style="display:flex;gap:4px;align-items:center;flex-wrap:wrap;margin-bottom:4px;">
    ${steps.map((s, i) => {
      const isActive = interrupt === s.key;
      return `
        ${i > 0 ? `<span style="color:var(--text-muted);font-size:0.6rem;">›</span>` : ""}
        <span style="display:inline-flex;align-items:center;gap:4px;font-size:0.68rem;font-weight:600;padding:3px 9px;border-radius:99px;
          background:${s.done ? 'rgba(34,197,94,0.1)' : isActive ? 'rgba(59,130,246,0.12)' : 'var(--bg-surface)'};
          border:1px solid ${s.done ? 'rgba(34,197,94,0.2)' : isActive ? 'rgba(59,130,246,0.3)' : 'var(--border-subtle)'};
          color:${s.done ? '#4ade80' : isActive ? 'var(--accent-blue-bright)' : 'var(--text-muted)'};">
          ${s.done ? '✓' : isActive ? '●' : '○'} ${s.label}
        </span>
      `;
    }).join("")}
  </div>`;
}

function buildDiagnosticSection(c, diag) {
  const questions = Array.isArray(diag.questions) ? diag.questions : [];
  const responseText = diag.customer_response || diag.agent_opening_message || "The diagnostic agent is reviewing the available evidence.";
  const statusText = diag.agent_status || "unknown";

  if (diag.status === "awaiting_customer_answers") {
    const questionsHtml = questions.map((q, i) => {
      const choices = Array.isArray(q.suggested_quick_answers) ? q.suggested_quick_answers : [];
      const input = choices.length
        ? '<select id="diag-answer-' + i + '"><option value="">Choose an answer</option>' + choices.map((answer) => '<option value="' + answer + '">' + answer + '</option>').join("") + '</select>'
        : '<input id="diag-answer-' + i + '" placeholder="Type your answer">';
      return '<div class="question-card"><label>Q' + (i + 1) + ' · ' + (q.topic || "Device check") + '</label><p>' + (q.question_text || "") + '</p>' + input + '<small>' + (q.why_asking || "") + '</small></div>';
    }).join("");
    return '<h3>Pixel Diagnostic Agent</h3><div class="interview-box">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;"><strong>Ollama case analysis</strong><span class="badge ' + (statusText === "ready" ? "green" : "amber") + '">' + statusText + (diag.agent_model ? " · " + diag.agent_model : "") + '</span></div>'
      + '<div class="clause-box">' + responseText + '</div>'
      + '<div class="question-list">' + questionsHtml + '</div>'
      + '<label>Anything else we should know? (Optional)</label><textarea id="diag-notes" rows="2" placeholder="Add details that may help the support specialist."></textarea>'
      + '<button class="teal" onclick="submitDiagnosticAnswers(\'' + c.case_id + '\')" id="diag-btn">Send answers for an updated AI review</button>'
      + '</div>';
  }

  if (diag.status === "completed") {
    const ansHtml = (diag.customer_answers || []).map((a) => '<li><strong>' + (a.question || "Answer") + ':</strong> ' + (a.answer || "") + '</li>').join("");
    const stepsHtml = (diag.recommended_troubleshooting_steps || []).map((step) => '<li>' + step + '</li>').join("");
    const gapsHtml = (diag.evidence_gaps || []).map((gap) => '<li>' + gap + '</li>').join("");
    return '<h3>Updated Pixel Diagnostic Assessment</h3><div class="interview-box">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><strong>Ollama case analysis</strong><span class="badge">' + statusText + ' · confidence ' + (diag.confidence || "low") + '</span></div>'
      + '<div class="clause-box">' + (diag.customer_response || responseText) + '</div>'
      + '<p><strong>Working hypothesis:</strong> ' + (diag.refined_diagnosis_hypothesis || "Insufficient information") + '</p>'
      + (ansHtml ? '<ul>' + ansHtml + '</ul>' : "")
      + (stepsHtml ? '<h4>Suggested next steps</h4><ul>' + stepsHtml + '</ul>' : "")
      + (gapsHtml ? '<h4>Evidence gaps for human review</h4><ul>' + gapsHtml + '</ul>' : "")
      + '</div>';
  }

  return '<h3>Pixel Diagnostic Agent</h3><div class="empty-state"><div class="empty-state-text">Awaiting case progress.</div></div>';
}
function buildResearchSection(c) {
  const research = c.device_research || {};
  const warranty = research.warranty_research || {};
  const community = research.community_research || {};
  const renderSources = (sources) => (sources || []).map((source) => {
    const link = String(source.url || "").startsWith("https://")
      ? '<a href="' + source.url + '" target="_blank" rel="noopener noreferrer">' + source.source_id + ' · ' + (source.title || source.domain) + '</a>'
      : '<strong>' + (source.source_id || "Source") + ' · ' + (source.title || "") + '</strong>';
    return '<article class="research-source">' + link
      + '<small>' + (source.domain || "") + (source.published ? ' · ' + source.published : "") + '</small>'
      + (source.snippet ? '<p>' + source.snippet + '</p>' : "") + '</article>';
  }).join("");
  const warrantySources = renderSources(warranty.sources);
  const communitySources = renderSources(community.sources);
  return '<h3>Device research agents</h3><p class="trace-summary">' + (research.source_policy || "") + '</p>'
    + '<div class="research-grid">'
    + '<section class="research-panel"><div class="research-panel-heading"><strong>Official Google warranty research</strong><span class="badge ' + (warranty.status === "ready" ? "green" : "amber") + '">' + (warranty.status || "not checked") + '</span></div>'
    + '<p>' + (warranty.message || "No warranty source status is available.") + '</p>' + (warrantySources || '<p class="research-empty">No official Google source was retrieved.</p>') + '</section>'
    + '<section class="research-panel"><div class="research-panel-heading"><strong>Pixel community research</strong><span class="badge ' + (community.status === "ready" ? "green" : "amber") + '">' + (community.status || "not checked") + '</span></div>'
    + '<p>' + (community.message || "No community source status is available.") + '</p>' + (communitySources || '<p class="research-empty">No matching community report was retrieved.</p>')
    + '<small class="research-disclaimer">Community reports are anecdotal. Contributor identity and technical qualifications are not verified; these reports never decide warranty coverage.</small></section>'
    + '</div>';
}

function getEligibilityClass(eligibility) {
  if (!eligibility) return "";
  if (eligibility.includes("ELIGIBLE") || eligibility.includes("SPECIAL")) return "success";
  if (eligibility.includes("EXCLUDED") || eligibility.includes("OUT_OF_WARRANTY")) return "warn";
  return "";
}

function buildRoleActions(c, pricing, finalAdj, booking, tech) {
  let html = "";

  if (currentUser?.role === "customer" && finalAdj?.human_review_required) {
    html += '<div class="clause-box warn">A human specialist must verify the applicable Google warranty terms and any official quote before this case can be completed.</div>';
  }

  // Customer slot booking
  if (currentUser?.role === "customer" && !booking && c.current_interrupt === "await_customer_slot_consent") {
    const slotOpts = openSlots.map((s) => `<option value="${s.slot_id}">${s.center_name} (${s.city}) — ${s.slot_window}</option>`).join("");
    html += `
      <div class="section-divider"></div>
      <h3>📅 Customer Action: Request a demo service review</h3>
      <label>Demo service desk slot</label>
      <select id="slot-select">${slotOpts || "<option disabled>No slots available</option>"}</select>
      <label class="consent-row" style="display:flex;align-items:flex-start;gap:10px;background:rgba(255,255,255,0.02);border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:12px;margin-top:10px;cursor:pointer;">
        <input type="checkbox" id="consent-check" onchange="document.getElementById('consent-book-slot-btn').disabled = !this.checked" style="width:16px;height:16px;margin-top:2px;flex-shrink:0;accent-color:var(--accent-blue);">
        <span class="consent-text">I understand this is a demo workflow and does not confirm Google warranty coverage or a Google service appointment. (Case reference: ${pricing.quote_version})</span>
      </label>
      <button id="consent-book-slot-btn" class="teal" disabled onclick="bookSlot('${c.case_id}', '${pricing.quote_version}')">
        ✅ Approve &amp; Book Appointment (Generate Job Sheet v1)
      </button>
    `;
  }

  // Post-inspection paid repair consent
  if (currentUser?.role === "customer" && finalAdj?.requires_customer_paid_repair_consent && !c.repair_consent) {
    html += `
      <div class="section-divider"></div>
      <h3>⚡ Customer Action: Post-Inspection Binding Repair Quote</h3>
      <div class="clause-box warn">
        <div style="font-size:0.9rem;font-weight:700;color:var(--accent-amber);margin-bottom:8px;">₹${Number(finalAdj.final_repair_cost_inr).toLocaleString()} — Binding Repair Offer</div>
        <div style="font-size:0.82rem;color:var(--text-secondary);">${finalAdj.adjudication_explanation}</div>
        <div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap;">
          <button class="teal" onclick="submitRepairConsent('${c.case_id}', true)">✅ Approve Repair (₹${Number(finalAdj.final_repair_cost_inr).toLocaleString()})</button>
          <button class="warn" onclick="submitRepairConsent('${c.case_id}', false)">❌ Decline &amp; Return Device</button>
        </div>
      </div>
    `;
  }

  // Technician inspection form
  if (currentUser?.role === "technician" && booking && !tech) {
    html += `
      <div class="section-divider"></div>
      <h3>🔧 Technician Portal: Submit Physical Inspection Report</h3>
      <div class="clause-box" style="border-left-color:var(--accent-teal);">
        <label>Serial Number Verified (Expected: ${c.order_record?.serial_number})?</label>
        <select id="tech-serial">
          <option value="true">✅ Yes — Serial Matches Order &amp; Chassis</option>
          <option value="false">❌ No — Serial Mismatch</option>
        </select>

        <label>External / Internal Physical Impact Damage?</label>
        <select id="tech-impact">
          <option value="false">✅ No Impact Damage</option>
          <option value="true">❌ Yes — Impact / Drop Damage Confirmed</option>
        </select>

        <label>Internal Liquid Contact Indicator (LCI) Triggered?</label>
        <select id="tech-liquid">
          <option value="false">✅ No — LCI Intact (Dry)</option>
          <option value="true">❌ Yes — Liquid Ingress Confirmed</option>
        </select>

        <label>Confirmed Fault Component</label>
        <select id="tech-component">
          <option value="display_module">Display Module / Flex Assembly</option>
          <option value="battery_subsystem">Battery Subsystem</option>
          <option value="logic_board">Main Logic Board</option>
          <option value="enclosure_glass">Enclosure / Glass</option>
          <option value="no_fault_found">No Hardware Fault Found</option>
        </select>

        <label>Technician Diagnostic Notes</label>
        <textarea id="tech-notes" rows="2" placeholder="Record only findings from the physical inspection."></textarea>

        <button class="teal" onclick="submitTechReport('${c.case_id}')">
          📋 Submit Inspection &amp; Resume Workflow (Generate Job Sheet v2)
        </button>
      </div>
    `;
  }

  return html;
}

function buildSupportSection(c) {
  const threadHtml = (c.support_thread || []).map((message) =>
    '<div class="support-msg ' + message.sender_role + '"><div class="support-msg-header"><strong>'
    + message.sender_name + ' · ' + String(message.sender_role || "").toUpperCase()
    + '</strong><span>' + (message.timestamp ? new Date(message.timestamp).toLocaleString() : "") + '</span></div>'
    + '<div class="support-msg-body">' + message.message + '</div>'
    + (message.resolution_action ? '<span class="badge green">' + message.resolution_action + '</span>' : "") + '</div>'
  ).join("");
  const brief = c.support_handoff?.research_brief || {};
  const sourceItems = [
    ...((brief.official_warranty_research || {}).sources || []),
    ...((brief.community_research || {}).sources || []),
  ];
  const sourceLinks = sourceItems.map((source) => String(source.url || "").startsWith("https://")
    ? '<li><a href="' + source.url + '" target="_blank" rel="noopener noreferrer">' + source.source_id + ' · ' + source.title + '</a></li>'
    : '<li>' + source.source_id + ' · ' + source.title + '</li>'
  ).join("");
  const handoffHtml = c.support_handoff
    ? '<div class="clause-box warn" style="margin-bottom:12px;"><strong>Human review brief</strong>'
      + '<p>Reason: ' + c.support_handoff.dispute_reason + '</p>'
      + '<p>AI response: ' + (brief.customer_facing_ai_response || "Not available") + '</p>'
      + '<p>Working hypothesis: ' + (brief.diagnostic_hypothesis || "Not available") + ' · confidence ' + (brief.confidence || "low") + '</p>'
      + '<p>Evidence gaps: ' + ((brief.evidence_gaps || []).join("; ") || "None recorded") + '</p>'
      + '<strong>Research sources for review</strong><ul>' + (sourceLinks || '<li>No external sources were retrieved.</li>') + '</ul>'
      + '<small>Community posts are anecdotal. Check official Google terms before discussing coverage or repair cost.</small></div>'
    : "";
  let controlsHtml = "";
  if (currentUser?.role === "customer") {
    controlsHtml = '<label>What should the specialist review?</label>'
      + '<input id="esc-reason" value="I would like a human review of the warranty information" placeholder="Reason for escalation">'
      + '<label>Your message</label><textarea id="esc-msg" rows="2" placeholder="Tell the specialist what still needs to be resolved."></textarea>'
      + '<p class="trace-summary">The handoff includes the image review, official source links, community reports, AI assessment, and unresolved questions.</p>'
      + '<button class="warn" onclick="escalateCase(\'' + c.case_id + '\')">Ask a human specialist to review</button>';
  } else if (currentUser?.role === "support") {
    controlsHtml = '<label>Resolution action</label><select id="sup-action">'
      + '<option value="keep_inspection_requirement">Explain next steps and keep inspection requirement</option>'
      + '<option value="waive_diagnostic_fee">Waive a diagnostic fee if approved</option></select>'
      + '<label>Support response</label><textarea id="sup-msg" rows="3" placeholder="Reply after reviewing the source links and evidence."></textarea>'
      + '<button class="teal" onclick="sendSupportReply(\'' + c.case_id + '\')">Send human support reply</button>';
  }
  return '<h3>Human support</h3>' + handoffHtml
    + (threadHtml || '<div class="empty-state"><div class="empty-state-text">No support messages yet.</div></div>')
    + '<div style="margin-top:12px;">' + controlsHtml + '</div>';
}
async function submitDiagnosticAnswers(caseId) {
  const btn = document.getElementById("diag-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Sending answers…"; }
  const questions = currentCase?.diagnostic_interview?.questions || [];
  const answers = questions.map((question, index) => ({
    question_id: question.question_id || "q_" + (index + 1),
    question: question.question_text || question.topic || "Device check",
    answer: document.getElementById("diag-answer-" + index)?.value || "",
  })).filter((item) => item.answer.trim());
  try {
    await apiFetch("/api/cases/" + caseId + "/interview-reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        answers,
        additional_customer_notes: document.getElementById("diag-notes")?.value || "",
      }),
    });
    toast("success", "Answers submitted", "Ollama is reassessing the case with your answers and the retrieved sources.");
    await loadWorkspace();
    await selectCase(caseId);
  } catch (e) {
    toast("error", "Submission failed", e.message);
    if (btn) { btn.disabled = false; btn.textContent = "Send answers for an updated AI review"; }
  }
}
async function bookSlot(caseId, quoteVersion) {
  const slotEl = document.getElementById("slot-select");
  const consentEl = document.getElementById("consent-check");
  if (!consentEl?.checked) { toast("warn", "Consent Required", "Please accept the consent checkbox to proceed."); return; }
  showLoading("Booking service slot…");
  try {
    await apiFetch(`/api/cases/${caseId}/book-slot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slot_id: slotEl.value, quote_version: quoteVersion, customer_consent_accepted: true }),
    });
    toast("success", "Appointment Booked", "Job Sheet v1 generated. Technician inspection pending.");
    await loadWorkspace();
    await selectCase(caseId);
  } catch (e) {
    toast("error", "Booking Failed", e.message);
  } finally { hideLoading(); }
}

async function submitTechReport(caseId) {
  showLoading("Submitting technician inspection…");
  try {
    await apiFetch(`/api/cases/${caseId}/technician-inspection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        serial_verified: document.getElementById("tech-serial").value === "true",
        physical_impact_damage: document.getElementById("tech-impact").value === "true",
        liquid_contact_detected: document.getElementById("tech-liquid").value === "true",
        confirmed_fault_component: document.getElementById("tech-component").value,
        technician_notes: document.getElementById("tech-notes").value,
      }),
    });
    toast("success", "Inspection Submitted", "Final adjudication and Job Sheet v2 generated.");
    await loadWorkspace();
    await selectCase(caseId);
  } catch (e) {
    toast("error", "Submission Failed", e.message);
  } finally { hideLoading(); }
}

async function submitRepairConsent(caseId, accepted) {
  showLoading(accepted ? "Approving repair…" : "Declining repair…");
  try {
    await apiFetch(`/api/cases/${caseId}/repair-consent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repair_consent_accepted: accepted,
        customer_comment: accepted ? "Approved post-inspection quote" : "Declined paid repair",
      }),
    });
    toast(accepted ? "success" : "info", accepted ? "Repair Approved" : "Repair Declined", accepted ? "Repair work will begin shortly." : "Device will be returned.");
    await loadWorkspace();
    await selectCase(caseId);
  } catch (e) {
    toast("error", "Failed", e.message);
  } finally { hideLoading(); }
}

async function escalateCase(caseId) {
  showLoading("Escalating to human support…");
  try {
    await apiFetch(`/api/cases/${caseId}/escalate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reason: document.getElementById("esc-reason").value,
        customer_message: document.getElementById("esc-msg").value,
      }),
    });
    toast("warn", "Escalated", "A support specialist will review your case.");
    await loadWorkspace();
    await selectCase(caseId);
  } catch (e) {
    toast("error", "Escalation Failed", e.message);
  } finally { hideLoading(); }
}

async function sendSupportReply(caseId) {
  showLoading("Sending support resolution…");
  try {
    await apiFetch(`/api/cases/${caseId}/support-reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: document.getElementById("sup-msg").value,
        resolution_action: document.getElementById("sup-action").value,
      }),
    });
    toast("success", "Support Reply Sent", "Job Sheet updated with resolution.");
    await loadWorkspace();
    await selectCase(caseId);
  } catch (e) {
    toast("error", "Reply Failed", e.message);
  } finally { hideLoading(); }
}
