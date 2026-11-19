"use strict";

// Shared by admin.html and category.html. Only administrators can use these pages.
requireLogin();

const $ = (id) => document.getElementById(id);

// Statuses an admin can choose. "Pending" and "Assigned" are set automatically by the system.
const COMPLAINT_STATUSES = [["In Progress", "In Progress"], ["Resolved", "Resolved"], ["Rejected", "Rejected"]];
const REPORT_STATUSES = [["open", "Open"], ["in_progress", "In Progress"], ["fix_to_verify", "Fix to Verify"], ["closed", "Closed"]];
const REPORT_LABEL = { open: "Open", in_progress: "In Progress", fix_to_verify: "Fix to Verify", closed: "Closed", pending: "Pending" };
const labelFor = (s) => REPORT_LABEL[s] || s;

function setStatus(message, isError = false) {
  const el = $("status");
  if (!el) return;
  el.textContent = message;
  el.classList.toggle("error", isError);
}

// /api/me returns { user: {...}, is_admin, is_technician, worker_id }.
async function checkAdmin() {
  try {
    const data = await api("/api/me");
    const user = data.user || data;
    if (user.role !== "admin") {
      // A stale admin login that the server no longer confirms is signed out (avoids redirect loops).
      if (Auth.user && Auth.user.role === "admin") { Auth.clear(); location.href = "index.html"; }
      else if (user.role === "technician" || user.role === "technision") location.href = "technician.html";
      else location.href = "dashboard.html";
      return false;
    }
    Auth.save(Auth.token, user);
    if ($("adminName")) $("adminName").textContent = user.name;
    return true;
  } catch (err) {
    // Slow or unreachable server: keep the login, show the reason. Logout still works; press Refresh to retry.
    setStatus(err.message, true);
    return false;
  }
}

async function checkStaff() {
  try {
    const data = await api("/api/me");
    const user = data.user || data;
    const isStaff = user.role === "admin" || user.role === "technician" || user.role === "technision" || data.is_admin || data.is_technician;
    if (!isStaff) {
      location.href = "dashboard.html";
      return false;
    }
    Auth.save(Auth.token, user);
    if ($("adminName")) $("adminName").textContent = user.name;
    return data;
  } catch (err) {
    setStatus(err.message, true);
    return false;
  }
}

// The Logout button is wired inline in each page (it must work even if this file or the server fails).

// ---------------------------------------------------------------- table helpers
function addCell(row, value) {
  const cell = document.createElement("td");
  cell.style.whiteSpace = "pre-line";
  cell.textContent = value ?? "-";
  row.appendChild(cell);
  return cell;
}

// A status cell; "Pending" is highlighted so the admin notices work that has no worker yet.
function addStatusCell(row, status) {
  const cell = document.createElement("td");
  const tag = document.createElement("span");
  tag.textContent = labelFor(status);
  if (status === "Pending" || status === "pending") tag.className = "badge-pending";
  cell.appendChild(tag);
  row.appendChild(cell);
  if (tag.className) row.classList.add("pending-row");
}

function emptyRow(box, cols, text) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = cols;
  cell.textContent = text;
  row.appendChild(cell);
  box.appendChild(row);
}

// A <td> with a status list + button. `save(newStatus)` must return a promise.
function statusCell(current, options, save) {
  const cell = document.createElement("td");
  const select = document.createElement("select");
  const known = options.some(([v]) => v === current);
  if (!known) {
    const ph = document.createElement("option");
    ph.value = ""; ph.textContent = "Change status…"; ph.selected = true;
    select.appendChild(ph);
  }
  options.forEach(([value, label]) => {
    const o = document.createElement("option");
    o.value = value; o.textContent = label;
    select.appendChild(o);
  });
  if (known) select.value = current;

  const btn = document.createElement("button");
  btn.textContent = "Update Status";
  btn.addEventListener("click", async () => {
    if (!select.value) return setStatus("Choose a status first.", true);
    const label = btn.textContent;
    btn.disabled = true; btn.textContent = "Updating…";   // instant feedback
    setStatus("Updating…");
    try { await save(select.value); }
    catch (err) { setStatus(err.message, true); }
    finally { btn.disabled = false; btn.textContent = label; }
  });
  cell.append(select, btn);
  return cell;
}

const matches = (values, q) => values.join(" ").toLowerCase().includes(q);
const clip = (t, n = 70) => (t && t.length > n ? t.slice(0, n - 1) + "…" : t || "");

// Small row of category links shown at the top of both admin pages.
async function renderCategoryNav(boxId, activeCat, cats) {
  const categories = cats || (await api("/api/admin/categories")).categories;   // reuse the data if the page already has it
  const box = $(boxId);
  box.replaceChildren();
  const home = document.createElement("a");
  home.href = "admin.html"; home.className = "tab-link" + (activeCat ? "" : " active"); home.textContent = "Overview";
  box.appendChild(home);
  categories.forEach((c) => {
    const a = document.createElement("a");
    a.href = "category.html?cat=" + encodeURIComponent(c.category);
    a.className = "tab-link" + (c.category === activeCat ? " active" : "");
    a.textContent = c.category;
    if (c.pending > 0) {
      const b = document.createElement("span");
      b.className = "badge-pending small"; b.textContent = c.pending;
      a.append(" ", b);
    }
    box.appendChild(a);
  });
  return categories;
}