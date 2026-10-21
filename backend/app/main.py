"""FastAPI server for the AI-Based Learning Recommendation System (v2).

Run:  uvicorn app.main:app --reload --port 8000   (from backend/)
"""

import os
from contextlib import asynccontextmanager
from typing import Literal

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from fastapi import Depends, FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app import auth, content, db, profile_model, recommender, roadmap  # noqa: E402
from app.auth import current_user  # noqa: E402

@asynccontextmanager
async def lifespan(_app):
    db.init()
    content.seed_curated()
    yield


app = FastAPI(title="AI-Based Learning Recommendation System", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)


def get_profile(user_id: int) -> dict | None:
    return db.one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))


def need_profile(user: dict) -> dict:
    p = get_profile(user["id"])
    if not p:
        raise HTTPException(400, "Finish onboarding first")
    return p


def step_state(user_id: int, topic_key: str) -> str:
    s = db.one("SELECT state FROM roadmap WHERE user_id = ? AND topic_key = ?", (user_id, topic_key))
    if not s:
        raise HTTPException(404, "This topic is not on your roadmap")
    return s["state"]


def public_questions(topic_key: str, idx: list[int]) -> list[dict]:
    t = content.topic(topic_key)
    return [{"id": f"{topic_key}#{i}", "topic": t["name"], "q": t["questions"][i]["q"],
             "options": t["questions"][i]["options"]} for i in idx]


def grade(answers: dict[str, int], qids: list[str]) -> dict[str, tuple[int, int]]:
    """Returns {topic_key: (correct, total)} for the given question ids."""
    out = {}
    for qid in qids:
        key, i = qid.rsplit("#", 1)
        ok = answers.get(qid) == content.topic(key)["questions"][int(i)]["answer"]
        c, n = out.get(key, (0, 0))
        out[key] = (c + ok, n + 1)
    return out


# ---------------------------------------------------------------- account / onboarding

@app.get("/api/me")
def me(user=Depends(current_user)):
    p = get_profile(user["id"])
    stage = "onboarding" if not p else "quiz" if not p["quiz_done"] else "ready"
    m = profile_model.load()
    model = {"type": "K-Means", "students": m["n_students"], "clusters": len(m["names"]),
             "silhouette": round(m["silhouette"], 3)} if m else {"type": "rule-based fallback"}
    return {"user": user, "stage": stage, "profile": p, "model": model}


@app.get("/api/domains")
def list_domains():
    return [{"id": d["id"], "name": d["name"], "description": d["description"],
             "goals": [{"id": g["id"], "name": g["name"]} for g in d["goals"]],
             "topics": [t["name"] for t in d["topics"]]} for d in content.domains().values()]


class OnboardingIn(BaseModel):
    domain: str
    goal: str
    level: Literal["beginner", "intermediate", "advanced"]
    format: Literal["video", "article", "practice"]
    hours_per_week: float = Field(ge=1, le=60)
    days_per_week: int = Field(ge=1, le=7)
    likes_discussion: bool = False


@app.post("/api/onboarding")
def onboarding(body: OnboardingIn, user=Depends(current_user)):
    d = content.domains().get(body.domain)
    if not d or body.goal not in {g["id"] for g in d["goals"]}:
        raise HTTPException(400, "Unknown domain or goal")
    c = profile_model.assign(body.format, body.hours_per_week, body.days_per_week, body.likes_discussion)
    db.run("DELETE FROM profiles WHERE user_id = ?", (user["id"],))
    db.run("DELETE FROM roadmap WHERE user_id = ?", (user["id"],))
    db.run("DELETE FROM topic_scores WHERE user_id = ?", (user["id"],))
    db.run("""INSERT INTO profiles (user_id, domain, goal, level, format, hours_per_week, days_per_week,
              likes_discussion, cluster_id, cluster_name, cluster_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
           (user["id"], body.domain, body.goal, body.level, body.format, body.hours_per_week, body.days_per_week,
            int(body.likes_discussion), c["cluster_id"], c["cluster_name"], c["source"]))
    return get_profile(user["id"])


@app.get("/api/quiz/skill")
def skill_quiz(user=Depends(current_user)):
    p = need_profile(user)
    topics = roadmap.required_topics(p["domain"], p["goal"])
    return [q for tid in topics for q in public_questions(f"{p['domain']}:{tid}", [0, 1])]


class AnswersIn(BaseModel):
    answers: dict[str, int]


@app.post("/api/quiz/skill")
def submit_skill_quiz(body: AnswersIn, user=Depends(current_user)):
    p = need_profile(user)
    topics = roadmap.required_topics(p["domain"], p["goal"])
    qids = [f"{p['domain']}:{tid}#{i}" for tid in topics for i in (0, 1)]
    scores = grade(body.answers, qids)
    db.run_many("INSERT OR REPLACE INTO topic_scores (user_id, topic_key, source, correct, total) VALUES (?, ?, 'skill', ?, ?)",
                [(user["id"], k, c, n) for k, (c, n) in scores.items()])
    roadmap.build(user["id"], p["domain"], p["goal"], {k.split(":", 1)[1]: v for k, v in scores.items()})
    db.run("UPDATE profiles SET quiz_done = 1 WHERE user_id = ?", (user["id"],))
    d = content.domains()[p["domain"]]
    return [{"topic": d["topic_map"][k.split(":", 1)[1]]["name"], "correct": c, "total": n,
             "result": "known (skipped)" if c == n else "partly known" if c else "new / weak"}
            for k, (c, n) in scores.items()]


@app.delete("/api/profile")
def restart(user=Depends(current_user)):
    for table in ("roadmap", "topic_scores", "progress", "profiles"):
        db.run(f"DELETE FROM {table} WHERE user_id = ?", (user["id"],))
    return {"ok": True}


# ---------------------------------------------------------------- roadmap / recommendations

@app.get("/api/roadmap")
def get_roadmap(user=Depends(current_user)):
    return roadmap.view(user["id"], need_profile(user))


@app.get("/api/steps/{topic_key}")
def get_step(topic_key: str, n: int = 6, user=Depends(current_user)):
    p = need_profile(user)
    state = step_state(user["id"], topic_key)
    warning = content.ensure_videos(topic_key)
    t = content.topic(topic_key)
    recs = recommender.rank(user["id"], p, topic_key, state, n=n)
    step = next(s for s in roadmap.view(user["id"], p)["steps"] if s["topic_key"] == topic_key)
    return {**step, "keywords": t["keywords"], "warning": warning, "reason": recommender.step_reason(user["id"], t, topic_key, state), **recs}


class ProgressIn(BaseModel):
    done: bool = True
    helpful: bool | None = None


@app.post("/api/resources/{resource_id}/progress")
def set_progress(resource_id: int, body: ProgressIn, user=Depends(current_user)):
    if not db.one("SELECT 1 FROM resources WHERE id = ?", (resource_id,)):
        raise HTTPException(404, "Resource not found")
    db.run("""INSERT INTO progress (user_id, resource_id, done, helpful) VALUES (?, ?, ?, ?)
              ON CONFLICT (user_id, resource_id) DO UPDATE SET done = excluded.done, helpful = excluded.helpful,
              updated_at = CURRENT_TIMESTAMP""",
           (user["id"], resource_id, int(body.done), None if body.helpful is None else int(body.helpful)))
    return {"ok": True}


def require_unlocked(user_id: int, profile: dict, topic_key: str) -> dict:
    step_state(user_id, topic_key)
    step = next(s for s in roadmap.view(user_id, profile)["steps"] if s["topic_key"] == topic_key)
    if step["status"] == "locked":
        raise HTTPException(400, f"Finish {', '.join(step['prereqs'])} first")
    return step


@app.get("/api/steps/{topic_key}/quiz")
def step_quiz(topic_key: str, user=Depends(current_user)):
    require_unlocked(user["id"], need_profile(user), topic_key)
    return public_questions(topic_key, list(range(len(content.topic(topic_key)["questions"]))))


@app.post("/api/steps/{topic_key}/quiz")
def submit_step_quiz(topic_key: str, body: AnswersIn, user=Depends(current_user)):
    p = need_profile(user)
    require_unlocked(user["id"], p, topic_key)
    n_q = len(content.topic(topic_key)["questions"])
    c, n = grade(body.answers, [f"{topic_key}#{i}" for i in range(n_q)])[topic_key]
    passed = c >= max(1, round(n * 2 / 3))
    db.run("INSERT OR REPLACE INTO topic_scores (user_id, topic_key, source, correct, total) VALUES (?, ?, 'step', ?, ?)",
           (user["id"], topic_key, c, n))
    db.run("UPDATE roadmap SET state = ? WHERE user_id = ? AND topic_key = ?",
           ("completed" if passed else "revise", user["id"], topic_key))
    nxt = next((s for s in roadmap.view(user["id"], p)["steps"] if s["status"] in ("available", "revise")), None)
    return {"correct": c, "total": n, "passed": passed, "next": nxt}


# ---------------------------------------------------------------- serve the built frontend (optional)

DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = os.path.join(DIST, path)
        return FileResponse(f if path and os.path.isfile(f) else os.path.join(DIST, "index.html"))
