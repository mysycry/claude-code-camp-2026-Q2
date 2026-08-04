"""Agent Chat responder for Mission Control.

Mission Control's Agent Chat drops messages addressed to an agent (`to_agent`)
and tries to deliver them to an OpenClaw gateway session. The Boukensha squad
doesn't run gateway sessions, so nobody answers. This worker makes the squad
agents answer on their own behalf:

- Polls each agent's task queue (`GET /api/tasks/queue`) and marks claimed
  tasks done with a status reply.
- Polls incoming chat messages (`GET /api/chat/messages?to_agent=...`) and
  posts a status reply to the same conversation (`POST /api/chat/messages`).

The reply text is a live status report: game state from the bulletin DB
(level/XP/gold/location), MUD daemon health, and whether the squad is active.

Usage:
    python agents/chat_worker.py            # run forever (default 5s poll)
    python agents/chat_worker.py --once     # single pass (for testing)
    python agents/chat_worker.py --interval 10 --agents grind_agent,squad_manager
"""

import argparse
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEEK3 = os.path.abspath(os.path.join(_HERE, os.pardir))
if _WEEK3 not in sys.path:
    sys.path.insert(0, _WEEK3)

from agents.mission_control import MissionControlClient, enabled  # noqa: E402
from agents.bulletin import get_state, recent_events  # noqa: E402

DEFAULT_INTERVAL = 5.0
AGENT_NAMES = [
    "squad_manager", "connection_agent", "reset_agent", "map_agent",
    "grind_agent", "observability_agent", "trace_agent", "grafana_agent",
]


def _daemon_ok():
    """Best-effort MUD daemon ping via its port file. Returns a string."""
    manager_dir = os.environ.get("MUD_MANAGER_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".mud_manager",
    )
    port_file = os.path.join(manager_dir, "port")
    try:
        with open(port_file, encoding="utf-8") as f:
            port = int(f.read().strip())
        import json
        import socket

        with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
            s.sendall(b'{"cmd":"ping"}\n')
            data = json.loads(s.recv(4096))
            return "up" if data.get("data") == "pong" else "unresponsive"
    except Exception:
        return "down"


def _player_line():
    """One-line snapshot of the player's state, or None."""
    try:
        st = get_state()
    except Exception:
        return None
    if not st:
        return None
    parts = []
    level = st.get("score_level")
    if level:
        parts.append(f"L{level}")
    xp = st.get("score_xp")
    xp_next = st.get("score_xp_next")
    if xp is not None:
        parts.append(f"{xp} XP" + (f"/{xp_next}" if xp_next is not None else ""))
    gold = st.get("score_gold")
    if gold is not None:
        parts.append(f"{gold} gold")
    hp = st.get("score_hp")
    max_hp = st.get("score_max_hp")
    if hp is not None:
        parts.append(f"{hp}/{max_hp} HP" if max_hp is not None else f"{hp} HP")
    loc = st.get("location")
    if loc:
        parts.append(f"at {loc}")
    return ", ".join(parts) if parts else None


def _squad_active():
    """True if the bulletin board saw an update within the last 60s."""
    try:
        st = get_state()
        updated = st.get("updated_at", "")
        if updated:
            from datetime import datetime

            t = datetime.fromisoformat(updated)
            if (datetime.now(t.tzinfo) - t).total_seconds() < 60:
                return True
        return bool(recent_events(1))
    except Exception:
        return False


def status_reply(agent, prompt=None):
    """Compose a live status reply on behalf of `agent`."""
    lines = []
    header = f"[{agent}]"
    if prompt:
        lines.append(f"{header} Re: \"{prompt.strip()}\"")
    else:
        lines.append(f"{header} Status report")
    player = _player_line()
    lines.append(f"  Player: {player if player else 'no snapshot yet'}")
    lines.append(f"  MUD daemon: {_daemon_ok()}")
    lines.append(
        f"  Squad: {'active' if _squad_active() else 'idle (not running right now)'}"
    )
    lines.append("  I poll for tasks and answer here in Agent Chat.")
    return "\n".join(lines)


class ChatWorker:
    def __init__(self, interval=DEFAULT_INTERVAL, agents=None, once=False, state_dir=None):
        self.client = MissionControlClient()
        self.interval = interval
        self.once = once
        self.agents = list(agents) if agents else list(AGENT_NAMES)
        self._seen_task = {}
        self._seen_msg = {}
        self._state_dir = state_dir or os.environ.get("MUD_MANAGER_DIR") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".mud_manager",
        )
        self._load_state()

    def _state_file(self):
        return os.path.join(self._state_dir, "chat_worker_state.json")

    def _load_state(self):
        try:
            with open(self._state_file(), encoding="utf-8") as f:
                import json as _json

                data = _json.load(f)
            self._seen_msg = {str(k): v for k, v in (data.get("seen_msg") or {}).items()}
            self._seen_task = {(a, t): True for a, t in data.get("seen_task") or []}
        except Exception:
            self._seen_msg = {}
            self._seen_task = {}

    def _save_state(self):
        try:
            os.makedirs(self._state_dir, exist_ok=True)
            with open(self._state_file(), "w", encoding="utf-8") as f:
                import json as _json

                _json.dump(
                    {"seen_msg": self._seen_msg, "seen_task": sorted(self._seen_task)},
                    f,
                )
        except Exception as e:
            print(f"  [chat_worker] state save failed: {e}", file=sys.stderr)

    def _registered_names(self):
        resp = self.client._get("/api/agents?limit=100")
        names = []
        if resp and isinstance(resp, dict):
            names = [a.get("name") for a in resp.get("agents") or [] if a.get("name")]
        return names

    def _handle_task(self, agent):
        reason, task = self.client.poll_queue(agent)
        if not task:
            return
        task_id = task.get("id")
        seen_key = (agent, task_id)
        if seen_key in self._seen_task:
            return
        self._seen_task[seen_key] = True
        title = task.get("title") or task.get("description") or "assigned task"
        reply = status_reply(agent, prompt=title)
        self.client.update_task(
            task_id,
            status="done",
            description=f"{task.get('description') or task.get('title') or ''}\n\n— {reply}",
            metadata={"response": reply},
        )
        print(f"  [chat_worker] {agent}: task #{task_id} done ({reason})", file=sys.stderr)

    def _handle_messages(self, agent):
        since = self._seen_msg.get(agent)
        msgs = self.client.get_messages(to_agent=agent, since=since)
        for m in msgs:
            mid = m.get("id")
            sender = m.get("from_agent") or m.get("sender") or ""
            if not mid or sender == agent:
                continue
            if self._seen_msg.get(agent) is not None and mid <= self._seen_msg[agent]:
                continue
            content = m.get("content") or ""
            conv = m.get("conversation_id")
            reply = status_reply(agent, prompt=content[:200])
            self.client.post_message(
                content=reply,
                conversation_id=conv,
                to_agent=sender,
                from_agent=agent,
            )
            self._seen_msg[agent] = max(self._seen_msg.get(agent) or 0, mid)
            print(f"  [chat_worker] {agent}: replied to message #{mid}", file=sys.stderr)
    def run(self):
        if not self.client.enabled:
            print(
                "[chat_worker] Mission Control disabled "
                "(MC_ENABLED=true MC_URL=... MC_API_KEY=...)",
                file=sys.stderr,
            )
            return
        registered = self._registered_names()
        if registered:
            known = set(registered)
            self.agents = [a for a in self.agents if a in known] or list(registered)
        print(
            f"[chat_worker] watching agents: {', '.join(self.agents)} "
            f"(poll {self.interval}s)",
            file=sys.stderr,
        )
        while True:
            for agent in self.agents:
                try:
                    self._handle_task(agent)
                except Exception as e:
                    print(f"  [chat_worker] {agent} task error: {e}", file=sys.stderr)
                try:
                    self._handle_messages(agent)
                except Exception as e:
                    print(f"  [chat_worker] {agent} message error: {e}", file=sys.stderr)
            self._save_state()
            if self.once:
                return
            time.sleep(self.interval)


def main():
    parser = argparse.ArgumentParser(description="Mission Control Agent Chat responder")
    parser.add_argument("--once", action="store_true", help="single poll pass, then exit")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    parser.add_argument("--agents", help="comma-separated agent names (default: registered)")
    args = parser.parse_args()
    agents = [a.strip() for a in args.agents.split(",")] if args.agents else None
    ChatWorker(interval=args.interval, agents=agents, once=args.once).run()


def _manager_dir():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.environ.get("MUD_MANAGER_DIR") or os.path.join(root, ".mud_manager")


def _worker_pid_file():
    return os.path.join(_manager_dir(), "chat_worker.pid")


def _read_worker_pid():
    try:
        with open(_worker_pid_file(), encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid):
    """Return True if the given PID is a running process."""
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _chat_worker_alive():
    return _pid_alive(_read_worker_pid())


def start_chat_worker(log_path=None):
    """Spawn the chat worker as a detached background process.

    The child survives the spawning process, so Agent Chat keeps answering
    after the squad run ends. Logs to `.mud_manager/chat_worker.log` and
    records its PID in `.mud_manager/chat_worker.pid`.
    """
    manager_dir = _manager_dir()
    os.makedirs(manager_dir, exist_ok=True)
    log = log_path or os.path.join(manager_dir, "chat_worker.log")
    env = dict(os.environ)
    env["MUD_MANAGER_DIR"] = manager_dir
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"=== starting chat_worker {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            proc = subprocess.Popen(
                [sys.executable, "-u", os.path.abspath(__file__)],
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except OSError as e:
        raise RuntimeError(f"failed to spawn chat worker: {e}") from e
    try:
        with open(_worker_pid_file(), "w", encoding="utf-8") as f:
            f.write(str(proc.pid))
    except OSError:
        pass
    return proc


def ensure_chat_worker(log_path=None):
    """Idempotent: spawn the chat worker unless one is already running.

    Returns (ok, detail). Never raises for a recoverable failure, mirroring
    `daemon_manager.ensure_daemon()`. Skips entirely when MC is disabled.
    """
    try:
        from agents.mission_control import enabled as _mc_enabled
    except Exception:
        _mc_enabled = None
    if _mc_enabled is not None and not _mc_enabled():
        return False, "Mission Control disabled; chat worker not started"
    if _chat_worker_alive():
        return True, f"chat worker already running (pid {_read_worker_pid()})"
    try:
        proc = start_chat_worker(log_path=log_path)
        return True, f"chat worker started (pid {proc.pid})"
    except (FileNotFoundError, RuntimeError, OSError) as e:
        return False, f"could not start chat worker: {e}"


if __name__ == "__main__":
    main()
