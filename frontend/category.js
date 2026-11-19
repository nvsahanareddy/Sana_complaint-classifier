"use strict";
// Separate dashboard for ONE category. Shared helpers are in admin-common.js.

const CAT = new URLSearchParams(location.search).get("cat");
if (!CAT) location.href = "admin.html";

function renderCategory(d) {
  document.title = d.category + " | Category Dashboard";
  $("catTitle").textContent = d.category;
  $("catDept").textContent = "Department: " + d.department;
  $("sWorkers").textContent = d.workers.length;
  $("sActive").textContent = `${d.active} / ${d.capacity}`;
  $("sPending").textContent = d.pending.length;
  $("sResolved").textContent = d.resolved;
  $("sTotal").textContent = d.total;
  $("pendingCard").classList.toggle("has-pending", d.pending.length > 0);

  // Workers and what each of them is doing now
  const wb = $("workerTable"); wb.replaceChildren();
  if (!d.workers.length) emptyRow(wb, 3, "No workers found for this category.");
  d.workers.forEach((w) => {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const link = document.createElement("a");
    link.href = "technician.html?id=" + w.id; link.textContent = w.name;
    nameCell.appendChild(link); row.appendChild(nameCell);
    const load = addCell(row, `${w.load} / ${w.capacity} jobs${w.load >= w.capacity ? "  (full)" : ""}`);
    if (w.load >= w.capacity) load.style.color = "#bd3030";
    addCell(row, w.items.length ? w.items.map((i) => `${i.kind} #${i.id}: ${clip(i.title, 55)} (${labelFor(i.status)})`).join("\n") : "Free");
    wb.appendChild(row);
  });

  // Pending queue (oldest first)
  const pb = $("pendingTable"); pb.replaceChildren();
  if (!d.pending.length) emptyRow(pb, 5, "No pending work in this category.");
  d.pending.forEach((p) => {
    const row = document.createElement("tr"); row.classList.add("pending-row");
    addCell(row, p.kind); addCell(row, "#" + p.id); addCell(row, clip(p.title, 90)); addCell(row, p.citizen); addCell(row, fmtDate(p.created_at));
    pb.appendChild(row);
  });

  // Complaints
  const cb = $("complaintTable"); cb.replaceChildren();
  if (!d.complaints.length) emptyRow(cb, 8, "No complaints in this category.");
  d.complaints.forEach((c) => {
    const row = document.createElement("tr");
    addCell(row, "#" + c.id); addCell(row, `${c.user_name}\n${c.user_email}`); addCell(row, c.text);
    addCell(row, c.ward || "-"); addCell(row, c.confidence == null ? "-" : `${Math.round(c.confidence * 100)}%`);
    addCell(row, c.worker_name || "Not assigned (pending)");
    addStatusCell(row, c.status);
    row.appendChild(statusCell(c.status, COMPLAINT_STATUSES, async (status) => {
      await api(`/api/admin/complaints/${c.id}/status`, { method: "POST", body: { status } });
      setStatus(`Status updated for complaint #${c.id}.`);
      await load();
    }));
    cb.appendChild(row);
  });

  // Map reports
  const rb = $("reportTable"); rb.replaceChildren();
  if (!d.reports.length) emptyRow(rb, 7, "No map reports in this category.");
  d.reports.forEach((r) => {
    const row = document.createElement("tr");
    addCell(row, "#" + r.id); addCell(row, `${r.reporter}\n${r.reporter_email}`); addCell(row, `${r.title}\n${r.text}`);
    addCell(row, [r.area, r.city].filter(Boolean).join(", ") || "-");
    addCell(row, r.worker_name || "Not assigned (pending)");
    addStatusCell(row, r.status);
    row.appendChild(statusCell(r.status, REPORT_STATUSES, async (status) => {
      await api(`/api/reports/${r.id}/status`, { method: "POST", body: { status } });
      setStatus(`Report #${r.id} is now ${labelFor(status)}.`);
      await load();
    }));
    rb.appendChild(row);
  });
}

async function load() {
  setStatus("Loading…");
  try {
    const [d] = await Promise.all([api("/api/admin/category?name=" + encodeURIComponent(CAT)), renderCategoryNav("catNav", CAT)]);
    renderCategory(d);
    setStatus("Updated successfully.");
  } catch (err) {
    setStatus(err.message, true);
  }
}

$("refreshBtn").addEventListener("click", load);
(async function start() { if (await checkAdmin()) await load(); })();