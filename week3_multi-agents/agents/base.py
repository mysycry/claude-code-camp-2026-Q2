import os
import sys
import yaml


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, os.pardir, os.pardir))


ROOT = _repo_root()

_LOADED_ENV = []


def load_env(path=None):
    """Load a .env file into os.environ (existing vars win; idempotent).

    Reads `week3_multi-agents/.env` by default. Any variable already set in
    the environment takes precedence, so shell exports beat the file.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    path = os.path.abspath(path)
    if path in _LOADED_ENV:
        return
    _LOADED_ENV.append(path)
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_env()


def ensure_boukensha_path():
    framework = os.path.join(ROOT, "week1_baseline", "python", "12_context")
    if framework not in sys.path:
        sys.path.insert(0, framework)
    return framework


def load_squad_config():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "squad.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def mud_settings():
    cfg = load_squad_config()
    mud = cfg.get("mud", {})
    return {
        "host": os.environ.get("MUD_HOST", mud.get("host", "localhost")),
        "port": int(os.environ.get("MUD_PORT", mud.get("port", 4000))),
        "name": os.environ.get("MUD_USERNAME", mud.get("username", "dummy")),
        "password": os.environ.get("MUD_PASSWORD", mud.get("password", "helloworld")),
    }


def jaeger_settings():
    cfg = load_squad_config()
    j = cfg.get("jaeger", {})
    return {
        "otlp_endpoint": j.get("otlp_endpoint", "http://localhost:4318/v1/traces"),
        "ui_url": j.get("ui_url", "http://localhost:16686"),
        "services_api": j.get("services_api", "http://localhost:16686/api/services"),
    }


def grafana_settings():
    cfg = load_squad_config()
    g = cfg.get("grafana", {})
    return {
        "url": g.get("url", "http://localhost:3000"),
        "health_api": g.get("health_api", "http://localhost:3000/api/health"),
    }


class SubAgent:
    """Base class for squad sub-agents.

    Subclasses define `name`, `description`, `parameters`, and `run(**kwargs)`.
    `run()` must return a human-readable string report.
    """

    name = "subagent"
    description = "A squad sub-agent."
    parameters = {}

    def __init__(self):
        ensure_boukensha_path()

    def run(self, **kwargs):
        raise NotImplementedError

    def _mc_managed(self):
        """Create (or reuse) a Mission Control registration for this agent.

        Returns a `ManagedAgent` (or None if disabled/unavailable). Best-effort.
        """
        if getattr(self, "_mc", None) is None:
            from agents.mission_control import ManagedAgent, enabled

            self._mc = ManagedAgent(self.name) if enabled() else None
            if self._mc is not None:
                self._mc.start()
        return self._mc

    def _execute(self, **kwargs):
        """Run() wrapper that reports busy/idle/error to Mission Control."""
        mc = self._mc_managed()
        task = _describe_task(self.name, kwargs)
        if mc is not None:
            mc.set_status("busy", task=task)
        try:
            return self.run(**kwargs)
        except Exception as e:
            if mc is not None:
                mc.set_status("error", task=f"{task}: {e}")
            raise
        finally:
            if mc is not None:
                mc.set_status("idle")

    def _summary(self, title, checks, failed=None):
        lines = [f"== {title} =="]
        for label, ok, detail in checks:
            lines.append(f"  [{('OK' if ok else 'FAIL')}] {label}: {detail}")
        if failed is None:
            failed = not all(ok for _, ok, _ in checks)
        lines.append(f"RESULT: {'FAIL' if failed else 'OK'}")
        return "\n".join(lines)


def _describe_task(name, kwargs):
    """Short human-readable description of what an agent was asked to do."""
    parts = [f"{k}={v}" for k, v in (kwargs or {}).items() if v is not None]
    body = ", ".join(parts) if parts else "(no args)"
    return f"{name}({body})"


def register_subagents(registry, agents):
    from boukensha.tool import Tool

    for agent in agents:
        agent._mc_managed()
        registry.tool(
            agent.name,
            description=agent.description,
            parameters=agent.parameters,
            block=lambda args=None, _a=agent: _a._execute(**(args or {})),
        )
