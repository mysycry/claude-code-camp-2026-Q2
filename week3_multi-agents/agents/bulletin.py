"""Bulletin board: a shared SQLite store the manager/agents write to and the
memory HTTP server (port 9876) serves to the Grafana dashboard."""

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir,
    "memory",
    "memory_bench.db",
)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS player_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS player_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            kind TEXT NOT NULL,
            message TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


def set_state(**fields):
    conn = _connect()
    try:
        for key, value in fields.items():
            if value is None:
                continue
            conn.execute(
                "INSERT INTO player_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )
        conn.commit()
    finally:
        conn.close()


def get_state():
    conn = _connect()
    try:
        rows = conn.execute("SELECT key, value FROM player_state").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


def del_state(*keys):
    conn = _connect()
    try:
        for key in keys:
            conn.execute("DELETE FROM player_state WHERE key=?", (key,))
        conn.commit()
    finally:
        conn.close()


def log_event(kind, message):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO player_events (ts, kind, message) VALUES (datetime('now'), ?, ?)",
            (kind, message),
        )
        conn.commit()
    finally:
        conn.close()


def recent_events(limit=50):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, ts, kind, message FROM player_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def post_player_snapshot(score=None, location=None, kill=None, note=None, destination=None):
    """Convenience: write a full snapshot of the player's current state."""
    fields = {}
    if score:
        for k, v in score.items():
            fields[f"score_{k}"] = v
        pct = {}
        if score.get("max_hp"):
            pct["hp"] = round(100.0 * score["hp"] / score["max_hp"])
        if score.get("max_mana"):
            pct["mana"] = round(100.0 * score["mana"] / score["max_mana"])
        if score.get("max_mv"):
            pct["mv"] = round(100.0 * score["mv"] / score["max_mv"])
        if score.get("xp") is not None and score.get("xp_next"):
            pct["xp"] = round(100.0 * score["xp"] / (score["xp"] + score["xp_next"]))
        for k, v in pct.items():
            fields[f"pct_{k}"] = v
    if location:
        fields["location"] = location
        fields["current_room"] = hashlib.md5(location.encode()).hexdigest()[:16]
        log_event("nav", f"At: {location}")
    if kill:
        fields["last_kill"] = kill
        log_event("kill", f"Slain: {kill}")
    if destination:
        fields["destination"] = destination
        log_event("nav", f"Heading to: {destination}")
    if note:
        log_event("note", note)
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_state(**fields)
