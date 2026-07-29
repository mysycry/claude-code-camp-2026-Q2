# Goal: Build unified observability before optimizing further

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/docker-compose.yml` | Jaeger + Grafana Docker services |
| `week2_capable/grafana/Dockerfile` | Custom Grafana image with pre-installed Infinity datasource plugin |
| `week2_capable/grafana/datasources/jaeger.yaml` | Jaeger trace datasource provisioning |
| `week2_capable/grafana/datasources/memory.yaml` | Memory API datasource provisioning (Infinity plugin) |
| `week2_capable/grafana/dashboards/` | Dashboard provider configuration |
| `week2_capable/grafana/dashboards-json/boukensha.json` | Boukensha Trace Explorer dashboard (stat, table, timeseries panels) |
| `week2_capable/grafana/dashboards-json/memory.json` | Memory/Knowledge dashboard (rooms, exits, frontier) |
| `week2_capable/grafana/dashboards-json/token-usage.json` | Token usage dashboard (calls, input/output tokens by model) |
| `week2_capable/01_benchmark/memory_server.py` | REST API feeding memory data to Grafana via Infinity |
| `week1_baseline/ruby/12_context/lib/boukensha/logger.rb` | Structured JSONL event logger — foundation for all observability |

## Key Architecture Decisions

- **Three-view system**: Agent view (what the agent saw and did), Manager view (underlying MudManager commands), and Raw Telnet view (bytes over the wire). Each provides a different level of abstraction.
- **SQLite as the shared data bus**: The agent writes to SQLite during execution; the Memory API server reads the same SQLite file to serve Grafana. No message queue or event bus needed.
- **Infinity datasource plugin**: Grafana queries the Memory API via the `yesoreyeram-infinity-datasource` plugin, which treats JSON REST endpoints as time-series or table data sources.
- **Plugin pre-installed at Docker build**: The Infinity plugin is installed via `RUN grafana cli plugins install yesoreyeram-infinity-datasource` in the Dockerfile, avoiding the race condition where provisioning runs before the plugin finishes installing.

## Key Findings

- All the data needed for observability was already being logged by Boukensha's structured logger — the missing piece was the visualization layer.
- The Grafana Infinity plugin is required but must be pre-installed in the Docker image, not at startup, because Grafana's provisioning is synchronous and fails fatally if a datasource type isn't registered yet.
- The Memory API server binds to `0.0.0.0:9876`, reachable from the Grafana Docker container via `host.docker.internal:9876`.

## Verification

```
http://localhost:3000/d/boukensha-memory/boukensha-memory (memory dashboard)
http://localhost:3000/d/boukensha-traces/boukensha-trace-explorer (trace dashboard)
http://localhost:3000/d/boukensha-token-usage/boukensha-token-usage (token usage)
```
