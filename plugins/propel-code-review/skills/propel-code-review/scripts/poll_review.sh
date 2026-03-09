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
  --max-attempts   Number of polling attempts (default: 30)
  --sleep-seconds  Delay between polls in seconds (default: 30)
  --api-url        Override API base URL (default: https://api.propelcode.ai)
  -h, --help       Show this help

Environment:
  PROPEL_API_KEY      Required bearer token for Propel Review API
  PROPEL_API_BASE_URL Optional API base URL override (preferred)
  PROPEL_API_URL      Optional legacy API base URL override
EOF
}

DEFAULT_POLL_TIMEOUT_SECONDS=900
DEFAULT_SLEEP_SECONDS=30
DEFAULT_MAX_ATTEMPTS=$((DEFAULT_POLL_TIMEOUT_SECONDS / DEFAULT_SLEEP_SECONDS))

REVIEW_ID=""
OUTPUT_FILE=""
MAX_ATTEMPTS=$DEFAULT_MAX_ATTEMPTS
SLEEP_SECONDS=$DEFAULT_SLEEP_SECONDS
API_URL="${PROPEL_API_BASE_URL:-${PROPEL_API_URL:-https://api.propelcode.ai}}"

require_option_value() {
  local opt="$1"
  local value="${2-}"
  if [[ -z "$value" || "$value" == --* ]]; then
    echo "Missing value for $opt" >&2
    usage >&2
    exit 2
  fi
  printf '%s\n' "$value"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --review-id)
      REVIEW_ID="$(require_option_value "$1" "${2-}")"
      shift 2
      ;;
    --output-file)
      OUTPUT_FILE="$(require_option_value "$1" "${2-}")"
      shift 2
      ;;
    --max-attempts)
      MAX_ATTEMPTS="$(require_option_value "$1" "${2-}")"
      shift 2
      ;;
    --sleep-seconds)
      SLEEP_SECONDS="$(require_option_value "$1" "${2-}")"
      shift 2
      ;;
    --api-url)
      API_URL="$(require_option_value "$1" "${2-}")"
      shift 2
      ;;
    -h | --help)
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

BODY_FILE="$(mktemp)"
CURL_CONFIG_FILE="$(mktemp)"
chmod 600 "$CURL_CONFIG_FILE"
trap 'rm -f "$BODY_FILE" "$CURL_CONFIG_FILE"' EXIT
printf 'header = "Authorization: Bearer %s"\n' "$PROPEL_API_KEY" >"$CURL_CONFIG_FILE"

for ((i = 1; i <= MAX_ATTEMPTS; i++)); do
  if ! HTTP_CODE="$(
    curl -sS -o "$BODY_FILE" -w "%{http_code}" \
      --config "$CURL_CONFIG_FILE" \
      "$API_URL/v1/reviews/$REVIEW_ID"
  )"; then
    if [[ "$i" -lt "$MAX_ATTEMPTS" ]]; then
      sleep "$SLEEP_SECONDS"
      continue
    fi
    echo "poll failed: transport-level request error after bounded retries" >&2
    if [[ -s "$BODY_FILE" ]]; then
      cat "$BODY_FILE" >&2
    fi
    exit 1
  fi

  if [[ "$HTTP_CODE" =~ ^5 ]] && [[ "$i" -lt "$MAX_ATTEMPTS" ]]; then
    sleep "$SLEEP_SECONDS"
    continue
  fi

  if [[ ! "$HTTP_CODE" =~ ^2 ]]; then
    echo "poll failed ($HTTP_CODE):" >&2
    cat "$BODY_FILE" >&2
    exit 1
  fi

  RESPONSE="$(cat "$BODY_FILE")"
  SANITIZED_RESPONSE="$(printf '%s' "$RESPONSE" | tr -d '\000-\037')"
  # If jq parsing fails, keep polling rather than crashing on transient non-JSON responses.
  REVIEW_STATUS="$(printf '%s' "$SANITIZED_RESPONSE" | jq -r '.status // empty' 2>/dev/null || echo '')"
  NOW="$(date +%H:%M:%S)"
  echo "$NOW poll=$i status=${REVIEW_STATUS:-unknown}" >&2

  if [[ "$REVIEW_STATUS" == "completed" || "$REVIEW_STATUS" == "failed" ]]; then
    if [[ -n "$OUTPUT_FILE" ]]; then
      printf '%s\n' "$SANITIZED_RESPONSE" >"$OUTPUT_FILE"
    fi
    printf '%s\n' "$SANITIZED_RESPONSE"
    if [[ "$REVIEW_STATUS" == "failed" ]]; then
      exit 2
    fi
    exit 0
  fi

  sleep "$SLEEP_SECONDS"
done

echo "timed out after $MAX_ATTEMPTS polls (~$((MAX_ATTEMPTS * SLEEP_SECONDS)) seconds)" >&2
exit 1
