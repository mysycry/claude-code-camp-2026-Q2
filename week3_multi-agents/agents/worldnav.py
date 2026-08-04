import os
import sqlite3
from collections import deque

from agents.base import ROOT

DB_PATH = os.path.join(ROOT, "week3_multi-agents", "memory", "memory_bench.db")

_GRAPH = None


def _load_graph():
    """Load world_rooms/world_exits from the offline world DB (cached).

    Live-server vnums can differ from the offline DB, so routing is done by
    room NAME: find candidate vnums for a name, BFS on the offline graph, and
    return directions. The caller verifies each step against the live room.
    """
    global _GRAPH
    if _GRAPH is not None:
        return _GRAPH

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rooms = {}
    for v, n, z in cur.execute("SELECT vnum, name, zone_number FROM world_rooms"):
        rooms[v] = {"name": n, "zone": z}
    adj = {}
    for f, _d, dn, t, df in cur.execute(
        "SELECT from_room, direction, dir_name, room_linked, door_flag FROM world_exits"
    ):
        if t is not None:
            adj.setdefault(f, []).append({"dir": dn, "to": t, "door": df != 0})
    spawns = {}
    for _zv, mv, rv, _mx in cur.execute(
        "SELECT zone_vnum, mob_vnum, room_vnum, max_count FROM zone_mob_spawns"
    ):
        spawns.setdefault(rv, []).append(mv)
    mob_levels = {}
    for v, lv in cur.execute("SELECT vnum, level FROM world_mobs"):
        mob_levels[v] = lv
    con.close()

    _GRAPH = {"rooms": rooms, "adj": adj, "spawns": spawns, "mob_levels": mob_levels}
    return _GRAPH


def vnums_by_name(name):
    graph = _load_graph()
    target = (name or "").strip().lower()
    if not target:
        return []
    return [v for v, r in graph["rooms"].items() if r["name"].lower() == target]


def hunting_rooms(min_level=0, max_level=99):
    """Rooms that spawn at least one mob whose level is within [min, max]."""
    graph = _load_graph()
    levels = graph["mob_levels"]
    out = set()
    for rv, mvs in graph["spawns"].items():
        if any(min_level <= levels.get(m, 99) <= max_level for m in mvs):
            out.add(rv)
    return out


def bfs_route(start_vnum, target_vnums, max_depth=400):
    """Shortest path in directions from start to any target room.

    Returns a list of {"direction": str, "name": str, "vnum": int} steps, or
    None if unreachable. Doors are allowed but flagged via 'door'.
    """
    graph = _load_graph()
    if start_vnum not in graph["adj"]:
        if start_vnum in target_vnums:
            return []
        return None
    if start_vnum in target_vnums:
        return []

    prev = {start_vnum: None}
    pdir = {}
    pdoor = {}
    q = deque([start_vnum])
    found = None
    while q:
        cur = q.popleft()
        if cur in target_vnums:
            found = cur
            break
        for e in graph["adj"].get(cur, []):
            nxt = e["to"]
            if nxt in prev:
                continue
            prev[nxt] = cur
            pdir[nxt] = e["dir"]
            pdoor[nxt] = e["door"]
            q.append(nxt)
            if len(prev) > max_depth:
                break
        if len(prev) > max_depth:
            break

    if found is None:
        return None

    route = []
    cur = found
    while cur != start_vnum:
        route.append({
            "direction": pdir[cur],
            "name": graph["rooms"][cur]["name"],
            "vnum": cur,
            "door": pdoor.get(cur, False),
        })
        cur = prev[cur]
    route.reverse()
    return route


def route_to_nearest_hunt(start_vnum, player_level, level_band=3, prefer_open=True):
    """Route from start to the nearest room with huntable mobs.

    player_level: the character's level. Targets mobs in
    [player_level - level_band, player_level + level_band].
    Returns (route, target_vnum) or (None, None) if unreachable.
    """
    if start_vnum is None:
        return None, None
    lo = max(0, player_level - level_band)
    hi = player_level + level_band
    targets = hunting_rooms(lo, hi)
    if not targets:
        return None, None
    route = bfs_route(start_vnum, targets)
    if route is None:
        return None, None
    return route, route[-1]["vnum"] if route else start_vnum
