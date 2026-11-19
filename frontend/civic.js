"use strict";
// Neighbourhood map page. Talks to the FastAPI backend (see reports.py).
// Works when served by FastAPI (port 8000) or opened with Live Server (any other port).
const API_BASE = location.port === "8000" ? "" : "http://127.0.0.1:8000";

const CITIES = {            // name: [lat, lng, zoom]
  "Bengaluru": [12.9716, 77.5946, 11], "Delhi": [28.6139, 77.2090, 11],
  "Mumbai": [19.0760, 72.8777, 11], "Chennai": [13.0827, 80.2707, 11],
  "Hyderabad": [17.3850, 78.4867, 11], "Kolkata": [22.5726, 88.3639, 11],
  "Pune": [18.5204, 73.8567, 11],
};
const STATUS = {
  open:          { label: "Open",          color: "#d98a2b" },
  in_progress:   { label: "In progress",   color: "#4c7fb0" },
  fix_to_verify: { label: "Fix to verify", color: "#3d9a62" },
  closed:        { label: "Closed",        color: "#8a948d" },
  pending:       { label: "Pending",       color: "#c0392b" },   // waiting for a free worker
};
const isAdmin = () => !!(Session.user && Session.user.role === "admin");
// Must match the categories your classifier was trained on.
const ICONS = {
  "Garbage and Sanitation": "🗑️", "Water Supply": "💧", "Roads and Potholes": "🛣️",
  "Street Lights": "💡", "Drainage and Sewage": "🌊", "Noise and Pollution": "🔊",
  "Public Transport": "🚌", "Encroachment and Illegal Construction": "🚧",
};
const iconFor = (cat) => ICONS[cat] || "📍";

// ------------------------------------------------------------------ small helpers
const $ = (id) => document.getElementById(id);
function h(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;   // textContent: no HTML injection
  return n;
}
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
function ago(sqlUtc) {
  const s = (Date.now() - new Date(sqlUtc.replace(" ", "T") + "Z")) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return plural(Math.floor(s / 60), "min") + " ago";
  if (s < 86400) return plural(Math.floor(s / 3600), "hour") + " ago";
  return plural(Math.floor(s / 86400), "day") + " ago";
}
function chip(status) {
  const s = STATUS[status] || STATUS.open;
  const c = h("span", "chip", s.label);
  c.style.setProperty("--c", s.color);
  return c;
}
let toastTimer;
function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "show" + (isError ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, 5500);
}
function setBusy(btn, busy, label) {
  if (busy) { btn.dataset.label = btn.textContent; btn.textContent = label; }
  else if (btn.dataset.label) { btn.textContent = btn.dataset.label; }
  btn.disabled = busy;
}

// ------------------------------------------------------------------ session + API
const Session = {   // same tab storage as api.js (per tab, see api.js)
  get token() { return sessionStorage.getItem("token"); },
  get user() { try { return JSON.parse(sessionStorage.getItem("user") || "null"); } catch { return null; } },
  save(token, user) { sessionStorage.setItem("token", token); sessionStorage.setItem("user", JSON.stringify(user)); },
  clear() { sessionStorage.removeItem("token"); sessionStorage.removeItem("user"); },
};
class NeedLogin extends Error {}
let me = null;          // { user, is_admin } once signed in
let afterLogin = null;  // action to run after a successful sign-in

async function call(path, { method = "GET", body, auth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && Session.token) headers.Authorization = "Bearer " + Session.token;
  let res;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);   // never wait forever for the server
  try {
    res = await fetch(API_BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined, signal: ctrl.signal });
  } catch (e) {
    throw new Error(e && e.name === "AbortError"
      ? "The server is not answering (waited 20 seconds). It may still be starting: wait for 'Application startup complete' in the backend window."
      : "Cannot reach the backend. Is `uvicorn app.main:app --reload` running in the backend folder?");
  } finally {
    clearTimeout(timer);
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && auth) {
    Session.clear(); me = null; renderUser();
    throw new NeedLogin("Please sign in to continue.");
  }
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d
      : Array.isArray(d) ? d.map((x) => x.msg).join(", ")
      : `Request failed (${res.status})`);
  }
  return data;
}
function fail(e) {
  if (e instanceof NeedLogin) openAuth("login"); else toast(e.message, true);
}
function requireAuth(fn) {
  if (!Session.token) { afterLogin = fn; openAuth("login"); return; }
  fn();
}

// ------------------------------------------------------------------ map
const map = L.map("map").setView([12.9716, 77.5946], 11);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
const markers = L.layerGroup().addTo(map);
let draftMarker = null, draftPoint = null, pickMode = false;

function pinIcon(status, extra = "") {
  const color = (STATUS[status] || STATUS.open).color;     // from our own constants, safe in HTML
  return L.divIcon({ className: "pin-wrap", html: `<span class="pin ${extra}" style="--c:${color}"></span>`,
                     iconSize: [24, 24], iconAnchor: [12, 12] });
}

// ------------------------------------------------------------------ reports: load + render
let reports = [], showAll = false;

async function loadReports() {
  try {
    const d = await call("/api/reports", { auth: true });
    reports = d.reports;
    $("sNeeds").textContent = d.stats.needs_attention;
    $("sChecks").textContent = d.stats.checks;
    $("sClosed").textContent = d.stats.closed_this_week;
    $("navCount").textContent = reports.length;
    renderMap(); renderFeed();
  } catch (e) { fail(e); }
}

function renderMap() {
  markers.clearLayers();
  reports.filter((r) => isAdmin() || r.status !== "closed").forEach((r) => {   // admin sees every status
    const m = L.marker([r.lat, r.lng], { icon: pinIcon(r.status), title: r.title });
    m.on("click", () => openDetail(r.id));
    markers.addLayer(m);
  });
}

function renderFeed() {
  const list = $("feed");
  list.replaceChildren();
  let items = reports.slice();
  if (!showAll) {   // fewest checks first: those are the ones that need a second look
    items = items.filter((r) => r.status !== "closed")
                 .sort((a, b) => a.checks - b.checks || b.id - a.id).slice(0, 8);
  }
  if (!items.length) list.append(h("li", "empty", "No reports yet. Be the first to put an issue on the map."));
  items.forEach((r) => {
    const li = h("li");
    const btn = h("button", "feed-btn"); btn.type = "button";
    const info = h("div");
    info.append(h("div", "feed-title", r.title),
                h("div", "feed-meta", `${r.area || r.city || "Pinned location"} · ${ago(r.created_at)}${isAdmin() ? " · " + (r.worker_name || "No worker yet") : ""}`),
                chip(r.status));
    const checks = h("div", "feed-checks");
    checks.append(h("b", "", r.checks), h("span", "", r.checks === 1 ? "check" : "checks"));
    btn.append(h("div", "feed-ico", iconFor(r.category)), info, checks);
    btn.addEventListener("click", () => { map.flyTo([r.lat, r.lng], 15); openDetail(r.id); });
    li.append(btn); list.append(li);
  });
  $("viewAll").textContent = showAll ? "Show fewer" : `View all ${reports.length} reports →`;
}

// ------------------------------------------------------------------ report form
let analysisFresh = false, lastAnalysis = null;

function setPin(lat, lng) {
  draftPoint = { lat, lng };
  if (draftMarker) draftMarker.setLatLng([lat, lng]);
  else draftMarker = L.marker([lat, lng], { icon: pinIcon("open", "pin-new"), zIndexOffset: 1000 }).addTo(map);
  $("locText").textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  analysisFresh = false;
}
function locate(cb) {
  if (!navigator.geolocation) { toast("Your browser can't share your location. Tap the map instead.", true); return; }
  navigator.geolocation.getCurrentPosition(
    (p) => cb(p.coords.latitude, p.coords.longitude),
    () => toast("Couldn't get your location. Allow it in the browser, or tap the map instead.", true),
    { enableHighAccuracy: true, timeout: 10000 });
}
function showFormError(msg) { const e = $("formError"); e.textContent = msg; e.hidden = false; }
function clearFormError() { $("formError").hidden = true; }

function openReport() {
  if (Session.user && Session.user.role === "admin") {
    toast("Admins manage reports in the admin panel. Use a citizen account to file one.", true);
    return;
  }
  requireAuth(() => {
    if (!$("fCity").value) $("fCity").value = $("city").value;
    if (!$("reportDlg").open) $("reportDlg").showModal();
  });
}
function resetForm() {
  ["fCategory", "fTitle", "fText", "fArea"].forEach((id) => { $(id).value = ""; });
  $("analysis").hidden = true; $("analysis").replaceChildren();
  analysisFresh = false; lastAnalysis = null; clearFormError();
  if (draftMarker) { map.removeLayer(draftMarker); draftMarker = null; }
  draftPoint = null; $("locText").textContent = "No pin yet";
}
function formValues() {
  return { title: $("fTitle").value.trim(), text: $("fText").value.trim(),
           city: $("fCity").value.trim(), area: $("fArea").value.trim(),
           lat: draftPoint ? draftPoint.lat : null, lng: draftPoint ? draftPoint.lng : null };
}

function panel(title, cls = "") {
  const p = h("div", "panel " + cls);
  p.append(h("h3", "", title));
  return p;
}

function renderAnalysis(a) {
  const box = $("analysis");
  box.replaceChildren();

  if (a.category) {   // admins only; users never receive a category
  const cat = panel("What the model thinks");
  const line = h("div");
  line.append(h("strong", "", `${iconFor(a.category)} ${a.category}`),
              document.createTextNode(` · ${Math.round(a.confidence * 100)}% confident`));
  const bar = h("div", "bar"); const fill = h("i"); fill.style.width = Math.round(a.confidence * 100) + "%"; bar.append(fill);
  const note = h("p", "hint", $("fCategory").value
    ? `You chose "${$("fCategory").value}", so that is what will be filed. Department: ${a.department}.`
    : `This will be filed under it unless you pick another type above. Department: ${a.department}.`);
  cat.append(line, bar, note); box.append(cat);
  }

  if (a.possible_duplicates.length) {
    const dup = panel("This may already be reported nearby", "warn");
    const ul = h("ul");
    a.possible_duplicates.forEach((d) => {
      const li = h("li");
      li.append(h("strong", "", d.title),
                h("small", "", `${d.area || "Nearby"} · ${d.distance_m} m away · ${Math.round(d.similarity * 100)}% similar · ${STATUS[d.status].label}`));
      const b = h("button", "ghost small", "View and add a check instead"); b.type = "button";
      b.style.marginTop = "6px";
      b.addEventListener("click", () => { $("reportDlg").close(); map.flyTo([d.lat, d.lng], 16); openDetail(d.id); });
      li.append(b); ul.append(li);
    });
    dup.append(ul, h("p", "hint", "If yours is a different problem, just press Add report again."));
    box.append(dup);
  }

  if (a.past_cases.length) {
    const past = panel(a.typical_days ? `How similar issues were resolved (about ${plural(a.typical_days, "day")})` : "How similar issues were resolved");
    const ul = h("ul");
    a.past_cases.forEach((c) => {
      const li = h("li", "", c.resolution);
      li.append(h("small", "", `${c.ward || "Earlier case"}${c.resolution_days != null ? " · " + plural(c.resolution_days, "day") : ""} · ${Math.round(c.similarity * 100)}% similar`));
      ul.append(li);
    });
    past.append(ul); box.append(past);
  }

  if (a.draft) {   // admins only
  const dr = panel(`Draft email to ${a.department}`, "draft");
  dr.append(h("p", "meta", a.draft.summary));
  const ta = h("textarea"); ta.rows = 9; ta.readOnly = true; ta.value = `Subject: ${a.draft.subject}\n\n${a.draft.body}`;
  const row = h("div", "btn-row");
  const copy = h("button", "ghost small", "Copy email"); copy.type = "button";
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(ta.value); toast("Email copied."); }
    catch { ta.select(); toast("Press Ctrl+C to copy.", false); }
  });
  const mail = h("a", "ghost small", "Open in email app");
  mail.href = `mailto:${a.draft.to}?subject=${encodeURIComponent(a.draft.subject)}&body=${encodeURIComponent(a.draft.body)}`;
  row.append(copy, mail); dr.append(ta, row); box.append(dr);
  }
  box.hidden = false;
}

async function analyze() {
  const v = formValues();
  if (v.text.length < 10) { showFormError("Please describe the issue in at least 10 characters."); return false; }
  clearFormError(); setBusy($("analyzeBtn"), true, "Checking…");
  try {
    lastAnalysis = await call("/api/reports/preview", { method: "POST", body: v, auth: true });
    analysisFresh = true; renderAnalysis(lastAnalysis);
    return true;
  } catch (e) { fail(e); return false; }
  finally { setBusy($("analyzeBtn"), false); }
}

async function submitReport() {
  const v = formValues();
  if (v.title.length < 3) return showFormError("Add a short title (at least 3 characters).");
  if (v.text.length < 10) return showFormError("Please describe the issue in at least 10 characters.");
  if (!draftPoint) return showFormError("Pin the location: use your location or choose a spot on the map.");
  clearFormError();

  if (!analysisFresh) {   // run the duplicate check first; if something similar is nearby, ask before filing
    if (!(await analyze())) return;
    if (lastAnalysis.possible_duplicates.length) {
      toast("Similar reports exist nearby. Add a check to one of them, or press Add report again to file a new one.");
      $("analysis").scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
  }
  setBusy($("submitReport"), true, "Adding…");
  try {
    const res = await call("/api/reports", { method: "POST", auth: true,
      body: { title: v.title, text: v.text, category: $("fCategory").value,
              city: v.city, area: v.area, lat: v.lat, lng: v.lng } });
    $("reportDlg").close(); resetForm();
    toast("Report added. Thank you!");
    await loadReports();
    map.flyTo([res.report.lat, res.report.lng], 15);
  } catch (e) { fail(e); }
  finally { setBusy($("submitReport"), false); }
}

// ------------------------------------------------------------------ report detail
async function openDetail(id) {
  const dlg = $("detailDlg"), body = $("detailBody");
  if (!dlg.open) { body.replaceChildren(h("p", "muted", "Loading…")); dlg.showModal(); }
  try { renderDetail(await call(`/api/reports/${id}`, { auth: true })); }
  catch (e) { dlg.close(); fail(e); }
}

function renderDetail(d) {
  const r = d.report, body = $("detailBody");
  body.replaceChildren();

  const head = h("div");
  const x = h("button", "x", "×"); x.type = "button"; x.setAttribute("aria-label", "Close");
  x.style.float = "right"; x.addEventListener("click", () => $("detailDlg").close());
  head.append(x, h("p", "eyebrow", r.category ? `${iconFor(r.category)} ${r.category}` : "📍 Civic report"), h("h2", "", r.title), chip(r.status),
              h("p", "meta", `${[r.area, r.city].filter(Boolean).join(", ") || "Pinned location"} · ${ago(r.created_at)} · reported by ${r.reporter}`));
  body.append(head, h("p", "", r.text));
  if (me && me.is_admin) {   // admin only: who is doing the work
    body.append(h("p", "meta", `Department: ${r.department || "-"} · Worker: ${r.worker_name || "Not assigned (pending)"}`));
  }

  if (r.status !== "closed" && !(me && me.is_admin)) {   // only regular users add neighbour checks
    const sec = h("div", "panel");
    sec.append(h("h3", "", r.status === "fix_to_verify" ? "Is it really fixed?" : "Passing by? Check on it"),
               h("p", "hint", r.status === "fix_to_verify"
                 ? "Neighbours confirm whether the fix is real. The ward desk reviews these checks before closing the report."
                 : "A quick check from someone nearby helps this report move forward."));
    const note = h("input"); note.placeholder = "Optional note, e.g. “still overflowing this morning”"; note.maxLength = 300;
    note.style.margin = "8px 0";
    const row = h("div", "check-btns");
    const still = h("button", "ghost", "Still there"); still.type = "button";
    const fixed = h("button", "ghost btn-fixed", "Looks fixed"); fixed.type = "button";
    still.addEventListener("click", () => sendCheck(r.id, "still_there", note.value));
    fixed.addEventListener("click", () => sendCheck(r.id, "looks_fixed", note.value));
    row.append(still, fixed); sec.append(note, row); body.append(sec);
  }

  if (d.checks.length) {
    const p = panel(`Neighbour checks (${d.checks.length})`); const ul = h("ul");
    d.checks.forEach((c) => {
      const li = h("li", "", `${c.by}: ${c.kind === "looks_fixed" ? "looks fixed" : "still there"}${c.note ? " — " + c.note : ""}`);
      li.append(h("small", "", ago(c.created_at))); ul.append(li);
    });
    p.append(ul); body.append(p);
  }

  if (d.past_cases.length) {
    const p = panel(d.typical_days ? `What usually happens (about ${plural(d.typical_days, "day")})` : "What usually happens");
    const ul = h("ul");
    d.past_cases.forEach((c) => {
      const li = h("li", "", c.resolution);
      li.append(h("small", "", `${c.ward || "Earlier case"}${c.resolution_days != null ? " · " + plural(c.resolution_days, "day") : ""}`));
      ul.append(li);
    });
    p.append(ul); body.append(p);
  }

  if (me && me.is_admin) {   // ward desk controls: only admins can change status
    const p = panel("Ward desk"); const row = h("div", "btn-row");
    const sel = h("select");   // "Pending" is not listed: it is set by the system
    Object.entries(STATUS).filter(([k]) => k !== "pending").forEach(([k, v]) => { const o = h("option", "", v.label); o.value = k; if (k === r.status) o.selected = true; sel.append(o); });
    const go = h("button", "primary small", "Update status"); go.type = "button";
    go.addEventListener("click", () => setStatus(r.id, sel.value));
    row.append(sel, go); p.append(row); body.append(p);
  }
}

async function sendCheck(id, kind, note) {
  requireAuth(async () => {
    try {
      await call(`/api/reports/${id}/checks`, { method: "POST", auth: true, body: { kind, note: note.trim() } });
      toast("Thanks for checking! The ward desk will review it.");
      await loadReports(); await openDetail(id);
    } catch (e) { fail(e); }
  });
}
async function setStatus(id, status) {
  try {
    await call(`/api/reports/${id}/status`, { method: "POST", auth: true, body: { status } });
    toast("Status updated."); await loadReports(); await openDetail(id);
  } catch (e) { fail(e); }
}

// ------------------------------------------------------------------ sign in / register
let authMode = "login";
function setAuthMode(mode) {
  authMode = mode;
  $("tabLogin").classList.toggle("active", mode === "login");
  $("tabRegister").classList.toggle("active", mode === "register");
  $("nameRow").hidden = mode !== "register";
  $("authSubmit").textContent = mode === "login" ? "Log in" : "Create account";
  $("authPass").autocomplete = mode === "login" ? "current-password" : "new-password";
  $("authError").hidden = true;
}
function openAuth(mode = "login") { setAuthMode(mode); if (!$("authDlg").open) $("authDlg").showModal(); }

async function refreshMe() {
  if (!Session.token) { me = null; return; }
  try { me = await call("/api/me", { auth: true }); } catch { me = null; }
}
function renderUser() {
  const u = Session.user;
  $("userChip").hidden = !u; $("signOutBtn").hidden = !u; $("signInBtn").hidden = !!u;
  if (u) $("userChip").textContent = u.name;
}

$("authForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const email = $("authEmail").value.trim(), password = $("authPass").value, name = $("authName").value.trim();
  const err = $("authError");
  if (!email || !password || (authMode === "register" && !name)) {
    err.textContent = "Please fill in all the fields."; err.hidden = false; return;
  }
  setBusy($("authSubmit"), true, "Please wait…");
  try {
    const body = authMode === "login" ? { email, password } : { name, email, password };
    const data = await call(`/api/auth/${authMode}`, { method: "POST", body });
    Session.save(data.token, data.user);
    await refreshMe(); renderUser();
    $("authDlg").close(); $("authPass").value = "";
    toast(`Welcome, ${data.user.name}!`);
    if (afterLogin) { const f = afterLogin; afterLogin = null; f(); }
  } catch (e) { err.textContent = e.message; err.hidden = false; }
  finally { setBusy($("authSubmit"), false); }
});

// ------------------------------------------------------------------ wiring
Object.keys(ICONS).forEach((c) => { const o = h("option", "", c); o.value = c; $("fCategory").append(o); });
Object.keys(CITIES).forEach((c) => { const o = h("option", "", c); o.value = c; $("city").append(o); });

$("city").addEventListener("change", () => { const [la, ln, z] = CITIES[$("city").value]; map.flyTo([la, ln], z); $("fCity").value = $("city").value; });
$("reportBtn").addEventListener("click", openReport);
$("signInBtn").addEventListener("click", () => { location.href = "index.html"; });
$("signOutBtn").addEventListener("click", () => {   // instant: does not wait for the server
  const token = Session.token;
  Session.clear(); me = null; renderUser();
  try { fetch(API_BASE + "/api/auth/logout", { method: "POST", headers: { Authorization: "Bearer " + token }, keepalive: true }); } catch { /* ignore */ }
  location.href = "index.html?logout=1";
});
$("tabLogin").addEventListener("click", () => setAuthMode("login"));
$("tabRegister").addEventListener("click", () => setAuthMode("register"));
$("locateBtn").addEventListener("click", () => locate((la, ln) => map.flyTo([la, ln], 15)));
$("useGps").addEventListener("click", () => locate((la, ln) => { setPin(la, ln); map.flyTo([la, ln], 16); }));
$("analyzeBtn").addEventListener("click", analyze);
$("submitReport").addEventListener("click", submitReport);
$("viewAll").addEventListener("click", () => { showAll = !showAll; renderFeed(); });
["fTitle", "fText", "fCity", "fArea"].forEach((id) => $(id).addEventListener("input", () => { analysisFresh = false; }));

$("pickOnMap").addEventListener("click", () => {      // close the form, let the user tap the map, then reopen it
  $("reportDlg").close(); pickMode = true; $("pickBanner").hidden = false;
  $("map").scrollIntoView({ behavior: "smooth", block: "center" });
});
$("pickCancel").addEventListener("click", () => { pickMode = false; $("pickBanner").hidden = true; openReport(); });
map.on("click", (e) => {
  if (Session.user && Session.user.role === "admin") return;   // admins do not file reports
  setPin(e.latlng.lat, e.latlng.lng);
  pickMode = false; $("pickBanner").hidden = true;
  openReport();
});

document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
document.querySelectorAll("dialog").forEach((dlg) =>   // click on the dim backdrop closes the dialog
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); }));

(async function init() {
  if (!Session.token) { location.href = "index.html"; return; }   // the map now needs a login
  renderUser();
  await refreshMe();
  if (me && me.is_admin) $("reportBtn").hidden = true;            // admins manage, they don't file
  await loadReports();
})();