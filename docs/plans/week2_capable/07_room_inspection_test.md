# Goal: Test room inspection and identify where the first design failed

## Files

| File | What It Does |
|------|-------------|
| `docs/journal/2_capable.md` | Captures test findings, measurements, and technical observations |
| `week2_capable/01_benchmark/traces/` | Trace log files from benchmark runs showing 30-35s per room |

## Key Architecture Decisions

- **Empirical measurement**: Real `inspect_room` outputs were captured as journal artifacts and timed, rather than relying on qualitative observation.
- **Failure-driven development**: The failures identified here directly drove two subsequent steps — Mud Monitor (Step 08) for observability, and deterministic surveying (Step 10) to replace agentic inspection with code.

## Key Findings

- Inspection calls took ~30-35 seconds per room — far too slow for practical gameplay.
- The delegated inspection was running a full agent loop (model calls, tool dispatch, LLM-generated analysis) instead of a focused deterministic parse.
- The player sometimes moved to a new room without inspecting it first, creating blind spots.
- There was no visibility into delegated calls, their durations, or their token accounting — these gaps drove Step 08.

## Verification

```bash
# Run benchmark and measure per-room inspection time
cd week2_capable/01_benchmark
python -c "from navigation import run_benchmark; run_benchmark(runs=1, max_iterations=5)"
```
