---
name: carl
description: Continuously run Propel code review, fix valid comments, and re-review until there are no remaining comments.
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
3. If review status is `failed`, retry once. If it fails again, stop and report the API error.
4. If there are zero comments, stop and report completion.
5. For each comment:
   - Decide if it is valid for this codebase.
   - If valid, implement the fix.
   - If not valid, keep code unchanged and record a brief reason.
6. Run relevant checks after edits (at minimum, checks related to touched code).
7. Only after step 6 is fully complete, repeat from step 1 until comments are zero or max iterations is reached.

## Loop Guards

- Stop at `max iterations` even if comments remain.
- Never run overlapping CARL iterations or overlapping `propel-code-review` requests within the same CARL run.
- Track a stable signature of remaining comments (`file_path + line + severity + message`).
- If the same signature repeats twice in a row, stop and report as blocked instead of looping forever.
- If there is no branch diff against base (`git diff <base>...HEAD` is empty), stop and report there is nothing to review.

## Output Contract

For each iteration, report:

- Comment count at start
- Number fixed
- Number deferred (with short reasons)
- Whether checks passed

Final states:

- `COMPLETE`: zero comments remain.
- `BLOCKED`: repeated comment signature or unresolved hard blocker.
- `MAX_ITERATIONS_REACHED`: loop limit hit with remaining comments.

## GitHub PR Bridge

When CARL reaches a terminal stop condition (`COMPLETE`, `BLOCKED`, or `MAX_ITERATIONS_REACHED`), publish a PR summary comment
using:

```bash
python scripts/post_carl_summary_comment.py \
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
- If there is no open PR for the current branch, report this to the user and continue.
- If `gh` is not authenticated, report the error and continue.
- If the Review API upsert call fails, report the error and continue.
- Never hide CARL output if PR comment publishing fails.

## Suggested Invocation

Use the `carl` skill to run Propel review/fix/re-review on this branch against `main` until there are no comments left.
