# Python Port Plan: Step 01 — The Struct Skeleton

**Starting point:** copy `week1_baseline/python/00_config/` → `week1_baseline/python/01_struct_skeleton/`.
Then port only the *new* Ruby files that Step 01 adds on top of Step 00.

---

## What's New in Step 01 (Ruby → Python)

| Ruby Source (new in 01) | Python Target | What It Does |
|---|---|---|
| `ruby/01_struct_skeleton/lib/boukensha/tool.rb` | `python/01_struct_skeleton/boukensha/tool.py` | `Tool` data container — `name`, `description`, `parameters`, `block` |
| `ruby/01_struct_skeleton/lib/boukensha/message.rb` | `python/01_struct_skeleton/boukensha/message.py` | `Message` data container — `role`, `content`, `tool_use_id` |
| `ruby/01_struct_skeleton/lib/boukensha/context.rb` | `python/01_struct_skeleton/boukensha/context.py` | `Context` class — holds `system`, `messages`, `tools`, `task` |
| `ruby/01_struct_skeleton/lib/boukensha.rb` | → update `python/01_struct_skeleton/boukensha/__init__.py` | Add imports for `Tool`, `Message`, `Context` |
| `ruby/01_struct_skeleton/examples/example.rb` | `python/01_struct_skeleton/examples/example.py` | Smoke-test using all three new structs |

## What Stays the Same (carried forward from 00_config Python)

| File | Action |
|---|---|
| `boukensha/config.py` | Copy as-is (no changes from Step 00) |
| `boukensha/tasks/base.py` | Copy as-is |
| `boukensha/tasks/player.py` | Copy as-is |
| `boukensha/prompts/system.md` | Copy as-is |
| `pyproject.toml` | Copy as-is |

## Bin Scripts

| File | What It Does |
|---|---|
| `week1_baseline/bin/python/01_struct_skeleton` | Runs the example via root `.venv` (same pattern as `00_config`) |
| `bin/python/01_struct_skeleton` | Top-level convenience wrapper |

## Dependencies

No new dependencies. Tool/Message/Context use stdlib only (`dataclasses`, `typing`).

---

## Architecture (per Ruby source)

### `tool.rb` (7 LOC)

Ruby `Struct.new(:name, :description, :parameters, :block)`:

```ruby
Tool = Struct.new(:name, :description, :parameters, :block) do
  def to_s
    "#<Tool name=#{name} description=#{description.to_s[0..40]} params=#{parameters.keys}>"
  end
end
```

Python: `@dataclass`.

- `name: str`
- `description: str`
- `parameters: dict` — maps param name → `{type: str, description: str}`
- `block: callable` — Ruby `Proc`/`lambda` → Python `Callable`

### `message.rb` (8 LOC)

```ruby
Message = Struct.new(:role, :content, :tool_use_id) do
  def to_s
    id_tag = tool_use_id ? " [#{tool_use_id}]" : ""
    "#<Message role=#{role}#{id_tag} content=#{content.to_s[0..60]}...>"
  end
end
```

- `role: str` — `"user"`, `"assistant"`, or `"tool_result"`
- `content: str | None`
- `tool_use_id: str | None`

### `context.rb` (30 LOC)

```ruby
class Context
  attr_reader :task, :system, :messages, :tools

  def initialize(task:, system: nil)
    @task, @system = task, system
    @messages, @tools = [], {}
  end

  def register_tool(tool);  @tools[tool.name] = tool; end
  def add_message(role, content, tool_use_id: nil)
    @messages << Message.new(role, content, tool_use_id)
  end
  def tool_count = @tools.size
  def turn_count = @messages.size
end
```

- `task` — stores the task *class* (e.g. `Player`), not an instance
- `system` — system prompt string
- `messages` — list of `Message` objects
- `tools` — dict of `name → Tool`
- `register_tool(tool)` — stores by `tool.name`
- `add_message(role, content, tool_use_id=)` — creates and appends a `Message`

### `example.rb` (34 LOC)

```ruby
config = Boukensha::Config.new
player_settings = config.tasks(:player)
system_prompt = Boukensha::Tasks::Player.system_prompt(player_settings, user_prompts_dir: config.user_prompts_dir)

ctx = Boukensha::Context.new(task: Boukensha::Tasks::Player, system: system_prompt)

ctx.register_tool(Boukensha::Tool.new("move", "Move the player...", {direction: {type: "string", ...}}, ->(d) { "..." }))

ctx.add_message(:user, "Explore north and tell me what you find.")
ctx.add_message(:assistant, "Sure, let me head north and take a look.")

puts config
puts ctx
puts ctx.tools['move']
ctx.messages.each { |m| puts "  #{m}" }
```

---

## Files to Create (only 5)

```
week1_baseline/python/01_struct_skeleton/
├── boukensha/
│   ├── __init__.py          ← update (add Tool, Message, Context imports)
│   ├── tool.py              ← NEW
│   ├── message.py           ← NEW
│   └── context.py           ← NEW
├── examples/
│   └── example.py           ← NEW
```

Everything else (`config.py`, `tasks/`, `prompts/`, `pyproject.toml`) is copied unchanged from `00_config`.

## Questions

1. **Tool `parameters` shape** — Ruby uses `{ direction: { type: "string", description: "..." } }`. Python: `dict[str, dict]` OK?

2. **Context `task` field** — Ruby stores the task *class* (e.g. `Boukensha::Tasks::Player`). Python: store the class reference or just `task_name` as a string?

3. **`token_budget` field** — README mentions it but Ruby code doesn't implement it yet. Add a `token_budget` field to `Context` or leave it out?
