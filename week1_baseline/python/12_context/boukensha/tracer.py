import json
import os
import secrets
import time
from datetime import datetime, timezone


class Span:
    __slots__ = ("trace_id", "span_id", "parent_id", "name", "phase",
                 "started_at", "finished_at", "duration_ms",
                 "status", "error", "metadata")

    def __init__(self, trace_id, span_id, parent_id, name, phase):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.name = name
        self.phase = phase
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at = None
        self.duration_ms = None
        self.status = "ok"
        self.error = None
        self.metadata = {}

    def finish(self, status="ok", error=None, metadata=None):
        self.finished_at = datetime.now(timezone.utc).isoformat()
        started = datetime.fromisoformat(self.started_at)
        finished = datetime.fromisoformat(self.finished_at)
        self.duration_ms = round((finished - started).total_seconds() * 1000, 1)
        self.status = status
        if error:
            self.error = str(error)
        if metadata:
            self.metadata.update(metadata)

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "phase": self.phase,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata,
        }


def _generate_trace_id():
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rand = secrets.token_hex(4)
    return f"{now}-{rand}"


def _generate_span_id():
    return secrets.token_hex(8)


class Tracer:
    def __init__(self, trace_id=None, path=None, dir=None, otel_endpoint=None):
        self.trace_id = trace_id or _generate_trace_id()
        self._spans = []
        self._stack = []
        self._span_map = {}
        if path is None and dir is not None:
            os.makedirs(dir, exist_ok=True)
            path = os.path.join(dir, f"trace_{self.trace_id}.jsonl")
        self._path = path
        self._otel = None
        if otel_endpoint:
            from boukensha.opentelemetry import OtelExporter
            self._otel = OtelExporter(endpoint=otel_endpoint)

    @property
    def spans(self):
        return list(self._spans)

    def start_span(self, name, phase, parent_id=None):
        if parent_id is None and self._stack:
            parent_id = self._stack[-1]
        span_id = _generate_span_id()
        span = Span(self.trace_id, span_id, parent_id, name, phase)
        self._spans.append(span)
        self._span_map[span_id] = span
        self._stack.append(span_id)
        return span_id

    def end_span(self, span_id=None, status="ok", error=None, metadata=None):
        if span_id is None:
            if not self._stack:
                return
            span_id = self._stack.pop()
        else:
            if span_id in self._stack:
                self._stack.remove(span_id)
        span = self._span_map.get(span_id)
        if span is None:
            return
        span.finish(status, error, metadata)
        if self._otel:
            self._otel.export_span(span)

    def dump(self, path=None):
        output = path or self._path
        if output is None:
            return
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
        with open(output, "a", encoding="utf-8") as f:
            for span in self._spans:
                if span.finished_at is None:
                    continue
                f.write(json.dumps(span.to_dict()) + "\n")

    def finish(self, path=None):
        while self._stack:
            self.end_span()
        self.dump(path)
        if self._otel:
            self._otel.flush()

    def waterfall(self):
        tree = []
        root_spans = [s for s in self._spans if s.parent_id is None]
        for root in root_spans:
            tree.append(self._format_span(root, 0))
        return "\n".join(tree)

    def _format_span(self, span, depth):
        indent = "  " * depth
        dur = f"{span.duration_ms:>8.0f}ms" if span.duration_ms is not None else "  pending"
        status = "OK" if span.status == "ok" else "ERR"
        line = f"{indent}{dur} {status} {span.phase}/{span.name}"
        children = [s for s in self._spans if s.parent_id == span.span_id]
        for child in children:
            line += "\n" + self._format_span(child, depth + 1)
        return line
