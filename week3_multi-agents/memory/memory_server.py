import json
import os
import sqlite3
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


PORT = 9876
DB_PATH = os.path.join(os.path.dirname(__file__), "memory_bench.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rooms (room_id TEXT PRIMARY KEY, name TEXT NOT NULL, desc_hash TEXT, last_seen TEXT, visit_count INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS exits (id INTEGER PRIMARY KEY AUTOINCREMENT, from_room TEXT NOT NULL, direction TEXT NOT NULL, to_room TEXT, seen INTEGER DEFAULT 0, walked INTEGER DEFAULT 0, UNIQUE(from_room, direction));
        CREATE TABLE IF NOT EXISTS entities (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT NOT NULL, entity_type TEXT NOT NULL, name TEXT NOT NULL, count INTEGER DEFAULT 1, last_seen TEXT);
        CREATE TABLE IF NOT EXISTS player_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS player_events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT (datetime('now')), kind TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sightings (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT NOT NULL, entity_key TEXT NOT NULL, last_seen TEXT);
        CREATE TABLE IF NOT EXISTS token_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT NOT NULL, provider TEXT NOT NULL, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')));
    """)
    conn.commit()
    return conn


class Handler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _html(self, text, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(text.encode())

    def _parse_qs(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/rooms":
            self._handle_rooms()
        elif path == "/exits":
            self._handle_exits()
        elif path == "/stats":
            self._handle_stats()
        elif path == "/player-state":
            self._handle_player_state()
        elif path == "/player-events":
            self._handle_player_events()
        elif path == "/frontier":
            self._handle_frontier()
        elif path == "/api":
            self._handle_api_list()
        elif path == "/token-usage":
            self._handle_token_usage()
        elif path == "/token-usage/raw":
            self._handle_token_usage_raw()
        elif path == "/world/rooms":
            self._handle_world_rooms()
        elif path == "/world/exits":
            self._handle_world_exits()
        elif path == "/world/zones":
            self._handle_world_zones()
        elif path == "/world/mobs":
            self._handle_world_mobs()
        elif path == "/world/shops":
            self._handle_world_shops()
        elif path == "/world/counts":
            self._handle_world_counts()
        elif path == "/world/summary":
            self._handle_world_summary()
        elif path == "" or path == "/":
            self._handle_index()
        else:
            self._json({"error": "not found"}, 404)

    def _handle_rooms(self):
        conn = _get_conn()
        rows = conn.execute(
            "SELECT room_id, name, visit_count, last_seen FROM rooms ORDER BY visit_count DESC"
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_exits(self):
        conn = _get_conn()
        rows = conn.execute(
            "SELECT e.direction, e.from_room, e.to_room, e.walked, "
            "COALESCE(fr.name, '?') AS from_name, "
            "COALESCE(tr.name, '?') AS to_name "
            "FROM exits e "
            "LEFT JOIN rooms fr ON e.from_room = fr.room_id "
            "LEFT JOIN rooms tr ON e.to_room = tr.room_id "
            "ORDER BY e.from_room, e.direction"
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_player_state(self):
        conn = _get_conn()
        rows = conn.execute("SELECT key, value FROM player_state").fetchall()

        def _coerce(v):
            try:
                return int(v)
            except ValueError:
                try:
                    return float(v)
                except ValueError:
                    return v

        self._json({r["key"]: _coerce(r["value"]) for r in rows})

    def _handle_player_events(self):
        conn = _get_conn()
        params = self._parse_qs()
        limit = int(params.get("limit", [50])[0])
        rows = conn.execute(
            "SELECT id, ts, kind, message FROM player_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_stats(self):
        conn = _get_conn()
        room_count = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        exit_count = conn.execute("SELECT COUNT(*) FROM exits").fetchone()[0]
        frontier = conn.execute(
            "SELECT COUNT(*) FROM exits WHERE walked=0 AND to_room IS NULL"
        ).fetchone()[0]
        walked = conn.execute("SELECT COUNT(*) FROM exits WHERE walked=1").fetchone()[0]
        current_room_id = conn.execute(
            "SELECT value FROM player_state WHERE key='current_room'"
        ).fetchone()
        current_name = None
        if current_room_id:
            row = conn.execute(
                "SELECT name FROM rooms WHERE room_id=?", (current_room_id[0],)
            ).fetchone()
            current_name = row[0] if row else None
        location_row = conn.execute(
            "SELECT value FROM player_state WHERE key='location'"
        ).fetchone()
        live_location = location_row[0] if location_row else None
        if live_location:
            current_name = live_location
        world_counts = {}
        for table in ("world_rooms", "world_exits", "world_mobs", "world_objects", "world_zones", "world_shops"):
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            world_counts[table] = row[0] if row else 0
        self._json({
            "rooms_explored": room_count,
            "total_exits": exit_count,
            "frontier_exits": frontier,
            "walked_exits": walked,
            "current_room": current_room_id[0] if current_room_id else None,
            "current_room_name": current_name,
            **world_counts,
        })

    def _handle_token_usage(self):
        conn = _get_conn()
        rows = conn.execute(
            "SELECT model, provider, COUNT(*) as calls, "
            "SUM(input_tokens) as total_input, SUM(output_tokens) as total_output, "
            "SUM(input_tokens) + SUM(output_tokens) as total_tokens, "
            "SUM(duration_ms) as total_duration "
            "FROM token_usage GROUP BY model, provider ORDER BY total_tokens DESC"
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_token_usage_raw(self):
        conn = _get_conn()
        import urllib.parse
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        limit = int(params.get("limit", [50])[0])
        rows = conn.execute(
            "SELECT model, provider, input_tokens, output_tokens, duration_ms, created_at "
            "FROM token_usage ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_frontier(self):
        conn = _get_conn()
        rows = conn.execute(
            "SELECT e.direction, e.from_room, r.name AS room_name "
            "FROM exits e LEFT JOIN rooms r ON e.from_room = r.room_id "
            "WHERE e.walked=0 AND e.to_room IS NULL"
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_api_list(self):
        self._json({
            "endpoints": {
                "/rooms": "All known (explored) rooms",
                "/exits": "All known (explored) exits",
                "/stats": "Summary statistics",
                "/frontier": "Unexplored exits",
                "/token-usage": "Token usage aggregated by model",
                "/token-usage/raw": "Raw token usage events (?limit=N)",
                "/world/rooms": "All world map rooms (?zone=N)",
                "/world/exits": "All world map exits (?room=N)",
                "/world/zones": "All zones with mob level ranges",
                "/world/mobs": "All mobs (?min_level=N&max_level=N)",
                "/world/shops": "All shops",
                "/world/counts": "World data counts only",
                "/world/summary": "World data counts + level distribution",
            }
        })

    def _handle_world_rooms(self):
        conn = _get_conn()
        params = self._parse_qs()
        zone = params.get("zone", [None])[0]
        if zone:
            rows = conn.execute(
                "SELECT vnum, name, zone_number, sector_type FROM world_rooms WHERE zone_number=? ORDER BY vnum",
                (int(zone),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT vnum, name, zone_number, sector_type FROM world_rooms ORDER BY vnum"
            ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_world_exits(self):
        conn = _get_conn()
        params = self._parse_qs()
        room = params.get("room", [None])[0]
        if room:
            rows = conn.execute(
                "SELECT we.from_room, we.dir_name, we.room_linked, we.door_flag, "
                "COALESCE(wr.name, '?') AS to_name "
                "FROM world_exits we "
                "LEFT JOIN world_rooms wr ON we.room_linked = wr.vnum "
                "WHERE we.from_room=? ORDER BY we.direction",
                (int(room),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT we.from_room, we.dir_name, we.room_linked, we.door_flag, "
                "COALESCE(wr.name, '?') AS to_name "
                "FROM world_exits we "
                "LEFT JOIN world_rooms wr ON we.room_linked = wr.vnum "
                "LIMIT 500"
            ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_world_zones(self):
        conn = _get_conn()
        rows = conn.execute("""
            SELECT z.vnum, z.name, z.bottom_room, z.top_room,
                   COALESCE(MIN(wm.level), 0) as min_level,
                   COALESCE(MAX(wm.level), 0) as max_level,
                   COUNT(DISTINCT zms.mob_vnum) as mob_count,
                   (SELECT COUNT(*) FROM world_rooms wr2 WHERE wr2.zone_number = z.vnum) as room_count
            FROM world_zones z
            LEFT JOIN zone_mob_spawns zms ON zms.zone_vnum = z.vnum
            LEFT JOIN world_mobs wm ON wm.vnum = zms.mob_vnum
            GROUP BY z.vnum ORDER BY z.vnum
        """).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_world_mobs(self):
        conn = _get_conn()
        params = self._parse_qs()
        min_lvl = int(params.get("min_level", [1])[0])
        max_lvl = int(params.get("max_level", [99])[0])
        rows = conn.execute(
            "SELECT vnum, short_desc, level, gold, xp, alignment, aggro, "
            "hp_dice, damage_dice, flags "
            "FROM world_mobs WHERE level >= ? AND level <= ? ORDER BY level, vnum",
            (min_lvl, max_lvl),
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_world_shops(self):
        conn = _get_conn()
        rows = conn.execute(
            "SELECT ws.vnum, ws.shopkeeper_mob, ws.objects, ws.sell_rate, ws.buy_rate, "
            "ws.buy_types, ws.rooms, ws.trades_with, "
            "COALESCE(wm.short_desc, '?') AS shopkeeper_name, "
            "COALESCE(wr.name, '?') AS room_name "
            "FROM world_shops ws "
            "LEFT JOIN world_mobs wm ON wm.vnum = ws.shopkeeper_mob "
            "LEFT JOIN world_rooms wr ON wr.vnum = CAST(ws.rooms AS INTEGER) "
            "ORDER BY ws.vnum"
        ).fetchall()
        self._json([dict(r) for r in rows])

    def _handle_world_counts(self):
        conn = _get_conn()
        result = {}
        for table in ("world_rooms", "world_exits", "world_mobs", "world_objects", "world_zones", "world_shops"):
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            result[table] = row[0] if row else 0
        self._json(result)

    def _handle_world_summary(self):
        conn = _get_conn()
        result = {}
        for table in ("world_rooms", "world_exits", "world_mobs", "world_objects", "world_zones", "world_shops"):
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            result[table] = row[0] if row else 0
        lvl_dist = conn.execute(
            "SELECT level, COUNT(*) as count FROM world_mobs GROUP BY level ORDER BY level"
        ).fetchall()
        result["level_distribution"] = [dict(r) for r in lvl_dist]
        self._json(result)

    def _handle_index(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Boukensha Memory</title>
<style>
body{font-family:system-ui,sans-serif;max-width:960px;margin:2em auto;padding:0 1em;background:#111;color:#e0e0e0}
h1{color:#7c3aed}
h2{color:#a78bfa;margin-top:2em}
table{width:100%;border-collapse:collapse;margin:1em 0}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid #333}
th{color:#9ca3af;font-size:.85em;text-transform:uppercase}
td{font-family:monospace}
.room-tag{display:inline-block;background:#1e1b4b;color:#a78bfa;padding:2px 8px;border-radius:4px;font-family:monospace;font-size:.85em}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.stat-card{background:#1a1a2e;border:1px solid #2d2d4e;border-radius:8px;padding:16px;text-align:center}
.stat-card .value{font-size:2em;font-weight:700;color:#7c3aed}
.stat-card .label{font-size:.8em;color:#9ca3af;margin-top:4px}
.frontier-item{background:#1a1a2e;border:1px solid #2d2d4e;border-radius:6px;padding:8px 12px;margin:4px 0;font-family:monospace}
</style></head>
<body>
<h1>Boukensha Memory</h1>
<div id="stats" class="stat-grid"></div>
<h2>Rooms</h2>
<table><thead><tr><th>Name</th><th>Room ID</th><th>Visits</th><th>Last Seen</th></tr></thead><tbody id="rooms"></tbody></table>
<h2>Exits</h2>
<table><thead><tr><th>From</th><th>Dir</th><th>To</th><th>Walked</th></tr></thead><tbody id="exits"></tbody></table>
<h2>Frontier (unexplored)</h2>
<div id="frontier"></div>
<h2>Token Usage</h2>
<table><thead><tr><th>Model</th><th>Provider</th><th>Calls</th><th>Input Tokens</th><th>Output Tokens</th><th>Total Tokens</th></tr></thead><tbody id="token-usage"></tbody></table>
<script>
async function load(){
 const [rooms,exits,stats,frontier,tokens]=await Promise.all([
  fetch('/rooms').then(r=>r.json()),
  fetch('/exits').then(r=>r.json()),
  fetch('/stats').then(r=>r.json()),
  fetch('/frontier').then(r=>r.json()),
  fetch('/token-usage').then(r=>r.json()),
 ]);
 document.getElementById('stats').innerHTML=[
  {label:'Rooms Explored',value:stats.rooms_explored},
  {label:'Frontier Exits',value:stats.frontier_exits},
  {label:'Walked Exits',value:stats.walked_exits},
  {label:'Current Room',value:stats.current_room_name||stats.current_room||'—'},
 ].map(s=>'<div class="stat-card"><div class="value">'+s.value+'</div><div class="label">'+s.label+'</div></div>').join('');
 document.getElementById('rooms').innerHTML=rooms.map(r=>'<tr><td>'+r.name+'</td><td><span class="room-tag">'+r.room_id+'</span></td><td>'+r.visit_count+'</td><td>'+(r.last_seen||'')+'</td></tr>').join('');
 document.getElementById('exits').innerHTML=exits.map(e=>'<tr><td>'+e.from_name+' <span class="room-tag">'+e.from_room.slice(0,8)+'</span></td><td>'+e.direction+'</td><td>'+e.to_name+' <span class="room-tag">'+(e.to_room||'').slice(0,8)+'</span></td><td>'+(e.walked?'yes':'no')+'</td></tr>').join('');
 document.getElementById('frontier').innerHTML=frontier.length?frontier.map(f=>'<div class="frontier-item">'+f.direction+' from '+f.room_name+'</div>').join(''):'<p style="color:#6b7280">None — all exits explored!</p>';
 document.getElementById('token-usage').innerHTML=tokens.map(t=>'<tr><td>'+t.model+'</td><td>'+t.provider+'</td><td>'+t.calls+'</td><td>'+(t.total_input||0).toLocaleString()+'</td><td>'+(t.total_output||0).toLocaleString()+'</td><td>'+((t.total_input||0)+(t.total_output||0)).toLocaleString()+'</td></tr>').join('');
}
load()
</script>
</body></html>"""
        self._html(html)

    def log_message(self, format, *args):
        sys.stderr.write(f"[memory_server] {args[0]} {args[1]} {args[2]}\n")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True


def main():
    db_msg = f"DB: {DB_PATH}" if os.path.exists(DB_PATH) else "DB: (no file yet — run a benchmark first)"
    print(f"[memory_server] http://localhost:{PORT}  {db_msg}", file=sys.stderr)
    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
