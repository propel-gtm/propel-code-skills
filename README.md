# Propel Code Review Skills - Install Guide

This repo ships the following skills:

- `plugins/propel-code-review/skills/propel-code-review`
- `plugins/propel-code-review/skills/propel-address-pr-comments`

## Prerequisite

Set `PROPEL_API_KEY` in your environment before running the skill. Generate a
Review API token from the
[Review API Tokens](https://app.propelcode.ai/administration/settings?tab=review-api-tokens&scopes=reviews:read,reviews:write)
page in the Propel web app.

```
export PROPEL_API_KEY="rev_..."
```

To make it persistent, add the export to your shell profile:

```bash
# bash
echo 'export PROPEL_API_KEY="rev_..."' >> ~/.bashrc && source ~/.bashrc

# zsh
echo 'export PROPEL_API_KEY="rev_..."' >> ~/.zshrc && source ~/.zshrc
```

> **Note:** If you skip this step, the skill will prompt you to generate a token
> interactively when it runs.

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
