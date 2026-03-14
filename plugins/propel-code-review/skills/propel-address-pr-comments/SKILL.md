---
name: propel-address-pr-comments
description: Help address Propel Code AI review/issue comments on the open GitHub PR for the current branch using gh CLI, with mode-based execution and agent triage defaults.
metadata:
  short-description: Address Propel AI comments in a GitHub PR review
---

# PR Comment Handler

Guide to find the open PR for the current branch and address its comments with gh CLI. Run all `gh` commands with elevated network access.

## Scripts Used by This Skill

Paths below are relative to this skill directory:

- `scripts/fetch_comments.py` fetches PR conversation comments, reviews, and
  inline review threads via `gh api graphql`.
- The fetch script also emits an `addressable` subset that already excludes:
  - resolved inline review threads
  - Propel-authored summary-like comments/reviews
- Use the fetch script, not `gh pr view --json`, for inline review discovery.
  `gh pr view` does not expose `reviewThreads`.

## Approval-Friendly Prefixes (One-Time)

If your client supports prefix-based trust/approval, approve these once before
running this skill:

- `scripts/fetch_comments.py`
- `python3 scripts/fetch_comments.py`
- `python scripts/fetch_comments.py`
- `gh auth status`
- `gh pr view`
- `gh api graphql`
- `jq`

## 0) Execution order (fetch first, then ask mode)

Execution order:
1. Fetch comments first, then use the script's `addressable` subset.
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
- Skip all resolved review threads.
- Skip Propel-authored comments/reviews that look like summary comments (for example summary headers, overall PR summaries, LGTM-only approvals).

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
- **gh CLI**: ensure `gh` is authenticated (for example, run `gh auth login` once), then run `gh auth status` with escalated permissions (include workflow/repo scopes) so `gh` commands succeed. If sandboxing blocks `gh auth status`, rerun it with `sandbox_permissions=require_escalated`.
- **PROPEL_API_KEY**: check that the `PROPEL_API_KEY` environment variable is set (for example, run `if [ -n "$PROPEL_API_KEY" ]; then echo "PROPEL_API_KEY is set"; else echo "PROPEL_API_KEY is not set"; fi`). If it is not set, tell the user to open https://app.propelcode.ai/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write, generate a token (scopes are pre-filled), and paste it back. Then export it for the session: `export PROPEL_API_KEY="<token>"`.

## 1) Inspect comments needing attention
- Run `scripts/fetch_comments.py --addressable-only` (or `python3 scripts/fetch_comments.py --addressable-only`).
- Do not use `gh pr view --json` to fetch inline comments; it does not expose `reviewThreads`.
- If running without `--addressable-only`, read from `addressable` in the JSON payload and ignore the raw top-level arrays.

## 2) Build candidate findings set
- Build the candidate set from the `addressable` payload only.
- Do not re-add any item listed in `addressable.excluded`.
- Always present the comment inventory in this standardized format, regardless of PR size:
  - First line: `I found <N> Propel comments.`
  - Then list every eligible comment as a numbered bullet.
  - Bullet format: `[<severity>] <file-or-thread-location> - <very concise summary>`
  - Summary should be just a few words (target 3-8 words).
- If a comment has no structured severity, infer severity first and then use the same format.
- If there are no eligible comments, report that and stop.

## 3) Ask for mode (after showing comments)
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

## 4) Execute by mode

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

## 5) Apply fixes and report
- Implement approved comments according to mode outcome.
- Summarize:
  - mode used
  - internal severity policy used (if `AGENT_DECIDES`)
  - count fixed
  - count deferred with short reasons

Notes:
- If gh hits auth/rate issues mid-run, prompt the user to re-authenticate with `gh auth login`, then retry.
