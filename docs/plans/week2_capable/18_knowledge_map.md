# Goal: Add a map of what the agent currently knows

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/python/12_context/boukensha/memory.py` | `find_path()` (BFS shortest path, lines 230-260), `rooms_nearby()` (bidirectional BFS, lines 262-296), `pathfinding_block()` (text navigation hints) |

## Key Architecture Decisions

- **Text-based map, not graphical**: The Python implementation generates a text-based navigation hints block (`[paths]`) injected into the system prompt, not a rendered graphical map. The block lists up to 5 nearby destinations with direction arrows.
- **BFS pathfinding**: `find_path()` builds a directed graph from walked exits (`walked=1` and `to_room IS NOT NULL`) and runs BFS up to `max_depth=20`. Only verified connections are used — seen-but-not-walked exits are excluded.
- **Bidirectional rooms_nearby**: `rooms_nearby()` treats the graph as undirected (computing reverse directions via `_reverse_dir()`), finding rooms within `max_hops=3`. Returns `{room_name: [directions]}`.
- **Ruby Mud Monitor map**: The Ruby version (`week1_baseline/log_viz/`) includes a Sinatra web app with a graphical map using deterministic grid-based BFS layout, showing room names, IDs, visits, entities, and explored vs unexplored frontiers.

## Key Findings

- `find_path()` only uses walked exits, so it only shows routes the agent has actually traveled.
- `rooms_nearby()` treats the graph as undirected, which may be incorrect for one-way exits but works acceptably for well-designed MUD areas.
- No graphical map visualization was built in Python. The room graph exists purely in SQLite and is consumed through text prompts and the Memory API.

## Verification

```python
from boukensha.memory import MemoryStore
store = MemoryStore(":memory:")
store.record_room("r1", "Room A"); store.record_room("r2", "Room B")
store.record_exit("r1", "east", dest_room="r2", walked=True)
assert store.find_path("r1", "r2") == ["east"]
```
