# Week 3 Multi-Agent Enhancements

Companion to `3_multi-agent.md`. That journal covers what was built during the
week; this file documents the reliability pass done afterwards — the changes,
why they were made, and how each piece works.

## Scope

| Enhancement | Files | What changed |
|---|---|---|
| Verified player reset | `resets/player_reset.py`, `agents/reset_agent.py` | Reset now verifies the room the player actually lands in and retries |
| DB-planned hunting route | `agents/worldnav.py`, `agents/grind_agent.py` | BFS over the offline world DB by room *name*; grind agent walks the route before DFS |
| Vitals polling | `agents/grind_agent.py` | Blind sleeps for HP/MV recovery replaced with polling helpers |
| Squad unit tests | `tests/` | 61 stdlib `unittest` tests across mudparse, bulletin, grind, worldnav, mission_control, daemon_manager, env loader |
| Deps manifest | `requirements.txt` | Single dep (PyYAML); everything else is stdlib or local |
| Env docs | `.env.example` | Documents every `*_*` override the squad reads |
| Project README | `README.md` | Architecture, quick start, ports, config, tests, known limitations |
| Span correlation | none (code already correct) | Verified sub-agent tool spans inherit the task's trace ID |
| Env loading | `agents/base.py` `load_env()` | Idempotent `.env` loader (`week3_multi-agents/.env`; existing env wins) |
| Daemon auto-start | `agents/daemon_manager.py` | Squad pings the MUD daemon and spawns it if missing/unresponsive |
| Daemon threading | `week1_baseline/ruby/10_standard_tool_library/lib/mud_daemon.rb` | Thread-per-connection + mutex so concurrent logins no longer wedge the daemon |
| Client port/timeouts | `week1_baseline/python/12_context/boukensha/tools/mud_client.py` | Lazy `_port_file()` resolution (no stale import-time cache), connect timeout 60s |
| Mission Control | `agents/mission_control.py` + integration | All 8 agents register/heartbeat on the MC dashboard (:3001), GET-first to dodge the 5/min rate limit |
| Agent Chat responder | `agents/chat_worker.py` | Polls each agent's task queue + chat messages and replies with live status; restart-safe via `.mud_manager/chat_worker_state.json` |
| MC client extras | `agents/mission_control.py` | `poll_queue()`, `update_task()` (`_put` with retry), `get_messages()`, `post_message()`, `_headers(agent=None)` |
| Sub-agent tool dispatch | `agents/base.py` | Fix: framework calls tools as `block(**kwargs)`, so sub-agents register a closure forwarding typed params to `_execute()` (was `block=lambda args=None` → `TypeError: unexpected keyword argument` on every option) |
| Dispatch regression tests | `tests/test_subagents.py` | 3 tests: typed kwargs, no args, per-agent binding |

## 9. Agent Chat responder + sub-agent tool dispatch

### Sub-agent tool dispatch bug

The squad run "reset me to the Temple" failed not because of a PORT_FILE
problem but because sub-agent tools are invoked as `block(**kwargs)`: the
framework unpacks the tool-call parameters into keyword arguments, but
`register_subagents()` had registered a bare `block=lambda args=None, _a=agent:`.
Any documented option (`start_room`, `action`, `target`, `steps`) then raised
`TypeError: unexpected keyword argument`, the manager fell back to manual MUD
navigation, and the player died in the Chessboard of Midgaard (lost ~5.7k XP,
level 5, 1/85 HP). `register_subagents()` now closes over the agent and
forwards typed params:

```python
def _subagent_block(agent):
    def block(**kwargs):
        return agent._execute(**kwargs)
    return block
```

Covered by `tests/test_subagents.py` (typed kwargs, no args, per-agent
binding); the full suite went to **69/69**.

### Why Agent Chat never answered

MC's Agent Chat writes `to_agent` messages into the `messages` table and hands
them to a gateway session for delivery. The squad runs no OpenClaw gateway, so
messages sat unclaimed — even though agents register/heartbeat for the
dashboard. Verified from the container's `openapi.json` and route sources that
the squad's generic REST path is fully capable: `GET /api/tasks/queue`,
`PUT /api/tasks/{id}`, `GET/POST /api/chat/messages`.

### What the worker does

- `MissionControlClient` grew `_put()`, `poll_queue()`, `update_task()`,
  `get_messages()`, `post_message()`.
- `chat_worker.py` polls each registered agent: claims queue tasks (marks them
  done with the status reply attached) and answers new `to_agent` chat
  messages in the same conversation.
- Replies are live: bulletin snapshot (L5, 5,772/26,228 XP, gold, HP, current
  room), MUD daemon ping through its port file, squad liveness from recent
  bulletin updates.
- Sender attribution: MC rewrites `from` to the authenticated API user, so a
  pure API key posts as "API Access"; the body is prefixed `[<agent>]` to make
  the speaker explicit.
- Restart-safe: seen message ids persist to
  `.mud_manager/chat_worker_state.json` (a one-time catch-up replies to the
  pre-existing unhandled messages on first boot, then never duplicates).
- Standalone: `python agents/chat_worker.py [--once] [--interval N] [--agents a,b]`.

### Auto-start with the squad

`chat_worker.py` gained a lifecycle layer mirroring `daemon_manager.py`:
`start_chat_worker()` spawns the worker as a **detached background process**
(`subprocess.Popen`, `CREATE_NO_WINDOW`, logging to
`.mud_manager/chat_worker.log`, PID in `.mud_manager/chat_worker.pid`), so it
keeps answering Agent Chat long after the squad run exits. `ensure_chat_worker()`
is idempotent (skips when the PID is alive; skips entirely when
`MC_ENABLED=false`) and is called best-effort from `squad.py` right after
`ensure_daemon()` — the squad now starts it automatically. A Git Bash helper
`agents/bin/run_chat_worker` ensures the daemon and runs the worker in the
foreground for manual use. Covered by `tests/test_chat_worker.py` (6 tests:
spawn writes pid file, spawn-when-down, skip-when-up, skip-when-MC-off,
spawn-failure reporting, status-reply fields).

Verified live: `ensure_chat_worker()` spawned pid 12228, a second call
reported "already running", and the background worker answered new Agent Chat
messages within one 5s poll cycle (including ones typed in the MC UI while it
ran).

Verified end-to-end live: posted a test message to `grind_agent`, one
`--once` pass replied with the live status report in conversation
`agent_grind_agent` (message ids 3-5), and a re-run made no duplicates.

### One test fix

`test_poll_queue_returns_claimed_task` asserted `req.get_header("x-agent-name")`
— but `urllib.request` headers given as a dict are matched case-sensitively
(`get_header` delegates to `dict.get`), so it returned `None` even though the
wire header `X-agent-name` was correct and the server accepts it fine. The
assert now inspects `req.header_items()` with a lowercase map.

## 1. Verified player reset

The old reset did `goto <vnum>` as an immortal admin, then `transfer` to pull
the player. Nobody confirmed where the player ended up. On the live server the
vnums don't match the offline world DB, so the player kept landing in
"The Great Field Of Midgaard" instead of the intended zone, and the grind/map
agents burned their whole budget crossing it.

`reset_player_to_start()` now has a `start_room_name` parameter and a
`max_attempts` retry loop:

1. Connect as admin, `goto <vnum>` (falling back to `@goto` if the first form
   doesn't answer).
2. `look` as admin and parse the room *name* to confirm where the admin is.
3. `transfer <player>`, then `look` again — the player lands in the admin's
   room, so this tells us where the player actually ended up.
4. If `start_room_name` is set and the name matches, return. If it doesn't
   match, retry. After `max_attempts`, raise a `RuntimeError` with a diagnostic
   that explains the vnum mismatch and points at the config keys.

New config (`.boukensha/settings.yaml`) and env overrides:

```yaml
reset:
  admin:
    username: <admin>
    password: <admin password>
  start_room: 3001          # vnum for goto
  start_room_name: "The Temple Of Midgaard"   # expected room NAME to verify
  max_attempts: 3
```

Env overrides: `RESET_START_ROOM`, `RESET_START_ROOM_NAME`,
`RESET_MAX_ATTEMPTS`. Verified with a fake-client unit harness (3 cases:
success with verified room; retry then `RuntimeError` on persistent mismatch;
success using config-only name). Live verification landed later once the
daemon could be restarted reliably (see §7/§8).

## 2. DB-planned hunting route (`worldnav`)

`agents/worldnav.py` is a pure-Python BFS over the offline world DB
(`memory_bench.db` — `world_rooms`, `world_exits`, `zone_mob_spawns`,
`world_mobs`), cached in a module-level `_GRAPH` after first load.

Key insight: because live-server vnums differ from the offline DB, routing is
done by **room name**, not vnum. `vnums_by_name(name)` finds candidate vnums,
`hunting_rooms(min_level, max_level)` finds rooms that spawn mobs in a level
band, and `bfs_route(start, targets)` returns the shortest direction list.
`route_to_nearest_hunt(start_vnum, player_level, level_band=3)` ties them
together: find the nearest room whose mobs are within
`[level-3, level+3]` of the player.

The grind agent's `_walk_toward_hunt(client, start)` uses it like this:

1. `score` the player to get level, and map the current room's *name* to
   candidate vnums.
2. Pick the shortest route to any huntable room across all candidates.
3. Walk the plan one direction at a time, parsing each live room.
4. If a live room's name doesn't match the plan step, **stop following the
   plan** and let the normal DFS take over from wherever we actually are.
   Doors are opened when movement reports blocked.

If the plan is unreachable or diverges immediately, the agent falls back to
the old DFS behavior, so a bad plan is a performance miss, not a failure.
Verified against the DB: Temple of Midgaard → nearest huntable mob (Grunting
Boar) routes in 3 steps.

## 3. Vitals polling instead of blind sleeps

`_recover_until(client, attr, target, interval, timeout, command)` is a
module-level helper that loops: send the rest/sleep command, sleep `interval`,
wake and stand, parse H/M/V, return when the target is reached or the timeout
expires.

- `_recover_hp()` — if HP < 50, rest until HP ≥ 75% of max (timeout 40s).
- `_recover_mv()` — if MV < 10, sleep until MV ≥ 50 (or max MV if lower;
  timeout 45s).

This replaced the previous hard `sleep(15)`/`sleep(8)` calls. Recovery now
stops the moment vitals are back, which is a real win given how slow MV regen
is, and it can't overshoot as badly as the fixed sleeps did. Both methods are
also what `_walk_toward_hunt` uses between plan steps.

## 4. Squad unit tests

Stdlib `unittest`, no pytest, no network, no live MUD. Run with:

```bash
python -m unittest discover -s tests -v   # or
python tests/run_tests.py                 # same, with exit code
```

61 tests across 7 files:

- `test_mudparse.py` (10) — ANSI stripping, exit/room-block parsing,
  entity classification, health extraction, score parsing.
- `test_bulletin.py` (6) — key-value round-trips, None-skipping, overwrite,
  delete, snapshot field mapping, event log. Patches `bulletin.DB_PATH` to a
  temp DB so tests never touch the real store.
- `test_grind.py` (14) — `_mob_alias` (articles stripped, first-3-words rule),
  `_room_key` name+exit-signature dedupe, mob filtering, kill detection
  (`You have slain` / `for the kill` / `receive` / fighting-gone checks).
- `test_worldnav.py` (6) — name→vnum lookup, route finding, huntability level
  filtering, unreachable returns `None`, no-move-when-already-at-target.
- `test_mission_control.py` (16) — GET-first registration reuse (never POSTs
  existing names), heartbeat/status payloads, retry counts (URLError, 500,
  401-not-retried, recovery after 503), `Retry-After` parsing, and that MC
  failures are swallowed.
- `test_daemon_manager.py` (8) — daemon ping, spawn on missing port file,
  ensure when reachable, failure propagation, port-file refresh.
- `test_env_loader.py` (1) — `load_env()` precedence (existing env wins),
  parsing, and idempotence.

## 5. Deps, env docs, README

- `requirements.txt` — just `PyYAML>=6.0`. The framework lives in
  `week1_baseline/python/12_context` (added to `sys.path` at runtime); the
  MUD daemon is Ruby; infra is Docker Compose. README's Quick start covers
  all three.
- `.env.example` — documents `MUD_HOST/MUD_PORT/MUD_USERNAME/MUD_PASSWORD`,
  `SQUAD_TASK/SQUAD_MODEL/SQUAD_PROVIDER/SQUAD_MAX_ITERATIONS/
  SQUAD_MAX_TURN_TOKENS/SQUAD_MEMORY_PATH/SQUAD_TRACE_DIR`, and
  `RESET_START_ROOM/RESET_START_ROOM_NAME/RESET_MAX_ATTEMPTS`.
- `README.md` — architecture diagram, quick start, ports table, config, Mission
  Control section, test commands, and a "Known limitations" section (live vnum
  mismatch + Mission Control rate limits).

## 6. Span correlation (verified, no code change)

Checked whether the manager's sub-agent calls produce traces under the parent
task. They do: sub-agents register as tools (`SubAgent` extends `base.py`'s
`Tracer`), the registry wraps each call as `tool/{name}`, and the wrapping
inherits the task's current `trace_id`, so every sub-agent span hangs off the
right root. Only `trace_agent` creates its own synthetic trace on purpose —
that's the "send a probe span and confirm it lands in Jaeger" test. No change
was needed.

## 7. `.env` loading, daemon auto-start, daemon/client reliability

### Env loading (`base.py::load_env`)

The squad previously relied on env vars being exported before `python
agents/squad.py`. Now `load_env()` (called at `agents.base` import) reads
`week3_multi-agents/.env`, with **existing environment winning** over the file
(so shell exports can override `.env`), and an `_LOADED_ENV` module flag so
importing the module multiple times is idempotent. Parsing handles blank
lines, `#` comments, and quotes. `.env` itself is gitignored; `.env.example`
documents every key including the MC block.

### Daemon auto-start (`daemon_manager.py`)

The "MUD is down" failure mode turned out to be a dead *Ruby control daemon*
while the tbaMUD game container stayed up. `ensure_daemon()` now recovers it
instead of erroring:

1. Ping the daemon via its port file (`.mud_manager/port`). If it answers,
   done.
2. If the port file is stale, remove it and spawn
   `week1_baseline/ruby/10_standard_tool_library/bin/mud_daemon`.
3. Wait for the daemon to write a fresh port (with a timeout), then re-ping.

### Daemon threading (`mud_daemon.rb`)

The daemon was a single-threaded accept loop: two concurrent clients could
stall the game response. It now spawns a thread per connection (mutex-guarded)
so concurrent logins no longer wedge it.

### Client port/timeout fixes (`mud_client.py`)

Two bugs made the client flaky:

- `PORT_FILE` was resolved at import time, **before** `squad.py` set
  `MUD_MANAGER_DIR` — so it pointed at the wrong path. Fixed by lazy
  `_port_file()` resolution in `__init__`.
- `recv_timeout` connect default raised from 30s to 60s for slow daemon
  startup.

### `squad.py` env ordering + encoding

`squad.py` sets `MUD_MANAGER_DIR`, `BOUKENSHA_DIR`, and
`BOUKENSHA_OTEL_ENABLED` via `os.environ.setdefault` **before** importing
`boukensha`, and reconfigures `sys.stdout`/`sys.stderr` to UTF-8 — the final
status print was crashing under Windows' cp1252 console because of a ✅ emoji.

## 8. Mission Control integration

See `docs/plans/week3_multi-agents/01_mission_control.md` for the full plan;
summary of what shipped:

- **Eager registration.** `register_subagents()` registers every sub-agent
  with MC at startup, so all 8 agents (manager + 7) appear on the board
  immediately — not just the ones the manager happens to call.
- **GET-first, rate-limit friendly.** MC caps `POST /api/agents/register` at
  **5/min per IP** (`selfRegisterLimiter`, confirmed from source). `register()`
  first GETs `/api/agents?limit=100` (cached 5s) and only POSTs names that
  don't already exist — repeat runs cost zero registration budget. Requests
  carry an `x-agent-name` header and `Retry-After`-aware backoff on 429/5xx.
- **Heartbeats.** Each agent heartbeats every 30s in a background thread
  (`MC_HEARTBEAT_INTERVAL`), reporting `busy`/`idle`/`error` status, git
  version, current task, and token usage. Verified live: 7 registers in 0.0s
  with no 429s on a warm board.
- **Best-effort.** Any MC failure is logged and swallowed (`MC_ENABLED=false`
  disables it). It's a dashboard, never a dependency.

## Verification

- `python -m compileall week3_multi-agents` — clean.
- `python -m unittest discover -s "week3_multi-agents\tests"` — 75/75 pass
  (61 baseline + `test_subagents.py` x3 + chat/task client tests +
  `test_chat_worker.py` x6 lifecycle/status-reply tests).
- All agent modules import successfully; memory server `/stats` healthy
  (world_rooms 1878, world_exits 4291); Grafana 13.1.1 healthy.
- `reset_player_to_start` exercised via fake-client harness — 3/3 cases pass.
- Live squad run (green): daemon auto-started on an empty port file (port
  58288), login as `dummy`, MC heartbeats flowing, Jaeger/Grafana verified.
- Mission Control board shows all 8 real agents (ids 1-7 + 16) with zero 429s;
  probe agents cleaned up via `DELETE /api/agents/{id}`.

## Remaining gaps

- The Great Field remains a slow crossing even with a planned route; a future
  fix would pick a start room that skips it entirely.
- A very large one-shot spawn of brand-new agent names could still brush the
  5/min MC registration limit; the `Retry-After` backoff covers it, but a
  queue/coalesce would be cleaner.
