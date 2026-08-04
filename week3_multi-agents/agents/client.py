import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "week1_baseline", "python", "12_context"))

from boukensha.tools.mud_client import MudDaemonClient


def make_client(session="squad"):
    """Return a MudDaemonClient wired to the squad MUD settings.

    Reads MUD_HOST/MUD_PORT/MUD_USERNAME/MUD_PASSWORD env overrides, then
    falls back to agents/squad.yaml.
    """
    from agents.base import mud_settings

    settings = mud_settings()
    client = MudDaemonClient(session=session)
    client._mud_settings = settings
    return client


def connect(client):
    settings = client._mud_settings
    result = client.connect(
        host=settings["host"],
        port=settings["port"],
        name=settings["name"],
        password=settings["password"],
    )
    if result.get("ok"):
        return result["data"]
    return f"error: {result.get('error', 'unknown error')}"


def disconnect(client):
    result = client.disconnect()
    if result.get("ok"):
        return result["data"]
    return f"error: {result.get('error', 'unknown error')}"


def send(client, command):
    result = client.send(command)
    if result.get("ok"):
        return result["data"]
    return f"error: {result.get('error', 'unknown error')}"


def wake_and_stand(client):
    send(client, "wake")
    send(client, "stand")
    return send(client, "look")
