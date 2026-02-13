---
name: propel-address-pr-comments
description: Help address Propel Code AI review/issue comments on the open GitHub PR for the current branch using gh CLI; verify gh auth first and prompt the user to authenticate if not logged in.
metadata:
  short-description: Address Propel AI comments in a GitHub PR review
---

# PR Comment Handler

Guide to find the open PR for the current branch and address its comments with gh CLI. Run all `gh` commands with elevated network access.

Prerequisites:
- **gh CLI**: ensure `gh` is authenticated (for example, run `gh auth login` once), then run `gh auth status` with escalated permissions (include workflow/repo scopes) so `gh` commands succeed. If sandboxing blocks `gh auth status`, rerun it with `sandbox_permissions=require_escalated`.
- **PROPEL_API_KEY**: check that the `PROPEL_API_KEY` environment variable is set (`echo "${PROPEL_API_KEY:-(not set)}"`). If it is not set, tell the user to open https://app.propelcode.ai/administration/settings?tab=review-api-tokens, generate a token with **reviews:write** scope, and paste it back. Then export it for the session: `export PROPEL_API_KEY="<token>"`.

## 1) Inspect comments needing attention
- Run scripts/fetch_comments.py which will print out all the comments and review threads on the PR

## 2) Ask the user for clarification
- Number only comments/review threads authored by Propel Code AI and provide a short summary of what would be required to apply a fix for each
- Ignore non-Propel comments unless the user explicitly asks to include them
- Ask the user which numbered comments should be addressed

## 3) If user chooses comments
- Apply fixes for the selected Propel Code AI comments

Notes:
- If gh hits auth/rate issues mid-run, prompt the user to re-authenticate with `gh auth login`, then retry.
