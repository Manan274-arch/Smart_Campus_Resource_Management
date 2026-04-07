/**
 * maintenance.js — Smart Campus Resource Management System
 * Handles all maintenance page interactions:
 *  - Fetch & display maintenance issues
 *  - Create new issue
 *  - Update issue status
 *  - View maintenance logs per issue
 *  - Filter by status / resource
 */

const API = "http://127.0.0.1:8000/api";
let currentUser = null;
let allIssues = [];
let resourceMap = {};

// ─── INIT ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  currentUser = JSON.parse(localStorage.getItem("campus_user") || "null");
  if (!currentUser) {
    window.location.href = "index.html";
    return;
  }

  updateNavUser();
  await loadResources();
  await loadMaintenance();
  setupEventListeners();
});

// ─── AUTH HELPERS ─────────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem("campus_token") || "";
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
  };
}

function updateNavUser() {
  const el = document.getElementById("nav-user");
  if (el && currentUser) el.textContent = currentUser.name || "User";
}

// ─── API CALLS ────────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${API}${path}`, {
      headers: authHeaders(),
      ...options,
    });
    if (res.status === 401) {
      localStorage.clear();
      window.location.href = "index.html";
      return null;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }));
      showToast(err.detail || "Request failed", "error");
      return null;
    }
    if (res.status === 204) return true;
    return await res.json();
  } catch (e) {
    showToast("Network error — is the server running?", "error");
    return null;
  }
}

// ─── LOAD DATA ────────────────────────────────────────────────────────────────

async function loadResources() {
  const data = await apiFetch("/resources/");
  if (!data) return;
  data.forEach((r) => (resourceMap[r.resource_id] = r.name));

  // Populate resource dropdowns
  ["filter-resource", "form-resource"].forEach((id) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = `<option value="">All Resources</option>`;
    data.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r.resource_id;
      opt.textContent = r.name;
      sel.appendChild(opt);
    });
  });
}

async function loadMaintenance() {
  showLoader(true);
  const data = await apiFetch("/maintenance/");
  showLoader(false);
  if (!data) return;
  allIssues = data;
  renderTable(allIssues);
  updateSummaryCards(allIssues);
}

// ─── RENDER ───────────────────────────────────────────────────────────────────

function renderTable(issues) {
  const tbody = document.getElementById("maintenance-tbody");
  const empty = document.getElementById("empty-state");
  if (!tbody) return;

  if (issues.length === 0) {
    tbody.innerHTML = "";
    if (empty) empty.classList.remove("hidden");
    return;
  }
  if (empty) empty.classList.add("hidden");

  tbody.innerHTML = issues
    .map(
      (issue) => `
    <tr data-id="${issue.maintenance_id}">
      <td>#${issue.maintenance_id}</td>
      <td>${resourceMap[issue.resource_id] || "Unknown"}</td>
      <td class="issue-text" title="${escHtml(issue.issue)}">${escHtml(truncate(issue.issue, 60))}</td>
      <td><span class="badge badge-${statusClass(issue.status)}">${issue.status}</span></td>
      <td>${formatDate(issue.reported_date)}</td>
      <td class="actions">
        <button class="btn btn-sm btn-outline" onclick="openLogsModal(${issue.maintenance_id})">
          Logs
        </button>
        ${
          canEdit()
            ? `<button class="btn btn-sm btn-primary" onclick="openEditModal(${issue.maintenance_id})">
            Edit
          </button>`
            : ""
        }
      </td>
    </tr>
  `
    )
    .join("");
}

function updateSummaryCards(issues) {
  const counts = { open: 0, "in-progress": 0, resolved: 0, total: 0 };
  issues.forEach((i) => {
    counts.total++;
    const s = (i.status || "").toLowerCase().replace(" ", "-");
    if (counts[s] !== undefined) counts[s]++;
  });
  setCard("card-total", counts.total);
  setCard("card-open", counts.open);
  setCard("card-inprogress", counts["in-progress"]);
  setCard("card-resolved", counts.resolved);
}

function setCard(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ─── FILTERS ──────────────────────────────────────────────────────────────────

function applyFilters() {
  const status = document.getElementById("filter-status")?.value || "";
  const resource = document.getElementById("filter-resource")?.value || "";
  const search = (document.getElementById("filter-search")?.value || "").toLowerCase();

  const filtered = allIssues.filter((i) => {
    const matchStatus = !status || i.status.toLowerCase() === status.toLowerCase();
    const matchResource = !resource || String(i.resource_id) === String(resource);
    const matchSearch =
      !search ||
      i.issue.toLowerCase().includes(search) ||
      (resourceMap[i.resource_id] || "").toLowerCase().includes(search);
    return matchStatus && matchResource && matchSearch;
  });

  renderTable(filtered);
}

// ─── MODALS ───────────────────────────────────────────────────────────────────

// ── New Issue Modal ──
function openNewModal() {
  const modal = document.getElementById("modal-new");
  if (modal) {
    document.getElementById("form-issue").value = "";
    document.getElementById("form-resource").value = "";
    modal.classList.remove("hidden");
    modal.querySelector("textarea")?.focus();
  }
}

function closeNewModal() {
  document.getElementById("modal-new")?.classList.add("hidden");
}

async function submitNewIssue() {
  const resource_id = document.getElementById("form-resource")?.value;
  const issue = document.getElementById("form-issue")?.value?.trim();

  if (!resource_id) return showToast("Please select a resource.", "error");
  if (!issue) return showToast("Please describe the issue.", "error");

  const btn = document.getElementById("btn-submit-issue");
  setLoading(btn, true);

  const data = await apiFetch("/maintenance/", {
    method: "POST",
    body: JSON.stringify({ resource_id: parseInt(resource_id), issue, status: "open" }),
  });

  setLoading(btn, false);
  if (data) {
    closeNewModal();
    showToast("Issue reported successfully.", "success");
    await loadMaintenance();
  }
}

// ── Edit / Status Modal ──
function openEditModal(id) {
  const issue = allIssues.find((i) => i.maintenance_id === id);
  if (!issue) return;

  document.getElementById("edit-id").value = id;
  document.getElementById("edit-issue").value = issue.issue;
  document.getElementById("edit-status").value = issue.status;
  document.getElementById("modal-edit")?.classList.remove("hidden");
}

function closeEditModal() {
  document.getElementById("modal-edit")?.classList.add("hidden");
}

async function submitEditIssue() {
  const id = parseInt(document.getElementById("edit-id")?.value);
  const issue = document.getElementById("edit-issue")?.value?.trim();
  const status = document.getElementById("edit-status")?.value;

  if (!issue) return showToast("Issue description cannot be empty.", "error");

  const btn = document.getElementById("btn-submit-edit");
  setLoading(btn, true);

  const data = await apiFetch(`/maintenance/${id}`, {
    method: "PUT",
    body: JSON.stringify({ issue, status }),
  });

  setLoading(btn, false);
  if (data) {
    closeEditModal();
    showToast("Issue updated.", "success");
    await loadMaintenance();
  }
}

// ── Logs Modal ──
async function openLogsModal(id) {
  const issue = allIssues.find((i) => i.maintenance_id === id);
  const modal = document.getElementById("modal-logs");
  const logsContainer = document.getElementById("logs-list");
  const logTitle = document.getElementById("logs-title");

  if (!modal || !logsContainer) return;

  if (logTitle)
    logTitle.textContent = `Logs — Issue #${id}: ${truncate(issue?.issue || "", 40)}`;

  logsContainer.innerHTML = `<p class="loading-text">Loading logs…</p>`;
  modal.classList.remove("hidden");

  document.getElementById("log-maintenance-id").value = id;

  const logs = await apiFetch(`/maintenance/${id}/logs`);
  if (!logs) {
    logsContainer.innerHTML = `<p class="empty-text">Failed to load logs.</p>`;
    return;
  }

  if (logs.length === 0) {
    logsContainer.innerHTML = `<p class="empty-text">No logs yet for this issue.</p>`;
    return;
  }

  logsContainer.innerHTML = logs
    .map(
      (log) => `
    <div class="log-entry">
      <div class="log-meta">${formatDateTime(log.updated_at)}</div>
      <div class="log-text">${escHtml(log.update_text)}</div>
    </div>
  `
    )
    .join("");
}

function closeLogsModal() {
  document.getElementById("modal-logs")?.classList.add("hidden");
}

async function submitLogUpdate() {
  const id = parseInt(document.getElementById("log-maintenance-id")?.value);
  const update_text = document.getElementById("log-update-text")?.value?.trim();

  if (!update_text) return showToast("Log entry cannot be empty.", "error");

  const btn = document.getElementById("btn-submit-log");
  setLoading(btn, true);

  const data = await apiFetch(`/maintenance/${id}/logs`, {
    method: "POST",
    body: JSON.stringify({ update_text }),
  });

  setLoading(btn, false);
  if (data) {
    document.getElementById("log-update-text").value = "";
    showToast("Log added.", "success");
    await openLogsModal(id); // refresh logs in modal
  }
}

// ─── EVENT LISTENERS ──────────────────────────────────────────────────────────

function setupEventListeners() {
  // Filters
  document.getElementById("filter-status")?.addEventListener("change", applyFilters);
  document.getElementById("filter-resource")?.addEventListener("change", applyFilters);
  document.getElementById("filter-search")?.addEventListener("input", applyFilters);

  // New issue button
  document.getElementById("btn-new-issue")?.addEventListener("click", openNewModal);

  // Modal close on backdrop click
  document.querySelectorAll(".modal-backdrop").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target === el) el.classList.add("hidden");
    });
  });

  // Keyboard ESC closes modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-backdrop:not(.hidden)").forEach((m) => {
        m.classList.add("hidden");
      });
    }
  });

  // Logout
  document.getElementById("btn-logout")?.addEventListener("click", () => {
    localStorage.clear();
    window.location.href = "index.html";
  });
}

// ─── UTILITY ──────────────────────────────────────────────────────────────────

function statusClass(status) {
  const map = {
    open: "danger",
    "in-progress": "warning",
    resolved: "success",
    closed: "neutral",
  };
  return map[(status || "").toLowerCase()] || "neutral";
}

function canEdit() {
  return currentUser && (currentUser.role_id === 1 || currentUser.role_id === 2);
}

function escHtml(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str || ""));
  return div.innerHTML;
}

function truncate(str, len) {
  return str && str.length > len ? str.slice(0, len) + "…" : str;
}

function formatDate(dt) {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(dt) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.classList.add("show"), 10);
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function showLoader(show) {
  const el = document.getElementById("table-loader");
  if (el) el.classList.toggle("hidden", !show);
}

function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  btn.textContent = loading ? "Please wait…" : btn.dataset.label || btn.textContent;
}