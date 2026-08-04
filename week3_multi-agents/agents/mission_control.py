"""Mission Control client for the Boukensha squad.

Thin stdlib-only REST client + heartbeat thread so the squad appears in a
self-hosted Mission Control dashboard (online/offline, version, current task,
token usage). All calls are best-effort: any failure is logged and swallowed,
so Mission Control is a dashboard, never a dependency.
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

try:
    from agents.base import load_env as _load_env
    _load_env()
except Exception:
    pass

ROLE_MAP = {
    "connection_agent": "devops",
    "reset_agent": "devops",
    "map_agent": "researcher",
    "grind_agent": "agent",
    "observability_agent": "devops",
    "trace_agent": "devops",
    "grafana_agent": "devops",
    "squad_manager": "agent",
}

DEFAULT_URL = "http://localhost:3001"
DEFAULT_INTERVAL = 30.0


def _settings():
    """Read mission_control settings from squad.yaml + env overrides."""
    url = DEFAULT_URL
    api_key = ""
    enabled = False
    interval = DEFAULT_INTERVAL
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "squad.yaml"), encoding="utf-8") as f:
            import yaml
            cfg = yaml.safe_load(f) or {}
        mc = cfg.get("mission_control", {})
        url = mc.get("url", DEFAULT_URL)
        api_key = mc.get("api_key", "")
        enabled = bool(mc.get("enabled", False))
        interval = float(mc.get("heartbeat_interval", DEFAULT_INTERVAL))
    except Exception:
        pass

    if os.environ.get("MC_URL"):
        url = os.environ["MC_URL"]
    if os.environ.get("MC_API_KEY"):
        api_key = os.environ["MC_API_KEY"]
    if os.environ.get("MC_ENABLED"):
        enabled = os.environ["MC_ENABLED"].strip().lower() in ("1", "true", "yes", "on")
    if os.environ.get("MC_HEARTBEAT_INTERVAL"):
        try:
            interval = float(os.environ["MC_HEARTBEAT_INTERVAL"])
        except ValueError:
            pass
    return {"url": url, "api_key": api_key, "enabled": enabled, "interval": interval}


def enabled():
    return _settings()["enabled"]


def squad_version():
    """Version string: BOUKENSHA_VERSION env, else git short sha, else 'unknown'."""
    env = os.environ.get("BOUKENSHA_VERSION")
    if env:
        return env
    try:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


class MissionControlClient:
    """Authenticated REST client for Mission Control."""

    RETRYABLE_HTTP = {429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BACKOFF = 0.5

    def __init__(self, url=None, api_key=None, enabled=None, timeout=5):
        s = _settings()
        self.url = (url or s["url"]).rstrip("/")
        self.api_key = api_key if api_key is not None else s["api_key"]
        self.enabled = s["enabled"] if enabled is None else enabled
        self.enabled = self.enabled and bool(self.url)
        self.timeout = timeout
        self._agent_id = None
        self._agent_name = None

    def _post(self, path, payload):
        if not self.enabled:
            return None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    self.url + path,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8", "replace")
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as e:
                if e.code not in self.RETRYABLE_HTTP or attempt == self.MAX_RETRIES:
                    print(f"  [mc] {path} failed: HTTP {e.code}", file=sys.stderr)
                    return None
            except (urllib.error.URLError, OSError, ValueError) as e:
                if attempt == self.MAX_RETRIES:
                    print(f"  [mc] {path} failed: {e}", file=sys.stderr)
                    return None
            if attempt < self.MAX_RETRIES:
                time.sleep(self.BACKOFF * attempt)
        return None

    def register(self, name, role="agent", capabilities=None):
        payload = {"name": name, "role": role}
        if capabilities:
            payload["capabilities"] = list(capabilities)
        resp = self._post("/api/agents/register", payload)
        if resp:
            agent = resp.get("agent") or {}
            self._agent_id = agent.get("id")
            self._agent_name = agent.get("name", name)
        return self._agent_id

    def heartbeat(self, status="idle", version=None, task=None, token_usage=None):
        if self._agent_id is None:
            return None
        payload = {}
        if status:
            payload["status"] = status
        if version:
            payload["version"] = version
        if task:
            payload["task"] = task
        if token_usage:
            payload["token_usage"] = token_usage
        return self._post(f"/api/agents/{self._agent_id}/heartbeat", payload)

    def create_task(self, title, assigned_to=None, description=None, priority="medium"):
        payload = {"title": title, "priority": priority}
        if assigned_to:
            payload["assigned_to"] = assigned_to
        if description:
            payload["description"] = description
        return self._post("/api/tasks", payload)


class AgentState:
    """Shared mutable state between the heartbeat thread and the agent."""

    def __init__(self):
        self.lock = threading.Lock()
        self.status = "idle"
        self.task = ""
        self.token_usage = None

    def set(self, status=None, task=None, token_usage=None):
        with self.lock:
            if status is not None:
                self.status = status
            if task is not None:
                self.task = task
            if token_usage is not None:
                self.token_usage = token_usage

    def snapshot(self):
        with self.lock:
            return {
                "status": self.status,
                "task": self.task,
                "token_usage": self.token_usage,
            }


class HeartbeatThread(threading.Thread):
    def __init__(self, client, state, version, interval=30.0):
        super().__init__(daemon=True)
        self.client = client
        self.state = state
        self.version = version
        self.interval = interval
        self._stop = threading.Event()

    def run(self):
        while not self._stop.wait(self.interval):
            snap = self.state.snapshot()
            self.client.heartbeat(
                status=snap["status"],
                version=self.version,
                task=snap["task"] or None,
                token_usage=snap["token_usage"],
            )

    def stop(self):
        self._stop.set()


class ManagedAgent:
    """Registers a squad agent with Mission Control and tracks its status.

    Usage in the registry wrapper:
        mc = ManagedAgent(name)
        mc.start()                     # register + start heartbeat thread
        ...
        mc.set_status("busy", task=...)
        mc.set_status("idle")          # after run completes
    """

    def __init__(self, name, role=None, capabilities=None):
        s = _settings()
        self.name = name
        self.role = role or ROLE_MAP.get(name, "agent")
        self.capabilities = capabilities
        self.client = MissionControlClient()
        self.state = AgentState()
        self._thread = None
        self._agent_id = None
        self._interval = s["interval"]

    def start(self, version=None):
        if not self.client.enabled:
            return None
        self._agent_id = self.client.register(self.name, self.role, self.capabilities)
        if self._agent_id is None:
            return None
        self._thread = HeartbeatThread(
            self.client, self.state, version or squad_version(), interval=self._interval
        )
        self._thread.start()
        return self._agent_id

    def set_status(self, status, task=None, token_usage=None):
        self.state.set(status=status, task=task, token_usage=token_usage)
        # Push the transition immediately so the board reflects it now, not on
        # the next tick.
        self.client.heartbeat(
            status=status,
            version=squad_version(),
            task=task,
            token_usage=token_usage,
        )

    def stop(self):
        if self._thread is not None:
            self._thread.stop()
        if self._agent_id is not None:
            self.client.heartbeat(status="offline", version=squad_version())
