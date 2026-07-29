# Goal: Capture changes over time instead of storing only the latest state

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/python/12_context/boukensha/logger.py` | Append-only JSONL logger — 14 event phases, before/after tracking in compaction events |

## Key Architecture Decisions

- **Append-only JSONL format**: Each event is a JSON object on a single line appended to `sessions/{session_id}.jsonl`. The file is opened once when the session starts and kept open for the duration.
- **14 event phases**: `session_start`, `turn`, `iteration`, `limit_reached`, `turn_end`, `prompt`, `compaction`, `tool_call`, `tool_result`, `response`, `reasoning`, `plan`, `raw` (debug-only).
- **Before/after tracking**: Compaction events record `before` token count, `dropped` message count, and `context_window`. Turn_end events record `iterations` used and `tokens` consumed. The snapshot at `session_start` captures configured limits as a baseline.
- **`subscribe(callback)`**: Allows real-time forwarding of events to stdout, a websocket, or external analysis tools without coupling the logger to any particular consumer.
- **Sequence numbers and timestamps**: Each event carries an ISO timestamp and session ID, enabling chronological ordering and session attribution across restarts.

## Key Findings

- The logger captures before/after values while suppressing unchanged writes — only actual mutations produce events.
- The `raw()` method is gated by a module-level `_boukensha_debug` flag — not normally emitted to avoid noise.
- Session IDs use the format `YYYYMMDDTHHMMSSZ-{8 hex chars}` for human-readable chronological sorting.
- Change journal events can be joined back to the relevant session via session_id, enabling traceability from knowledge-store writes to the agent turn that produced them.

## Verification

```python
from boukensha.logger import Logger
log = Logger("test_session")
log.log("tool_call", {"name": "move", "args": {"direction": "north"}})
# Verify JSONL file contains the event
```
