import json
import socket
from pathlib import Path

PORT_FILE = Path.home() / ".mud_manager" / "port"


class MudDaemonClient:
    """Thin TCP/NDJSON client for the mud_daemon Ruby process."""

    def __init__(self, session="default"):
        self._session = session
        self._port = int(PORT_FILE.read_text().strip())
        self._host = "127.0.0.1"

    def _send(self, request):
        sock = socket.create_connection((self._host, self._port), timeout=10)
        try:
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
            data = sock.recv(65536).decode("utf-8")
            return json.loads(data)
        finally:
            sock.close()

    def ping(self):
        return self._send({"cmd": "ping"})

    def connect(self, host="localhost", port=4000, name=None, password=None):
        return self._send({
            "cmd": "connect",
            "session": self._session,
            "host": host,
            "port": port,
            "name": name,
            "password": password,
        })

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
