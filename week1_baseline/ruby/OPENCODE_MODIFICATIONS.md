# OpenCode Provider Modifications (Steps 03–10)

The `opencode` backend ([api.opencode.ai](https://opencode.ai)) was added retroactively to
every Ruby step that had a backends directory, so the framework can run using free-tier
OpenCode models (`deepseek-v4-flash-free`) instead of paid API keys.

## What was added

Each modified step received up to three changes:

### 1. Backend class `lib/boukensha/backends/opencode.rb`

```ruby
module Boukensha
  module Backends
    class OpenCode < Base
      BASE_URL = "https://api.opencode.ai/v1"
      SUPPORTED_MODELS = %w[deepseek-v4-flash-free].freeze
      # ...
    end
  end
end
```

Created in every step from **03** onward. Earlier steps (00–02) don't have a backends
directory.

### 2. `require_relative` in `lib/boukensha.rb`

```ruby
require_relative "boukensha/backends/opencode"
```

Added alongside the other backend requires. Present in **03–10**.

### 3. Dispatch wiring in `lib/boukensha.rb`

Steps that define `Boukensha.run` and/or `Boukensha.repl` have one or two `case backend`
blocks. Each needed three additions:

| What | Before | After |
|------|--------|-------|
| API key lookup | `when :ollama_cloud then ENV["OLLAMA_API_KEY"]` | `when :opencode then ENV["OPENCODE_API_KEY"]` |
| Backend instantiation | `when :ollama_cloud then Backends::OllamaCloud.new(...)` | `when :opencode then Backends::OpenCode.new(...)` |
| Error message | `"Use :anthropic, :openai, :gemini, :ollama, or :ollama_cloud."` | `"Use :anthropic, :openai, :gemini, :ollama, :ollama_cloud, or :opencode."` |

### 4. Bin script fixes

`bin/ruby/09_global_executable` was changed from:

```bash
bundle exec ruby examples/example.rb
```

to:

```bash
ruby bin/boukensha
```

because step 09 has no `examples/` directory — its entry point is `bin/boukensha` (which
uses `BoukenshaLoader` to resolve and start the REPL).

Step 10's bin script was also fixed: the cd path had a typo (`standarad` → `standard`),
and `bundle exec` was added to load gems declared in the gemspec. The correctly-spelled
script was created at `bin/ruby/10_standard_tool_library`.

## Step 10 additional fix: `mud_manager` made optional

Step 10 depends on `mud_manager` for its MUD gameplay tools, but the gem was removed
from rubygems.org. Two changes make the step operable without it:

### `boukensha.gemspec`
The hard dependency was commented out so `bundle install` succeeds:

```ruby
# spec.add_dependency "mud_manager", "~> 0.1"
```

### `lib/boukensha/tools/mud.rb`
The `require "mud_manager"` was wrapped in a `rescue LoadError`, and `Mud.register`
returns early with a warning when the gem isn't available:

```ruby
begin
  require "mud_manager"
rescue LoadError
  # mud_manager not installed — MUD tools won't be available.
end

def self.register(registry, host: "localhost", port: 4000, name:, password:)
  unless defined?(MudManager)
    warn "[boukensha] mud_manager gem not available — MUD tools disabled"
    return
  end
  # ...
end
```

## Per-step summary

| Step | Backend file | `require_relative` | `run()` dispatch | `repl()` dispatch | Notes |
|------|-------------|-------------------|-----------------|-------------------|-------|
| 00 | — | — | — | — | No backends directory |
| 01 | — | — | — | — | No backends directory |
| 02 | — | — | — | — | No backends directory |
| 03 | added | added | — | — | Only `base.rb` backend exists; `run()` doesn't exist yet |
| 04 | added | added | — | — | Only `base.rb` backend exists; `run()` doesn't exist yet |
| 05 | added | added | added | — | Single `case backend` in `run()` |
| 06 | added | added | added | — | Single `case backend` in `run()` |
| 07 | added | added | added | — | Single `case backend` in `run()` |
| 08 | added | added | 2 blocks | 2 blocks | Both `run()` and `repl()` dispatch |
| 09 | added | added | 2 blocks | 2 blocks | Both `run()` and `repl()` dispatch; bin script fixed |
| 10 | added | added | 2 blocks | 2 blocks | `mud_manager` gem yanked from rubygems — made optional in mud.rb and gemspec |

## Running with OpenCode

```bash
export OPENCODE_API_KEY="sk-..."
./bin/ruby/07_the_run_dsl    # uses :opencode by default (set in settings.yaml)
```

The `.boukensha/settings.yaml` at the repo root sets:

```yaml
tasks:
  player:
    provider: opencode
    model: deepseek-v4-flash-free
```

so every step picks up OpenCode automatically without passing explicit arguments.

---

## Python Port Notes

The `week1_baseline/python/` steps are ports of the Ruby steps. Key differences in the Python port:

### OpenCode backend URL

- **Ruby**: `BASE_URL = "https://api.opencode.ai/v1"` — OpenCode was initially a standalone `Base` subclass in Ruby 09–10 with a different URL that doesn't actually work.
- **Python**: `BASE_URL = "https://opencode.ai/zen/v1/chat/completions"` — Inherits from `OpenAI` (since OpenCode's API is OpenAI-compatible) and uses the working Zen API endpoint.

This was corrected during the Python port of step 03 and carried forward.

### Step 04 (`client.py`)

Python's `Client` sets `User-Agent: boukensha/0.1.0` because `urllib.request` defaults to `Python-urllib/3.x` which OpenCode blocks with 403. Ruby's `net/http` default of `"Ruby"` is typically allowed.

### Step 10 (`tools/mud.py`)

`mud_manager` has no Python equivalent. `Mud.register` logs a single warning and returns, matching the Ruby behavior of printing `[boukensha] mud_manager gem not available — MUD tools disabled`.

### Version alignment

| Step | Ruby VERSION | Python VERSION |
|------|-------------|---------------|
| 09 | `0.9.0` | `0.8.0` |
| 10 | `0.10.0` | `0.10.0` |

Step 09 Python used a dev version number (`0.8.0`). Step 10 Python was bumped to match Ruby's `0.10.0`.

### Working directory auto-registration

Ruby step 10 introduced `Boukensha.run(working_dir:)` and `Boukensha.repl(working_dir:)` which auto-register `FileSystem` and `Shell` tools. Python's `run()` and `repl()` in step 10 were ported to accept `working_dir`, `allowed_commands`, `shell_timeout`, and `mud` parameters, with `_resolve_mud()` handling config-based MUD resolution.
