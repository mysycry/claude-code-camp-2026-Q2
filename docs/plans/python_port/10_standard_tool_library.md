# Python Port Plan: Step 10 — Standard Tool Library

**Starting point:** copy `python/09_global_executable/` → `python/10_standard_tool_library/`.

---

## What's New in Ruby Step 10

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `lib/boukensha/tools/file_system.rb` (new) | `boukensha/tools/file_system.py` | FileSystem: pwd, list_directory, read_file, write_file, delete_file, search_files |
| `lib/boukensha/tools/shell.rb` (new) | `boukensha/tools/shell.py` | Shell: run_command with allow-list + timeout |
| `lib/boukensha/tools/mud.rb` (new) | `boukensha/tools/mud.py` | Mud: gameplay tools (stub — no mud_manager in Python) |
| `lib/boukensha.rb` | `boukensha/__init__.py` | Add `working_dir`, `mud`, `allowed_commands`, `shell_timeout` params to `run()`/`repl()`, auto-register tools, `mud_opts_from_config` |
| `lib/boukensha/context.rb` | `boukensha/context.py` | Add `working_dir` attribute |
| `lib/boukensha/repl.rb` | `boukensha/repl.py` | Add mud status to banner |
| `lib/boukensha/version.rb` | `boukensha/version.py` | Bump to `0.10.0` |
| `examples/example.rb` | `examples/example.py` | Demo `run()` with `working_dir` |

## What Stays the Same

`agent.py`, `client.py`, `prompt_builder.py`, `errors.py`, `logger.py`, `registry.py`, `tool.py`, `message.py`, `config.py`, `run_dsl.py`, `tasks/`, `backends/`, `pyproject.toml` — no changes.

---

## Tools Architecture

Each tool module exposes a `register(registry, **kwargs)` classmethod that registers one or more tools against the shared Registry. The `Boukensha.run()` and `Boukensha.repl()` functions call these automatically when `working_dir` or `mud` are provided.

### FileSystem (`file_system.py`)
- `register(registry, working_dir)` — registers 6 tools:
  - `pwd` — return working directory
  - `list_directory` — list files/subdirs at a relative path
  - `read_file` — read file contents
  - `write_file` — write/overwrite a file
  - `delete_file` — delete a file
  - `search_files` — grep for a pattern across files

All paths are resolved against `working_dir`; path traversal is rejected.

### Shell (`shell.py`)
- `register(registry, working_dir, timeout, allowed_commands)` — registers 1 tool:
  - `run_command` — run a shell command with timeout and optional allow-list

### Mud (`mud.py`) — Stub
- Since there's no Python equivalent of `mud_manager` gem, this logs a warning and returns.
- Registered as a no-op so `Boukensha.run(mud=True)` doesn't crash.

---

## Files to Create / Modify

| Action | File |
|---|---|
| CREATE | `boukensha/tools/__init__.py` |
| CREATE | `boukensha/tools/file_system.py` |
| CREATE | `boukensha/tools/shell.py` |
| CREATE | `boukensha/tools/mud.py` |
| UPDATE | `boukensha/context.py` — add `working_dir` |
| UPDATE | `boukensha/__init__.py` — new params, auto-register tools, `mud_opts_from_config` |
| UPDATE | `boukensha/repl.py` — add `mud`, mud status in banner |
| UPDATE | `boukensha/version.py` — bump to `0.10.0` |
| OVERWRITE | `examples/example.py` — demo `run()` with `working_dir` |
| CREATE | `week1_baseline/bin/python/10_standard_tool_library` |

## Questions

1. **MUD module** — Ruby's `mud.rb` depends on `mud_manager` gem. Python has no equivalent. Should Mud.register be a no-op with a warning, or should we skip it entirely? → Make it a no-op that warns once.

2. **search_files glob** — Ruby uses `Dir.glob` with `**` for recursive search. Python's `glob.glob` with `**` requires `recursive=True`. Should we use `pathlib` or `glob`? → `glob.glob` with `recursive=True` + `Path.rglob` for simplicity.

3. **run_command encoding** — subprocess output encoding on Windows may be cp1252. Should we decode with `errors="replace"`? → Yes, use `errors="replace"` for safety.
