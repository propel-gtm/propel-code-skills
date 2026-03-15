#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  publish_clawhub_skills.sh --version <semver> --changelog <text> [options]

Options:
  --version <semver>      Required. Version to publish for every selected skill.
  --changelog <text>      Required. Release notes used for every selected skill.
  --skill <name>          Publish only one skill. Repeatable.
  --tags <csv>            Tags to attach (default: latest)
  --print-only            Print commands without executing them.
  -h, --help              Show this help.

Examples:
  scripts/publish_clawhub_skills.sh \
    --version 1.0.0 \
    --changelog "Initial ClawHub publish" \
    --print-only

  scripts/publish_clawhub_skills.sh \
    --skill carl \
    --version 1.0.1 \
    --changelog "Fix metadata and docs"
EOF
}

require_value() {
  local opt="$1"
  local value="${2-}"
  if [[ -z "$value" || "$value" == --* ]]; then
    echo "Missing value for $opt" >&2
    usage >&2
    exit 2
  fi
  printf '%s\n' "$value"
}

skill_display_name() {
  case "$1" in
    propel-code-review)
      printf '%s\n' "Propel Code Review"
      ;;
    carl)
      printf '%s\n' "CARL"
      ;;
    propel-address-pr-comments)
      printf '%s\n' "Propel Address PR Comments"
      ;;
    *)
      return 1
      ;;
  esac
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_ROOT="$REPO_ROOT/plugins/propel-code-review/skills"

VERSION=""
CHANGELOG=""
TAGS="latest"
PRINT_ONLY=0
declare -a REQUESTED_SKILLS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --changelog)
      CHANGELOG="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --skill)
      REQUESTED_SKILLS+=("$(require_value "$1" "${2-}")")
      shift 2
      ;;
    --tags)
      TAGS="$(require_value "$1" "${2-}")"
      shift 2
      ;;
    --print-only)
      PRINT_ONLY=1
      shift
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

if [[ -z "$VERSION" || -z "$CHANGELOG" ]]; then
  echo "--version and --changelog are required" >&2
  usage >&2
  exit 2
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "--version must be semver like 1.2.3" >&2
  exit 2
fi

declare -a SKILLS=()
if [[ "${#REQUESTED_SKILLS[@]}" -eq 0 ]]; then
  SKILLS=("propel-code-review" "carl" "propel-address-pr-comments")
else
  for skill in "${REQUESTED_SKILLS[@]}"; do
    if ! skill_display_name "$skill" >/dev/null; then
      echo "Unknown skill: $skill" >&2
      exit 2
    fi
    SKILLS+=("$skill")
  done
fi

if [[ "$PRINT_ONLY" -eq 0 ]]; then
  if ! command -v clawhub >/dev/null 2>&1; then
    echo "clawhub CLI not found. Install it with: npm install -g clawhub" >&2
    exit 1
  fi
  if ! clawhub whoami >/dev/null 2>&1; then
    echo "clawhub auth check failed. Run 'clawhub login' first." >&2
    exit 1
  fi
fi

for skill in "${SKILLS[@]}"; do
  skill_dir="$SKILLS_ROOT/$skill"
  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    echo "Missing SKILL.md for $skill at $skill_dir" >&2
    exit 1
  fi
  skill_name="$(skill_display_name "$skill")"

  cmd=(
    clawhub publish "$skill_dir"
    --slug "$skill"
    --name "$skill_name"
    --version "$VERSION"
    --tags "$TAGS"
    --changelog "$CHANGELOG"
  )

  if [[ "$PRINT_ONLY" -eq 1 ]]; then
    printf '%q ' "${cmd[@]}"
    printf '\n'
    continue
  fi

  "${cmd[@]}"
done
