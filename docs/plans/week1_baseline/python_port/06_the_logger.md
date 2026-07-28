# Python Port Plan: Step 06 — The Logger

**Starting point:** copy `python/05_agent_loop/` → `python/06_the_logger/`.
Then add the Logger class, update Agent to log at each phase, add `backend` accessor to PromptBuilder, and update the example.

---

## What's New in Step 06

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `logger.rb` | `boukensha/logger.py` | **NEW** — Session logger writing JSONL to `.boukensha/sessions/` |
| `agent.rb` | `boukensha/agent.py` | **UPDATE** — Takes `logger:` kwarg, logs at each phase, `handle_tool_calls(response)` sig change |
| `prompt_builder.rb` | `boukensha/prompt_builder.py` | **UPDATE** — Add `backend` property |
| `boukensha.rb` | `boukensha/__init__.py` | **UPDATE** — Module-level `quiet!`/`debug!`/`config` helpers, import Logger |
| `examples/example.rb` | `examples/example.py` | **OVERWRITE** — Creates Logger, passes to Agent |
| `backends/*.rb` | unchanged | Already ported |
| `config.rb` | unchanged | Already ported |
| `client.rb` | unchanged | Already ported from 05 |

---

## What Stays the Same

`client.py`, `errors.py`, `context.py`, `message.py`, `tool.py`, `registry.py`, `tasks/*.py`, `backends/*.py`, `prompts/system.md` — no changes.

---

## Architecture

```
Agent.run()
  ├── @logger.iteration(n:, max:)
  ├── @logger.prompt(messages:, tools:)
  ├── @client.call → response
  ├── @logger.raw(data: response)       [only if Boukensha.debug!]
  ├── parse response → stop_reason
  │
  ├─ tool_use → @logger.tool_call(name:, args:)
  │           → @registry.dispatch
  │           → @logger.tool_result(name:, result:, ok:, error:)
  │           → loop
  │
  └─ end_turn → @logger.response(text:, usage:, task:, backend:)
              → @logger.turn_end(reason:, iterations:)
              → return text
```

### `logger.rb` (143 LOC)

```ruby
class Logger
  DEFAULT_SESSION_DIR = "sessions"

  def initialize(session_id:, dir:, log:, snapshot:)
    @session_id = session_id || generate_session_id
    @path = log || File.join(dir || default_dir, "#{@session_id}.jsonl")
    FileUtils.mkdir_p(File.dirname(@path))
    @log_io = File.open(@path, "a")
    write_log({ phase: "session_start" }.merge(snapshot))
  end

  def iteration(n:, max:)
  def limit_reached(kind:, n:, max:)
  def turn_end(reason:, iterations:, tokens:)
  def prompt(messages:, tools:)
  def tool_call(name:, args:)
  def tool_result(name:, result:, ok:, error:)
  def response(text:, usage:, stop_reason:, task:, backend:)
  def raw(data:)        # only writes if Boukensha.debug?
  def close

  private
  def default_dir     → File.join(Boukensha.config.dir, "sessions")
  def write_log(event) → @log_io.puts(JSON.generate(event + session_id + timestamp))
  def generate_session_id
  def serialize_message(msg)
  def execution_metadata(task:, backend:, usage:)  → task, provider, model, tokens, cost
  def usage_tokens(usage)      → extract input/output from multiple key names
  def estimate_cost(backend, tokens) → backend.estimate_cost(...)
end
```

### `agent.rb` changes

- Constructor: `logger:` kwarg, defaults to `Logger.new`
- `run`: calls `@logger.iteration()`, `@logger.prompt()`, `@logger.raw(data: response)`
- `handle_tool_calls(content, response)`: now accepts `response`, logs response before dispatching
- New methods: `log_response(text:, response:)`, `normalized_usage(response)`
- `wrap_up`: logs response and turn_end

### `prompt_builder.rb` change

Add `attr_reader :backend` so Agent can access `@builder.backend` for logging metadata.

### `boukensha.rb` / `__init__.py` change

Module-level helpers for global state (quiet/debug/config):
```ruby
Boukensha.debug!   → sets @debug = true
Boukensha.debug?   → reads @debug
Boukensha.config   → lazy Config.new singleton
```

---

## Files to Create / Modify

| Action | File | Notes |
|---|---|---|
| CREATE | `boukensha/logger.py` | Port of `Logger` — JSONL writer to `.boukensha/sessions/` |
| UPDATE | `boukensha/agent.py` | Add `logger:` kwarg, `handle_tool_calls(content, response)`, `log_response`, `normalized_usage` |
| UPDATE | `boukensha/prompt_builder.py` | Add `backend` property |
| UPDATE | `boukensha/__init__.py` | Module-level `debug!`/`debug?`/`quiet!`/`quiet?`/`config`, import `Logger` |
| REWRITE | `examples/example.py` | Create Logger, pass to Agent |
| CREATE | `week1_baseline/bin/python/06_the_logger` | Bin script |
