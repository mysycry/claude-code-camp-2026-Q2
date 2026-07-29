# Goal: Convert operation logs into structured traces

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/python/12_context/boukensha/tracer.py` | `Span` class (with `__slots__`), `Tracer` (span tree, lifecycle, `waterfall()` rendering, `dump()` serialization) |
| `week1_baseline/python/12_context/boukensha/agent.py` | Span creation at each lifecycle point — `turn`, `llm_call`, `tool_loop`, `tool/{name}`, `compaction`, `wrap_up` |

## Key Architecture Decisions

- **Span struct with `__slots__`**: `trace_id`, `span_id`, `parent_id`, `name`, `phase`, `started_at`, `finished_at`, `duration_ms`, `status`, `error`, `metadata` — compact memory footprint.
- **Waterfall rendering**: `Tracer.waterfall()` outputs a human-readable indented tree with duration (right-aligned, ms) and status (OK/ERR):
  ```
  turn (41030ms)
    llm_call (2456ms)
    tool_loop (3280ms)
      tool/mud_connect (3280ms)
  ```
- **Span tree structure** (from trace files):
  - `turn` (root, ~41s total) → alternating `llm_call` (~2.5s each) and `tool_loop` (0.1-3.3s each)
  - Optional `compaction` and `wrap_up` siblings
- **Trace file output**: `Tracer.dump()` writes finished spans as JSONL to `{trace_dir}/trace_{trace_id}.jsonl`. Created in `Tracer.finish()`, which first ends all remaining open spans.
- **Detailed JSONL logs preserved**: The structured trace format supplements, not replaces, the existing JSONL session logs. Both formats are written independently.

## Key Findings

- 50 trace files exist in `traces/`, representing multiple benchmark runs on July 28-29, 2026.
- A typical turn takes 30-50 seconds with 10-15 LLM calls and 10-20 tool calls.
- Connection overhead is visible: `tool/mud_connect` spans 3-5 seconds.
- The waterfall format is purely textual (console/terminal output), no HTML or graphical rendering.

## Verification

```python
from boukensha.tracer import Tracer
tracer = Tracer()
with tracer.span("turn", "run") as s:
    with tracer.span("llm_call", "model") as s2:
        s2.ok({"tokens": 150})
tracer.waterfall()  # Should show: turn -> llm_call
```
