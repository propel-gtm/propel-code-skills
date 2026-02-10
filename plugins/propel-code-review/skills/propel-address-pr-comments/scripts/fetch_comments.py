#!/usr/bin/env python3
"""
Fetch Propel code review findings for the current branch PR.

Default behavior:
- Resolve the open PR for the current branch via gh CLI.
- Build diff from PR base branch to HEAD.
- Submit async review to Propel Review API.
- Poll until completion and print numbered findings.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence

API_BASE_URL = "https://api.propelcode.ai"
MAX_DIFF_BYTES = 1_000_000


class CommandError(RuntimeError):
    pass


class ApiError(RuntimeError):
    pass


def run_command(cmd: Sequence[str], *, check: bool = True) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        detail = stderr or stdout or "command failed"
        raise CommandError(f"{' '.join(cmd)}: {detail}")
    return proc.stdout.strip()


def api_request(
    method: str,
    path: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": {"message": body}}
        message = (
            parsed.get("error", {}).get("message")
            or parsed.get("message")
            or body
            or "unknown error"
        )
        raise ApiError(f"{method} {path} failed ({exc.code}): {message}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"{method} {path} failed: {exc.reason}") from exc


def get_current_branch() -> str:
    return run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def get_open_pr_for_branch(branch: str) -> Dict[str, Any]:
    out = run_command(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number,title,url,baseRefName,headRefName",
        ]
    )
    prs = json.loads(out or "[]")
    if not prs:
        raise CommandError(
            f"No open PR found for branch '{branch}'. "
            "Pass --base-branch <branch> to run without PR lookup."
        )
    if len(prs) > 1:
        print(
            f"Found {len(prs)} open PRs for {branch}; using PR #{prs[0]['number']}.",
            file=sys.stderr,
        )
    return prs[0]


def get_repository() -> str:
    return run_command(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])


def ensure_base_ref(base_branch: str) -> str:
    run_command(["git", "fetch", "--quiet", "origin", base_branch], check=False)
    candidates = [f"origin/{base_branch}", base_branch]
    for ref in candidates:
        try:
            run_command(["git", "rev-parse", "--verify", ref])
            return ref
        except CommandError:
            continue
    raise CommandError(
        f"Cannot resolve base branch '{base_branch}' locally or on origin."
    )


def build_diff(base_ref: str) -> str:
    diff = run_command(["git", "diff", f"{base_ref}...HEAD"])
    diff_bytes = len(diff.encode("utf-8"))
    if diff_bytes > MAX_DIFF_BYTES:
        raise CommandError(
            f"Diff size {diff_bytes} exceeds Propel limit {MAX_DIFF_BYTES} bytes."
        )
    return diff


def create_review(token: str, diff: str, repository: str, base_commit: str) -> Dict[str, Any]:
    return api_request(
        "POST",
        "/v1/reviews",
        token,
        payload={
            "diff": diff,
            "repository": repository,
            "base_commit": base_commit,
        },
    )


def poll_review(
    token: str,
    review_id: str,
    poll_interval: float,
    timeout_seconds: int,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status = ""
    while True:
        body = api_request("GET", f"/v1/reviews/{review_id}", token)
        status = body.get("status", "unknown")
        if status != last_status:
            print(f"Review {review_id} status: {status}", file=sys.stderr)
            last_status = status
        if status in {"completed", "failed"}:
            return body
        if time.time() > deadline:
            raise TimeoutError(
                f"Timed out after {timeout_seconds}s waiting for review {review_id}."
            )
        time.sleep(poll_interval)


def normalize_comment(comment: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "index": index,
        "comment_id": comment.get("comment_id", ""),
        "file_path": comment.get("file_path", "<unknown>"),
        "line": comment.get("line", "?"),
        "severity": comment.get("severity", "info"),
        "rule_id": comment.get("rule_id", ""),
        "message": (comment.get("message") or "").strip(),
        "suggestion": (comment.get("suggestion") or "").strip(),
    }


def print_human_output(
    review_id: str,
    repository: str,
    base_branch: str,
    comments: List[Dict[str, Any]],
) -> None:
    print(f"Review ID: {review_id}")
    print(f"Repository: {repository}")
    print(f"Base branch: {base_branch}")
    if not comments:
        print("No Propel comments found.")
        return

    print(f"Found {len(comments)} Propel comments:")
    for c in comments:
        print(f"{c['index']}. [{c['severity']}] {c['file_path']}:{c['line']}")
        if c["rule_id"]:
            print(f"   Rule: {c['rule_id']}")
        if c["comment_id"]:
            print(f"   Comment ID: {c['comment_id']}")
        if c["message"]:
            print(f"   Message: {c['message']}")
        if c["suggestion"]:
            print(f"   Suggestion: {c['suggestion']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Propel review findings for the current branch PR."
    )
    parser.add_argument(
        "--review-id",
        help="Poll an existing Propel review ID instead of creating a new review.",
    )
    parser.add_argument(
        "--base-branch",
        help="Override base branch (skip PR base lookup).",
    )
    parser.add_argument(
        "--repository",
        help="Override repository in owner/repo format.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between status polls. Default: 5.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Polling timeout in seconds. Default: 600.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    args = parser.parse_args()

    token = os.getenv("PROPEL_API_KEY")
    if not token:
        print("Missing PROPEL_API_KEY in environment.", file=sys.stderr)
        return 1

    repository = args.repository or ""
    base_branch = args.base_branch or ""
    review_id = args.review_id or ""
    pr_data: Optional[Dict[str, Any]] = None

    try:
        if not review_id:
            branch = get_current_branch()
            if not base_branch:
                pr_data = get_open_pr_for_branch(branch)
                base_branch = pr_data["baseRefName"]
            if not repository:
                repository = get_repository()

            base_ref = ensure_base_ref(base_branch)
            base_commit = run_command(["git", "rev-parse", base_ref])
            diff = build_diff(base_ref)
            if not diff.strip():
                output = {
                    "review_id": "",
                    "status": "completed",
                    "repository": repository,
                    "base_branch": base_branch,
                    "pr": pr_data,
                    "comments": [],
                    "message": "No diff detected between base branch and HEAD.",
                }
                if args.json:
                    print(json.dumps(output, indent=2))
                else:
                    print("No diff detected between base branch and HEAD.")
                return 0

            create_body = create_review(token, diff, repository, base_commit)
            review_id = create_body.get("review_id", "")
            if not review_id:
                raise ApiError("Create review response did not include review_id.")

        status_body = poll_review(
            token,
            review_id,
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout,
        )
        if status_body.get("status") == "failed":
            err = status_body.get("error", {})
            message = err.get("message") or "Propel review failed."
            print(message, file=sys.stderr)
            return 2

        comments = [
            normalize_comment(comment, idx)
            for idx, comment in enumerate(status_body.get("comments", []), start=1)
        ]
        output = {
            "review_id": review_id,
            "status": status_body.get("status"),
            "repository": repository,
            "base_branch": base_branch,
            "pr": pr_data,
            "comments": comments,
        }
        if args.json:
            print(json.dumps(output, indent=2))
        else:
            print_human_output(review_id, repository, base_branch, comments)
        return 0

    except (CommandError, ApiError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

