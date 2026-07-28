# Python Port Plan: Step 12 — Context

**Starting point:** copy `python/11_tui/` → `python/12_context/`.

---

## What's New in Ruby Step 12

**Theme**: Eliminate the `tasks/` framework. Add token-aware context tracking with auto-compaction. Add reasoning/thinking block support to backends. Migrate OpenAI to Responses API.

### New file

| Ruby | Python | Description |
|---|---|---|
| `lib/boukensha/models.rb` | `boukensha/models.py` | Static model→context_window lookup table |

### Deleted files (remove from Python)

| File | Reason |
|---|---|
| `boukensha/tasks/__init__.py` | Tasks framework eliminated — config reads provider/model/limits directly |
| `boukensha/tasks/base.py` | Same |
| `boukensha/tasks/player.py` | Same |

### Changed files

| Ruby | Python | Changes |
|---|---|---|
| `lib/boukensha/version.rb` | `boukensha/version.py` | Bump to `0.12.0` |
| `lib/boukensha/config.rb` | `boukensha/config.py` | **Major rewrite**: remove `tasks()`, `user_prompts_dir`, `PROMPTS_DIR`. Add `provider_type`, `model`, `system_prompt`, `system_override?`, `agent_max_iterations`, `agent_max_output_tokens`, `agent_max_turn_tokens`, `agent_compaction_threshold`. Add `load_system_prompt` which reads `prompts/player/system.md` or `prompts/system.md`. |
| `lib/boukensha/context.rb` | `boukensha/context.py` | **Major rewrite**: remove `task`. Add `context_window`, `compaction_threshold`, `current_tokens`, `turn_tokens`. Add `update_tokens(n)`, `reset_turn_tokens()`, `add_turn_tokens(input, output)`, `usage_fraction`, `usage_pct`, `needs_compaction?(threshold)`, `compact_messages!`. `clear_messages!` now also resets `current_tokens`. |
| `lib/boukensha/agent.rb` | `boukensha/agent.py` | **Substantial**: remove `task_settings`. Add `max_turn_tokens`, `token_limit_reached?`, `record_usage(response)`, `compact_if_needed`, `log_reasoning(content)`. `run()` calls `reset_turn_tokens` + `compact_if_needed` at top. Checks two limits (iteration + token). Extract `extract_text` joins with `\n`. `handle_tool_calls` logs `plan` + `response` before tool dispatch. `wrap_up` records usage. |
| `lib/boukensha/logger.rb` | `boukensha/logger.py` | Add `compaction(before:, dropped:, context_window:)`, `reasoning(text:, redacted:)`, `plan(text:)` events. Add `context_window:` to `prompt()`. Simplify `response()` — remove task/backend metadata and cost estimation. Remove all `_usage_tokens`, `estimate_cost`, `execution_metadata` helpers. |
| `lib/boukensha/repl.rb` | `boukensha/repl.py` | Add `/compact` command and HELP line. Replace `task_settings` with `max_turn_tokens` in constructor and Agent construction. |
| `lib/boukensha.rb` | `boukensha/__init__.py` | Remove `task_class`/`task_settings` pattern. Add `context_window:` param. Use `cfg.system_prompt`, `cfg.model`, `cfg.provider_type` directly. Pass `context_window` to `Context`. Pass `max_turn_tokens` from `cfg.agent_max_turn_tokens`. |
| `lib/boukensha/backends/anthropic.rb` | `boukensha/backends/anthropic.py` | Add `normalize_block(block)` to convert `thinking`→`reasoning` and `redacted_thinking`→`reasoning` blocks. Add `assistant_content(content)` and `denormalize_block` to reverse mapping for round-trip. |
| `lib/boukensha/backends/gemini.rb` | `boukensha/backends/gemini.py` | Update models table. Add `thinking_config` to payload. Parse `thought` parts as reasoning blocks. Add `thoughtSignature` to tool_use blocks. |
| `lib/boukensha/backends/openai.rb` | `boukensha/backends/openai.py` | **Migrate from Chat Completions to Responses API**: URL→`/v1/responses`, `messages`→`input`, `system`→`instructions`, flat tools (no `function:` wrapper), `function_call_output` items for tool results, `assistant_items` returns array of items. Parse `reasoning` output items. |
| `lib/boukensha/backends/ollama.rb` | `boukensha/backends/ollama.py` | Add `think: false` to payload. Parse `message["thinking"]` as reasoning blocks. |
| `lib/boukensha/backends/ollama_cloud.rb` | `boukensha/backends/ollama_cloud.py` | Same as ollama — add `think: false`, reasoning parsing. |
| `lib/boukensha/tools/file_system.rb` | `boukensha/tools/file_system.py` | Disable `list_directory` and `search_files` tools (comment out registration). |
| `lib/boukensha/tools/mud.rb` | `boukensha/tools/mud.py` | Remove `begin/rescue LoadError` guard — `mud_manager` is now a hard dependency. |
| `lib/boukensha/tui.rb` | `boukensha/tui.py` | (Stub — skip implementation details) |

---

## Files to Create / Modify / Delete

| Action | File |
|---|---|
| CREATE | `boukensha/models.py` |
| DELETE | `boukensha/tasks/` (3 files) |
| OVERWRITE | `boukensha/config.py` |
| OVERWRITE | `boukensha/context.py` |
| OVERWRITE | `boukensha/agent.py` |
| OVERWRITE | `boukensha/logger.py` |
| OVERWRITE | `boukensha/__init__.py` |
| OVERWRITE | `boukensha/backends/anthropic.py` |
| OVERWRITE | `boukensha/backends/gemini.py` |
| OVERWRITE | `boukensha/backends/openai.py` |
| OVERWRITE | `boukensha/backends/ollama.py` |
| OVERWRITE | `boukensha/backends/ollama_cloud.py` |
| UPDATE | `boukensha/repl.py` — add /compact, max_turn_tokens |
| UPDATE | `boukensha/version.py` — bump |
| UPDATE | `boukensha/tools/file_system.py` — disable list_directory + search_files |
| UPDATE | `boukensha/tools/mud.py` — remove LoadError guard |
| UPDATE | `examples/example.py` — update if needed |
| CREATE | `week1_baseline/bin/python/12_context` |

---

## Questions

1. **Config system prompt resolution**: Python's Config needs to match Ruby's `load_system_prompt` which checks `prompts/player/system.md` first (if `tasks.player.prompt_override.system` is true), then falls back to `prompts/system.md`. Should the Python config look for these files in `BOUKENSHA_DIR/prompts/` or in the step directory's `prompts/`? → Following Ruby: reads from `BOUKENSHA_DIR/prompts/`.

2. **OpenAI Responses API**: The Ruby backend now targets `/v1/responses` instead of `/v1/chat/completions`. This changes the entire message format. The Python port must mirror this exactly. The `to_input` method maps messages to Responses API items.

3. **Agent extract_text join**: Ruby changed from `.join` to `.join("\n")`. Python's agent already uses `"\n".join(...)` in some places — verify consistency.
