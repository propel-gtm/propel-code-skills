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

## PROPEL_API_KEY

Set `PROPEL_API_KEY` in your environment before running the skill. Obtain the key from [Company Settings](https://app.propelcode.ai/administration/settings) in the Propel web app.

```
export PROPEL_API_KEY="your_key_here"
```

To make it persistent in bash, add the export line to your bash profile and reload:

```
echo 'export PROPEL_API_KEY="your_key_here"' >> ~/.bash_profile
source ~/.bash_profile
```

## Cursor

Cursor supports Agent Skills defined in `SKILL.md` files.

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
- Cursor projects use `.cursor/skills/<skill-name>/SKILL.md` and Cursor also looks in `~/.cursor/skills` for global skills.
