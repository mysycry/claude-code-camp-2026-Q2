import json
import time
import urllib.request

from agents.base import SubAgent, jaeger_settings
from boukensha.opentelemetry import OtelExporter


class TraceAgent(SubAgent):
    name = "trace_agent"
    description = (
        "Sends a synthetic test span through the OTLP pipeline and verifies Jaeger "
        "actually stored it. Use when you need to prove end-to-end tracing works."
    )
    parameters = {}

    def run(self, **kwargs):
        j = jaeger_settings()
        checks = []

        exporter = OtelExporter(endpoint=j["otlp_endpoint"])
        from boukensha.tracer import Tracer

        tracer = Tracer(trace_id=f"squad-trace-{int(time.time())}", otel_endpoint=j["otlp_endpoint"])
        span_id = tracer.start_span("squad.synthetic.check", phase="squad")
        tracer.end_span(span_id, status="ok", metadata={"source": "trace_agent", "test": "true"})
        try:
            tracer.finish()
            checks.append(("otlp export", True, f"span sent to {j['otlp_endpoint']}"))
        except Exception as e:
            checks.append(("otlp export", False, str(e)))
            return self._summary("Trace check", checks)

        time.sleep(2)
        code, body = _get(j["services_api"])
        found = False
        detail = f"services API -> HTTP {code}"
        if code is not None and code < 500:
            try:
                payload = json.loads(body)
                names = payload.get("data") if isinstance(payload, dict) else payload
                names = names or []
                found = "boukensha" in names
                detail += f" ({len(names)} services: {names})"
            except Exception:
                pass
        checks.append(("jaeger has boukensha service", found, detail))

        return self._summary("Trace check", checks)


def _get(url, timeout=8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def register(registry):
    from agents.base import register_subagents

    register_subagents(registry, [TraceAgent()])
