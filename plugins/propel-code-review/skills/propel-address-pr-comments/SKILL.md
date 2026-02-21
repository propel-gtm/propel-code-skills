---
name: propel-address-pr-comments
description: Help address Propel Code AI review/issue comments on the open GitHub PR for the current branch using gh CLI, with mode-based execution and optional severity gating.
metadata:
  short-description: Address Propel AI comments in a GitHub PR review
---

# PR Comment Handler

Guide to find the open PR for the current branch and address its comments with gh CLI. Run all `gh` commands with elevated network access.

## 0) Resolve execution mode (do not force a prompt every run)

Mode resolution order:
1. If the user explicitly chooses a mode in the current request, use it.
2. Else if the user has an established preference in this thread, reuse it.
3. Else default to `AGENT_DECIDES` without prompting.
4. Only prompt if user intent is ambiguous or contradictory.

Supported modes:
- `ALL_COMMENTS`: Address all eligible comments.
- `AGENT_DECIDES`: Agent selects which comments to implement using severity + confidence rules.
- `HUMAN_SELECTS`: Human chooses numbered comments to implement.

Eligibility scope:
- By default, include only comments/review threads authored by Propel Code AI.
- Ignore non-Propel comments unless the user explicitly asks to include them.

Severity policy (used only for `AGENT_DECIDES`):
- Supported levels: `error`, `warning`, `info`.
- Threshold options:
  - `ERROR_ONLY` -> include only `error`
  - `ERROR_WARNING` (default) -> include `error` + `warning`
  - `ALL` -> include `error` + `warning` + `info`
- Resolve threshold using the same precedence as mode:
  1. explicit user instruction
  2. existing thread preference
  3. default `ERROR_WARNING`

When no structured severity is present in fetched GitHub comments:
- Infer severity from comment intent and record a short reason:
  - `error`: security, data loss, crashes, major correctness bugs
  - `warning`: correctness risks, reliability/performance concerns, maintainability problems
  - `info`: style, naming, docs, non-blocking suggestions

Prerequisites:
- **gh CLI**: ensure `gh` is authenticated (for example, run `gh auth login` once), then run `gh auth status` with escalated permissions (include workflow/repo scopes) so `gh` commands succeed. If sandboxing blocks `gh auth status`, rerun it with `sandbox_permissions=require_escalated`.
- **PROPEL_API_KEY**: check that the `PROPEL_API_KEY` environment variable is set (for example, run `if [ -n "$PROPEL_API_KEY" ]; then echo "PROPEL_API_KEY is set"; else echo "PROPEL_API_KEY is not set"; fi`). If it is not set, tell the user to open https://app.propelcode.ai/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write, generate a token (scopes are pre-filled), and paste it back. Then export it for the session: `export PROPEL_API_KEY="<token>"`.

## 1) Inspect comments needing attention
- Run scripts/fetch_comments.py which will print out all the comments and review threads on the PR

## 2) Build candidate findings set
- Filter to eligible comments based on scope rules above.
- Present a concise summary of each candidate comment/thread with enough context to implement.
- If there are no eligible comments, report that and stop.

## 3) Execute by mode

### `ALL_COMMENTS`
- Address all eligible comments.

### `AGENT_DECIDES`
- For each eligible comment:
  - Decide whether it is valid and applicable to this codebase.
  - Determine (or infer) severity.
  - Include the comment for implementation if:
    - severity is within the active threshold, and
    - confidence is high that the change is safe and correct.
- Defer comments that are out-of-threshold, low-confidence, duplicate, outdated, or not valid.
- Keep a short reason for each deferred comment.

### `HUMAN_SELECTS`
- Number all eligible comments and provide a short implementation summary for each.
- Ask the user which numbered comments should be addressed.
- Apply fixes only for selected items.

## 4) Apply fixes and report
- Implement approved comments according to mode outcome.
- Summarize:
  - mode used
  - severity threshold (if `AGENT_DECIDES`)
  - count fixed
  - count deferred with short reasons

Notes:
- If gh hits auth/rate issues mid-run, prompt the user to re-authenticate with `gh auth login`, then retry.
