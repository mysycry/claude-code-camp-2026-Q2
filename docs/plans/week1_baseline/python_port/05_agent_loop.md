# Python Port Plan: Step 05 — The Agent Loop

**Starting point:** copy `python/04_api_client/` → `python/05_agent_loop/`.
Then add the Agent loop class, `parse_response` on all backends, `assistant_message` helpers, and task config defaults.

---

## What's New in Step 05

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `agent.rb` | `boukensha/agent.py` | **NEW** — The agent loop: `run`, `handle_tool_calls`, `wrap_up`, limits |
| `errors.rb` | `boukensha/errors.py` | Add `LoopError` |
| `prompt_builder.rb` | `boukensha/prompt_builder.py` | Add `parse_response`; `to_api_payload` gains `tools:` kwarg |
| `client.rb` | `boukensha/client.py` | `call` gains `tools:` kwarg, passes through to `builder.to_api_payload` |
| `backends/anthropic.rb` | `boukensha/backends/anthropic.py` | Add `to_payload(tools:)` kwarg, add `parse_response` |
| `backends/openai.rb` | `boukensha/backends/openai.py` | Add `to_payload(tools:)`, `parse_response`, `assistant_message` (private) |
| `backends/gemini.rb` | `boukensha/backends/gemini.py` | Add `to_payload(tools:)`, `parse_response`, `assistant_parts` (private); `to_messages` handles `:assistant` role |
| `backends/ollama.rb` | `boukensha/backends/ollama.py` | Add `to_payload(tools:)`, `parse_response`, `assistant_message` (private); `to_messages` handles `:assistant` role |
| `backends/ollama_cloud.rb` | `boukensha/backends/ollama_cloud.py` | Add `to_payload(tools:)`, `parse_response`, `assistant_message` (private); `to_messages` handles `:assistant` role |
| `backends/opencode.rb` | `boukensha/backends/opencode.py` | No change needed — inherits all from OpenAI |
| `tasks/base.rb` | `boukensha/tasks/base.py` | Add `max_iterations`, `max_output_tokens` class methods with defaults |
| `tasks/player.rb` | `boukensha/tasks/player.py` | No change needed — inherits from Base |
| `lib/boukensha.rb` | `boukensha/__init__.py` | Add import for `Agent`, `LoopError` |
| `examples/example.rb` | `examples/example.py` | **REWRITE** — uses `Agent.run()`, `read_file`/`list_directory` tools, prints final response |

---

## What Stays the Same

`config.py`, `context.py`, `tool.py`, `message.py`, `registry.py`, `backends/base.py`, `prompts/system.md` — no changes.

---

## Architecture

```
Agent.run()
  ↓  (loop)
    Client.call(tools:, max_output_tokens:)
    PromptBuilder.parse_response(response)  → normalized shape
    ↓
    stop_reason == "tool_use"?
      yes → handle_tool_calls(content)
              → dispatch via Registry
              → inject tool_result messages
              → continue loop
      no  → return final text
    ↓
    iteration_limit_reached? → wrap_up() → return final text
```

### Normalized response shape (shared by all backends)

```python
{
    "stop_reason": "tool_use" | "end_turn",
    "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
    ]
}
```

### `agent.rb` (111 LOC) — what to port

```ruby
class Agent
  MAX_ITERATIONS = 25
  WRAP_UP_OUTPUT_TOKENS = 400
  WRAP_UP_DIRECTIVE = "..."

  def initialize(context:, registry:, builder:, client:, task_settings:, max_iterations:, max_output_tokens:)
    @max_iterations = resolve from task_settings or explicit or MAX_ITERATIONS
    @max_output_tokens = resolve from task_settings or explicit
  end

  def run
    loop:
      return wrap_up if iteration_limit_reached?
      @iteration += 1
      response = @client.call(**call_opts)
      parsed   = @builder.parse_response(response)
      if parsed[:stop_reason] == "tool_use"
        handle_tool_calls(parsed[:content])
      else
        return extract_text(parsed[:content])
      end
  end

  private

  def handle_tool_calls(content):
    @context.add_message(:assistant, content)
    content.filter { "tool_use" }.each:
      dispatch tool via @registry
      @context.add_message(:tool_result, result, tool_use_id: id)

  def wrap_up(reason):
    add WRAP_UP_DIRECTIVE as user message
    client.call(tools: [], max_output_tokens: 400)
    extract text from parsed response
    fallback if empty

  def extract_text(content):
    join all "text" blocks
end
```

### Key behavioral notes

- **`to_payload(tools: nil)`** — When `tools:` is explicitly passed (e.g. `[]` for wrap-up), use that instead of `context.tools`. When `nil`, fall back to `context.tools` (existing behavior).
- **`client.call(tools: nil, max_output_tokens:)`** — Now passes `tools` through to `builder.to_api_payload`.
- **`assistant_message(content)`** — Private method on OpenAI/Ollama/OllamaCloud backends. When an assistant message with `tool_use` blocks is replayed, it must be reconstructed in the provider's wire format (with `tool_calls` array). When content is a string, wraps it as `[{type: "text", text: content}]`.
- **`assistant_parts(content)`** — Same concept for Gemini's `parts` format.
- **Anthropic** needs no `assistant_message` — its `content` array is already the normalized shape and the wire format simultaneously.
- **`parse_response`** — Each backend converts its raw API response into the normalized shape. See Ruby implementations for exact field mappings.

---

## Files to Create / Modify

| Action | File | Notes |
|---|---|---|
| CREATE | `boukensha/agent.py` | Port of `Agent` class |
| UPDATE | `boukensha/errors.py` | Add `class LoopError(Exception): pass` |
| UPDATE | `boukensha/prompt_builder.py` | Add `parse_response(self, response)`; `to_api_payload` gains `tools=None` kwarg |
| UPDATE | `boukensha/client.py` | `call` gains `tools=None` kwarg, passes to `builder.to_api_payload` |
| UPDATE | `boukensha/backends/anthropic.py` | `to_payload` gains `tools=None` kwarg; add `parse_response` |
| UPDATE | `boukensha/backends/openai.py` | `to_payload` gains `tools=None` kwarg; add `parse_response`; add private `_assistant_message` |
| UPDATE | `boukensha/backends/gemini.py` | `to_payload` gains `tools=None` kwarg; add `parse_response`; add private `_assistant_parts`; `to_messages` handle `:assistant` role |
| UPDATE | `boukensha/backends/ollama.py` | `to_payload` gains `tools=None` kwarg; add `parse_response`; add private `_assistant_message`; `to_messages` handle `:assistant` role |
| UPDATE | `boukensha/backends/ollama_cloud.py` | `to_payload` gains `tools=None` kwarg; add `parse_response`; add private `_assistant_message`; `to_messages` handle `:assistant` role |
| UPDATE | `boukensha/tasks/base.py` | Add `max_iterations` and `max_output_tokens` class methods |
| UPDATE | `boukensha/__init__.py` | Import `Agent`, `LoopError` |
| REWRITE | `examples/example.py` | Uses `Agent.run()`, `read_file`/`list_directory` tools, prints final response |

---

## Questions

1. **`assistant_message` vs inline** — Ruby OpenAI/Ollama/OllamaCloud/Gemini all have private helper methods to rebuild assistant messages from normalized content. Python should mirror this exactly with private `_assistant_message` / `_assistant_parts` methods. **mirror ruby**
2. **`to_payload(tools:)` signature** — All backends get `tools=None` kwarg added. When `None`, falls back to `to_tools(context.tools)`. When explicitly set (even to `[]`), uses it directly. **mirror ruby**
