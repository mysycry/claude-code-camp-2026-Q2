import json
import os
import sqlite3
import threading
from datetime import datetime, timezone


_LOCAL = threading.local()


def _get_conn(path):
    if not hasattr(_LOCAL, "conn") or _LOCAL.conn is None:
        _LOCAL.conn = sqlite3.connect(path)
        _LOCAL.conn.execute("PRAGMA journal_mode=WAL")
        _LOCAL.conn.execute("PRAGMA synchronous=NORMAL")
    return _LOCAL.conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rooms (
    room_id    TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    desc_hash  TEXT,
    last_seen  TEXT,
    visit_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS exits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_room  TEXT NOT NULL REFERENCES rooms(room_id),
    direction  TEXT NOT NULL,
    to_room    TEXT REFERENCES rooms(room_id),
    seen       INTEGER DEFAULT 0,
    walked     INTEGER DEFAULT 0,
    UNIQUE(from_room, direction)
);

CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id     TEXT NOT NULL REFERENCES rooms(room_id),
    entity_type TEXT NOT NULL,
    name        TEXT NOT NULL,
    count       INTEGER DEFAULT 1,
    last_seen   TEXT
);

CREATE TABLE IF NOT EXISTS player_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sightings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    TEXT NOT NULL REFERENCES rooms(room_id),
    entity_key TEXT NOT NULL,
    last_seen  TEXT
);

CREATE TABLE IF NOT EXISTS token_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    model      TEXT NOT NULL,
    provider   TEXT NOT NULL,
    input_tokens  INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    duration_ms   INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_exits_from ON exits(from_room);
CREATE INDEX IF NOT EXISTS idx_entities_room ON entities(room_id);
CREATE INDEX IF NOT EXISTS idx_token_model ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_token_created ON token_usage(created_at);
"""


class MemoryStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(os.getcwd(), "memory.db")
        self._init_schema()

    def _init_schema(self):
        conn = _get_conn(self.path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def _execute(self, sql, params=None):
        conn = _get_conn(self.path)
        if params:
            return conn.execute(sql, params)
        return conn.execute(sql)

    def record_room(self, room_id, name, desc_hash=None):
        now = datetime.now(timezone.utc).isoformat()
        existing = self._execute(
            "SELECT visit_count FROM rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
        if existing:
            self._execute(
                "UPDATE rooms SET name=?, desc_hash=?, last_seen=?, visit_count=visit_count+1 WHERE room_id=?",
                (name, desc_hash, now, room_id),
            )
        else:
            self._execute(
                "INSERT INTO rooms (room_id, name, desc_hash, last_seen, visit_count) VALUES (?, ?, ?, ?, 1)",
                (room_id, name, desc_hash, now),
            )
        self._execute(
            "INSERT OR REPLACE INTO player_state (key, value) VALUES ('current_room', ?)",
            (room_id,),
        )
        self._commit()

    def record_exit(self, from_room, direction, to_room=None):
        existing = self._execute(
            "SELECT id FROM exits WHERE from_room=? AND direction=?",
            (from_room, direction),
        ).fetchone()
        if existing:
            self._execute(
                "UPDATE exits SET seen=1, to_room=COALESCE(?, to_room) WHERE id=?",
                (to_room, existing[0]),
            )
        else:
            self._execute(
                "INSERT INTO exits (from_room, direction, to_room, seen, walked) VALUES (?, ?, ?, 1, 0)",
                (from_room, direction, to_room),
            )
        self._commit()

    def mark_exit_walked(self, from_room, direction):
        self._execute(
            "UPDATE exits SET walked=1 WHERE from_room=? AND direction=?",
            (from_room, direction),
        )
        self._commit()

    def record_entity(self, room_id, entity_type, name):
        now = datetime.now(timezone.utc).isoformat()
        existing = self._execute(
            "SELECT id FROM entities WHERE room_id=? AND entity_type=? AND name=?",
            (room_id, entity_type, name),
        ).fetchone()
        if existing:
            self._execute(
                "UPDATE entities SET count=count+1, last_seen=? WHERE id=?",
                (now, existing[0]),
            )
        else:
            self._execute(
                "INSERT INTO entities (room_id, entity_type, name, last_seen) VALUES (?, ?, ?, ?)",
                (room_id, entity_type, name, now),
            )
        self._commit()

    def current_room(self):
        row = self._execute(
            "SELECT value FROM player_state WHERE key='current_room'"
        ).fetchone()
        if row:
            return row[0]
        return None

    def room_name(self, room_id):
        row = self._execute(
            "SELECT name FROM rooms WHERE room_id=?", (room_id,)
        ).fetchone()
        return row[0] if row else None

    def exits_for(self, room_id):
        rows = self._execute(
            "SELECT direction, to_room, walked FROM exits WHERE from_room=?", (room_id,)
        ).fetchall()
        return [{"direction": r[0], "to_room": r[1], "walked": bool(r[2])} for r in rows]

    def entities_for(self, room_id):
        rows = self._execute(
            "SELECT entity_type, name, count FROM entities WHERE room_id=?", (room_id,)
        ).fetchall()
        return [{"type": r[0], "name": r[1], "count": r[2]} for r in rows]

    def frontier_exits(self):
        rows = self._execute(
            "SELECT e.direction, e.from_room, r.name "
            "FROM exits e LEFT JOIN rooms r ON e.from_room=r.room_id "
            "WHERE e.walked=0 AND e.to_room IS NULL"
        ).fetchall()
        return [{"direction": r[0], "from_room": r[1], "room_name": r[2]} for r in rows]

    def visited_count(self):
        row = self._execute("SELECT COUNT(*) FROM rooms").fetchone()
        return row[0] if row else 0

    def here_block(self):
        room_id = self.current_room()
        if not room_id:
            return ""
        name = self.room_name(room_id)
        if not name:
            return ""
        exits = self.exits_for(room_id)
        entities = self.entities_for(room_id)
        parts = [f"[here] You are in {name}."]
        if exits:
            known = [e["direction"] for e in exits]
            parts.append(f"Known exits: {', '.join(known)}.")
        if entities:
            for e in entities:
                parts.append(f"There {_is_are(e['count'])} {e['name']} here.")
        blocks = self.memory_blocks()
        if blocks:
            parts.append("")
            parts.extend(blocks)
        path_block = self.pathfinding_block()
        if path_block:
            parts.append("")
            parts.append(path_block)
        return " ".join(parts)

    def memory_blocks(self):
        blocks = []
        frontier = self.frontier_exits()
        if frontier:
            unseen = [f"{f['direction']} from {f['room_name'] or f['from_room']}" for f in frontier[:3]]
            blocks.append(f"[frontier] {len(frontier)} unexplored exit{'s' if len(frontier)!=1 else ''}: {', '.join(unseen)}.")
        visited = self.visited_count()
        if visited > 0:
            blocks.append(f"[explored] Visited {visited} room{'s' if visited!=1 else ''}.")
        return blocks

    def find_path(self, from_room, to_room, max_depth=20):
        rows = self._execute(
            "SELECT from_room, direction, to_room FROM exits WHERE to_room IS NOT NULL AND walked=1"
        ).fetchall()
        graph = {}
        for fr, direction, tr in rows:
            graph.setdefault(fr, []).append((direction, tr))
        if from_room not in graph and from_room != to_room:
            return None
        queue = [(from_room, [])]
        visited = {from_room}
        while queue:
            current, path = queue.pop(0)
            if current == to_room:
                return path
            if len(path) >= max_depth:
                continue
            for direction, neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [direction]))
        return None

    def rooms_nearby(self, room_id, max_hops=3):
        rows = self._execute(
            "SELECT from_room, direction, to_room FROM exits WHERE to_room IS NOT NULL AND walked=1"
        ).fetchall()
        graph = {}
        for fr, direction, tr in rows:
            graph.setdefault(fr, []).append((direction, tr))
            graph.setdefault(tr, []).append((_reverse_dir(direction), fr))
        result = {}
        queue = [(room_id, [])]
        visited = {room_id}
        while queue:
            current, path = queue.pop(0)
            if len(path) > 0:
                name = self.room_name(current)
                if name:
                    result[name] = path
                if len(path) >= max_hops:
                    continue
            for direction, neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [direction]))
        return result

    def pathfinding_block(self):
        room_id = self.current_room()
        if not room_id:
            return ""
        name = self.room_name(room_id)
        if not name:
            return ""
        nearby = self.rooms_nearby(room_id, max_hops=3)
        if not nearby:
            return ""
        lines = []
        for dest_name, path in nearby.items():
            if dest_name == name:
                continue
            arrows = " → ".join(path)
            lines.append(f"{dest_name}: {arrows}")
        if not lines:
            return ""
        return f"[paths] From here: {' | '.join(lines[:5])}."

    def _commit(self):
        _get_conn(self.path).commit()

    def record_token_usage(self, model, provider, input_tokens, output_tokens, duration_ms=0):
        self._execute(
            "INSERT INTO token_usage (model, provider, input_tokens, output_tokens, duration_ms) VALUES (?, ?, ?, ?, ?)",
            (model, provider, int(input_tokens or 0), int(output_tokens or 0), int(duration_ms or 0)),
        )
        self._commit()

    def token_usage_stats(self):
        rows = self._execute(
            "SELECT model, provider, COUNT(*) as calls, "
            "SUM(input_tokens) as total_input, SUM(output_tokens) as total_output, "
            "SUM(duration_ms) as total_duration "
            "FROM token_usage GROUP BY model, provider ORDER BY total_input + total_output DESC"
        ).fetchall()
        return [{"model": r[0], "provider": r[1], "calls": r[2],
                  "total_input": r[3], "total_output": r[4],
                  "total_tokens": (r[3] or 0) + (r[4] or 0),
                  "total_duration_ms": r[5]} for r in rows]

    def token_usage_raw(self, limit=50):
        rows = self._execute(
            "SELECT model, provider, input_tokens, output_tokens, duration_ms, created_at "
            "FROM token_usage ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"model": r[0], "provider": r[1], "input_tokens": r[2],
                  "output_tokens": r[3], "duration_ms": r[4], "created_at": r[5]} for r in rows]

    def close(self):
        conn = _get_conn(self.path)
        conn.commit()
        conn.close()
        _LOCAL.conn = None


def _is_are(count):
    return "is" if count == 1 else "are"

_REVERSE_DIR = {
    "north": "south", "south": "north",
    "east": "west", "west": "east",
    "up": "down", "down": "up",
}


def _reverse_dir(d):
    return _REVERSE_DIR.get(d, d)
