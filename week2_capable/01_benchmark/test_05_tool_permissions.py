"""Step 05: Tool Permissions — test allow rules, dispatch gate, parameter restrictions."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "week1_baseline", "python", "12_context"))

from boukensha.registry import Registry
from boukensha.context import Context
from boukensha.errors import UnknownToolError

print("=== STEP 05: Tool Permissions ===\n")

# 1. Default allow (all tools permitted)
print("1) No allow / wildcard ---")
r = Registry(Context())
print(f"   allowed('look'):   {r.allowed('look')}   (expect True)")
print(f"   allowed('attack'): {r.allowed('attack')}   (expect True)")

r2 = Registry(Context(), allow=["*"])
print(f"   wildcard allowed('look'): {r2.allowed('look')}   (expect True)")

# 2. Specific allow list
print("\n2) Allow list ---")
r3 = Registry(Context(), allow=["look", "move"])
print(f"   allowed('look'):   {r3.allowed('look')}   (expect True)")
print(f"   allowed('attack'): {r3.allowed('attack')}   (expect False)")

# 3. Tool registration silently skips non-allowed
print("\n3) Registration gating ---")
ctx = Context()
r4 = Registry(ctx, allow=["look", "move"])

t = r4.tool("look", "Look around")
print(f"   register look:   {'OK' if t is not None else 'SKIPPED'}   (expect OK)")
print(f"   look in context: {'YES' if 'look' in ctx.tools else 'NO'}   (expect YES)")

t2 = r4.tool("attack", "Attack mob")
print(f"   register attack: {'OK' if t2 is not None else 'SKIPPED'}   (expect SKIPPED)")
print(f"   attack in context: {'YES' if 'attack' in ctx.tools else 'NO'}   (expect NO)")

# 4. Dispatch gate
print("\n4) Dispatch enforcement ---")
try:
    r4.dispatch("attack")
    print("   dispatch('attack'): ALLOWED (unexpected!)")
except UnknownToolError as e:
    print(f"   dispatch('attack'): BLOCKED — {e}   (expect BLOCKED)")

# 5. Parameter-level restrictions
print("\n5) Parameter-level restrictions ---")
r5 = Registry(Context(), allow=[
    "look",
    {"check": {"kind": ["exits", "score"]}},
])
print(f"   allowed('check', kind=exits):  {r5.allowed('check', {'kind': 'exits'})}   (expect True)")
print(f"   allowed('check', kind=score):  {r5.allowed('check', {'kind': 'score'})}   (expect True)")
print(f"   allowed('check', kind=kill):   {r5.allowed('check', {'kind': 'kill'})}   (expect False)")
print(f"   allowed('attack'):             {r5.allowed('attack')}   (expect False)")

# 6. Parameter dispatch gate
print("\n6) Parameter dispatch ---")
ctx6 = Context()
r6 = Registry(ctx6, allow=[
    "look",
    {"check": {"kind": ["exits", "score"]}},
])
r6.tool("check", "Check things", parameters={"kind": {"type": "string"}},
        block=lambda kind: f"checked {kind}")

try:
    r6.dispatch("check", {"kind": "kill"})
    print("   dispatch check(kind=kill): ALLOWED (unexpected!)")
except UnknownToolError as e:
    print(f"   dispatch check(kind=kill): BLOCKED — {e}   (expect BLOCKED)")

result = r6.dispatch("check", {"kind": "exits"})
print(f"   dispatch check(kind=exits): {result}   (expect 'checked exits')")

print("\n=== STEP 05 DONE ===")
