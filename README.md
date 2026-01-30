# Propel Code Review Skill - Install Guide

This repo ships the Propel code review skill at:

`plugins/propel-code-review/skills/agent-code-review`

## Claude (Claude Code)

Run these commands in Claude:

```
/plugin marketplace add propel-gtm/propel-code-skills
/plugin install propel-code-review@propel-code-skills
```

## Codex

```
$skill-installer propel-gtm/propel-code-skills
```

## Cursor

Cursor supports Agent Skills defined in `SKILL.md` files.citeturn19view0

Project-scoped install (recommended):

```
mkdir -p .cursor/skills
cp -R plugins/propel-code-review/skills/agent-code-review .cursor/skills/
```

User-scoped install:

```
mkdir -p ~/.cursor/skills
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/agent-code-review ~/.cursor/skills/
```

Notes:
- Cursor projects use `.cursor/skills/<skill-name>/SKILL.md` and Cursor also looks in `~/.cursor/skills` for global skills.citeturn16view1turn16view0
