"""Add demo reports around Bengaluru so the map has pins to look at.

Run from the backend/ folder (venv active), BEFORE starting uvicorn:

    python seed_demo.py

Safe to run twice: it does nothing if the demo reports already exist.
Demo accounts (password for both: demo-pass-123):
    demo.reporter@example.com     demo.neighbour@example.com
"""
import random

import pandas as pd

from app import auth, db, reports
from app.config import DATA_PATH
from app.engine import ComplaintEngine

PLACES = [  # (area, lat, lng): approximate centres of well-known Bengaluru areas
    ("Indiranagar", 12.9784, 77.6408), ("Koramangala", 12.9352, 77.6245),
    ("Jayanagar", 12.9308, 77.5838), ("Malleshwaram", 13.0035, 77.5647),
    ("Whitefield", 12.9698, 77.7500), ("HSR Layout", 12.9121, 77.6446),
    ("Hebbal", 13.0358, 77.5970), ("Yelahanka", 13.1007, 77.5963),
    ("BTM Layout", 12.9166, 77.6101), ("Rajajinagar", 12.9916, 77.5521),
    ("Electronic City", 12.8452, 77.6602), ("Banashankari", 12.9255, 77.5468),
]
STATUSES = ["open", "closed", "in_progress", "open", "fix_to_verify", "closed"]


def get_or_create_user(conn, name, email):
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                       (name, email, auth.hash_password("demo-pass-123")))
    return cur.lastrowid


def main():
    random.seed(7)
    db.init_db()
    eng = ComplaintEngine()
    df = pd.read_csv(DATA_PATH).drop_duplicates(subset="text")
    categories = sorted(df["category"].unique())

    with db.connect() as conn:
        reporter = get_or_create_user(conn, "Demo Reporter", "demo.reporter@example.com")
        neighbour = get_or_create_user(conn, "Demo Neighbour", "demo.neighbour@example.com")
        if conn.execute("SELECT COUNT(*) FROM reports WHERE user_id = ?", (reporter,)).fetchone()[0]:
            print("Demo reports already exist; nothing to do.")
            return
        for i, (area, lat, lng) in enumerate(PLACES):
            category = categories[i % len(categories)]
            text = df[df["category"] == category].sample(1, random_state=i).iloc[0]["text"]
            title = text.split(".")[0][:70]
            rid, _ = reports.insert_report(
                conn, eng, reporter, title, text, category, "Bengaluru", area,
                lat + random.uniform(-0.004, 0.004), lng + random.uniform(-0.004, 0.004))
            status = STATUSES[i % len(STATUSES)]
            if status != "open":
                conn.execute("UPDATE reports SET status = ? WHERE id = ?", (status, rid))
            if i % 3 == 0:
                conn.execute("INSERT INTO checks (report_id, user_id, kind, note) VALUES (?, ?, ?, ?)",
                             (rid, neighbour, "still_there", "Still there this morning"))
    print(f"Added {len(PLACES)} demo reports. Start the server and open http://127.0.0.1:8000")


if __name__ == "__main__":
    main()

