# Boukensha Squad (week3_multi-agents)

A multi-agent system that plays a CircleMUD (tbaMUD) game server, runs an
observability stack (Jaeger + Grafana), and reports what it finds. A manager
agent (the "squad") delegates to specialized sub-agents, all built on the
Boukensha agent framework from `week1_baseline/python/12_context`.

## Architecture

```
┌──────────────┐   sub-agents registered as tools   ┌───────────────┐
│  Squad manager │ ─────────────────────────────────► │ sub-agents    │
│  (agents/squad)│                                    │ (agents/*)    │
└──────┬───────┘                                      └───────┬───────┘
       │                                                      │  MUD client
       ▼                                                      ▼
┌──────────────┐   SQLite (memory_bench.db)        ┌───────────────────┐
│ memory_server│ ◄─────────────────────────────────►│ tbaMUD on :4000  │
│ (HTTP :9876) │                                    └───────────────────┘
└──────┬───────┘
       │ data source
       ▼
┌──────────────┐  OTLP :4318 ──► Jaeger :16686 ──► Grafana :3000
│  Grafana     │
└──────────────┘
```

- **`agents/`** — the squad manager (`squad.py`, `base.py`) and sub-agents:
  - `mission_control.py` — Mission Control REST client (register/heartbeat, retries)
  - `daemon_manager.py` — auto-starts the MUD Ruby daemon if it's down (ping → spawn → re-ping)
  - `connection_agent.py` — MUD reachability checks
  - `reset_agent.py` — moves the player to a verified start room via an admin char
  - `map_agent.py` — bounded DFS exploration + hunting-spot reports
  - `grind_agent.py` — walks to a hunting zone (DB-planned route) and fights mobs
  - `observability_agent.py` — checks Jaeger/Grafana health and service stats
  - `trace_agent.py` — synthetic trace to verify the OTLP pipeline
  - `grafana_agent.py` — dashboard/datasource checks
- **`memory/`** — `memory_server.py` (HTTP API, port 9876), `memory_hook.py`
  (parses MUD output into the store), and `memory_bench.db` (the shared SQLite DB:
  player state, world data, token usage, traces).
- **`resets/player_reset.py`** — admin-based reset with post-transfer verification.
- **`grafana/`** — provisioned datasources, dashboards, and provider config.
- **`bin/`** — launchers (`memory_ui`, `move_player_to_start_room`).
- **`tests/`** — unit tests (stdlib `unittest`; no extra deps required).

## Quick start

```bash
# 1. deps
pip install -r requirements.txt

# 2. infrastructure (MUD + observability + Mission Control)
docker compose -f docker-compose.yml up -d        # jaeger + grafana + mission-control (:3001)
ruby ../week1_baseline/ruby/10_standard_tool_library/bin/mud_daemon &   # MUD daemon
python memory/memory_server.py &                  # memory HTTP server

# 3. configure Mission Control
cp .env.example .env                              # then set MC_API_KEY (Settings > API Key)
# MC_ENABLED=true MC_URL=http://localhost:3001 MC_API_KEY=<key>

# 4. run the squad (auto-starts the MUD daemon if it's down)
python agents/squad.py "Go check the MUD, fight something, and report."
# or via launcher:
bash bin/run_squad "Go check the MUD, fight something, and report."
```

The MUD Ruby daemon is auto-started by `daemon_manager.ensure_daemon()` on every
squad run: if the port file is missing or unresponsive it spawns
`week1_baseline/ruby/10_standard_tool_library/bin/mud_daemon`, waits for it to
write a port, and re-pings — so a down daemon is recovered, not an error.

## Ports

| Service        | Address                       |
|----------------|-------------------------------|
| MUD (tbaMUD)   | `localhost:4000`              |
| MUD daemon     | repo `.mud_manager/port`      |
| Memory server  | `localhost:9876`              |
| Jaeger UI      | `localhost:16686`             |
| OTLP (traces)  | `localhost:4318` (HTTP) / `4317` (gRPC) |
| Grafana        | `localhost:3000`              |
| Mission Control| `localhost:3001`              |
| Log viewer     | `localhost:4567`              |

## Configuration

- **`agents/squad.yaml`** — squad model/provider/limits, MUD, Jaeger, Grafana,
  and the `mission_control:` block (`enabled`, `url`, `api_key`,
  `heartbeat_interval`).
- **`.boukensha/settings.yaml`** — MUD credentials + `reset:` block (admin creds,
  `start_room`, verified `start_room_name`, `max_attempts`).
- **`agents/base.py` `load_env()`** — reads `week3_multi-agents/.env` at import
  (existing env wins; idempotent) so shell exports beat the file.
- **Environment overrides** (see `.env.example`):
  - `MUD_HOST` / `MUD_PORT` / `MUD_USERNAME` / `MUD_PASSWORD`
  - `SQUAD_TASK` / `SQUAD_MODEL` / `SQUAD_PROVIDER` / `SQUAD_MAX_ITERATIONS` /
    `SQUAD_MAX_TURN_TOKENS` / `SQUAD_MEMORY_PATH` / `SQUAD_TRACE_DIR`
  - `RESET_START_ROOM` / `RESET_START_ROOM_NAME` / `RESET_MAX_ATTEMPTS`
  - `MC_ENABLED` / `MC_URL` / `MC_API_KEY` / `MC_HEARTBEAT_INTERVAL` /
    `BOUKENSHA_VERSION`

## Mission Control

All 8 agents (manager + 7 sub-agents) self-register on squad startup and
heartbeat in the background (`mission_control.py`):

- **Eager registration.** Every sub-agent registers the moment it's added to
  the tool registry (`base.register_subagents`), so the board shows the full
  squad immediately — not only the agents the manager happens to call.
- **GET-first, rate-limit friendly.** Mission Control limits agent registration
  to 5/min per IP, so `register()` first fetches `/api/agents` and only POSTs
  names that don't already exist. Requests carry an `x-agent-name` header and
  `Retry-After`-aware backoff on 429/5xx.
- **Status mapping.** Each agent reports `busy` while running, `idle` when done,
  and `error` on exception; the manager (`squad_manager`) registers in `squad.py`
  and its own heartbeat includes the task and git-version.
- **Best-effort.** Any MC failure is logged and swallowed — Mission Control is a
  dashboard, never a dependency (`MC_ENABLED=false` disables it entirely).
- **Agent Chat responder.** `chat_worker.py` makes the squad answer Agent Chat
  messages and task-queue assignments itself (MC expects an OpenClaw gateway
  session, which the squad doesn't run). It polls each agent's queue + messages
  and posts a live status reply (bulletin player snapshot, MUD daemon health,
  squad liveness) to the same conversation. It auto-starts with the squad
  (`squad.py` → `ensure_chat_worker()`, a detached background process that
  survives the run) or can be launched by hand:
  `python agents/chat_worker.py` (or `--once` for a single pass; on Git Bash,
  `agents/bin/run_chat_worker`). Seen-message IDs persist to
  `.mud_manager/chat_worker_state.json` and the PID to
  `.mud_manager/chat_worker.pid`, so restarts never double-reply or double-spawn.

## Tests

```bash
python -m unittest discover -s tests -v     # stdlib runner
python tests/run_tests.py                   # same, with exit code
```

## Known limitations

- **Live vnums ≠ offline world DB.** The admin reset uses `goto <vnum>`; the
  live server's room vnums can differ from the offline world files, so the reset
  verifies the room *name* after transfer and retries. Configure
  `reset.start_room_name` to match your server.
- **Mission Control rate limits.** Agent registration is limited to 5/min per
  IP; the client GETs the existing agent list first so repeat runs don't burn
  the budget. A very large one-shot spawn of brand-new agents may still need the
  `Retry-After` backoff to settle.
- Grinding assumes the character can fight the targeted mobs; use `consider` /
  level-aware mob filtering before committing to a hunt.
