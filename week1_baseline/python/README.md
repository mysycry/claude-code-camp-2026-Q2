# Python Port — Boukensha Agent

Python port of the Boukensha agent framework, originally built in Ruby.

## Environment Setup

A shared virtual environment lives at the project root:

```bash
# From the project root (<repo-root>/)
python -m venv .venv
```

Activate it:

| Platform | Command |
|----------|---------|
| Windows (cmd) | `.venv\Scripts\activate` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| macOS / Linux | `source .venv/bin/activate` |

Install dependencies:

```bash
# With env active
pip install -r requirements.txt

# Or install each step's package in editable mode
pip install -e week1_baseline/python/00_config
```

Alternatively, use [uv](https://docs.astral.sh/uv/):

```bash
uv venv .venv
uv sync
```

> **Note:** You may need to configure your editor/IDE to use
> `<repo-root>/.venv/Scripts/python.exe` as the Python interpreter
> for this project.

## Verification

Check the environment is set up correctly:

```bash
# Activate first, then:
python .venv/verify.py

# Or without activation:
.venv/Scripts/python .venv/verify.py
```

Expected output:
```
=== Boukensha Environment Check ===

Python: 3.14.x ...
Virtual env: .../.venv
  Active: yes
  python-dotenv: 1.x.x  OK
  pyyaml: 6.x  OK
  .boukensha/.env: found  OK
All checks passed
```

## Steps

```
week1_baseline/python/
  .python-version        # Python 3.14 (for pyenv/uv)
  requirements.txt       # Shared dependencies
  Makefile               # make check-env, make install
  00_config/             # Configuration system (in progress)
  01_struct_skeleton/    # (planned)
  ...
```

Run a step's example:

```bash
./bin/python/00_config
```

The script will check the venv exists first and print setup instructions
if it doesn't.
