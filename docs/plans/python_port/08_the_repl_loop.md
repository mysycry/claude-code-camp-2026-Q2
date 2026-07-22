# Step 08 — The REPL Loop

## What's new in Ruby 08 vs Ruby 07

| File | Change |
|------|--------|
| `lib/boukensha/version.rb` | **NEW** — `Boukensha::VERSION = "0.8.0"` |
| `lib/boukensha/repl.rb` | **NEW** — `Boukensha::Repl` class (interactive REPL loop) |
| `lib/boukensha.rb` | **UPDATED** — added `require_relative "boukensha/version"` at top, `Boukensha.repl` class method, `require_relative "boukensha/repl"` at bottom |
| `examples/example.rb` | **REWRITTEN** — uses `Boukensha.repl` instead of `Boukensha.run` |

## Already ported (from previous Python step)

Everything in `python/07_the_run_dsl/` — including `__init__.py` with the `run()` function, all backends, agent, client, config, context, errors, logger, message, prompt_builder, registry, run_dsl, tool, tasks, prompts, and the full `__all__` export list.

## Python mapping

| Ruby | Python |
|------|--------|
| `lib/boukensha/version.rb` | `boukensha/version.py` |
| `lib/boukensha/repl.rb` | `boukensha/repl.py` |
| `lib/boukensha.rb` (additional `require_relative` + `repl` method) | `boukensha/__init__.py` (additional `repl()` function + `Repl` + `VERSION` imports) |
| `examples/example.rb` | `examples/example.py` |

## Quirks / non-trivial ports

1. **`boukensha/repl.rb` → `repl.py`**
   - Ruby `$stdin.gets` → `sys.stdin.readline()`
   - Ruby `print PROMPT; $stdout.flush` → `print(PROMPT, end="", flush=True)`
   - Ruby `Boukensha.quiet!` / `Boukensha.loud!` → `quiet()` / `loud()` module-level functions in `__init__.py`
   - Ruby `@context.clear_messages!` maps to `Context.clear_messages()` — need to check if that method exists on Python Context
   - Banner uses unicode box drawing — fine in UTF-8 Python, need `PYTHONIOENCODING=utf-8`
   - Ruby `Dir.exist?` → `os.path.isdir`
   - `rescue LoopError => e` / `rescue ApiError => e` per turn

2. **`boukensha.rb` → `__init__.py`**: The `repl()` function mirrors `run()` but creates a `Repl` instance instead of an `Agent`, passes extra metadata (config_dir, provider, model, version, api_key), and calls `.start()`.

3. **`version.rb` → `version.py`**: Straightforward constant.

4. **`example.rb` → `example.py`**: Interactive REPL — user types tasks at the prompt. Use `input()` in Python. `base_dir` points to `07_the_run_dsl` to reuse source files.

## Action table

| Action | File | Notes |
|--------|------|-------|
| CREATE | `boukensha/version.py` | `VERSION = "0.8.0"` |
| CREATE | `boukensha/repl.py` | `Repl` class with `start()` loop and `run_turn()` |
| UPDATE | `boukensha/__init__.py` | Import `Repl`, `VERSION`; add `repl()` function; export in `__all__` |
| OVERWRITE | `examples/example.py` | Use `repl()` with interactive prompt |
| CREATE | `week1_baseline/bin/python/08_the_repl_loop` | Bin script |

## Verification

1. `py_compile` all files
2. `from boukensha import Repl, repl, VERSION` resolves
3. Run `examples/example.py` via the bin script — interact with the REPL
