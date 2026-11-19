"""Checks why the backend does not start or is slow.  Run from the backend folder:
       .venv\\Scripts\\python.exe check_backend.py
"""
import importlib
import os
import socket
import sqlite3
import sys
from pathlib import Path

print("Python", sys.version.split()[0], "\n")
print("-- libraries")
for name in ("fastapi", "uvicorn", "pydantic", "numpy", "pandas", "sklearn", "joblib", "faiss", "sentence_transformers"):
    try:
        importlib.import_module(name)
        print(f"  OK    {name}")
    except Exception as ex:
        print(f"  FAIL  {name}: {ex}")

print("\n-- files")
try:
    from app.config import CLASSIFIER_PATH, DATA_PATH, DB_PATH, INDEX_PATH
    for label, p in (("dataset", DATA_PATH), ("classifier", CLASSIFIER_PATH), ("FAISS index", INDEX_PATH)):
        print(f"  {'OK  ' if Path(p).exists() else 'FAIL'}  {label}: {p}")
except Exception as ex:
    print("  FAIL  cannot read app/config.py:", ex)
    DB_PATH = None

print("\n-- database")
if DB_PATH and Path(DB_PATH).exists():
    print("  file:", DB_PATH, f"({Path(DB_PATH).stat().st_size // 1024} KB)")
    if any(x in str(DB_PATH).lower() for x in ("onedrive", "dropbox", "google drive")):
        print("  NOTE  the database is inside a synced folder (OneDrive/Dropbox). That can make it slow or locked. Move the project to C:\\projects.")
    try:
        c = sqlite3.connect(DB_PATH, timeout=5)
        print("  journal mode:", c.execute("PRAGMA journal_mode").fetchone()[0])
        for t in ("users", "workers", "complaints", "reports"):
            try:
                print(f"  {t}: {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rows")
            except sqlite3.Error as ex:
                print(f"  {t}: {ex}")
        c.execute("BEGIN IMMEDIATE"); c.rollback()
        print("  OK    the database can be written (no other program is blocking it)")
        c.close()
    except sqlite3.Error as ex:
        print("  FAIL  database problem:", ex, "\n        -> close every other backend window, then try again")
else:
    print("  (no database file yet: it is created on the first start)")

print("\n-- port 8000")
s = socket.socket(); s.settimeout(1)
if s.connect_ex(("127.0.0.1", 8000)) == 0:
    print("  NOTE  something is already running on port 8000 (an older backend window?). Only ONE backend may run.")
else:
    print("  OK    port 8000 is free (no backend running right now)")
s.close()

print("\n-- sentence model")
cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub" / "models--sentence-transformers--all-MiniLM-L6-v2"
print(f"  {'OK  ' if cache.exists() else 'NOTE'}  model {'is downloaded' if cache.exists() else 'is not downloaded yet: the first start needs internet once'}")
print("\nDone. Send me this whole text if something is still wrong.")