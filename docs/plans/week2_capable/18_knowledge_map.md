# Goal: Add a map of what the agent currently knows

- Added /knowledge/map to Mud Monitor.
- Built the map entirely from the existing knowledge endpoint.
- Positioned connected rooms using deterministic grid-based BFS layout.
- Displayed room names, internal IDs, visits, entities, and look targets.
- Highlighted the current room.
- Rendered explored connections and unexplored frontiers differently.
- Added zooming, panning, disconnected-component handling, and layout tests.
- Exposed malformed exit-direction data discovered during visualization.
