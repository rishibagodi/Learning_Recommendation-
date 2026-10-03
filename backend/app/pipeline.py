"""
Data pipeline for OULAD-based learning resource recommendation.

Stages:
  1. Preprocessing — engagement matrix (% per bucket) + pace features
  2. Weak-topic detection — per-student weak modules
  3. K-Means clustering with elbow + silhouette analysis
  4. Resource catalog construction + TF-IDF vectorization
  5. Hybrid recommendation (filter → rank with cluster boost)
  6. Evaluation — Precision@k, Recall@k, ablation study
"""

import os
import warnings
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "..", "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "..", "data", "processed")

ACTIVITY_BUCKETS = {
    "oucontent": "structured_content",
    "resource": "structured_content",
    "subpage": "structured_content",
    "url": "structured_content",
    "page": "structured_content",
    "quiz": "interactive_quiz",
    "externalquiz": "interactive_quiz",
    "forumng": "discussion_social",
    "ouwiki": "discussion_social",
    "ouelluminate": "discussion_social",
    "oucollaborate": "discussion_social",
}
BUCKET_NAMES = ["structured_content", "interactive_quiz", "discussion_social", "other"]


# ===================================================================
# Stage 1 — Preprocessing
# ===================================================================
def load_raw_data():
    """Load all 7 OULAD CSVs."""
    dfs = {}
    for name in [
        "courses", "assessments", "vle", "studentInfo",
        "studentRegistration", "studentAssessment", "studentVle",
    ]:
        path = os.path.join(RAW_DIR, f"{name}.csv")
        dfs[name] = pd.read_csv(path)
    return dfs


def build_engagement_matrix(student_vle: pd.DataFrame, vle: pd.DataFrame) -> pd.DataFrame:
    """
    Merge studentVle + vle → per-student engagement-bucket percentages + pace features.

    Returns DataFrame indexed by (code_module, code_presentation, id_student) with columns:
      pct_structured_content, pct_interactive_quiz, pct_discussion_social, pct_other,
      active_days, clicks_per_active_day
    """
    merged = student_vle.merge(
        vle[["id_site", "code_module", "code_presentation", "activity_type"]],
        on=["id_site", "code_module", "code_presentation"],
        how="left",
    )
    merged["bucket"] = merged["activity_type"].map(ACTIVITY_BUCKETS).fillna("other")

    group_keys = ["code_module", "code_presentation", "id_student"]

    # Bucket click totals
    bucket_clicks = (
        merged.groupby(group_keys + ["bucket"])["sum_click"]
        .sum()
        .unstack(fill_value=0)
        .reindex(columns=BUCKET_NAMES, fill_value=0)
    )
    total_clicks = bucket_clicks.sum(axis=1).replace(0, 1)  # avoid div-by-zero
    bucket_pcts = bucket_clicks.div(total_clicks, axis=0)
    bucket_pcts.columns = [f"pct_{c}" for c in bucket_pcts.columns]

    # Pace features
    pace = merged.groupby(group_keys).agg(
        active_days=("date", "nunique"),
        total_clicks=("sum_click", "sum"),
    )
    pace["clicks_per_active_day"] = pace["total_clicks"] / pace["active_days"].replace(0, 1)
    pace = pace.drop(columns=["total_clicks"])

    engagement = bucket_pcts.join(pace, how="outer").reset_index()
    return engagement


# ===================================================================
# Stage 2 — Weak-topic detection
# ===================================================================
def detect_weak_topics(
    student_assessment: pd.DataFrame,
    assessments: pd.DataFrame,
) -> pd.DataFrame:
    """
    Per-student, flag code_modules where avg score < student's global avg.

    Returns DataFrame with columns:
      id_student, code_module, module_avg_score, student_avg_score, is_weak
    """
    merged = student_assessment.merge(
        assessments[["id_assessment", "code_module", "code_presentation"]],
        on="id_assessment",
        how="left",
    )
    merged["score"] = pd.to_numeric(merged["score"], errors="coerce")
    merged = merged.dropna(subset=["score"])

    # Per-student per-module average
    mod_avg = (
        merged.groupby(["id_student", "code_module"])["score"]
        .mean()
        .reset_index()
        .rename(columns={"score": "module_avg_score"})
    )
    # Per-student global average
    stu_avg = (
        merged.groupby("id_student")["score"]
        .mean()
        .reset_index()
        .rename(columns={"score": "student_avg_score"})
    )
    weak = mod_avg.merge(stu_avg, on="id_student")
    weak["is_weak"] = weak["module_avg_score"] < weak["student_avg_score"]
    return weak


# ===================================================================
# Stage 3 — K-Means clustering
# ===================================================================
FEATURE_COLS = [
    "pct_structured_content",
    "pct_interactive_quiz",
    "pct_discussion_social",
    "pct_other",
    "active_days",
    "clicks_per_active_day",
]


def cluster_students(
    engagement: pd.DataFrame,
    k_range=(3, 7),
) -> dict:
    """
    Cluster students on engagement features.

    Returns dict with keys:
      scaler, kmeans, k, silhouette, elbow_data,
      cluster_labels (Series aligned to engagement index),
      centroids (DataFrame), pca_coords (nx2 array), pca_model
    """
    # Aggregate to one row per student (average across module-presentations)
    agg = engagement.groupby("id_student")[FEATURE_COLS].mean()
    X_raw = agg.values
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    # Elbow + silhouette
    inertias, sil_scores = [], []
    for k in range(k_range[0], k_range[1]):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(X)
        inertias.append(float(km.inertia_))
        sil = float(silhouette_score(X, labels))
        sil_scores.append(sil)
        print(f"  k={k}: inertia={km.inertia_:.1f}, silhouette={sil:.4f}")

    # Pick k with best silhouette
    best_idx = int(np.argmax(sil_scores))
    best_k = k_range[0] + best_idx
    print(f"\n>>> Chosen k={best_k} (silhouette={sil_scores[best_idx]:.4f})")

    km = KMeans(n_clusters=best_k, n_init=10, random_state=42)
    labels = km.fit_predict(X)

    # PCA for visualization
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)

    # Interpret centroids
    centroids_raw = scaler.inverse_transform(km.cluster_centers_)
    centroid_df = pd.DataFrame(centroids_raw, columns=FEATURE_COLS)
    centroid_df.index.name = "cluster"

    # Name clusters
    cluster_names = _name_clusters(centroid_df)
    centroid_df["cluster_name"] = cluster_names

    result = {
        "scaler": scaler,
        "kmeans": km,
        "k": best_k,
        "silhouette": sil_scores[best_idx],
        "elbow_data": {
            "k_values": list(range(k_range[0], k_range[1])),
            "inertias": inertias,
            "silhouette_scores": sil_scores,
        },
        "student_ids": agg.index.tolist(),
        "cluster_labels": labels.tolist(),
        "centroids": centroid_df,
        "pca_coords": coords,
        "pca_model": pca,
    }
    return result


def _name_clusters(centroid_df: pd.DataFrame) -> list:
    """Generate interpretive names based on centroid features."""
    pct_cols = [c for c in centroid_df.columns if c.startswith("pct_")]
    names = []
    for _, row in centroid_df.iterrows():
        # Dominant bucket
        dominant = row[pct_cols].idxmax().replace("pct_", "")
        bucket_label = {
            "structured_content": "content-focused",
            "interactive_quiz": "quiz-driven",
            "discussion_social": "discussion-oriented",
            "other": "explorer",
        }.get(dominant, dominant)

        # Pace characterization (relative within centroids)
        pace = row.get("clicks_per_active_day", 0)
        all_paces = centroid_df["clicks_per_active_day"].values
        if pace >= np.percentile(all_paces, 66):
            pace_label = "fast"
        elif pace <= np.percentile(all_paces, 33):
            pace_label = "steady"
        else:
            pace_label = "moderate"

        names.append(f"{bucket_label} {pace_label} learner")
    return names


# ===================================================================
# Stage 4 — Resource catalog
# ===================================================================
def build_resource_catalog(vle: pd.DataFrame) -> pd.DataFrame:
    """
    Build recommendable item catalog from vle.csv.
    Each row = one VLE site (id_site) tagged with topic + format bucket + activity type.
    Tags are enriched to give TF-IDF enough signal to rank within a module.
    """
    catalog = vle.copy()
    catalog["bucket"] = catalog["activity_type"].map(ACTIVITY_BUCKETS).fillna("other")
    catalog["topic"] = catalog["code_module"]

    # Build richer tags: topic (repeated for weight) + bucket + specific activity_type
    # + presentation + early/mid/late week label to help TF-IDF differentiate resources
    def _week_label(row):
        w = row.get("week_from")
        try:
            w = float(w)
        except (TypeError, ValueError):
            return ""
        if w <= 5:
            return "early_weeks"
        elif w <= 15:
            return "mid_weeks"
        else:
            return "late_weeks"

    catalog["week_label"] = catalog.apply(_week_label, axis=1)
    catalog["tags"] = (
        catalog["topic"] + " "
        + catalog["topic"] + " "          # repeat topic for weight
        + catalog["bucket"] + " "
        + catalog["activity_type"] + " "  # specific type (e.g. quiz vs externalquiz)
        + catalog["code_presentation"] + " "
        + catalog["week_label"]
    ).str.strip()

    catalog = catalog.drop_duplicates(subset=["id_site"])
    return catalog


def vectorize_catalog(catalog: pd.DataFrame):
    """TF-IDF on resource tags. Returns vectorizer + matrix."""
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(catalog["tags"])
    return vectorizer, tfidf_matrix


# ===================================================================
# Stage 5 — Hybrid recommendation
# ===================================================================
def recommend_for_student(
    student_id: int,
    weak_topics_df: pd.DataFrame,
    catalog: pd.DataFrame,
    tfidf_matrix,
    vectorizer,
    cluster_info: dict,
    engagement: pd.DataFrame,
    n: int = 5,
    site_to_tfidf_idx: dict | None = None,
) -> list:
    """
    Staged hybrid recommendation:
      Stage 1 — filter catalog to student's weak topic(s)
      Stage 2 — rank by cosine similarity to student profile + cluster format boost
                 + week proximity bonus (earlier = more foundational) + activity diversity

    Returns list of dicts with keys:
      id_site, activity_type, topic, bucket, score, explanation
    """
    # Get student's weak topics
    stu_weak = weak_topics_df[
        (weak_topics_df["id_student"] == student_id) & (weak_topics_df["is_weak"])
    ]
    weak_modules = stu_weak["code_module"].unique().tolist()

    if not weak_modules:
        # No weak areas — use all modules the student studied
        stu_all = weak_topics_df[weak_topics_df["id_student"] == student_id]
        weak_modules = stu_all["code_module"].unique().tolist()

    if not weak_modules:
        return []

    # Stage 1: filter catalog
    filtered = catalog[catalog["topic"].isin(weak_modules)].copy().reset_index(drop=True)
    if filtered.empty:
        return []

    # Build student profile as TF-IDF query
    stu_eng = engagement[engagement["id_student"] == student_id]
    if stu_eng.empty:
        return []

    # Student's cluster
    cluster_label = _get_student_cluster(student_id, cluster_info)
    cluster_name = "unknown"
    dominant_bucket = "structured_content"
    if cluster_label is not None:
        centroids = cluster_info["centroids"]
        cluster_name = centroids.loc[cluster_label, "cluster_name"]
        pct_cols = [c for c in centroids.columns if c.startswith("pct_")]
        dominant_bucket = centroids.loc[cluster_label, pct_cols].idxmax().replace("pct_", "")

    # Build student query combining weak topics + preferred format (bucket + specific types)
    # Match vocabulary of enriched catalog tags for meaningful cosine similarity
    BUCKET_TO_TYPES = {
        "structured_content": ["structured_content", "oucontent", "resource", "subpage", "url", "page"],
        "interactive_quiz": ["interactive_quiz", "quiz", "externalquiz"],
        "discussion_social": ["discussion_social", "forumng", "ouwiki", "ouelluminate", "oucollaborate"],
        "other": ["other"],
    }
    query_parts = (
        weak_modules + weak_modules  # repeat for weight
        + BUCKET_TO_TYPES.get(dominant_bucket, [dominant_bucket])
    )
    query_str = " ".join(query_parts)
    query_vec = vectorizer.transform([query_str])

    # Cosine similarity against filtered catalog
    # Build an O(1) id_site → tfidf row index map (use pre-built if provided)
    _site_idx = site_to_tfidf_idx if site_to_tfidf_idx is not None else {
        int(r["id_site"]): i
        for i, r in catalog.reset_index(drop=True).iterrows()
    }
    flat_indices = [
        _site_idx[int(row["id_site"])]
        for _, row in filtered.iterrows()
        if int(row["id_site"]) in _site_idx
    ]
    if not flat_indices:
        return []
    filtered_tfidf = tfidf_matrix[flat_indices]
    similarities = cosine_similarity(query_vec, filtered_tfidf).flatten()

    # Cluster format boost (30% lift for matching dominant bucket)
    format_boost = np.array([
        1.3 if filtered.iloc[i]["bucket"] == dominant_bucket else 1.0
        for i in range(len(filtered))
    ])

    # Week proximity bonus: resources appearing earlier in the module are
    # more foundational — add a small bonus (max 5% of base score) to
    # break ties among items with identical cosine similarity.
    # week_from is NaN for some rows; treat NaN as median.
    if "week_from" in filtered.columns:
        weeks = filtered["week_from"].astype(float)
        week_max = weeks.max()
        week_min = weeks.min()
        week_range = max(week_max - week_min, 1)
        # Earlier week → higher bonus (inverted normalisation)
        week_bonus = 1.0 + 0.05 * (1.0 - (weeks.fillna(weeks.median()) - week_min) / week_range)
    else:
        week_bonus = np.ones(len(filtered))

    scores = similarities * format_boost * week_bonus.values

    # Enforce activity-type diversity: keep at most 2 items per activity_type
    activity_counts: dict = {}
    diverse_indices = []
    for idx in np.argsort(scores)[::-1]:
        act = filtered.iloc[idx]["activity_type"]
        if activity_counts.get(act, 0) < 2:
            diverse_indices.append(idx)
            activity_counts[act] = activity_counts.get(act, 0) + 1
        if len(diverse_indices) >= n:
            break

    results = []
    for idx in diverse_indices:
        row = filtered.iloc[idx]
        score = float(scores[idx])
        if score <= 0:
            continue

        weak_score_info = ""
        for _, wr in stu_weak[stu_weak["code_module"] == row["topic"]].iterrows():
            weak_score_info = f" (your avg: {wr['module_avg_score']:.0f} vs overall: {wr['student_avg_score']:.0f})"
            break

        # Generate explanation
        format_match = " Matches your cluster's preferred format." if row["bucket"] == dominant_bucket else ""
        week_info = ""
        if "week_from" in row and pd.notna(row.get("week_from")):
            week_info = f" Available from week {int(row['week_from'])}."
        explanation = (
            f"Recommended because {row['topic']} is a weak area for you{weak_score_info}. "
            f"This {row['bucket'].replace('_', ' ')} resource ({row['activity_type']}) aligns with your "
            f"'{cluster_name}' learning profile.{format_match}{week_info}"
        )

        results.append({
            "id_site": int(row["id_site"]),
            "activity_type": row["activity_type"],
            "topic": row["topic"],
            "bucket": row["bucket"],
            "score": round(score, 4),
            "explanation": explanation,
        })

    return results


def _get_student_cluster(student_id, cluster_info):
    """Look up which cluster a student belongs to (O(1) via cached dict)."""
    # Build lookup dict on first call and cache it inside cluster_info
    if "_student_cluster_map" not in cluster_info:
        cluster_info["_student_cluster_map"] = dict(
            zip(cluster_info["student_ids"], cluster_info["cluster_labels"])
        )
    return cluster_info["_student_cluster_map"].get(student_id, None)


# ===================================================================
# Stage 6 — Evaluation
# ===================================================================
def evaluate_recommendations(
    engagement: pd.DataFrame,
    weak_topics_df: pd.DataFrame,
    catalog: pd.DataFrame,
    tfidf_matrix,
    vectorizer,
    cluster_info: dict,
    student_vle: pd.DataFrame,
    k_eval: int = 5,
    sample_size: int = 500,
) -> dict:
    """
    Precision@k and Recall@k via holdout evaluation.
    Also runs ablation: content-based-only vs. hybrid (content-based + clustering).
    """
    rng = np.random.RandomState(42)

    # Get students that have both engagement data and weak topics
    valid_students = set(engagement["id_student"].unique()) & set(
        weak_topics_df["id_student"].unique()
    )
    valid_students = sorted(valid_students)
    if len(valid_students) > sample_size:
        valid_students = rng.choice(valid_students, sample_size, replace=False).tolist()

    # Build ground-truth: actual VLE sites each student interacted with
    student_sites = (
        student_vle.groupby("id_student")["id_site"]
        .apply(set)
        .to_dict()
    )

    results = {"hybrid": {"precision": [], "recall": []}, "content_only": {"precision": [], "recall": []}}

    for sid in valid_students:
        actual_sites = student_sites.get(sid, set())
        if len(actual_sites) < 5:
            continue

        # Hold out 30% of interactions as test set
        actual_list = sorted(actual_sites)
        test_size = max(1, int(len(actual_list) * 0.3))
        test_set = set(rng.choice(actual_list, test_size, replace=False).tolist())

        # Hybrid recommendations
        recs_hybrid = recommend_for_student(
            sid, weak_topics_df, catalog, tfidf_matrix, vectorizer,
            cluster_info, engagement, n=k_eval,
        )
        rec_sites_hybrid = {r["id_site"] for r in recs_hybrid}

        # Content-only (no cluster boost) — build a dummy cluster_info
        dummy_cluster = {**cluster_info}
        dummy_centroids = cluster_info["centroids"].copy()
        # Set all pct columns equal — no dominant bucket
        for col in [c for c in dummy_centroids.columns if c.startswith("pct_")]:
            dummy_centroids[col] = 0.25
        dummy_cluster["centroids"] = dummy_centroids

        recs_content = recommend_for_student(
            sid, weak_topics_df, catalog, tfidf_matrix, vectorizer,
            dummy_cluster, engagement, n=k_eval,
        )
        rec_sites_content = {r["id_site"] for r in recs_content}

        # Compute metrics
        for variant, rec_sites in [("hybrid", rec_sites_hybrid), ("content_only", rec_sites_content)]:
            if not rec_sites:
                continue
            hits = rec_sites & test_set
            precision = len(hits) / len(rec_sites) if rec_sites else 0
            recall = len(hits) / len(test_set) if test_set else 0
            results[variant]["precision"].append(precision)
            results[variant]["recall"].append(recall)

    summary = {}
    for variant in ["hybrid", "content_only"]:
        p_list = results[variant]["precision"]
        r_list = results[variant]["recall"]
        summary[variant] = {
            "precision_at_k": round(float(np.mean(p_list)) if p_list else 0, 4),
            "recall_at_k": round(float(np.mean(r_list)) if r_list else 0, 4),
            "num_students_evaluated": len(p_list),
        }

    return summary


# ===================================================================
# Main pipeline execution
# ===================================================================
def run_pipeline():
    """Execute the full pipeline and cache results."""
    print("=" * 60)
    print("OULAD LEARNING RESOURCE RECOMMENDATION PIPELINE")
    print("=" * 60)

    # Load data
    print("\n[1/6] Loading raw data...")
    dfs = load_raw_data()
    print(f"  Loaded {len(dfs)} files.")
    for name, df in dfs.items():
        print(f"    {name}: {df.shape}")

    # Stage 1: Engagement matrix
    print("\n[2/6] Building engagement matrix...")
    engagement = build_engagement_matrix(dfs["studentVle"], dfs["vle"])
    print(f"  Engagement matrix shape: {engagement.shape}")
    print(f"  Sample:\n{engagement.head(3).to_string()}")

    # Stage 2: Weak-topic detection
    print("\n[3/6] Detecting weak topics...")
    weak_topics = detect_weak_topics(dfs["studentAssessment"], dfs["assessments"])
    n_weak = weak_topics["is_weak"].sum()
    print(f"  Total student-module pairs: {len(weak_topics)}, weak: {n_weak}")

    # Stage 3: Clustering
    print("\n[4/6] Clustering students...")
    cluster_info = cluster_students(engagement)
    print(f"\n  Cluster centroids:")
    print(cluster_info["centroids"].to_string())

    # Stage 4: Resource catalog
    print("\n[5/6] Building resource catalog + TF-IDF...")
    catalog = build_resource_catalog(dfs["vle"])
    vectorizer, tfidf_matrix = vectorize_catalog(catalog)
    print(f"  Catalog size: {len(catalog)} resources")
    print(f"  TF-IDF matrix: {tfidf_matrix.shape}")

    # Quick sanity check — recommend for a sample student
    sample_students = engagement["id_student"].unique()[:3]
    print("\n  Sample recommendations:")
    for sid in sample_students:
        recs = recommend_for_student(
            int(sid), weak_topics, catalog, tfidf_matrix, vectorizer,
            cluster_info, engagement, n=3,
        )
        print(f"\n  Student {sid}:")
        for r in recs:
            print(f"    - [{r['bucket']}] {r['topic']} site={r['id_site']} "
                  f"score={r['score']:.3f}")
            print(f"      {r['explanation']}")

    # Stage 6: Evaluation
    print("\n[6/6] Running evaluation (this may take a minute)...")
    eval_results = evaluate_recommendations(
        engagement, weak_topics, catalog, tfidf_matrix, vectorizer,
        cluster_info, dfs["studentVle"], k_eval=5, sample_size=500,
    )
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS (ablation study)")
    print("=" * 60)
    for variant, metrics in eval_results.items():
        print(f"  {variant}:")
        print(f"    Precision@5 = {metrics['precision_at_k']:.4f}")
        print(f"    Recall@5    = {metrics['recall_at_k']:.4f}")
        print(f"    Evaluated on {metrics['num_students_evaluated']} students")

    print("\n" + "=" * 60)
    print("SUMMARY FOR REPORT")
    print("=" * 60)
    print(f"  Chosen k          = {cluster_info['k']}")
    print(f"  Silhouette score  = {cluster_info['silhouette']:.4f}")
    print(f"  Hybrid Prec@5     = {eval_results['hybrid']['precision_at_k']:.4f}")
    print(f"  Hybrid Recall@5   = {eval_results['hybrid']['recall_at_k']:.4f}")
    print(f"  ContentOnly Prec@5= {eval_results['content_only']['precision_at_k']:.4f}")
    print(f"  ContentOnly Rec@5 = {eval_results['content_only']['recall_at_k']:.4f}")

    # Save processed artifacts
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    pipeline_state = {
        "engagement": engagement,
        "weak_topics": weak_topics,
        "catalog": catalog,
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf_matrix,
        "cluster_info": cluster_info,
        "eval_results": eval_results,
        "student_info": dfs["studentInfo"],
        "student_vle": dfs["studentVle"],
    }
    with open(os.path.join(PROCESSED_DIR, "pipeline_state.pkl"), "wb") as f:
        pickle.dump(pipeline_state, f)
    print(f"\n  Pipeline state saved to {PROCESSED_DIR}/pipeline_state.pkl")

    return pipeline_state


if __name__ == "__main__":
    run_pipeline()
