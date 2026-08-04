import json
import os
import time

from agents.base import SubAgent
from agents.bulletin import post_player_snapshot
from agents.client import connect, make_client, send, wake_and_stand
from agents.mudparse import classify_entity, extract_health, parse_room_block

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "rooms_cache.json")

DIRS = {"n": "north", "e": "east", "s": "south", "w": "west", "u": "up", "d": "down"}
OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e", "u": "d", "d": "u"}
EXIT_ORDER = ["n", "e", "s", "w", "u", "d"]


def _load_cache():
    if not os.path.isfile(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(rooms):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(rooms, f, indent=2)


class MapAgent(SubAgent):
    name = "map_agent"
    description = (
        "Explores the MUD from the current room, builds a room graph, and reports "
        "the best hunting spots (rooms with the most monsters). "
        "Options: action='explore' (bounded DFS) or action='hunting_spots' "
        "(report known spots without moving)."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "'explore' to walk the area, 'hunting_spots' to report known spots",
        },
        "max_rooms": {
            "type": "integer",
            "description": "Maximum rooms to visit before stopping (default: 25)",
        },
    }

    def run(self, **kwargs):
        action = kwargs.get("action") or "explore"
        max_rooms = int(kwargs.get("max_rooms") or 25)

        if action == "hunting_spots":
            return self._hunting_spots()

        client = make_client(session="squad_map")
        connect(client)
        try:
            send(client, "stand")
            rooms, order = self._explore(client, max_rooms)
            _save_cache(rooms)
            best = max(rooms.values(), key=lambda r: len(r["mobs"]), default=None)
            post_player_snapshot(
                location=order[0] if order else None,
                destination=best["name"] if best else None,
                note=f"Map explored {len(order)} rooms, best spot: {best['name'] if best else 'none'}",
            )
            return self._report(rooms, order)
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    def _explore(self, client, max_rooms):
        """DFS with backtracking. Returns (rooms, order)."""
        rooms = {}
        order = []
        visited = set()

        def add_current(name, parsed):
            rooms[name] = {
                "name": name,
                "exits": {e["direction"]: e["open"] for e in parsed["exits"]},
                "mobs": self._mobs(parsed),
                "items": self._items(parsed),
            }
            visited.add(name)
            order.append(name)

        def recover_if_needed():
            out = wake_and_stand(client)
            vitals = extract_health(out)
            if vitals and vitals["mv"] < 15:
                send(client, "sleep")
                time.sleep(15)
                send(client, "wake")
                send(client, "stand")

        # entry: current position
        start = parse_room_block(wake_and_stand(client))
        if not start:
            return rooms, order
        add_current(start["name"], start)

        # DFS stack entries: (room_name, list_of_dirs_to_backtrack_to_start, next_exit_index)
        stack = [(start["name"], [], 0)]

        while stack and len(order) < max_rooms:
            recover_if_needed()
            name, back_path, idx = stack[-1]
            room = rooms[name]
            exits = [d for d in EXIT_ORDER if d in room["exits"] and room["exits"][d]]

            if idx < len(exits):
                stack[-1] = (name, back_path, idx + 1)
                direction = exits[idx]
                out = send(client, DIRS[direction])
                parsed = parse_room_block(out)
                if not parsed:
                    continue
                new_name = parsed["name"]
                enter_dir = OPPOSITE[direction]
                if new_name in visited:
                    # loop or known room: step back immediately
                    send(client, DIRS[enter_dir])
                    continue
                add_current(new_name, parsed)
                if len(order) >= max_rooms:
                    # done exploring: backtrack along the path taken so far
                    new_back = back_path + [enter_dir]
                    for d in reversed(new_back):
                        send(client, DIRS[d])
                    break
                stack.append((new_name, back_path + [enter_dir], 0))
            else:
                # all exits of this room processed: backtrack to parent
                stack.pop()
                if stack:
                    send(client, DIRS[back_path[-1]])

        # return to start room (stack is empty when DFS finishes)
        send(client, "look")
        return rooms, order

    def _mobs(self, parsed):
        return [e for e in parsed["entities"] if classify_entity(e) == "mob"]

    def _items(self, parsed):
        return [e for e in parsed["entities"] if classify_entity(e) == "item"]

    def _hunting_spots(self):
        rooms = _load_cache()
        if not rooms:
            client = make_client(session="squad_map")
            connect(client)
            try:
                send(client, "stand")
                rooms, order = self._explore(client, 15)
                _save_cache(rooms)
            finally:
                try:
                    client.disconnect()
                except Exception:
                    pass
        return self._spots_report(rooms)

    def _spots_report(self, rooms):
        scoring = sorted(rooms.values(), key=lambda r: len(r["mobs"]), reverse=True)
        lines = [f"== Hunting spots ({len(rooms)} rooms known) =="]
        for r in scoring[:8]:
            lines.append(
                f"  {r['name']}: {len(r['mobs'])} mob(s), exits: {''.join(r['exits'])}"
            )
        if not rooms:
            lines.append("  (no rooms explored yet — run action='explore' first)")
        lines.append("RESULT: OK")
        return "\n".join(lines)

    def _report(self, rooms, order):
        lines = [f"== Map exploration: {len(order)} rooms =="]
        for name in order:
            r = rooms[name]
            lines.append(f"  {name} [exits {''.join(r['exits'])}] mobs={len(r['mobs'])}")
        lines.append("-- hunting spots --")
        scoring = sorted(rooms.values(), key=lambda r: len(r["mobs"]), reverse=True)
        for r in scoring[:8]:
            lines.append(f"  {r['name']}: {len(r['mobs'])} mob(s)")
        lines.append("RESULT: OK")
        return "\n".join(lines)


def register(registry):
    from agents.base import register_subagents

    register_subagents(registry, [MapAgent()])
