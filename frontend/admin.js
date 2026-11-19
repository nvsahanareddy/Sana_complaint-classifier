"use strict";
// Admin overview. Shared helpers are in admin-common.js.

let allComplaints = [];
let allReports = [];

// ---------------------------------------------------------------- stats + category dashboards
async function loadStats() {
  const data = await api("/api/admin/stats");
  $("totalComplaints").textContent = data.total_complaints;
  $("totalReports").textContent = data.total_reports;
  $("totalPending").textContent = data.total_pending;
  $("totalUsers").textContent = data.total_users;
  $("totalAdmins").textContent = data.total_admins;
  renderStats("statusStats", data.complaints_by_status);
  renderStats("categoryStats", data.complaints_by_category);
  renderStats("reportStatusStats", data.reports_by_status);
}

function renderStats(elementId, rows) {
  const box = $(elementId);
  box.replaceChildren();
  if (!rows.length) { box.textContent = "No data available."; box.className = "empty"; return; }
  box.className = "";
  rows.forEach((item) => {
    const line = document.createElement("div");
    line.className = "stat-line";
    const name = document.createElement("span");
    name.textContent = labelFor(item.status || item.category);
    const count = document.createElement("strong");
    count.textContent = item.count;
    line.append(name, count);
    box.appendChild(line);
  });
}

async function loadCategories() {
  const { categories } = await api("/api/admin/categories");
  renderCategoryNav("catNav", null, categories);   // same data, no second request
  const box = $("categoryCards");
  box.replaceChildren();
  categories.forEach((c) => {
    const a = document.createElement("a");
    a.className = "cat-card" + (c.pending > 0 ? " has-pending" : "");
    a.href = "category.html?cat=" + encodeURIComponent(c.category);
    const t = document.createElement("h3"); t.textContent = c.category;
    const d = document.createElement("p"); d.className = "muted-small"; d.textContent = c.department;
    const w = document.createElement("div"); w.className = "cat-line"; w.textContent = `Workers: ${c.workers}  ·  Open work: ${c.active} / ${c.capacity}`;
    const r = document.createElement("div"); r.className = "cat-line"; r.textContent = `Resolved: ${c.resolved}  ·  Total: ${c.total}`;
    const p = document.createElement("div");
    p.className = c.pending > 0 ? "badge-pending" : "badge-ok";
    p.textContent = c.pending > 0 ? `${c.pending} pending (no free worker)` : "No pending work";
    a.append(t, d, w, r, p);
    box.appendChild(a);
  });
}

// ---------------------------------------------------------------- pending queue (all categories)
function renderPending() {
  const box = $("pendingTable");
  box.replaceChildren();
  const rows = [
    ...allComplaints.filter((c) => c.status === "Pending").map((c) => ["Complaint", c.id, c.category, c.text, c.created_at, c.user_name]),
    ...allReports.filter((r) => r.status === "pending").map((r) => ["Map report", r.id, r.category, r.title, r.created_at, r.reporter]),
  ].sort((a, b) => String(a[4]).localeCompare(String(b[4])));
  $("pendingCount").textContent = rows.length;
  if (!rows.length) return emptyRow(box, 6, "No pending work. Every complaint and report has a worker.");
  rows.forEach(([type, id, cat, text, when, who]) => {
    const row = document.createElement("tr");
    row.classList.add("pending-row");
    addCell(row, type); addCell(row, "#" + id); addCell(row, cat); addCell(row, clip(text, 90)); addCell(row, who); addCell(row, fmtDate(when));
    box.appendChild(row);
  });
}

// ---------------------------------------------------------------- text complaints
async function loadComplaints() {
  const data = await api("/api/admin/complaints");
  allComplaints = data.complaints || [];
  renderComplaints();
  renderPending();
}

function renderComplaints() {
  const box = $("complaintTable");
  box.replaceChildren();
  const q = $("searchComplaints").value.toLowerCase().trim();
  const rows = allComplaints.filter((c) =>
    matches([c.id, c.user_name, c.user_email, c.text, c.category, c.department, c.worker_name, c.status, c.ward], q));
  if (!rows.length) return emptyRow(box, 10, "No complaints found.");

  rows.forEach((c) => {
    const row = document.createElement("tr");
    addCell(row, "#" + c.id);
    addCell(row, `${c.user_name}\n${c.user_email}`);
    addCell(row, c.text);
    addCell(row, c.category);
    addCell(row, c.confidence == null ? "-" : `${Math.round(c.confidence * 100)}%`);
    addCell(row, c.ward || "-");
    addCell(row, c.department || "-");                         // fixed per category
    addCell(row, c.worker_name || "Not assigned (pending)");   // assigned automatically
    addStatusCell(row, c.status);
    row.appendChild(statusCell(c.status, COMPLAINT_STATUSES, async (status) => {
      await api(`/api/admin/complaints/${c.id}/status`, { method: "POST", body: { status } });
      setStatus(`Status updated for complaint #${c.id}.`);
      await refreshData();
    }));
    box.appendChild(row);
  });
}

// ---------------------------------------------------------------- map reports
async function loadReports() {
  const data = await api("/api/admin/reports");
  allReports = data.reports || [];
  renderReports();
  renderPending();
}

function renderReports() {
  const box = $("reportTable");
  box.replaceChildren();
  const q = $("searchComplaints").value.toLowerCase().trim();
  const rows = allReports.filter((r) =>
    matches([r.id, r.reporter, r.reporter_email, r.title, r.text, r.category, r.area, r.city, r.worker_name, r.status], q));
  if (!rows.length) return emptyRow(box, 10, "No map reports found.");

  rows.forEach((r) => {
    const row = document.createElement("tr");
    addCell(row, "#" + r.id);
    addCell(row, `${r.reporter}\n${r.reporter_email}`);
    addCell(row, `${r.title}\n${r.text}`);
    addCell(row, r.category);
    addCell(row, [r.area, r.city].filter(Boolean).join(", ") || "-");

    const locCell = document.createElement("td");
    const a = document.createElement("a");
    a.href = `https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lng}#map=17/${r.lat}/${r.lng}`;
    a.target = "_blank"; a.rel = "noopener"; a.textContent = "View pin";
    locCell.appendChild(a);
    row.appendChild(locCell);

    addCell(row, r.worker_name || "Not assigned (pending)");
    addCell(row, `Fixed: ${r.fixed_votes}\nStill there: ${r.still_votes}`);
    addStatusCell(row, r.status);
    row.appendChild(statusCell(r.status, REPORT_STATUSES, async (status) => {
      await api(`/api/reports/${r.id}/status`, { method: "POST", body: { status } });
      setStatus(`Report #${r.id} is now ${labelFor(status)}.`);
      await refreshData();
    }));
    box.appendChild(row);
  });
}

// ---------------------------------------------------------------- technicians (every technician has a dashboard)
async function loadTechnicians() {
  const { workers } = await api("/api/admin/workers");
  const box = $("techTable");
  box.replaceChildren();
  workers.forEach((w) => {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const a = document.createElement("a");
    a.href = "technician.html?id=" + w.id; a.textContent = w.name;
    nameCell.appendChild(a); row.appendChild(nameCell);
    addCell(row, w.category);
    addCell(row, `${w.load} / ${w.capacity}`);
    addCell(row, w.done);
    const st = addCell(row, w.load >= w.capacity ? "Full" : "Available");
    st.style.color = w.load >= w.capacity ? "#bd3030" : "#1f7a45";
    box.appendChild(row);
  });
}

// ---------------------------------------------------------------- users
async function loadUsers() {
  const data = await api("/api/admin/users");
  const box = $("userTable");
  box.replaceChildren();
  if (!data.users.length) return emptyRow(box, 5, "No users found.");
  data.users.forEach((u) => {
    const row = document.createElement("tr");
    addCell(row, u.id); addCell(row, u.name); addCell(row, u.email); addCell(row, u.role); addCell(row, u.created_at);
    box.appendChild(row);
  });
}

$("searchComplaints").addEventListener("input", () => { renderComplaints(); renderReports(); });

// Changing one status can free a worker, which assigns pending work, so everything is reloaded.
async function refreshData() {
  await Promise.all([loadStats(), loadCategories(), loadComplaints(), loadReports(), loadTechnicians()]);
}

async function refreshDashboard() {
  setStatus("Loading dashboard...");
  try {
    await Promise.all([refreshData(), loadUsers()]);
    setStatus("Dashboard updated successfully.");
  } catch (err) {
    setStatus(err.message, true);
  }
}

$("refreshBtn").addEventListener("click", refreshDashboard);

(async function startDashboard() {
  if (await checkAdmin()) await refreshDashboard();
})();