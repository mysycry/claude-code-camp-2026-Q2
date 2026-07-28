# Goal: Expand player memory beyond basic vitals

- Extended the schema for score data, skills, inventory, and equipment.
- Captured live fixtures from a seeded level-10 cleric.
- Added parsers for score, practice, inventory, and equipment.
- Accounted for this MUD's actual wording instead of assumed CircleMUD formats.
- Reused already-issued commands to avoid extra network round trips.
- Marked inventory state stale when mutations could not be verified.
- Added a Player view under Knowledge.
