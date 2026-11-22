"""Core ML logic: classify a complaint, find similar ones, recommend resolutions.

Speed notes
  * Every text is embedded only ONCE: embeddings are kept in a small cache, so classify,
    similar and recommend (and the map preview) share the same vector instead of running
    the sentence model again and again.
  * The model is warmed up when the server starts, so the first click is not slow.
  * Dataset rows are plain dicts (fast) instead of pandas .iloc lookups.
"""
import threading
from collections import OrderedDict

import faiss
import joblib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from app.config import CLASSIFIER_PATH, DATA_PATH, EMBED_MODEL, INDEX_PATH

SETUP_STEPS = ("python -m ml.generate_data  ->  python -m ml.train_classifier  ->  "
               "python -m ml.build_index   (run these from the backend folder)")


def _to_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class ComplaintEngine:
    CACHE_SIZE = 512

    def __init__(self):
        # Fail early with a message that says what to do, instead of a bare traceback.
        missing = [p.name for p in (DATA_PATH, CLASSIFIER_PATH, INDEX_PATH) if not p.exists()]
        if missing:
            raise RuntimeError(f"Missing file(s): {', '.join(missing)}. Run: {SETUP_STEPS}")

        self.df = pd.read_csv(DATA_PATH).fillna("")
        self.rows = self.df.to_dict("records")
        try:
            self.model = SentenceTransformer(EMBED_MODEL, local_files_only=True)
        except Exception:
            self.model = SentenceTransformer(EMBED_MODEL)
        self.clf = joblib.load(CLASSIFIER_PATH)
        self.index = faiss.read_index(str(INDEX_PATH))

        # The index row number must equal the CSV row number. If you regenerate the
        # CSV but forget to rebuild the index, results would silently point at the
        # wrong complaints, so check it here.
        if self.index.ntotal != len(self.df):
            raise RuntimeError(
                f"complaints.faiss has {self.index.ntotal} vectors but complaints.csv has "
                f"{len(self.df)} rows. Rebuild the index: python -m ml.build_index")

        self._cache = OrderedDict()
        self._cache_lock = threading.Lock()
        self._model_lock = threading.Lock()      # one encode at a time: avoids CPU thrashing
        self._dept, self._days = {}, {}
        self._encode(["warm up"])                # the first encode is slow: do it now

    # ------------------------------------------------------------ embeddings
    def _encode(self, texts):
        with self._model_lock:
            return self.model.encode(texts, normalize_embeddings=True).astype("float32")

    def embed(self, texts):
        out, todo = [None] * len(texts), []
        with self._cache_lock:
            for i, t in enumerate(texts):
                v = self._cache.get(t)
                if v is None:
                    todo.append(i)
                else:
                    out[i] = v
                    self._cache.move_to_end(t)
        if todo:
            vecs = self._encode([texts[i] for i in todo])
            with self._cache_lock:
                for i, v in zip(todo, vecs):
                    out[i] = v
                    self._cache[texts[i]] = v
                while len(self._cache) > self.CACHE_SIZE:
                    self._cache.popitem(last=False)
        return np.stack(out).astype("float32")

    # ------------------------------------------------------------ ML
    def classify(self, text, top_n=3):
        """Predicted category plus the top-n (category, probability) pairs."""
        probs = self.clf.predict_proba(self.embed([text]))[0]
        ranked = sorted(zip(self.clf.classes_, probs), key=lambda x: -x[1])
        top = [(str(c), float(p)) for c, p in ranked[:top_n]]
        return top[0][0], top

    def similar(self, text, k=5, category=None, resolved_only=False, vec=None):
        """Top-K most similar complaints, optionally filtered. `vec` = an embedding you already have."""
        q = self.embed([text]) if vec is None else np.ascontiguousarray(vec, dtype="float32").reshape(1, -1)
        scores, ids = self.index.search(q, min(len(self.rows), 200))
        results = []
        for score, i in zip(scores[0], ids[0]):
            if i < 0:
                continue
            row = self.rows[int(i)]
            if category and row["category"] != category:
                continue
            if resolved_only and row["status"] != "Resolved":
                continue
            results.append({
                "similarity": round(float(score), 3),
                "complaint_id": int(row["complaint_id"]),
                "text": str(row["text"]),
                "category": str(row["category"]),
                "ward": str(row["ward"]),
                "status": str(row["status"]),
                "resolution": str(row["resolution"]),
                "department": str(row["department"]),
                "resolution_days": _to_int(row["resolution_days"]),
            })
            if len(results) == k:
                break
        return results

    def department_for(self, category):
        if category not in self._dept:
            rows = self.df[self.df["category"] == category]
            if rows.empty:
                self._dept[category] = "Municipal Office"
            else:
                mode_series = rows["department"].mode()
                self._dept[category] = str(mode_series.iloc[0]) if not mode_series.empty else str(rows["department"].iloc[0])
        return self._dept[category]

    def typical_days(self, category):
        """Median resolution time (days) for a category, from past resolved complaints."""
        if category not in self._days:
            days = pd.to_numeric(
                self.df.loc[self.df["category"] == category, "resolution_days"],
                errors="coerce").dropna()
            self._days[category] = int(round(days.median())) if len(days) else None
        return self._days[category]

    def recommend(self, text, k=5):
        """Predict category, then return similar *resolved* complaints in it (with fallback)."""
        category, top = self.classify(text)
        matches = self.similar(text, k=k, category=category, resolved_only=True)
        if len(matches) < k:
            supplement = self.similar(text, k=k, category=category, resolved_only=False)
            seen_ids = {m["complaint_id"] for m in matches}
            for s in supplement:
                if s["complaint_id"] not in seen_ids:
                    matches.append(s)
                if len(matches) == k:
                    break
        return category, top, matches