"""
Map reports: ML category suggestion, vector-search duplicate detection,
neighbour checks, and the Open -> In progress -> Fix to verify -> Closed flow.

Roles: users create reports and add neighbour checks; ONLY admins change status.

Optional environment variables:
  AUTHORITY_EMAIL    address used in the "open in email app" draft
  VERIFY_THRESHOLD   neighbours needed to confirm a fix (default 2)
  AUTO_VERIFY        true = neighbour votes may auto-close/reopen reports (default false)
  ALLOW_SELF_VERIFY  true = the reporter's own vote counts (default false)
"""

import logging
import math
import os
import threading
from typing import Optional

import faiss
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import assign, auth, db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
ctx = {}

STATUSES = ("open", "in_progress", "fix_to_verify", "closed")
KINDS = ("still_there", "looks_fixed")

SAME_ISSUE_SIM = 0.75
DUP_RADIUS_M = 250

VERIFY_THRESHOLD = int(os.environ.get("VERIFY_THRESHOLD", "2"))
AUTHORITY_EMAIL = os.environ.get("AUTHORITY_EMAIL", "")


def _flag(name: str) -> bool:
    return os.environ.get(name, "false").lower() in ("true", "1", "yes")


ALLOW_SELF_VERIFY = _flag("ALLOW_SELF_VERIFY")
AUTO_VERIFY = _flag("AUTO_VERIFY")


# ---------------- Live vector index ----------------

class LiveIndex:
    """FAISS index of report embeddings. The vector ids are the report ids."""

    def __init__(self, dim: int):
        self.index = faiss.IndexIDMap(faiss.IndexFlatIP(dim))
        self.lock = threading.Lock()

    def add(self, report_id: int, vec) -> None:
        v = np.ascontiguousarray(vec, dtype="float32").reshape(1, -1)
        with self.lock:
            self.index.add_with_ids(v, np.array([report_id], dtype="int64"))

    def search(self, vec, k: int):
        v = np.ascontiguousarray(vec, dtype="float32").reshape(1, -1)
        with self.lock:
            if self.index.ntotal == 0:
                return []
            scores, ids = self.index.search(v, min(k, self.index.ntotal))
        return [(int(i), float(s)) for s, i in zip(scores[0], ids[0]) if i != -1]


def load_live_index():
    """Rebuild the live index from embeddings stored in the database."""
    eng = ctx.get("engine")
    if not eng:
        return

    live = LiveIndex(eng.index.d)
    with db.connect() as conn:
        rows = conn.execute("SELECT id, embedding FROM reports WHERE embedding IS NOT NULL")
        for row in rows:
            vec = np.frombuffer(row["embedding"], dtype="float32").copy()
            if vec.shape[0] == eng.index.d:
                live.add(row["id"], vec)
            else:
                logger.warning(
                    "Skipping report %d in live index: embedding dim %d does not match model dim %d",
                    row["id"], vec.shape[0], eng.index.d,
                )
    ctx["live"] = live


def engine():
    if not ctx.get("engine") or not ctx.get("live"):
        raise HTTPException(503, "ML Engine Unavailable: Model not loaded yet")
    return ctx["engine"]


# ---------------- Helpers ----------------

def haversine_m(lat1, lng1, lat2, lng2) -> float:
    """Distance between two coordinates in metres."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


def is_staff(user: dict) -> bool:
    return user.get("role") in ("admin", "technician", "technision")


# Internal fields hidden from normal users (category and department are citizen-facing)
HIDDEN_FOR_USERS = ("draft", "worker_id")


def public_view(d: dict, user: dict) -> dict:
    if is_staff(user):
        return d
    return {k: v for k, v in d.items() if k not in HIDDEN_FOR_USERS}


def public_cases(cases: list, _user: dict) -> list:
    del _user
    return cases


def full_text(title: str, text: str) -> str:
    title, text = title.strip(), text.strip()
    return f"{title}. {text}" if title else text


def find_nearby_similar(vec, lat, lng, k=5):
    """Open reports describing the same issue near this location (vector search)."""
    if lat is None or lng is None:
        return []

    hits = [(i, s) for i, s in ctx["live"].search(vec, 25) if s >= SAME_ISSUE_SIM]
    if not hits:
        return []

    marks = ",".join("?" * len(hits))
    with db.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, title, category, area, city, lat, lng, status, created_at
            FROM reports
            WHERE status != 'closed' AND id IN ({marks})
            """,
            [i for i, _ in hits],
        ).fetchall()

    by_id = {r["id"]: r for r in rows}
    found = []
    for rid, score in hits:
        r = by_id.get(rid)
        if not r:
            continue
        dist = haversine_m(lat, lng, r["lat"], r["lng"])
        if dist <= DUP_RADIUS_M:
            found.append({
                "id": rid, "title": r["title"], "category": r["category"],
                "area": r["area"], "status": r["status"], "lat": r["lat"],
                "lng": r["lng"], "similarity": round(score, 3), "distance_m": int(dist),
            })

    found.sort(key=lambda x: -x["similarity"])
    return found[:k]


def make_draft(user, category, department, title, text, city, area, lat, lng, typical_days):
    """Report summary and authority email draft."""
    place = ", ".join(x for x in (area, city) if x)
    if not place and lat is not None:
        place = f"{lat:.5f}, {lng:.5f}"

    headline = title.strip() or text.strip()[:80]

    lines = [
        f"Dear {department},",
        "",
        f"I would like to report a {category.lower()} issue near {place or 'my area'}.",
        "",
        text.strip(),
        "",
    ]
    if lat is not None and lng is not None:
        lines += [
            f"Location: https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=18/{lat}/{lng}",
            "",
        ]

    ask = "Kindly look into this and share an update."
    if typical_days:
        ask = f"Similar issues have usually been resolved in about {typical_days} day(s). " + ask

    lines += [ask, "", "Thank you,", user["name"]]

    return {
        "summary": f"{category} near {place or 'the pinned location'}: {headline}",
        "subject": f"[{category}] {headline[:70]}" + (f" - {place}" if place else ""),
        "body": "\n".join(lines),
        "to": AUTHORITY_EMAIL,
    }


def insert_report(conn, eng, user_id, title, text, category, city, area, lat, lng):
    """Classify, embed and store a report. Caller adds the vector to the live index after commit."""
    combined = full_text(title, text)
    guess, top = eng.classify(combined)

    category = category or guess
    confidence = top[0][1] if category == guess else None
    department = assign.department_for(category)
    vec = eng.embed([combined])[0].astype("float32")

    cur = conn.execute(
        """
        INSERT INTO reports (user_id, title, text, category, confidence, department,
                             city, area, lat, lng, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id, title.strip(), text.strip(), category, confidence, department,
            city.strip() or None, area.strip() or None, lat, lng, vec.tobytes(),
        ),
    )
    return cur.lastrowid, vec


def apply_verification(conn, report_id, report_owner_id, status, status_changed_at):
    """
    Only used when AUTO_VERIFY is on. Enough 'looks_fixed' checks close the report;
    a 'still_there' majority reopens it.
    """
    if status != "fix_to_verify":
        return status

    sql = """
        SELECT kind, COUNT(*) AS n FROM checks
        WHERE report_id = ? AND created_at >= ? {extra}
        GROUP BY kind
    """
    if ALLOW_SELF_VERIFY:
        rows = conn.execute(sql.format(extra=""), (report_id, status_changed_at)).fetchall()
    else:
        rows = conn.execute(
            sql.format(extra="AND user_id != ?"), (report_id, status_changed_at, report_owner_id)
        ).fetchall()

    n = {r["kind"]: r["n"] for r in rows}
    fixed, still = n.get("looks_fixed", 0), n.get("still_there", 0)

    new = status
    if fixed >= VERIFY_THRESHOLD and fixed > still:
        new = "closed"
    elif still > fixed:
        new = "open"

    if new != status:
        conn.execute(
            "UPDATE reports SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new, report_id),
        )
    return new


# ---------------- Request schemas ----------------

class PreviewIn(BaseModel):
    title: str = Field("", max_length=120)
    text: str = Field(..., min_length=10, max_length=2000)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    city: str = Field("", max_length=80)
    area: str = Field("", max_length=120)


class ReportIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    text: str = Field(..., min_length=10, max_length=2000)
    category: str = Field("", max_length=80)
    city: str = Field("", max_length=80)
    area: str = Field("", max_length=120)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class CheckIn(BaseModel):
    kind: str = Field(..., max_length=20)
    note: str = Field("", max_length=300)


class StatusIn(BaseModel):
    status: str = Field(..., max_length=20)


# ---------------- Routes ----------------

@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    """Logged-in user's details and role."""
    with db.connect() as conn:
        worker_id = assign.worker_id_for_user(conn, user)
    return {
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]},
        "is_admin": is_admin(user),
        "is_technician": user.get("role") in ("technician", "technision"),
        "worker_id": worker_id,
    }


@router.get("/reports")
def list_reports(user: dict = Depends(auth.current_user)):
    """Reports for the map and feed (login required), with headline statistics."""
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.title, r.category, r.department, r.city, r.area, r.lat, r.lng,
                   r.status, r.created_at, r.updated_at, r.worker_id,
                   (SELECT name FROM workers w WHERE w.id = r.worker_id) AS worker_name,
                   (SELECT COUNT(*) FROM checks c WHERE c.report_id = r.id) AS checks,
                   (SELECT COUNT(*) FROM checks c
                     WHERE c.report_id = r.id AND c.kind = 'looks_fixed') AS fixed_votes
            FROM reports r
            ORDER BY r.id DESC
            LIMIT 500
            """
        ).fetchall()

        stats = {
            "needs_attention": conn.execute(
                "SELECT COUNT(*) FROM reports WHERE status != 'closed'"
            ).fetchone()[0],
            "checks": conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0],
            "closed_this_week": conn.execute(
                "SELECT COUNT(*) FROM reports WHERE status = 'closed' "
                "AND updated_at > datetime('now', '-7 days')"
            ).fetchone()[0],
        }

    return {"reports": [public_view(dict(r), user) for r in rows], "stats": stats}


@router.get("/reports/mine")
def my_reports(user: dict = Depends(auth.require_user)):
    """A user sees the status of their own reports. (Declared before /reports/{report_id}.)"""
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, text, city, area, lat, lng,
                   status, created_at, updated_at
            FROM reports WHERE user_id = ? ORDER BY id DESC
            """,
            (user["id"],),
        ).fetchall()
    return {"reports": [dict(r) for r in rows]}


@router.get("/admin/reports", dependencies=[Depends(auth.require_admin)])
def admin_reports():
    """Admin sees every report with reporter details and neighbour votes."""
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.title, r.text, r.category, r.confidence, r.department,
                   r.city, r.area, r.lat, r.lng, r.status, r.created_at, r.updated_at,
                   u.name AS reporter, u.email AS reporter_email,
                   (SELECT name FROM workers w WHERE w.id = r.worker_id) AS worker_name,
                   (SELECT COUNT(*) FROM checks c WHERE c.report_id = r.id) AS checks,
                   (SELECT COUNT(*) FROM checks c
                     WHERE c.report_id = r.id AND c.kind = 'looks_fixed') AS fixed_votes,
                   (SELECT COUNT(*) FROM checks c
                     WHERE c.report_id = r.id AND c.kind = 'still_there') AS still_votes
            FROM reports r
            JOIN users u ON u.id = r.user_id
            ORDER BY r.id DESC
            """
        ).fetchall()
    return {"reports": [dict(r) for r in rows], "statuses": list(STATUSES)}


@router.post("/reports/preview")
def preview(body: PreviewIn, user: dict = Depends(auth.current_user)):
    """Classify text, find nearby duplicates and prepare an email draft."""
    eng = engine()
    combined = full_text(body.title, body.text)

    category, top = eng.classify(combined)
    department = eng.department_for(category)
    typical = eng.typical_days(category)
    vec = eng.embed([combined])[0]
    nearby_duplicates = find_nearby_similar(vec, body.lat, body.lng)

    result = {
        "category": category,
        "confidence": round(top[0][1], 3),
        "top_categories": [{"category": c, "probability": round(p, 3)} for c, p in top],
        "department": department,
        "typical_days": typical,
        "possible_duplicates": nearby_duplicates,
        "nearby_duplicates": nearby_duplicates,
        "past_cases": eng.similar(combined, k=3, category=category, resolved_only=True),
        "draft": make_draft(
            user, category, department, body.title, body.text,
            body.city, body.area, body.lat, body.lng, typical,
        ),
    }
    result["past_cases"] = public_cases(result["past_cases"], user)
    return result


@router.post("/reports")
def create_report(body: ReportIn, user: dict = Depends(auth.require_user)):
    """Users create a report; its embedding is added to the live index."""
    eng = engine()
    category = body.category.strip()

    if category and category not in {str(c) for c in eng.clf.classes_}:
        raise HTTPException(422, "Unknown category.")

    with db.connect() as conn:
        report_id, vec = insert_report(
            conn, eng, user["id"], body.title, body.text, category,
            body.city, body.area, body.lat, body.lng,
        )
        assign.assign_report(conn, report_id)   # automatic assignment (or Pending when the team is full)
        row = conn.execute(
            """
            SELECT id, title, category, department, confidence, city, area,
                   lat, lng, status, created_at
            FROM reports WHERE id = ?
            """,
            (report_id,),
        ).fetchone()

    ctx["live"].add(report_id, vec)
    return {"report": public_view(dict(row), user)}


@router.get("/reports/{report_id}")
def report_detail(report_id: int, user: dict = Depends(auth.current_user)):
    """Report details, neighbour checks and similar past cases."""
    eng = engine()

    with db.connect() as conn:
        r = conn.execute(
            """
            SELECT r.id, r.title, r.text, r.category, r.confidence, r.department,
                   r.city, r.area, r.lat, r.lng, r.status, r.created_at, r.updated_at,
                   (SELECT name FROM workers w WHERE w.id = r.worker_id) AS worker_name,
                   r.embedding AS emb,
                   u.name AS reporter
            FROM reports r
            JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
            """,
            (report_id,),
        ).fetchone()

        if not r:
            raise HTTPException(404, "Report not found.")

        checks = conn.execute(
            """
            SELECT c.kind, c.note, c.created_at, u.name
            FROM checks c
            JOIN users u ON u.id = c.user_id
            WHERE c.report_id = ?
            ORDER BY c.id DESC
            LIMIT 20
            """,
            (report_id,),
        ).fetchall()

    report = dict(r)
    emb = report.pop("emb", None)   # stored embedding: reused below, never sent to the browser
    report["reporter"] = (report["reporter"].split() or ["Neighbour"])[0]

    return {
        "report": public_view(report, user),
        "checks": [
            {
                "kind": c["kind"],
                "note": c["note"],
                "by": (c["name"].split() or ["Neighbour"])[0],
                "created_at": c["created_at"],
            }
            for c in checks
        ],
        "past_cases": public_cases(eng.similar(
            full_text(r["title"], r["text"]), k=3, category=r["category"], resolved_only=True,
            vec=(np.frombuffer(emb, dtype="float32") if emb and len(emb) == 4 * eng.index.d else None),
        ), user),
        "typical_days": eng.typical_days(r["category"]),
    }


@router.post("/reports/{report_id}/checks")
def add_check(report_id: int, body: CheckIn, user: dict = Depends(auth.require_user)):
    """Users confirm whether an issue is fixed. This never changes status unless AUTO_VERIFY is on."""
    if body.kind not in KINDS:
        raise HTTPException(422, "kind must be 'still_there' or 'looks_fixed'.")

    with db.connect() as conn:
        rep = conn.execute(
            "SELECT id, user_id, status, updated_at, category FROM reports WHERE id = ?", (report_id,)
        ).fetchone()

        if not rep:
            raise HTTPException(404, "Report not found.")
        if rep["status"] == "closed":
            raise HTTPException(409, "This report is already closed.")

        conn.execute(
            """
            INSERT INTO checks (report_id, user_id, kind, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (report_id, user_id)
            DO UPDATE SET kind = excluded.kind, note = excluded.note,
                          created_at = CURRENT_TIMESTAMP
            """,
            (report_id, user["id"], body.kind, body.note.strip() or None),
        )

        status = rep["status"]
        if AUTO_VERIFY:
            status = apply_verification(
                conn, report_id, rep["user_id"], rep["status"], rep["updated_at"]
            )
            if status == "closed":
                assign.fill_queue(conn, rep["category"])

    return {"ok": True, "status": status}


@router.post("/reports/{report_id}/status")
def set_status(report_id: int, body: StatusIn, user: dict = Depends(auth.require_technician_or_admin)):
    """Admins and Technicians can change a report's status; the reporter is notified."""
    if body.status not in STATUSES:
        raise HTTPException(422, "Unknown status.")

    with db.connect() as conn:
        rep = conn.execute(
            "SELECT id, user_id, title, category, worker_id FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if not rep:
            raise HTTPException(404, "Report not found.")
        if auth.is_technician(user):
            worker_id = assign.worker_id_for_user(conn, user)
            if worker_id is None or rep["worker_id"] != worker_id:
                raise HTTPException(403, "You can only update reports assigned to you.")

        if body.status != "closed" and rep["worker_id"] is None:   # a pending report needs a free worker first
            w = assign.pick_worker(conn, rep["category"])
            if w is None:
                raise HTTPException(409, "All workers in this category are busy. The report stays Pending until a worker is free.")
            conn.execute("UPDATE reports SET worker_id = ? WHERE id = ?", (w, report_id))
        conn.execute(
            "UPDATE reports SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (body.status, report_id),
        )
        assign.fill_queue(conn, rep["category"])   # a closed report frees a worker for pending work
        conn.execute(
            "INSERT INTO notifications (user_id, complaint_id, title, message) "
            "VALUES (?, NULL, ?, ?)",
            (
                rep["user_id"],
                "Report status updated",
                f"Your report \"{rep['title']}\" is now: {body.status.replace('_', ' ')}.",
            ),
        )

    return {"ok": True, "status": body.status}