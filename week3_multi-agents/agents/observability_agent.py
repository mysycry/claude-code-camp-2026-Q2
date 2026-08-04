import json
import os
import subprocess
import sys
import urllib.request

from agents.base import SubAgent, ROOT, jaeger_settings, grafana_settings


def _http_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def _compose_ps():
    try:
        compose_file = os.path.join(ROOT, "week3_multi-agents", "docker-compose.yml")
        r = subprocess.run(
            ["docker", "compose", "-f", compose_file, "ps", "--format", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return None, r.stderr.strip()
        out = r.stdout.strip()
        if not out:
            return [], ""
        if out.startswith("["):
            return json.loads(out), ""
        return [json.loads(line) for line in out.splitlines() if line.strip()], ""
    except Exception as e:
        return None, str(e)


class ObservabilityAgent(SubAgent):
    name = "observability_agent"
    description = (
        "Checks the whole observability stack: Jaeger OTLP receiver, Jaeger UI/API, "
        "Grafana UI/API, and whether the docker-compose containers are up."
    )
    parameters = {}

    def run(self, **kwargs):
        checks = []
        j = jaeger_settings()
        g = grafana_settings()

        code, body = _http_get(j["otlp_endpoint"], timeout=5)
        otlp_ok = code is not None and code < 500
        checks.append(("jaeger OTLP receiver", otlp_ok, f"{j['otlp_endpoint']} -> HTTP {code}"))

        code, body = _http_get(j["ui_url"], timeout=5)
        ui_ok = code is not None and code < 500
        checks.append(("jaeger UI", ui_ok, f"{j['ui_url']} -> HTTP {code}"))

        code, body = _http_get(j["services_api"], timeout=5)
        svc_ok = code is not None and code < 500
        detail = f"{j['services_api']} -> HTTP {code}"
        if svc_ok:
            try:
                payload = json.loads(body)
                names = payload.get("data") if isinstance(payload, dict) else payload
                names = names or []
                detail += f" ({len(names)} services)"
            except Exception:
                pass
        checks.append(("jaeger services API", svc_ok, detail))

        code, body = _http_get(g["health_api"], timeout=5)
        graf_ok = code is not None and code < 500
        checks.append(("grafana API", graf_ok, f"{g['health_api']} -> HTTP {code}"))

        code, body = _http_get(g["url"], timeout=5)
        checks.append(("grafana UI", code is not None and code < 500, f"{g['url']} -> HTTP {code}"))

        containers, err = _compose_ps()
        if containers is None:
            checks.append(("docker compose ps", False, f"unable to query: {err}"))
        else:
            def _is_up(c):
                st = (c.get("State") or c.get("state") or "").lower()
                return st in ("running", "running (healthy)")
            up = [c for c in containers if _is_up(c)]
            checks.append(
                ("docker containers", len(up) == len(containers) and len(containers) > 0,
                 f"{len(up)}/{len(containers)} running")
            )

        return self._summary("Observability stack", checks)


def register(registry):
    from agents.base import register_subagents

    register_subagents(registry, [ObservabilityAgent()])
