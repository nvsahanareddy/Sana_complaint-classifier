const $ = (id) => document.getElementById(id);
const statusEl = $("status");

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
}

// A saved login is only used when the SERVER confirms it (4 seconds at most).
// Otherwise the old login is forgotten and the form stays: this page can never get stuck or loop.
async function checkSavedLogin() {
  const saved = Auth.token;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 4000);
  try {
    const res = await fetch(API_BASE + "/api/me", { headers: { Authorization: "Bearer " + saved }, signal: ctrl.signal });
    if (res.ok) {
      const data = await res.json();
      const user = data.user || data;
      location.href = user.role === "admin" ? "admin.html" : "dashboard.html";
      return;
    }
  } catch { /* the server is not answering */ }
  finally { clearTimeout(timer); }
  if (Auth.token === saved) Auth.clear();   // not if the person has just logged in again
}

if (location.search.indexOf("logout") !== -1) {
  Auth.clear();                                           // ?logout = forget the login and stay here
  try { history.replaceState(null, "", location.pathname); } catch { /* ignore */ }
} else if (Auth.token) {
  checkSavedLogin();
}

function showTab(which) {
  const login = which === "login";
  $("loginForm").classList.toggle("hidden", !login);
  $("registerForm").classList.toggle("hidden", login);
  $("tabLogin").classList.toggle("active", login);
  $("tabRegister").classList.toggle("active", !login);
  setStatus("");
}

$("tabLogin").addEventListener("click", () => showTab("login"));
$("tabRegister").addEventListener("click", () => showTab("register"));

async function submitAuth(path, body) {
  setStatus("Please wait...");

  try {
    const data = await api(path, {
      method: "POST",
      body,
      auth: false
    });

    Auth.save(data.token, data.user);

    if (data.user?.role === "admin" || data.user?.is_admin) {
      location.href = "admin.html";
    } else {
      location.href = "dashboard.html";
    }
  } catch (err) {
    setStatus(err.message, true);
  }
}

$("loginForm").addEventListener("submit", (e) => {
  e.preventDefault();

  submitAuth("/api/auth/login", {
    email: $("loginEmail").value,
    password: $("loginPassword").value
  });
});

$("registerForm").addEventListener("submit", (e) => {
  e.preventDefault();

  submitAuth("/api/auth/register", {
    name: $("regName").value,
    email: $("regEmail").value,
    password: $("regPassword").value
  });
});

// Check whether the backend is running.
api("/api/health", { auth: false }).catch((err) => {
  const box = $("serverWarning");
  box.textContent = err.message;
  box.classList.remove("hidden");
});