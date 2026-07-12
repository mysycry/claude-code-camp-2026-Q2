---
description: Execute MUD commands on tbaMUD (localhost:4000) as player dummy
agent: build
---

Run the MUD client with the given commands. The script connects to tbaMUD at localhost:4000, logs in as dummy/helloworld, and executes the commands.

Use the `;` separator for multiple commands. Returns room descriptions, exits, and results.

```bash
python3 week0_explore/explore_architecture/02_agent_skills/.claude/skills/play-mud/scripts/mud.py "/mud"
```
