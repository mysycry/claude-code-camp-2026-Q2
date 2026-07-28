# Goal: Restrict tools so each task can only perform its intended role

- Added default-deny allow: rules per task.
- Added parameter-level rules such as restricting check to specific kinds.
- Validated permission rules against each tool's schema during startup.
- Preserved explicit MCP prefixes to prevent naming conflicts.
- Enforced permissions during both tool advertisement and dispatch.
- Later moved permission enforcement into the registry so native tools were also gated.
