import json
import os
import secrets
import time
from datetime import datetime, timezone



DEFAULT_SESSION_DIR = "sessions"


class Logger:
    def __init__(self, session_id=None, dir=None, log=None, snapshot=None):
        snapshot = snapshot or {}
        self._session_id = session_id or _generate_session_id()
        self._path = log or os.path.join(dir or _default_dir(), f"{self._session_id}.jsonl")

        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._log_io = open(self._path, "a", encoding="utf-8")
        self._write({**{"phase": "session_start"}, **snapshot})

    @property
    def session_id(self):
        return self._session_id

    @property
    def path(self):
        return self._path

    def iteration(self, n, max):
        self._write({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind, n, max):
        self._write({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, reason, iterations, tokens=None):
        self._write({"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens})

    def prompt(self, messages, tools):
        self._write({
            "phase": "prompt",
            "message_count": len(messages),
            "messages": [_serialize_message(m) for m in messages],
            "tool_count": len(tools),
            "tools": list(tools.keys()),
        })

    def tool_call(self, name, args):
        self._write({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, name, result, ok=True, error=None):
        self._write({"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error})

    def response(self, text, usage=None, stop_reason=None, task=None, backend=None):
        meta = _execution_metadata(task=task, backend=backend, usage=usage)
        self._write({
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
            **meta,
        })

    def raw(self, data):
        from boukensha import _boukensha_debug
        if not _boukensha_debug:
            return
        self._write({"phase": "raw", "data": data})

    def close(self):
        if self._log_io:
            self._log_io.close()
            self._log_io = None

    def _write(self, event):
        event["session_id"] = self._session_id
        event["at"] = datetime.now(timezone.utc).isoformat()
        self._log_io.write(json.dumps(event) + "\n")
        self._log_io.flush()


def _generate_session_id():
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rand = secrets.token_hex(4)
    return f"{now}-{rand}"


def _default_dir():
    from boukensha import _get_config
    return os.path.join(_get_config().dir, DEFAULT_SESSION_DIR)


def _serialize_message(msg):
    return {"role": msg.role, "content": msg.content}


def _execution_metadata(task=None, backend=None, usage=None):
    if not task and not backend and not usage:
        return {}

    tokens = _usage_tokens(usage)
    meta = {
        "task": _task_name(task),
        "provider": _provider_name(backend),
        "model": backend.model if backend else None,
        "usage_unit": backend.usage_unit if backend and hasattr(backend, "usage_unit") else None,
        "usage_level": backend.usage_level if backend and hasattr(backend, "usage_level") else None,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
        "cost_usd": _estimate_cost(backend, tokens),
    }
    return {k: v for k, v in meta.items() if v is not None}


def _task_name(task):
    if task and hasattr(task, "task_name"):
        return task.task_name
    return str(task) if task else None


def _provider_name(backend):
    if not backend:
        return None
    name = type(backend).__name__
    result = []
    for ch in name:
        if ch.isupper() and result:
            result.append("_")
        result.append(ch.lower())
    return "".join(result)


def _usage_tokens(usage):
    usage = usage or {}
    return (
        _first_integer(usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"),
        _first_integer(usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"),
    )


def _first_integer(hash, *keys):
    for key in keys:
        value = hash.get(key)
        if value is not None:
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
    return None


def _estimate_cost(backend, tokens):
    if not backend or not hasattr(backend, "estimate_cost"):
        return None
    inp, out = tokens
    if inp is None or out is None:
        return None
    return backend.estimate_cost(inp, out)
