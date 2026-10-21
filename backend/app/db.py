"""SQLite storage: users, learner profiles, quiz scores, roadmap state, resources, progress."""

import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    goal TEXT NOT NULL,
    level TEXT NOT NULL,
    format TEXT NOT NULL,
    hours_per_week REAL NOT NULL,
    days_per_week INTEGER NOT NULL,
    likes_discussion INTEGER NOT NULL DEFAULT 0,
    cluster_id INTEGER,
    cluster_name TEXT,
    cluster_source TEXT,
    quiz_done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS topic_scores (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_key TEXT NOT NULL,
    source TEXT NOT NULL,            -- 'skill' (onboarding quiz) or 'step' (mini-quiz)
    correct INTEGER NOT NULL,
    total INTEGER NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, topic_key, source)
);
CREATE TABLE IF NOT EXISTS roadmap (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_key TEXT NOT NULL,
    position INTEGER NOT NULL,
    state TEXT NOT NULL,             -- skipped | pending | revise | completed
    PRIMARY KEY (user_id, topic_key)
);
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_key TEXT NOT NULL,
    kind TEXT NOT NULL,              -- video | article | practice
    source TEXT NOT NULL,            -- youtube | curated
    external_id TEXT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    channel TEXT,
    description TEXT,
    thumbnail TEXT,
    duration_min REAL,
    views INTEGER,
    difficulty INTEGER NOT NULL DEFAULT 2,
    UNIQUE (topic_key, url)
);
CREATE TABLE IF NOT EXISTS progress (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    done INTEGER NOT NULL DEFAULT 0,
    helpful INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, resource_id)
);
CREATE TABLE IF NOT EXISTS youtube_fetches (
    topic_key TEXT PRIMARY KEY,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    count INTEGER NOT NULL
);
"""


def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _with(fn):
    con = connect()
    try:
        with con:  # commits on success, rolls back on error
            return fn(con)
    finally:
        con.close()


def init():
    _with(lambda c: c.executescript(SCHEMA))


def rows(sql, args=()):
    return _with(lambda c: [dict(r) for r in c.execute(sql, args).fetchall()])


def one(sql, args=()):
    r = rows(sql, args)
    return r[0] if r else None


def run(sql, args=()):
    return _with(lambda c: c.execute(sql, args).lastrowid)


def run_many(sql, seq):
    _with(lambda c: c.executemany(sql, seq))
