# Goal: Mission Control as the squad operations panel

Give the Boukensha squad a single self-hosted "center of operations":
online/offline per agent, what each is doing right now, version, tool calls,
token usage, and task/event history — all in one panel.

## Context

Today the squad is observable only indirectly:

- Jaeger shows span trees (tools invoked, trace relationships).
- The bulletin board shows the *player's* state (level/gold/XP/location).
- Nothing answers "is `grind_agent` alive right now?", "which version is
  running?", or "what is it doing at this instant?".

Mission Control (builderz-labs/mission-control, MIT, self-hosted, SQLite)
provides exactly that layer: agent registration, heartbeats/liveness,
sessions, tasks, activity stream, token/cost views, RBAC, and a web dashboard.
It is alpha software; adapters exist for OpenClaw/Claude Code/Codex/CrewAI/
LangGraph/AutoGen/Claude SDK and a generic fallback — the squad connects via
the authenticated REST API (generic path), so no framework rewrite is needed.

## Files

| File | What It Does |
|------|-------------|
| `week3_multi-agents/agents/mission_control.py` | REST client + heartbeat loop: GET-first register, heartbeat, status/version/current task, token usage, `Retry-After`-aware retries |
| `week3_multi-agents/agents/base.py` | `load_env()` (.env loader); `SubAgent._mc_managed()` register + heartbeat thread; `_execute()` marks busy/idle/error; `register_subagents()` eagerly registers every sub-agent |
| `week3_multi-agents/agents/squad.py` | Registers `squad_manager` with MC; auto-starts the MUD daemon via `ensure_daemon()` |
| `week3_multi-agents/agents/daemon_manager.py` | Ensures the MUD Ruby daemon is reachable, spawning it if not (ping → spawn → re-ping) |
| `week3_multi-agents/agents/squad.yaml` | `mission_control:` block: `enabled`, `url`, `api_key`, `heartbeat_interval` |
| `week3_multi-agents/agents/chat_worker.py` | Agent Chat responder. Polls each agent's task queue + incoming chat messages and posts a live status reply to the same conversation (bulletin player snapshot, MUD daemon health, squad liveness) |
| `week3_multi-agents/agents/base.py` `_subagent_block` | Fixes sub-agent tool dispatch: the framework invokes tools as `block(**kwargs)`, so each sub-agent now registers a closure that forwards typed params (`start_room`, `action`, `target`, `steps`) to `agent._execute()` instead of a `block=lambda args=None` that threw `TypeError` on every option |
| `week3_multi-agents/tests/test_subagents.py` | Regression tests for the tool-dispatch fix (typed kwargs, no args, per-agent binding) |
| `week3_multi-agents/.env.example` | `MC_URL`, `MC_API_KEY`, `MC_ENABLED`, `MC_HEARTBEAT_INTERVAL`, `BOUKENSHA_VERSION` |
| `week3_multi-agents/docker-compose.yml` | mission-control service (port 3001 — Grafana owns 3000) |
| `week3_multi-agents/tests/test_mission_control.py` | Unit tests with a mocked HTTP layer (no live MC needed) |
| `week3_multi-agents/tests/test_daemon_manager.py` | Daemon ping/start/ensure unit tests (mocked subprocess/socket) |
| `week3_multi-agents/tests/test_env_loader.py` | `load_env()` parsing, precedence, idempotence |
| `docs/plans/week3_multi-agents/01_mission_control.md` | This plan |

## Key Architecture Decisions

- **REST, not the MCP server or a custom adapter.** The documented agent loop
  is: `POST /api/agents/register` → `GET /api/tasks/queue` →
  `PUT /api/tasks/{id}` → `POST /api/agents/{id}/heartbeat`. The squad is a
  custom Python framework, so a small stdlib `urllib` client (mirroring the
  OTel exporter pattern — zero new deps) is the least invasive path.
- **Heartbeats drive liveness.** Each sub-agent posts a heartbeat every 30s in
  a background thread while the process is alive; MC flips it to `offline`
  after a missed window. Registration is idempotent (registering an existing
  name updates its status/last_seen and returns the existing id).
- **GET-first registration (rate-limit safety).** MC limits `POST
  /api/agents/register` to **5/min per IP** (`selfRegisterLimiter`). Since the
  squad always starts as a burst of 8 eager registrations, `register()` first
  `GET`s `/api/agents` and only POSTs names that don't already exist — repeat
  runs cost zero registration budget. Requests carry an `x-agent-name` header
  so per-agent limiter keys are honored.
- **Version + current task as heartbeat payload.** Include a `version` field
  (git short sha / `BOUKENSHA_VERSION`) and the current task string so the
  panel shows "what version, what doing now" without extra queries.
- **Token usage forwarded.** The squad already records per-model token usage in
  `token_usage`; the heartbeat posts `token_usage.model/inputTokens/
  outputTokens` so MC shows spend per agent. (Source of truth stays
  `memory_bench.db`.)
- **Busy/idle state mapping.** `SubAgent._execute()` marks `busy` on entry,
  `idle` on exit, `error` on exception. The manager (`squad.py`) registers
  `squad_manager` the same way.
- **Eager registration.** `register_subagents()` calls `_mc_managed()` on every
  sub-agent at tool-registration time, so all 8 agents appear on the board
  immediately — not only the ones the manager happens to call.
- **Port 3001.** Mission Control defaults to 3000 which collides with Grafana;
  remap to 3001 in compose.
- **Non-fatal.** `MC_ENABLED=false` or any MC error must not break the squad —
  all calls are try/except + logged. MC is a dashboard, not a dependency.

## Implementation Steps

1. **Deploy MC** — add a compose service for `ghcr.io/builderz-labs/
   mission-control:latest` on port 3001 with a persistent volume at `/app/.data`
   (the entrypoint's data dir; a bogus `MISSION_CONTROL_DATA_DIR` env caused a
   SQLite "unable to open database" on first boot). Seed admin via
   `AUTH_USER`/`AUTH_PASS`; the API key is auto-generated into
   `/app/.data/.generated-secrets` (or set `API_KEY` for a fixed key).
2. **Write `mission_control.py`** — `register()` (GET-first), `heartbeat()`,
   `set_status()`, `HeartbeatThread`, `ManagedAgent`, and `_post()/ _get()`
   with `Retry-After`-aware backoff on 429/5xx.
3. **Hook into `base.py`** — `load_env()` reads `.env` at import;
   `SubAgent._mc_managed()` registers lazily and starts the heartbeat thread;
   `_execute()` sets busy/idle/error around the body; `register_subagents()`
   eagerly registers all sub-agents.
4. **Config + env** — read `squad.yaml.mission_control` with `MC_*` env
   overrides; document in `.env.example`.
5. **Manager registration + daemon auto-start** — `squad.py` registers
   `squad_manager` and calls `daemon_manager.ensure_daemon()` before running.
6. **Tests** — mock the HTTP layer; assert register/heartbeat/status payloads,
   GET-first reuse, retry counts (URLError, 500, 401-not-retried, recovery
   after 503), and that failures are swallowed.
7. **Verify end-to-end** — run the squad, watch all 8 agents appear in MC with
   heartbeats and versions; kill the MUD daemon and confirm the squad
   auto-starts it.

## Key Findings (verified)

- **Rate limit confirmed from source.** `POST /api/agents/register` is guarded
  by `selfRegisterLimiter` = **5/min per IP**; the registration endpoint is
  idempotent for existing names (registering an existing agent returns its id
  without creating a duplicate). There is no `MC_DISABLE_RATE_LIMIT` knob for
  non-critical limiters — the GET-first strategy is the right call.
- **`role` is constrained.** `coder`, `reviewer`, `tester`, `devops`,
  `researcher`, `assistant`, `agent` — `ROLE_MAP` assigns squad agents
  accordingly (grind/map/connection/reset → `agent`, observability/trace →
  `devops`, grafana → `devops`, squad_manager → `agent`).
- **Name rules.** 1-63 chars, alphanumeric + `.`/`-`/`_`, start with letter/digit
  — all squad names comply.
- **`x-agent-name` header.** MC's rate limiter and idempotency key off the
  `x-agent-name` header; the client always sends it.
- **GET /api/agents paginates** (`limit`, `offset`); the client requests
  `limit=100` and caches the list for 5s to stay within budget during a burst.
- **Self-registration vs API-key registration.** `AUTH_USER`/`AUTH_PASS` seeds
  admin; agents that POST with `x-agent-name` but no `Authorization` use the
  self-registration path (rate-limited). The client still sends the API key on
  all requests so heartbeat/liveness count against the API-key quota, not the
  per-IP self-registration budget.
- **Secrets live in `/app/.data`.** The API key is generated into
  `.generated-secrets` on first boot unless `API_KEY` is set; the volume must
  persist.

## Agent Chat responder

Mission Control's Agent Chat drops messages addressed to an agent
(`to_agent`) into the `messages` table and hands them to a gateway session for
delivery — the squad runs no OpenClaw gateway, so nothing answered. The
`squad` still shows agents on the dashboard (register/heartbeat) but chat and
task-queue messages sat unclaimed.

The API contract (from the container's `openapi.json` + route sources):

- `GET /api/tasks/queue?agent=<name>` — claims `inbox`/`assigned` tasks for the
  agent (→ `in_progress`) and returns `{task, reason, agent}`; `reason` is
  `continue_current` | `assigned` | `at_capacity` | `no_tasks_available`.
- `PUT /api/tasks/{id}` — status/description/tags update.
- `GET /api/chat/messages?conversation_id&from_agent&to_agent&limit&offset&since`
  — returns `{messages: [{id, conversation_id, from_agent, to_agent, content, created_at}]}`.
- `POST /api/chat/messages {content, conversation_id?, recipient?}` — inserts
  `(conversation_id, from_agent, to_agent, content, ...)`; the sender comes
  from `x-agent-name`/auth, so MC rewrites `from` to the authenticated user
  (a pure API key shows up as "API Access"; the reply body is prefixed
  `[<agent>]` to identify the speaker).

`agents/chat_worker.py` makes the agents answer on their own behalf:

- Polls each agent's task queue and marks claimed tasks done, attaching the
  status reply to the task description/metadata.
- Polls incoming chat messages (`?to_agent=<name>`) and posts a reply to the
  same conversation.
- Reply content is live: bulletin player snapshot (level/XP/gold/HP/
  location), MUD daemon ping via its port file, and squad liveness.
- Restart-safe: seen message IDs persist to
  `.mud_manager/chat_worker_state.json`, so restarts never double-reply.

Run it (needs the MUD daemon up and `MC_ENABLED=true`):

```bash
cd week3_multi-agents
python agents/chat_worker.py            # watch all registered agents (5s poll)
python agents/chat_worker.py --once     # single pass, for testing
# agents/bin/run_chat_worker            # Git Bash helper: ensures daemon, runs in foreground
```

It also **auto-starts with the squad**: `squad.py` calls `ensure_chat_worker()`
after `ensure_daemon()`, spawning a detached background process
(`.mud_manager/chat_worker.log`, `.mud_manager/chat_worker.pid`) that keeps
answering after the squad exits. Idempotent — repeated runs/spawns reuse the
live process.

## Verification

```bash
cd week3_multi-agents
docker compose up -d                # includes mission-control on :3001
export MC_URL=http://localhost:3001 MC_API_KEY=<key>
python -m unittest tests/test_mission_control.py -v
python agents/chat_worker.py --once # replies to any unhandled Agent Chat messages
python agents/squad.py "Go check the MUD, fight something, and report."
# Open http://localhost:3001 → all 8 agents registered, heartbeats flowing,
# versions + current tasks visible.
# Kill the MUD daemon → squad auto-starts it (daemon_manager) instead of failing.
```

Verified live: daemon auto-start on an empty port file, login as `dummy`, all
8 agents eager-registered with no 429s (GET-first reuse), Jaeger/Grafana
healthy, the dashboard showing the board once the squad runs, a full
Agent Chat round trip (a test message posted to `grind_agent` in conversation
`agent_grind_agent` was answered within one `--once` pass), and the squad's
`ensure_chat_worker()` auto-spawned a persistent background worker (pid
12228) that answered messages typed in the MC UI during its run. Full suite:
**75/75**. The one fix along the way: `get_header()` on plain-dict headers is
case-sensitive, so the poll-queue test now inspects `req.header_items()`.
