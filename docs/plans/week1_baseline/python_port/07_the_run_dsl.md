# Python Port Plan: Step 07 — The Boukensha.run DSL

**Starting point:** copy `python/06_the_logger/` → `python/07_the_run_dsl/`.
Then add the `RunDSL` class, a `run()` function in `__init__.py`, and simplify the example.

---

## What's New in Step 07

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `run_dsl.rb` | `boukensha/run_dsl.py` | **NEW** — Tiny class exposing only `tool()`, used as `instance_eval` host |
| `boukensha.rb` | `boukensha/__init__.py` | **UPDATE** — Add `run()` function that wires everything, import `RunDSL` |
| `examples/example.rb` | `examples/example.py` | **REWRITE** — Use `Boukensha.run(task: ...) do ... end` DSL |

---

## What Stays the Same

Everything else — `agent.py`, `logger.py`, `client.py`, `backends/*.py`, `config.py`, `context.py`, `errors.py`, `prompt_builder.py`, `tasks/*.py`, `registry.py`, `prompts/` — no changes.

---

## Architecture

```
Boukensha.run(task:, system:, model:, backend:, api_key:, ...) do
  tool "name", description:, parameters: do |args|
    # implementation
  end
end
  ↓
  Config → task_settings, system_prompt
  Context, Registry
  RunDSL.new(registry).instance_eval(&block)   ← registers tools
  Backend dispatch by :backend symbol
  PromptBuilder, Client, Logger, Agent
  ctx.add_message(:user, task)
  agent.run
  return result
```

### `run_dsl.rb` (13 LOC)

```ruby
class RunDSL
  def initialize(registry)
    @registry = registry
  end

  def tool(name, description:, parameters: {}, &block)
    @registry.tool(name, description: description, parameters: parameters, &block)
  end
end
```

Python: same delegation pattern. `instance_eval` in Ruby → Python just calls `block(registry)` or wraps it differently. Actually, looking at the Ruby code: `RunDSL.new(registry).instance_eval(&block) if block`. In Python, there's no `instance_eval`. The simplest Python equivalent is to pass a `RunDSL`-wrapped registry into a callable.

### `__init__.py` / `boukensha.rb` change

Add a `run()` function that:
1. Gets config, task settings, system prompt, model, backend
2. Resolves API key from env var based on backend
3. Creates Context, Registry
4. If a block is given, passes a RunDSL(registry) to the block
5. Instantiates the correct backend
6. Wires PromptBuilder, Client, Logger, Agent
7. Adds user message, calls agent.run
8. Returns result, ensures logger.close

---

## Files to Create / Modify

| Action | File | Notes |
|---|---|---|
| CREATE | `boukensha/run_dsl.py` | Port of `RunDSL` — tiny tool-registration proxy |
| UPDATE | `boukensha/__init__.py` | Add `run()` function, import `RunDSL` |
| REWRITE | `examples/example.py` | Uses `boukensha.run(task=...)` DSL |
| CREATE | `week1_baseline/bin/python/07_the_run_dsl` | Bin script |
