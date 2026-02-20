from __future__ import annotations

import io
import json
import os
from urllib.error import HTTPError
from unittest.mock import patch

import pytest

from post_carl_summary_comment import (
    MARKER,
    ScriptError,
    _parse_review_ids,
    _post_summary_via_propel_api,
    build_comment_body,
    main,
)


class _Proc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _mock_run_factory():
    state = {"calls": []}

    def _mock_run(cmd, input=None, capture_output=True, text=True, timeout=120):  # noqa: ARG001
        state["calls"].append(cmd)

        if cmd[:3] == ["gh", "auth", "status"]:
            return _Proc(0, "", "")

        if cmd[:5] == ["gh", "pr", "status", "--json", "currentBranch"]:
            return _Proc(0, json.dumps({"currentBranch": {"number": 42}}), "")

        if cmd[:4] == ["gh", "pr", "view", "42"] and cmd[4:6] == ["--json", "number,url,title"]:
            return _Proc(0, json.dumps({"number": 42, "url": "https://github.com/o/r/pull/42", "title": "Test PR"}), "")

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


def test_parse_args_rejects_non_terminal_status():
    with pytest.raises(SystemExit):
        main(
            [
                "--status",
                "RUNNING",
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


def test_main_complete_requires_zero_remaining():
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
            "1",
            "--checks",
            "passed",
        ]
    )
    assert rc == 1


def test_main_non_complete_requires_non_zero_remaining():
    rc = main(
        [
            "--status",
            "BLOCKED",
            "--iterations",
            "3",
            "--fixed",
            "1",
            "--deferred",
            "1",
            "--remaining",
            "0",
            "--checks",
            "failed",
        ]
    )
    assert rc == 1


@patch("subprocess.run")
def test_main_dry_run(mock_run):
    runner, state = _mock_run_factory()
    mock_run.side_effect = runner

    with patch.dict(os.environ, {"PROPEL_API_BASE_URL": "https://api.test.example"}):
        with patch("post_carl_summary_comment._post_summary_via_propel_api") as mock_post:
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
    mock_post.assert_not_called()


@patch("subprocess.run")
def test_main_create_comment_via_propel_api(mock_run):
    runner, _ = _mock_run_factory()
    mock_run.side_effect = runner

    with patch.dict(os.environ, {"PROPEL_API_KEY": "rev_test_key"}):
        with patch(
            "post_carl_summary_comment._post_summary_via_propel_api",
            return_value={"action": "created", "comment_id": "1001", "url": "https://github.com/o/r/pull/42#issuecomment-1001"},
        ) as mock_post:
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
    assert mock_post.call_count == 1


@patch("subprocess.run")
def test_main_update_comment_via_propel_api(mock_run):
    runner, _ = _mock_run_factory()
    mock_run.side_effect = runner

    with patch.dict(os.environ, {"PROPEL_API_KEY": "rev_test_key"}):
        with patch(
            "post_carl_summary_comment._post_summary_via_propel_api",
            return_value={"action": "updated", "comment_id": "77", "url": "https://github.com/o/r/pull/42#issuecomment-77"},
        ) as mock_post:
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
    assert mock_post.call_count == 1


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
        if cmd[:5] == ["gh", "pr", "status", "--json", "currentBranch"]:
            return _Proc(0, json.dumps({"currentBranch": None}), "")
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


@patch("subprocess.run")
def test_main_missing_propel_api_key_returns_error(mock_run):
    runner, _ = _mock_run_factory()
    mock_run.side_effect = runner

    with patch.dict(os.environ, {}, clear=True):
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


def test_post_summary_via_propel_api_success():
    with patch(
        "post_carl_summary_comment.urlrequest.urlopen",
        return_value=_FakeHTTPResponse({"action": "created", "comment_id": "1001", "url": "https://example.com/comment/1001"}),
    ) as mock_urlopen:
        result = _post_summary_via_propel_api(
            api_base_url="https://api.propelcode.ai",
            api_key="rev_test",
            repository="owner/repo",
            pr_number=42,
            body=f"{MARKER}\nhello",
        )

    assert result["action"] == "created"
    request_obj = mock_urlopen.call_args.args[0]
    assert request_obj.full_url == "https://api.propelcode.ai/v1/reviews/pr-comments/upsert"
    assert request_obj.get_method() == "POST"

    payload = json.loads(request_obj.data.decode("utf-8"))
    assert payload["repository"] == "owner/repo"
    assert payload["pr_number"] == 42
    assert payload["marker"] == MARKER


@patch("subprocess.run")
def test_main_derives_repo_from_pr_url(mock_run):
    state = {"calls": []}

    def runner(cmd, input=None, capture_output=True, text=True, timeout=120):  # noqa: ARG001
        state["calls"].append(cmd)
        if cmd[:3] == ["gh", "auth", "status"]:
            return _Proc(0, "", "")
        if cmd[:5] == ["gh", "pr", "status", "--json", "currentBranch"]:
            return _Proc(0, json.dumps({"currentBranch": {"number": 42}}), "")
        if cmd[:4] == ["gh", "pr", "view", "42"] and cmd[4:6] == ["--json", "number,url,title"]:
            return _Proc(0, json.dumps({"number": 42, "url": "https://github.com/base/repo/pull/42", "title": "Cross-repo PR"}), "")
        raise AssertionError(f"Unhandled command: {cmd}")

    mock_run.side_effect = runner

    with patch.dict(os.environ, {"PROPEL_API_KEY": "rev_test_key"}):
        with patch(
            "post_carl_summary_comment._post_summary_via_propel_api",
            return_value={"action": "created", "comment_id": "1001"},
        ) as mock_post:
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
    assert mock_post.call_count == 1
    assert mock_post.call_args.kwargs["repository"] == "base/repo"


def test_post_summary_via_propel_api_http_error():
    err = HTTPError(
        url="https://api.propelcode.ai/v1/reviews/pr-comments/upsert",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"Repository not found"}'),
    )

    with patch("post_carl_summary_comment.urlrequest.urlopen", side_effect=err):
        with pytest.raises(ScriptError, match="Propel API request failed \\(404\\)"):
            _post_summary_via_propel_api(
                api_base_url="https://api.propelcode.ai",
                api_key="rev_test",
                repository="missing/repo",
                pr_number=42,
                body=f"{MARKER}\nhello",
            )


def test_script_error_str():
    assert str(ScriptError("x")) == "x"
