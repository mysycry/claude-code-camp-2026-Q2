# Goal: Delegate room investigation so the player remains focused on orchestration

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/ruby/12_context/lib/boukensha/tasks/room_inspector.rb` | Delegated `room_inspector` task definition and system prompt |
| `week1_baseline/ruby/12_context/lib/boukensha/tools/agent_tools.rb` | `inspect_room` native tool that invokes the room_inspector task |

## Key Architecture Decisions

- **Sub-agent pattern**: The main agent (player) calls `inspect_room`, which spawns a child agent (room_inspector) with its own task and prompt scope. The child shares the parent's MCP/Telnet session — no second network connection needed.
- **Direct MUD tool access**: The inspector calls MUD tools (`look`, `exits`, `consider`, `examine`) directly rather than receiving pre-copied raw output from the parent. This keeps the child's context focused and avoids stale data.
- **Mob appraisal**: Added `consider` (assess mob difficulty by level/HP) and `examine` (detailed mob/object stats) to the inspection sequence.
- **Later removed**: The model-driven subagent was removed from the inspection path when deterministic processing (Step 10) proved faster and cheaper — zero LLM calls per room vs 30-35 seconds per room.

## Key Findings

- A full agent loop for every room inspection cost 30-35 seconds per room — far too slow for practical gameplay.
- Delegation introduced visibility gaps: the parent couldn't easily see what the child was doing, how long it took, or how many tokens it consumed.
- These visibility gaps directly drove the observability work (Step 08, Mud Monitor).

## Verification

```ruby
# Agent should be able to call inspect_room and get structured room data back
```
