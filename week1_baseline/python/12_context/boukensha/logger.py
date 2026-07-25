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
        self._subscribers = []

        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._log_io = open(self._path, "a", encoding="utf-8")
        self._write({**{"phase": "session_start"}, **snapshot})

    @property
    def session_id(self):
        return self._session_id

    @property
    def path(self):
        return self._path

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def turn(self, n):
        self._write({"phase": "turn", "n": n})

    def iteration(self, n, max):
        self._write({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind, n, max):
        self._write({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, reason, iterations, tokens=None):
        self._write({
            "phase": "turn_end", "reason": reason,
            "iterations": iterations, "tokens": tokens,
        })

    def prompt(self, messages, tools, context_window=None):
        self._write({
            "phase": "prompt",
            "message_count": len(messages),
            "messages": [_serialize_message(m) for m in messages],
            "tool_count": len(tools),
            "tools": list(tools.keys()),
            "context_window": context_window,
        })

    def compaction(self, before, dropped, context_window):
        self._write({
            "phase": "compaction",
            "before": before,
            "dropped": dropped,
            "context_window": context_window,
        })

    def tool_call(self, name, args):
        self._write({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, name, result, ok=True, error=None):
        self._write({
            "phase": "tool_result", "name": name,
            "result": str(result), "ok": ok, "error": error,
        })

    def response(self, text, usage=None, stop_reason=None):
        self._write({
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        })

    def reasoning(self, text, redacted=False):
        self._write({"phase": "reasoning", "text": str(text), "redacted": redacted})

    def plan(self, text):
        self._write({"phase": "plan", "text": str(text).strip()})

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
        for cb in self._subscribers:
            cb(event)


def _generate_session_id():
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rand = secrets.token_hex(4)
    return f"{now}-{rand}"


def _default_dir():
    from boukensha import _get_config
    return os.path.join(_get_config().dir, DEFAULT_SESSION_DIR)


def _serialize_message(msg):
    return {"role": msg.role, "content": msg.content}
