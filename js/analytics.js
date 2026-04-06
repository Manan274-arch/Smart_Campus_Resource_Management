// analytics.js

document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  initNav("analytics");
  renderUserChip();
  await loadAnalytics();
});

async function loadAnalytics() {
  try {
    const [summary, usage, byDate, byStatus] = await Promise.all([
      apiFetch("/api/analytics/summary"),
      apiFetch("/api/analytics/usage"),
      apiFetch("/api/analytics/bookings-by-date"),
      apiFetch("/api/analytics/resource-status")
    ]);

    renderSummaryStats(summary);
    renderUsageTable(usage);
    renderBookingChart(byDate);
    renderStatusChart(byStatus);
    renderStatusDonut(summary.bookings_by_status);
  } catch (err) {
    console.error("Analytics load failed:", err);
  }
}

function renderSummaryStats(summary) {
  const el = document.getElementById("analytics-stats");
  if (!el) return;
  el.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Total Users</div>
      <div class="stat-value">${summary.total_users}</div>
    </div>
    <div class="stat-card green">
      <div class="stat-label">Total Resources</div>
      <div class="stat-value">${summary.total_resources}</div>
    </div>
    <div class="stat-card yellow">
      <div class="stat-label">Total Bookings</div>
      <div class="stat-value">${summary.total_bookings}</div>
    </div>
    <div class="stat-card red">
      <div class="stat-label">Active Maintenance</div>
      <div class="stat-value">${summary.active_maintenance}</div>
    </div>
  `;
}

function renderUsageTable(stats) {
  const el = document.getElementById("usage-table");
  if (!el) return;
  if (!stats.length) {
    el.innerHTML = `<div class="empty-state"><p>No usage data available</p></div>`;
    return;
  }
  el.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Resource</th>
            <th>Total Bookings</th>
            <th>Usage Count</th>
            <th>Last Used</th>
          </tr>
        </thead>
        <tbody>
          ${stats.map((s, i) => `
            <tr>
              <td class="text-muted">${i + 1}</td>
              <td>${escHtml(s.resource_name || "Resource #" + s.resource_id)}</td>
              <td>${s.total_bookings}</td>
              <td>${s.usage_count}</td>
              <td>${s.last_used || "—"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderBookingChart(data) {
  const el = document.getElementById("booking-chart");
  if (!el) return;
  if (!data.length) {
    el.innerHTML = `<div class="empty-state"><p>No booking data</p></div>`;
    return;
  }
  const max = Math.max(...data.map(d => d.count), 1);
  el.innerHTML = `
    <div class="bar-chart">
      ${data.slice(-14).map(d => `
        <div class="bar-row">
          <div class="bar-label">${d.date}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${(d.count / max * 100).toFixed(1)}%"></div>
          </div>
          <div class="bar-count">${d.count}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderStatusChart(data) {
  const el = document.getElementById("status-chart");
  if (!el) return;
  const colors = {
    available:   "var(--green)",
    booked:      "var(--accent)",
    maintenance: "var(--yellow)",
    inactive:    "var(--text-muted)"
  };
  const max = Math.max(...data.map(d => d.count), 1);
  el.innerHTML = `
    <div class="bar-chart">
      ${data.map(d => `
        <div class="bar-row">
          <div class="bar-label">${capitalize(d.status)}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${(d.count / max * 100).toFixed(1)}%;background:${colors[d.status] || "var(--accent)"}"></div>
          </div>
          <div class="bar-count">${d.count}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderStatusDonut(statuses) {
  const el = document.getElementById("booking-donut");
  if (!el) return;
  const colors = {
    confirmed: "var(--accent)",
    completed: "var(--green)",
    cancelled: "var(--red)",
    pending:   "var(--yellow)"
  };
  const entries = Object.entries(statuses).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  let cumulative = 0;
  const segments = entries.map(([k, v]) => {
    const pct = (v / total) * 100;
    const seg = `${colors[k] || "var(--text-muted)"} ${cumulative.toFixed(1)}% ${(cumulative + pct).toFixed(1)}%`;
    cumulative += pct;
    return seg;
  }).join(", ");

  el.innerHTML = `
    <div class="donut-wrap">
      <div style="
        width:140px;height:140px;border-radius:50%;flex-shrink:0;
        background:conic-gradient(${segments || "var(--border) 0% 100%"});
        -webkit-mask:radial-gradient(farthest-side,transparent 55%,black 56%);
        mask:radial-gradient(farthest-side,transparent 55%,black 56%);
      "></div>
      <div class="donut-legend">
        ${entries.map(([k, v]) => `
          <div class="legend-item">
            <div class="legend-dot" style="background:${colors[k] || "var(--text-muted)"}"></div>
            <span>${capitalize(k)}: <strong>${v}</strong> (${((v/total)*100).toFixed(0)}%)</span>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}