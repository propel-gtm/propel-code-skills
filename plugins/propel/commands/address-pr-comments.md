---
description: Fetch Propel-authored comments on the current PR and address them
argument-hint: "[optional mode or instructions]"
---

Use the bundled `propel-address-pr-comments` skill from this plugin.

Raw slash-command arguments:
`$ARGUMENTS`

Execution rules:
- Follow the skill's execution order exactly: fetch first, show the standardized comment inventory, then choose or confirm mode before editing.
- If the raw arguments clearly specify a handling mode, use that mode without asking again.
- Only process Propel-authored comments or review threads.
- Before making edits, restate the execution plan in one line exactly as the skill requires.
- Summarize the final outcome with the mode used plus fixed and deferred counts.
