"""
FastAPI backend for Smart Complaint Assistant.

Run from the project root:
    ./backend/.venv/Scripts/python.exe -m uvicorn app.main:app --reload --app-dir backend

Optional environment variables: ADMIN_EMAIL, ADMIN_PASSWORD (first-run admin account).
"""

import os
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import assign, auth, db, reports
from app.config import ALLOW_ALL_ORIGINS, CORS_ORIGINS, DUPLICATE_THRESHOLD, FRONTEND_DIR
from app.engine import ComplaintEngine

state = {}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COMPLAINT_COLS = "id, user_id, text, ward, category, confidence, department, status, created_at"
USER_COLS = "id, user_id, text, ward, status, created_at"   # categories are admin-only
# Statuses an admin may set. "Pending" and "Assigned" are set by the system (automatic assignment).
COMPLAINT_STATUSES = ("In Progress", "Resolved", "Rejected")


def seed_admin():
    """Create the first admin account if none exists (registration only makes users)."""
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
    with db.connect() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE role = 'admin'").fetchone():
            conn.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                ("Administrator", email, auth.hash_password(password)),
            )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    del _app
    db.init_db()
    seed_admin()
    state["startup_error"] = None
    try:
        with db.connect() as conn:
            assign.seed_workers(conn)   # 4 workers per category
            assign.backfill(conn)       # fixed departments + workers for existing work
    except Exception as ex:         # the site must still start; the reason is printed here and shown in /api/health
        import traceback
        traceback.print_exc()
        state["startup_error"] = f"Worker setup failed: {ex}"
    try:
        state["engine"] = ComplaintEngine()
        reports.ctx["engine"] = state["engine"]
        reports.load_live_index()
        state["engine_status"] = "ready"
        state["engine_error"] = None
    except Exception as ex:
        state["engine"] = None
        state["engine_status"] = "uninitialized"
        state["engine_error"] = str(ex)
        reports.ctx["engine"] = None
    yield
    state.clear()


app = FastAPI(title="Smart Complaint Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOW_ALL_ORIGINS else CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(reports.router)


class TimingMiddleware:
    """Adds an X-Process-Time-ms header and prints any request slower than 400 ms in the backend window."""

    def __init__(self, asgi_app):
        self.app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.perf_counter()
        path = scope.get("path", "")

        async def send_with_timing(message):
            if message["type"] == "http.response.start":
                ms = (time.perf_counter() - started) * 1000
                message["headers"] = list(message.get("headers", [])) + [(b"x-process-time-ms", f"{ms:.0f}".encode())]
                if ms > 400 and not path.endswith((".js", ".css", ".html", ".png", ".svg", ".ico")):
                    print(f"SLOW  {scope.get('method')} {path}  {ms:.0f} ms", flush=True)
            await send(message)

        await self.app(scope, receive, send_with_timing)


app.add_middleware(TimingMiddleware)


class ComplaintIn(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)
    k: int = Field(5, ge=1, le=10)


class RegisterIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=6, max_length=200)
    role: Literal["user", "technician"] = "user"
    category: Optional[str] = None


class LoginIn(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=200)


class SubmitIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=2000)
    ward: str = Field("", max_length=100)


class AdminStatusIn(BaseModel):
    status: str = Field(..., min_length=2, max_length=50)


class AdminDepartmentIn(BaseModel):
    department: str = Field(..., min_length=2, max_length=100)


def engine() -> ComplaintEngine:
    if not state.get("engine"):
        detail = state.get("engine_error") or "Model not loaded yet"
        raise HTTPException(503, f"ML Engine Unavailable: {detail}")
    return state["engine"]


def top_list(top):
    return [{"category": c, "probability": round(p, 3)} for c, p in top]


# ---------------- Health and ML ----------------

@app.get("/api/health")
def health():
    response = {"status": "ok", "engine": state.get("engine_status", "unknown")}
    if state.get("engine_error"):
        response["engine_error"] = state["engine_error"]
    if state.get("startup_error"):
        response["startup_error"] = state["startup_error"]
    try:
        started = time.perf_counter()
        with db.connect() as conn:
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "workers", "complaints", "reports")}
        response["database"] = {"ok": True, "ms": round((time.perf_counter() - started) * 1000), **counts}
    except Exception as ex:
        response["database"] = {"ok": False, "error": str(ex)}
        response["status"] = "degraded"
    return response


@app.post("/api/classify", dependencies=[Depends(auth.require_admin)])
def classify(body: ComplaintIn):
    category, top = engine().classify(body.text)
    return {"category": category, "confidence": round(top[0][1], 3), "top_categories": top_list(top)}


@app.post("/api/similar", dependencies=[Depends(auth.require_admin)])
def similar(body: ComplaintIn):
    return {"matches": engine().similar(body.text, k=body.k)}


@app.post("/api/analyze", dependencies=[Depends(auth.require_admin)])
def analyze(body: ComplaintIn):
    category, top, matches = engine().recommend(body.text, k=body.k)
    for m in matches:
        m["possible_duplicate"] = m["similarity"] >= DUPLICATE_THRESHOLD
    return {
        "category": category,
        "confidence": round(top[0][1], 3),
        "top_categories": top_list(top),
        "matches": matches,
    }


# ---------------- Registration and login ----------------

@app.post("/api/auth/register")
def register(body: RegisterIn):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Please enter a valid email address.")
    name = body.name.strip()
    category = (body.category or "").strip()
    if body.role == "technician" and category not in assign.CATEGORIES:
        raise HTTPException(422, "Choose a valid technician category.")

    with db.connect() as conn:
        worker = None
        if body.role == "technician":
            worker = conn.execute(
                "SELECT id, user_id, category FROM workers WHERE lower(email) = ?",
                (email,),
            ).fetchone()
            if worker:
                if worker["user_id"] is not None:
                    raise HTTPException(409, "This technician profile is already linked to an account.")
                if worker["category"] != category:
                    raise HTTPException(422, f"This worker profile belongs to {worker['category']}.")
            else:
                worker_count = conn.execute(
                    "SELECT COUNT(*) FROM workers WHERE category = ?", (category,)
                ).fetchone()[0]
                if worker_count >= assign.MAX_WORKERS_PER_CATEGORY:
                    raise HTTPException(
                        409,
                        f"{category} already has {assign.MAX_WORKERS_PER_CATEGORY} workers. "
                        "Ask an administrator to link you to an existing profile.",
                    )
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, auth.hash_password(body.password), body.role),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with this email already exists. Try logging in.")

        user = {"id": cur.lastrowid, "name": name, "email": email, "role": body.role}
        if body.role == "technician":
            if worker:
                conn.execute(
                    "UPDATE workers SET name = ?, user_id = ? WHERE id = ?",
                    (name, user["id"], worker["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO workers (name, category, user_id, email) VALUES (?, ?, ?, ?)",
                    (name, category, user["id"], email),
                )
        token = auth.create_session(conn, user["id"])

    return {"token": token, "user": user}


@app.post("/api/auth/login")
def login(body: LoginIn):
    email = body.email.strip().lower()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, name, email, password_hash, role FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not row or not auth.verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Incorrect email or password.")
        token = auth.create_session(conn, row["id"])

    return {
        "token": token,
        "user": {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]},
    }


@app.post("/api/auth/logout")
def logout(user: dict = Depends(auth.current_user)):
    with db.connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (user["token"],))
    return {"ok": True}


# NOTE: GET /api/me is defined in reports.py (returns {user, is_admin}).


# ---------------- Normal user complaint routes ----------------

@app.post("/api/complaints")
def submit_complaint(body: SubmitIn, user: dict = Depends(auth.require_user)):
    """Classify a complaint, find similar complaints, save and notify."""
    eng = engine()
    complaint_text = body.text.strip()

    category, top, matches = eng.recommend(complaint_text, k=5)
    confidence = round(float(top[0][1]), 3)
    department = assign.department_for(category)
    typical_days = eng.typical_days(category)

    for m in matches:
        m["possible_duplicate"] = m["similarity"] >= DUPLICATE_THRESHOLD
    possible_duplicate = bool(matches) and matches[0]["possible_duplicate"]

    with db.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO complaints (user_id, text, ward, category, confidence, department)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user["id"], complaint_text, body.ward.strip() or None, category, confidence, department),
        )
        complaint_id = cur.lastrowid
        worker_id = assign.assign_complaint(conn, complaint_id)   # automatic assignment

        if worker_id:
            parts = [f"Complaint #{complaint_id} was received and assigned to our team."]
        else:
            parts = [f"Complaint #{complaint_id} was received. All our teams are busy, so it is Pending and will be assigned as soon as a worker is free."]
        if typical_days:
            parts.append(f"Similar complaints were usually resolved in about {typical_days} day(s).")
        if possible_duplicate:
            parts.append("It looks very similar to a past complaint, so it may be a duplicate.")

        title = "Complaint received"
        message = " ".join(parts)

        conn.execute(
            "INSERT INTO notifications (user_id, complaint_id, title, message) VALUES (?, ?, ?, ?)",
            (user["id"], complaint_id, title, message),
        )
        saved = conn.execute(
            f"SELECT {USER_COLS} FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()

    return {
        "complaint": dict(saved),
        "id": complaint_id,
        "category": category,
        "confidence": confidence,
        "department": department,
        "notification": {"title": title, "message": message},
        "similar": [{k: v for k, v in m.items() if k not in ("category", "department")} for m in matches],
        "possible_duplicate": possible_duplicate,
    }


@app.get("/api/complaints")
def my_complaints(user: dict = Depends(auth.require_user)):
    """Normal users can only see their own complaints."""
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT {USER_COLS} FROM complaints WHERE user_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()
    return {"complaints": [dict(r) for r in rows]}


# ---------------- Admin routes ----------------

@app.get("/api/admin/complaints", dependencies=[Depends(auth.require_admin)])
def admin_all_complaints():
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.user_id, u.name AS user_name, u.email AS user_email,
                   c.text, c.ward, c.category, c.confidence, c.department,
                   c.status, c.created_at, c.worker_id,
                   (SELECT name FROM workers w WHERE w.id = c.worker_id) AS worker_name
            FROM complaints c
            JOIN users u ON u.id = c.user_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    return {"complaints": [dict(r) for r in rows]}


@app.post(
    "/api/admin/complaints/{complaint_id}/status",
    dependencies=[Depends(auth.require_admin)],
)
def admin_update_status(complaint_id: int, body: AdminStatusIn):
    """Only an admin can change a complaint's status."""
    return _update_complaint_status(complaint_id, body)


@app.post("/api/technician/complaints/{complaint_id}/status")
def technician_update_status(
    complaint_id: int,
    body: AdminStatusIn,
    user: dict = Depends(auth.require_technician),
):
    """A technician can update only complaints assigned to their worker profile."""
    return _update_complaint_status(complaint_id, body, user)


def _update_complaint_status(
    complaint_id: int, body: AdminStatusIn, user: Optional[dict] = None
):
    new_status = body.status.strip()
    if new_status not in COMPLAINT_STATUSES:
        raise HTTPException(422, f"Status must be one of: {', '.join(COMPLAINT_STATUSES)}")

    with db.connect() as conn:
        complaint = conn.execute(
            "SELECT id, user_id, category, worker_id FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()
        if not complaint:
            raise HTTPException(404, "Complaint not found.")
        if user is not None:
            worker_id = assign.worker_id_for_user(conn, user)
            if worker_id is None or complaint["worker_id"] != worker_id:
                raise HTTPException(403, "You can only update complaints assigned to you.")

        if new_status == "In Progress" and complaint["worker_id"] is None:
            w = assign.pick_worker(conn, complaint["category"])
            if w is None:
                raise HTTPException(409, "All workers in this category are busy. The complaint stays Pending until a worker is free.")
            conn.execute("UPDATE complaints SET worker_id = ? WHERE id = ?", (w, complaint_id))
        conn.execute("UPDATE complaints SET status = ? WHERE id = ?", (new_status, complaint_id))
        assign.fill_queue(conn, complaint["category"])   # a finished job frees a worker for pending work
        conn.execute(
            "INSERT INTO notifications (user_id, complaint_id, title, message) VALUES (?, ?, ?, ?)",
            (
                complaint["user_id"],
                complaint_id,
                "Complaint status updated",
                f"Your complaint #{complaint_id} status is now: {new_status}.",
            ),
        )

    return {"ok": True, "complaint_id": complaint_id, "status": new_status}


@app.post(
    "/api/admin/complaints/{complaint_id}/department",
    dependencies=[Depends(auth.require_admin)],
)
def admin_update_department(
    complaint_id: int, body: AdminDepartmentIn
):
    department = body.department.strip()
    if department not in assign.DEPARTMENTS:
        raise HTTPException(422, "Unknown department.")
    with db.connect() as conn:
        cur = conn.execute(
            "UPDATE complaints SET department = ? WHERE id = ?", (department, complaint_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Complaint not found.")
    return {"ok": True, "complaint_id": complaint_id, "department": department}


@app.get("/api/admin/users", dependencies=[Depends(auth.require_admin)])
def admin_all_users():
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, name, email, role, created_at FROM users ORDER BY id DESC"
        ).fetchall()
    return {"users": [dict(r) for r in rows]}


@app.get("/api/admin/stats", dependencies=[Depends(auth.require_admin)])
def admin_dashboard_stats():
    with db.connect() as conn:
        total_complaints = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        total_reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0]
        total_admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
        total_pending = conn.execute(
            "SELECT (SELECT COUNT(*) FROM complaints WHERE status = 'Pending') "
            "+ (SELECT COUNT(*) FROM reports WHERE status = 'pending')").fetchone()[0]
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM complaints GROUP BY status ORDER BY status"
        ).fetchall()
        category_rows = conn.execute(
            "SELECT category, COUNT(*) AS count FROM complaints GROUP BY category ORDER BY count DESC"
        ).fetchall()
        report_status_rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM reports GROUP BY status ORDER BY status"
        ).fetchall()

    return {
        "total_complaints": total_complaints,
        "total_reports": total_reports,
        "total_users": total_users,
        "total_admins": total_admins,
        "total_pending": total_pending,
        "complaints_by_status": [dict(r) for r in status_rows],
        "complaints_by_category": [dict(r) for r in category_rows],
        "reports_by_status": [dict(r) for r in report_status_rows],
    }


@app.get("/api/admin/categories", dependencies=[Depends(auth.require_admin)])
def admin_categories():
    """One summary card per category: workers, open work, pending queue."""
    with db.connect() as conn:
        cats = [assign.category_summary(conn, c) for c in assign.CATEGORIES]
    return {"categories": cats, "worker_capacity": assign.WORKER_CAPACITY}


@app.get("/api/admin/workers", dependencies=[Depends(auth.require_admin)])
def admin_workers():
    """All technicians with their current load (for the technician list)."""
    with db.connect() as conn:
        return {"workers": assign.all_workers(conn)}


@app.get("/api/admin/worker", dependencies=[Depends(auth.require_admin)])
def admin_worker(id: int):
    """The separate dashboard of one technician."""
    with db.connect() as conn:
        data = assign.worker_detail(conn, id)
    if not data:
        raise HTTPException(404, "Technician not found.")
    return data


@app.get("/api/technician/worker")
def technician_worker(user: dict = Depends(auth.require_technician)):
    """Return the signed-in technician's own worker dashboard."""
    with db.connect() as conn:
        worker_id = assign.worker_id_for_user(conn, user)
        if worker_id is None:
            raise HTTPException(
                404,
                "Your technician account is not linked to a worker profile. Ask an administrator to link it.",
            )
        data = assign.worker_detail(conn, worker_id)
    if not data:
        raise HTTPException(404, "Technician profile not found.")
    return data


@app.get("/api/admin/category", dependencies=[Depends(auth.require_admin)])
def admin_category(name: str):
    """The separate dashboard of one category: workers and their jobs, pending queue, all work."""
    if name not in assign.CATEGORIES:
        raise HTTPException(404, "Unknown category.")
    with db.connect() as conn:
        return assign.category_detail(conn, name)


# ---------------- Notifications ----------------

@app.get("/api/notifications")
def notifications(user: dict = Depends(auth.current_user)):
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id, complaint_id, title, message, is_read, created_at
            FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 50
            """,
            (user["id"],),
        ).fetchall()
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],)
        ).fetchone()[0]
    return {"notifications": [dict(r) for r in rows], "unread": unread}


@app.post("/api/notifications/read-all")
def read_all(user: dict = Depends(auth.current_user)):
    with db.connect() as conn:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
    return {"ok": True}


@app.post("/api/notifications/{notification_id}/read")
def read_one(notification_id: int, user: dict = Depends(auth.current_user)):
    with db.connect() as conn:
        cur = conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user["id"]),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Notification not found.")
    return {"ok": True}


# ---------------- Frontend ----------------

@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/civic.html")


# Keep this LAST so it does not shadow API routes.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")