# Goal: Review a complete bakery run and identify the next navigation problem

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/01_benchmark/navigation.py` | Benchmark runner — runs end-to-end navigation from Temple of Midgaard to the Bakery |
| `week2_capable/01_benchmark/traces/` | JSONL trace files from benchmark runs |
| `week2_capable/01_benchmark/memory_bench.db` | SQLite database with recorded rooms, exits, token usage |

## Key Architecture Decisions

- **End-to-end measurement**: The benchmark resets the player, runs the full navigation task, and captures every movement, error, token usage, and timing detail. No hand-holding or mid-run intervention.
- **Hook-based instrumentation**: Movements, errors, and token usage are collected via benchmark-specific hook closures wrapped around the memory hooks. This keeps measurement separate from agent logic.
- **Structured results**: Each run produces a dict with `elapsed_seconds`, `movements`, `movement_count`, `errors`, `success`, `result`. The summary function averages across runs for statistical validity.

## Key Findings

- Automatic context injection (`[here]` block) and compact movement summaries worked correctly, eliminating redundant `look` calls.
- Redundant `score` and `look` work originating from hooks was found — the hooks were triggering full inspection even when not needed.
- Automatic work (hooks) was not clearly distinguished from model-selected tools in the trace viewer, making it hard to understand what was driving token consumption.
- Invalid abbreviated movement arguments were discovered (e.g., the model sending `d` instead of `down`).
- The review concluded that navigation needed an explicit `plan_route` tool with three behaviors: known-route traversal, frontier ranking for exploration, and broad-exploration mode.

## Verification

```bash
cd week2_capable
BOUKENSHA_OTEL_ENABLED=true bin/nav_bench 3 15
```
