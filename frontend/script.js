// ─── CONFIG ──────────────────────────────────────────────────────────────
// Point this at your deployed Render URL, or http://localhost:8000 for local testing.
const API_BASE = "http://localhost:8000";

// ─── STATE (in-memory only — refresh the page and you're logged out) ──────
let accessToken = null;
let refreshToken = null;
let accessExpiresAt = null;   // epoch ms
let countdownInterval = null;
let autoRefreshTimeout = null;

// ─── DOM REFS ────────────────────────────────────────────────────────────
const authCard = document.getElementById("authCard");
const sessionCard = document.getElementById("sessionCard");
const statusBox = document.getElementById("statusBox");

const tabLogin = document.getElementById("tabLogin");
const tabSignup = document.getElementById("tabSignup");
const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");

const sessionName = document.getElementById("sessionName");
const sessionEmail = document.getElementById("sessionEmail");
const accessExpiry = document.getElementById("accessExpiry");
const accessTokenDisplay = document.getElementById("accessTokenDisplay");
const refreshTokenDisplay = document.getElementById("refreshTokenDisplay");
const eventLog = document.getElementById("eventLog");

// ─── TAB SWITCHING ───────────────────────────────────────────────────────
function showLogin() {
    tabLogin.classList.add("tab--active");
    tabSignup.classList.remove("tab--active");
    loginForm.classList.add("form--active");
    signupForm.classList.remove("form--active");
    hideStatus();
}
function showSignup() {
    tabSignup.classList.add("tab--active");
    tabLogin.classList.remove("tab--active");
    signupForm.classList.add("form--active");
    loginForm.classList.remove("form--active");
    hideStatus();
}
tabLogin.addEventListener("click", showLogin);
tabSignup.addEventListener("click", showSignup);
document.getElementById("goToSignup").addEventListener("click", (e) => { e.preventDefault(); showSignup(); });
document.getElementById("goToLogin").addEventListener("click", (e) => { e.preventDefault(); showLogin(); });

// ─── STATUS MESSAGES ─────────────────────────────────────────────────────
function showStatus(message, isError) {
    statusBox.textContent = message;
    statusBox.hidden = false;
    statusBox.className = "status " + (isError ? "status--error" : "status--ok");
}
function hideStatus() {
    statusBox.hidden = true;
}

// ─── EVENT LOG (visual proof of the refresh cycle) ──────────────────────
function logEvent(text) {
    const line = document.createElement("div");
    const time = new Date().toLocaleTimeString();
    line.textContent = `[${time}] ${text}`;
    eventLog.prepend(line);
}

// ─── SIGNUP ──────────────────────────────────────────────────────────────
signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();
    const full_name = document.getElementById("signupName").value;
    const email = document.getElementById("signupEmail").value;
    const password = document.getElementById("signupPassword").value;

    try {
        const res = await fetch(`${API_BASE}/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ full_name, email, password }),
        });
        const data = await res.json();

        if (!res.ok) {
            showStatus(data.detail || "Signup failed", true);
            return;
        }

        onAuthSuccess(data, full_name, email);
    } catch (err) {
        showStatus("Could not reach the API. Check API_BASE in script.js.", true);
    }
});

// ─── LOGIN ───────────────────────────────────────────────────────────────
loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();
    const email = document.getElementById("loginEmail").value;
    const password = document.getElementById("loginPassword").value;

    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();

        if (!res.ok) {
            showStatus(data.detail || "Login failed", true);
            return;
        }

        onAuthSuccess(data, null, email);
    } catch (err) {
        showStatus("Could not reach the API. Check API_BASE in script.js.", true);
    }
});

// ─── ON SUCCESSFUL LOGIN/SIGNUP ─────────────────────────────────────────
async function onAuthSuccess(tokenData, knownName, email) {
    accessToken = tokenData.access_token;
    refreshToken = tokenData.refresh_token;
    accessExpiresAt = Date.now() + tokenData.expires_in_minutes * 60 * 1000;

    logEvent(`Logged in — access token valid ${tokenData.expires_in_minutes} min`);

    // Fetch profile via /auth/me to prove the access token actually works
    let displayName = knownName;
    try {
        const meRes = await fetch(`${API_BASE}/auth/me`, {
            headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (meRes.ok) {
            const me = await meRes.json();
            displayName = me.full_name;
            logEvent("GET /auth/me succeeded — token verified");
        }
    } catch (_) { }

    sessionName.textContent = displayName || "Welcome";
    sessionEmail.textContent = email;
    renderTokens();

    authCard.hidden = true;
    sessionCard.hidden = false;

    startCountdown();
    scheduleAutoRefresh(tokenData.expires_in_minutes);
}

function renderTokens() {
    accessTokenDisplay.textContent = accessToken;
    refreshTokenDisplay.textContent = refreshToken;
}

// ─── COUNTDOWN DISPLAY ───────────────────────────────────────────────────
function startCountdown() {
    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = setInterval(() => {
        const msLeft = accessExpiresAt - Date.now();
        if (msLeft <= 0) {
            accessExpiry.textContent = "expired";
            accessExpiry.classList.add("expiring");
            return;
        }
        const totalSec = Math.floor(msLeft / 1000);
        const mm = String(Math.floor(totalSec / 60)).padStart(2, "0");
        const ss = String(totalSec % 60).padStart(2, "0");
        accessExpiry.textContent = `expires in ${mm}:${ss}`;
        accessExpiry.classList.toggle("expiring", totalSec <= 30);
    }, 1000);
}

// ─── AUTO REFRESH — the actual access→refresh cycle in action ───────────
function scheduleAutoRefresh(expiresInMinutes) {
    if (autoRefreshTimeout) clearTimeout(autoRefreshTimeout);
    // Refresh 15 seconds before expiry, not exactly at expiry
    const refreshInMs = Math.max(expiresInMinutes * 60 * 1000 - 15000, 2000);
    autoRefreshTimeout = setTimeout(doRefresh, refreshInMs);
}

async function doRefresh() {
    logEvent("Access token nearing expiry — calling /auth/refresh...");
    try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        const data = await res.json();

        if (!res.ok) {
            logEvent(`Refresh failed: ${data.detail || "session expired"}`);
            showStatus("Session expired. Please sign in again.", true);
            logout();
            return;
        }

        accessToken = data.access_token;
        refreshToken = data.refresh_token;
        accessExpiresAt = Date.now() + data.expires_in_minutes * 60 * 1000;
        renderTokens();

        logEvent(`New access token issued — valid ${data.expires_in_minutes} more min`);
        scheduleAutoRefresh(data.expires_in_minutes);
    } catch (err) {
        logEvent("Refresh request failed — network error");
    }
}

document.getElementById("manualRefreshBtn").addEventListener("click", doRefresh);

// ─── LOGOUT ──────────────────────────────────────────────────────────────
document.getElementById("logoutBtn").addEventListener("click", logout);

function logout() {
    accessToken = null;
    refreshToken = null;
    accessExpiresAt = null;
    if (countdownInterval) clearInterval(countdownInterval);
    if (autoRefreshTimeout) clearTimeout(autoRefreshTimeout);
    eventLog.innerHTML = "";

    sessionCard.hidden = true;
    authCard.hidden = false;
    loginForm.reset();
    signupForm.reset();
    showLogin();
}