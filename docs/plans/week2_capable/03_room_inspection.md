# Goal: Collect complete room information before choosing the next movement

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/ruby/12_context/lib/boukensha/tools/mud.rb` | `look` tool (lines 131-147), `check kind: "exits"` tool (lines 162-175) |
| `week1_baseline/ruby/12_context/prompts/system.md` | System prompt encoding the inspection policy |

## Key Architecture Decisions

- **Composite inspection**: The agent was instructed to always `look` at a room first (gets exit directions, room description, entities), then call `exits` to get destination room names. These two calls together provide complete navigation information.
- **What was inspected per room**: Room description (from `look`), exit directions + destination names (from `exits`), entities/mobs/players present, hidden scenery, player vitals (HP/mana/moves), and asynchronous room activity (combat ticks).
- **Initial approach**: The LLM decided what to inspect — this was agentic, slow (30-35s/room), and expensive. Later replaced with deterministic surveying (Step 10).
- **Policy encoding**: The "look then check exits" behavior was encoded in the system prompt as agent policy, not as hardcoded logic.

## Key Findings

- `look` only provides exit *directions* (north, south, east, west), not destination room names.
- The `exits` MUD command provides destination names (e.g., `north - The Temple Of Midgaard`).
- Both commands are needed for complete spatial awareness.
- The agentic approach (LLM deciding per-room what to inspect) was too slow and expensive for practical use.

## Verification

```ruby
# In a Boukensha session:
# Agent should call look, then exits before moving to a new room
```
