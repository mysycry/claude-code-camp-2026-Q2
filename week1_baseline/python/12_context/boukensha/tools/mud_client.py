import json
import os
import socket
from pathlib import Path

def _port_file():
    mud_dir = os.environ.get("MUD_MANAGER_DIR") or str(Path.home() / ".mud_manager")
    return Path(mud_dir) / "port"


class MudDaemonClient:
    """Thin TCP/NDJSON client for the mud_daemon Ruby process."""

    def __init__(self, session="default"):
        self._session = session
        self._port = int(_port_file().read_text().strip())
        self._host = "127.0.0.1"

    def _send(self, request, recv_timeout=20):
        sock = socket.create_connection((self._host, self._port), timeout=5)
        sock.settimeout(recv_timeout)
        try:
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
            data = sock.recv(65536).decode("utf-8")
            return json.loads(data)
        finally:
            sock.close()

    def ping(self):
        return self._send({"cmd": "ping"}, recv_timeout=5)

    def connect(self, host="localhost", port=4000, name=None, password=None):
        # MUD login can take 30-40s (4 sequential read_until steps), so allow a
        # generous response window instead of the default 20s.
        return self._send({
            "cmd": "connect",
            "session": self._session,
            "host": host,
            "port": port,
            "name": name,
            "password": password,
        }, recv_timeout=60)

    def send(self, command):
        return self._send({
            "cmd": "send",
            "session": self._session,
            "command": command,
        })

    def disconnect(self):
        return self._send({
            "cmd": "disconnect",
            "session": self._session,
        })

    def status(self):
        return self._send({
            "cmd": "status",
            "session": self._session,
        })
