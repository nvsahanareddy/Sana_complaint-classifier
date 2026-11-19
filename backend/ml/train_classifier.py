"""Step 2: train and evaluate classifiers.  Run from backend/:  python -m ml.train_classifier"""
import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

from app.config import CLASSIFIER_PATH, DATA_PATH, EMBED_MODEL, MODEL_DIR

def train():
    df = pd.read_csv(DATA_PATH)
    train_df, test_df = train_test_split(
        df, test_size=0.2, stratify=df["category"], random_state=42)

    # ---- Baseline: TF-IDF + Logistic Regression ----
    tfidf_clf = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
        LogisticRegression(max_iter=1000))
    tfidf_clf.fit(train_df["text"], train_df["category"])
    pred = tfidf_clf.predict(test_df["text"])
    print("=== TF-IDF + Logistic Regression ===")
    print(classification_report(test_df["category"], pred))
    print("Macro-F1:", round(f1_score(test_df["category"], pred, average="macro"), 4))

    # ---- Sentence embeddings + Logistic Regression ----
    embedder = SentenceTransformer(EMBED_MODEL)
    X_train = embedder.encode(train_df["text"].tolist(), normalize_embeddings=True)
    X_test = embedder.encode(test_df["text"].tolist(), normalize_embeddings=True)
    emb_clf = LogisticRegression(max_iter=1000)
    emb_clf.fit(X_train, train_df["category"])
    pred = emb_clf.predict(X_test)
    print("\n=== Sentence embeddings + Logistic Regression ===")
    print(classification_report(test_df["category"], pred))
    print("Macro-F1:", round(f1_score(test_df["category"], pred, average="macro"), 4))

    # ---- Refit on all data and save the embedding-based classifier ----
    X_all = embedder.encode(df["text"].tolist(), normalize_embeddings=True)
    emb_clf.fit(X_all, df["category"])
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(emb_clf, CLASSIFIER_PATH)
    print("\nSaved", CLASSIFIER_PATH)


if __name__ == "__main__":
    train()

