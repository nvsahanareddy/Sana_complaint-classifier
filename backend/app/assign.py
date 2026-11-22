"""Departments, workers and automatic assignment of work.

Every category has one fixed department and a team of workers. New work (a complaint or a
map report) is given to the least busy worker of its category. When every worker is full the
item waits as "Pending" and is assigned automatically as soon as a worker finishes something.
"""
import os

CATEGORY_DEPARTMENT = {
    "Roads and Potholes": "Public Works Department",
    "Garbage and Sanitation": "Solid Waste Management",
    "Street Lights": "Electricity and Street Lighting Department",
    "Water Supply": "Water Supply and Sewerage Board",
    "Drainage and Sewage": "Drainage and Sewerage Division",
    "Noise and Pollution": "Pollution Control Board",
    "Public Transport": "Transport Department",
    "Encroachment and Illegal Construction": "Town Planning Department",
}
CATEGORIES = list(CATEGORY_DEPARTMENT)
DEPARTMENTS = set(CATEGORY_DEPARTMENT.values()) | {
    "Water Supply Board",
    "Electricity Department",
    "Sewerage Board",
    "Transport Corporation",
    "Municipal Office",
}

# Sample workers: 4 per category (edit the names here before the first run, or in the workers table).
MAX_WORKERS_PER_CATEGORY = 4
WORKERS = {
    "Roads and Potholes": ["Ravi Kumar", "Suresh Gowda", "Manjunath Reddy", "Prakash Naik"],
    "Garbage and Sanitation": ["Lakshmi Devi", "Mohan Raj", "Savitha Rao", "Basavaraj Patil"],
    "Street Lights": ["Anil Shetty", "Vijay Kumar", "Harish Babu", "Nagaraj Hegde"],
    "Water Supply": ["Sugamya", "Shankar Gowda", "Geetha Nair", "Dinesh Kamath"],
    "Drainage and Sewage": ["Venkatesh Iyer", "Kiran Kumar", "Pradeep Joshi", "Mahesh Acharya"],
    "Noise and Pollution": ["Sunitha Rao", "Arun Prasad", "Deepa Shenoy", "Rajesh Bhat"],
    "Public Transport": ["Siddharth Menon", "Naveen Gowda", "Kavitha Reddy", "Girish Kulkarni"],
    "Encroachment and Illegal Construction": ["Srinivas Rao", "Vinod Kumar", "Anitha Shetty", "Ashok Naik"],
}

# How many open jobs one worker can hold at the same time (complaints + map reports together).
WORKER_CAPACITY = int(os.environ.get("WORKER_CAPACITY", "3"))

COMPLAINT_ACTIVE = ("Submitted", "Assigned", "In Progress")
REPORT_ACTIVE = ("open", "in_progress", "fix_to_verify")
_C = ",".join("?" * len(COMPLAINT_ACTIVE))
_R = ",".join("?" * len(REPORT_ACTIVE))


def department_for(category):
    return CATEGORY_DEPARTMENT.get(category, "Municipal Office")


def worker_id_for_user(conn, user):
    row = conn.execute(
        """
        SELECT id FROM workers
        WHERE user_id = ? OR email = ?
        ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (user["id"], user.get("email", ""), user["id"]),
    ).fetchone()
    return row["id"] if row else None


def seed_workers(conn):
    if conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]:
        return
    for cat, names in WORKERS.items():
        for n in names:
            conn.execute("INSERT INTO workers (name, category) VALUES (?, ?)", (n, cat))


def worker_loads(conn, category):
    """[(worker_id, name, number of open jobs)] for the active workers of a category."""
    rows = conn.execute(
        f"""
        SELECT w.id, w.name,
               (SELECT COUNT(*) FROM complaints c WHERE c.worker_id = w.id AND c.status IN ({_C}))
             + (SELECT COUNT(*) FROM reports r WHERE r.worker_id = w.id AND r.status IN ({_R})) AS load
        FROM workers w WHERE w.category = ? AND w.active = 1 ORDER BY w.id
        """,
        (*COMPLAINT_ACTIVE, *REPORT_ACTIVE, category),
    ).fetchall()
    return [(r["id"], r["name"], r["load"]) for r in rows]


def pick_worker(conn, category):
    """The least busy worker who still has room, or None when the whole team is full."""
    free = [(load, wid) for wid, _, load in worker_loads(conn, category) if load < WORKER_CAPACITY]
    return min(free)[1] if free else None


def _notify(conn, user_id, complaint_id, title, message):
    conn.execute("INSERT INTO notifications (user_id, complaint_id, title, message) VALUES (?, ?, ?, ?)",
                 (user_id, complaint_id, title, message))


def assign_complaint(conn, cid):
    """Give a complaint to a worker, or mark it Pending when nobody is free. Returns worker id or None."""
    row = conn.execute("SELECT category, status FROM complaints WHERE id = ?", (cid,)).fetchone()
    if not row:
        return None
    w = pick_worker(conn, row["category"])
    if w is None:
        if row["status"] in ("Submitted", "Pending"):
            conn.execute("UPDATE complaints SET worker_id = NULL, status = 'Pending' WHERE id = ?", (cid,))
        return None
    new = "Assigned" if row["status"] in ("Submitted", "Pending") else row["status"]
    conn.execute("UPDATE complaints SET worker_id = ?, status = ? WHERE id = ?", (w, new, cid))
    return w


def assign_report(conn, rid):
    row = conn.execute("SELECT category, status FROM reports WHERE id = ?", (rid,)).fetchone()
    if not row:
        return None
    w = pick_worker(conn, row["category"])
    if w is None:
        if row["status"] in ("open", "pending"):
            conn.execute("UPDATE reports SET worker_id = NULL, status = 'pending' WHERE id = ?", (rid,))
        return None
    new = "open" if row["status"] == "pending" else row["status"]
    conn.execute("UPDATE reports SET worker_id = ?, status = ? WHERE id = ?", (w, new, rid))
    return w


def fill_queue(conn, category):
    """Give waiting (Pending) work, oldest first, to workers who now have room."""
    while True:
        w = pick_worker(conn, category)
        if w is None:
            return
        nxt = conn.execute(
            """
            SELECT kind, id FROM (
                SELECT 'c' AS kind, id, created_at FROM complaints WHERE category = ? AND status = 'Pending'
                UNION ALL
                SELECT 'r', id, created_at FROM reports WHERE category = ? AND status = 'pending'
            ) ORDER BY created_at, id LIMIT 1
            """, (category, category)).fetchone()
        if not nxt:
            return
        if nxt["kind"] == "c":
            owner = conn.execute("SELECT user_id FROM complaints WHERE id = ?", (nxt["id"],)).fetchone()
            conn.execute("UPDATE complaints SET worker_id = ?, status = 'Assigned' WHERE id = ?", (w, nxt["id"]))
            _notify(conn, owner["user_id"], nxt["id"], "Complaint assigned",
                    f"Your complaint #{nxt['id']} has been assigned to our team.")
        else:
            owner = conn.execute("SELECT user_id, title FROM reports WHERE id = ?", (nxt["id"],)).fetchone()
            conn.execute("UPDATE reports SET worker_id = ?, status = 'open', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (w, nxt["id"]))
            _notify(conn, owner["user_id"], None, "Report assigned",
                    f"Your report \"{owner['title']}\" has been assigned to our team.")


def backfill(conn):
    """Run at start-up: fixed departments for old rows and workers for work that has none yet."""
    for cat, dept in CATEGORY_DEPARTMENT.items():
        conn.execute("UPDATE complaints SET department = ? WHERE category = ?", (dept, cat))
        conn.execute("UPDATE reports SET department = ? WHERE category = ?", (dept, cat))
    for r in conn.execute("SELECT id FROM complaints WHERE worker_id IS NULL AND status IN "
                          "('Submitted','Pending','Assigned','In Progress') ORDER BY created_at, id").fetchall():
        assign_complaint(conn, r["id"])
    for r in conn.execute("SELECT id FROM reports WHERE worker_id IS NULL AND status IN "
                          "('open','pending','in_progress','fix_to_verify') ORDER BY created_at, id").fetchall():
        assign_report(conn, r["id"])
    for cat in CATEGORIES:
        fill_queue(conn, cat)


def category_summary(conn, cat):
    loads = worker_loads(conn, cat)
    one = lambda sql: conn.execute(sql, (cat,)).fetchone()[0]
    pending = one("SELECT COUNT(*) FROM complaints WHERE category = ? AND status = 'Pending'") + \
              one("SELECT COUNT(*) FROM reports WHERE category = ? AND status = 'pending'")
    resolved = one("SELECT COUNT(*) FROM complaints WHERE category = ? AND status = 'Resolved'") + \
               one("SELECT COUNT(*) FROM reports WHERE category = ? AND status = 'closed'")
    total = one("SELECT COUNT(*) FROM complaints WHERE category = ?") + one("SELECT COUNT(*) FROM reports WHERE category = ?")
    return {"category": cat, "department": department_for(cat), "workers": len(loads),
            "capacity": len(loads) * WORKER_CAPACITY, "active": sum(l for _, _, l in loads),
            "pending": pending, "resolved": resolved, "total": total}


def category_detail(conn, cat):
    out = category_summary(conn, cat)
    workers = []
    for wid, name, load in worker_loads(conn, cat):
        items = conn.execute(
            f"""SELECT 'Complaint' AS kind, id, text AS title, status FROM complaints WHERE worker_id = ? AND status IN ({_C})
                UNION ALL
                SELECT 'Report', id, title, status FROM reports WHERE worker_id = ? AND status IN ({_R}) ORDER BY id""",
            (wid, *COMPLAINT_ACTIVE, wid, *REPORT_ACTIVE)).fetchall()
        workers.append({"id": wid, "name": name, "load": load, "capacity": WORKER_CAPACITY, "items": [dict(i) for i in items]})
    pending = conn.execute(
        """SELECT * FROM (
             SELECT 'Complaint' AS kind, c.id, c.text AS title, c.status, c.created_at, u.name AS citizen
               FROM complaints c JOIN users u ON u.id = c.user_id WHERE c.category = ? AND c.status = 'Pending'
             UNION ALL
             SELECT 'Report', r.id, r.title, r.status, r.created_at, u.name
               FROM reports r JOIN users u ON u.id = r.user_id WHERE r.category = ? AND r.status = 'pending'
           ) ORDER BY created_at, id""", (cat, cat)).fetchall()
    complaints = conn.execute(
        """SELECT c.id, u.name AS user_name, u.email AS user_email, c.text, c.ward, c.confidence, c.status, c.created_at,
                  (SELECT name FROM workers w WHERE w.id = c.worker_id) AS worker_name
           FROM complaints c JOIN users u ON u.id = c.user_id WHERE c.category = ? ORDER BY c.id DESC""", (cat,)).fetchall()
    reports = conn.execute(
        """SELECT r.id, u.name AS reporter, u.email AS reporter_email, r.title, r.text, r.area, r.city, r.lat, r.lng,
                  r.status, r.created_at, (SELECT name FROM workers w WHERE w.id = r.worker_id) AS worker_name
           FROM reports r JOIN users u ON u.id = r.user_id WHERE r.category = ? ORDER BY r.id DESC""", (cat,)).fetchall()
    out.update(workers=workers, pending=[dict(p) for p in pending],
               complaints=[dict(c) for c in complaints], reports=[dict(r) for r in reports])
    return out


def all_workers(conn):
    """Every technician with open jobs and finished jobs (for the technician list)."""
    rows = conn.execute(
        f"""
        SELECT w.id, w.name, w.category, w.active,
               (SELECT COUNT(*) FROM complaints c WHERE c.worker_id = w.id AND c.status IN ({_C}))
             + (SELECT COUNT(*) FROM reports r WHERE r.worker_id = w.id AND r.status IN ({_R})) AS load,
               (SELECT COUNT(*) FROM complaints c WHERE c.worker_id = w.id AND c.status IN ('Resolved','Rejected'))
             + (SELECT COUNT(*) FROM reports r WHERE r.worker_id = w.id AND r.status = 'closed') AS done
        FROM workers w ORDER BY w.category, w.id
        """, (*COMPLAINT_ACTIVE, *REPORT_ACTIVE)).fetchall()
    return [dict(r, capacity=WORKER_CAPACITY, department=department_for(r["category"])) for r in rows]


def worker_detail(conn, wid):
    """The dashboard of ONE technician: current work and finished work."""
    w = conn.execute("SELECT id, name, category, active FROM workers WHERE id = ?", (wid,)).fetchone()
    if not w:
        return None
    cur_c = conn.execute(
        f"""SELECT c.id, u.name AS user_name, u.email AS user_email, c.text, c.ward, c.status, c.created_at
            FROM complaints c JOIN users u ON u.id = c.user_id
            WHERE c.worker_id = ? AND c.status IN ({_C}) ORDER BY c.created_at""", (wid, *COMPLAINT_ACTIVE)).fetchall()
    cur_r = conn.execute(
        f"""SELECT r.id, u.name AS reporter, u.email AS reporter_email, r.title, r.text, r.area, r.city, r.lat, r.lng, r.status, r.created_at
            FROM reports r JOIN users u ON u.id = r.user_id
            WHERE r.worker_id = ? AND r.status IN ({_R}) ORDER BY r.created_at""", (wid, *REPORT_ACTIVE)).fetchall()
    done = conn.execute(
        """SELECT * FROM (
             SELECT 'Complaint' AS kind, id, text AS title, status, created_at FROM complaints WHERE worker_id = ? AND status IN ('Resolved','Rejected')
             UNION ALL
             SELECT 'Map report', id, title, status, created_at FROM reports WHERE worker_id = ? AND status = 'closed'
           ) ORDER BY created_at DESC LIMIT 30""", (wid, wid)).fetchall()
    load = len(cur_c) + len(cur_r)
    done_total = conn.execute(
        """SELECT (SELECT COUNT(*) FROM complaints WHERE worker_id = ? AND status IN ('Resolved','Rejected'))
                + (SELECT COUNT(*) FROM reports WHERE worker_id = ? AND status = 'closed')""", (wid, wid)).fetchone()[0]
    return {"id": w["id"], "name": w["name"], "category": w["category"], "department": department_for(w["category"]),
            "active": bool(w["active"]), "load": load, "capacity": WORKER_CAPACITY, "done": done_total,
            "complaints": [dict(r) for r in cur_c], "reports": [dict(r) for r in cur_r], "history": [dict(r) for r in done]}