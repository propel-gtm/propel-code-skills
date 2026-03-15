---
name: carl
description: Continuously run Propel code review, fix valid findings, rerun review, and publish a final PR summary when the loop reaches a terminal state. Use when the goal is to clear Propel findings on the current branch.
metadata: {"clawdbot":{"requires":{"env":["PROPEL_API_KEY"],"bins":["curl","git","gh","jq","python3"]},"primaryEnv":"PROPEL_API_KEY","homepage":"https://www.propelcode.ai/"}}
---

# CARL (Coding Agent Review Loop)

Use this skill when the goal is to clear Propel review comments on the current branch diff.

CARL repeatedly invokes `propel-code-review`, applies fixes, and reruns review until comments are zero or a loop guard stops execution.
Run the loop in strict sequence: never start a new CARL iteration while the current iteration is still in progress.

## Required Dependency

- Load and use `propel-code-review` for each review pass.
- Use `scripts/post_carl_summary_comment.py` to publish final loop summary to the open PR.

If `propel-code-review` is unavailable, stop and report that dependency is missing.

## Inputs

- Base branch (default: `main` unless user specifies otherwise)
- Max iterations (default: `6`)

## Loop Workflow

1. Determine the base branch and compute the diff: `git diff <base>...HEAD`.
2. Run `propel-code-review` on that diff and wait for completion (`completed` or `failed`) before doing anything else.
3. If `propel-code-review` returns permission/access errors (`401`, `403`, `404`, "Repository not found"), stop immediately with `BLOCKED` and report the exact repo slug plus required user action.
4. If review status is `failed`, retry once. If it fails again, stop and report the API error.
5. If there are zero comments, stop and report completion.
6. For each comment:
   - Decide if it is valid for this codebase.
   - If valid, implement the fix.
   - If not valid, keep code unchanged and record a brief reason.
7. Run relevant checks after edits (at minimum, checks related to touched code).
8. Only after step 7 is fully complete, repeat from step 1 until comments are zero or max iterations is reached.

## Scripts Used by This Skill

Use `propel-code-review` scripts for all review API calls. Paths below are
relative to this skill directory:

- `../propel-code-review/scripts/create_review.sh` creates a review.
- `../propel-code-review/scripts/poll_review.sh` polls until terminal status.
- `../propel-code-review/scripts/post_comment_feedback.sh` posts incorporated
  true/false feedback for each review comment.

## Approval-Friendly Prefixes (One-Time)

If your client supports prefix-based trust/approval, approve these once before
running CARL:

- `../propel-code-review/scripts/create_review.sh`
- `../propel-code-review/scripts/poll_review.sh`
- `../propel-code-review/scripts/post_comment_feedback.sh`
- `scripts/post_carl_summary_comment.py`
- `python scripts/post_carl_summary_comment.py`
- `git diff`
- `git rev-parse`
- `git remote get-url`
- `go test`
- `jq`

## Scripted Review Calls

For each CARL iteration, use the `propel-code-review` helper scripts instead of
inline curl loops. Paths below are relative to this skill directory:

```bash
ITERATION=1
BASE_COMMIT=$(git rev-parse "$BASE_BRANCH")
HEAD_COMMIT=$(git rev-parse HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
REPO_SLUG=$(git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s/\\.git$//')
DIFF_FILE="/tmp/carl_iteration${ITERATION}.diff"
REVIEW_FILE="/tmp/carl_review_iter${ITERATION}.json"

git diff "$BASE_BRANCH...HEAD" > "$DIFF_FILE"

CREATE_RESPONSE=$(
  ../propel-code-review/scripts/create_review.sh \
    --diff-file "$DIFF_FILE" \
    --repo "$REPO_SLUG" \
    --base-commit "$BASE_COMMIT" \
    --head-commit-sha "$HEAD_COMMIT" \
    --branch "$BRANCH"
)
REVIEW_ID=$(echo "$CREATE_RESPONSE" | jq -r '.review_id // empty')

../propel-code-review/scripts/poll_review.sh \
  --review-id "$REVIEW_ID" \
  --max-attempts 30 \
  --sleep-seconds 30 \
  --output-file "$REVIEW_FILE"

cat "$REVIEW_FILE"

jq -c '.comments[]?' "$REVIEW_FILE" | while read -r comment; do
  COMMENT_ID=$(echo "$comment" | jq -r '.comment_id // empty')
  if [ -z "$COMMENT_ID" ]; then
    continue
  fi
  ../propel-code-review/scripts/post_comment_feedback.sh \
    --review-id "$REVIEW_ID" \
    --comment-id "$COMMENT_ID" \
    --incorporated true \
    --notes "Applied in CARL iteration ${ITERATION}."
done
```

## Loop Guards

- Stop at `max iterations` even if comments remain.
- Never run overlapping CARL iterations or overlapping `propel-code-review` requests within the same CARL run.
- Track a stable signature of remaining comments (`file_path + line + severity + message`).
- If the same signature repeats twice in a row, stop and report as blocked instead of looping forever.
- If there is no branch diff against base (`git diff <base>...HEAD` is empty), stop and report there is nothing to review.
- Do not retry `401/403/404` permission/access failures. Exit as `BLOCKED` immediately.

## Output Contract

For each iteration, report:

- Comment count at start
- Number fixed
- Number deferred (with short reasons)
- Whether checks passed

Final states:

- `COMPLETE`: zero comments remain.
- `BLOCKED`: repeated comment signature, permission/access failure (`401/403/404`), or unresolved hard blocker.
- `MAX_ITERATIONS_REACHED`: loop limit hit with remaining comments.

## GitHub PR Bridge

When CARL reaches a terminal stop condition (`COMPLETE`, `BLOCKED`, or `MAX_ITERATIONS_REACHED`), publish a PR summary comment
using:

```bash
scripts/post_carl_summary_comment.py \
  --status <COMPLETE|BLOCKED|MAX_ITERATIONS_REACHED> \
  --base <base-branch> \
  --iterations <n> \
  --fixed <n> \
  --deferred <n> \
  --remaining <n> \
  --checks <passed|failed|not_run> \
  --review-ids "<id1,id2,...>" \
  --notes "<optional short note>"
```

Rules:
- The script upserts a sticky comment via Propel Review API (`/v1/reviews/pr-comments/upsert`) so the author is Propel Bot.
- `PROPEL_API_KEY` must be set with `reviews:write` scope.
- If there is no open PR for the current branch, persist a pending terminal CARL run via `POST /v1/reviews/carl-runs` and continue.
- If `gh` is not authenticated, report the error and continue.
- If the Review API upsert call fails, report the error and continue.
- Never hide CARL output if PR comment publishing fails.

## Suggested Invocation

Use the `carl` skill to run Propel review/fix/re-review on this branch against `main` until there are no comments left.
