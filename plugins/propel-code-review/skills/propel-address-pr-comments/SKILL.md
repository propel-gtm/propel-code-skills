---
name: propel-address-pr-comments
description: Help address Propel Code AI review/issue comments on the open GitHub PR for the current branch using gh CLI, with mode-based execution and agent triage defaults.
metadata:
  short-description: Address Propel AI comments in a GitHub PR review
---

# PR Comment Handler

Guide to find the open PR for the current branch and address its comments with gh CLI. Run all `gh` commands with elevated network access.

## 0) One-time approval setup (do not repeat every run)

Use one-time approval/trust setup so this skill does not perform separate permission checks every run.

If your client supports prefix-based trust/approval, approve these once:
- `python3 scripts/fetch_comments.py`
- `gh auth status`
- `gh pr view`
- `gh api graphql`

Runtime rules:
- Do not run a standalone permission-check command on every invocation.
- Start directly with comment fetch: `python3 scripts/fetch_comments.py > /tmp/pr_comments_latest.json`.
- Then parse/inspect JSON (`jq` is local-only): `jq -r '[.conversation_comments[]?, .reviews[]?, .review_threads[].comments.nodes[]?] | ...' /tmp/pr_comments_latest.json`.
- If a `gh`/fetch command is blocked by sandboxing, rerun that command with `sandbox_permissions=require_escalated` immediately.
- Run `gh auth status` only for first-time setup or when a `gh` command fails with auth errors.

If the user provides a repo-specific variant (for example `cd /Users/tony/.codex/worktrees/e8af/propel-gtm && python3 /Users/tony/.codex/skills/propel-address-pr-comments/scripts/fetch_comments.py > /tmp/pr5116_comments_latest.json`), follow it exactly.

## 1) Execution order (fetch first, then ask mode)

Execution order:
1. Fetch and filter Propel-authored comments first.
2. Present the standardized comment inventory so the user can see all comments.
3. Then ask the mode question (unless the user already explicitly chose mode).
4. Do not silently default to a mode when user intent is missing.
5. If the user response is ambiguous, ask one focused clarification and wait.
6. Once a mode is chosen, restate it in a one-line execution plan before editing.

Supported modes:
- `ALL_COMMENTS`: Address all eligible Propel-authored comments.
- `AGENT_DECIDES`: Let this coding agent triage and implement comments using internal triage rules.
- `HUMAN_SELECTS`: Human chooses numbered comments to implement.

Eligibility scope:
- Process only comments/review threads authored by Propel Code AI.
- Ignore all non-Propel comments.

Internal triage policy (used only for `AGENT_DECIDES`):
- Do not ask the user to choose severity by default.
- Use severity levels `error`, `warning`, `info` internally.
- Default implementation policy:
  - implement valid, high-confidence `error` and `warning` comments
  - defer `info` by default unless user explicitly asks to include it, or the fix is clearly high-value and low-risk
- Defer low-confidence, duplicate, outdated, or non-applicable comments with a short reason.
- Avoid low-value churn: do not make purely editorial/style-only wording changes unless explicitly requested.
- Advanced override is allowed only when user explicitly asks (for example: "include info" or "error only").

When no structured severity is present in fetched GitHub comments:
- Infer severity from comment intent and record a short reason:
  - `error`: security, data loss, crashes, major correctness bugs
  - `warning`: correctness risks, reliability/performance concerns, maintainability problems
  - `info`: style, naming, docs, non-blocking suggestions

Prerequisites:
- **gh CLI**: authenticate once with `gh auth login`. Do not run `gh auth status` every run; use it only for first-time setup or when `gh` returns auth errors. Keep `gh` commands on elevated permissions, and if sandboxing blocks a command, rerun with `sandbox_permissions=require_escalated`.
- **PROPEL_API_KEY**: check that the `PROPEL_API_KEY` environment variable is set (for example, run `if [ -n "$PROPEL_API_KEY" ]; then echo "PROPEL_API_KEY is set"; else echo "PROPEL_API_KEY is not set"; fi`). If it is not set, tell the user to open https://app.propelcode.ai/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write, generate a token (scopes are pre-filled), and paste it back. Then export it for the session: `export PROPEL_API_KEY="<token>"`.

## 2) Inspect comments needing attention
- Run scripts/fetch_comments.py which will print out all the comments and review threads on the PR

## 3) Build candidate findings set
- Filter to eligible comments based on scope rules above.
- Always present the comment inventory in this standardized format, regardless of PR size:
  - First line: `I found <N> Propel comments.`
  - Then list every eligible comment as a numbered bullet.
  - Bullet format: `[<severity>] <file-or-thread-location> - <very concise summary>`
  - Summary should be just a few words (target 3-8 words).
- If a comment has no structured severity, infer severity first and then use the same format.
- If there are no eligible comments, report that and stop.

## 4) Ask for mode (after showing comments)
- If the user already explicitly chose a mode in the current request, use it and skip this question.
- Otherwise ask using this exact structure:
```text
How should I handle Propel comments for this PR?
1. Fix all actionable Propel comments
2. Let this coding agent triage and implement comments
3. I'll choose comments manually by number
Reply with 1, 2, or 3.
```
- Before making any code edits, state the execution plan in one line:
  - `mode`, and that user can reply `change mode` to override.

## 5) Execute by mode

### `ALL_COMMENTS`
- Address all eligible actionable Propel-authored comments.
- Defer non-actionable items (for example approvals/LGTM-only comments) with short reasons.

### `AGENT_DECIDES`
- For each eligible comment:
  - Decide whether it is valid and applicable to this codebase.
  - Determine (or infer) severity.
  - Include the comment for implementation using the internal triage policy above.
- Defer comments that are low-confidence, duplicate, outdated, non-applicable, or intentionally out of policy.
- Keep a short reason for each deferred comment.

### `HUMAN_SELECTS`
- Number all eligible comments and provide a short implementation summary for each.
- Ask the user which numbered comments should be addressed.
- Select the chosen comments for implementation.

## 6) Apply fixes and report
- Implement approved comments according to mode outcome.
- Summarize:
  - mode used
  - internal severity policy used (if `AGENT_DECIDES`)
  - count fixed
  - count deferred with short reasons

Notes:
- If gh hits auth/rate issues mid-run, prompt the user to re-authenticate with `gh auth login`, then retry.
