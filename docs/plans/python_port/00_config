# Python Port Plan: Step 00 — Configuration

Port the Ruby Boukensha configuration system to Python,
mirroring Step 0 of the baseline agent.

This is the first step in porting the entire Boukensha agent
framework from `week1_baseline/ruby/` to `week1_baseline/python/`.

---

## Files to Port (Ruby → Python)

| Ruby Source | Python Target | What It Does |
|---|---|---|
| `week1_baseline/ruby/00_config/lib/boukensha.rb` | `week1_baseline/python/00_config/boukensha/__init__.py` | Package entry point — exports `Config`, `Tasks::Base`, `Tasks::Player` |
| `week1_baseline/ruby/00_config/lib/boukensha/config.rb` | `week1_baseline/python/00_config/boukensha/config.py` | `Boukensha::Config` → `Config` class — dir resolution, `.env` loading, YAML parsing, settings accessors |
| `week1_baseline/ruby/00_config/lib/boukensha/tasks/base.rb` | `week1_baseline/python/00_config/boukensha/tasks/base.py` | `Tasks::Base` — abstract class methods for provider, model, prompt resolution |
| `week1_baseline/ruby/00_config/lib/boukensha/tasks/player.rb` | `week1_baseline/python/00_config/boukensha/tasks/player.py` | `Tasks::Player` — task_name = "player" |
| `week1_baseline/ruby/00_config/examples/example.rb` | `week1_baseline/python/00_config/examples/example.py` | Smoke-test — loads config, prints all values |
| `week1_baseline/ruby/00_config/Gemfile` | `week1_baseline/python/00_config/pyproject.toml` | Dependencies (`dotenv` → `python-dotenv`, `yaml` → `pyyaml`) |
| `week1_baseline/bin/ruby/00_config` | `week1_baseline/bin/python/00_config` | Entry script for running the example |
| `.boukensha/settings.yaml` | shared — no change needed | Config consumed by both Ruby and Python |
| `.boukensha/.env` | shared — no change needed | Secrets loaded by both |
| `.boukensha/prompts/player/system.md` | shared — no change needed | System prompt consumed by both |

## Files Already Updated (bin pathing fix)

| File | Change |
|---|---|
| `week1_baseline/bin/ruby/00_config` | `../ruby/00_config` → `../../ruby/00_config` (corrects path after move to `bin/ruby/` subfolder) |
| `week1_baseline/bin/python/00_config` | **New** — runs `../../python/00_config/examples/example.py` |
| `bin/ruby/00_config` | **New** — top-level convenience wrapper, delegates to `week1_baseline/bin/ruby/00_config` |
| `bin/python/00_config` | **New** — top-level convenience wrapper, delegates to `week1_baseline/bin/python/00_config` |

---

## Dependencies

- **`python-dotenv`** — load `.env` (replaces Ruby `dotenv` gem)
- **`pyyaml`** — parse `settings.yaml` (replaces Ruby stdlib `yaml`)
- **stdlib** `pathlib`, `os` — file resolution, env var reading

---

## Architecture (per Ruby source)

### `config.rb` (94 LOC)

- `Config#initialize` — resolves `.boukensha/` dir via `BOUKENSHA_DIR` env var → `~/.boukensha`, loads `.env`, parses `settings.yaml`
- `Config#tasks(name=nil)` — returns full tasks hash or a single task's settings
- `Config#mud_host/port/username/password` — MUD connection accessors with defaults
- `Config#dig(*keys)` — nested hash key lookup (string/symbol fallback)
- Uses `Dotenv.load` for env vars, `YAML.safe_load` for YAML

### `tasks/base.rb` (60 LOC)

- Stateless class methods operating on a raw `settings` hash
- `provider(settings)` / `model(settings)` — reads key or raises
- `prompt_override?(settings, prompt_name)` — checks `prompt_override.<name>` boolean
- `system_prompt(settings, ...)` — resolution: user override file → default shipped prompt
- All methods are class-level (no instances); Python equivalent: `@classmethod` or module-level functions

### `player.rb` (9 LOC)

- `task_name = "player"` — links to `tasks.player` in settings.yaml
- Everything else inherited from `Base`

### `example.rb` (26 LOC)

- Sets `BOUKENSHA_DIR` env var if not present (defaults to repo's `.boukensha/`)
- Creates `Config()`, queries each accessor, prints to stdout

---

## Questions

1. **Port scope — just Config, or start MudManager too?** The Ruby `mud_manager` gem (`week0_explore/mud_manager/`) is separate from Boukensha. Did you want a Python `mud_manager` too, or let Boukensha call the Ruby gem via MCP/stdio? just config for now

2. **Python package naming** — `boukensha` (mirrors Ruby namespace), or prefix like `boukensha_config` for disambiguation? the first one

3. **Python version target** — `circlemud-world-parser` uses `>=3.14`. Same constraint here, or more flexible (`>=3.10`)? same constraint

4. **Default prompt path** — Ruby ships `prompts/system.md` relative to the lib dir. Where should the shipped default live in the Python package? Inside the package dir? yes

5. **Class/module structure** — Ruby uses stateless class methods on `Tasks::Base`. Python: `@classmethod` on a class, or plain module-level functions? module-level

6. **Port exact API or improve it?** E.g. Ruby's `dig` helper with string/symbol fallback — port it identically, or use Pydantic models / dataclasses? port it identically

7. **Tests** — Ruby has no unit tests for Config (example only). Add pytest tests during the port? not now
