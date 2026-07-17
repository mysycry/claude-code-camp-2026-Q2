#!/usr/bin/env python3
"""
Grinding bot — calls mud.py in a loop to level up and defeat the minotaur.
"""

import subprocess
import re
import sys
import os
import time

MUD_PY = os.path.join(os.path.dirname(__file__), "mud.py")
DATA_DIR = "/tmp/mud-data"


def run(cmds, wait=None):
    args = ["python3", MUD_PY, cmds, "--data-dir", DATA_DIR]
    if wait:
        args += ["--wait", str(wait)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return r.stdout


def parse_stats(output):
    stats = {"hp": 0, "max_hp": 0, "mv": 0, "max_mv": 0, "xp": 0, "xp_next": 0, "level": 1, "room": ""}
    for line in output.split("\n"):
        m = re.match(r"You have (\d+)\((\d+)\) hit.*?and (\d+)\((\d+)\) movement", line)
        if m:
            stats["hp"] = int(m.group(1))
            stats["max_hp"] = int(m.group(2))
            stats["mv"] = int(m.group(3))
            stats["max_mv"] = int(m.group(4))
        m = re.match(r"You have (\d+) exp", line)
        if m: stats["xp"] = int(m.group(1))
        m = re.match(r"You need (\d+) exp to reach your next level", line)
        if m: stats["xp_next"] = int(m.group(1))
        m = re.match(r"This ranks you as .+ \(level (\d+)\)", line)
        if m: stats["level"] = int(m.group(1))
        m = re.match(r"^([A-Z][A-Za-z ]+)$", line)
        if m and not stats["room"]:
            stats["room"] = m.group(1).strip()
    return stats


def parse_room(output):
    for line in output.split("\n"):
        m = re.match(r"^([A-Z][A-Za-z ]+)$", line)
        if m:
            return m.group(1).strip()
    return ""


def has_mobs(output, *keywords):
    ol = output.lower()
    for kw in keywords:
        if kw.lower() in ol:
            return True
    return False


def is_exhausted(output):
    return "too exhausted" in output.lower() or "exhausted" in output.lower()


def main():
    target_level = 6
    if len(sys.argv) > 1:
        target_level = int(sys.argv[1])

    os.makedirs(DATA_DIR, exist_ok=True)

    print("=== Starting grind ===")
    out = run("look;score")
    stats = parse_stats(out)
    print(f"Room: {stats['room']}  L{stats['level']} HP:{stats['hp']}/{stats['max_hp']} MV:{stats['mv']}/{stats['max_mv']}")

    # If not in newbie zone, navigate there
    if "newbie" not in stats["room"].lower() and "passage" not in stats["room"].lower() and "hallway" not in stats["room"].lower() and "nexus" not in stats["room"].lower() and "corner" not in stats["room"].lower() and "brighter" not in stats["room"].lower() and "dark" not in stats["room"].lower() and "dirty" not in stats["room"].lower() and "entrance" not in stats["room"].lower():
        print("Navigating to newbie zone...")
        out = run("n;n;n;n;e;look;score", wait=0.6)
        stats = parse_stats(out)
        room = parse_room(out)
        print(f"  Now at: {room}")
        if is_exhausted(out):
            run("rest;rest;rest;rest;rest;stand;look")

    print(f"\nHunting at: {stats['room']}")
    hunt_count = 0

    while True:
        out = run("score;look")
        stats = parse_stats(out)
        room = parse_room(out)

        # Check if we died
        if stats["hp"] <= 0:
            print("DIED! Trying to recover...")
            out = run("look;score")
            stats = parse_stats(out)
            if stats["hp"] <= 0:
                print("Still dead!")
                break

        print(f"L{stats['level']} XP:{stats['xp']}/{stats['xp_next']} HP:{stats['hp']}/{stats['max_hp']} MV:{stats['mv']}/{stats['max_mv']} [{room}]")

        # Check level up
        if stats["xp_next"] > 0 and stats["xp"] >= stats["xp_next"]:
            out = run("level;score")
            stats = parse_stats(out)
            print(f"  ** LEVEL UP! Now level {stats['level']}! **")

        # Check if we reached target level
        if stats["level"] >= target_level:
            print(f"\nReached level {target_level}!")
            break

        # Rest if low HP
        if stats["hp"] < stats["max_hp"] // 2:
            run("rest;rest;rest;rest;rest;stand", wait=2.0)
            continue

        # Rest if exhausted
        if stats["mv"] <= 0:
            run("rest;rest;rest;rest;rest;stand", wait=2.0)
            continue

        # Look for mobs and fight
        look_out = run("look")
        mob_found = False

        for mob in ["monster", "crawler", "dragon"]:
            if mob in look_out.lower():
                print(f"  Fighting {mob}...")
                combat_out = run(f"kill {mob}", wait=3.0)
                stats = parse_stats(combat_out)
                if "receive" in combat_out.lower() or "experience" in combat_out.lower():
                    hunt_count += 1
                    run("get all corpse;get all;wear all")
                    print(f"  Killed! ({hunt_count} total)")
                mob_found = True
                break

        if not mob_found:
            # Move to find mobs
            for d in ["e", "w"]:
                move_out = run(f"{d};look", wait=0.5)
                if not is_exhausted(move_out):
                    new_room = parse_room(move_out)
                    if new_room and new_room != room:
                        mob_check = run("look")
                        for mob in ["monster", "crawler", "dragon"]:
                            if mob in mob_check.lower():
                                mob_found = True
                                break
                        if mob_found:
                            break
                # Go back
                back = {"e": "w", "w": "e"}
                run(f"{back[d]};look", wait=0.5)

        if not mob_found and hunt_count == 0:
            print("  No mobs found, waiting...")
            run("look", wait=3.0)

    # Now go for the minotaur
    print(f"\n{'='*50}")
    print(f"GOING FOR THE MINOTAUR (Level {stats['level']})")
    print(f"{'='*50}")

    # Navigate through the newbie zone to the minotaur
    # Current location should be in the newbie zone upper level
    out = run("look;score", wait=0.5)
    stats = parse_stats(out)
    room = parse_room(out)
    print(f"Starting from: {room}")

    # Navigate to Alchemist's Room (need to go through specific rooms)
    out = run("look")
    room = parse_room(out)

    # Navigate to "Another Corner" first, then "Alchemist's Room"
    route_to_alchemist = []

    if "nexus" in room.lower():
        route_to_alchemist = ["s", "s", "open e", "e"]
    elif "more of the hallway" in room.lower():
        route_to_alchemist = ["s", "open e", "e"]
    elif "corner" in room.lower() and "another" in room.lower():
        route_to_alchemist = ["open e", "e"]
    elif "brighter" in room.lower():
        route_to_alchemist = ["e", "s", "open e", "e"]
    elif "dirty" in room.lower():
        route_to_alchemist = ["e", "s", "s", "open e", "e"]
    else:
        route_to_alchemist = ["e", "e", "s", "s", "open e", "e"]

    # Execute the route
    cmd_str = ";".join(route_to_alchemist)
    out = run(f"{cmd_str};look;score", wait=0.5)
    room = parse_room(out)
    print(f"After navigation: {room}")

    if "alchemist" not in room.lower():
        print("Trying to find Alchemist's Room...")
        out = run("look")
        out = run("open e;e;look;score", wait=0.5)
        room = parse_room(out)
        print(f"Now at: {room}")

    if "alchemist" in room.lower():
        print("Going downstairs!")
        out = run("d;look;score", wait=0.5)
        room = parse_room(out)
        print(f"Lower level: {room}")

        # Navigate through lower level to the Red Room (minotaur)
        lower_route = ["n", "e", "n", "w", "w", "s"]
        for step in lower_route:
            out = run(f"{step};look", wait=0.5)
            room = parse_room(out)
            if is_exhausted(out):
                run("rest;rest;rest;rest;rest;stand", wait=2.0)
            print(f"  {step} -> {room}")

        # Fight the minotaur
        print("\nLooking for the minotaur...")
        for attempt in range(10):
            out = run("look", wait=0.5)
            if "minotaur" in out.lower():
                print("MINOTAUR FOUND! ATTACKING!")
                combat_out = run("kill minotaur", wait=8.0)
                print(combat_out[:500])
                if "receive" in combat_out.lower() or "experience" in combat_out.lower():
                    run("get all corpse;get all;wear all")
                    print(">>> MINOTAUR DEFEATED! <<<")
                    out = run("score")
                    print(out)
                    return
                else:
                    print("Fight ended. Checking status...")
                    out = run("score;look")
                    print(out[:500])
                    break
            else:
                print(f"Waiting for minotaur ({attempt+1}/10)...")
                run("look", wait=4.0)
    else:
        print(f"Couldn't find Alchemist's Room. Current room: {room}")
        run("look")


if __name__ == "__main__":
    main()
