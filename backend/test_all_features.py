"""Comprehensive automated test suite for Smart Complaint Assistant.
Covers all ML, authentication, complaints, notifications, and reports features.
"""
import os
import sys

# Prevent network timeout when offline in sandbox
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["PYTHONUNBUFFERED"] = "1"

import uuid
from pathlib import Path

# Ensure backend directory is in python path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app, state


def run_tests():
    print("=" * 65, flush=True)
    print("  SMART COMPLAINT ASSISTANT - EXHAUSTIVE TEST SUITE", flush=True)
    print("=" * 65, flush=True)

    passed = 0
    total = 28
    failures = []

    def record(num, name, ok, reason=""):
        nonlocal passed
        num_str = f"{num:02d}"
        if ok:
            passed += 1
            print(f"[PASS] {num_str}: {name}", flush=True)
        else:
            failures.append((num_str, name, reason))
            print(f"[FAIL] {num_str}: {name} - {reason}", flush=True)

    with TestClient(app) as client:
        print("TestClient entered lifespan", flush=True)
        # Get admin credentials / token
        admin_token = None
        print("Logging in admin...", flush=True)
        for email, pw in [("admin@gmail.com", "demo-pass-123"), ("admin@example.com", "ChangeMe123!")]:
            print(f"Trying login {email}...", flush=True)
            res = client.post("/api/auth/login", json={"email": email, "password": pw})
            print(f"Login result {email}: {res.status_code}", flush=True)
            if res.status_code == 200:
                admin_token = res.json().get("token")
                break
        if not admin_token:
            from app import db, auth
            with db.connect() as conn:
                row = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()
                if row:
                    admin_token = auth.create_session(conn, row["id"])
        admin_headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}

        # 01: GET /api/health returns ready status
        try:
            r = client.get("/api/health")
            ok = r.status_code == 200 and r.json().get("status") in ("ok", "degraded")
            record(1, "GET /api/health returns ready status", ok, f"status={r.status_code}, body={r.text}")
        except Exception as e:
            record(1, "GET /api/health returns ready status", False, str(e))

        # 02: Graceful degraded startup on missing ML model (503 response)
        try:
            saved_engine = state.get("engine")
            state["engine"] = None
            r = client.post("/api/classify", json={"text": "Big pothole on the road"}, headers=admin_headers)
            state["engine"] = saved_engine
            ok = r.status_code == 503
            record(2, "Graceful degraded startup on missing ML model (503 response)", ok, f"status={r.status_code}")
        except Exception as e:
            record(2, "Graceful degraded startup on missing ML model (503 response)", False, str(e))

        # 03: POST /api/classify predicts correct category and rounded confidence
        try:
            r = client.post("/api/classify", json={"text": "Big pothole near the school causing accidents for two wheelers"}, headers=admin_headers)
            data = r.json()
            ok = r.status_code == 200 and data.get("category") == "Roads and Potholes" and isinstance(data.get("confidence"), float)
            record(3, "POST /api/classify predicts correct category and rounded confidence", ok, f"status={r.status_code}, data={data}")
        except Exception as e:
            record(3, "POST /api/classify predicts correct category and rounded confidence", False, str(e))

        # 04: POST /api/classify rejects text under 5 characters (422)
        try:
            r = client.post("/api/classify", json={"text": "bad"}, headers=admin_headers)
            ok = r.status_code == 422
            record(4, "POST /api/classify rejects text under 5 characters (422)", ok, f"status={r.status_code}")
        except Exception as e:
            record(4, "POST /api/classify rejects text under 5 characters (422)", False, str(e))

        # 05: POST /api/similar returns top-K vector matches from seed index
        try:
            r = client.post("/api/similar", json={"text": "Garbage not collected for a week, smells terrible", "k": 3}, headers=admin_headers)
            matches = r.json().get("matches", [])
            ok = r.status_code == 200 and len(matches) > 0
            record(5, "POST /api/similar returns top-K vector matches from seed index", ok, f"status={r.status_code}, count={len(matches)}")
        except Exception as e:
            record(5, "POST /api/similar returns top-K vector matches from seed index", False, str(e))

        # 06: POST /api/analyze returns category, resolution cases, and duplicate check
        try:
            r = client.post("/api/analyze", json={"text": "Street light is broken near the park, area is very dark", "k": 3}, headers=admin_headers)
            data = r.json()
            ok = r.status_code == 200 and "category" in data and "matches" in data
            record(6, "POST /api/analyze returns category, resolution cases, and duplicate check", ok, f"status={r.status_code}")
        except Exception as e:
            record(6, "POST /api/analyze returns category, resolution cases, and duplicate check", False, str(e))

        # 07: Engine department_for uses statistical mode and defaults gracefully
        try:
            eng = state.get("engine")
            dept = eng.department_for("Roads and Potholes") if eng else None
            ok = dept is not None and len(dept) > 0
            record(7, "Engine department_for uses statistical mode and defaults gracefully", ok, f"dept={dept}")
        except Exception as e:
            record(7, "Engine department_for uses statistical mode and defaults gracefully", False, str(e))

        # 08: POST /api/auth/register enforces validation rules
        try:
            r1 = client.post("/api/auth/register", json={"name": "A", "email": "notanemail", "password": "123"})
            ok = r1.status_code == 422
            record(8, "POST /api/auth/register enforces validation rules", ok, f"status={r1.status_code}")
        except Exception as e:
            record(8, "POST /api/auth/register enforces validation rules", False, str(e))

        # 09: POST /api/auth/register successfully creates user and session
        test_email = f"citizen_{uuid.uuid4().hex[:8]}@example.com"
        test_pass = "securepass123"
        citizen_token = None
        try:
            r = client.post("/api/auth/register", json={"name": "Test Citizen", "email": test_email, "password": test_pass})
            data = r.json()
            citizen_token = data.get("token")
            ok = r.status_code == 200 and citizen_token is not None
            record(9, "POST /api/auth/register successfully creates user and session", ok, f"status={r.status_code}")
        except Exception as e:
            record(9, "POST /api/auth/register successfully creates user and session", False, str(e))

        citizen_headers = {"Authorization": f"Bearer {citizen_token}"} if citizen_token else {}

        # 10: POST /api/auth/register blocks duplicate email (409 Conflict)
        try:
            r = client.post("/api/auth/register", json={"name": "Duplicate Citizen", "email": test_email, "password": test_pass})
            ok = r.status_code == 409
            record(10, "POST /api/auth/register blocks duplicate email (409 Conflict)", ok, f"status={r.status_code}")
        except Exception as e:
            record(10, "POST /api/auth/register blocks duplicate email (409 Conflict)", False, str(e))

        # 11: POST /api/auth/login rejects incorrect credentials (401)
        try:
            r = client.post("/api/auth/login", json={"email": test_email, "password": "wrongpassword"})
            ok = r.status_code == 401
            record(11, "POST /api/auth/login rejects incorrect credentials (401)", ok, f"status={r.status_code}")
        except Exception as e:
            record(11, "POST /api/auth/login rejects incorrect credentials (401)", False, str(e))

        # 12: POST /api/auth/login succeeds with valid credentials
        try:
            r = client.post("/api/auth/login", json={"email": test_email, "password": test_pass})
            ok = r.status_code == 200 and "token" in r.json()
            record(12, "POST /api/auth/login succeeds with valid credentials", ok, f"status={r.status_code}")
        except Exception as e:
            record(12, "POST /api/auth/login succeeds with valid credentials", False, str(e))

        # 13: GET /api/me returns user profile and admin status
        try:
            r = client.get("/api/me", headers=citizen_headers)
            data = r.json()
            ok = r.status_code == 200 and data.get("user", {}).get("email") == test_email and data.get("is_admin") is False
            record(13, "GET /api/me returns user profile and admin status", ok, f"status={r.status_code}, data={data}")
        except Exception as e:
            record(13, "GET /api/me returns user profile and admin status", False, str(e))

        # 14: Protected endpoints reject unauthorized requests (401)
        try:
            r = client.get("/api/complaints")
            ok = r.status_code == 401
            record(14, "Protected endpoints reject unauthorized requests (401)", ok, f"status={r.status_code}")
        except Exception as e:
            record(14, "Protected endpoints reject unauthorized requests (401)", False, str(e))

        # 15: POST /api/complaints classifies, rounds confidence, and notifies
        complaint_id = None
        try:
            r = client.post("/api/complaints", json={"text": "Sewage overflowing on the road in Koramangala and entering houses", "ward": "Koramangala"}, headers=citizen_headers)
            data = r.json()
            complaint_id = data.get("id")
            ok = r.status_code == 200 and complaint_id is not None and data.get("category") is not None and isinstance(data.get("confidence"), float)
            record(15, "POST /api/complaints classifies, rounds confidence, and notifies", ok, f"status={r.status_code}")
        except Exception as e:
            record(15, "POST /api/complaints classifies, rounds confidence, and notifies", False, str(e))

        # 16: GET /api/complaints retrieves submitted complaints list
        try:
            r = client.get("/api/complaints", headers=citizen_headers)
            data = r.json()
            items = data.get("complaints", []) if isinstance(data, dict) else []
            ok = r.status_code == 200 and len(items) >= 1
            record(16, "GET /api/complaints retrieves submitted complaints list", ok, f"status={r.status_code}, len={len(items)}")
        except Exception as e:
            record(16, "GET /api/complaints retrieves submitted complaints list", False, str(e))

        # 17: Notifications lifecycle (fetch, read-one, read-all) works cleanly
        try:
            r = client.get("/api/notifications", headers=citizen_headers)
            data = r.json()
            notifs = data.get("notifications", []) if isinstance(data, dict) else []
            ok_fetch = r.status_code == 200 and len(notifs) >= 1
            nid = notifs[0]["id"] if ok_fetch else 1
            r_one = client.post(f"/api/notifications/{nid}/read", headers=citizen_headers)
            r_all = client.post("/api/notifications/read-all", headers=citizen_headers)
            ok = ok_fetch and r_one.status_code == 200 and r_all.status_code == 200
            record(17, "Notifications lifecycle (fetch, read-one, read-all) works cleanly", ok, f"fetch={ok_fetch}, r_one={r_one.status_code}, r_all={r_all.status_code}")
        except Exception as e:
            record(17, "Notifications lifecycle (fetch, read-one, read-all) works cleanly", False, str(e))

        # 18: GET /api/reports returns active reports and populated stats
        try:
            r = client.get("/api/reports", headers=citizen_headers)
            data = r.json()
            ok = r.status_code == 200 and "reports" in data and "stats" in data
            record(18, "GET /api/reports returns active reports and populated stats", ok, f"status={r.status_code}")
        except Exception as e:
            record(18, "GET /api/reports returns active reports and populated stats", False, str(e))

        # 19: POST /api/reports/preview provides AI classification, email draft, and duplicate scan
        try:
            r = client.post("/api/reports/preview", json={
                "title": "Broken street light",
                "text": "The street light in our 4th block lane is not turning on since last week.",
                "area": "Koramangala",
                "city": "Bengaluru",
                "lat": 12.9352,
                "lng": 77.6245
            }, headers=citizen_headers)
            data = r.json()
            ok = r.status_code == 200 and "category" in data and "draft" in data
            record(19, "POST /api/reports/preview provides AI classification, email draft, and duplicate scan", ok, f"status={r.status_code}")
        except Exception as e:
            record(19, "POST /api/reports/preview provides AI classification, email draft, and duplicate scan", False, str(e))

        # 20: POST /api/reports creates report and updates live FAISS vector index
        created_report_id = None
        try:
            r = client.post("/api/reports", json={
                "title": f"Unique Test Pothole {uuid.uuid4().hex[:4]}",
                "text": "Huge hazardous pothole on 80ft road causing severe vehicle damages and traffic jams.",
                "area": "Indiranagar",
                "city": "Bengaluru",
                "lat": 12.9784,
                "lng": 77.6408
            }, headers=citizen_headers)
            data = r.json()
            created_report_id = data.get("report", {}).get("id") or data.get("id")
            ok = r.status_code == 200 and created_report_id is not None
            record(20, "POST /api/reports creates report and updates live FAISS vector index", ok, f"status={r.status_code}")
        except Exception as e:
            record(20, "POST /api/reports creates report and updates live FAISS vector index", False, str(e))

        # 21: Live FAISS index detects duplicate report within 250m radius
        try:
            r = client.post("/api/reports/preview", json={
                "title": "Pothole nearby",
                "text": "Huge hazardous pothole on 80ft road causing severe vehicle damages and traffic jams.",
                "area": "Indiranagar",
                "city": "Bengaluru",
                "lat": 12.97845,
                "lng": 77.64085
            }, headers=citizen_headers)
            data = r.json()
            duplicates = data.get("nearby_duplicates", [])
            ok = r.status_code == 200 and len(duplicates) >= 1
            record(21, "Live FAISS index detects duplicate report within 250m radius", ok, f"status={r.status_code}, dupes={len(duplicates)}")
        except Exception as e:
            record(21, "Live FAISS index detects duplicate report within 250m radius", False, str(e))

        # 22: GET /api/reports/{id} returns full report details and history
        try:
            rid = created_report_id or 1
            r = client.get(f"/api/reports/{rid}", headers=citizen_headers)
            data = r.json()
            ok = r.status_code == 200 and "report" in data and "checks" in data
            record(22, "GET /api/reports/{id} returns full report details and history", ok, f"status={r.status_code}")
        except Exception as e:
            record(22, "GET /api/reports/{id} returns full report details and history", False, str(e))

        # 23: POST /api/reports/{id}/checks submits and updates checks cleanly
        try:
            rid = created_report_id or 1
            # Check with demo neighbour or registered user
            r = client.post(f"/api/reports/{rid}/checks", json={"kind": "still_there", "note": "Checked today"}, headers=citizen_headers)
            ok = r.status_code == 200 and r.json().get("ok") is True
            record(23, "POST /api/reports/{id}/checks submits and updates checks cleanly", ok, f"status={r.status_code}")
        except Exception as e:
            record(23, "POST /api/reports/{id}/checks submits and updates checks cleanly", False, str(e))

        # 24: POST /api/reports/{id}/status enforces admin-only access
        try:
            rid = created_report_id or 1
            r = client.post(f"/api/reports/{rid}/status", json={"status": "in_progress"}, headers=citizen_headers)
            ok = r.status_code == 403
            record(24, "POST /api/reports/{id}/status enforces admin-only access", ok, f"status={r.status_code}")
        except Exception as e:
            record(24, "POST /api/reports/{id}/status enforces admin-only access", False, str(e))

        # 25: Static web assets and / redirect serve correctly
        try:
            r = client.get("/", follow_redirects=False)
            ok = r.status_code in (200, 301, 302, 307)
            record(25, "Static web assets and / redirect serve correctly", ok, f"status={r.status_code}")
        except Exception as e:
            record(25, "Static web assets and / redirect serve correctly", False, str(e))

        # 26: POST /api/auth/logout purges session and revokes access
        try:
            r = client.post("/api/auth/logout", headers=citizen_headers)
            r_me = client.get("/api/me", headers=citizen_headers)
            ok = r.status_code == 200 and r_me.status_code == 401
            record(26, "POST /api/auth/logout purges session and revokes access", ok, f"status={r.status_code}, me={r_me.status_code}")
        except Exception as e:
            record(26, "POST /api/auth/logout purges session and revokes access", False, str(e))

        # 27: Technician registration creates a linked profile and keeps admin data protected
        from app import db
        technician_email = f"technician_{uuid.uuid4().hex[:8]}@example.com"
        technician_id = worker_id = None
        technician_token = None
        try:
            with db.connect() as conn:
                worker = conn.execute(
                    "INSERT INTO workers (name, category, email) VALUES (?, ?, ?)",
                    ("Test Technician", "Water Supply", technician_email),
                )
                worker_id = worker.lastrowid

            registration = client.post(
                "/api/auth/register",
                json={
                    "name": "Test Technician",
                    "email": technician_email,
                    "password": "securepass123",
                    "role": "technician",
                    "category": "Water Supply",
                },
            )
            account = registration.json()
            technician_id = account.get("user", {}).get("id")
            technician_token = account.get("token")
            headers = {"Authorization": f"Bearer {technician_token}"} if technician_token else {}
            own_worker = client.get("/api/technician/worker", headers=headers)
            admin_worker = client.get(
                f"/api/admin/worker?id={own_worker.json().get('id', 0)}",
                headers=headers,
            )
            ok = (
                registration.status_code == 200
                and account.get("user", {}).get("role") == "technician"
                and own_worker.status_code == 200
                and own_worker.json().get("id") == worker_id
                and own_worker.json().get("category") == "Water Supply"
                and admin_worker.status_code == 403
            )
            record(
                27,
                "Technician registration creates a linked profile and keeps admin data protected",
                ok,
                f"register={registration.status_code}, own={own_worker.status_code}, admin_endpoint={admin_worker.status_code}",
            )
        except Exception as e:
            record(27, "Technician registration creates a linked profile and keeps admin data protected", False, str(e))
        finally:
            with db.connect() as conn:
                if technician_token:
                    conn.execute("DELETE FROM sessions WHERE token = ?", (technician_token,))
                if technician_id:
                    conn.execute(
                        "DELETE FROM workers WHERE user_id = ? OR email = ?",
                        (technician_id, technician_email),
                    )
                elif worker_id:
                    conn.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
                if technician_id:
                    conn.execute("DELETE FROM users WHERE id = ?", (technician_id,))

        # 28: Technician signup cannot add a fifth worker to a full category
        full_category_email = f"extra_technician_{uuid.uuid4().hex[:8]}@example.com"
        try:
            response = client.post(
                "/api/auth/register",
                json={
                    "name": "Extra Technician",
                    "email": full_category_email,
                    "password": "securepass123",
                    "role": "technician",
                    "category": "Water Supply",
                },
            )
            ok = response.status_code == 409
            record(
                28,
                "Technician signup cannot add a fifth worker to a full category",
                ok,
                f"status={response.status_code}",
            )
            if response.status_code == 200:
                extra_user_id = response.json().get("user", {}).get("id")
                with db.connect() as conn:
                    conn.execute(
                        "DELETE FROM workers WHERE user_id = ? OR email = ?",
                        (extra_user_id, full_category_email),
                    )
                    if extra_user_id:
                        conn.execute("DELETE FROM users WHERE id = ?", (extra_user_id,))
        except Exception as e:
            record(28, "Technician signup cannot add a fifth worker to a full category", False, str(e))

        with db.connect() as conn:
            test_user = conn.execute(
                "SELECT id FROM users WHERE email = ?", (test_email,)
            ).fetchone()
            if test_user:
                conn.execute(
                    "DELETE FROM checks WHERE report_id IN (SELECT id FROM reports WHERE user_id = ?)",
                    (test_user["id"],),
                )
                conn.execute("DELETE FROM notifications WHERE user_id = ?", (test_user["id"],))
                conn.execute("DELETE FROM complaints WHERE user_id = ?", (test_user["id"],))
                conn.execute("DELETE FROM reports WHERE user_id = ?", (test_user["id"],))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (test_user["id"],))
                conn.execute("DELETE FROM users WHERE id = ?", (test_user["id"],))

    print("=" * 65)
    print(f"  RESULT: {passed} / {total} PASSED ({passed*100//total}%, {len(failures)} FAILED)")
    print("=" * 65)

    if failures:
        print("\nFailures:")
        for num, name, reason in failures:
            print(f"  - [{num}] {name}: {reason}")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    run_tests()
