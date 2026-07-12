---
name: play-mud
description: Connect to tbaMUD on localhost:4000, execute commands, and maintain persistent memory for long-term goals
license: MIT
compatibility: opencode
---

## Overview
Connect to tbaMUD (CircleMUD) on localhost:4000 as player `dummy` / `helloworld` and drive toward long-term goals using persistent memory files.

## Quick Commands
```bash
# Run a command (auto-login, fresh connection each time)
python3 scripts/mud.py "<command>"
python3 scripts/mud.py "cmd1;cmd2;cmd3"
python3 scripts/mud.py "cmd1;cmd2" --wait 2.0

# With persistent memory (auto-loads/saves player.md and world.md)
python3 scripts/mud.py "score;look;eq" --data-dir ./data
```

## Memory System (data/player.md + data/world.md)
The `--data-dir ./data` flag enables persistent memory:
- **Before** execution: loads existing state from `data/player.md` and `data/world.md`
- **After** execution: auto-updates stats from `score` output and room info from `look` output
- Also saves `last_output.txt` for debugging

### How to use memory for long-term goals
1. Run `python3 scripts/mud.py "score;look;eq" --data-dir ./data` to start
2. After every action, **update the memory files yourself**:
   - `data/player.md` — track goals, sub-goals, quests, XP progress, equipment, inventory, learned spells/skills, faction standings, and notes about what you've tried
   - `data/world.md` — track explored areas, room connections, NPC locations, monster spawns, shop locations, quest markers, and loot spots
3. Before complex actions, check your goals in `data/player.md` and plan sub-goals
4. Reflect on what worked/didn't work and update notes

## Example workflow for reaching level 7
```
# 1. Check status and surroundings
python3 scripts/mud.py "score;look;eq;inv" --data-dir ./data
# Update data/player.md: add sub-goals (get weapon, train, find hunting spot)
# Update data/world.md: note room exits and NPCs

# 2. Explore toward hunting grounds
python3 scripts/mud.py "s;s;e" --data-dir ./data
python3 scripts/mud.py "look" --data-dir ./data
# Update data/world.md: map the area, note aggressive mobs

# 3. Fight and grind
python3 scripts/mud.py "kill mob" --data-dir ./data
python3 scripts/mud.py "get all;score" --data-dir ./data
# Update data/player.md: track XP, loot, HP/Mana after fight
# Update data/world.md: note good farming spots

# 4. Repeat until level 7, then pursue the specific monster
```

## Notes
- Logs in as `dummy` / `helloworld`
- Recovers from sleep/rest on login
- Strips ANSI codes from output
- Each invocation is a fresh connection
- Auto-parses `score` → `data/player.md` and `look` → `data/world.md`
- Agent should manually update Goals, Equipment, Inventory, Explored Areas, NPC info, and strategy notes
