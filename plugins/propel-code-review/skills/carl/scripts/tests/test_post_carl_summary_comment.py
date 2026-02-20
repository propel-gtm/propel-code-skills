from __future__ import annotations

import json
from unittest.mock import patch

from post_carl_summary_comment import (
    MARKER,
    ScriptError,
    _find_existing_comment_id,
    _parse_review_ids,
    build_comment_body,
    main,
)


class _Proc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _mock_run_factory():
    state = {"calls": []}

    def _mock_run(cmd, input=None, capture_output=True, text=True, timeout=120):  # noqa: ARG001
        state["calls"].append(cmd)
        joined = " ".join(cmd)

        if cmd[:3] == ["gh", "auth", "status"]:
            return _Proc(0, "", "")

        if cmd[:4] == ["gh", "pr", "view", "--json"]:
            return _Proc(0, json.dumps({"number": 42, "url": "https://github.com/o/r/pull/42", "title": "Test PR"}), "")

        if cmd[:6] == ["gh", "repo", "view", "--json", "nameWithOwner", "--jq"]:
            return _Proc(0, "owner/repo\n", "")

        if "/issues/42/comments" in joined and "--method" not in cmd:
            return _Proc(0, json.dumps([]), "")

        if "/issues/42/comments" in joined and "POST" in cmd:
            return _Proc(0, json.dumps({"id": 1001}), "")

        if "/issues/comments/" in joined and "PATCH" in cmd:
            return _Proc(0, json.dumps({"id": 999}), "")

        raise AssertionError(f"Unhandled command: {cmd}")

    return _mock_run, state


def test_build_comment_body_contains_marker_and_fields():
    body = build_comment_body(
        status="COMPLETE",
        base="main",
        iterations=2,
        fixed=7,
        deferred=1,
        remaining=0,
        checks="passed",
        review_ids=["r1", "r2"],
        notes="done",
    )
    assert MARKER in body
    assert "- status: `COMPLETE`" in body
    assert "- fixed: `7`" in body
    assert "r1, r2" in body


def test_parse_review_ids():
    assert _parse_review_ids("") == []
    assert _parse_review_ids("a,b,, c ") == ["a", "b", "c"]


@patch("post_carl_summary_comment._list_bot_comments")
def test_find_existing_comment_id(mock_list):
    mock_list.return_value = [
        {"id": 1, "body": "hello"},
        {"id": 2, "body": f"{MARKER}\nexisting"},
    ]
    assert _find_existing_comment_id(42, "owner/repo") == 2


@patch("subprocess.run")
def test_main_dry_run_create(mock_run):
    runner, state = _mock_run_factory()
    mock_run.side_effect = runner

    rc = main(
        [
            "--status",
            "COMPLETE",
            "--iterations",
            "2",
            "--fixed",
            "7",
            "--deferred",
            "0",
            "--remaining",
            "0",
            "--checks",
            "passed",
            "--review-ids",
            "a,b",
            "--dry-run",
        ]
    )
    assert rc == 0
    assert any(cmd[:3] == ["gh", "auth", "status"] for cmd in state["calls"])
    # Dry run should not post comment.
    assert not any("/issues/42/comments" in " ".join(cmd) and "POST" in cmd for cmd in state["calls"])


@patch("subprocess.run")
def test_main_create_comment(mock_run):
    runner, state = _mock_run_factory()
    mock_run.side_effect = runner

    rc = main(
        [
            "--status",
            "BLOCKED",
            "--iterations",
            "1",
            "--fixed",
            "0",
            "--deferred",
            "1",
            "--remaining",
            "1",
            "--checks",
            "failed",
        ]
    )
    assert rc == 0
    assert any("/issues/42/comments" in " ".join(cmd) and "POST" in cmd for cmd in state["calls"])


@patch("subprocess.run")
def test_main_update_comment(mock_run):
    state = {"calls": []}

    def runner(cmd, input=None, capture_output=True, text=True, timeout=120):  # noqa: ARG001
        state["calls"].append(cmd)
        joined = " ".join(cmd)

        if cmd[:3] == ["gh", "auth", "status"]:
            return _Proc(0, "", "")
        if cmd[:4] == ["gh", "pr", "view", "--json"]:
            return _Proc(0, json.dumps({"number": 42, "url": "https://github.com/o/r/pull/42", "title": "Test PR"}), "")
        if cmd[:6] == ["gh", "repo", "view", "--json", "nameWithOwner", "--jq"]:
            return _Proc(0, "owner/repo\n", "")
        if "/issues/42/comments" in joined and "--method" not in cmd:
            comments = [{"id": 77, "body": f"{MARKER}\nold summary"}]
            return _Proc(0, json.dumps(comments), "")
        if "/issues/comments/77" in joined and "PATCH" in cmd:
            return _Proc(0, json.dumps({"id": 77}), "")
        raise AssertionError(f"Unhandled command: {cmd}")

    mock_run.side_effect = runner

    rc = main(
        [
            "--status",
            "MAX_ITERATIONS_REACHED",
            "--iterations",
            "6",
            "--fixed",
            "4",
            "--deferred",
            "2",
            "--remaining",
            "3",
            "--checks",
            "passed",
        ]
    )
    assert rc == 0
    assert any("/issues/comments/77" in " ".join(cmd) and "PATCH" in cmd for cmd in state["calls"])


@patch("subprocess.run")
def test_main_returns_error_code_on_gh_failure(mock_run):
    mock_run.return_value = _Proc(1, "", "gh auth failed")
    rc = main(
        [
            "--status",
            "COMPLETE",
            "--iterations",
            "1",
            "--fixed",
            "1",
            "--deferred",
            "0",
            "--remaining",
            "0",
            "--checks",
            "passed",
        ]
    )
    assert rc == 1


@patch("subprocess.run")
def test_main_no_open_pr_returns_zero(mock_run):
    state = {"calls": []}

    def runner(cmd, input=None, capture_output=True, text=True, timeout=120):  # noqa: ARG001
        state["calls"].append(cmd)
        if cmd[:3] == ["gh", "auth", "status"]:
            return _Proc(0, "", "")
        if cmd[:4] == ["gh", "pr", "view", "--json"]:
            return _Proc(1, "", 'no pull requests found for branch "main"')
        raise AssertionError(f"Unhandled command: {cmd}")

    mock_run.side_effect = runner
    rc = main(
        [
            "--status",
            "COMPLETE",
            "--iterations",
            "1",
            "--fixed",
            "1",
            "--deferred",
            "0",
            "--remaining",
            "0",
            "--checks",
            "passed",
        ]
    )
    assert rc == 0
    assert not any("/issues/" in " ".join(cmd) for cmd in state["calls"])


def test_find_existing_comment_none():
    with patch("post_carl_summary_comment._list_bot_comments", return_value=[{"id": 1, "body": "x"}]):
        assert _find_existing_comment_id(42, "owner/repo") is None


def test_script_error_str():
    assert str(ScriptError("x")) == "x"
