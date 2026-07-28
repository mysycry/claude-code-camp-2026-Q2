# Goal: Convert operation logs into structured traces

- Instrumented turns, iterations, LLM generation, tool execution, hooks, compaction, and wrap-up.
- Added nested span trees and duration waterfalls to Mud Monitor.
- Propagated trace context across MCP boundaries.
- Recorded errors and incomplete operations.
- Added a waterfall interface for understanding where each turn spent its time.
- Preserved detailed JSONL logs alongside the new trace structure.
