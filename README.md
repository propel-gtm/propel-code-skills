# Propel Code Skills

Official docs: [Skills](https://docs.propelcode.ai/features/skills)

This repository packages two skills:

- `propel-code-review`: Run async diff-based code reviews with the Propel Review API.
- `propel-address-pr-comments`: Fetch and address Propel AI comments on the open PR for the current branch.

## Prerequisite

Set `PROPEL_API_KEY` before running these skills. Get the key from [Company Settings](https://app.propelcode.ai/administration/settings).

```bash
export PROPEL_API_KEY="rev_..."
```

## Install

### Codex

```bash
$skill-installer propel-gtm/propel-code-skills
```

### Claude Code

```text
/plugin marketplace add propel-gtm/propel-code-skills
/plugin install propel-code-review@propel-code-skills
```

### Cursor

Project-scoped install (recommended):

```bash
mkdir -p .cursor/skills
cp -R plugins/propel-code-review/skills/propel-code-review .cursor/skills/
cp -R plugins/propel-code-review/skills/propel-address-pr-comments .cursor/skills/
```

User-scoped install:

```bash
mkdir -p ~/.cursor/skills
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/propel-code-review ~/.cursor/skills/
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/propel-address-pr-comments ~/.cursor/skills/
```

## Usage Prompts

```text
Use `propel-code-review` to review the diff from base branch to HEAD, then report findings before final output.
```

```text
Use `propel-address-pr-comments` to find the open PR for the current branch, fetch Propel findings, ask which comments to address, and apply fixes for selected findings.
```
