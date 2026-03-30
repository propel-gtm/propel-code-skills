---
description: Run CARL to review, fix valid Propel comments, and re-review until they are cleared
argument-hint: "[--base <ref>] [--max-iterations <n>]"
---

Use the bundled `carl` skill from this plugin.

Raw slash-command arguments:
`$ARGUMENTS`

Execution rules:
- Parse `--base <ref>` and `--max-iterations <n>` if present; otherwise use the skill defaults.
- CARL is allowed to edit files and run relevant checks.
- Follow the loop, stop conditions, and reporting contract from the skill strictly.
- If `PROPEL_API_KEY` is missing or invalid, follow the token setup flow from the dependent review skill before proceeding.
- Finish by reporting the terminal state plus fixed, deferred, remaining, and checks status counts.
