---
name: ruby-to-python
description: Port the Boukensha agent framework from Ruby to Python. Copies the last Python step, writes a delta plan against the new Ruby step, then implements the plan and verifies. Works one step at a time — each step only carries over the new changes from the latest Ruby step.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: porting
---

## What I Do

Port the Boukensha agent framework one step at a time from Ruby (`week1_baseline/ruby/XX_*`) to Python (`week1_baseline/python/XX_*`).

Each port step:
1. Copies the previous Python step as the starting point
2. Compares the new Ruby step against the previous Ruby step to identify the delta
3. Writes a port plan to `docs/plans/python_port/`
4. Implements the plan — only files that are new or changed in Ruby
5. Creates/updates the bin script at `week1_baseline/bin/python/{N}_{name}`
6. Verifies compilation, imports, and runs the example live — then fixes any issues

## Workflow

### 1. Identify the step numbers

```
Ruby last:   week1_baseline/ruby/04_api_client/
Python last: week1_baseline/python/03_prompt_builder/
Next step:   04_api_client  (Python dir name matches Ruby dir name)
```

- Python step names always match the Ruby step names (e.g., `04_api_client`)
- The numbers stay in sync — Python 03 is the port of Ruby 03, etc.

### 2. Copy the previous Python step

Copy `python/{N-1}_{name}/` → `python/{N}_{name}/` so the new directory inherits all previously ported code.

Only the delta from the new Ruby step needs to be created or changed — everything else comes from the copy.

### 3. Write the port plan

Create `docs/plans/python_port/{N}_{name}.md`. The plan should:

- List **what's new** in the Ruby step vs the previous Ruby step
- List **what was already ported** in the previous Python step (so we know what to skip)
- Map each new/changed Ruby file to its Python target
- Note any Ruby-specific quirks (constant lookup, exception types, SSL, etc.)
- Ask questions about design decisions if the Ruby code is ambiguous

Follow the format established in existing plan files like `docs/plans/python_port/03_prompt_builder.md`.

### 4. Implement the plan

Create or update only the files listed in the plan's action table. Typically:

- **CREATE**: new Python files that didn't exist in the previous step
- **UPDATE**: existing Python files that need changes (new imports, new errors, etc.)
- **OVERWRITE**: files whose content completely changes (examples, prompts)
- Everything else stays untouched from the copy

### 5. Create the bin script

Create `week1_baseline/bin/python/{N}_{name}` (no extension) as a bash script:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV="$ROOT/.venv"
PYTHON="$VENV/Scripts/python"
if [ -f "${PYTHON}.exe" ]; then
  PYTHON="${PYTHON}.exe"
fi

if [ ! -f "$PYTHON" ]; then
  echo "ERROR: Virtual environment not found at $VENV" >&2
  echo "Run: python -m venv \"$VENV\"" >&2
  exit 1
fi

cd "$ROOT/week1_baseline/python/{N}_{name}"
"$PYTHON" examples/example.py
```

### 6. Verify and fix

```powershell
.venv\Scripts\python.exe -c "import py_compile; py_compile.compile('week1_baseline/python/{N}_{name}/boukensha/client.py', doraise=True)"
```

Check that:
- All `.py` files compile without syntax errors
- Package imports resolve (e.g. `from boukensha import Agent, LoopError`)
- Ruff linting passes if available
- The example script runs live via the bin script or directly

Then **execute the example** and fix any runtime issues discovered:

- **Path resolution**: If tools reference files relative to the step directory, make sure the paths resolve correctly in the Python step. The Ruby step may have files the Python step doesn't (e.g., `README.md`). Either point tools at the Ruby step's files or make the example self-contained.
- **Encoding issues**: On Windows, the console may use cp1252. Set `PYTHONIOENCODING=utf-8` or ensure the print output is encodable. The bin script should set this.
- **API errors**: If the live API call fails (e.g., 403 from blocked User-Agent), check and fix the client code.
- **Tool call flow**: Verify the Agent loop correctly dispatches tools, injects results back as messages, and terminates on `stop_reason: "end_turn"`.
- **Config defaults**: If new task settings are introduced (e.g., `max_iterations`, `max_output_tokens`), ensure the Python tasks/base.py has matching defaults.
- **Wrap-up**: Verify the `wrap_up` path (tools disabled, fallback message) works if the model hits the iteration limit.

## Known Ruby → Python Mappings

| Ruby | Python |
|---|---|
| `Module:Class` | `module/class` → `module.py` + `class ClassName` |
| `require_relative` | `from .module import Class` |
| `attr_reader` / `attr_accessor` | `@property` or plain attributes in `__init__` |
| `StandardError` subclasses | `Exception` subclasses |
| `CONST = value.freeze` | `CONST = value` (dicts are mutable, use tuple for immutability) |
| `symbol` keys (`:key`) | `string` keys (`"key"`) |
| `dig(:a, :b)` | nested `.get()` calls |
| `net/http` | `urllib.request` (stdlib, no deps) |
| `OpenSSL::SSL::VERIFY_PEER` | `ssl.create_default_context()` |
| `JSON.parse` / `.to_json` | `json.loads` / `json.dumps` |

## Ruby Quirks to Watch For

- **Constant lookup**: Ruby resolves `BASE_URL` lexically in the defining class, not through inheritance. Python's `self.BASE_URL` uses MRO and works correctly.
- **Exception catching**: Ruby `rescue *TRANSIENT_ERRORS` maps to `except tuple(TRANSIENT_ERRORS)` in Python.
- **Default User-Agent**: Ruby's `net/http` default User-Agent is `Ruby`, which is typically allowed. Python's `urllib.request` defaults to `Python-urllib/3.x` which some APIs (like OpenCode) block with 403. Always override with `boukensha/0.1.0` or similar.
- **Windows paths**: `os.path.join` doesn't normalize `..` — use `os.path.normpath` or `pathlib` for correct resolution.
- **Windows encoding**: The console is typically cp1252. Use `PYTHONIOENCODING=utf-8` in the bin script or handle encoding in print calls.
