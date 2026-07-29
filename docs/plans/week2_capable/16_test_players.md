# Goal: Create populated test players and isolate their state

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/02_automatic_resets/player_reset.py` | `reset_player_to_start()` — uses admin character to move player to a target room |
| `week2_capable/bin/move_player_to_start_room` | Shell script that auto-starts the MUD daemon and runs the Python reset |
| `.boukensha/settings.yaml` | Credentials for admin and player characters |

## Key Architecture Decisions

- **Bash wrapper pattern**: `move_player_to_start_room` is a shell script that auto-starts the MUD daemon (with health-check polling, up to 10 retries) before calling the reset. This makes it usable as a standalone CLI tool.
- **Profile concept** (partially implemented): Named Boukensha profiles with separate databases and logs were designed, with `--profile` selection. In practice, only the `dummy` player with password `helloworld` is configured.
- **No formal seed_player script**: The player_reset logic handles positioning but not character creation or equipment seeding. Player level, money, stats, skills, inventory, and equipment seeding (as described in the plan) were not implemented in Python.

## Key Findings

- The admin `dummy` character is NOT an immortal in this MUD, so `goto` and `transfer` fail silently. The reset falls through to alternative syntax that may or may not work.
- Despite the unreliability, the reset works often enough for benchmark automation.
- The `admin_connected()` function provides a lightweight ping check that the benchmark uses to decide whether to skip reset if the daemon is down.

## Verification

```bash
cd week2_capable
python -c "from automatic_resets.player_reset import reset_player_to_start; reset_player_to_start('3001')"
```
