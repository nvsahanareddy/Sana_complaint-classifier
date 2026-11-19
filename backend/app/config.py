import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]          # .../backend
FRONTEND_DIR = BASE_DIR.parent / "frontend"

DATA_PATH = BASE_DIR / "data" / "complaints.csv"
DB_PATH = BASE_DIR / "data" / "app.db"          # users, complaints, notifications
MODEL_DIR = BASE_DIR / "models"
CLASSIFIER_PATH = MODEL_DIR / "classifier.joblib"
INDEX_PATH = MODEL_DIR / "complaints.faiss"
EMBEDDINGS_PATH = MODEL_DIR / "embeddings.npy"

EMBED_MODEL = "all-MiniLM-L6-v2"
DUPLICATE_THRESHOLD = 0.85

# CORS Settings
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5503,http://localhost:5503",
    ).split(",")
    if o.strip()
]
ALLOW_ALL_ORIGINS = os.environ.get("ALLOW_ALL_ORIGINS", "true").lower() in ("true", "1", "yes")