import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime


DEFAULT_ENDPOINT = "http://localhost:4318/v1/traces"


def _otel_enabled():
    return os.environ.get("BOUKENSHA_OTEL_ENABLED", "").lower() in ("1", "true", "yes")


def _trace_id_to_hex(tid):
    return hashlib.md5(tid.encode()).hexdigest()


def _hex(n, bytes_len):
    return format(n, "0" + str(bytes_len * 2) + "x")


def _to_nanos(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        epoch = int(dt.timestamp() * 1_000_000_000)
        return epoch
    except Exception:
        return int(time.time() * 1_000_000_000)


class OtelExporter:
    def __init__(self, endpoint=None):
        self.endpoint = endpoint or DEFAULT_ENDPOINT
        self._batches = []
        print(f"[opentelemetry] exporter created -> {self.endpoint}", file=sys.stderr)

    def export_span(self, span):
        nanos = _to_nanos(span.started_at)
        duration = int(span.duration_ms * 1_000_000) if span.duration_ms else 0
        # Ensure endTimeUnixNano > startTimeUnixNano (at least 1 ns)
        if duration <= 0:
            duration = 1

        otel_span = {
            "traceId": _trace_id_to_hex(span.trace_id) if span.trace_id else "0" * 32,
            "spanId": span.span_id,
            "name": span.name,
            "kind": 1,
            "startTimeUnixNano": nanos,
            "endTimeUnixNano": nanos + duration,
            "attributes": [
                {"key": "phase", "value": {"stringValue": span.phase}},
            ],
            "status": {"code": 2 if span.status == "error" else 1},
        }

        # Only include parentSpanId when valid (16 hex chars); omit for root spans
        if span.parent_id and len(span.parent_id) == 16:
            otel_span["parentSpanId"] = span.parent_id

        if span.error:
            otel_span["status"]["message"] = span.error

        for k, v in span.metadata.items():
            attr = _make_attribute(k, v)
            if attr:
                otel_span["attributes"].append(attr)

        self._batches.append(otel_span)

    def flush(self):
        if not self._batches:
            print("[opentelemetry] flush: no spans to send", file=sys.stderr)
            return
        n = len(self._batches)
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "boukensha"}},
                            {"key": "service.version", "value": {"stringValue": "0.13.0"}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "boukensha.tracer"},
                            "spans": self._batches,
                        }
                    ],
                }
            ]
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            print(f"[opentelemetry] POST {self.endpoint} -> {resp.status} ({n} spans)", file=sys.stderr)
        except Exception as e:
            print(f"[opentelemetry] POST {self.endpoint} failed ({n} spans): {e}", file=sys.stderr)
        self._batches = []


def _make_attribute(key, value):
    if isinstance(value, str):
        return {"key": key, "value": {"stringValue": value}}
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": value}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    if isinstance(value, dict):
        return {"key": key, "value": {"stringValue": json.dumps(value)}}
    return None
