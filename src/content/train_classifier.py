r"""
Script per trainare il classificatore ML (TF-IDF + SVM).
Richiede scikit-learn (non disponibile su Python 3.14).
Uso: .\venv\Scripts\python -m src.content.train_classifier

Dataset atteso: models/training_data.json con formato:
[
    {"text": "...", "category": "invoice"},
    {"text": "...", "category": "sales"},
    ...
]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "training_data.json"
MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "classifier.pkl"


def main():
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.svm import LinearSVC
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.model_selection import cross_val_score
        import joblib
    except ImportError:
        print("ERRORE: scikit-learn non disponibile.")
        print("Installa con: pip install scikit-learn")
        print("Nota: richiede Python <= 3.12 per wheel precompilati.")
        sys.exit(1)

    if not DATASET_PATH.exists():
        print(f"ERRORE: Dataset non trovato: {DATASET_PATH}")
        print("Crea il file JSON con almeno 50-100 email etichettate.")
        sys.exit(1)

    # Carica dataset
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = [item["text"] for item in data]
    labels = [item["category"] for item in data]

    print(f"Dataset caricato: {len(data)} email")
    print(f"Categorie: {set(labels)}")
    print(f"Distribuzione: {dict((l, labels.count(l)) for l in set(labels))}")

    # Pipeline TF-IDF + SVM
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
    )

    X = vectorizer.fit_transform(texts)
    print(f"\nFeatures TF-IDF: {X.shape[1]}")

    # SVM con calibrazione probabilistica
    base_clf = LinearSVC(max_iter=10000, C=1.0)
    clf = CalibratedClassifierCV(base_clf, cv=3)
    clf.fit(X, labels)

    # Cross-validation
    scores = cross_val_score(clf, X, labels, cv=5, scoring="accuracy")
    print(f"Cross-validation accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

    # Salvataggio
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "vectorizer": vectorizer}, MODEL_PATH)
    print(f"\nModello salvato: {MODEL_PATH}")
    print("Training completato.")


if __name__ == "__main__":
    main()
