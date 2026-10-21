"""Personalised roadmap: goal -> required topics (prerequisite closure) -> topological order,
skipping topics the learner already knows (full marks in the skill check)."""

from app import db
from app.content import domains

DONE = ("skipped", "completed")


def required_topics(domain: str, goal_id: str) -> list[str]:
    d = domains()[domain]
    goal = next(g for g in d["goals"] if g["id"] == goal_id)
    need, stack = set(), list(goal["targets"])
    while stack:
        t = stack.pop()
        if t not in need:
            need.add(t)
            stack.extend(d["topic_map"][t]["prereqs"])
    return topo_order(domain, need)


def topo_order(domain: str, need: set) -> list[str]:
    """Kahn's algorithm; among ready topics, easier first, then file order."""
    d = domains()[domain]
    file_pos = {t["id"]: i for i, t in enumerate(d["topics"])}
    indeg = {t: sum(p in need for p in d["topic_map"][t]["prereqs"]) for t in need}
    order = []
    ready = [t for t in need if indeg[t] == 0]
    while ready:
        ready.sort(key=lambda t: (d["topic_map"][t]["difficulty"], file_pos[t]))
        t = ready.pop(0)
        order.append(t)
        for u in need:
            if t in d["topic_map"][u]["prereqs"]:
                indeg[u] -= 1
                if indeg[u] == 0:
                    ready.append(u)
    return order


def build(user_id: int, domain: str, goal_id: str, skill: dict):
    """skill = {topic_id: (correct, total)}. Writes the roadmap table."""
    db.run("DELETE FROM roadmap WHERE user_id = ?", (user_id,))
    seq = []
    for pos, tid in enumerate(required_topics(domain, goal_id)):
        c, n = skill.get(tid, (0, 1))
        seq.append((user_id, f"{domain}:{tid}", pos, "skipped" if n and c == n else "pending"))
    db.run_many("INSERT INTO roadmap (user_id, topic_key, position, state) VALUES (?, ?, ?, ?)", seq)


def view(user_id: int, profile: dict) -> dict:
    d = domains()[profile["domain"]]
    steps = db.rows("SELECT topic_key, position, state FROM roadmap WHERE user_id = ? ORDER BY position", (user_id,))
    scores = {(r["topic_key"], r["source"]): r for r in
              db.rows("SELECT topic_key, source, correct, total FROM topic_scores WHERE user_id = ?", (user_id,))}
    state = {s["topic_key"]: s["state"] for s in steps}
    out, total_h, left_h = [], 0.0, 0.0
    for s in steps:
        tid = s["topic_key"].split(":", 1)[1]
        t = d["topic_map"][tid]
        sk = scores.get((s["topic_key"], "skill"))
        partial = sk and 0 < sk["correct"] < sk["total"]
        hours = round(t["hours"] * (0.6 if partial else 1.0), 1)
        locked = s["state"] not in DONE and any(
            state.get(f"{profile['domain']}:{p}", "skipped") not in DONE for p in t["prereqs"])
        status = "locked" if locked else ("available" if s["state"] == "pending" else s["state"])
        if s["state"] != "skipped":
            total_h += hours
            if s["state"] != "completed":
                left_h += hours
        st = scores.get((s["topic_key"], "step"))
        out.append({
            "topic_key": s["topic_key"], "name": t["name"], "position": s["position"] + 1,
            "status": status, "difficulty": t["difficulty"], "hours": hours,
            "weeks": round(hours / profile["hours_per_week"], 1),
            "prereqs": [d["topic_map"][p]["name"] for p in t["prereqs"]],
            "skill_score": f"{sk['correct']}/{sk['total']}" if sk else None,
            "step_score": f"{st['correct']}/{st['total']}" if st else None,
        })
    counted = [o for o in out if o["status"] != "skipped"]
    done = sum(o["status"] == "completed" for o in counted)
    return {
        "domain": d["name"], "goal": next(g["name"] for g in d["goals"] if g["id"] == profile["goal"]),
        "steps": out, "progress_pct": round(100 * done / len(counted)) if counted else 100,
        "total_hours": round(total_h, 1), "remaining_hours": round(left_h, 1),
        "remaining_weeks": round(left_h / profile["hours_per_week"], 1),
    }
