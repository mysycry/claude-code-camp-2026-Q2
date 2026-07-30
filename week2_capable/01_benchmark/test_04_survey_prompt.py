"""Step 04: Verify deterministic survey protocol is in the system prompt."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "week1_baseline", "python", "12_context"))

print("=== STEP 04: Deterministic Survey ===\n")

prompt_path = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir,
    "week1_baseline", "python", "12_context",
    "boukensha", "prompts", "system.md",
)

with open(prompt_path, encoding="utf-8") as f:
    prompt = f.read()

print("System prompt:")
print("-" * 40)
print(prompt)
print("-" * 40)
print()

checks = {"look": False, "exits": False, "consider": False, "examine": False}
for word in checks:
    if word in prompt:
        checks[word] = True

for word, found in checks.items():
    status = "OK" if found else "MISSING"
    print(f"  {word}: {status}")

print(f"\nResult: {'ALL PRESENT' if all(checks.values()) else 'SOME MISSING'}")
