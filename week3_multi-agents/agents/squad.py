import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
for p in (HERE, PARENT):
    if p not in sys.path:
        sys.path.insert(0, p)

from agents.base import ROOT, ensure_boukensha_path, load_squad_config

os.environ.setdefault("BOUKENSHA_DIR", os.path.join(ROOT, ".boukensha"))
os.environ.setdefault("MUD_MANAGER_DIR", os.path.join(ROOT, ".mud_manager"))
os.environ.setdefault("BOUKENSHA_OTEL_ENABLED", "true")

ensure_boukensha_path()

import boukensha

from agents import connection_agent, grafana_agent, grind_agent, map_agent
from agents import observability_agent, reset_agent, trace_agent


def _system_prompt():
    prompt_path = os.path.join(HERE, "system.md")
    if os.path.isfile(prompt_path):
        with open(prompt_path, encoding="utf-8") as f:
            return f.read().strip()
    return "You are the Boukensha Squad Manager. Delegate to your sub-agents."


def register_subagents(block):
    connection_agent.register(block)
    reset_agent.register(block)
    map_agent.register(block)
    grind_agent.register(block)
    observability_agent.register(block)
    trace_agent.register(block)
    grafana_agent.register(block)


def run_squad(task=None, max_iterations=None, max_turn_tokens=None):
    cfg = load_squad_config()
    squad = cfg.get("squad", {})

    if task is None:
        task = os.environ.get("SQUAD_TASK") or "Check the MUD and observability stack, then report what you find."

    if max_iterations is None:
        max_iterations = int(os.environ.get("SQUAD_MAX_ITERATIONS") or squad.get("max_iterations", 60))
    if max_turn_tokens is None:
        max_turn_tokens = int(os.environ.get("SQUAD_MAX_TURN_TOKENS") or squad.get("max_turn_tokens", 60000))

    model = os.environ.get("SQUAD_MODEL") or squad.get("model", "deepseek-v4-flash-free")
    provider = os.environ.get("SQUAD_PROVIDER") or squad.get("provider", "opencode")

    trace_dir = os.environ.get("SQUAD_TRACE_DIR") or os.path.join(HERE, "traces")
    memory_path = os.environ.get("SQUAD_MEMORY_PATH") or os.path.join(
        ROOT, "week3_multi-agents", "memory", "memory_bench.db"
    )

    manager_mc = None
    try:
        from agents.mission_control import ManagedAgent, enabled

        if enabled():
            manager_mc = ManagedAgent("squad_manager")
            manager_mc.start()
            manager_mc.set_status("busy", task=task)
    except Exception:
        manager_mc = None

    from agents.daemon_manager import ensure_daemon

    daemon_ok, daemon_detail = ensure_daemon()
    if not daemon_ok:
        print(f"  [squad] WARNING: {daemon_detail}", file=sys.stderr)

    try:
        from agents.chat_worker import ensure_chat_worker

        cw_ok, cw_detail = ensure_chat_worker()
        if not cw_ok:
            print(f"  [squad] WARNING: {cw_detail}", file=sys.stderr)
    except Exception as e:
        print(f"  [squad] WARNING: chat worker not started: {e}", file=sys.stderr)

    try:
        return boukensha.run(
            task=task,
            system=_system_prompt(),
            model=model,
            backend=provider,
            max_iterations=max_iterations,
            max_turn_tokens=max_turn_tokens,
            block=register_subagents,
            trace_dir=trace_dir,
            memory_path=memory_path,
        )
    finally:
        if manager_mc is not None:
            manager_mc.stop()


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_squad(task=task)
    print("\n--- SQUAD RESULT ---")
    print(result)
