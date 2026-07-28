# Goal: Add lifecycle control and memory so inspection is enforced by the loop

- Added generic lifecycle hooks around turns and tool calls.
- Added automatic room surveying before model calls.
- Added a SQLite knowledge store using WAL mode.
- Added tables for player state, rooms, exits, entities, sightings, and encounters.
- Added room fingerprinting and exit linking.
- Added current-location tracking and visit counts.
- Added frontier tracking for exits that had been seen but not walked.
- Injected a compact [here] state block before each model call.
- Replaced large raw room outputs with condensed movement and state summaries.
- Added stale-state handling and survey rules after movement.
