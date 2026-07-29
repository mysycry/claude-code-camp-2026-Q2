# Goal: Benchmark navigation cost to expose why the agent could not reliably reach the bakery

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/01_benchmark/navigation.py` | Benchmark runner — repeatedly tries navigating from Temple of Midgaard to the Bakery, tracks movements, errors, token usage, duration |
| `week2_capable/01_benchmark/memory_hook.py` | Hooks that parse room descriptions (`look` output) and record rooms/exits into `MemoryStore` |
| `week2_capable/01_benchmark/memory_server.py` | REST API + HTML UI on port 9876 for viewing memory/exploration data |
| `week2_capable/01_benchmark/test_memory.py` | Smoke test: resets player, looks around, moves, verifies parsing |
| `week2_capable/01_benchmark/traces/` | JSONL trace files from benchmark runs |
| `week2_capable/bin/nav_bench` | Bash wrapper — auto-starts MUD daemon, sets env vars, runs benchmark |

## Key Architecture Decisions

- **Hook-based memory**: Memory recording is injected via the `hooks` dict (before_tool, after_tool, after_model), not baked into the agent loop. The benchmark creates closures that capture a `MemoryStore` instance and a movement/error accumulator.
- **Room identification**: MD5 hash of room name truncated to 16 hex chars (`_room_id()`). This gives deterministic IDs without needing MUD room numbers.
- **Exit parsing**: Regex handles both `Obvious exits:` and `[ Exits]:` formats (CircleMUD vs ROM), plus `north - Room Name` long-form and `n s e w` short-form.
- **Token usage recording**: `after_model` hook maps LLM API response fields — handles both `input_tokens`/`output_tokens` and `prompt_tokens`/`completion_tokens` naming conventions.
- **Memory server**: Standalone Python `http.server` with `ThreadingMixIn`, queries the same `memory_bench.db` SQLite file. Serves both a JSON REST API and an HTML dashboard.
- **Pathfinding**: BFS algorithms in `MemoryStore` (`find_path`, `rooms_nearby`) generate a `[paths]` block injected into the system prompt.

## Key Findings

- Runs consumed roughly 65K tokens without reaching the bakery.
- Missing exit knowledge and repeated room reasoning were the main failure modes.
- Manual resets were unreliable.
- These failures directly drove automated resets (step 02) and structured room inspection (step 03).

## Verification

```bash
cd week2_capable/01_benchmark
python -c "from navigation import run_benchmark; run_benchmark(runs=3, max_iterations=15)"
```
