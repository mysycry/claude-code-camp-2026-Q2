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

-- World data (static knowledge from parsed MUD files)
CREATE TABLE IF NOT EXISTS world_zones (
    vnum INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    bottom_room INTEGER,
    top_room INTEGER
);
CREATE TABLE IF NOT EXISTS world_rooms (
    vnum INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    zone_number INTEGER,
    sector_type TEXT,
    flags TEXT
);
CREATE TABLE IF NOT EXISTS world_exits (
    from_room INTEGER NOT NULL,
    direction INTEGER NOT NULL,
    dir_name TEXT NOT NULL,
    room_linked INTEGER,
    door_flag INTEGER DEFAULT 0,
    PRIMARY KEY(from_room, direction)
);
CREATE TABLE IF NOT EXISTS world_mobs (
    vnum INTEGER PRIMARY KEY,
    aliases TEXT,
    short_desc TEXT,
    long_desc TEXT,
    level INTEGER DEFAULT 1,
    thac0 INTEGER DEFAULT 0,
    armor_class INTEGER DEFAULT 0,
    hp_dice TEXT,
    damage_dice TEXT,
    gold INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    alignment INTEGER DEFAULT 0,
    aggro INTEGER DEFAULT 0,
    flags TEXT
);
CREATE TABLE IF NOT EXISTS world_objects (
    vnum INTEGER PRIMARY KEY,
    aliases TEXT,
    short_desc TEXT,
    long_desc TEXT,
    obj_type TEXT,
    wear_flags TEXT,
    weight INTEGER DEFAULT 0,
    cost INTEGER DEFAULT 0,
    rent INTEGER DEFAULT 0,
    values_str TEXT,
    affects TEXT
);
CREATE TABLE IF NOT EXISTS zone_mob_spawns (
    zone_vnum INTEGER NOT NULL,
    mob_vnum INTEGER NOT NULL,
    room_vnum INTEGER,
    max_count INTEGER DEFAULT 1,
    PRIMARY KEY(zone_vnum, mob_vnum, room_vnum)
);
CREATE TABLE IF NOT EXISTS zone_object_spawns (
    zone_vnum INTEGER NOT NULL,
    obj_vnum INTEGER NOT NULL,
    room_vnum INTEGER,
    max_count INTEGER DEFAULT 1,
    PRIMARY KEY(zone_vnum, obj_vnum, room_vnum)
);
CREATE TABLE IF NOT EXISTS world_shops (
    vnum INTEGER PRIMARY KEY,
    shopkeeper_mob INTEGER,
    objects TEXT,
    sell_rate REAL,
    buy_rate REAL,
    buy_types TEXT,
    rooms TEXT,
    trades_with TEXT
);
CREATE INDEX IF NOT EXISTS idx_world_rooms_zone ON world_rooms(zone_number);
CREATE INDEX IF NOT EXISTS idx_world_exits_from ON world_exits(from_room);
CREATE INDEX IF NOT EXISTS idx_world_mobs_level ON world_mobs(level);
CREATE INDEX IF NOT EXISTS idx_zone_mob_spawns_zone ON zone_mob_spawns(zone_vnum);
CREATE INDEX IF NOT EXISTS idx_zone_mob_spawns_mob ON zone_mob_spawns(mob_vnum);
CREATE INDEX IF NOT EXISTS idx_zone_mob_spawns_room ON zone_mob_spawns(room_vnum);
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

    def record_room(self, room_id, name, desc_hash=None, current=False):
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
        if current:
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
            "SELECT e.direction, e.to_room, e.walked, r.name "
            "FROM exits e LEFT JOIN rooms r ON e.to_room = r.room_id "
            "WHERE e.from_room=?", (room_id,)
        ).fetchall()
        return [{"direction": r[0], "to_room": r[1], "walked": bool(r[2]), "dest_name": r[3]} for r in rows]

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
            known = []
            for e in exits:
                if e["dest_name"]:
                    known.append(f"{e['direction']} -> {e['dest_name']}")
                else:
                    known.append(e["direction"])
            parts.append(f"Exits: {', '.join(known)}.")
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

    # ---- World data loading ----
    WORLD_DIR_NAMES = {0: "north", 1: "east", 2: "south", 3: "west", 4: "up", 5: "down"}

    def load_world_data(self, zones=None, rooms=None, exits=None,
                        mobs=None, objects=None, spawns=None, shops=None):
        conn = _get_conn(self.path)
        if zones:
            conn.executemany(
                "INSERT OR REPLACE INTO world_zones (vnum, name, bottom_room, top_room) VALUES (?, ?, ?, ?)",
                [(z["vnum"], z["name"], z.get("bottom_room"), z.get("top_room")) for z in zones],
            )
        if rooms:
            conn.executemany(
                "INSERT OR REPLACE INTO world_rooms (vnum, name, zone_number, sector_type, flags) VALUES (?, ?, ?, ?, ?)",
                [(r["vnum"], r["name"], r.get("zone_number"), r.get("sector_type"), r.get("flags")) for r in rooms],
            )
        if exits:
            conn.executemany(
                "INSERT OR REPLACE INTO world_exits (from_room, direction, dir_name, room_linked, door_flag) VALUES (?, ?, ?, ?, ?)",
                [(e["from_room"], e["direction"], self.WORLD_DIR_NAMES.get(e["direction"], "?"), e.get("room_linked"), e.get("door_flag", 0)) for e in exits],
            )
        if mobs:
            conn.executemany(
                "INSERT OR REPLACE INTO world_mobs (vnum, aliases, short_desc, long_desc, level, thac0, armor_class, hp_dice, damage_dice, gold, xp, alignment, aggro, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(m["vnum"], m.get("aliases"), m.get("short_desc"), m.get("long_desc"),
                  m.get("level", 1), m.get("thac0", 0), m.get("armor_class", 0),
                  m.get("hp_dice"), m.get("damage_dice"), m.get("gold", 0),
                  m.get("xp", 0), m.get("alignment", 0),
                  1 if "AGGRESSIVE" in (m.get("flags") or "") else 0,
                  m.get("flags")) for m in mobs],
            )
        if objects:
            conn.executemany(
                "INSERT OR REPLACE INTO world_objects (vnum, aliases, short_desc, long_desc, obj_type, wear_flags, weight, cost, rent, values_str, affects) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(o["vnum"], o.get("aliases"), o.get("short_desc"), o.get("long_desc"),
                  o.get("obj_type"), o.get("wear_flags"), o.get("weight", 0),
                  o.get("cost", 0), o.get("rent", 0), o.get("values_str"), o.get("affects")) for o in objects],
            )
        if spawns:
            conn.executemany(
                "INSERT OR REPLACE INTO zone_mob_spawns (zone_vnum, mob_vnum, room_vnum, max_count) VALUES (?, ?, ?, ?)",
                [(s["zone_vnum"], s["mob_vnum"], s.get("room_vnum"), s.get("max_count", 1)) for s in spawns],
            )
        if shops:
            conn.executemany(
                "INSERT OR REPLACE INTO world_shops (vnum, shopkeeper_mob, objects, sell_rate, buy_rate, buy_types, rooms, trades_with) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(s["vnum"], s.get("shopkeeper_mob"), s.get("objects"), s.get("sell_rate"),
                  s.get("buy_rate"), s.get("buy_types"), s.get("rooms"), s.get("trades_with")) for s in shops],
            )
        conn.commit()

    def world_has_data(self):
        row = self._execute("SELECT COUNT(*) FROM world_rooms").fetchone()
        return row and row[0] > 0

    def world_summary(self):
        rooms = self._execute("SELECT COUNT(*) FROM world_rooms").fetchone()[0]
        mobs = self._execute("SELECT COUNT(*) FROM world_mobs").fetchone()[0]
        objs = self._execute("SELECT COUNT(*) FROM world_objects").fetchone()[0]
        zones = self._execute("SELECT COUNT(*) FROM world_zones").fetchone()[0]
        shops = self._execute("SELECT COUNT(*) FROM world_shops").fetchone()[0]
        exits = self._execute("SELECT COUNT(*) FROM world_exits").fetchone()[0]
        return {"rooms": rooms, "mobs": mobs, "objects": objs,
                "zones": zones, "shops": shops, "exits": exits}

    def world_rooms_all(self, zone_number=None):
        if zone_number is not None:
            rows = self._execute(
                "SELECT vnum, name, zone_number, sector_type, flags FROM world_rooms WHERE zone_number=? ORDER BY vnum",
                (zone_number,),
            ).fetchall()
        else:
            rows = self._execute(
                "SELECT vnum, name, zone_number, sector_type, flags FROM world_rooms ORDER BY vnum"
            ).fetchall()
        return [{"vnum": r[0], "name": r[1], "zone_number": r[2], "sector_type": r[3], "flags": r[4]} for r in rows]

    def world_exits_all(self, from_room=None):
        if from_room is not None:
            rows = self._execute(
                "SELECT from_room, direction, dir_name, room_linked, door_flag FROM world_exits WHERE from_room=? ORDER BY direction",
                (from_room,),
            ).fetchall()
        else:
            rows = self._execute(
                "SELECT from_room, direction, dir_name, room_linked, door_flag FROM world_exits ORDER BY from_room, direction"
            ).fetchall()
        return [{"from_room": r[0], "direction": r[1], "dir_name": r[2], "room_linked": r[3], "door_flag": r[4]} for r in rows]

    def world_zones_all(self):
        rows = self._execute(
            "SELECT z.vnum, z.name, z.bottom_room, z.top_room, "
            "MIN(wm.level) as min_level, MAX(wm.level) as max_level, "
            "COUNT(DISTINCT zms.mob_vnum) as mob_count, "
            "COUNT(DISTINCT wr.vnum) as room_count "
            "FROM world_zones z "
            "LEFT JOIN world_rooms wr ON wr.zone_number = z.vnum "
            "LEFT JOIN zone_mob_spawns zms ON zms.zone_vnum = z.vnum "
            "LEFT JOIN world_mobs wm ON wm.vnum = zms.mob_vnum "
            "GROUP BY z.vnum ORDER BY z.vnum"
        ).fetchall()
        return [{"vnum": r[0], "name": r[1], "bottom_room": r[2], "top_room": r[3],
                  "min_level": r[4], "max_level": r[5], "mob_count": r[6], "room_count": r[7]} for r in rows]

    def world_mobs_all(self, min_level=1, max_level=99):
        rows = self._execute(
            "SELECT vnum, short_desc, level, thac0, armor_class, hp_dice, damage_dice, "
            "gold, xp, alignment, aggro, flags "
            "FROM world_mobs WHERE level >= ? AND level <= ? ORDER BY level, vnum",
            (min_level, max_level),
        ).fetchall()
        return [{"vnum": r[0], "name": r[1], "level": r[2], "thac0": r[3],
                  "armor_class": r[4], "hp_dice": r[5], "damage_dice": r[6],
                  "gold": r[7], "xp": r[8], "alignment": r[9], "aggro": r[10], "flags": r[11]} for r in rows]

    def world_mobs_for_zone(self, zone_vnum):
        rows = self._execute(
            "SELECT wm.vnum, wm.short_desc, wm.level, wm.hp_dice, wm.damage_dice, "
            "wm.gold, wm.xp, wm.aggro, zms.room_vnum, zms.max_count "
            "FROM zone_mob_spawns zms "
            "JOIN world_mobs wm ON wm.vnum = zms.mob_vnum "
            "WHERE zms.zone_vnum=? ORDER BY wm.level, wm.vnum",
            (zone_vnum,),
        ).fetchall()
        return [{"vnum": r[0], "name": r[1], "level": r[2], "hp_dice": r[3],
                  "damage_dice": r[4], "gold": r[5], "xp": r[6], "aggro": r[7],
                  "room_vnum": r[8], "max_count": r[9]} for r in rows]

    def world_shops_all(self):
        rows = self._execute(
            "SELECT vnum, shopkeeper_mob, objects, sell_rate, buy_rate, "
            "buy_types, rooms, trades_with FROM world_shops ORDER BY vnum"
        ).fetchall()
        return [{"vnum": r[0], "shopkeeper_mob": r[1], "objects": r[2],
                  "sell_rate": r[3], "buy_rate": r[4], "buy_types": r[5],
                  "rooms": r[6], "trades_with": r[7]} for r in rows]

    def world_route_to(self, from_vnum, to_vnum, max_depth=50):
        if not self.world_has_data():
            return None
        rows = self._execute(
            "SELECT from_room, dir_name, room_linked FROM world_exits WHERE room_linked IS NOT NULL"
        ).fetchall()
        graph = {}
        for fr, direction, tr in rows:
            graph.setdefault(fr, []).append((direction, tr))
        if from_vnum not in graph and from_vnum != to_vnum:
            return None
        queue = [(from_vnum, [])]
        visited = {from_vnum}
        while queue:
            current, path = queue.pop(0)
            if current == to_vnum:
                return path
            if len(path) >= max_depth:
                continue
            for direction, neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [direction]))
        return None

    def world_room_name(self, vnum):
        row = self._execute(
            "SELECT name FROM world_rooms WHERE vnum=?", (vnum,)
        ).fetchone()
        return row[0] if row else None

    def world_training_spots(self, player_level, radius=3):
        low = max(1, player_level - 3)
        high = player_level + 3
        rows = self._execute(
            "SELECT z.name as zone_name, z.vnum as zone_vnum, "
            "MIN(wm.level) as min_level, MAX(wm.level) as max_level, "
            "COUNT(DISTINCT wm.vnum) as mob_types, "
            "SUM(zms.max_count) as total_pop "
            "FROM world_zones z "
            "JOIN zone_mob_spawns zms ON zms.zone_vnum = z.vnum "
            "JOIN world_mobs wm ON wm.vnum = zms.mob_vnum "
            "WHERE wm.level >= ? AND wm.level <= ? "
            "GROUP BY z.vnum ORDER BY MIN(wm.level)",
            (low, high),
        ).fetchall()
        return [{"zone_name": r[0], "zone_vnum": r[1], "min_level": r[2],
                  "max_level": r[3], "mob_types": r[4], "total_pop": r[5]} for r in rows]

    def world_knowledge_block(self):
        if not self.world_has_data():
            return ""
        summary = self.world_summary()
        current_room_id = self.current_room()
        parts = [f"[knowledge] World map: {summary['rooms']} rooms, {summary['mobs']} mobs, {summary['zones']} zones."]
        zones = self.world_zones_all()
        low_zones = [z for z in zones if z["min_level"] and z["min_level"] <= 10]
        if low_zones:
            zone_list = [f"{z['name']} (lvl {z['min_level']}-{z['max_level']})" for z in low_zones[:5]]
            parts.append(f"Nearby zones: {' | '.join(zone_list)}.")
        nearby = self.world_training_spots(player_level=10, radius=5)
        if nearby:
            spots = [f"{s['zone_name']} (lvl {s['min_level']}-{s['max_level']})" for s in nearby[:4]]
            parts.append(f"Training: {' | '.join(spots)}.")
        return " ".join(parts)

    # ---- Knowledge block injection ----
    def full_context_block(self):
        blocks = []
        hb = self.here_block()
        if hb:
            blocks.append(hb)
        kb = self.world_knowledge_block()
        if kb:
            blocks.append(kb)
        return "\n\n".join(blocks)

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
