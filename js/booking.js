// booking.js

let selectedResourceId = null;
let selectedSlotId     = null;
let allResources       = [];
let allSlots           = [];

document.addEventListener("DOMContentLoaded", async () => {
  requireAuth();
  initNav("booking");
  renderUserChip();

  await Promise.all([loadResources(), loadMyBookings()]);
  setupFilters();
});

// ── Load resources ────────────────────────────────────────────
async function loadResources() {
  const container = document.getElementById("resource-list");
  container.innerHTML = `<div class="loading-overlay"><div class="spinner"></div><span>Loading resources...</span></div>`;

  try {
    allResources = await apiFetch("/api/resources/");
    renderResources(allResources);
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><p>Failed to load resources: ${escHtml(err.message)}</p></div>`;
  }
}

function renderResources(resources) {
  const container = document.getElementById("resource-list");
  if (!resources.length) {
    container.innerHTML = `<div class="empty-state"><p>No resources found</p></div>`;
    return;
  }

  container.innerHTML = `<div class="resource-grid">
    ${resources.map(r => `
      <div class="resource-card ${r.status !== "available" ? "disabled" : ""}"
           data-id="${r.resource_id}"
           onclick="selectResource(${r.resource_id})">
        <div class="resource-name">${escHtml(r.name)}</div>
        ${statusBadge(r.status)}
        <div class="resource-meta">
          <span>📍 ${escHtml(r.location || "—")}</span>
          <span>🏷 ${escHtml(r.type_name || "")}</span>
        </div>
      </div>
    `).join("")}
  </div>`;
}

// ── Resource selection ────────────────────────────────────────
async function selectResource(id) {
  selectedResourceId = id;
  selectedSlotId     = null;

  // Highlight selected card
  document.querySelectorAll(".resource-card").forEach(c => c.classList.remove("selected"));
  document.querySelector(`[data-id="${id}"]`)?.classList.add("selected");

  const resource = allResources.find(r => r.resource_id === id);
  document.getElementById("selected-resource-name").textContent = resource?.name || "";

  // Show booking panel
  document.getElementById("booking-panel").classList.remove("hidden");
  document.getElementById("slot-section").classList.add("hidden");
  document.getElementById("book-btn").disabled = true;

  // Load availability if date already set
  const dateInput = document.getElementById("booking-date");
  if (dateInput.value) await loadAvailability();
}

// ── Date change ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("booking-date")?.addEventListener("change", async () => {
    if (selectedResourceId) await loadAvailability();
  });

  document.getElementById("book-btn")?.addEventListener("click", handleBooking);
});

async function loadAvailability() {
  const dateVal = document.getElementById("booking-date").value;
  if (!dateVal || !selectedResourceId) return;

  const container = document.getElementById("slot-grid");
  document.getElementById("slot-section").classList.remove("hidden");
  container.innerHTML = `<div class="spinner" style="margin:16px auto"></div>`;

  try {
    const slots = await apiFetch(`/api/bookings/availability?resource_id=${selectedResourceId}&date=${dateVal}`);
    allSlots = slots;
    renderSlots(slots);
  } catch (err) {
    container.innerHTML = `<p class="text-muted text-sm">Failed to load slots: ${escHtml(err.message)}</p>`;
  }
}

function renderSlots(slots) {
  const container = document.getElementById("slot-grid");
  container.innerHTML = `<div class="slot-grid">
    ${slots.map(s => `
      <button class="slot-btn ${!s.available ? "" : ""}"
              data-id="${s.slot_id}"
              ${!s.available ? "disabled" : ""}
              onclick="selectSlot(${s.slot_id}, this)">
        ${s.start_time} – ${s.end_time}
        ${!s.available ? '<br><small style="color:var(--red)">Booked</small>' : ""}
      </button>
    `).join("")}
  </div>`;
}

function selectSlot(id, btn) {
  selectedSlotId = id;
  document.querySelectorAll(".slot-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
  document.getElementById("book-btn").disabled = false;
}

// ── Create booking ────────────────────────────────────────────
async function handleBooking() {
  const date = document.getElementById("booking-date").value;
  if (!selectedResourceId || !selectedSlotId || !date) {
    showAlert("booking-alert", "error", "Please select a resource, date, and slot");
    return;
  }

  const btn = document.getElementById("book-btn");
  setLoading(btn, true, "Confirming...");
  hideAlert("booking-alert");

  try {
    await apiFetch("/api/bookings/", {
      method: "POST",
      body: JSON.stringify({ resource_id: selectedResourceId, slot_id: selectedSlotId, date })
    });
    showAlert("booking-alert", "success", "Booking confirmed! ✓");
    await Promise.all([loadMyBookings(), loadAvailability()]);
    selectedSlotId = null;
    document.querySelectorAll(".slot-btn").forEach(b => b.classList.remove("selected"));
    document.getElementById("book-btn").disabled = true;
  } catch (err) {
    showAlert("booking-alert", "error", err.message);
  } finally {
    setLoading(btn, false, "Confirm Booking");
  }
}

// ── My bookings ───────────────────────────────────────────────
async function loadMyBookings() {
  const container = document.getElementById("my-bookings");
  container.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;

  try {
    const bookings = await apiFetch("/api/bookings/");
    renderMyBookings(bookings);
  } catch (err) {
    container.innerHTML = `<p class="text-muted text-sm">Failed to load bookings</p>`;
  }
}

function renderMyBookings(bookings) {
  const container = document.getElementById("my-bookings");
  if (!bookings.length) {
    container.innerHTML = `<div class="empty-state"><p>No bookings yet</p></div>`;
    return;
  }

  container.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Resource</th><th>Date</th><th>Slot</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          ${bookings.map(b => `
            <tr>
              <td>${escHtml(b.resource_name || "-")}</td>
              <td>${b.date}</td>
              <td>${b.slot_start || "-"} – ${b.slot_end || "-"}</td>
              <td>${statusBadge(b.status_name)}</td>
              <td>
                ${b.status_name === "confirmed" ? `
                  <button class="btn btn-sm btn-danger"
                    onclick="cancelBooking(${b.booking_id}, this)">Cancel</button>
                ` : ""}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function cancelBooking(id, btn) {
  if (!confirm("Cancel this booking?")) return;
  btn.disabled = true;
  btn.textContent = "Cancelling...";
  try {
    await apiFetch(`/api/bookings/${id}`, { method: "DELETE" });
    await loadMyBookings();
    if (selectedResourceId) await loadAvailability();
  } catch (err) {
    alert("Cancel failed: " + err.message);
    btn.disabled = false;
    btn.textContent = "Cancel";
  }
}

// ── Filters ───────────────────────────────────────────────────
function setupFilters() {
  const typeFilter   = document.getElementById("filter-type");
  const statusFilter = document.getElementById("filter-status");
  const searchInput  = document.getElementById("search-resource");

  // Populate type filter
  const types = [...new Set(allResources.map(r => r.type_name).filter(Boolean))];
  types.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t; opt.textContent = t;
    typeFilter?.appendChild(opt);
  });

  function applyFilters() {
    const type   = typeFilter?.value;
    const status = statusFilter?.value;
    const search = searchInput?.value.toLowerCase();
    let filtered = allResources;
    if (type)   filtered = filtered.filter(r => r.type_name === type);
    if (status) filtered = filtered.filter(r => r.status === status);
    if (search) filtered = filtered.filter(r => r.name.toLowerCase().includes(search));
    renderResources(filtered);
  }

  typeFilter?.addEventListener("change", applyFilters);
  statusFilter?.addEventListener("change", applyFilters);
  searchInput?.addEventListener("input", applyFilters);
}