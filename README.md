# Propel Code Skills

Official docs: [Skills](https://docs.propelcode.ai/features/skills)

This repo ships these skills:

- `propel-code-review`: Run async diff-based code reviews with the Propel Review API.
- `carl`: Run a continuous review/fix loop until Propel comments are cleared.
- `propel-address-pr-comments`: Fetch and address Propel AI comments on the open PR for the current branch.

## Prerequisite

Set `PROPEL_API_KEY` in your environment before running these skills. Generate a Review API token from [Review API Tokens](https://app.propelcode.ai/administration/settings?tab=review-api-tokens&scopes=reviews:read,reviews:write).

```bash
export PROPEL_API_KEY="rev_..."
```

To make it persistent, add the export to your shell profile:

```bash
# bash
echo 'export PROPEL_API_KEY="rev_..."' >> ~/.bashrc && source ~/.bashrc

# zsh
echo 'export PROPEL_API_KEY="rev_..."' >> ~/.zshrc && source ~/.zshrc
```

## Install

### Codex

Install from GitHub (installs all three skills: `propel-code-review`, `carl`, and `propel-address-pr-comments`):

```bash
$skill-installer propel-gtm/propel-code-skills
```

### Claude Code

Run these commands in Claude Code to install all three skills (`propel-code-review`, `carl`, and `propel-address-pr-comments`):

```text
/plugin marketplace add propel-gtm/propel-code-skills
/plugin install propel-code-review@propel-code-skills
/plugin install carl@propel-code-skills
/plugin install propel-address-pr-comments@propel-code-skills
```

### Cursor

Project-scoped install (recommended):

```bash
mkdir -p .cursor/skills
cp -R plugins/propel-code-review/skills/propel-code-review .cursor/skills/
cp -R plugins/carl/skills/carl .cursor/skills/
cp -R plugins/propel-address-pr-comments/skills/propel-address-pr-comments .cursor/skills/
```

User-scoped install:

```bash
mkdir -p ~/.cursor/skills
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/propel-code-review ~/.cursor/skills/
cp -R /path/to/propel-code-skills/plugins/carl/skills/carl ~/.cursor/skills/
cp -R /path/to/propel-code-skills/plugins/propel-address-pr-comments/skills/propel-address-pr-comments ~/.cursor/skills/
```

## Usage Prompts

```text
Use `propel-code-review` to review the diff from base branch to HEAD, then report findings before final output.
```

```text
Use `carl` to repeatedly run `propel-code-review` and address valid comments until none remain.
```

```text
Use `propel-address-pr-comments` to find the open PR for the current branch, fetch Propel findings, ask which comments to address, and apply fixes for selected findings.
```
