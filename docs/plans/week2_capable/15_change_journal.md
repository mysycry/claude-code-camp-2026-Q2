# Goal: Capture changes over time instead of storing only the latest state

- Added an append-only JSONL change journal.
- Captured every knowledge-store mutation at the store layer.
- Recorded before/after values while suppressing unchanged writes.
- Captured room, exit, entity, encounter, player, death, level-up, and item events.
- Added sequence numbers, timestamps, session attribution, and restart continuity.
- Added a Progression view with time-series charts and a raw change log.
- Captured changing HP, mana, and movement values instead of pre-filtering them.
