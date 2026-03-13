# Propel Code Skills

Official docs: [Skills](https://docs.propelcode.ai/features/skills)

This repo ships these skills:

- `propel-code-review`: Run async diff-based code reviews with the Propel Review API.
- `carl`: Run a continuous review/fix loop until Propel comments are cleared.
- `propel-address-pr-comments`: Fetch and address Propel AI comments on the open PR for the current branch.

## Prerequisites

For `propel-code-review` and `carl`, set `PROPEL_API_KEY` in your environment before running the skill. Generate a Review API token from [Review API Tokens](https://app.propelcode.ai/administration/settings?tab=review-api-tokens&scopes=reviews:read,reviews:write).

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

For `propel-address-pr-comments`, authenticate GitHub CLI instead:

```bash
gh auth login
gh auth status
```

## Install

### Codex

Install from GitHub (installs all three skills: `propel-code-review`, `carl`, and `propel-address-pr-comments`):

```bash
$skill-installer propel-gtm/propel-code-skills
```

### OpenClaw / ClawHub

ClawHub publishes one skill directory at a time. In this repo, the publishable unit is each folder under `plugins/propel-code-review/skills/<skill-name>/`.

OpenClaw-compatible skill spec for this repo:

- required: `SKILL.md`
- required frontmatter keys: `name`, `description`
- optional frontmatter: runtime metadata under `metadata.openclaw` or `metadata.clawdbot`
- this repo standard: use a single-line flow-style `metadata: {...}` object for simpler validation and review
- recommended runtime metadata: `requires.env`, `requires.bins`, `primaryEnv`, `homepage`
- optional publish filter: `.clawhubignore`
- supporting files: keep `scripts/` and other text resources inside the same skill folder you publish
- no separate build step: `clawhub publish` packages the skill folder directly
- publishing on ClawHub releases the uploaded skill under `MIT-0`

Install the CLI:

```bash
npm install -g clawhub
```

Log in:

```bash
clawhub login
clawhub whoami
```

Publish a skill:

```bash
clawhub publish plugins/propel-code-review/skills/propel-code-review --slug propel-code-review --name "Propel Code Review" --version 1.0.0 --tags latest --changelog "Initial ClawHub publish"
```

Other publishable skill paths:

- `plugins/propel-code-review/skills/carl`
- `plugins/propel-code-review/skills/propel-address-pr-comments`

Exact first-release commands for all three skills:

```bash
clawhub publish plugins/propel-code-review/skills/propel-code-review --slug propel-code-review --name "Propel Code Review" --version 1.0.0 --tags latest --changelog "Initial ClawHub publish"
clawhub publish plugins/propel-code-review/skills/carl --slug carl --name "CARL" --version 1.0.0 --tags latest --changelog "Initial ClawHub publish"
clawhub publish plugins/propel-code-review/skills/propel-address-pr-comments --slug propel-address-pr-comments --name "Propel Address PR Comments" --version 1.0.0 --tags latest --changelog "Initial ClawHub publish"
```

Sync the repo locally into an OpenClaw workspace without moving folders:

```bash
clawhub sync --root plugins/propel-code-review/skills --all
```

Print or execute the same publish flow from this repo:

```bash
scripts/publish_clawhub_skills.sh --print-only --version 1.0.0 --changelog "Initial ClawHub publish"
scripts/publish_clawhub_skills.sh --version 1.0.0 --changelog "Initial ClawHub publish"
```

### Claude Code

Run these commands in Claude Code to install all three skills (`propel-code-review`, `carl`, and `propel-address-pr-comments`):

```text
/plugin marketplace add propel-gtm/propel-code-skills
/plugin install propel-code-review@propel-code-skills
```

### Cursor

Project-scoped install (recommended):

```bash
mkdir -p .cursor/skills
cp -R plugins/propel-code-review/skills/propel-code-review .cursor/skills/
cp -R plugins/propel-code-review/skills/carl .cursor/skills/
cp -R plugins/propel-code-review/skills/propel-address-pr-comments .cursor/skills/
```

User-scoped install:

```bash
mkdir -p ~/.cursor/skills
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/propel-code-review ~/.cursor/skills/
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/carl ~/.cursor/skills/
cp -R /path/to/propel-code-skills/plugins/propel-code-review/skills/propel-address-pr-comments ~/.cursor/skills/
```

## Usage Prompts

```text
Use `propel-code-review` to review the diff from base branch to HEAD, then report findings before final output.
```

```text
Use `carl` to repeatedly run `propel-code-review` and address valid comments until none remain.
```

```text
Use `carl` and publish a sticky GitHub PR summary comment only when the loop reaches a terminal stop condition (COMPLETE, BLOCKED, or MAX_ITERATIONS_REACHED), with counts of fixed/deferred/remaining comments.
```

```text
Use `propel-address-pr-comments` to find the open PR for the current branch, fetch Propel findings, ask which comments to address, and apply fixes for selected findings.
```

## CARL PR Summary Comment

CARL can publish/update a sticky summary comment on the open PR using Propel Review API, but this should run once at terminal stop condition only.
If no PR exists yet, the script persists a pending terminal CARL run (`POST /v1/reviews/carl-runs`) for later PR bridging.
This keeps the comment author as Propel Bot (instead of local `gh` user identity).

```bash
python plugins/propel-code-review/skills/carl/scripts/post_carl_summary_comment.py \
  --status COMPLETE \
  --base main \
  --iterations 3 \
  --fixed 7 \
  --deferred 1 \
  --remaining 0 \
  --checks passed \
  --review-ids "019c...,019d..." \
  --notes "Local CARL loop finished."
```

Optional:

```bash
export PROPEL_API_BASE_URL="https://api.propelcode.ai"
```

Dry run (no GitHub write):

```bash
python plugins/propel-code-review/skills/carl/scripts/post_carl_summary_comment.py \
  --status COMPLETE \
  --iterations 1 \
  --fixed 1 \
  --deferred 0 \
  --remaining 0 \
  --checks passed \
  --dry-run
```

## Permission Smoke Test

From a target repository (for example, `propel-gtm`), run:

```bash
/path/to/propel-code-skills/plugins/propel-code-review/skills/propel-code-review/scripts/smoke_test_permissions.sh
```

This checks:
- good token + good repo (`202`)
- good token + bad repo (`404`)
- bad token + good repo (`401/403`)
