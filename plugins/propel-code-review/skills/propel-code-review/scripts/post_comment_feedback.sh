#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  post_comment_feedback.sh --review-id <uuid> --comment-id <id> --incorporated <true|false> [options]

Required:
  --review-id       Review ID
  --comment-id      Review comment ID
  --incorporated    true or false

Options:
  --notes           Optional short note describing the decision
  --output-file     Write API response JSON to this file
  --api-url         Override API base URL (default: https://api.propelcode.ai)
  -h, --help        Show this help

Environment:
  PROPEL_API_KEY    Required bearer token for Propel Review API
EOF
}

REVIEW_ID=""
COMMENT_ID=""
INCORPORATED=""
NOTES=""
OUTPUT_FILE=""
API_URL="${PROPEL_API_URL:-https://api.propelcode.ai}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --review-id)
      REVIEW_ID="${2:-}"
      shift 2
      ;;
    --comment-id)
      COMMENT_ID="${2:-}"
      shift 2
      ;;
    --incorporated)
      INCORPORATED="${2:-}"
      shift 2
      ;;
    --notes)
      NOTES="${2:-}"
      shift 2
      ;;
    --output-file)
      OUTPUT_FILE="${2:-}"
      shift 2
      ;;
    --api-url)
      API_URL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${PROPEL_API_KEY:-}" ]]; then
  echo "PROPEL_API_KEY is not set" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 1
fi

if [[ -z "$REVIEW_ID" || -z "$COMMENT_ID" || -z "$INCORPORATED" ]]; then
  echo "Missing required arguments" >&2
  usage >&2
  exit 2
fi

if [[ "$INCORPORATED" != "true" && "$INCORPORATED" != "false" ]]; then
  echo "--incorporated must be true or false" >&2
  exit 2
fi

PAYLOAD="$(jq -n \
  --arg comment_id "$COMMENT_ID" \
  --arg notes "$NOTES" \
  --argjson incorporated "$INCORPORATED" \
  'if $notes == "" then
      {comment_id:$comment_id, incorporated:$incorporated}
   else
      {comment_id:$comment_id, incorporated:$incorporated, notes:$notes}
   end'
)"

BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

HTTP_CODE="$(
  curl -sS -o "$BODY_FILE" -w "%{http_code}" \
    -X POST "$API_URL/v1/reviews/$REVIEW_ID/comments/feedback" \
    -H "Authorization: Bearer $PROPEL_API_KEY" \
    -H "Content-Type: application/json" \
    --data-binary "$PAYLOAD"
)"

RESPONSE="$(cat "$BODY_FILE")"

if [[ ! "$HTTP_CODE" =~ ^2 ]]; then
  echo "Feedback post failed ($HTTP_CODE)" >&2
  echo "$RESPONSE" >&2
  exit 1
fi

if [[ -n "$OUTPUT_FILE" ]]; then
  printf '%s\n' "$RESPONSE" > "$OUTPUT_FILE"
fi

printf '%s\n' "$RESPONSE"
