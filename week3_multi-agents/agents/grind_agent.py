import os
import time

from agents.base import ROOT, SubAgent
from agents.bulletin import post_player_snapshot, set_state
from agents.client import connect, make_client, send, wake_and_stand
from agents.map_agent import DIRS, EXIT_ORDER, OPPOSITE
from agents.mudparse import classify_entity, extract_health, parse_room_block, parse_score

BLOCKED_MSGS = ["can't go", "alas", "in your dreams", "too exhausted", "closed",
                "door seems to be closed"]


def _recover_until(client, attr, target, interval=3.0, timeout=45.0, command="rest"):
    """Poll H/M/V until `attr` reaches `target` (or a timeout), instead of a blind sleep."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        send(client, command)
        time.sleep(interval)
        out = wake_and_stand(client)
        vitals = extract_health(out)
        if vitals and vitals[attr] >= target:
            return True
    return False


class GrindAgent(SubAgent):
    name = "grind_agent"
    description = (
        "Explores the area around the player's current room and fights monsters "
        "to gain XP/gold/levels. Takes a target mob name and a kill budget. "
        "Returns a combat summary with level/gold/xp."
    )
    parameters = {
        "target": {
            "type": "string",
            "description": "Mob alias/name to fight (e.g. 'rat', 'goblin'). Default: any mob.",
        },
        "steps": {
            "type": "integer",
            "description": "Maximum kills before stopping (default: 3)",
        },
        "max_rooms": {
            "type": "integer",
            "description": "Maximum rooms to walk looking for fights (default: 12)",
        },
    }

    def run(self, **kwargs):
        target = (kwargs.get("target") or "").strip()
        steps = int(kwargs.get("steps") or 3)
        max_rooms = int(kwargs.get("max_rooms") or 12)

        client = make_client(session="squad_grind")
        connect(client)
        try:
            out = wake_and_stand(client)
            start = parse_room_block(out)
            if not start:
                return self._summary("Grind", [("start", False, "could not parse start room")])

            kills = 0
            fought = 0
            last_kill = ""
            visited = set()
            order = []
            start_key = self._room_key(start)
            visited.add(start_key)
            order.append(start["name"])

            # Try to pre-plan a route to the nearest hunting zone using the world DB.
            routed_rooms = self._walk_toward_hunt(client, start)
            current = routed_rooms[-1] if routed_rooms else start
            for rm in routed_rooms:
                visited.add(self._room_key(rm))
                order.append(rm["name"])

            stack = [(self._room_key(current), [], 0)]
            visited.add(self._room_key(current))

            while stack and len(order) < max_rooms and kills < steps:
                key, back_path, idx = stack[-1]
                name = self._key_name(key)
                room = self._room_info(client, name)
                if room is None:
                    stack.pop()
                    continue

                mobs = self._mobs(room, target)
                if mobs and kills < steps:
                    killed, alias = self._fight(client, mobs[0])
                    fought += 1
                    if killed:
                        kills += 1
                        last_kill = alias
                        self._loot(client)
                        self._recover_hp(client)

                exits = [d for d in EXIT_ORDER if d in room["exits"] and room["exits"][d]]
                if idx < len(exits):
                    stack[-1] = (key, back_path, idx + 1)
                    direction = exits[idx]
                    if not self._recover_mv(client):
                        continue
                    out = send(client, DIRS[direction])
                    if any(m in out.lower() for m in BLOCKED_MSGS):
                        send(client, "open " + direction)
                        out = send(client, DIRS[direction])
                    parsed = parse_room_block(out)
                    if not parsed:
                        continue
                    enter_dir = OPPOSITE[direction]
                    new_key = self._room_key(parsed)
                    if new_key in visited:
                        send(client, DIRS[enter_dir])
                        continue
                    visited.add(new_key)
                    order.append(parsed["name"])
                    if len(order) >= max_rooms or kills >= steps:
                        new_back = back_path + [enter_dir]
                        for d in reversed(new_back):
                            send(client, DIRS[d])
                        break
                    stack.append((new_key, back_path + [enter_dir], 0))
                else:
                    stack.pop()
                    if stack:
                        send(client, DIRS[back_path[-1]])

            send(client, "look")
            score = parse_score(send(client, "score"))
            post_player_snapshot(
                score=score,
                location=order[0] if order else None,
                destination=target or "any mob",
                note=f"Grind done: {kills}/{steps} kills in {len(order)} rooms",
            )
            return self._summary(
                f"Grind (target='{target or 'any'}', {kills}/{steps} kills, {len(order)} rooms)",
                [
                    ("kills", kills > 0, f"{kills} kills (fought {fought})"),
                    ("last kill", bool(last_kill), last_kill or "none"),
                    ("level", score.get("level", 0) > 0, f"level {score.get('level')}"),
                    ("xp/gold", True, f"XP={score.get('xp')} Gold={score.get('gold')}"),
                    ("location", bool(score), f"HP {score.get('hp')}/{score.get('max_hp')}"),
                ],
            )
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    @staticmethod
    def _room_key(room):
        exits = room.get("exits")
        if exits and isinstance(exits, list):
            sig = "".join(e["direction"] for e in exits if e.get("open"))
        else:
            sig = "".join(d for d in EXIT_ORDER if d in (exits or {}) and exits[d])
        return (room["name"], sig)

    @staticmethod
    def _key_name(key):
        return key[0]

    def _room_info(self, client, name):
        out = wake_and_stand(client)
        room = parse_room_block(out)
        if not (room and room["name"] == name):
            room = parse_room_block(send(client, "look"))
        if not room:
            return None
        return {
            "name": room["name"],
            "exits": {e["direction"]: e["open"] for e in room["exits"]},
            "entities": room["entities"],
        }

    def _mobs(self, room, target):
        target_l = target.lower() if target else ""
        out = []
        for e in room["entities"]:
            if classify_entity(e) != "mob":
                continue
            if target_l and target_l not in e.lower():
                continue
            out.append(e)
        return out

    def _mob_alias(self, mob):
        import re

        text = re.split(
            r"\s+(?:is\s+)?(?:standing|sitting|resting|sleeping|crouching|here|waiting|looking|guarding)\b",
            mob,
        )[0]
        text = re.sub(r"\b(?:has (?:just )?arrived|arrives|has gotten|is lurking)\b.*$", "", text)
        text = re.sub(r"^\s*(?:You\s+see\s+)?(?:a\s+|an\s+|the\s+)?", "", text)
        words = [w.strip(".,'()\"") for w in text.split() if w.strip(".,'()\"")]
        words = [w for w in words if w.lower() not in ("a", "an", "the")]
        if not words:
            return mob.split(" is ")[0].strip()
        return " ".join(words[:3])

    def _fight(self, client, mob):
        alias = self._mob_alias(mob)
        send(client, f"kill {alias}")
        for _ in range(40):
            time.sleep(2)
            out = wake_and_stand(client)
            if "You are dead" in out:
                return False, alias
            if "You have slain" in out or "for the kill" in out or "receive" in out:
                return True, alias
            room = parse_room_block(out)
            if room:
                fighting = any("fighting" in e for e in room["entities"])
                still_present = any(alias.split()[0].lower() in e.lower() for e in room["entities"])
                if not fighting and not still_present:
                    return True, alias
            if "flee" in out.lower():
                send(client, "flee")
                return False, alias
        return False, alias

    def _loot(self, client):
        send(client, "get all corpse")
        send(client, "get all")
        send(client, "wear all")

    def _recover_hp(self, client):
        out = wake_and_stand(client)
        vitals = extract_health(out)
        if vitals and vitals["hp"] < 50:
            _recover_until(client, "hp", max(75, vitals["max_hp"] * 3 // 4),
                           command="rest", timeout=40.0)

    def _recover_mv(self, client):
        out = wake_and_stand(client)
        vitals = extract_health(out)
        if vitals and vitals["mv"] < 10:
            _recover_until(client, "mv", min(50, vitals["max_mv"]), command="sleep")
        return True

    def _walk_toward_hunt(self, client, start):
        """Optionally walk a DB-planned route toward a hunting zone.

        Returns a list of parsed rooms actually reached (empty if no route
        planned, unreachable, or the plan diverges from the live world).
        """
        try:
            from agents.worldnav import route_to_nearest_hunt, vnums_by_name
        except Exception:
            return []

        score = parse_score(send(client, "score"))
        level = score.get("level", 1)
        start_name = start["name"]
        candidates = vnums_by_name(start_name)
        if not candidates:
            return []

        best_route = None
        for v in candidates:
            route, _target = route_to_nearest_hunt(v, level)
            if route is not None and (best_route is None or len(route) < len(best_route)):
                best_route = route
        if not best_route:
            return []

        reached = []
        for step in best_route:
            direction = step["direction"]
            if not self._recover_mv(client):
                break
            out = send(client, direction)
            if any(m in out.lower() for m in BLOCKED_MSGS):
                send(client, "open " + direction)
                out = send(client, direction)
            parsed = parse_room_block(out)
            if not parsed:
                break
            # If the live room doesn't match the plan, stop route-following and
            # let the caller's DFS take over from wherever we actually are.
            if parsed["name"] != step["name"]:
                break
            reached.append(parsed)
        return reached


def register(registry):
    from agents.base import register_subagents

    register_subagents(registry, [GrindAgent()])
