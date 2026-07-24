# Python Port Plan: Step 11 — TUI

**Starting point:** copy `python/10_standard_tool_library/` → `python/11_tui/`.

---

## What's New in Ruby Step 11

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `lib/boukensha/tui.rb` (new) | `boukensha/tui.py` | TUI wrapper — four-zone display (viewport, progress, input, status). In Python this is a stub that warns and falls back to the plain REPL (no charm-ruby equivalent exists). |
| `lib/boukensha/repl.rb` | `boukensha/repl.py` | **Major refactoring** — Repl exposes public `on_output`, `handle_command`, `run_turn`, `banner` for TUI composability. Output routed through callback when set. `/quiet`/`/loud` removed from HELP. |
| `lib/boukensha/logger.rb` | `boukensha/logger.py` | Add `subscribe(callback)` — calls all subscribers on every `_write`. |
| `lib/boukensha.rb` | `boukensha/__init__.py` | `repl()` gains `tui: bool = True` param. Constructs Repl, then conditionally wraps in Tui. `try/except ImportError` for tui module. |
| `lib/boukensha_loader.rb` | (n/a — no Python equivalent) | `--no-tui` flag parsing handled in entry point / bin script. |
| `lib/boukensha/version.rb` | `boukensha/version.py` | Bump to `0.11.0` |
| `examples/example.rb` | `examples/example.py` | Minor — add BOUKENSHA_DIR default + `tui: False` to `repl()` call |
| `patches/bubbletea/*` | SKIP | Go native extension patches, not applicable to Python |

## What Stays the Same

`agent.py`, `client.py`, `prompt_builder.py`, `errors.py`, `registry.py`, `tool.py`, `message.py`, `config.py`, `context.py`, `run_dsl.py`, `tasks/`, `backends/`, `tools/` (except `mud_client.py` checked), `pyproject.toml`, `tests/` — no changes.

---

## REPL Refactoring Details

The Ruby step 11 refactors Repl from a monolithic I/O loop into a composable session controller. The Python port must mirror this exactly:

### New public API
```
Repl.on_output(callback)      # Register output callback (suppresses stdout)
Repl.banner                   # Property returning banner string (was _banner())
Repl.handle_command(input)    # Dispatch /commands. Returns "quit", "command", or None.
Repl.run_turn(input)          # Run one agent turn (was _run_turn())
```

### Start loop
`start()` uses the public methods:
```
start():
    print(banner)  # via output()
    loop:
        if no output_cb: print prompt
        read stdin
        cmd = handle_command(input)
        if cmd == "quit": break
        if cmd: continue
        run_turn(input)
```

### output() helper
`output(str)` routes to `@output_cb` if set, else `print()`.

### HELP changes
Remove `/quiet` and `/loud` from HELP text. The `quiet()`/`loud()` module functions remain.

---

## TUI Architecture (Python = stub)

The Ruby Tui wraps a Repl with charm-ruby (bubbletea + lipgloss + bubbles), a Go native extension gem. No equivalent exists in Python's stdlib or currently installed packages.

**Python `tui.py`** will be a stub that:
1. Exports a `Tui` class with the same `__init__(repl)` and `start()` interface
2. `start()` prints a warning that TUI requires a charm-ruby equivalent, then calls `repl.start()` (plain REPL fallback)
3. This keeps the architecture identical to Ruby (condition checked via `if tui and "Tui" in globals()`)
4. Future implementation can swap in `textual`, `prompt_toolkit`, or `urwid` without changing `__init__.py`

---

## Files to Create / Modify

| Action | File |
|---|---|
| CREATE | `boukensha/tui.py` — Tui stub class |
| UPDATE | `boukensha/repl.py` — refactored public API |
| UPDATE | `boukensha/logger.py` — add `subscribe()` |
| UPDATE | `boukensha/__init__.py` — add `tui` param, conditional Tui wrapping, try/except import |
| UPDATE | `boukensha/version.py` — bump to `0.11.0` |
| UPDATE | `examples/example.py` — add `tui=False` |
| CREATE | `week1_baseline/bin/python/11_tui` |

---

## Questions

1. **TUI approach**: The Ruby TUI depends on `charm-ruby` (Go native extension). Python has no equivalent installed. Should we:
   - (A) Create a stub that warns and falls back to plain REPL
   - (B) Implement with `prompt_toolkit` (add to requirements.txt)
   - (C) Skip TUI entirely

2. **No Python boukensha_loader**: Ruby's `boukensha_loader.rb` handles `--no-tui` flag from ARGV. Python has no equivalent loader script. Should the bin script handle `--no-tui` or should we add a `__main__.py` entry point?
