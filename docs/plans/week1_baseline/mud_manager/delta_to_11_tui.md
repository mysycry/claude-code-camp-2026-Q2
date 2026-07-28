# Delta Plan: Carry 10_standard_tool_library changes into 11_tui

## Context

`11_tui` branched from `10_standard_tool_library`. Since then, several changes
were made to `10_standard_tool_library` (MUD daemon, MCP server, OpenCode
backend, quiet mode, LoadError guard) that were never ported to `11_tui`.
This plan lists every file that must be added, updated, or merged.

## 1. New files to add (exist in 10, absent from 11)

### 1.1 `lib/mud_daemon.rb` — NDJSON daemon
Copied verbatim from 10. Wraps `MudManager::Session` behind a TCP daemon that
speaks newline-delimited JSON. Python clients reach it via `~/.mud_manager/port`.

### 1.2 `bin/mud_daemon` — daemon entry point
Copied verbatim from 10. `#!/usr/bin/env ruby` that loads `lib/mud_daemon.rb`
and starts the server.

### 1.3 `lib/mud_mcp.rb` — MCP server
Copied verbatim from 10. JSON-RPC 2.0 over stdio with 27 tool definitions.
Auto-connects to CircleMUD via `MUD_USERNAME` / `MUD_PASSWORD`.

### 1.4 `bin/mud_mcp` — MCP server entry point
Copied verbatim from 10.

### 1.5 `bin/mud_grind` — combat grind script
Copied verbatim from 10. Directly uses `MudManager::Session` to walk, find
mobs, and kill them.

### 1.6 `bin/mud_explore` — map explorer
Copied verbatim from 10.

### 1.7 `bin/mud_debug` — raw MUD debug tool
Copied verbatim from 10.

### 1.8 `bin/mud_check` — quick MUD status check
Copied verbatim from 10.

### 1.9 `bin/mud_grind_test` — grind test harness
Copied verbatim from 10.

### 1.10 `lib/boukensha/backends/opencode.rb` — OpenCode backend
Copied verbatim from 10. Used by `Boukensha.run` and `Boukensha.repl` when
`backend: :opencode` is selected. Supports `deepseek-v4-flash-free`.

## 2. Existing files to update (content differs)

### 2.1 `lib/boukensha.rb` — main module

**Two deltas to port from 10 into 11:**

**Delta A — `@quiet` / `quiet!` / `loud!` / `quiet?`**
10 adds these four members to the module (after `@debug`). 11 lacks them.
Insert after `def self.debug?` block:

```ruby
def self.quiet!
  @quiet = true
end

def self.loud!
  @quiet = false
end

def self.quiet?
  @quiet
end
```

And add `@quiet = false` alongside `@debug = false` at the top of the module.

**Delta B — `:opencode` backend**
10's `self.run` and `self.repl` both have a `when :opencode` case. 11's
versions are missing it. In both methods, add:

```ruby
when :opencode     then ENV["OPENCODE_API_KEY"]
```

to the `api_key ||= case backend` block, and add:

```ruby
when :opencode     then Backends::OpenCode.new(api_key: api_key, model: model)
```

to the `be = case backend` block.

Also add `require_relative "boukensha/backends/opencode"` to the requires
at the bottom (after `openai`).

### 2.2 `lib/boukensha/tools/mud.rb` — MUD tools

**Delta — LoadError guard**
10 wraps the `require "mud_manager"` in a `begin/rescue LoadError` block so
the gem is optional. 11 has a bare `require "mud_manager"`. Replace line 1
in 11 with:

```ruby
begin
  require "mud_manager"
rescue LoadError
  # mud_manager not installed — MUD tools won't be available.
  # The Mud.register method below will be a no-op returning nil.
end
```

And update the `self.register` method to guard with
`unless defined?(MudManager)` (as 10 does) instead of relying on a
hard `require` failure.

### 2.3 `boukensha.gemspec` — gem specification

**Delta — make mud_manager optional**
10 comments out `spec.add_dependency "mud_manager"` because it's loaded
conditionally. 11 has it as a hard dependency. Change to optional:

```ruby
# MUD session management is optional — load via Gemfile when needed.
# spec.add_dependency "mud_manager", "~> 0.1"
```

(Keep the `charm` dependency — that's 11's addition.)

## 3. Already-different files that need NO changes

These files differ structurally between 10 and 11, but the differences belong
to 11's feature set (TUI plumbing) and don't need backporting:

| File | 11's addition | Keep as-is |
|------|--------------|-----------|
| `lib/boukensha/repl.rb` | `on_output` callback, `handle_command`, `attr_reader` | Yes — TUI integration |
| `lib/boukensha_loader.rb` | `--no-tui` flag | Yes — TUI integration |
| `lib/boukensha/tui.rb` | Whole file (TUI class) | Yes — 11-only |

## 4. Execution order

1. Add `backends/opencode.rb` + `require_relative` in `boukensha.rb`
2. Add `@quiet` / `quiet!` / `loud!` / `quiet?` to `boukensha.rb`
3. Add `:opencode` backend cases to both `run` and `repl` in `boukensha.rb`
4. Update `tools/mud.rb` with `LoadError` guard
5. Update `boukensha.gemspec` — make `mud_manager` optional
6. Copy `lib/mud_daemon.rb`, `lib/mud_mcp.rb` verbatim
7. Copy all `bin/mud_*` scripts verbatim
8. Verify: `ruby -c <file>` on every changed file
9. Verify: `gem build boukensha.gemspec && gem install boukensha-0.11.0.gem`
10. Smoke-test: `MUD_NAME=dummy MUD_PASSWORD=helloworld boukensha`

## 5. Files unchanged by this delta

The following shared files are identical between 10 and 11 and need no update:

```
lib/boukensha/agent.rb
lib/boukensha/client.rb
lib/boukensha/config.rb
lib/boukensha/context.rb
lib/boukensha/errors.rb
lib/boukensha/logger.rb
lib/boukensha/message.rb
lib/boukensha/prompt_builder.rb
lib/boukensha/registry.rb
lib/boukensha/run_dsl.rb
lib/boukensha/tool.rb
lib/boukensha/tasks/base.rb
lib/boukensha/tasks/player.rb
lib/boukensha/tools/file_system.rb
lib/boukensha/tools/shell.rb
lib/boukensha/backends/base.rb
lib/boukensha/backends/anthropic.rb
lib/boukensha/backends/gemini.rb
lib/boukensha/backends/ollama.rb
lib/boukensha/backends/ollama_cloud.rb
lib/boukensha/backends/openai.rb
lib/boukensha/version.rb           (different version string — correct as-is)
Gemfile                              (11 has "charm" gem — correct as-is)
Gemfile.lock                         (regenerate after changes)
prompts/system.md
examples/example.rb
```
