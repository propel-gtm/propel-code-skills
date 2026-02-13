# Propel Code Review Skills - Install Guide

This repo ships the following skills:

- `plugins/propel-code-review/skills/propel-code-review`
- `plugins/propel-code-review/skills/propel-address-pr-comments`

## Prerequisite

Set `PROPEL_API_KEY` in your environment before running the skill. Obtain the key from [Company Settings](https://app.propelcode.ai/administration/settings) in the Propel web app.

```
export PROPEL_API_KEY="your_key_here"
```

To make it persistent in bash, add the export line to your bash profile and reload:

```
echo 'export PROPEL_API_KEY="your_key_here"' >> ~/.bash_profile
source ~/.bash_profile
```

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

Cursor supports Agent Skills defined in `SKILL.md` files.

Project-scoped install (recommended):

```
mkdir -p .cursor/skills
cp -R plugins/propel-code-review/skills/propel-code-review .cursor/skills/
cp -R plugins/propel-code-review/skills/propel-address-pr-comments .cursor/skills/
```

User-scoped install:

```
mkdir -p ~/.cursor/skills
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/propel-code-review ~/.cursor/skills/
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/propel-address-pr-comments ~/.cursor/skills/
```

Notes:
- Cursor projects use `.cursor/skills/<skill-name>/SKILL.md` and Cursor also looks in `~/.cursor/skills` for global skills.

## Best practice (coding agents)

Tell your agent:

```
Use `propel-code-review` to review the diff from base branch to HEAD, then report any findings before final output.
```

For PR-specific triage and fixing:

```
Use `propel-address-pr-comments` to find the open PR for the current branch, fetch Propel findings, ask which comments to address, and apply fixes for selected findings.
```
