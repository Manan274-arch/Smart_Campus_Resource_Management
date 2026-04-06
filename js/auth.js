// auth.js — Handles login and signup

const API = "http://localhost:8000";

// ── Token helpers ─────────────────────────────────────────────
function saveSession(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}
function getToken()  { return localStorage.getItem("token"); }
function getUser()   { const u = localStorage.getItem("user"); return u ? JSON.parse(u) : null; }
function clearSession() { localStorage.removeItem("token"); localStorage.removeItem("user"); }
function isLoggedIn() { return !!getToken(); }

// Redirect if not logged in
function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = "index.html";
  }
}

// ── API helper ────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearSession();
    window.location.href = "index.html";
    return;
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

// ── Auth page logic ───────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Redirect if already logged in
  if (isLoggedIn() && window.location.pathname.endsWith("index.html")) {
    window.location.href = "dashboard.html";
    return;
  }

  // Tab switching
  const tabs = document.querySelectorAll(".auth-tab");
  const loginForm  = document.getElementById("login-form");
  const signupForm = document.getElementById("signup-form");

  if (tabs.length) {
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        tabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        const target = tab.dataset.tab;
        if (target === "login") {
          loginForm.classList.remove("hidden");
          signupForm.classList.add("hidden");
        } else {
          loginForm.classList.add("hidden");
          signupForm.classList.remove("hidden");
        }
        hideAlert("login-alert");
        hideAlert("signup-alert");
      });
    });
  }

  // Login form
  const loginBtn = document.getElementById("login-btn");
  if (loginBtn) {
    loginBtn.addEventListener("click", handleLogin);
  }
  document.getElementById("login-email")?.addEventListener("keydown", e => e.key === "Enter" && handleLogin());
  document.getElementById("login-password")?.addEventListener("keydown", e => e.key === "Enter" && handleLogin());

  // Signup form
  const signupBtn = document.getElementById("signup-btn");
  if (signupBtn) {
    signupBtn.addEventListener("click", handleSignup);
  }
});

async function handleLogin() {
  const email    = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const btn      = document.getElementById("login-btn");

  if (!email || !password) {
    showAlert("login-alert", "error", "Please fill in all fields");
    return;
  }

  setLoading(btn, true, "Signing in...");
  try {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    saveSession(data.access_token, data.user);
    window.location.href = "dashboard.html";
  } catch (err) {
    showAlert("login-alert", "error", err.message);
  } finally {
    setLoading(btn, false, "Sign In");
  }
}

async function handleSignup() {
  const name     = document.getElementById("signup-name").value.trim();
  const email    = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;
  const role_id  = parseInt(document.getElementById("signup-role").value);
  const btn      = document.getElementById("signup-btn");

  if (!name || !email || !password) {
    showAlert("signup-alert", "error", "Please fill in all fields");
    return;
  }
  if (password.length < 6) {
    showAlert("signup-alert", "error", "Password must be at least 6 characters");
    return;
  }

  setLoading(btn, true, "Creating account...");
  try {
    const data = await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password, role_id })
    });
    saveSession(data.access_token, data.user);
    window.location.href = "dashboard.html";
  } catch (err) {
    showAlert("signup-alert", "error", err.message);
  } finally {
    setLoading(btn, false, "Create Account");
  }
}

// ── UI helpers ────────────────────────────────────────────────
function showAlert(id, type, message) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = `alert alert-${type} show`;
  el.textContent = message;
}
function hideAlert(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.remove("show"); el.textContent = ""; }
}
function setLoading(btn, loading, label) {
  if (!btn) return;
  btn.disabled = loading;
  btn.textContent = loading ? label : btn.dataset.label || label;
  if (!btn.dataset.label) btn.dataset.label = label;
}