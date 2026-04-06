// dashboard.js

document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  initNav("dashboard");
  renderUserChip();

  await loadDashboard();
});

async function loadDashboard() {
  showSectionLoading("dash-stats");
  showSectionLoading("dash-top-resources");
  showSectionLoading("dash-bookings");

  try {
    const [summary, myBookings] = await Promise.all([
      apiFetch("/api/analytics/summary"),
      apiFetch("/api/bookings/")
    ]);

    renderStats(summary);
    renderTopResources(summary.top_resources);
    renderRecentBookings(myBookings.slice(0, 8));
    renderStatusDonut(summary.bookings_by_status);
  } catch (err) {
    console.error("Dashboard load failed:", err);
  }
}

function renderStats(summary) {
  const container = document.getElementById("dash-stats");
  container.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Total Users</div>
      <div class="stat-value">${summary.total_users}</div>
      <div class="stat-sub">Registered accounts</div>
    </div>
    <div class="stat-card green">
      <div class="stat-label">Resources</div>
      <div class="stat-value">${summary.total_resources}</div>
      <div class="stat-sub">Campus facilities</div>
    </div>
    <div class="stat-card yellow">
      <div class="stat-label">Total Bookings</div>
      <div class="stat-value">${summary.total_bookings}</div>
      <div class="stat-sub">All time</div>
    </div>
    <div class="stat-card red">
      <div class="stat-label">Maintenance</div>
      <div class="stat-value">${summary.active_maintenance}</div>
      <div class="stat-sub">Active issues</div>
    </div>
  `;
}

function renderTopResources(resources) {
  const container = document.getElementById("dash-top-resources");
  if (!resources.length) {
    container.innerHTML = `<div class="empty-state"><p>No usage data yet</p></div>`;
    return;
  }
  const max = Math.max(...resources.map(r => r.usage_count), 1);
  container.innerHTML = `
    <div class="bar-chart">
      ${resources.map(r => `
        <div class="bar-row">
          <div class="bar-label">${escHtml(r.resource_name || "Resource #" + r.resource_id)}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${(r.usage_count / max * 100).toFixed(1)}%"></div>
          </div>
          <div class="bar-count">${r.usage_count}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderRecentBookings(bookings) {
  const container = document.getElementById("dash-bookings");
  if (!bookings.length) {
    container.innerHTML = `<div class="empty-state"><p>No bookings yet. <a href="booking.html" class="text-accent">Make one →</a></p></div>`;
    return;
  }
  container.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Resource</th>
            <th>Date</th>
            <th>Slot</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${bookings.map(b => `
            <tr>
              <td>${escHtml(b.resource_name || "-")}</td>
              <td>${b.date}</td>
              <td>${b.slot_start || "-"} – ${b.slot_end || "-"}</td>
              <td>${statusBadge(b.status_name)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderStatusDonut(statuses) {
  const container = document.getElementById("dash-status");
  if (!container) return;

  const colors = {
    confirmed: "var(--accent)",
    completed: "var(--green)",
    cancelled: "var(--red)",
    pending:   "var(--yellow)"
  };
  const entries = Object.entries(statuses).filter(([, v]) => v > 0);
  const total   = entries.reduce((s, [, v]) => s + v, 0) || 1;

  // Build conic-gradient for donut
  let cumulative = 0;
  const segments = entries.map(([k, v]) => {
    const pct = (v / total) * 100;
    const seg = `${colors[k] || "var(--text-muted)"} ${cumulative.toFixed(1)}% ${(cumulative + pct).toFixed(1)}%`;
    cumulative += pct;
    return seg;
  }).join(", ");

  container.innerHTML = `
    <div class="donut-wrap">
      <div style="
        width:120px;height:120px;border-radius:50%;flex-shrink:0;
        background: conic-gradient(${segments});
        -webkit-mask: radial-gradient(farthest-side, transparent 55%, black 56%);
        mask: radial-gradient(farthest-side, transparent 55%, black 56%);
      "></div>
      <div class="donut-legend">
        ${entries.map(([k, v]) => `
          <div class="legend-item">
            <div class="legend-dot" style="background:${colors[k] || "var(--text-muted)"}"></div>
            <span>${capitalize(k)}: <strong>${v}</strong></span>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

// ── Shared helpers ────────────────────────────────────────────
function showSectionLoading(id) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="loading-overlay"><div class="spinner"></div><span>Loading...</span></div>`;
}

function statusBadge(status) {
  const map = {
    confirmed: "badge-teal",
    completed: "badge-green",
    cancelled: "badge-red",
    pending:   "badge-yellow",
    open:      "badge-red",
    in_progress: "badge-yellow",
    resolved:  "badge-green",
    available: "badge-green",
    maintenance: "badge-yellow",
    inactive:  "badge-muted"
  };
  return `<span class="badge ${map[status] || "badge-muted"}">${capitalize(status || "")}</span>`;
}

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, " ") : "";
}

function escHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function renderUserChip() {
  const user = getUser();
  if (!user) return;
  const chip = document.getElementById("user-chip");
  if (!chip) return;
  const roles = ["","Admin","Student","Faculty","Staff"];
  chip.innerHTML = `
    <div class="user-avatar">${user.name.charAt(0).toUpperCase()}</div>
    <div class="user-info">
      <div class="user-name">${escHtml(user.name)}</div>
      <div class="user-role">${roles[user.role_id] || "User"}</div>
    </div>
  `;
}

function initNav(active) {
  document.querySelectorAll(".nav-item").forEach(item => {
    if (item.dataset.page === active) item.classList.add("active");
    item.addEventListener("click", () => {
      const page = item.dataset.page;
      if (page) window.location.href = page + ".html";
    });
  });

  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      clearSession();
      window.location.href = "index.html";
    });
  }
}