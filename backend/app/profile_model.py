"""Learner-profile model: K-Means trained on real OULAD learner behaviour, applied to new users.

Train once (needs data/raw/studentVle.csv + vle.csv from OULAD):
    python -m app.profile_model train

A new user's onboarding answers are mapped onto the same 6 behaviour features using the
percentiles of the OULAD population (e.g. "prefers practice" -> 90th percentile of quiz share),
then scaled and assigned to the nearest cluster. Without a trained model, a rule-based fallback
gives the same kind of label so the app still works.
"""

import os
import pickle
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE, "..", "data", "processed", "profile_model.pkl")
RAW_DIR = os.path.join(BASE, "..", "data", "raw")
FEATURES = ["pct_structured_content", "pct_interactive_quiz", "pct_discussion_social", "pct_other",
            "active_days", "clicks_per_active_day"]
PCTS = [10, 25, 50, 75, 90]
STYLE = {"structured_content": "content-focused", "interactive_quiz": "practice-driven",
         "discussion_social": "community-oriented", "other": "exploratory"}

_model = None


def train(k: int = 4):
    import pandas as pd
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
    from app.pipeline import build_engagement_matrix

    print("Loading OULAD click logs...")
    vle = pd.read_csv(os.path.join(RAW_DIR, "vle.csv"))
    svle = pd.read_csv(os.path.join(RAW_DIR, "studentVle.csv"))
    X_df = build_engagement_matrix(svle, vle).groupby("id_student")[FEATURES].mean().dropna()
    scaler = StandardScaler().fit(X_df.values)
    X = scaler.transform(X_df.values)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    sample = np.random.RandomState(42).choice(len(X), min(len(X), 10000), replace=False)
    sil = float(silhouette_score(X[sample], km.labels_[sample]))

    # Name each cluster by what it does MORE than the average learner (standardised centroid).
    centers = km.cluster_centers_
    pace_rank = np.argsort(np.argsort(centers[:, FEATURES.index("clicks_per_active_day")]))
    names = []
    for i, c in enumerate(centers):
        style = STYLE[FEATURES[int(np.argmax(c[:4]))].replace("pct_", "")]
        pace = "fast" if pace_rank[i] == k - 1 else "steady" if pace_rank[i] == 0 else "moderate"
        names.append(f"{style} {pace} learner")
    for i, n in enumerate(names):  # disambiguate duplicates by consistency (active days)
        if names.count(n) > 1:
            names[i] = n + (" (regular)" if centers[i, FEATURES.index("active_days")] > 0 else " (occasional)")

    model = {"scaler": scaler, "kmeans": km, "names": names, "silhouette": sil, "n_students": len(X_df),
             "percentiles": {f: np.percentile(X_df[f], PCTS).tolist() for f in FEATURES},
             "sizes": np.bincount(km.labels_, minlength=k).tolist()}
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(model, fh)
    print(f"Trained on {len(X_df)} students, k={k}, silhouette={sil:.3f}")
    for n, s in zip(names, model["sizes"]):
        print(f"  {n:45s} {s} students")


def load():
    global _model
    if _model is None and os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as fh:
            _model = pickle.load(fh)
    return _model


def _at(pcts: list, level: float) -> float:
    """Value at a population percentile level in [0, 1] (interpolated between 10th..90th)."""
    return float(np.interp(level * 100, PCTS, pcts))


def assign(fmt: str, hours_per_week: float, days_per_week: int, likes_discussion: bool) -> dict:
    hours_per_day = hours_per_week / max(days_per_week, 1)
    intensity = min(hours_per_day / 3, 1.0)       # 3+ h per study day = top of the scale
    regularity = min(days_per_week / 7, 1.0)
    m = load()
    if m is None:
        style = {"video": "content-focused", "article": "content-focused", "practice": "practice-driven"}[fmt]
        if likes_discussion and fmt != "practice":
            style = "community-oriented"
        pace = "fast" if intensity > 0.66 else "steady" if intensity < 0.33 else "moderate"
        return {"cluster_id": None, "cluster_name": f"{style} {pace} learner", "source": "rule-based"}

    p = m["percentiles"]
    share = [
        _at(p["pct_structured_content"], 0.9 if fmt in ("video", "article") else 0.4),
        _at(p["pct_interactive_quiz"], 0.9 if fmt == "practice" else 0.3),
        _at(p["pct_discussion_social"], 0.9 if likes_discussion else 0.3),
        _at(p["pct_other"], 0.5),
    ]
    share = [s / sum(share) for s in share]
    x = np.array([share + [_at(p["active_days"], regularity), _at(p["clicks_per_active_day"], intensity)]])
    cid = int(m["kmeans"].predict(m["scaler"].transform(x))[0])
    return {"cluster_id": cid, "cluster_name": m["names"][cid], "source": f"K-Means on {m['n_students']} OULAD learners"}


if __name__ == "__main__":
    if sys.argv[1:2] == ["train"]:
        train(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    else:
        sys.exit(__doc__)
