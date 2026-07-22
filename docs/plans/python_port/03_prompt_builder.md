# Python Port Plan: Step 03 — The Prompt Builder

**Starting point:** copy `python/02_the_registry/` → `python/03_prompt_builder/`.
Then add the PromptBuilder, backends, and default prompt that Step 03 introduces.

---

## What's New in Step 03

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `backends/base.rb` | `boukensha/backends/__init__.py` + `boukensha/backends/base.py` | Abstract base with model validation, cost helpers |
| `backends/anthropic.rb` | `boukensha/backends/anthropic.py` | Anthropic API format (`input_schema`, `tool_result` as user msg) |
| `backends/ollama.rb` | `boukensha/backends/ollama.py` | Ollama API format (`tool_name`, local endpoint) |
| `backends/ollama_cloud.rb` | `boukensha/backends/ollama_cloud.py` | Ollama Cloud API format (Bearer auth at `ollama.com/api/chat`) |
| `backends/openai.rb` | `boukensha/backends/openai.py` | OpenAI format (`function`-wrapped tools, `tool_call_id`) |
| `backends/gemini.rb` | `boukensha/backends/gemini.py` | Gemini format (`functionDeclarations`, `parts`, `functionResponse`) |
| `backends/opencode.rb` | `boukensha/backends/opencode.py` | OpenCode Zen (inherits OpenAI, overrides URL + free models) |
| `prompt_builder.rb` | `boukensha/prompt_builder.py` | Delegates messages/tools/payload/headers/url to the backend |
| `errors.rb` | `boukensha/errors.py` | Add `UnsupportedModelError` |
| `lib/boukensha.rb` | `boukensha/__init__.py` | Add imports for all backends + PromptBuilder |
| `prompts/system.md` | `boukensha/prompts/system.md` | Already exists — no action needed |
| `examples/example.rb` | `examples/example.py` | Rewrite using PromptBuilder + backends, output JSON payload |

## What Stays the Same

`config.py`, `context.py`, `tool.py`, `message.py`, `registry.py`, `tasks/`, `pyproject.toml` — no changes.

---

## Architecture

```
Context (Tool, Message objects)
        ↓
PromptBuilder
        ↓
Backend (Anthropic | OpenAI | Gemini | Ollama | OllamaCloud | OpenCode)
        ↓
API Payload (plain dicts)  ←  to_api_payload()
Headers                   ←  headers()
URL                       ←  url()
```

### `prompt_builder.rb` (28 LOC)

```ruby
class PromptBuilder
  def initialize(context, backend)
    @context, @backend = context, backend
  end

  def to_messages       = @backend.to_messages(@context.messages)
  def to_tools           = @backend.to_tools(@context.tools)
  def to_api_payload     = @backend.to_payload(@context, ...)
  def headers            = @backend.headers
  def url                = @backend.url
end
```

Python: `PromptBuilder` stores `context` and `backend`, delegates each method.

### `backends/base.rb` (65 LOC)

- Class-level: `.models`, `.model_info(name)`, `.validate_model!(name)`
- Instance: `context_window`, `input_token_cost_per_million`, `output_token_cost_per_million`, `usage_unit`, `usage_level`, `estimate_cost(input_tokens, output_tokens)`
- Subclasses implement: `__init__`, `to_messages`, `to_tools`, `to_payload`, `headers`, `url`

### Backend API Format Differences

| Concern | Anthropic | OpenAI / OpenCode | Ollama / OllamaCloud | Gemini |
|---|---|---|---|---|
| System prompt | Top-level `system` field | `role: system` in messages | `role: system` in messages | `systemInstruction.parts[0].text` |
| Tool result | `role: user` with `tool_result` content block | `role: tool` with `tool_call_id` | `role: tool` with `tool_name` | `role: user` with `functionResponse` part |
| Tool definition | `input_schema` (no `type: "function"` wrapper) | `type: "function"` → `function.name/description/parameters` | Same as OpenAI | `functionDeclarations` array |
| Auth | `x-api-key` header | `Authorization: Bearer` | None (ollama) / Bearer (cloud) | `x-goog-api-key` header |

### `errors.rb` change

Add `UnsupportedModelError` alongside existing `UnknownToolError`:

```ruby
class UnknownToolError < StandardError; end
class UnsupportedModelError < StandardError; end
```

### `example.rb` (62 LOC)

- Creates Config, gets player settings + system prompt
- Creates Context + Registry, registers `look` and `move` tools
- Adds 3 messages (user, assistant, tool_result) — includes a `tool_use_id` field this step
- Reads provider/model from settings
- Case-switches on provider to instantiate the correct backend
- Creates `PromptBuilder.new(ctx, backend)`
- Prints `JSON.pretty_generate(builder.to_api_payload)`

---

## Files to Create / Modify

| Action | File |
|---|---|
| CREATE | `boukensha/backends/__init__.py` |
| CREATE | `boukensha/backends/base.py` |
| CREATE | `boukensha/backends/anthropic.py` |
| CREATE | `boukensha/backends/ollama.py` |
| CREATE | `boukensha/backends/ollama_cloud.py` |
| CREATE | `boukensha/backends/openai.py` |
| CREATE | `boukensha/backends/gemini.py` |
| CREATE | `boukensha/backends/opencode.py` |
| CREATE | `boukensha/prompt_builder.py` |
| UPDATE | `boukensha/errors.py` — add `UnsupportedModelError` |
| UPDATE | `boukensha/__init__.py` — import all backends + PromptBuilder |
| REWRITE | `examples/example.py` — PromptBuilder + backend dispatch + JSON output |

## Questions

1. **Backend `to_messages` signature mismatch** — Ruby backends have inconsistent signatures: `Anthropic#to_messages(messages)` (no system), `OpenAI#to_messages(system, messages)`, `Gemini#to_messages(messages)`. The `PromptBuilder` delegates to the backend directly. Should Python standardize on `to_messages(context)` (passing the full context so the backend can extract system + messages) or mirror Ruby's inconsistency? mirror ruby

2. **Ollama/OllamaCloud vs OpenAI tool format** — Ruby OpenAI and Ollama share identical `to_messages` and `to_tools` logic, yet are separate classes. Python: share via inheritance or keep separate? mirror ruby

3. **`advertised_context_window` on OllamaCloud** — The `minimax-m3:cloud` Ruby model entry has an extra field `advertised_context_window` that `base.rb` doesn't use. Include it in Python or leave it out? keep it i guess
