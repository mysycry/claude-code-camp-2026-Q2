# Goal: Create populated test players and isolate their state

- Added bin/seed_player as a deterministic development harness.
- Deleted and recreated the configured player on every run.
- Added Mud Manager character-seeding and administrator primitives.
- Seeded level, money, stats, skills, inventory, and equipment.
- Verified the resulting character through live MUD output.
- Added optional fixture generation for parser development.
- Added named Boukensha profiles with separate databases and logs.
- Added --profile selection to Boukensha.
- Added a player-profile selector to Mud Monitor.
- Kept shared models, prompts, and installation settings outside profile state.
