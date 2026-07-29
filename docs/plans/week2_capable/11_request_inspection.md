# Goal: Expose exactly what the model consumes on every request

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/ruby/12_context/lib/boukensha/logger.rb` | Records every event as JSONL with full message snapshots and token usage |
| `week1_baseline/ruby/12_context/lib/boukensha/backends/base.rb` | `estimate_cost()` computes cost estimates from per-model token pricing (lines 77-82) |
| `week1_baseline/log_viz/lib/log_viz/session.rb` | Parses JSONL session logs into structured entries with token counts, cost breakdowns, usage series, and turn-level rollups |

## Key Architecture Decisions

- **Log reconstruction, not re-instrumentation**: All the data needed for request inspection was already being logged by Boukensha's structured logger. The missing piece was the visualization layer — no new instrumentation was needed.
- **Full message timeline**: The `prompt` event records the complete message list (system, user, assistant, tool messages) and tool list sent to each LLM call. This allows reconstructing the exact prompt the model received.
- **Lifecycle tracking**: The viewer handles normal message additions, compaction (dropped old messages), and cleared histories (`/clear`).
- **Injected context visibility**: Previously invisible auto-injected context blocks (`[here]`, `[paths]`) are surfaced in the message timeline.

## Key Findings

- The existing JSONL log format was sufficient for full request reconstruction — no schema changes needed.
- Token counts are available per message and per request section, enabling detailed cost breakdowns.
- Compaction events are visible in the timeline, showing when context window pressure causes old messages to be dropped.
- The `_serialize_message()` helper only extracts `role` and `content` from Message objects (not `tool_use_id`), so tool result routing information is not directly visible in the log.

## Verification

```ruby
# Open a session log in Mud Monitor and verify the message timeline shows:
# - System prompt
# - Each user/assistant/tool exchange
# - Token counts per message
# - Compaction events
# - Injected context blocks
```
