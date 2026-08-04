"""MUD daemon lifecycle manager.

Ensures the Ruby `mud_daemon.rb` control layer is running before the squad
talks to the game. The daemon is what the Python clients proxy through to
reach CircleMUD, and it is what the agents ping to confirm a live connection.

Auto-start pattern (mirrors `week2_capable/bin/nav_bench`):
    ping -> if unreachable, delete stale port file -> spawn ruby daemon
    -> wait for the port file to appear -> re-ping with retries.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time

MAX_PING_ATTEMPTS = 3
PING_TIMEOUT = 2.0
STARTUP_WAIT_STEPS = 10
STARTUP_WAIT_STEP = 0.3
STARTUP_LOG = None


def mud_manager_dir():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    return os.environ.get("MUD_MANAGER_DIR") or os.path.join(root, ".mud_manager")


def port_file():
    return os.path.join(mud_manager_dir(), "port")


def daemon_script():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    return os.path.join(
        root, "week1_baseline", "ruby", "10_standard_tool_library", "bin", "mud_daemon"
    )


def find_ruby():
    exe = os.environ.get("MUD_RUBY") or shutil.which("ruby")
    if exe:
        return exe
    for candidate in (r"C:\Ruby40-x64\bin\ruby.exe", r"C:\Ruby37-x64\bin\ruby.exe"):
        if os.path.isfile(candidate):
            return candidate
    return "ruby"


def read_port():
    pf = port_file()
    if not os.path.isfile(pf):
        return None
    try:
        with open(pf, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def ping_daemon(port=None, timeout=PING_TIMEOUT):
    """Return True if the daemon at the port file answers `ping` with pong."""
    if port is None:
        port = read_port()
    if port is None:
        return False
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        try:
            s.sendall(b'{"cmd":"ping"}\n')
            r = json.loads(s.recv(4096))
            return r.get("data") == "pong"
        finally:
            s.close()
    except (OSError, ValueError):
        return False


def start_daemon(log_path=None):
    """Spawn the Ruby daemon in the background and wait for its port file."""
    script = daemon_script()
    ruby = find_ruby()
    if not os.path.isfile(script):
        raise FileNotFoundError(f"mud_daemon.rb not found: {script}")
    if not os.path.isfile(ruby):
        raise FileNotFoundError(f"ruby not found at {ruby} — set MUD_RUBY")

    os.makedirs(mud_manager_dir(), exist_ok=True)
    pf = port_file()
    if os.path.isfile(pf):
        os.remove(pf)

    log = log_path or os.path.join(mud_manager_dir(), "mud_daemon.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"=== starting mud_daemon {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    global STARTUP_LOG
    STARTUP_LOG = log

    env = dict(os.environ)
    env["MUD_MANAGER_DIR"] = mud_manager_dir()

    try:
        with open(log, "a", encoding="utf-8") as f:
            proc = subprocess.Popen(
                [ruby, script],
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except OSError as e:
        raise RuntimeError(f"failed to spawn ruby daemon: {e}") from e

    port = None
    for _ in range(STARTUP_WAIT_STEPS):
        port = read_port()
        if port is not None:
            break
        if proc.poll() is not None:
            raise RuntimeError(
                f"ruby daemon exited early (code {proc.returncode}); see {log}"
            )
        time.sleep(STARTUP_WAIT_STEP)

    if port is None:
        proc.kill()
        raise RuntimeError(f"daemon never wrote a port file; see {log}")

    return proc, port


def ensure_daemon(log_path=None):
    """Idempotent: guarantee the daemon is reachable, starting it if needed.

    Returns a (ok, detail) tuple. Never raises for a recoverable failure —
    callers can degrade gracefully (e.g. report the MUD as unreachable).
    """
    for attempt in range(1, MAX_PING_ATTEMPTS + 1):
        if ping_daemon():
            return True, f"daemon already running on port {read_port()}"
        try:
            proc, port = start_daemon(log_path=log_path)
            if ping_daemon(port=port, timeout=PING_TIMEOUT):
                return True, f"daemon started on port {port} (pid {proc.pid})"
        except (FileNotFoundError, RuntimeError, OSError) as e:
            if attempt == MAX_PING_ATTEMPTS:
                return False, f"could not start daemon: {e}"
    return False, "daemon unreachable after retries"


def main():
    ok, detail = ensure_daemon()
    print(f"OK: {detail}" if ok else f"FAIL: {detail}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
