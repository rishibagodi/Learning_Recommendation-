"""
FastAPI server for the OULAD Learning Resource Recommendation System.

Endpoints:
  GET /api/students               — list students with id, cluster label, basic info
  GET /api/students/{id}          — full profile: cluster, pace, weak topics
  GET /api/students/{id}/recommendations?n=5 — ranked resources + explanation strings
  GET /api/clusters               — cluster centroids + PCA 2D coords per student
  GET /api/evaluation             — precision@k / recall@k for both ablation variants
"""

import os
import pickle
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.pipeline import (
    run_pipeline,
    recommend_for_student,
    FEATURE_COLS,
    PROCESSED_DIR,
    _get_student_cluster,
)

# ---------------------------------------------------------------------------
# Global state — loaded once at startup
# ---------------------------------------------------------------------------
STATE = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load or compute pipeline state on startup."""
    cache_path = os.path.join(PROCESSED_DIR, "pipeline_state.pkl")
    if os.path.exists(cache_path):
        print("Loading cached pipeline state...")
        with open(cache_path, "rb") as f:
            STATE.update(pickle.load(f))
        print("Pipeline state loaded from cache.")
    else:
        print("No cached state found — running pipeline...")
        STATE.update(run_pipeline())
        print("Pipeline complete.")

    # Pre-build O(1) site→tfidf-index lookup (avoids rebuilding per request)
    catalog = STATE["catalog"].reset_index(drop=True)
    STATE["site_to_tfidf_idx"] = {
        int(row["id_site"]): i for i, row in catalog.iterrows()
    }
    # Also cache cluster lookup dict
    ci = STATE["cluster_info"]
    ci["_student_cluster_map"] = dict(
        zip(ci["student_ids"], ci["cluster_labels"])
    )
    print(f"Pre-built lookup indices: {len(STATE['site_to_tfidf_idx'])} catalog sites.")
    yield


app = FastAPI(
    title="OULAD Learning Resource Recommender",
    description="AI-based personalized resource recommendation using K-Means + Content-Based Filtering",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _student_cluster_name(student_id: int) -> str:
    cluster_label = _get_student_cluster(student_id, STATE["cluster_info"])
    if cluster_label is not None:
        return STATE["cluster_info"]["centroids"].loc[cluster_label, "cluster_name"]
    return "unassigned"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/students")
def list_students(limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    """List students with id, cluster label, and basic info."""
    student_info = STATE["student_info"]
    cluster_info = STATE["cluster_info"]

    # Unique students
    unique_students = student_info.drop_duplicates(subset=["id_student"]).sort_values("id_student")
    total = len(unique_students)
    page = unique_students.iloc[offset : offset + limit]

    results = []
    for _, row in page.iterrows():
        sid = int(row["id_student"])
        cl = _get_student_cluster(sid, cluster_info)
        results.append({
            "id_student": sid,
            "gender": row.get("gender", ""),
            "region": row.get("region", ""),
            "highest_education": row.get("highest_education", ""),
            "age_band": row.get("age_band", ""),
            "final_result": row.get("final_result", ""),
            "cluster_label": int(cl) if cl is not None else None,
            "cluster_name": _student_cluster_name(sid),
        })

    return {"total": total, "offset": offset, "limit": limit, "students": results}


@app.get("/api/students/{student_id}")
def get_student(student_id: int):
    """Full student profile: cluster, pace stats, weak topics."""
    student_info = STATE["student_info"]
    engagement = STATE["engagement"]
    weak_topics = STATE["weak_topics"]
    cluster_info = STATE["cluster_info"]

    # Basic info
    info = student_info[student_info["id_student"] == student_id]
    if info.empty:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    info_row = info.iloc[0]

    # Cluster
    cl = _get_student_cluster(student_id, cluster_info)

    # Engagement / pace
    stu_eng = engagement[engagement["id_student"] == student_id]
    pace_stats = {}
    if not stu_eng.empty:
        pace_stats = {
            "avg_active_days": round(float(stu_eng["active_days"].mean()), 1),
            "avg_clicks_per_active_day": round(float(stu_eng["clicks_per_active_day"].mean()), 1),
            "pct_structured_content": round(float(stu_eng["pct_structured_content"].mean()), 3),
            "pct_interactive_quiz": round(float(stu_eng["pct_interactive_quiz"].mean()), 3),
            "pct_discussion_social": round(float(stu_eng["pct_discussion_social"].mean()), 3),
            "pct_other": round(float(stu_eng["pct_other"].mean()), 3),
        }

    # Weak topics
    stu_weak = weak_topics[weak_topics["id_student"] == student_id]
    weak_list = []
    for _, wr in stu_weak.iterrows():
        weak_list.append({
            "code_module": wr["code_module"],
            "module_avg_score": round(float(wr["module_avg_score"]), 1),
            "student_avg_score": round(float(wr["student_avg_score"]), 1),
            "is_weak": bool(wr["is_weak"]),
        })

    return {
        "id_student": student_id,
        "gender": str(info_row.get("gender", "")),
        "region": str(info_row.get("region", "")),
        "highest_education": str(info_row.get("highest_education", "")),
        "age_band": str(info_row.get("age_band", "")),
        "final_result": str(info_row.get("final_result", "")),
        "cluster_label": int(cl) if cl is not None else None,
        "cluster_name": _student_cluster_name(student_id),
        "pace_stats": pace_stats,
        "weak_topics": weak_list,
    }


@app.get("/api/students/{student_id}/recommendations")
def get_recommendations(student_id: int, n: int = Query(5, ge=1, le=20)):
    """Ranked resources + explanation strings for a student."""
    # Verify student exists
    student_info = STATE["student_info"]
    if student_id not in student_info["id_student"].values:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    recs = recommend_for_student(
        student_id,
        STATE["weak_topics"],
        STATE["catalog"],
        STATE["tfidf_matrix"],
        STATE["vectorizer"],
        STATE["cluster_info"],
        STATE["engagement"],
        n=n,
        site_to_tfidf_idx=STATE.get("site_to_tfidf_idx"),
    )
    return {
        "id_student": student_id,
        "n": n,
        "recommendations": recs,
    }


@app.get("/api/clusters")
def get_clusters():
    """Cluster centroids + PCA 2D coordinates per student."""
    cluster_info = STATE["cluster_info"]

    # Centroids
    centroids = []
    centroid_df = cluster_info["centroids"]
    for idx, row in centroid_df.iterrows():
        centroids.append({
            "cluster_id": int(idx),
            "cluster_name": row["cluster_name"],
            **{col: round(float(row[col]), 4) for col in FEATURE_COLS if col in row.index},
        })

    # Per-student PCA coords
    students = []
    for i, sid in enumerate(cluster_info["student_ids"]):
        students.append({
            "id_student": int(sid),
            "cluster_label": int(cluster_info["cluster_labels"][i]),
            "pca_x": round(float(cluster_info["pca_coords"][i, 0]), 4),
            "pca_y": round(float(cluster_info["pca_coords"][i, 1]), 4),
        })

    return {
        "k": cluster_info["k"],
        "silhouette_score": round(cluster_info["silhouette"], 4),
        "elbow_data": cluster_info["elbow_data"],
        "centroids": centroids,
        "students": students,
    }


@app.get("/api/evaluation")
def get_evaluation():
    """Precision@k / Recall@k results for both ablation variants."""
    return STATE.get("eval_results", {})
