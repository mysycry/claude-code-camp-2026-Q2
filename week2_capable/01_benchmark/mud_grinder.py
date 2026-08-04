#!/usr/bin/env python3
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent.resolve()
PROJECT_ROOT = HERE.parent.parent.resolve()
BOUKENSHA_DIR = Path(os.environ.get("BOUKENSHA_DIR", PROJECT_ROOT / ".boukensha"))
SETTINGS_PATH = BOUKENSHA_DIR / "settings.yaml"

sys.path.insert(0, str(PROJECT_ROOT / "week1_baseline" / "python" / "12_context"))
from boukensha.tools.mud_client import MudDaemonClient

DB_PATH = PROJECT_ROOT / "week3_multi-agents" / "memory" / "memory_bench.db"
DIR_SHORT = {0: "n", 1: "e", 2: "s", 3: "w", 4: "u", 5: "d"}
DIR_OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e", "u": "d", "d": "u"}
ANSI_RE = re.compile(r"\x1b\[[\d;]*[a-zA-Z]")
HP_RE = re.compile(r"You have (\d+)\((\d+)\) hit", re.IGNORECASE)
XP_RE = re.compile(r"You have (\d+) exp", re.IGNORECASE)
XP_NEXT_RE = re.compile(r"You need (\d+) exp to reach your next level", re.IGNORECASE)
LEVEL_RE = re.compile(r"\(level (\d+)\)", re.IGNORECASE)
GOLD_RE = re.compile(r"(\d+) gold coins", re.IGNORECASE)
HMV_RE = re.compile(r"(\d+)H\s+(\d+)M\s+(\d+)V")


def pr(*args, **kwargs):
    print(*args, **kwargs, flush=True)


def strip_ansi(text):
    return ANSI_RE.sub("", text)


def load_settings():
    import yaml
    with open(SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def parse_hmv(text):
    m = HMV_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None, None, None


class WorldDB:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def get_room_name(self, vnum):
        cur = self.conn.execute("SELECT name FROM world_rooms WHERE vnum = ?", (vnum,))
        row = cur.fetchone()
        return row["name"] if row else None

    def get_exits(self, vnum):
        cur = self.conn.execute(
            "SELECT direction, dir_name, room_linked, door_flag FROM world_exits WHERE from_room = ?", (vnum,)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_zone_rooms(self, zone_vnum):
        cur = self.conn.execute(
            "SELECT vnum, name FROM world_rooms WHERE zone_number = ? ORDER BY vnum", (zone_vnum,)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_mobs_in_zone(self, zone_vnum):
        cur = self.conn.execute("""
            SELECT DISTINCT m.vnum, m.short_desc, m.long_desc, m.level, m.aliases
            FROM world_mobs m
            JOIN zone_mob_spawns zms ON m.vnum = zms.mob_vnum
            WHERE zms.zone_vnum = ?
            ORDER BY m.level
        """, (zone_vnum,))
        return [dict(row) for row in cur.fetchall()]

    def get_mob_spawn_rooms(self, zone_vnum):
        cur = self.conn.execute("""
            SELECT DISTINCT zms.room_vnum, r.name
            FROM zone_mob_spawns zms
            JOIN world_rooms r ON zms.room_vnum = r.vnum
            WHERE zms.zone_vnum = ?
            ORDER BY zms.room_vnum
        """, (zone_vnum,))
        return [dict(row) for row in cur.fetchall()]

    def bfs(self, start_vnum, end_vnum):
        if start_vnum == end_vnum:
            return []
        visited = {start_vnum}
        queue = [(start_vnum, [])]
        while queue:
            room, path = queue.pop(0)
            for ex in self.get_exits(room):
                to_room = ex["room_linked"]
                if to_room is None or to_room < 0 or to_room in visited:
                    continue
                step = (ex["direction"], ex["dir_name"], to_room, ex["door_flag"])
                new_path = path + [step]
                if to_room == end_vnum:
                    return new_path
                visited.add(to_room)
                queue.append((to_room, new_path))
        return None

    def find_room_by_name(self, name):
        cur = self.conn.execute("SELECT vnum FROM world_rooms WHERE name = ?", (name,))
        row = cur.fetchone()
        return row["vnum"] if row else None

    def find_rooms_by_name(self, name):
        cur = self.conn.execute("SELECT vnum FROM world_rooms WHERE name = ?", (name,))
        return [r["vnum"] for r in cur.fetchall()]


class MudClient:
    def __init__(self, host="localhost", port=4000, username="dummy", password="helloworld"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None

    def connect(self):
        self.client = MudDaemonClient()
        st = self.client.status()
        if not (st.get("ok") and st.get("data", {}).get("connected")):
            r = self.client.connect(host=self.host, port=self.port, name=self.username, password=self.password)
            if not r.get("ok"):
                raise RuntimeError(f"Connect failed: {r.get('error', r)}")
        self.wake_and_stand()

    def wake_and_stand(self):
        self.cmd_quiet("look")
        self.cmd_quiet("wake")
        self.cmd_quiet("stand")

    def ensure_connected(self):
        if self.client and self.client.status().get("data", {}).get("connected"):
            return True
        st = self.client.status()
        if not st.get("ok"):
            raise RuntimeError("Mud daemon unavailable")
        if not st.get("data", {}).get("connected"):
            r = self.client.connect(host=self.host, port=self.port, name=self.username, password=self.password)
            if not r.get("ok"):
                raise RuntimeError(f"Reconnect failed: {r.get('error', r)}")
            self.wake_and_stand()
        return True

    def cmd(self, command, timeout=5):
        try:
            r = self.client.send(command)
            if not r.get("ok"):
                if "connect" in str(r.get("error", "")):
                    self.ensure_connected()
                    r = self.client.send(command)
                if not r.get("ok"):
                    raise RuntimeError(f"Command '{command}' failed: {r.get('error', r)}")
            return strip_ansi(r["data"])
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            self.ensure_connected()
            r = self.client.send(command)
            if not r.get("ok"):
                raise RuntimeError(f"Command '{command}' failed: {r.get('error', r)}")
            return strip_ansi(r["data"])

    def cmd_quiet(self, command):
        try:
            return self.cmd(command, timeout=3)
        except RuntimeError:
            return ""

    def disconnect(self):
        if self.client:
            self.client.disconnect()


class Grinder:
    def __init__(self, mc, wdb, target_kills=10, target_level=None, zone_vnum=186):
        self.mc = mc
        self.wdb = wdb
        self.target_kills = target_kills
        self.target_level = target_level
        self.zone_vnum = zone_vnum
        self.kills = 0
        self.level = 1
        self.xp = 0
        self.gold = 0
        self.current_room = None
        self.mv = 0

    MV_LOW = 15
    MV_NAV_GATE = 35
    MV_SLEEP_TARGET = 35
    PATROL_ROOMS = 5
    SLEEP_CHUNK = 90

    def sleep_to_mv(self, target=35, max_wait=900):
        start = time.time()
        while time.time() - start < max_wait:
            if self.is_fighting():
                pr("  In combat — waiting for it to end before sleeping...")
                won, hp, max_hp = self.combat(None)
                if won and hp:
                    self.kills += 1
                    self.mc.cmd_quiet("get all corpse")
                    self.mc.cmd_quiet("get all")
                    self.mc.cmd_quiet("wear all")
                    self.check_score()
            if self.mv >= target:
                pr(f"  MV={self.mv} reached target {target}")
                return True
            pr(f"  Sleeping {self.SLEEP_CHUNK}s to recover MV (MV {self.mv} -> target {target})...")
            self.mc.cmd_quiet("sleep")
            time.sleep(self.SLEEP_CHUNK)
            self.mc.wake_and_stand()
            out, hmv, room_vnum = self.look_with_room()
            if hmv and hmv[2] is not None:
                self.mv = hmv[2]
        pr(f"  MV recovery timed out (MV={self.mv})")
        return self.mv >= target

    def look_with_room(self):
        out = self.mc.cmd("look", timeout=8)
        hmv = parse_hmv(out)
        if hmv and hmv[2] is not None:
            self.mv = hmv[2]
        game_exits = None
        m = re.search(r"\[ Exits: ([a-z ]+)\]", out)
        if m:
            game_exits = set(m.group(1).split())
        for line in out.split("\n"):
            s = line.strip()
            if not s or s.startswith("["):
                continue
            if s.startswith("The corpse") or s.startswith("corpse"):
                continue
            if s[0].isupper() and "H " not in s and "M " not in s and "V " not in s and "> " not in s:
                name = s.split("[")[0].strip()
                matches = self.wdb.find_rooms_by_name(name)
                if len(matches) == 1:
                    self.current_room = matches[0]
                elif matches:
                    self.current_room = self._disambiguate_room(matches, game_exits)
                return out, hmv, self.current_room
        return out, hmv, self.current_room

    def _disambiguate_room(self, matches, game_exits):
        if game_exits is not None:
            for vnum in matches:
                db_exits = {e["dir_name"][0] for e in self.wdb.get_exits(vnum)}
                if db_exits == game_exits:
                    return vnum
        if self.current_room in matches:
            return self.current_room
        return matches[0]

    def get_current_room(self):
        out, _, _ = self.look_with_room()
        return self.current_room

    def nearest_patrol_room(self, from_vnum, patrol_vnums):
        best = patrol_vnums[0]
        best_len = 10 ** 9
        for target in patrol_vnums:
            path = self.wdb.bfs(from_vnum, target)
            if path is not None and len(path) < best_len:
                best = target
                best_len = len(path)
        return best

    BLOCKED_MSGS = ["can't go", "alas", "in your dreams", "too exhausted", "closed"]

    def is_blocked(self, text):
        t = text.lower()
        return any(m in t for m in self.BLOCKED_MSGS), t

    def navigate_to_room(self, target_vnum):
        if self.current_room is None:
            self.get_current_room()
        if self.current_room == target_vnum:
            return True
        if self.mv < self.MV_NAV_GATE:
            pr(f"  MV={self.mv} < {self.MV_NAV_GATE} — recovering before navigating")
            self.sleep_to_mv(self.MV_NAV_GATE)
        path = self.wdb.bfs(self.current_room, target_vnum)
        if path is None:
            pr(f"  No path from {self.current_room} to {target_vnum}")
            return False
        for direction, dir_name, to_room, door_flag in path:
            d_short = DIR_SHORT[direction]
            for attempt in range(3):
                out = self.mc.cmd(d_short, timeout=8)
                hmv = parse_hmv(out)
                if hmv and hmv[2] is not None:
                    self.mv = hmv[2]
                blocked, lower = self.is_blocked(out)
                if not blocked:
                    self.current_room = to_room
                    break
                if "too exhausted" in lower or "in your dreams" in lower:
                    self.sleep_to_mv(20)
                    continue
                if "closed" in lower:
                    self.mc.cmd_quiet("open door")
                    self.mc.cmd_quiet("open grate")
                    continue
                self.get_current_room()
                return False
            else:
                pr(f"  Stuck at {d_short} after 3 attempts")
                self.get_current_room()
                return False
        self.get_current_room()
        return True

    def sleep_to_recover(self, seconds=60):
        if self.is_fighting():
            pr(f"  In combat — waiting for it to end before sleeping...")
            won, hp, max_hp = self.combat(None)
            if won and hp:
                self.mc.cmd_quiet("get all corpse")
                self.mc.cmd_quiet("get all")
        pr(f"  Sleeping {seconds}s to recover...")
        self.mc.cmd_quiet("sleep")
        time.sleep(seconds)
        self.mc.wake_and_stand()

    def build_mob_map(self, zone_vnum):
        mobs = self.wdb.get_mobs_in_zone(zone_vnum)
        alias_counts = {}
        for m in mobs:
            if m["aliases"]:
                for a in m["aliases"].split(","):
                    a = a.strip()
                    alias_counts[a] = alias_counts.get(a, 0) + 1
        result = {}
        for m in mobs:
            desc = (m["long_desc"] or "").strip()
            aliases = [a.strip() for a in m["aliases"].split(",")] if m["aliases"] else []
            unique = [a for a in aliases if alias_counts.get(a, 0) == 1]
            best = unique[0] if unique else (aliases[0] if aliases else "")
            if desc:
                result[desc] = {"alias": best, "level": m["level"], "vnum": m["vnum"]}
        return result

    def parse_mobs_in_room(self, look_output, mob_map):
        found = []
        for line in look_output.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("[") or stripped.startswith("The corpse") or stripped.startswith("corpse"):
                continue
            for desc, info in mob_map.items():
                if desc.strip(".") in stripped or desc in stripped:
                    found.append(info)
                    break
        seen = set()
        uniq = []
        for f in found:
            if f["alias"] not in seen:
                seen.add(f["alias"])
                uniq.append(f)
        return uniq

    def check_score(self):
        out = self.mc.cmd("score", timeout=8)
        hp = 99
        max_hp = 99
        xp_next = 0
        m = HP_RE.search(out)
        if m:
            hp, max_hp = int(m.group(1)), int(m.group(2))
        m = XP_RE.search(out)
        if m:
            self.xp = int(m.group(1))
        m = XP_NEXT_RE.search(out)
        if m:
            xp_next = int(m.group(1))
        m = LEVEL_RE.search(out)
        if m:
            self.level = int(m.group(1))
        m = GOLD_RE.search(out)
        if m:
            self.gold = int(m.group(1))
        return hp, max_hp, xp_next

    def is_fighting(self):
        try:
            out = self.mc.cmd("score", timeout=8)
        except RuntimeError:
            return True
        return "fighting" in out.lower()

    def combat(self, alias):
        """Kill a mob and wait for combat to resolve. Returns (won, hp, max_hp)."""
        if alias:
            result = self.mc.cmd(f"kill {alias}", timeout=15)
            lower = result.lower()
            if "not here" in lower or "isn't here" in lower or "aren't here" in lower:
                return False, None, None

        start = time.time()
        while time.time() - start < 150:
            time.sleep(5)
            out = self.mc.cmd("score", timeout=8)
            if "fighting" not in out.lower():
                m = HP_RE.search(out)
                hp = int(m.group(1)) if m else 0
                max_hp = int(m.group(2)) if m else 0
                return hp > 0, hp, max_hp
            m = HP_RE.search(out)
            if m and int(m.group(1)) <= 0:
                return False, 0, int(m.group(2))
        return False, None, None

    def rest_if_needed(self):
        hp, max_hp, _ = self.check_score()
        if hp < max_hp * 0.4:
            pr(f"  HP {hp}/{max_hp} — resting...")
            self.mc.cmd_quiet("rest")
            time.sleep(8)
            self.mc.cmd_quiet("stand")
            hp, max_hp, _ = self.check_score()
            pr(f"  HP now {hp}/{max_hp}")

    def grind_loop(self):
        mob_map = self.build_mob_map(self.zone_vnum)
        pr(f"  Tracked {len(mob_map)} mob types in zone {self.zone_vnum}")

        spawn_rooms = self.wdb.get_mob_spawn_rooms(self.zone_vnum)
        patrol_vnums = [s["room_vnum"] for s in spawn_rooms]
        pr(f"  Patrol: {len(patrol_vnums)} rooms")

        self.get_current_room()
        if self.is_fighting():
            pr("  In combat — waiting for it to end before starting...")
            won, hp, max_hp = self.combat(None)
            if won and hp:
                self.kills += 1
                self.mc.cmd_quiet("get all corpse")
                self.mc.cmd_quiet("get all")
                self.mc.cmd_quiet("wear all")
                self.check_score()
                pr(f"  Won initial fight! Kills={self.kills} HP={hp}/{max_hp}")
        if self.current_room and self.current_room not in patrol_vnums:
            near = self.nearest_patrol_room(self.current_room, patrol_vnums)
            pr(f"  At room {self.current_room} (not a spawn room), moving to nearest spawn {near}")
            self.navigate_to_room(near)
        elif self.current_room:
            pr(f"  Starting at spawn room {self.current_room}")

        start_room = self.current_room or patrol_vnums[0]
        def _dist(v):
            p = self.wdb.bfs(start_room, v)
            return len(p) if p is not None else 10 ** 9
        patrol_vnums.sort(key=_dist)
        patrol_vnums = patrol_vnums[: min(self.PATROL_ROOMS, len(patrol_vnums))]
        pr(f"  Local patrol (nearest {len(patrol_vnums)}): {patrol_vnums}")

        start_time = time.time()
        patrol_index = 0
        stuck_count = 0

        while True:
            if self.target_level and self.level >= self.target_level:
                pr(f"  Reached level {self.level}!")
                break
            if self.kills >= self.target_kills:
                pr(f"  Reached {self.kills} kills!")
                break

            look_out, hmv, room_vnum = self.look_with_room()
            mobs = self.parse_mobs_in_room(look_out, mob_map)

            if self.mv < self.MV_LOW:
                pr(f"  MV={self.mv} < {self.MV_LOW} — recovering before continuing")
                self.sleep_to_mv(self.MV_SLEEP_TARGET)

            if self.is_fighting():
                pr("  Already in combat — waiting for it to end...")
                won, hp, max_hp = self.combat(None)
                if won and hp:
                    self.kills += 1
                    self.mc.cmd_quiet("get all corpse")
                    self.mc.cmd_quiet("get all")
                    self.mc.cmd_quiet("wear all")
                    _, _, xp_next = self.check_score()
                    pr(f"  Won! Kills={self.kills} L{self.level} XP={self.xp}/{xp_next} HP={hp}/{max_hp} Gold={self.gold}")
                else:
                    pr(f"  Lost the fight (HP={hp}/{max_hp})")
                    self.mc.cmd_quiet("get all corpse")
                continue

            if mobs:
                mobs.sort(key=lambda m: m["level"] or 99)
                target = mobs[0]
                t_alias = target["alias"]
                t_level = target["level"]
                lstr = f"L{t_level}" if t_level else "?"
                stuck_count = 0
                pr(f"  [{self.kills + 1}/{self.target_kills}] Attacking '{t_alias}' {lstr}...")

                won, hp, max_hp = self.combat(t_alias)

                if won and hp:
                    self.kills += 1
                    self.mc.cmd_quiet("get all corpse")
                    self.mc.cmd_quiet("get all")
                    self.mc.cmd_quiet("wear all")
                    _, _, xp_next = self.check_score()
                    pr(f"  Killed! Kills={self.kills} L{self.level} XP={self.xp}/{xp_next} HP={hp}/{max_hp} Gold={self.gold}")
                else:
                    pr(f"  No kill — moving on")
                self.rest_if_needed()
            else:
                stuck_count += 1
                if stuck_count >= 4:
                    pr(f"  No mobs in {stuck_count} checks — sleeping 45s for respawns")
                    self.sleep_to_recover(45)
                    stuck_count = 0

                next_room = patrol_vnums[patrol_index % len(patrol_vnums)]
                patrol_index += 1
                if self.current_room != next_room:
                    ok = self.navigate_to_room(next_room)
                    if not ok:
                        self.get_current_room()
                        if self.mv < self.MV_LOW:
                            pr(f"  Can't move (MV={self.mv}) — recovering before retrying")
                            self.sleep_to_mv(self.MV_SLEEP_TARGET)
                            self.get_current_room()
                else:
                    time.sleep(5)

        elapsed = time.time() - start_time
        rate = self.kills / elapsed * 60 if elapsed > 0 else 0
        pr(f"\n=== GRIND COMPLETE ===")
        pr(f"Kills: {self.kills} | Level: {self.level} | XP: {self.xp} | Gold: {self.gold}")
        pr(f"Time: {elapsed:.0f}s | Rate: {rate:.0f} kills/min")


def main():
    settings = load_settings()
    mud_cfg = settings.get("mud", {})
    mc = MudClient(
        host=mud_cfg.get("host", "localhost"),
        port=mud_cfg.get("port", 4000),
        username=mud_cfg.get("username", "dummy"),
        password=mud_cfg.get("password", "helloworld"),
    )
    wdb = WorldDB(DB_PATH)

    import argparse
    parser = argparse.ArgumentParser(description="MUD Grinder")
    parser.add_argument("--kills", type=int, default=10)
    parser.add_argument("--level", type=int, default=None)
    parser.add_argument("--zone", type=str, default="newbie", choices=["newbie", "sewer"])
    args = parser.parse_args()

    zone_map = {"newbie": 186, "sewer": 70}
    zone_vnum = zone_map[args.zone]

    pr(f"Connecting to MUD as {mc.username}...")
    try:
        mc.connect()
    except RuntimeError as e:
        pr(f"  Connection failed: {e}")
        return 1
    pr("  Connected.")

    grinder = Grinder(mc, wdb, target_kills=args.kills, target_level=args.level, zone_vnum=zone_vnum)
    grinder.get_current_room()
    pr(f"  Start: room {grinder.current_room} ({wdb.get_room_name(grinder.current_room)})")

    zone_rooms = wdb.get_zone_rooms(zone_vnum)
    if not zone_rooms:
        pr(f"  Zone {zone_vnum} has no rooms!")
        return 1

    grinder.grind_loop()
    mc.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
