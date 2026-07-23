import os
import subprocess
import threading


class Shell:
    @classmethod
    def register(cls, registry, working_dir, timeout=30, allowed_commands=None):
        root = os.path.abspath(working_dir)
        allowed = set(str(c) for c in (allowed_commands or []))

        def oops(msg):
            return f"error: {msg}"

        allowed_desc = f"Allowed executables: {', '.join(sorted(allowed))}." if allowed else ""

        registry.tool(
            "run_command",
            description=(
                "Run a shell command inside the working directory and return its combined stdout+stderr output. "
                f"Commands run with a {timeout}-second timeout. "
                f"{allowed_desc}"
            ),
            parameters={
                "command": {"type": "string", "description": "The shell command to execute (e.g. 'python script.py', 'ls -la', 'git status')"}
            },
            block=lambda command: _run_command(command, root, timeout, allowed, oops),
        )


def _run_command(command, root, timeout, allowed, oops):
    tokens = str(command).strip().split()
    if not tokens:
        return oops("empty command")

    executable = tokens[0]
    if allowed and executable not in allowed:
        return oops(f"'{executable}' is not in the allowed-commands list ({', '.join(sorted(allowed))})")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=root,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        return oops(f"command not found: {e}")
    except subprocess.TimeoutExpired:
        return oops(f"command timed out after {timeout}s: {command}")
    except Exception as e:
        return oops(str(e))

    output = (result.stdout + result.stderr).strip()
    exit_note = "" if result.returncode == 0 else f"\n[exit {result.returncode}]"
    return f"(no output){exit_note}" if not output else f"{output}{exit_note}"
