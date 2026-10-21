"""Domain skill graphs, curated resources and the YouTube Data API video catalog.

CLI:  python -m app.content fetch            # pre-fetch videos for every topic (uses ~2.5k of the 10k daily quota)
      python -m app.content fetch web_dev    # one domain only
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from functools import lru_cache

from app import db

DOMAINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "domains")
YT_API = "https://www.googleapis.com/youtube/v3"
BEGINNER_WORDS = re.compile(r"beginner|crash course|basics|introduction|intro\b|for dummies|from scratch|in \d+ minutes|full course", re.I)
ADVANCED_WORDS = re.compile(r"advanced|deep dive|internals|under the hood|optimi[sz]|expert|masterclass", re.I)


@lru_cache
def domains() -> dict:
    out = {}
    for f in sorted(os.listdir(DOMAINS_DIR)):
        if f.endswith(".json"):
            with open(os.path.join(DOMAINS_DIR, f), encoding="utf-8") as fh:
                d = json.load(fh)
            d["topic_map"] = {t["id"]: t for t in d["topics"]}
            out[d["id"]] = d
    return out


def topic(topic_key: str) -> dict:
    dom, tid = topic_key.split(":", 1)
    return domains()[dom]["topic_map"][tid]


def infer_difficulty(title: str, default: int) -> int:
    if BEGINNER_WORDS.search(title):
        return 1
    if ADVANCED_WORDS.search(title):
        return 3
    return default


def seed_curated():
    """Insert the hand-picked docs / practice links from the domain JSON files."""
    seq = [
        (f"{d['id']}:{t['id']}", r["kind"], "curated", r["title"], r["url"], r.get("difficulty", t["difficulty"]))
        for d in domains().values() for t in d["topics"] for r in t.get("resources", [])
    ]
    db.run_many("INSERT OR IGNORE INTO resources (topic_key, kind, source, title, url, difficulty) VALUES (?, ?, ?, ?, ?, ?)", seq)


# ---------------------------------------------------------------- YouTube

def _yt(endpoint: str, **params) -> dict:
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    url = f"{YT_API}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


def iso_minutes(iso: str) -> float:
    """'PT1H2M30S' -> 62.5"""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0.0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return round(d * 1440 + h * 60 + mi + s / 60, 1)


def fetch_videos(topic_key: str, max_results: int = 15) -> int:
    """Search YouTube for a topic, pull duration + views, store videos. Returns number stored."""
    t = topic(topic_key)
    search = _yt("search", part="snippet", q=t["youtube_query"], type="video", maxResults=max_results,
                 relevanceLanguage="en", safeSearch="strict", videoEmbeddable="true")
    ids = [it["id"]["videoId"] for it in search.get("items", []) if it.get("id", {}).get("videoId")]
    if not ids:
        db.run("INSERT OR REPLACE INTO youtube_fetches (topic_key, count) VALUES (?, 0)", (topic_key,))
        return 0
    details = _yt("videos", part="snippet,contentDetails,statistics", id=",".join(ids))
    seq = []
    for v in details.get("items", []):
        mins = iso_minutes(v["contentDetails"].get("duration"))
        if mins < 4:  # skip Shorts and teasers
            continue
        sn = v["snippet"]
        thumbs = sn.get("thumbnails", {})
        thumb = (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url")
        seq.append((topic_key, "video", "youtube", v["id"], sn["title"], f"https://www.youtube.com/watch?v={v['id']}",
                    sn.get("channelTitle"), (sn.get("description") or "")[:500], thumb, mins,
                    int(v.get("statistics", {}).get("viewCount", 0)), infer_difficulty(sn["title"], t["difficulty"])))
    db.run_many("""INSERT OR IGNORE INTO resources
        (topic_key, kind, source, external_id, title, url, channel, description, thumbnail, duration_min, views, difficulty)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", seq)
    db.run("INSERT OR REPLACE INTO youtube_fetches (topic_key, count) VALUES (?, ?)", (topic_key, len(seq)))
    return len(seq)


def ensure_videos(topic_key: str) -> str | None:
    """Fetch videos for a topic on first use. Returns a warning string if videos are unavailable."""
    if db.one("SELECT 1 FROM youtube_fetches WHERE topic_key = ? AND count > 0", (topic_key,)):
        return None
    if not os.getenv("YOUTUBE_API_KEY"):
        return "YouTube videos are off: set YOUTUBE_API_KEY in backend/.env to enable them."
    try:
        return None if fetch_videos(topic_key) else "YouTube returned no videos for this topic."
    except Exception as e:  # quota exceeded, bad key, no network
        return f"Could not reach YouTube right now ({e.__class__.__name__}). Showing docs and practice links."


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    if len(sys.argv) < 2 or sys.argv[1] != "fetch":
        sys.exit(__doc__)
    db.init()
    wanted = sys.argv[2:] or list(domains())
    for dom in wanted:
        for t in domains()[dom]["topics"]:
            key = f"{dom}:{t['id']}"
            print(f"{key:32s} {fetch_videos(key)} videos")
