# Goal: Export traces through OpenTelemetry

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/python/12_context/boukensha/opentelemetry.py` | `OtelExporter` — converts Boukensha spans to OTLP HTTP JSON format, POSTs to `{endpoint}/v1/traces` |
| `week1_baseline/python/12_context/boukensha/tracer.py` | Integrates `OtelExporter` — `Tracer.__init__()` creates exporter when `otel_endpoint` provided, `end_span()` calls `export_span()`, `finish()` calls `flush()` |
| `week2_capable/docker-compose.yml` | Jaeger all-in-one (ports 16686/4318/4317) + Grafana with Infinity plugin |
| `week2_capable/grafana/Dockerfile` | Pre-installs Infinity datasource plugin at Docker build time |
| `week2_capable/grafana/datasources/jaeger.yaml` | Jaeger datasource with fixed UID |
| `week2_capable/grafana/dashboards-json/boukensha.json` | Trace Explorer dashboard — Total Traces stat, Recent Traces table, Traces Over Time timeseries, Service Operations table |

## Key Architecture Decisions

- **No OpenTelemetry SDK dependency**: The OTLP exporter uses stdlib only (`urllib`, `json`) — no `opentelemetry-api` or `opentelemetry-sdk` packages required. The HTTP JSON endpoint is hit directly.
- **Trace ID hashing**: Boukensha trace IDs are hashed with MD5 to produce the 32-hex-char format required by OTLP. Span IDs (16 hex chars from `secrets.token_hex(8)`) are passed through verbatim.
- **Batched export**: Spans are accumulated in-memory and sent in a single POST on `flush()`. If `flush()` is never called (e.g., process crash), in-flight spans are lost.
- **Status code mapping**: OTLP spec: `0`=UNSET, `1`=OK, `2`=ERROR. The exporter maps `status == "error"` to `2`, everything else to `1`. (Initial version mapped errors to `0`=UNSET, making error spans invisible in Jaeger.)
- **BOUKENSHA_OTEL_ENABLED env var**: Set to `"true"` to enable OTEL export. Can also be passed explicitly via the `otel_endpoint` parameter to `run()` or `repl()`. Default endpoint: `http://localhost:4318/v1/traces`.

## Key Findings

- The entire tracing pipeline was initially non-functional because `run()` was not passing `tracer=tracer` to the Agent constructor. Only `repl()` worked. This was the root cause behind the first "no data in panels" report.
- Jaeger all-in-one uses in-memory storage — all traces are lost on container restart (`docker compose down`). For persistent storage, a Jaeger deployment with Elasticsearch or Cassandra backend would be needed.
- The Infinity plugin must be pre-installed at Docker build time (in `Dockerfile`) because Grafana's provisioning is synchronous and fails fatally if a datasource type isn't registered.

## Verification

```bash
# Set the env var before running
export BOUKENSHA_OTEL_ENABLED=true
cd week2_capable/01_benchmark
python -c "from navigation import run_benchmark; run_benchmark(runs=1, max_iterations=5)"
# Check http://localhost:16686 for traces (service: boukensha)
# Check http://localhost:3000/d/boukensha-traces/boukensha-trace-explorer
```
