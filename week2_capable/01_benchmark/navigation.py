import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone


_BOOTSTRAPPED = False

def _ensure_bootstrap():
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    _BOOTSTRAPPED = True
    _add_paths()


def _add_paths():
    root = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    for p in (
        os.path.join(root, "week1_baseline", "python", "12_context"),
        os.path.dirname(__file__),
    ):
        if p not in sys.path:
            sys.path.insert(0, p)


_add_paths()
from memory_hook import make_memory_hook

def _import_boukensha():
    _ensure_bootstrap()
    import boukensha
    return boukensha.run

def run_benchmark(task="Navigate from the Temple of Midgaard to the Bakery",
                  runs=3, max_iterations=25, log_dir=None, quiet=False,
                  _run=None, start_room="3001", skip_reset=False,
                  trace_dir=None, memory_path=None, otel_endpoint=None):
    if _run is None:
        agent_run = _import_boukensha()
    else:
        agent_run = _run

    if trace_dir is None:
        trace_dir = os.path.join(os.path.dirname(__file__), "traces")
    if memory_path is None:
        memory_path = os.path.join(os.path.dirname(__file__), "memory_bench.db")

    if not skip_reset:
        root = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
        sys.path.insert(0, os.path.join(root, "week2_capable", "02_automatic_resets"))
        from player_reset import reset_player_to_start
        if not quiet:
            print(f"  resetting player to start room {start_room}...", file=sys.stderr)
        reset_player_to_start(start_room=start_room, quiet=quiet)
    elif not quiet:
        print("  skipping player reset", file=sys.stderr)

    # Read model/provider from settings for token tracking
    from boukensha.config import Config
    _cfg = Config()
    _model = _cfg.model()
    _provider = _cfg.provider_type()

    results = []

    for i in range(1, runs + 1):
        run_log = {"run": i, "task": task, "started_at": datetime.now(timezone.utc).isoformat()}
        turns = []
        tokens_used = 0
        success = False
        movements = []
        errors = []
        model = _model
        provider = _provider

        def make_hooks(run_i, model_name=model, provider_name=provider):
            hooks = {}
            memory_hook = make_memory_hook()

            def before_tool(ctx, name, args):
                if name == "move":
                    movements.append(args.get("direction", "?"))

            def after_tool(ctx, name, args, result, err):
                if err:
                    errors.append(f"{name}: {err}")
                memory_hook(ctx, name, args, result, err)

            def after_model(ctx, response, parsed):
                store = ctx.memory_store
                if not store:
                    return
                usage = response.get("usage", {})
                inp = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
                out = usage.get("output_tokens") or usage.get("completion_tokens", 0)
                if inp or out:
                    store.record_token_usage(model_name, provider_name, inp, out)

            hooks["before_tool"] = before_tool
            hooks["after_tool"] = after_tool
            hooks["after_model"] = after_model
            return hooks

        start = time.monotonic()
        try:
            result = agent_run(
                task,
                max_iterations=max_iterations,
                mud=True,
                hooks=make_hooks(i),
                trace_dir=trace_dir,
                memory_path=memory_path,
                otel_endpoint=otel_endpoint,
            )
            elapsed = time.monotonic() - start
            run_log["elapsed_seconds"] = round(elapsed, 2)
            run_log["result"] = result
            run_log["success"] = True
            success = True
        except Exception as e:
            elapsed = time.monotonic() - start
            run_log["elapsed_seconds"] = round(elapsed, 2)
            run_log["error"] = f"{type(e).__name__}: {e}"
            run_log["success"] = False
            if not quiet:
                print(f"  run {i} failed: {e}", file=sys.stderr)

        run_log["movements"] = movements
        run_log["movement_count"] = len(movements)
        run_log["errors"] = errors
        run_log["finished_at"] = datetime.now(timezone.utc).isoformat()
        results.append(run_log)

    return _summarize(results)


def _summarize(results):
    total = len(results)
    succeeded = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    lines = []
    lines.append("=" * 60)
    lines.append(f"Navigation Benchmark: {results[0]['task']}")
    lines.append(f"Runs: {total}  |  Succeeded: {len(succeeded)}  |  Failed: {len(failed)}")
    lines.append("")

    if succeeded:
        avg_sec = sum(r["elapsed_seconds"] for r in succeeded) / len(succeeded)
        avg_moves = sum(r["movement_count"] for r in succeeded) / len(succeeded)
        lines.append(f"Avg time (successful): {avg_sec:.1f}s")
        lines.append(f"Avg movements (successful): {avg_moves:.0f}")
        lines.append("")

    for r in results:
        status = "OK" if r.get("success") else "FAIL"
        moves = ", ".join(r.get("movements", [])) or "(none)"
        lines.append(f"  Run {r['run']:>2} [{status}]  {r['elapsed_seconds']:>6.1f}s  "
                     f"moves={r['movement_count']:>2}  [{moves}]")

    if failed:
        lines.append("")
        lines.append("Failures:")
        for r in failed:
            lines.append(f"  Run {r['run']}: {r.get('error', 'unknown')}")

    lines.append("=" * 60)
    return "\n".join(lines)
