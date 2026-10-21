"""Hybrid content-based ranking of a topic's resources for one learner.

score = (0.4 + 0.6 * cosine(TF-IDF(learner query), TF-IDF(resource text)))
        x format boost x profile boost x difficulty match x session-length fit x popularity
"""

import math

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app import db
from app.content import topic

LEVEL = {"beginner": 1, "intermediate": 2, "advanced": 3}
DIFF_WORD = {1: "beginner", 2: "intermediate", 3: "advanced"}
FORMAT_WORD = {"video": "videos", "article": "reading docs and articles", "practice": "hands-on practice"}
PROFILE_KINDS = {"content-focused": ("video", "article"), "practice-driven": ("practice",)}


def rank(user_id: int, profile: dict, topic_key: str, state: str, n: int = 6) -> dict:
    t = topic(topic_key)
    pool = db.rows("""SELECT r.*, COALESCE(p.done, 0) AS done, p.helpful FROM resources r
                      LEFT JOIN progress p ON p.resource_id = r.id AND p.user_id = ?
                      WHERE r.topic_key = ?""", (user_id, topic_key))
    if not pool:
        return {"recommended": [], "completed": []}

    sk = db.one("SELECT correct, total FROM topic_scores WHERE user_id = ? AND topic_key = ? AND source = 'skill'",
                (user_id, topic_key))
    weak = sk is not None and sk["correct"] == 0
    revising = state == "revise"
    target = max(1, min(3, LEVEL[profile["level"]] - (1 if weak or revising else 0)))
    session_min = profile["hours_per_week"] * 60 / max(profile["days_per_week"], 1)
    style = next((s for s in PROFILE_KINDS if (profile.get("cluster_name") or "").startswith(s)), None)

    query = " ".join([t["name"], *t["keywords"], DIFF_WORD[target], "tutorial" if target == 1 else ""])
    texts = [f"{r['title']} {r.get('description') or ''} {r.get('channel') or ''}" for r in pool]
    vec = TfidfVectorizer(stop_words="english").fit(texts + [query])
    sims = cosine_similarity(vec.transform([query]), vec.transform(texts)).ravel()

    for r, sim in zip(pool, sims):
        fmt = 1.3 if r["kind"] == profile["format"] else 1.0
        prof = 1.1 if style and r["kind"] in PROFILE_KINDS[style] else 1.0
        diff = 1 - 0.15 * abs(r["difficulty"] - target)
        fit = 1.0
        if r["kind"] == "video" and r["duration_min"]:
            fit = 1.1 if r["duration_min"] <= session_min else 0.85 if r["duration_min"] > 3 * session_min else 1.0
        pop = 1 + 0.15 * min(math.log10((r["views"] or 0) + 1) / 7, 1) if r["kind"] == "video" else 1.0
        r["score"] = round((0.4 + 0.6 * float(sim)) * fmt * prof * diff * fit * pop, 4)
        r["why"] = explain(r, profile, target, fit, session_min, style)

    todo = sorted((r for r in pool if not r["done"]), key=lambda r: -r["score"])
    picked = todo[:n]
    if picked and all(r["kind"] == "video" for r in picked):  # keep at least one doc / practice link in view
        other = next((r for r in todo[n:] if r["kind"] != "video"), None)
        if other:
            picked[-1] = other
    return {"recommended": picked, "completed": [r for r in pool if r["done"]]}


def step_reason(user_id: int, t: dict, topic_key: str, state: str) -> str:
    """Why this topic is on the roadmap / what the resources below aim at."""
    sk = db.one("SELECT correct, total FROM topic_scores WHERE user_id = ? AND topic_key = ? AND source = 'skill'",
                (user_id, topic_key))
    if state == "completed":
        st = db.one("SELECT correct, total FROM topic_scores WHERE user_id = ? AND topic_key = ? AND source = 'step'",
                    (user_id, topic_key))
        return f"You passed the {t['name']} check ({st['correct']}/{st['total']}). These stay here for revision." if st \
            else f"{t['name']} is complete."
    if state == "revise":
        return f"You didn't pass the {t['name']} check yet, so these resources revisit the basics."
    if state == "skipped":
        return f"You scored {sk['correct']}/{sk['total']} on {t['name']} in the skill check, so it's skipped. Resources are here if you want a refresher."
    if sk and sk["correct"] == 0:
        return f"You scored 0/{sk['total']} on {t['name']} in the skill check, so these start from the basics."
    if sk and sk["correct"] < sk["total"]:
        return f"You scored {sk['correct']}/{sk['total']} on {t['name']}, so these fill the gaps (time estimate reduced)."
    return f"{t['name']} is the next step towards your goal."


def explain(r, profile, target, fit, session_min, style) -> str:
    parts = []
    if r["kind"] == profile["format"]:
        parts.append(f"Matches your preference for {FORMAT_WORD[profile['format']]}")
    elif style and r["kind"] in PROFILE_KINDS[style]:
        parts.append(f"Suits your '{profile['cluster_name']}' profile")
    else:
        parts.append(f"Adds {FORMAT_WORD[r['kind']]} alongside your main format")
    if r["difficulty"] == target:
        parts.append(f"{DIFF_WORD[target]} level, right for you now")
    elif r["difficulty"] > target:
        parts.append(f"{DIFF_WORD[r['difficulty']]} level, for after the basics")
    if r["kind"] == "video" and r["duration_min"] and fit > 1:
        parts.append(f"{round(r['duration_min'])} min fits one study session (~{round(session_min)} min)")
    elif r["kind"] == "video" and r["duration_min"] and fit < 1:
        parts.append(f"long ({round(r['duration_min'])} min): split it over several sessions")
    return "; ".join(parts) + "."
