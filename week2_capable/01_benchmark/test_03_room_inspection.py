"""Step 03: Room Inspection — look + exits, verify dest names are recorded."""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "week1_baseline", "python", "12_context"))
sys.path.insert(0, os.path.dirname(__file__))

from boukensha.memory import MemoryStore
from boukensha.tools.mud_client import MudDaemonClient
from memory_hook import make_memory_hook

DB = os.path.join(os.path.dirname(__file__), "_test_03.db")
if os.path.isfile(DB): os.remove(DB)

store = MemoryStore(path=DB)
hook = make_memory_hook()


class Ctx:
    memory_store = store
    def inject_here_block(self):
        b = store.here_block()
        print(f"  [here block]\n    {b}")


c = MudDaemonClient(session="test_03")
try: c.disconnect()
except: pass
r = c.connect(host="localhost", port=4000, name="dummy", password="helloworld")
if not r.get("ok"):
    print(f"FAIL: connect error — {r.get('error', 'unknown')}")
    sys.exit(1)

print("=== STEP 03: Room Inspection ===\n")

# 1) LOOK around
print("1) look ---")
r = c.send("look")
hook(Ctx(), "look", {}, r["data"], None)
rid = store.current_room()
print(f"   Room: {store.room_name(rid)}")
for ex in store.exits_for(rid):
    d = ex["dest_name"] or "(unknown)"
    print(f"   Exit: {ex['direction']} -> {d}")

# 2) CHECK EXITS
print("\n2) check(kind: 'exits') ---")
r = c.send("exits")
print(f"   Raw:\n{r['data']}")
hook(Ctx(), "check", {"kind": "exits"}, r["data"], None)
print(f"\n   After exits command:")
for ex in store.exits_for(rid):
    d = ex["dest_name"] or "(unknown)"
    print(f"   Exit: {ex['direction']} -> {d}")

# 3) MOVE if there's at least one exit
exits = store.exits_for(rid)
if exits and any(e["dest_name"] for e in exits):
    target = next(e for e in exits if e["dest_name"])
    print(f"\n3) move {target['direction']} -> {target['dest_name']} ---")
    r = c.send(target["direction"])
    hook(Ctx(), "move", {"direction": target["direction"]}, r["data"], None)
    rid2 = store.current_room()
    print(f"   Now in: {store.room_name(rid2)}")

    print("\n4) look in new room ---")
    r = c.send("look")
    hook(Ctx(), "look", {}, r["data"], None)
    for ex in store.exits_for(rid2):
        d = ex["dest_name"] or "(unknown)"
        print(f"   Exit: {ex['direction']} -> {d}")

    print("\n5) check(kind: 'exits') in new room ---")
    r = c.send("exits")
    print(f"   Raw:\n{r['data']}")
    hook(Ctx(), "check", {"kind": "exits"}, r["data"], None)
    for ex in store.exits_for(rid2):
        d = ex["dest_name"] or "(unknown)"
        print(f"   Exit: {ex['direction']} -> {d}")
else:
    print("\n(no named exits to follow, skipping move)")

c.disconnect()
store.close()
os.remove(DB)
print("\n=== STEP 03 DONE ===")
