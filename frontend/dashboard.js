requireLogin();

const $ = (id) => document.getElementById(id);
const statusEl = $("status");

// Navigation shortcuts for staff/admins
if (Auth.user) {
  const nav = document.querySelector(".topbar-nav");
  if (nav) {
    if (Auth.user.role === "admin") {
      const a = document.createElement("a");
      a.href = "admin.html";
      a.className = "topbar-btn";
      a.innerHTML = "<span>⚙️ Admin Panel</span>";
      nav.appendChild(a);
    } else if (Auth.user.role === "technician" || Auth.user.role === "technision") {
      const a = document.createElement("a");
      a.href = "technician.html";
      a.className = "topbar-btn";
      a.innerHTML = "<span>🔧 Technician Portal</span>";
      nav.appendChild(a);
    }
  }
}

const REPORT_LABELS = {
  open: "Open", in_progress: "In progress", fix_to_verify: "Fix to verify", closed: "Closed", pending: "Pending",
};

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
}

$("userName").textContent = Auth.user ? Auth.user.name : "";

$("logout").addEventListener("click", logout);   // logout() is in api.js: instant, does not wait for the server

$("bell").addEventListener("click", () => {
  $("notifCard").scrollIntoView({ behavior: "smooth" });
});

// ---------------------------------------------------------------- submit
$("complaintForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("submitBtn");
  btn.disabled = true;
  setStatus("Analysing your complaint...");
  try {
    const data = await api("/api/complaints", {
      method: "POST",
      body: { text: $("complaint").value.trim(), ward: $("ward").value },
    });
    showResult(data);
    $("complaintForm").reset();
    setStatus("");
    loadComplaints();
    loadNotifications();
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    btn.disabled = false;
  }
});

function showResult(data) {
  const c = data.complaint;
  $("result").classList.remove("hidden");
  const catText = c.category ? ` · ${c.category}` : "";
  const deptText = c.department ? ` (${c.department})` : "";
  $("resCategory").textContent = `#${c.id} · ${c.status}${catText}${deptText}`;
  $("resMessage").textContent = data.notification.message;

  const box = $("resSimilar");
  box.replaceChildren();
  if (data.similar && data.similar.length) box.appendChild(el("h3", "", "Similar resolved complaints"));
  (data.similar || []).forEach((m) => {
    const card = el("div", "match");
    const meta = el("div", "meta", `Similarity ${m.similarity} · ${m.ward}${m.category ? " · " + m.category : ""}`);
    if (data.possible_duplicate && m === data.similar[0]) meta.appendChild(el("span", "badge", "Possible duplicate"));
    const res = el("div", "");
    res.append(el("strong", "", "Resolution: "), document.createTextNode(m.resolution));
    const days = m.resolution_days ? `Resolved in ${m.resolution_days} day(s)` : "";
    card.append(meta, el("div", "", m.text), res, el("div", "meta", days));
    box.appendChild(card);
  });
  $("result").scrollIntoView({ behavior: "smooth" });
}

// ---------------------------------------------------------------- my complaints (status is read-only)
async function loadComplaints() {
  const { complaints } = await api("/api/complaints");
  const box = $("myComplaints");
  box.replaceChildren();
  if (!complaints.length) { box.appendChild(el("p", "muted", "You have not submitted any complaints yet.")); return; }
  complaints.forEach((c) => {
    const card = el("div", "match");
    const catLabel = c.category ? ` · ${c.category}` : "";
    const meta = el("div", "meta", `#${c.id} · ${fmtDate(c.created_at)}${c.ward ? " · " + c.ward : ""}${catLabel}`);
    meta.appendChild(el("span", "pill", c.status));
    card.append(meta, el("div", "", c.text));
    box.appendChild(card);
  });
}

// ---------------------------------------------------------------- my map reports (status is read-only)
async function loadMyReports() {
  const box = $("myReports");
  if (!box) return;
  const { reports } = await api("/api/reports/mine");
  box.replaceChildren();
  if (!reports.length) {
    box.appendChild(el("p", "muted", "You have not filed any map reports yet."));
    return;
  }
  reports.forEach((r) => {
    const card = el("div", "match");
    const meta = el("div", "meta", `#${r.id} · ${fmtDate(r.created_at)}${r.area ? " · " + r.area : ""}`);
    meta.appendChild(el("span", "pill", REPORT_LABELS[r.status] || r.status));
    card.append(el("strong", "", r.title), meta, el("div", "", r.text));
    box.appendChild(card);
  });
}

// ---------------------------------------------------------------- notifications
async function loadNotifications() {
  const { notifications, unread } = await api("/api/notifications");
  const badge = $("badge");
  badge.textContent = unread;
  badge.classList.toggle("hidden", unread === 0);

  const box = $("notifList");
  box.replaceChildren();
  if (!notifications.length) { box.appendChild(el("p", "muted", "No notifications yet.")); return; }
  notifications.forEach((n) => {
    const item = el("div", "notif" + (n.is_read ? "" : " unread"));
    item.append(el("strong", "", n.title), el("p", "", n.message),
      el("div", "meta", fmtDate(n.created_at)));
    item.addEventListener("click", async () => {
      if (n.is_read) return;
      await api(`/api/notifications/${n.id}/read`, { method: "POST" });
      loadNotifications();
    });
    box.appendChild(item);
  });
}

$("readAll").addEventListener("click", async () => {
  await api("/api/notifications/read-all", { method: "POST" });
  loadNotifications();
});

loadComplaints().catch((e) => setStatus(e.message, true));
loadMyReports().catch((e) => setStatus(e.message, true));
loadNotifications().catch((e) => setStatus(e.message, true));
setInterval(() => {
  loadNotifications().catch(() => { });
  loadMyReports().catch(() => { });
}, 30000);