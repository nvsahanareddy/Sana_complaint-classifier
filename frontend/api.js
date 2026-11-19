// Shared helpers: talk to the backend + keep the login token.
// Works when served by FastAPI (port 8000) or opened with Live Server (any other port).
const API_BASE = location.port === "8000" ? "" : "http://127.0.0.1:8000";
const API_TIMEOUT_MS = 20000;   // never wait forever for the server

// The login is kept per TAB (sessionStorage), not per browser. So an admin tab and a user tab can be open
// at the same time and one can never overwrite the other's token. Closing the tab logs out.
const Auth = {
  get token() { return sessionStorage.getItem("token"); },
  get user() {
    try { return JSON.parse(sessionStorage.getItem("user") || "null"); } catch { return null; }
  },
  save(token, user) {
    sessionStorage.setItem("token", token);
    sessionStorage.setItem("user", JSON.stringify(user));
  },
  clear() { sessionStorage.removeItem("token"); sessionStorage.removeItem("user"); },
};
// Older versions kept the login in localStorage (shared by all tabs, never expiring in the browser).
// Those old tokens are the usual cause of "stuck" pages, so they are removed and never read again.
try { localStorage.removeItem("token"); localStorage.removeItem("user"); } catch { /* ignore */ }

function requireLogin() {
  if (!Auth.token) location.href = "index.html";
}

// Log out at once: forget the login in this browser, tell the server in the background,
// and go to the login page. It does NOT wait for the server, so it always works.
function logout() {
  const token = Auth.token;
  Auth.clear();
  try {
    fetch(API_BASE + "/api/auth/logout", { method: "POST", headers: { Authorization: "Bearer " + token }, keepalive: true });
  } catch { /* the server will expire the session by itself */ }
  location.href = "index.html?logout=1";
}

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && Auth.token) headers.Authorization = `Bearer ${Auth.token}`;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
  let res;
  try {
    res = await fetch(API_BASE + path, {
      method, headers, body: body ? JSON.stringify(body) : undefined, signal: ctrl.signal,
    });
  } catch (e) {
    throw new Error(e && e.name === "AbortError"
      ? "The server is not answering (waited 20 seconds). It may still be starting: wait for 'Application startup complete' in the backend window, then press Refresh."
      : "Cannot reach the backend. Is `uvicorn app.main:app --reload` running in the backend folder?");
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401 && auth) {
    Auth.clear();
    location.href = "index.html?logout=1";
    throw new Error("Session expired. Please log in again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d
      : Array.isArray(d) ? d.map((x) => x.msg).join(", ")
      : `Request failed (${res.status})`);
  }
  return data;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;   // textContent avoids HTML injection
  return node;
}

function fmtDate(sqliteUtc) {
  if (!sqliteUtc) return "";
  const isoStr = sqliteUtc.includes("T") ? sqliteUtc : sqliteUtc.replace(" ", "T") + (sqliteUtc.endsWith("Z") ? "" : "Z");
  const d = new Date(isoStr);
  return isNaN(d.getTime()) ? String(sqliteUtc) : d.toLocaleString();
}