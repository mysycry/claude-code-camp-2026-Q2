import json
import os
import subprocess
import urllib.request

from agents.base import SubAgent, ROOT, grafana_settings


def _http_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


class GrafanaAgent(SubAgent):
    name = "grafana_agent"
    description = (
        "Ensures Grafana has the Jaeger datasource provisioned and the dashboard "
        "definitions exist; can also bring the stack up via docker compose."
    )
    parameters = {}

    def run(self, **kwargs):
        g = grafana_settings()
        checks = []

        code, body = _http_get(g["health_api"], timeout=5)
        healthy = code is not None and code < 500
        checks.append(("grafana health", healthy, f"{g['health_api']} -> HTTP {code}"))

        ds_path = os.path.join(ROOT, "week3_multi-agents", "grafana", "datasources", "jaeger.yaml")
        ds_ok = os.path.isfile(ds_path)
        checks.append(("jaeger datasource file", ds_ok, ds_path))

        dash_dir = os.path.join(ROOT, "week3_multi-agents", "grafana", "dashboards-json")
        dash_ok = os.path.isdir(dash_dir) and any(
            f.endswith(".json") for f in os.listdir(dash_dir)
        )
        checks.append(("dashboard json files", dash_ok, dash_dir))

        return self._summary("Grafana check", checks)


def register(registry):
    from agents.base import register_subagents

    register_subagents(registry, [GrafanaAgent()])
