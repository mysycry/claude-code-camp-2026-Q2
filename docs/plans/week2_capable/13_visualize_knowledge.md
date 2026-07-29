# Goal: Visualize stored knowledge so memory behavior can be verified

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/01_benchmark/memory_server.py` | REST API + HTML dashboard at `GET /` showing rooms, exits, stats, frontier, token usage |
| `week2_capable/grafana/dashboards-json/memory.json` | Grafana dashboard — stat cards, bar chart, gauge, tables for rooms/exits |
| `week2_capable/grafana/dashboards-json/token-usage.json` | Grafana dashboard — stat cards, bar charts, table for token consumption |

## Key Architecture Decisions

- **Two visualization paths**: (1) Built-in HTML dashboard at `http://localhost:9876/` — self-contained, no dependencies, auto-fetches all endpoints with `Promise.all()`. (2) Grafana dashboards via Infinity datasource — richer visualization, time-series, configurable refresh.
- **Same data source**: Both visualization paths read from the same `memory_bench.db` SQLite file that the agent writes to during benchmark runs. No data duplication.
- **REST API endpoints**: `/rooms` (sorted by visit_count), `/exits` (with room names), `/stats` (summary counters), `/frontier` (unexplored exits), `/token-usage` (aggregated), `/token-usage/raw` (raw events).

## Key Findings

- The HTML dashboard provides instant feedback without Docker/Grafana — useful during development.
- Grafana dashboards provide better visualization and historical views but require Docker infrastructure.
- The `token-usage` endpoint aggregates by model and provider, showing total calls, input/output tokens, and duration.

## Verification

```
http://localhost:9876/ (built-in HTML dashboard)
http://localhost:3000/d/boukensha-memory/boukensha-memory (Grafana)
http://localhost:3000/d/boukensha-token-usage/boukensha-token-usage (Grafana)
```
