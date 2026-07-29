# Goal: Restrict tools so each task can only perform its intended role

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/ruby/12_context/lib/boukensha/registry.rb` | `dispatch()` gate that enforces permission rules before tool execution |
| `week1_baseline/ruby/12_context/lib/boukensha/tools/shell.rb` | Example of tool-level restrictions — `allowed_commands` parameter limits which executables the agent can run |
| Task definition files | Each task specifies `allow:` rules listing which tools its agent may call |

## Key Architecture Decisions

- **Default-deny**: A task must explicitly declare which tools it's allowed to use. If no `allow:` rules match, the tool is not advertised to the model and dispatch is blocked.
- **Parameter-level restrictions**: Some tools are restricted beyond the tool level. For example, the `check` tool can be limited to specific `kind` values (`score`, `inventory`, `equipment`, `exits`) depending on the task's role.
- **Startup validation**: Permission rules are validated against each tool's parameter schema when the registry is built. A rule referencing a non-existent parameter is caught early.
- **MCP prefix preservation**: When tools come from MCP servers, the server prefix is preserved to prevent naming collisions between servers (e.g., `mud__look` vs `file__look`).
- **Dual enforcement**: Permissions are checked both at advertisement (what the model sees as available tools) and at dispatch (actual gating when the model calls a tool). This prevents the model from "seeing" tools it can't use.

## Key Findings

- The permission system was initially written for MCP tools only, then extended to gate native tools via the registry.
- Without enforcement at both advertisement and dispatch, the model could attempt to call tools it had seen in earlier turns or training data.
- Parameter-level restrictions are essential for tools like `check` that cover multiple resource types.

## Verification

```ruby
# A task without inspect_room permission should not be able to call it
registry = Registry.new(tools: [look_tool, inspect_room_tool], allow: ["look"])
refute registry.allowed?("inspect_room")
```
