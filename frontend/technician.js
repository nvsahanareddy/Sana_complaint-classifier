"use strict";
// Dashboard of ONE technician (worker). Shared helpers are in admin-common.js.

let TECH_ID = new URLSearchParams(location.search).get("id");
let currentStaff = null;

function renderTechnician(d) {
  document.title = d.name + " | Technician Dashboard";
  $("techName").textContent = d.name;
  const info = $("techInfo");
  info.replaceChildren();
  const a = document.createElement("a");
  a.href = "category.html?cat=" + encodeURIComponent(d.category); a.textContent = d.category;
  info.append("Category: ", a, "  ·  Department: " + d.department);
  $("sLoad").textContent = `${d.load} / ${d.capacity}`;
  $("sDone").textContent = d.done;
  $("sAvail").textContent = d.load >= d.capacity ? "Full" : "Available";

  const cb = $("complaintTable"); cb.replaceChildren();
  if (!d.complaints.length) emptyRow(cb, 6, "No complaints assigned right now.");
  d.complaints.forEach((c) => {
    const row = document.createElement("tr");
    addCell(row, "#" + c.id); addCell(row, `${c.user_name}\n${c.user_email}`); addCell(row, c.text); addCell(row, c.ward || "-");
    addStatusCell(row, c.status);
    row.appendChild(statusCell(c.status, COMPLAINT_STATUSES, async (status) => {
      await api(`/api/admin/complaints/${c.id}/status`, { method: "POST", body: { status } });
      setStatus(`Status updated for complaint #${c.id}.`);
      await load();
    }));
    cb.appendChild(row);
  });

  const rb = $("reportTable"); rb.replaceChildren();
  if (!d.reports.length) emptyRow(rb, 7, "No map reports assigned right now.");
  d.reports.forEach((r) => {
    const row = document.createElement("tr");
    addCell(row, "#" + r.id); addCell(row, `${r.reporter}\n${r.reporter_email}`); addCell(row, `${r.title}\n${r.text}`);
    addCell(row, [r.area, r.city].filter(Boolean).join(", ") || "-");
    const loc = document.createElement("td"); const l = document.createElement("a");
    l.href = `https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lng}#map=17/${r.lat}/${r.lng}`; l.target = "_blank"; l.rel = "noopener"; l.textContent = "View pin";
    loc.appendChild(l); row.appendChild(loc);
    addStatusCell(row, r.status);
    row.appendChild(statusCell(r.status, REPORT_STATUSES, async (status) => {
      await api(`/api/reports/${r.id}/status`, { method: "POST", body: { status } });
      setStatus(`Report #${r.id} is now ${labelFor(status)}.`);
      await load();
    }));
    rb.appendChild(row);
  });

  const hb = $("historyTable"); hb.replaceChildren();
  if (!d.history.length) emptyRow(hb, 5, "No completed work yet.");
  d.history.forEach((h) => {
    const row = document.createElement("tr");
    addCell(row, h.kind); addCell(row, "#" + h.id); addCell(row, clip(h.title, 90)); addCell(row, labelFor(h.status)); addCell(row, fmtDate(h.created_at));
    hb.appendChild(row);
  });
}

async function load() {
  setStatus("Loading…");
  try {
    const workerUrl = TECH_ID ? `/api/admin/worker?id=${encodeURIComponent(TECH_ID)}` : "/api/admin/worker";
    const [d, cats] = await Promise.all([api(workerUrl), api("/api/admin/categories")]);
    TECH_ID = d.id;
    renderTechnician(d);
    await renderCategoryNav("catNav", d.category, cats.categories);
    setStatus("Updated successfully.");
  } catch (err) {
    setStatus(err.message, true);
  }
}

$("refreshBtn").addEventListener("click", load);
(async function start() {
  currentStaff = await checkStaff();
  if (currentStaff) {
    if (!TECH_ID && currentStaff.worker_id) {
      TECH_ID = currentStaff.worker_id;
    }
    await load();
  }
})();