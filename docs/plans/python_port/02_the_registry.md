# Python Port Plan: Step 02 — The Tool Registry

**Starting point:** your existing `python/02_the_registry/` (carried forward from `01_struct_skeleton`).
Port only the *new* Ruby files that Step 02 adds — the `Registry` class and tool dispatch.

---

## What's New in Step 02

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `ruby/02_the_registry/lib/boukensha/errors.rb` | `python/02_the_registry/boukensha/errors.py` | `UnknownToolError` exception class |
| `ruby/02_the_registry/lib/boukensha/registry.rb` | `python/02_the_registry/boukensha/registry.py` | `Registry` class — `tool()` to register, `dispatch()` to invoke |
| `ruby/02_the_registry/lib/boukensha.rb` | → update `python/02_the_registry/boukensha/__init__.py` | Add `Registry`, `UnknownToolError` to exports |
| `ruby/02_the_registry/examples/example.rb` | `python/02_the_registry/examples/example.py` | Rewrite using `Registry` and dispatch flow |

## What Stays the Same

Everything else (`config.py`, `context.py`, `tool.py`, `message.py`, `tasks/`, `pyproject.toml`, `prompts/`) — no changes needed.

---

## Architecture (per Ruby source)

### `errors.rb` (3 LOC)

```ruby
module Boukensha
  class UnknownToolError < StandardError; end
end
```

Python: simple `class UnknownToolError(Exception): pass` in `errors.py`.

### `registry.rb` (18 LOC)

```ruby
class Registry
  def initialize(context)
    @context = context
  end

  def tool(name, description:, parameters: {}, &block)
    tool = Tool.new(name.to_s, description, parameters, block)
    @context.register_tool(tool)
    tool
  end

  def dispatch(name, args = {})
    tool = @context.tools[name.to_s]
    raise UnknownToolError, "No tool registered as '#{name}'" unless tool
    tool.block.call(**args.transform_keys(&:to_sym))
  end
end
```

Key behaviors:
- Wraps a `Context` — tools still live on `Context.tools` (architectural debt noted in README)
- `tool(name, description, parameters, block)` — creates a `Tool` and registers via `Context.register_tool`
- `dispatch(name, args)` — looks up tool by name (string-keyed), raises `UnknownToolError` if missing, calls the block with keyword args (Ruby converts string keys → symbol keys)

Python equivalent:
- `Registry.__init__(self, context)` — store context reference
- `Registry.tool(self, name, description, parameters, block)` — create `Tool`, register on context
- `Registry.dispatch(self, name, args)` — lookup tool, raise if missing, call `tool.block(**args)`
- Ruby's `transform_keys(&:to_sym)` → unnecessary in Python since Python dict keys are already strings (no symbol type)

### `example.rb` changes

Old (Step 01): direct `ctx.register_tool(Tool(...))`
New (Step 02):
```ruby
registry = Boukensha::Registry.new(ctx)
registry.tool("move", description: ..., parameters: {...}) do |direction:|
  "You move #{direction}..."
end
registry.tool("shout", description: ..., parameters: {...}) do |message:|
  message.upcase
end

result = registry.dispatch("shout", { "message" => "dragon spotted" })
result = registry.dispatch("move", { "direction" => "north" })

begin
  registry.dispatch("flee")
rescue Boukensha::UnknownToolError => e
  puts e.message
end
```

---

## Files to Create / Modify

| Action | File |
|---|---|
| **CREATE** | `python/02_the_registry/boukensha/errors.py` |
| **CREATE** | `python/02_the_registry/boukensha/registry.py` |
| **UPDATE** | `python/02_the_registry/boukensha/__init__.py` — add `Registry`, `UnknownToolError` imports |
| **REWRITE** | `python/02_the_registry/examples/example.py` — use `Registry`, dispatch, error handling |

---

## Questions

1. **Keyword args in dispatch** — Ruby registry blocks use keyword args (`|direction:|`, `|message:|`). Python equivalent: `tool.block(**args)`. Since the Tool stores `block` as a `Callable`, the lambdas need to accept `**kwargs` or named params. Will the example lambdas work with `**kwargs` dispatch?

2. **`transform_keys` concern** — Ruby converts string keys to symbol keys. Python dicts don't have symbols, so this step is skipped entirely. The `dispatch` method passes `args` dict as `**args` directly. OK?
