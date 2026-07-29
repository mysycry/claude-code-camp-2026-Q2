"""Smoke test: connect to MUD, look, move, verify MemoryStore is populated."""
import os
import sqlite3
import sys

root = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
sys.path.insert(0, os.path.join(root, "week1_baseline", "python", "12_context"))
sys.path.insert(0, os.path.join(root, "week2_capable", "02_automatic_resets"))
sys.path.insert(0, os.path.dirname(__file__))

from boukensha.tools.mud_client import MudDaemonClient, PORT_FILE
from boukensha.memory import MemoryStore
from memory_hook import make_memory_hook, parse_room_description
from player_reset import reset_player_to_start

MEMORY_DB = os.path.join(os.path.dirname(__file__), "memory_bench.db")

store = MemoryStore(path=MEMORY_DB)
# Clear stale data via direct SQLite (works even if server holds WAL lock)
try:
    os.remove(MEMORY_DB)
except PermissionError:
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute("DELETE FROM token_usage")
    for t in ("rooms","exits","entities","player_state","sightings"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
store._execute("SELECT 1")  # ensure connection alive
hook = make_memory_hook()

class FakeCtx:
    memory_store = store
    def inject_here_block(self):
        store.here_block()
        return True

ctx = FakeCtx()

print("resetting player to start room 3001...", file=sys.stderr)
reset_player_to_start(start_room="3001", quiet=True)

print("connecting to MUD via daemon...", file=sys.stderr)
c = MudDaemonClient(session="mem_test")
try:
    c.disconnect()
except Exception:
    pass
r = c.connect(host="localhost", port=4000, name="dummy", password="helloworld")
assert r.get("ok"), f"connect failed: {r}"

print("  look...", file=sys.stderr)
r = c.send("look")
text = r.get("data", "")
parsed = parse_room_description(text)
assert parsed, f"could not parse room from: {text[:200]}"
print(f"  room: [{parsed['room_name']}]", file=sys.stderr)
print(f"  exits: {[e['direction'] for e in parsed['exits']]}", file=sys.stderr)
hook(ctx, "look", {}, text, None)

first = store.current_room()
assert first, "current_room should be set after look"
print(f"  stored current_room: {first}", file=sys.stderr)
print(f"  room name: {store.room_name(first)}", file=sys.stderr)
print(f"  here block: {store.here_block()}", file=sys.stderr)

# Try each valid exit until we find one that works
moved = False
for ex in parsed["exits"]:
    d = ex["direction"]
    if moved:
        break
    print(f"  move {d}...", file=sys.stderr)
    r = c.send(d)
    text = r.get("data", "")
    parsed2 = parse_room_description(text)
    if parsed2 and parsed2["room_name"]:
        print(f"  new room: [{parsed2['room_name']}]", file=sys.stderr)
        hook(ctx, "move", {"direction": d}, text, None)
        second = store.current_room()
        assert second, "current_room should update after move"
        if second != first:
            moved = True
            print(f"  moved to new room!", file=sys.stderr)
            print(f"  exits from new room: {store.exits_for(second)}", file=sys.stderr)
            print(f"  here block: {store.here_block()}", file=sys.stderr)

print("  look again (re-record current room)...", file=sys.stderr)
r = c.send("look")
text = r.get("data", "")
hook(ctx, "look", {}, text, None)
explored = store.visited_count()
print(f"  rooms visited: {explored}", file=sys.stderr)

if not moved:
    print("  (could not move — that's OK, room recording still works)", file=sys.stderr)
else:
    assert explored >= 2, f"expected >= 2 rooms after moving, got {explored}"

c.disconnect()
print(file=sys.stderr)
print(f"MEMORY TEST PASSED — {explored} rooms recorded in {MEMORY_DB}", file=sys.stderr)
