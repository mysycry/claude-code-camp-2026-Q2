# Python MUD Grinder — Design Plan

## Goal

A rule-based Python script that uses the existing daemon pipeline to automatically hunt mobs, gain XP, and level up in tbaMUD. It must produce real token-usage data for the Grafana dashboards (a side effect of running alongside the agent, but useful for benchmarking).

## Architecture

```
mud_grinder.py
├── GrinderClient (wraps MudDaemonClient)  — TCP/NDJSON to Ruby daemon
├── WorldDB (reads memory_bench.db)        — static map data for pathfinding
├── Navigator (BFS on world_exits)          — plan + follow a route to a hunting zone
└── Grinder (main loop)                    — look → kill → loot → heal → repeat
```

## Hunting Zone Selection

### Primary: Newbie Zone (zone 186, rooms 18600–18699)

- **Access**: 5 rooms north of Temple Of Midgaard (start room 3001):
  `north → 3054 → north → 3059 → north → 3060 → north → 3061 → east → 18600`
- **Mobs**: L1 creepy crawler (xp=100), L1 clueless newbie (xp=220, gold=50), L2 newbie monster (xp=400)
- **Patrol rooms** (shuffle between these for respawns):
  - 18602 (The Dirty Hallway) — 1× creepy crawler L1
  - 18606 (A Small Room) — 1× creepy crawler L1 + 1× Newbie Guard L3
  - 18609 (The End Of The Passage) — 1× creepy crawler L1
  - 18642 (The North Stairs) — 1× clueless newbie L1 (xp=220, gold=50)
  - 18600 (The Entrance) — 1× newbie monster L2 (xp=400)
  - 18607 (More Of The Hallway) — 1× newbie monster L2 (xp=400)
  - 18646 (A Bright Hallway) — 1× annoying newbie L2 (xp=500)

### Fallback: Sewer, First Level (zone 70)

- **Access**: 5–6 rooms then `down` from Temple (via Dump at 3025→3030→down)
- **Mobs**: L1 small bat (AGGRESSIVE, xp=150), L1 small Spider (AGGRESSIVE, xp=100)
- Aggressive mobs attack on sight — less navigation needed

## Mob Parsing Strategy

From the MUD output of `look`, scan lines matching:
```
<words> is here.
<words> is standing here.
<words> is lying here.
<words> is resting here.
<words> is sitting here.
```
- Filter out: `(party member)`, shopkeepers, guildmasters, quest-target tags
- Extract keywords (last 1–2 words of the name before `is`)
- Prefer attacking mobs by their first keyword alias (e.g., `crawler` for `the creepy crawler`)

## Combat Loop (per room)

```
while kills < target_kills or level < target_level:
  output = send("look")
  mobs = parse_mobs(output)
  if mobs:
    target = select_mob(mobs)  # prefer lowest-level first
    result = send(f"kill {target}")
    if "You receive" in result or "You have slain" in result:
      send("get all corpse")
      send("get all")
      send("wear all")
      if kills % 5 == 0:
        send("score")  # check level/XP progress
      kills += 1
    elif "miss" in result or "dodge" in result:
      retry kill (up to 20 rounds)
    else:
      # mob not present or combat ended
      check_hp()
  else:
    move to next room in patrol list
  check_hp()
```

## Health Management

- After every kill (or every move), send `score`
- Parse: `You have (\d+)\((\d+)\) hit`
- If `current_hp < max_hp * 0.4`: `rest` for 3–5 seconds, then `stand`
- If `current_hp <= 0`: dead — log and stop

## Safe Navigation (fallback)

- Track the last 3 rooms visited to detect getting stuck
- If same room visited 3+ times without a kill, use BFS to replan to a known hunting room
- If all navigation fails, `send("recall")` to return to temple (if the character has recall)

## Token Usage Recording

- After each LLM turn in the benchmark (not in the grinder itself — the grinder is rule-based)
- The grinder is a companion to the benchmark: run benchmark → grinder exercises the agent → benchmark records token usage
- The grinder can optionally call `memory_hook` to record room visits in the MemoryStore

## Files

| File | Purpose |
|------|---------|
| `week2_capable/01_benchmark/mud_grinder.py` | Main Python grinder script |
| (reuses) `week1_baseline/python/12_context/boukensha/tools/mud_client.py` | Daemon TCP client |
| (reuses) `week2_capable/01_benchmark/memory_bench.db` | World data for pathfinding |

## Testing Plan

1. Connect to daemon, verify communication via `ping`
2. Navigate from Temple to Newbie Zone entrance
3. Kill 1 mob in room 18602 (creepy crawler)
4. Kill 5 mobs across patrol rooms
5. Verify HP tracking recovers via rest
6. Check XP/level tracking via score

## Future Extensions (not in v1)

- Agent-based grinding (LLM decides combat targets)
- Equipment optimization (buy better weapons)
- Multi-zone patrol (move to harder zones as level increases)
- Loot filtering (keep valuable items, drop junk)
