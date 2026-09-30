// BhoomiRakshak dashboard client logic

const POLL_INTERVAL = 3000;
let trendChart = null;
let selectedNode = null;
let pendingAckId = null;

const nodeGrid = document.getElementById("node-grid");
const overallBanner = document.getElementById("overall-banner");
const alertBannerRegion = document.getElementById("alert-banner-region");
const zoneMap = document.getElementById("zone-map");
const alertsList = document.getElementById("alerts-list");
const chartNodeSelect = document.getElementById("chart-node-select");
const exportBtn = document.getElementById("export-btn");

function riskClass(level) {
  return level.replace(" ", "-"); // "HIGH RISK" -> "HIGH-RISK" for CSS class use
}

function fmt(n, digits = 2) {
  if (n === null || n === undefined) return "--";
  return Number(n).toFixed(digits);
}

function updateClock() {
  document.getElementById("system-clock").textContent = new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

// ---------- Node status polling ----------
async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    const nodes = await res.json();
    renderNodeCards(nodes);
    renderZoneMap(nodes);
    updateOverallBanner(nodes);
    populateChartSelect(nodes);
    if (selectedNode) loadChart(selectedNode);
  } catch (e) {
    console.error("status poll failed", e);
  }
}

function updateOverallBanner(nodes) {
  const levels = nodes.map(n => n.risk_level);
  let worst = "NORMAL";
  if (levels.includes("HIGH RISK")) worst = "HIGH RISK";
  else if (levels.includes("WARNING")) worst = "WARNING";
  else if (levels.includes("WATCH")) worst = "WATCH";

  const map = {
    "NORMAL": ["normal", "SYSTEM NORMAL"],
    "WATCH": ["watch", "ELEVATED ACTIVITY — WATCH"],
    "WARNING": ["warn", "WARNING — DEFORMATION DETECTED"],
    "HIGH RISK": ["high", "HIGH RISK — INSPECTION RECOMMENDED"],
  };
  const [cls, label] = map[worst];
  overallBanner.className = "overall-banner " + cls;
  overallBanner.textContent = label;
}

function renderNodeCards(nodes) {
  nodeGrid.innerHTML = "";
  nodes.forEach(n => {
    const cls = riskClass(n.risk_level);
    const batteryPct = n.battery ? Math.min(100, Math.round(((n.battery - 3.0) / 1.2) * 100)) : 0;
    const batteryLow = batteryPct < 30;

    const card = document.createElement("div");
    card.className = `node-card ${cls} ${n.online ? "" : "node-offline"}`;
    card.innerHTML = `
      <div class="node-card-head">
        <div>
          <h3>${n.name}</h3>
          <div class="node-zone">${n.zone}${n.online ? "" : '<span class="offline-tag">OFFLINE</span>'}</div>
        </div>
        <div class="status-pill ${cls}">${n.risk_level}</div>
      </div>
      <div class="metric-row">
        <div class="metric">Tilt X<strong>${fmt(n.tilt_x)}&deg;</strong></div>
        <div class="metric">Tilt Y<strong>${fmt(n.tilt_y)}&deg;</strong></div>
        <div class="metric">Vibration<strong>${fmt(n.vibration)}</strong></div>
        <div class="metric">Rate of change<strong>${fmt(n.rate_of_change, 4)}</strong></div>
      </div>
      <div class="metric" style="margin-top:12px;">
        Battery <strong>${n.battery ? n.battery.toFixed(2) + " V" : "--"}</strong>
        <div class="battery-bar"><div class="battery-bar-fill ${batteryLow ? "low" : ""}" style="width:${batteryPct}%"></div></div>
      </div>
    `;
    nodeGrid.appendChild(card);
  });
}

function renderZoneMap(nodes) {
  zoneMap.innerHTML = '<div class="map-legend">Relative node layout — not to scale</div>';
  const positions = [
    { left: "20%", top: "40%" },
    { left: "60%", top: "55%" },
    { left: "40%", top: "20%" },
    { left: "75%", top: "25%" },
  ];
  nodes.forEach((n, i) => {
    const pos = positions[i % positions.length];
    const div = document.createElement("div");
    div.className = `map-node ${riskClass(n.risk_level)}`;
    div.style.left = pos.left;
    div.style.top = pos.top;
    div.textContent = n.node_id;
    div.title = `${n.name} — ${n.risk_level}`;
    zoneMap.appendChild(div);
  });
}

// ---------- Chart ----------
function populateChartSelect(nodes) {
  if (chartNodeSelect.options.length === nodes.length) return;
  chartNodeSelect.innerHTML = "";
  nodes.forEach(n => {
    const opt = document.createElement("option");
    opt.value = n.node_id;
    opt.textContent = n.name;
    chartNodeSelect.appendChild(opt);
  });
  selectedNode = nodes[0]?.node_id || null;
  chartNodeSelect.value = selectedNode;
}

chartNodeSelect.addEventListener("change", (e) => {
  selectedNode = e.target.value;
  loadChart(selectedNode);
});

async function loadChart(nodeId) {
  const res = await fetch(`/api/history/${nodeId}?limit=40`);
  const readings = await res.json();
  const labels = readings.map(r => new Date(r.timestamp).toLocaleTimeString());
  const tiltData = readings.map(r => r.tilt_x);
  const vibData = readings.map(r => r.vibration);

  if (!trendChart) {
    const ctx = document.getElementById("trendChart").getContext("2d");
    trendChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "Tilt X (°)", data: tiltData, borderColor: "#c8622f", tension: 0.3, pointRadius: 0 },
          { label: "Vibration", data: vibData, borderColor: "#7c8f7a", tension: 0.3, pointRadius: 0 },
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: "#ece4d6" } } },
        scales: {
          x: { ticks: { color: "#b6ab98", maxTicksLimit: 6 }, grid: { color: "#302820" } },
          y: { ticks: { color: "#b6ab98" }, grid: { color: "#302820" } },
        }
      }
    });
  } else {
    trendChart.data.labels = labels;
    trendChart.data.datasets[0].data = tiltData;
    trendChart.data.datasets[1].data = vibData;
    trendChart.update();
  }
}

// ---------- Alerts ----------
async function pollAlerts() {
  try {
    const res = await fetch("/api/alerts?limit=30");
    const alerts = await res.json();
    renderAlerts(alerts);
    renderFloatingBanners(alerts);
  } catch (e) {
    console.error("alerts poll failed", e);
  }
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    alertsList.innerHTML = '<div class="no-alerts">No alerts yet. System monitoring normally.</div>';
    return;
  }
  alertsList.innerHTML = "";
  alerts.forEach(a => {
    const div = document.createElement("div");
    div.className = "alert-item" + (a.acknowledged ? " acked" : "");
    div.innerHTML = `
      <div class="alert-meta"><span>${a.node_id} — ${a.zone}</span><span>${new Date(a.created_at).toLocaleString()}</span></div>
      <div class="alert-msg">${a.message}</div>
      ${a.note ? `<div class="alert-msg" style="margin-top:4px;color:#b6ab98;">Note: ${a.note}</div>` : ""}
      ${!a.acknowledged ? `<button class="ghost-btn ack-btn" data-id="${a.id}">Acknowledge</button>` : ""}
    `;
    alertsList.appendChild(div);
  });

  document.querySelectorAll(".ack-btn").forEach(btn => {
    btn.addEventListener("click", () => openAckModal(btn.dataset.id));
  });
}

let lastBannerIds = new Set();
function renderFloatingBanners(alerts) {
  const unacked = alerts.filter(a => !a.acknowledged).slice(0, 3);
  alertBannerRegion.innerHTML = "";
  unacked.forEach(a => {
    const div = document.createElement("div");
    div.className = "floating-alert" + (a.risk_level === "HIGH RISK" ? " high" : "");
    div.innerHTML = `<span>${a.message}</span>`;
    alertBannerRegion.appendChild(div);
  });
}

// ---------- Acknowledge modal ----------
const noteModal = document.getElementById("note-modal");
function openAckModal(alertId) {
  pendingAckId = alertId;
  document.getElementById("note-text").value = "";
  noteModal.classList.remove("hidden");
}
document.getElementById("note-cancel").addEventListener("click", () => {
  noteModal.classList.add("hidden");
});
document.getElementById("note-confirm").addEventListener("click", async () => {
  const note = document.getElementById("note-text").value;
  await fetch(`/api/alerts/${pendingAckId}/acknowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note })
  });
  noteModal.classList.add("hidden");
  pollAlerts();
});

// ---------- Export ----------
exportBtn.addEventListener("click", () => {
  if (selectedNode) window.location.href = `/api/export/${selectedNode}`;
});

// ---------- Demo controls ----------
document.querySelectorAll(".demo-btn[data-node]").forEach(btn => {
  btn.addEventListener("click", async () => {
    await fetch(`/api/demo/trigger/${btn.dataset.node}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ correlated: true })
    });
  });
});
document.getElementById("reset-demo").addEventListener("click", async () => {
  await fetch("/api/demo/reset", { method: "POST" });
});

// ---------- Init ----------
pollStatus();
pollAlerts();
setInterval(pollStatus, POLL_INTERVAL);
setInterval(pollAlerts, POLL_INTERVAL);
