# Goal: Export traces through OpenTelemetry

- Added an optional OpenTelemetry telemetry backend.
- Exported spans through OTLP while retaining existing JSONL logging.
- Added trace attributes, parentage, durations, errors, and status recording.
- Added local Collector configurations for Jaeger, Tempo, and debug output.
- Added Docker Compose observability infrastructure and Grafana provisioning.
- Added telemetry contract tests and a no-op backend when tracing is disabled.
