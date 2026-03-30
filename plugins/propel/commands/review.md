---
description: Run a Propel async code review against local git state
argument-hint: "[--base <ref>]"
---

Use the bundled `propel-code-review` skill from this plugin.

Raw slash-command arguments:
`$ARGUMENTS`

Execution rules:
- This command is review-only. Do not fix code in this turn.
- Review the current working tree by default.
- If the user passed `--base <ref>`, review the branch diff from that base to `HEAD`.
- If `PROPEL_API_KEY` is missing or invalid, follow the token setup flow from the skill before proceeding.
- If there is nothing to review, say so briefly and stop.
- Return the Propel review findings clearly, with file paths and line references when available.
