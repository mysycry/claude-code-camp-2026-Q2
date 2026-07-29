# Goal: Add lifecycle control and memory so inspection is enforced by the loop

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/python/12_context/boukensha/memory.py` | `MemoryStore` class — SQLite knowledge store with WAL mode, 6 tables, pathfinding, context block generation |
| `week1_baseline/python/12_context/boukensha/agent.py` | Hook lifecycle — `_run_hook()` dispatches at 6 hook points (before/after turn, model, tool) |
| `week1_baseline/python/12_context/boukensha/context.py` | `inject_here_block()` — appends/replaces compact `[here]` awareness block in system prompt |
| `week1_baseline/python/12_context/boukensha/__init__.py` | `memory_path` parameter plumbed through `run()` and `repl()` |

## Key Architecture Decisions

- **Six hook points**: `before_turn`, `after_turn`, `before_model`, `after_model`, `before_tool`, `after_tool`. Each receives the `Context` object plus call-specific arguments. Errors are caught and logged but do NOT crash the agent.
- **SQLite with WAL mode**: `PRAGMA journal_mode=WAL` enables concurrent reads while the agent writes. Thread-local connections via `threading.local()`.
- **Six tables**: `rooms` (with visit_count), `exits` (with seen/walked flags), `entities` (mobs/items/players), `player_state` (key/value), `sightings` (timestamps), `token_usage` (model/provider/tokens).
- **Memory injection**: `Context.inject_here_block()` generates a compact `[here]` block (current room, known exits, entities, memory blocks, pathfinding hints) and appends it to, or replaces it in, the system prompt.
- **Compaction**: Happens at `compaction_threshold=0.70`, dropping 50% of messages when context window is 70% full.

## Key Findings

- The memory store is optional — only created when `memory_path` is passed to `run()` or `repl()`.
- Room recording uses upsert: if room already exists, increments `visit_count`. Exit recording uses `COALESCE(?, to_room)` to preserve destination even when initially unknown.
- `here_block()` eliminates the need for the agent to `look` every turn — it provides spatial context directly in the system prompt.
- Pathfinding BFS (`find_path()`, `rooms_nearby()`) generates pathfinding hints that help the agent reach destinations without getting lost.

## Verification

```python
from boukensha.memory import MemoryStore
store = MemoryStore(":memory:")
store.record_room("abc", "The Temple Of Midgaard")
store.record_exit("abc", "south", dest_room="def")
assert store.find_path("abc", "def") == ["south"]
```
