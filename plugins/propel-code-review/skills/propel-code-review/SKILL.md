---
name: propel-code-review
description: Run async diff-based code reviews using the Propel Review API and retrieve comments and feedback.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# Propel Review API Skill

Use this guide to interact with the Propel Review API from an AI agent.
Always target the production API unless told otherwise.

## Purpose

Run async, diff-based code reviews via the production API and retrieve comments.

## Pre-flight: Verify API Key

**Before making any API call**, check whether `PROPEL_API_KEY` is available.
First try the environment variable, then fall back to the env file:

```bash
if [ -z "$PROPEL_API_KEY" ] && [ -f "$HOME/.propel/env" ]; then
  source "$HOME/.propel/env";
fi;
if [ -n "$PROPEL_API_KEY" ]; then
  echo "PROPEL_API_KEY is set";
else
  echo "PROPEL_API_KEY is not set";
fi
```

If the variable is empty, unset, or you just received a `401/403` from the Review
API, **do not attempt any API calls** with the current value. Follow these steps
to capture a fresh token — each step is a separate action:

**Step 1** — Tell the user and open the browser. Send this message and run the
Bash command in the same response (in parallel):

Message to user:
> `PROPEL_API_KEY` is not set. Opening the token creation page:
> https://app.propelcode.ai/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write
> The name and scopes are pre-filled. Click **Create token**, copy it, and paste it here.

Bash command:
```bash
URL="https://app.propelcode.ai/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write"
if command -v xdg-open >/dev/null; then xdg-open "$URL"; else open "$URL"; fi
```

**Step 2** — Wait for the user to paste the token. Do not proceed until the user
pastes a value starting with `rev_`. If the value doesn't start with `rev_`, tell
them it doesn't look valid and ask them to try again.

**Step 3** — Once you have a valid token, persist it to `~/.propel/env` and the
shell profile. Run this in a **single Bash call** (replace `<TOKEN>` with the
actual token):

```bash
mkdir -p "$HOME/.propel" \
  && printf 'export PROPEL_API_KEY="%s"\n' "<TOKEN>" > "$HOME/.propel/env" \
  && chmod 600 "$HOME/.propel/env" \
  && echo "Saved to ~/.propel/env" \
  && SHELL_RC=""; \
     case "$SHELL" in */zsh) SHELL_RC="$HOME/.zshrc" ;; */bash) SHELL_RC="$HOME/.bashrc" ;; esac; \
     if [ -z "$SHELL_RC" ] && [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"; fi; \
     if [ -z "$SHELL_RC" ] && [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"; fi; \
     if [ -n "$SHELL_RC" ] && ! grep -q 'propel/env' "$SHELL_RC"; then \
       printf '\n# Propel Review API token\n[ -f "$HOME/.propel/env" ] && source "$HOME/.propel/env"\n' >> "$SHELL_RC" \
       && echo "Added source line to $SHELL_RC"; \
     fi
```

Tell the user where the key was saved (e.g. "Saved to ~/.propel/env").

**Step 4** — Continue with the review workflow.

## Setup (Manual)

If you prefer to set the token yourself ahead of time:

```bash
mkdir -p ~/.propel
echo 'export PROPEL_API_KEY="rev_..."' > ~/.propel/env
chmod 600 ~/.propel/env
```

The token must be a Review API token (scoped to both `reviews:write` and `reviews:read`).

## Base URL

```
https://api.propelcode.ai
```

## Authentication

Use a bearer token in the `Authorization` header:

```
Authorization: Bearer $PROPEL_API_KEY
```

## Endpoints (Only These)

Do not assume any other Review APIs exist. Only use the async endpoints below.

### Create Review (Async)

`POST /v1/reviews`

Request body:

```json
{
  "diff": "string (required)",
  "repository": "string (required)",
  "base_commit": "string (required)"
}
```

Constraints:
- `diff` max size: 1,000,000 bytes
- `repository` max length: 255
- `base_commit` max length: 255

Notes:
- `base_commit` should be a commit that exists in the remote repo history
  (typically the base commit of the branch you are reviewing).
- `repository` should be the canonical repo slug (for example, `owner/repo`)
  derived from the git remote URL.

Response (202):

```json
{
  "review_id": "uuid",
  "status": "queued",
  "repository": "owner/repo",
  "base_commit": "sha",
  "created_at": "...",
  "updated_at": "..."
}
```

### Get Review Status/Results

`GET /v1/reviews/:review_id`

Response (200):

```json
{
  "review_id": "uuid",
  "status": "queued|running|completed|failed",
  "comments": [
    {
      "comment_id": "string",
      "file_path": "path",
      "line": 123,
      "message": "...",
      "severity": "error|warning|info"
    }
  ],
  "error": {
    "code": "generation_failed",
    "message": "..."
  }
}
```

### Post Comment Feedback

`POST /v1/reviews/:review_id/comments/feedback`

Request body:

```json
{
  "comment_id": "string (required)",
  "incorporated": true,
  "notes": "string (optional)"
}
```

Response (200):

```json
{
  "review_id": "uuid",
  "comment_id": "string",
  "incorporated": true
}
```

## Workflow (Recommended)

1. Resolve the base branch (PR base when available; otherwise remote default branch):
   - `BASE_BRANCH=$(gh pr view --json baseRefName -q '.baseRefName' 2>/dev/null || git remote show origin | sed -n '/HEAD branch/s/.*: //p')`
2. Compute the base commit (must exist in the remote repo history):
   - `git rev-parse "$BASE_BRANCH"`
3. Compute the repository slug:
   - `git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s/\\.git$//'`
4. Generate the diff:
   - `git diff "$BASE_BRANCH"`
5. Call `POST /v1/reviews` with the diff, base commit, and repository using the canonical repo slug.
6. Poll `GET /v1/reviews/:review_id` every 30 seconds until status is `completed` or `failed`.
7. Present comments to the user with file/line context.
8. For each comment, determine whether it is valid and applicable to the code.
9. If valid, incorporate the change in the codebase. If invalid, do not change
   the codebase.
10. Immediately call `POST /v1/reviews/:review_id/comments/feedback` for each
   comment with the `comment_id` and `incorporated` true/false, plus brief
   `notes` explaining the decision. Do not wait for user confirmation.

## Example (Production)

```bash
BASE_BRANCH=$(gh pr view --json baseRefName -q '.baseRefName' 2>/dev/null || git remote show origin | sed -n '/HEAD branch/s/.*: //p')
BASE_COMMIT=$(git rev-parse "$BASE_BRANCH")
REPO_SLUG=$(git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s/\\.git$//')
git diff "$BASE_BRANCH" > /tmp/review_api.diff

CREATE_RESPONSE=$(curl -s \
  -H "Authorization: Bearer $PROPEL_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @<(jq -n --arg diff "$(cat /tmp/review_api.diff)" \
                    --arg repo "$REPO_SLUG" \
                    --arg base "$BASE_COMMIT" \
                    '{diff:$diff, repository:$repo, base_commit:$base}') \
  https://api.propelcode.ai/v1/reviews)

REVIEW_ID=$(echo "$CREATE_RESPONSE" | jq -r '.review_id')
if [ -z "$REVIEW_ID" ] || [ "$REVIEW_ID" = "null" ]; then
  echo "$CREATE_RESPONSE"
  exit 1
fi

while true; do
  REVIEW_RESPONSE=$(curl -s \
    -H "Authorization: Bearer $PROPEL_API_KEY" \
    "https://api.propelcode.ai/v1/reviews/$REVIEW_ID")

  STATUS=$(echo "$REVIEW_RESPONSE" | jq -r '.status')
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    echo "$REVIEW_RESPONSE"
    break
  fi

  sleep 30
done
```

Extract `review_id` from the response. If it is missing or `null`, show the
error and stop.

### Step 2 — Poll until complete (single Bash call)

Poll the review status every 30 seconds in a loop. Run this as **one** Bash
call (replace `<REVIEW_ID>` with the actual ID):

```bash
# Poll review status every 30s until completed or failed
source "$HOME/.propel/env" \
  && REVIEW_ID="<REVIEW_ID>" \
  && while true; do
       REVIEW_RESPONSE=$(curl -s \
         -H "Authorization: Bearer $PROPEL_API_KEY" \
         "https://api.propelcode.ai/v1/reviews/$REVIEW_ID") \
       && STATUS=$(echo "$REVIEW_RESPONSE" | jq -r '.status') \
       && echo "$(date +%H:%M:%S) Status: $STATUS";
       if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
         echo "$REVIEW_RESPONSE" | jq .;
         break;
       fi;
       sleep 30;
     done
```

### Step 3 — Process comments and send feedback

Read the review response from Step 2. For each comment:

1. Determine whether the comment is valid and applicable to the code.
2. If valid, incorporate the change in the codebase using Edit/Write tools.
3. If invalid, do not change the codebase.

After processing all comments, send feedback for **every** comment in a
**single** Bash call. Build the feedback calls as a chain (replace values):

```bash
# Send feedback for all comments in one call (chain with &&)
source "$HOME/.propel/env" \
  && curl -s -X POST \
       -H "Authorization: Bearer $PROPEL_API_KEY" \
       -H "Content-Type: application/json" \
       -d '{"comment_id":"<ID1>","incorporated":true,"notes":"<NOTES1>"}' \
       "https://api.propelcode.ai/v1/reviews/<REVIEW_ID>/comments/feedback" \
  && curl -s -X POST \
       -H "Authorization: Bearer $PROPEL_API_KEY" \
       -H "Content-Type: application/json" \
       -d '{"comment_id":"<ID2>","incorporated":false,"notes":"<NOTES2>"}' \
       "https://api.propelcode.ai/v1/reviews/<REVIEW_ID>/comments/feedback"
```

Chain all feedback calls with `&&` so they run in one Bash invocation.

### Step 4 — Present results

Present each comment to the user with:
- File path and line number
- The comment message and severity
- Whether it was incorporated and why

## Troubleshooting

- `401/403` — re-run the pre-flight check above. The token may be missing,
  expired, or missing scopes. Guide the user to generate a new one at:
  https://app.propelcode.ai/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write
- `404 {"error":"Repository not found"}` — the repository string does not match
  a repo connected to the account.
- `413` — the diff exceeded the 1,000,000 byte limit.

## Notes for Agents

- Do not log or expose tokens in output.
- Always use `https://api.propelcode.ai` until told otherwise.
- Only use `POST /v1/reviews`, `GET /v1/reviews/:review_id`, and
  `POST /v1/reviews/:review_id/comments/feedback`.
- Poll review status every 30 seconds to avoid tight loops.
- The agent must decide whether each comment is valid, incorporate fixes when
  valid, and report feedback automatically via the feedback endpoint using the
  `comment_id` from the review response (no user confirmation required).
