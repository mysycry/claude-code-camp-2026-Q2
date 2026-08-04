"""Verify steps 03 (room inspection), 04 (deterministic survey), 05 (tool permissions)."""
import os
import sys

root = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
sys.path.insert(0, os.path.join(root, "week1_baseline", "python", "12_context"))
sys.path.insert(0, os.path.join(root, "week3_multi-agents", "resets"))
sys.path.insert(0, os.path.join(root, "week3_multi-agents", "memory"))
sys.path.insert(0, os.path.dirname(__file__))

from boukensha.memory import MemoryStore
from boukensha.registry import Registry
from boukensha.context import Context
from boukensha.tools.mud_client import MudDaemonClient
from boukensha.errors import UnknownToolError
from memory_hook import make_memory_hook
from player_reset import reset_player_to_start

MEMDB = os.path.join(os.path.dirname(__file__), "memory_steps_test.db")


# ---- helpers ----
class FakeCtx:
    memory_store = None
    def __init__(self, store):
        self.memory_store = store
    def inject_here_block(self):
        self.memory_store.here_block()


# ---- cleanup ----
if os.path.isfile(MEMDB):
    os.remove(MEMDB)

store = MemoryStore(path=MEMDB)
hook = make_memory_hook()
ctx = FakeCtx(store)

# ---- connect & reset ----
reset_player_to_start(start_room="3001", quiet=True)
c = MudDaemonClient(session="step03_test")
try:
    c.disconnect()
except Exception:
    pass
r = c.connect(host="localhost", port=4000, name="dummy", password="helloworld")
assert r.get("ok"), f"connect failed: {r}"

# ============================
# STEP 03: Room Inspection
# ============================
print("=== STEP 03: Room Inspection ===")

# 3a: look + parse room description
r = c.send("look")
text = r.get("data", "")
hook(ctx, "look", {}, text, None)
room_id = store.current_room()
assert room_id, "no current_room after look"
print(f"  Current room: {store.room_name(room_id)}")

# 3b: exits command + dest name recording
r = c.send("exits")
text = r.get("data", "")
print(f"  exits output:")
for line in text.split("\n"):
    line = line.strip()
    if " - " in line:
        print(f"    {line}")

hook(ctx, "check", {"kind": "exits"}, text, None)
exits = store.exits_for(room_id)
with_dest = [e for e in exits if e.get("dest_name")]
print(f"  Exits with destination names: {len(with_dest)}/{len(exits)}")
for e in with_dest:
    print(f"    {e['direction']} -> {e['dest_name']}")
assert len(with_dest) > 0, "no exits with destination names recorded"

# 3c: here_block shows destination names
block = store.here_block()
assert "->" in block, f"here_block missing dest names: {block}"
print(f"  here_block: {block}")

print("  STEP 03 PASSED")

# ============================
# STEP 04: Deterministic Survey
# ============================
print()
print("=== STEP 04: Deterministic Survey ===")

# The survey protocol is encoded in the system prompt (prompts/system.md).
# Verify the prompt contains the expected protocol.
prompt_path = os.path.join(
    root, "week1_baseline", "python", "12_context", "boukensha", "prompts", "system.md"
)
with open(prompt_path, encoding="utf-8") as f:
    prompt = f.read()

checks = [
    "look" in prompt,
    "exits" in prompt,
    "consider" in prompt,
    "examine" in prompt,
]
assert all(checks), f"system prompt missing survey instructions: {prompt}"
print("  System prompt contains look/exits/consider/examine")
print("  STEP 04 PASSED")

# ============================
# STEP 05: Tool Permissions
# ============================
print()
print("=== STEP 05: Tool Permissions ===")

# 5a: no allow = all tools permitted
r = Registry(FakeCtx(None))
assert r.allowed("look") is True
assert r.allowed("attack") is True

# 5b: wildcard
r2 = Registry(FakeCtx(None), allow=["*"])
assert r2.allowed("look") is True

# 5c: specific allow list
r3 = Registry(FakeCtx(None), allow=["look", "move"])
assert r3.allowed("look") is True
assert r3.allowed("attack") is False

# 5d: dispatch enforcement
ctx5 = Context()
r5 = Registry(ctx5, allow=["look", "move"])
t = r5.tool("look", "Look around")
assert t is not None, "allowed tool should register"
assert "look" in ctx5.tools, "look should be in context.tools"
t2 = r5.tool("attack", "Attack mob")
assert t2 is None, "disallowed tool should return None"
assert "attack" not in ctx5.tools, "attack should NOT be in context.tools"

# dispatch gate
try:
    r5.dispatch("attack")
    assert False, "dispatch should raise for disallowed tool"
except UnknownToolError as e:
    assert "not permitted" in str(e)

# 5e: parameter-level restrictions
r6 = Registry(FakeCtx(None), allow=[
    "look",
    {"check": {"kind": ["exits", "score"]}},
])
assert r6.allowed("check", {"kind": "exits"}) is True
assert r6.allowed("check", {"kind": "score"}) is True
assert r6.allowed("check", {"kind": "kill"}) is False

# 5f: parameter dispatch gate
ctx6 = Context()
r6b = Registry(ctx6, allow=[
    "look",
    {"check": {"kind": ["exits", "score"]}},
])
r6b.tool("check", "Check things", parameters={"kind": {"type": "string"}},
        block=lambda kind: f"checked {kind}")
r6b.tool("look", "Look around")
try:
    r6b.dispatch("check", {"kind": "kill"})
    assert False, "should raise for disallowed param value"
except UnknownToolError as e:
    assert "not permitted" in str(e)
result = r6b.dispatch("check", {"kind": "exits"})
assert result == "checked exits", f"expected 'checked exits', got {result}"

print("  No allow: all OK  |  Wildcard: OK  |  Allow list: OK")
print("  Dispatch gate: OK  |  Param restrictions: OK  |  Param dispatch gate: OK")
print("  STEP 05 PASSED")

# ----
c.disconnect()
store.close()
os.remove(MEMDB)
print()
print("ALL STEPS 03-04-05 PASSED")
