---
description: Check whether Propel review workflows are ready in Claude Code
---

Prepare this workspace to use the bundled Propel Code plugin workflows.

Checks to run:
- whether `PROPEL_API_KEY` is set
- whether `gh` is installed
- whether `gh auth status` succeeds
- whether the current directory is inside a git repository with an `origin` remote

Behavior:
- Run the checks directly before answering.
- If everything is ready, say that `/propel:review`, `/propel:carl`, and `/propel:address-pr-comments` are ready to use.
- If `PROPEL_API_KEY` is missing, give the exact token creation URL from the `propel-code-review` skill and explain that the token must include `reviews:read` and `reviews:write`.
- If `gh` is missing or unauthenticated, tell the user to run `gh auth login`.
- Do not modify shell profiles automatically unless the user explicitly asks you to persist a pasted token.
