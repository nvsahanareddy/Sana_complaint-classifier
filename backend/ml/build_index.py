"""Step 3: build the FAISS vector index.  Run from backend/:  python -m ml.build_index"""
import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from app.config import DATA_PATH, EMBED_MODEL, EMBEDDINGS_PATH, INDEX_PATH, MODEL_DIR

def build():
    df = pd.read_csv(DATA_PATH)
    model = SentenceTransformer(EMBED_MODEL)
    emb = model.encode(df["text"].tolist(), normalize_embeddings=True,
                       show_progress_bar=True).astype("float32")

    # Vectors are normalised, so inner product == cosine similarity
    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    np.save(EMBEDDINGS_PATH, emb)
    print(f"Indexed {index.ntotal} complaints (dim={emb.shape[1]})")


if __name__ == "__main__":
    build()
