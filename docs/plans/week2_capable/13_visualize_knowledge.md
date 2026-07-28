# Goal: Visualize stored knowledge so memory behavior can be verified

- Added a Knowledge section to Mud Monitor.
- Added overview, rooms, entities, frontier, and player views.
- Read the live SQLite database without introducing ActiveRecord.
- Added WAL-aware freshness checks and schema-version handling.
- Displayed room confidence, visits, exits, entities, and survey times.
- Clarified that a frontier represents an unexplored exit, not an unexplored room.
