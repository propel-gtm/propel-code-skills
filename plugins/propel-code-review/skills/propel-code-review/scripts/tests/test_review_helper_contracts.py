from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[6]
SCRIPTS_DIR = REPO_ROOT / "plugins/propel-code-review/skills/propel-code-review/scripts"

MOCK_CURL = """#!/usr/bin/env bash
set -euo pipefail

OUT_FILE=""
WRITE_FMT=""
DATA_ARG=""
URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o)
      OUT_FILE="${2-}"
      shift 2
      ;;
    -w)
      WRITE_FMT="${2-}"
      shift 2
      ;;
    --data-binary)
      DATA_ARG="${2-}"
      shift 2
      ;;
    --config|-X)
      shift 2
      ;;
    -s|-S|-sS)
      shift
      ;;
    --*)
      shift
      ;;
    *)
      URL="$1"
      shift
      ;;
  esac
done

if [[ -n "${MOCK_CURL_URL_CAPTURE:-}" ]]; then
  printf '%s\\n' "$URL" >> "$MOCK_CURL_URL_CAPTURE"
fi

if [[ "$DATA_ARG" == "@-" ]]; then
  STDIN_PAYLOAD="$(cat)"
  if [[ -n "${MOCK_CURL_STDIN_CAPTURE:-}" ]]; then
    printf '%s' "$STDIN_PAYLOAD" > "$MOCK_CURL_STDIN_CAPTURE"
  fi
elif [[ -n "$DATA_ARG" && -n "${MOCK_CURL_DATA_CAPTURE:-}" ]]; then
  printf '%s' "$DATA_ARG" > "$MOCK_CURL_DATA_CAPTURE"
fi

COUNTER_FILE="${MOCK_CURL_COUNTER_FILE:-}"
COUNT=1
if [[ -n "$COUNTER_FILE" ]]; then
  if [[ -f "$COUNTER_FILE" ]]; then
    COUNT="$(cat "$COUNTER_FILE")"
  else
    COUNT=0
  fi
  COUNT=$((COUNT + 1))
  printf '%s' "$COUNT" > "$COUNTER_FILE"
fi

EXIT_CODE="${MOCK_CURL_EXIT_CODE:-0}"
HTTP_CODE="${MOCK_CURL_HTTP_CODE:-200}"
BODY="${MOCK_CURL_BODY:-{}}"
if [[ -n "${MOCK_CURL_SEQUENCE_FILE:-}" ]]; then
  LINE="$(sed -n "${COUNT}p" "$MOCK_CURL_SEQUENCE_FILE" || true)"
  if [[ -z "$LINE" ]]; then
    LINE="$(tail -n 1 "$MOCK_CURL_SEQUENCE_FILE")"
  fi
  EXIT_CODE="${LINE%%|*}"
  REST="${LINE#*|}"
  HTTP_CODE="${REST%%|*}"
  BODY="${REST#*|}"
fi

if [[ "${BODY}" == @* ]]; then
  BODY="$(cat "${BODY#@}")"
fi

if [[ -n "$OUT_FILE" ]]; then
  printf '%s' "$BODY" > "$OUT_FILE"
fi
if [[ -n "$WRITE_FMT" ]]; then
  printf '%s' "$HTTP_CODE"
fi
exit "$EXIT_CODE"
"""

MOCK_SLEEP = """#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${MOCK_SLEEP_CAPTURE:-}" ]]; then
  printf '%s\\n' "$*" >> "$MOCK_SLEEP_CAPTURE"
fi
exit 0
"""


@pytest.fixture
def mock_tooling(tmp_path: Path) -> dict[str, Path | dict[str, str]]:
    mock_bin = tmp_path / "mockbin"
    mock_bin.mkdir()

    curl_path = mock_bin / "curl"
    curl_path.write_text(MOCK_CURL, encoding="utf-8")
    curl_path.chmod(0o755)

    sleep_path = mock_bin / "sleep"
    sleep_path.write_text(MOCK_SLEEP, encoding="utf-8")
    sleep_path.chmod(0o755)

    counter_file = tmp_path / "curl_counter.txt"
    sequence_file = tmp_path / "curl_sequence.txt"
    stdin_capture = tmp_path / "curl_stdin_capture.txt"
    data_capture = tmp_path / "curl_data_capture.txt"
    url_capture = tmp_path / "curl_url_capture.txt"
    sleep_capture = tmp_path / "sleep_capture.txt"

    env = os.environ.copy()
    env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
    env["PROPEL_API_KEY"] = "rev_test_key"
    env["MOCK_CURL_COUNTER_FILE"] = str(counter_file)
    env["MOCK_CURL_SEQUENCE_FILE"] = str(sequence_file)
    env["MOCK_CURL_STDIN_CAPTURE"] = str(stdin_capture)
    env["MOCK_CURL_DATA_CAPTURE"] = str(data_capture)
    env["MOCK_CURL_URL_CAPTURE"] = str(url_capture)
    env["MOCK_SLEEP_CAPTURE"] = str(sleep_capture)

    return {
        "env": env,
        "counter_file": counter_file,
        "sequence_file": sequence_file,
        "stdin_capture": stdin_capture,
        "data_capture": data_capture,
        "url_capture": url_capture,
        "sleep_capture": sleep_capture,
    }


def _write_sequence(path: Path, rows: list[tuple[int, int, str | Path]]) -> None:
    lines = []
    for exit_code, http_code, body in rows:
        body_value = f"@{body}" if isinstance(body, Path) else body
        lines.append(f"{exit_code}|{http_code}|{body_value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_script(
    script_name: str, args: list[str], env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPTS_DIR / script_name), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_create_review_success_contract(mock_tooling: dict[str, Path | dict[str, str]]) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    counter_file = mock_tooling["counter_file"]
    stdin_capture = mock_tooling["stdin_capture"]
    url_capture = mock_tooling["url_capture"]

    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)
    assert isinstance(counter_file, Path)
    assert isinstance(stdin_capture, Path)
    assert isinstance(url_capture, Path)

    _write_sequence(
        sequence_file,
        [(0, 202, '{"review_id":"review-123","status":"queued"}')],
    )

    diff_file = sequence_file.parent / "sample.diff"
    diff_file.write_text("diff --git a/a b/a\n+hello\n", encoding="utf-8")
    output_file = sequence_file.parent / "create_response.json"

    result = _run_script(
        "create_review.sh",
        [
            "--diff-file",
            str(diff_file),
            "--repo",
            "propel-gtm/propel-code-skills",
            "--base-commit",
            "abc123",
            "--output-file",
            str(output_file),
        ],
        env,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["review_id"] == "review-123"
    assert json.loads(output_file.read_text(encoding="utf-8"))["status"] == "queued"

    payload = json.loads(stdin_capture.read_text(encoding="utf-8"))
    assert payload["repository"] == "propel-gtm/propel-code-skills"
    assert payload["base_commit"] == "abc123"
    assert payload["diff"] == "diff --git a/a b/a\n+hello\n"

    assert counter_file.read_text(encoding="utf-8") == "1"
    assert url_capture.read_text(encoding="utf-8").strip().endswith("/v1/reviews")


def test_create_review_retries_once_on_5xx(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    counter_file = mock_tooling["counter_file"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)
    assert isinstance(counter_file, Path)

    _write_sequence(
        sequence_file,
        [
            (0, 500, '{"error":"transient"}'),
            (0, 202, '{"review_id":"review-456","status":"queued"}'),
        ],
    )

    diff_file = sequence_file.parent / "retry.diff"
    diff_file.write_text("diff --git a/a b/a\n+retry\n", encoding="utf-8")

    result = _run_script(
        "create_review.sh",
        [
            "--diff-file",
            str(diff_file),
            "--repo",
            "propel-gtm/propel-code-skills",
            "--base-commit",
            "def456",
            "--max-attempts",
            "2",
        ],
        env,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["review_id"] == "review-456"
    assert counter_file.read_text(encoding="utf-8") == "2"


def test_poll_review_recovers_from_parse_failure(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    counter_file = mock_tooling["counter_file"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)
    assert isinstance(counter_file, Path)

    _write_sequence(
        sequence_file,
        [
            (0, 200, "not-json"),
            (0, 200, '{"status":"completed","comments":[]}'),
        ],
    )

    output_file = sequence_file.parent / "poll_response.json"
    result = _run_script(
        "poll_review.sh",
        [
            "--review-id",
            "review-123",
            "--max-attempts",
            "2",
            "--sleep-seconds",
            "1",
            "--output-file",
            str(output_file),
        ],
        env,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "completed"
    assert json.loads(output_file.read_text(encoding="utf-8"))["status"] == "completed"
    assert counter_file.read_text(encoding="utf-8") == "2"


def test_poll_review_failed_status_returns_exit_code_2(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)

    _write_sequence(
        sequence_file,
        [(0, 200, '{"status":"failed","error":{"code":"generation_failed"}}')],
    )

    result = _run_script(
        "poll_review.sh",
        [
            "--review-id",
            "review-123",
            "--max-attempts",
            "1",
            "--sleep-seconds",
            "1",
        ],
        env,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "failed"


def test_poll_review_waits_for_terminal_status_even_when_progress_is_high(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    counter_file = mock_tooling["counter_file"]
    sleep_capture = mock_tooling["sleep_capture"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)
    assert isinstance(counter_file, Path)
    assert isinstance(sleep_capture, Path)

    _write_sequence(
        sequence_file,
        [
            (
                0,
                200,
                '{"status":"running","estimated_progress_pct":99,"progress_is_estimated":true,"progress_message":"Reviewing","poll_after_ms":3000,"comments":[]}',
            ),
            (0, 200, '{"status":"completed","comments":[]}'),
        ],
    )

    result = _run_script(
        "poll_review.sh",
        [
            "--review-id",
            "review-123",
            "--max-attempts",
            "2",
            "--sleep-seconds",
            "30",
        ],
        env,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "completed"
    assert counter_file.read_text(encoding="utf-8") == "2"
    assert sleep_capture.read_text(encoding="utf-8").splitlines() == ["30"]


def test_poll_review_uses_api_poll_after_hint_as_lower_bound(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    sleep_capture = mock_tooling["sleep_capture"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)
    assert isinstance(sleep_capture, Path)

    _write_sequence(
        sequence_file,
        [
            (
                0,
                200,
                '{"status":"running","estimated_progress_pct":25,"progress_is_estimated":true,"progress_message":"Queued behind other work","poll_after_ms":12000}',
            ),
            (0, 200, '{"status":"completed","comments":[]}'),
        ],
    )

    result = _run_script(
        "poll_review.sh",
        [
            "--review-id",
            "review-123",
            "--max-attempts",
            "2",
            "--sleep-seconds",
            "5",
        ],
        env,
    )

    assert result.returncode == 0
    assert "next_poll=12s" in result.stderr
    assert sleep_capture.read_text(encoding="utf-8").splitlines() == ["12"]


def test_poll_review_default_budget_is_fifteen_minutes(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    counter_file = mock_tooling["counter_file"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)
    assert isinstance(counter_file, Path)

    _write_sequence(
        sequence_file,
        [(0, 200, '{"status":"running"}')],
    )

    result = _run_script(
        "poll_review.sh",
        [
            "--review-id",
            "review-123",
        ],
        env,
    )

    assert result.returncode == 1
    assert "timed out after 30 polls (~900 seconds of waiting)" in result.stderr
    assert counter_file.read_text(encoding="utf-8") == "30"


def test_post_comment_feedback_contract(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    data_capture = mock_tooling["data_capture"]
    url_capture = mock_tooling["url_capture"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)
    assert isinstance(data_capture, Path)
    assert isinstance(url_capture, Path)

    _write_sequence(
        sequence_file,
        [(0, 200, '{"review_id":"review-123","comment_id":"c-1","incorporated":true}')],
    )

    output_file = sequence_file.parent / "feedback_response.json"
    result = _run_script(
        "post_comment_feedback.sh",
        [
            "--review-id",
            "review-123",
            "--comment-id",
            "c-1",
            "--incorporated",
            "true",
            "--notes",
            "Applied patch",
            "--output-file",
            str(output_file),
        ],
        env,
    )

    assert result.returncode == 0
    payload = json.loads(data_capture.read_text(encoding="utf-8"))
    assert payload == {"comment_id": "c-1", "incorporated": True, "notes": "Applied patch"}

    assert json.loads(result.stdout)["comment_id"] == "c-1"
    assert json.loads(output_file.read_text(encoding="utf-8"))["review_id"] == "review-123"
    assert url_capture.read_text(encoding="utf-8").strip().endswith(
        "/v1/reviews/review-123/comments/feedback"
    )


def test_post_comment_feedback_non_2xx_fails(
    mock_tooling: dict[str, Path | dict[str, str]]
) -> None:
    env = mock_tooling["env"]
    sequence_file = mock_tooling["sequence_file"]
    assert isinstance(env, dict)
    assert isinstance(sequence_file, Path)

    _write_sequence(
        sequence_file,
        [(0, 400, '{"error":"bad request"}')],
    )

    result = _run_script(
        "post_comment_feedback.sh",
        [
            "--review-id",
            "review-123",
            "--comment-id",
            "c-1",
            "--incorporated",
            "false",
        ],
        env,
    )

    assert result.returncode == 1
    assert "Feedback post failed (400)" in result.stderr
