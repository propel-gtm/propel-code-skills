#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  poll_review.sh --review-id <uuid> [options]

Required:
  --review-id      Review ID returned by POST /v1/reviews

Options:
  --output-file    Write final review JSON to this file
  --max-attempts   Number of polling attempts (default: 40)
  --sleep-seconds  Delay between polls in seconds (default: 3)
  --api-url        Override API base URL (default: https://api.propelcode.ai)
  -h, --help       Show this help

Environment:
  PROPEL_API_KEY   Required bearer token for Propel Review API
EOF
}

REVIEW_ID=""
OUTPUT_FILE=""
MAX_ATTEMPTS=40
SLEEP_SECONDS=3
API_URL="${PROPEL_API_URL:-https://api.propelcode.ai}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --review-id)
      REVIEW_ID="${2:-}"
      shift 2
      ;;
    --output-file)
      OUTPUT_FILE="${2:-}"
      shift 2
      ;;
    --max-attempts)
      MAX_ATTEMPTS="${2:-}"
      shift 2
      ;;
    --sleep-seconds)
      SLEEP_SECONDS="${2:-}"
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

if [[ -z "$REVIEW_ID" ]]; then
  echo "Missing required argument: --review-id" >&2
  usage >&2
  exit 2
fi

if ! [[ "$MAX_ATTEMPTS" =~ ^[0-9]+$ ]] || [[ "$MAX_ATTEMPTS" -lt 1 ]]; then
  echo "--max-attempts must be a positive integer" >&2
  exit 2
fi

if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]] || [[ "$SLEEP_SECONDS" -lt 1 ]]; then
  echo "--sleep-seconds must be a positive integer" >&2
  exit 2
fi

for ((i = 1; i <= MAX_ATTEMPTS; i++)); do
  RESPONSE="$(
    curl -sS \
      -H "Authorization: Bearer $PROPEL_API_KEY" \
      "$API_URL/v1/reviews/$REVIEW_ID"
  )"

  REVIEW_STATUS="$(echo "$RESPONSE" | jq -r '.status // empty')"
  NOW="$(date +%H:%M:%S)"
  echo "$NOW poll=$i status=${REVIEW_STATUS:-unknown}" >&2

  if [[ "$REVIEW_STATUS" == "completed" || "$REVIEW_STATUS" == "failed" ]]; then
    if [[ -n "$OUTPUT_FILE" ]]; then
      printf '%s\n' "$RESPONSE" > "$OUTPUT_FILE"
    fi
    printf '%s\n' "$RESPONSE"
    exit 0
  fi

  sleep "$SLEEP_SECONDS"
done

echo "timed out after $MAX_ATTEMPTS polls" >&2
exit 1
