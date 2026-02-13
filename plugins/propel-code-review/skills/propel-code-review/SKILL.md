---
name: propel-code-review
description: Run async diff-based code reviews using the Propel Review API and retrieve comments and feedback.
---

# Propel Review API Skill

Use this guide to interact with the Propel Review API from an AI agent.
Always target the production API unless told otherwise.

## Purpose

Run async, diff-based code reviews via the production API and retrieve comments.

## Pre-flight: Verify API Key

**Before making any API call**, check whether `PROPEL_API_KEY` is set:

```bash
echo "${PROPEL_API_KEY:-(not set)}"
```

If the variable is empty or unset, **do not attempt any API calls**. Follow these
steps exactly — each step is a separate action:

**Step 1** — Tell the user and open the browser. Send this message and run the
Bash command in the same response (in parallel):

Message to user:
> `PROPEL_API_KEY` is not set. Opening the token creation page — the name and
> scopes are pre-filled. Click **Create token**, copy it, and paste it here.

Bash command:
```bash
open "http://localhost:4000/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write"
```
(On Linux use `xdg-open` instead of `open`.)

**Step 2** — Wait for the user to paste the token. Do not proceed until the user
pastes a value starting with `rev_`. If the value doesn't start with `rev_`, tell
them it doesn't look valid and ask them to try again.

**Step 3** — Once you have a valid token, persist it and load it into the session.
Run this in a **single Bash call** (replace `<TOKEN>` with the actual token):

```bash
SHELL_RC=""; if [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"; elif [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"; fi; if [ -n "$SHELL_RC" ]; then printf '\n# Propel Review API token\nexport PROPEL_API_KEY="%s"\n' "<TOKEN>" >> "$SHELL_RC" && echo "Saved to $SHELL_RC"; else echo "No shell profile found"; fi && export PROPEL_API_KEY="<TOKEN>"
```

Tell the user where the key was saved (e.g. "Saved to ~/.zshrc").

**Step 4** — Continue with the review workflow.

## Setup (Manual)

If you prefer to set the token yourself ahead of time:

```bash
export PROPEL_API_KEY="rev_..."
```

The token must be a Review API token (scoped to `reviews:write` and/or `reviews:read`).

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

1. Compute the base commit (must exist in the remote repo history):
   - `git rev-parse main`
2. Generate the diff:
   - `git diff main...HEAD`
3. Call `POST /v1/reviews` with the diff, repository, and base commit.
4. Poll `GET /v1/reviews/:review_id` until status is `completed` or `failed`.
5. Present comments to the user with file/line context.
6. For each comment, determine whether it is valid and applicable to the code.
7. If valid, incorporate the change in the codebase. If invalid, do not change
   the codebase.
8. Immediately call `POST /v1/reviews/:review_id/comments/feedback` for each
   comment with the `comment_id` and `incorporated` true/false, plus brief
   `notes` explaining the decision. Do not wait for user confirmation.

## Example (Production)

```bash
BASE_COMMIT=$(git rev-parse main)
git diff main...HEAD > /tmp/review_api.diff

curl -s \
  -H "Authorization: Bearer $PROPEL_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @<(jq -n --arg diff "$(cat /tmp/review_api.diff)" \
                    --arg repo "owner/repo" \
                    --arg base "$BASE_COMMIT" \
                    '{diff:$diff, repository:$repo, base_commit:$base}') \
  https://api.propelcode.ai/v1/reviews
```

## Troubleshooting

- `401/403` — re-run the pre-flight check above. The token may be missing,
  expired, or missing scopes. Guide the user to generate a new one at:
  http://localhost:4000/administration/settings?tab=review-api-tokens&token_name=Claude+Code&scopes=reviews:read,reviews:write
- `404 {"error":"Repository not found"}` — the repository string does not match
  a repo connected to the account.
- `413` — the diff exceeded the 1,000,000 byte limit.

## Notes for Agents

- Do not log or expose tokens in output.
- Always use `https://api.propelcode.ai` until told otherwise.
- Only use `POST /v1/reviews`, `GET /v1/reviews/:review_id`, and
  `POST /v1/reviews/:review_id/comments/feedback`.
- The agent must decide whether each comment is valid, incorporate fixes when
  valid, and report feedback automatically via the feedback endpoint using the
  `comment_id` from the review response (no user confirmation required).
