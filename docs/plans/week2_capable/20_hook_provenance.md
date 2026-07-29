# Goal: Attribute hidden automatic work to the turn that caused it

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/python/12_context/boukensha/tracer.py` | `Tracer` class — span creation, parent nesting, metadata attachment, waterfall rendering |
| `week1_baseline/python/12_context/boukensha/agent.py` | Creates Tracer spans for `turn`, `llm_call`, `tool_loop`, `tool/{name}`, `compaction`, `wrap_up` |

## Key Architecture Decisions

- **Operation IDs**: `Tracer.start_span()` returns a 16-hex-char `span_id`. Each span records `trace_id`, `span_id`, `parent_id`, `name`, `phase`, timestamps, `duration_ms`, `status`, `error`, `metadata`.
- **Automatic parent nesting**: `start_span()` auto-sets `parent_id` to the top of the internal `_stack` (the most recently started span) unless explicitly overridden. `end_span()` pops from the stack.
- **Context manager convenience**: `_SpanContext` in `agent.py` provides `with tracer.span("name", "phase") as s:` — auto-ends on block exit, setting status to "error" on exception.
- **Hook activity visibility**: Room surveys and hook-driven MUD commands are attributed to the turn via parent span ID. The database mutations they produce can be joined back to the relevant session.

## Key Findings

- The critical bug (per journal): `run()` was NOT passing `tracer=tracer` to the Agent constructor, so all production runs silently had no tracing. Only `repl()` worked correctly.
- Span hierarchy: `turn` → `llm_call` (parallel-level with `tool_loop` and `compaction`), `tool_loop` → `tool/{name}`.
- The `metadata` dict on each span allows attaching arbitrary key-value data at end time (e.g., `stop_reason`, `usage`, before/after token counts).

## Verification

```python
tracer = Tracer()
with tracer.span("test", "verify") as s:
    s.ok({"detail": "works"})
assert len(tracer.spans) == 1
assert tracer.spans[0].status == "ok"
```
