# Goal: Explore a real-time observer inspired by IbnouT's implementation

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/python/12_context/boukensha/agent.py` | `_run_hook()` — external callbacks observe every lifecycle event |
| `week1_baseline/python/12_context/boukensha/logger.py` | `subscribe(callback)` — real-time notification of every structured log event |

## Key Architecture Decisions

- **No formal Observer class**: Instead of a dedicated observer module, the framework uses lightweight callback injection through two mechanisms:
  1. **Agent hooks** (`hooks` dict) — external callbacks at every lifecycle stage (before/after model, tool, turn)
  2. **Logger subscribers** (`logger.subscribe()`) — real-time forwarding of every structured log event
- **Designed features** (not all built): a combined map display, player vitals panel, movement trail, activity feed, and thought display.
- **Identified gaps**: Missing vitals data (HP/mana/moves not always captured) and task-management data (sub-agent state not exposed).

## Key Findings

- The hooks + subscribers pattern provides the same decoupling as a formal Observer pattern with less code.
- The `memory_hook.py` after_tool hook is the primary observer in practice — it watches MUD commands and feeds parsed data into the MemoryStore.
- A full Observatory view as described in the design was not built; the need was met by Grafana dashboards, the Memory API, and the hook system.

## Verification

```python
# The observer pattern is exercised by the benchmark hooks
from week2_capable.benchmark.navigation import run_benchmark
run_benchmark(runs=1, max_iterations=5)  # hooks collect movements, errors, tokens
```
