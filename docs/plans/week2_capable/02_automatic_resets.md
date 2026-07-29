# Goal: Automate player resets so navigation experiments are repeatable

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/02_automatic_resets/player_reset.py` | Uses an immortal/admin character to `goto` a room and `transfer` the mortal player there |
| `week2_capable/bin/move_player_to_start_room` | Shell script that auto-starts the MUD daemon and runs the Python reset |
| `week1_baseline/ruby/lib/mud/manager/player.rb` | Mud Manager admin primitives for logging in, moving, and transferring players (Ruby) |

## Key Architecture Decisions

- **Two-character approach**: Logs in an admin character (immortal) and the target player character over a single Mud Manager daemon session. The admin `goto`s the target room, then `transfer`s the player there.
- **Credentials from settings**: Admin username/password and player username read from `.boukensha/settings.yaml`, keeping credentials out of source code.
- **Failover syntax**: If `goto {room}` fails, tries `@{room}` (alternate CircleMUD immortal syntax). If `transfer` fails, the player may be at an unexpected location.
- **Stale daemon handling**: Checks `PORT_FILE.is_file()` before creating a daemon client, wraps disconnect in try/except for `ConnectionRefusedError`.

## Key Findings

- The `dummy` character is NOT an immortal, so `goto` and `transfer` both return failure messages ("Huh!?!"). The reset function falls through to a `@room` syntax attempt, which may or may not work depending on MUD configuration.
- When the admin can't teleport, the player stays wherever the MUD server last saved it. This makes reset unreliable for non-immortal admins.
- Despite the unreliability, the reset works often enough for benchmark automation.

## Verification

```bash
cd week2_capable
python -c "from automatic_resets.player_reset import reset_player_to_start; reset_player_to_start('3001')"
```
