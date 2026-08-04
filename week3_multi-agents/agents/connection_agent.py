import os
import socket
import sys

from agents.base import SubAgent, mud_settings
from agents.daemon_manager import ensure_daemon


class ConnectionAgent(SubAgent):
    name = "connection_agent"
    description = (
        "Checks that the MUD daemon is running, the MUD server is reachable, "
        "and a player can log in. Call this first if anything MUD-related looks broken."
    )
    parameters = {}

    def run(self, **kwargs):
        checks = []

        # Make sure the Ruby control daemon is actually up before we judge
        # anything else MUD-related. Auto-starts it if missing/stale.
        daemon_ok, daemon_detail = ensure_daemon()
        checks.append(("mud_daemon", daemon_ok, daemon_detail))

        settings = mud_settings()
        srv_ok = False
        srv_detail = f"{settings['host']}:{settings['port']}"
        try:
            s = socket.create_connection((settings["host"], settings["port"]), timeout=3)
            s.close()
            srv_ok = True
            srv_detail += " reachable"
        except OSError as e:
            srv_detail += f" unreachable ({e})"
        checks.append(("mud server", srv_ok, srv_detail))

        login_ok = False
        login_detail = "not attempted"
        if daemon_ok:
            from agents.client import connect, make_client

            client = make_client(session="squad_conn")
            try:
                data = connect(client)
                status = client.status()
                connected = status.get("ok") and status.get("data", {}).get("connected")
                if connected:
                    login_ok = True
                    login_detail = f"logged in as {settings['name']}"
                else:
                    login_detail = str(data) if not isinstance(data, str) else data[:80]
                client.disconnect()
            except Exception as e:
                login_detail = f"error: {e}"
        checks.append(("player login", login_ok, login_detail))

        return self._summary("Connection check", checks)


def register(registry):
    from agents.base import register_subagents

    register_subagents(registry, [ConnectionAgent()])
