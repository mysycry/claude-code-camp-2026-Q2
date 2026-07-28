# Goal: Delegate room investigation so the player remains focused on orchestration

- Added a room_inspector task and prompt.
- Added a native inspect_room tool to invoke that task.
- Shared the existing MCP/Telnet session between the player and delegated task.
- Let the inspector call MUD tools directly instead of receiving copied raw output.
- Added mob appraisal using consider and examine.
- Later removed the model-driven subagent from the inspection path when deterministic processing proved faster.
