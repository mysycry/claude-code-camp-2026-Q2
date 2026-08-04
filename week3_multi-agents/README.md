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

# 2. infrastructure (MUD + observability)
docker compose -f docker-compose.yml up -d        # jaeger + grafana
ruby ../week1_baseline/ruby/10_standard_tool_library/bin/mud_daemon &   # MUD daemon
python memory/memory_server.py &                  # memory HTTP server

# 3. run the squad
python agents/squad.py "Go check the MUD, fight something, and report."
# or via launcher:
bash bin/run_squad "Go check the MUD, fight something, and report."
```

## Ports

| Service        | Address                       |
|----------------|-------------------------------|
| MUD (tbaMUD)   | `localhost:4000`              |
| MUD daemon     | repo `.mud_manager/port`      |
| Memory server  | `localhost:9876`              |
| Jaeger UI      | `localhost:16686`             |
| OTLP (traces)  | `localhost:4318` (HTTP) / `4317` (gRPC) |
| Grafana        | `localhost:3000`              |
| Log viewer     | `localhost:4567`              |

## Configuration

- **`agents/squad.yaml`** — squad model/provider/limits, MUD, Jaeger, Grafana.
- **`.boukensha/settings.yaml`** — MUD credentials + `reset:` block (admin creds,
  `start_room`, verified `start_room_name`, `max_attempts`).
- **Environment overrides** (see `.env.example`):
  - `MUD_HOST` / `MUD_PORT` / `MUD_USERNAME` / `MUD_PASSWORD`
  - `SQUAD_TASK` / `SQUAD_MODEL` / `SQUAD_PROVIDER` / `SQUAD_MAX_ITERATIONS` /
    `SQUAD_MAX_TURN_TOKENS` / `SQUAD_MEMORY_PATH` / `SQUAD_TRACE_DIR`
  - `RESET_START_ROOM` / `RESET_START_ROOM_NAME` / `RESET_MAX_ATTEMPTS`

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
- **Windows Ruby.** Fresh Ruby processes may fail to load `enc/encdb.so` if a
  Windows Application Control policy blocks it; launch the daemon/MCP server
  through the environment that already has a working Ruby process (e.g. the
  opencode MCP config) or repair the Ruby install.
- Grinding assumes the character can fight the targeted mobs; use `consider` /
  level-aware mob filtering before committing to a hunt.
