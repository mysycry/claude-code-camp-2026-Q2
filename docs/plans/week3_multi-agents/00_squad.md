# Goal: Multi-agent squad on the Boukensha framework

Turn the single Week 2 agent into a manager + specialists squad that plays
tbaMUD, with a live player-status dashboard. A manager agent decides what to
do; a set of sub-agents each handle one specific thing; a shared bulletin
board feeds Grafana.

## Files

| File | What It Does |
|------|-------------|
| `week3_multi-agents/agents/base.py` | `SubAgent` base class (name, description, typed `parameters`, `run()`), `register_subagents()` (eagerly registers every sub-agent with Mission Control), `load_env()` (idempotent `.env` loader), `_summary()` result formatter |
| `week3_multi-agents/agents/squad.py` | Squad manager — `run_squad(task, ...)` loads config/system prompt, registers the manager with Mission Control, auto-starts the MUD daemon, and calls `boukensha.run()` with a block that registers all sub-agents as tools |
| `week3_multi-agents/agents/mission_control.py` | Mission Control REST client — register/heartbeat/status, GET-first registration (avoids 5/min IP rate limit), `Retry-After`-aware backoff, `x-agent-name` header, `ManagedAgent`/`HeartbeatThread` |
| `week3_multi-agents/agents/daemon_manager.py` | Auto-starts the Ruby MUD daemon — ping → remove stale port file → spawn `mud_daemon` → wait for port → re-ping with retries |
| `week3_multi-agents/agents/system.md` | Manager system prompt — which sub-agent to call for which request, default flow (connection → reset → map → grind) |
| `week3_multi-agents/agents/connection_agent.py` | Checks MUD daemon up, server reachable, player can log in |
| `week3_multi-agents/agents/reset_agent.py` | Moves player to a start room via admin char, verifies room name, retries |
| `week3_multi-agents/agents/map_agent.py` | Bounded DFS exploration, room graph, hunting-spot reports |
| `week3_multi-agents/agents/grind_agent.py` | Walks to a hunting zone and fights mobs; looting + vitals recovery |
| `week3_multi-agents/agents/observability_agent.py` | Checks Jaeger OTLP/UI/API, Grafana UI/API, docker compose containers |
| `week3_multi-agents/agents/trace_agent.py` | Sends a synthetic OTLP span and verifies Jaeger stored it |
| `week3_multi-agents/agents/grafana_agent.py` | Checks datasource provisioned + dashboard JSONs exist |
| `week3_multi-agents/agents/bulletin.py` | Shared SQLite store: key-value `player_state` + append-only `player_events` |
| `week3_multi-agents/agents/mudparse.py` | Parser: ANSI strip, exits, room blocks, entity classify, health, score |
| `week3_multi-agents/agents/worldnav.py` | BFS over offline world DB by room *name* for hunting-route planning |
| `week3_multi-agents/memory/memory_server.py` | HTTP server on 9876 serving player state, events, world data, token usage |
| `week3_multi-agents/resets/player_reset.py` | Admin-based reset with post-transfer room verification + retry |
| `week3_multi-agents/grafana/dashboards-json/bulletin-board.json` | Live player-status dashboard |
| `week3_multi-agents/docker-compose.yml` | Jaeger all-in-one + Grafana with Infinity plugin + Mission Control (:3001) |
| `week3_multi-agents/tests/` | 61 stdlib `unittest` tests (mudparse, bulletin, grind, worldnav, mission_control, daemon_manager, env loader) |

## Key Architecture Decisions

- **Sub-agent = tool.** Each `SubAgent` subclass exposes `run(**kwargs)` and is
  registered with the existing Boukensha registry via `register_subagents()`
  → `registry.tool(name, description, parameters, block)`. No core-loop
  changes. The manager delegates by tool call exactly like any other tool.
- **Manager is thin.** `squad.py` decides which sub-agent handles a request
  and interprets the report; it never connects to the MUD itself. The system
  prompt encodes routing rules and a default flow for "play the game".
- **Bulletin board as shared state.** Agents write snapshots via
  `post_player_snapshot(score, location, kill, destination, note)` into
  SQLite (`player_state` keys + `player_events` log). The memory HTTP server
  serves `/player-state` (flat JSON, numeric coercion) and
  `/player-events?limit=N` to Grafana's Infinity datasource.
- **World routing by name, not vnum.** Live-server vnums differ from the
  offline DB, so `worldnav` maps the current room *name* to candidate vnums,
  BFS on the offline graph, and returns directions. The grind agent walks the
  plan verifying each live room name; on divergence it falls back to DFS.
- **Self-verifying reset.** After `goto`/`transfer`, the admin `look`s and
  parses the room *name*; mismatch → retry (up to `max_attempts`), persistent
  failure → `RuntimeError` with a diagnostic pointing at config keys.
- **Poll instead of sleep.** `_recover_until()` re-checks H/M/V every 3s and
  stops at the target instead of blind `sleep(15)`/`sleep(8)`.
- **Offline tests.** Everything under `tests/` runs without a live MUD;
  `bulletin.DB_PATH` is patched to a temp DB.

## Key Findings

- A sub-agent is just a tool as far as the framework is concerned — no changes
  to `boukensha.run()` were needed for multi-agent orchestration.
- The grind agent's zero-kill bug was two compounding bugs: a broken
  article-stripping regex (`"a goblin"`), and a fight-completion check that
  looked for the original entity line which disappears during combat.
- The reset dropping the player in "The Great Field Of Midgaard" is a live
  vnum vs offline DB mismatch; the fix keys rooms by name + exit signature and
  verifies the post-reset room name.
- Movement regen is the real bottleneck (each small regen ~18-20s); vitals
  polling and smaller room budgets are what make grinding feasible.
- Trace data was never missing; the Jaeger UI default 1-hour lookback hid
  traces older than that.
- "MUD down" usually means the *Ruby control daemon* is dead while the game
  container is up; `daemon_manager.ensure_daemon()` recovers it instead of
  erroring. The daemon needed a thread-per-connection model (concurrent
  logins wedged the old accept loop), and `mud_client.py` had a stale
  import-time `PORT_FILE` (fixed with lazy resolution).
- Mission Control limits registration to 5/min per IP; GET-first registration
  makes repeat squad runs cost zero budget, so all 8 agents appear eagerly.

## Verification

```bash
cd week3_multi-agents
python -m compileall week3_multi-agents
python -m unittest discover -s tests -v          # 61 tests pass
python agents/squad.py "Go check the MUD, fight something, and report."
# Grafana :3000/d/boukensha-bulletin → live player state
# Jaeger :16686 → boukensha service spans
# Mission Control :3001 → all 8 agents registered, heartbeats flowing
```
