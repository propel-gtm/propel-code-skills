---
name: propel-address-pr-comments
description: Find the open pull request for the current branch with gh CLI, run a Propel Review API diff review, present numbered findings, ask the user which findings to address, and apply fixes for selected comments. Use when the user wants to triage or resolve Propel code review comments on an active PR.
---

# Propel PR Comment Resolution

Use this skill to locate the open PR for the current branch, gather Propel review
findings, and implement selected fixes.

## Requirements

- Run all `gh` commands with elevated network access.
- Ensure `gh` is authenticated before fetching PR metadata.
- Ensure `PROPEL_API_KEY` is set to a valid Propel Review API token.
- Never print tokens in logs or final output.

## Workflow

1. Verify `gh` authentication and scopes.
   - Run `gh auth status` with elevated network access.
   - Ensure repo/workflow access is available.
   - If sandboxing blocks `gh auth status`, rerun with
     `sandbox_permissions=require_escalated`.
2. Fetch Propel findings for the current branch PR.
   - Run `scripts/fetch_comments.py`.
   - The script resolves the open PR for `HEAD`, computes the diff against the PR
     base branch, creates an async Propel review, polls for completion, and prints
     numbered findings.
3. Ask the user what to fix.
   - Summarize each numbered finding in one short line.
   - Ask which finding numbers should be addressed now.
4. If the user selects findings, apply targeted fixes.
   - Edit code to address only selected findings.
   - Run focused verification relevant to changed files.
   - Report what was fixed and what remains.
5. If the user does not select findings, stop after summarizing.

## Failure Handling

- If `gh` fails due to auth or rate limits, ask the user to re-run `gh auth login`,
  then retry.
- If no open PR is found for the current branch, ask the user for the intended base
  branch and rerun `scripts/fetch_comments.py --base-branch <branch>`.
- If Propel review status is `failed`, surface the API error and stop.

