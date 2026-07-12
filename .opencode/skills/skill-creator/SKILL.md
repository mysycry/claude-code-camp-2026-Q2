---
name: skill-creator
description: Scaffold new opencode skills. Guides users through creating SKILL.md files with proper frontmatter, naming conventions, and directory structure.
license: MIT
compatibility: opencode
metadata:
  audience: all
  workflow: scaffolding
---

## What I do

I help you create new opencode skills by:

1. Asking about the skill's purpose and behavior
2. Generating a valid skill name (lowercase alphanumeric with hyphens)
3. Writing a clear, specific description (1-1024 chars)
4. Creating the directory structure at `.opencode/skills/<name>/SKILL.md`
5. Setting up proper YAML frontmatter with name, description, and optional fields

## When to use me

Use this whenever you want to create a reusable skill for opencode agents. I handle the boilerplate so the resulting skill is valid and discoverable.

## Skill format reference

- Directory: `.opencode/skills/<name>/SKILL.md`
- Name regex: `^[a-z0-9]+(-[a-z0-9]+)*$` (1-64 chars, no leading/trailing hyphens)
- Description: 1-1024 characters
- The `name` field must match the directory name
- Skills are loaded on-demand via the `skill` tool

## Frontmatter fields

| Field          | Required | Description                              |
|----------------|----------|------------------------------------------|
| `name`         | yes      | Unique skill name matching dir name      |
| `description`  | yes      | Brief description (1-1024 chars)         |
| `license`      | no       | License identifier                       |
| `compatibility`| no       | Target platform (e.g. `opencode`)        |
| `metadata`     | no       | String-to-string map for extra context   |

## Placement order (checked in this order)

1. `.opencode/skills/<name>/SKILL.md` (project)
2. `~/.config/opencode/skills/<name>/SKILL.md` (global)
3. `.claude/skills/<name>/SKILL.md` (compat)
4. `.agents/skills/<name>/SKILL.md` (compat)
