#!/usr/bin/env python3
"""
Post or update a sticky PR comment summarizing a local CARL loop run.

Requires:
  - PROPEL_API_KEY with reviews:write scope
  - gh CLI installed and authenticated
  - current branch associated with an open PR

Usage example:
  python post_carl_summary_comment.py \
    --status COMPLETE \
    --base main \
    --iterations 3 \
    --fixed 7 \
    --deferred 1 \
    --remaining 0 \
    --checks passed \
    --review-ids "019c...,019d..."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

COMMAND_TIMEOUT_SECONDS = 120
MARKER = "<!-- carl-local-loop -->"
DEFAULT_PROPEL_API_BASE_URL = "https://api.propelcode.ai"


class ScriptError(RuntimeError):
    """Script-level failure with actionable message."""


SKILLS_DIR = Path(__file__).resolve().parents[2]
if str(SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(SKILLS_DIR))

from command_helpers import CommandError, run_cmd, run_json


def _run(cmd: list[str], stdin: str | None = None) -> str:
    try:
        return run_cmd(cmd, stdin=stdin, timeout_seconds=COMMAND_TIMEOUT_SECONDS)
    except CommandError as exc:
        raise ScriptError(str(exc)) from exc


def _run_json(cmd: list[str], stdin: str | None = None) -> dict[str, Any] | list[Any]:
    try:
        return run_json(cmd, stdin=stdin, timeout_seconds=COMMAND_TIMEOUT_SECONDS)
    except CommandError as exc:
        raise ScriptError(str(exc)) from exc


def _ensure_gh_authenticated() -> None:
    _run(["gh", "auth", "status"])


@dataclass
class PullRequestContext:
    number: int
    url: str
    title: str
    repo: str


def _repo_slug_from_pr_url(url: str) -> str:
    parsed = urlparse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 4 and parts[2] == "pull":
        return f"{parts[0]}/{parts[1]}"
    raise ScriptError(f"Could not derive repository slug from PR URL: {url}")


def _current_branch_name() -> str:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if branch == "" or branch == "HEAD":
        raise ScriptError("Could not determine current git branch")
    return branch


def _resolve_pr_lookup_repository() -> tuple[str, str]:
    payload = _run_json(["gh", "repo", "view", "--json", "nameWithOwner,parent"])
    if not isinstance(payload, dict):
        raise ScriptError("Unexpected response from gh repo view")

    current_repo = str(payload.get("nameWithOwner", "")).strip()
    if "/" not in current_repo:
        raise ScriptError("Could not determine current repository from gh repo view")

    current_owner = current_repo.split("/", 1)[0]

    parent_repo = ""
    parent = payload.get("parent")
    if isinstance(parent, dict):
        parent_repo = str(parent.get("nameWithOwner", "")).strip()

    lookup_repo = parent_repo or current_repo
    return lookup_repo, current_owner


def _current_branch_pr() -> tuple[int, str] | None:
    branch = _current_branch_name()
    lookup_repo, current_owner = _resolve_pr_lookup_repository()
    head_refs = [f"{current_owner}:{branch}", branch]
    seen: set[str] = set()

    for head_ref in head_refs:
        if head_ref in seen:
            continue
        seen.add(head_ref)

        payload = _run_json(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                lookup_repo,
                "--state",
                "open",
                "--head",
                head_ref,
                "--json",
                "number",
            ]
        )
        if not isinstance(payload, list):
            raise ScriptError("Unexpected response from gh pr list")
        if len(payload) == 0:
            continue
        first = payload[0]
        if not isinstance(first, dict):
            raise ScriptError("Unexpected PR payload from gh pr list")
        number = first.get("number")
        if not isinstance(number, int):
            raise ScriptError("Unexpected PR number from gh pr list")
        return number, lookup_repo

    return None


def _current_pr_context() -> PullRequestContext | None:
    current = _current_branch_pr()
    if current is None:
        return None
    pr_number, lookup_repo = current

    pr = _run_json(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            lookup_repo,
            "--json",
            "number,url,title",
        ]
    )
    if not isinstance(pr, dict):
        raise ScriptError("Unexpected response from gh pr view")
    number = int(pr["number"])
    url = str(pr["url"])
    title = str(pr.get("title", ""))
    repo = _repo_slug_from_pr_url(url)
    return PullRequestContext(number=number, url=url, title=title, repo=repo)


def _propel_api_key() -> str:
    key = os.getenv("PROPEL_API_KEY", "").strip()
    if not key:
        raise ScriptError("PROPEL_API_KEY is not set")
    return key


def _propel_api_base_url() -> str:
    base_url = os.getenv("PROPEL_API_BASE_URL", DEFAULT_PROPEL_API_BASE_URL).strip()
    if not base_url:
        raise ScriptError("PROPEL_API_BASE_URL is empty")
    return base_url.rstrip("/")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_comment_body(
    *,
    status: str,
    base: str,
    iterations: int,
    fixed: int,
    deferred: int,
    remaining: int,
    checks: str,
    review_ids: list[str],
    notes: str | None,
) -> str:
    rid_line = ", ".join(review_ids) if review_ids else "none"
    note_line = notes.strip() if notes else "none"
    return "\n".join(
        [
            MARKER,
            "### CARL Local Loop Summary",
            "",
            f"- status: `{status}`",
            f"- base: `{base}`",
            f"- iterations: `{iterations}`",
            f"- fixed: `{fixed}`",
            f"- deferred: `{deferred}`",
            f"- remaining: `{remaining}`",
            f"- checks: `{checks}`",
            f"- review_ids: `{rid_line}`",
            f"- notes: {note_line}",
            f"- updated_at_utc: `{_iso_now()}`",
            "",
            "_Generated by local CARL run._",
        ]
    )


def _post_summary_via_propel_api(*, api_base_url: str, api_key: str, repository: str, pr_number: int, body: str) -> dict[str, Any]:
    payload = {
        "repository": repository,
        "pr_number": pr_number,
        "marker": MARKER,
        "body": body,
    }
    req = urlrequest.Request(
        url=f"{api_base_url}/v1/reviews/pr-comments/upsert",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urlrequest.urlopen(req, timeout=COMMAND_TIMEOUT_SECONDS) as resp:
            response_text = resp.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace").strip()
        detail = error_body if error_body else str(exc.reason)
        raise ScriptError(f"Propel API request failed ({exc.code}): {detail}") from exc
    except urlerror.URLError as exc:
        raise ScriptError(f"Failed to reach Propel API: {exc.reason}") from exc

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ScriptError("Invalid JSON response from Propel API") from exc
    if not isinstance(data, dict):
        raise ScriptError("Unexpected response from Propel API")
    return data


def _parse_review_ids(raw: str) -> list[str]:
    values = [x.strip() for x in raw.split(",")]
    return [x for x in values if x]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", required=True, choices=["COMPLETE", "BLOCKED", "MAX_ITERATIONS_REACHED"])
    parser.add_argument("--base", default="main")
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--fixed", type=int, required=True)
    parser.add_argument("--deferred", type=int, required=True)
    parser.add_argument("--remaining", type=int, required=True)
    parser.add_argument(
        "--checks",
        required=True,
        choices=["passed", "failed", "not_run"],
        help="passed|failed|not_run",
    )
    parser.add_argument("--review-ids", default="", help="Comma-separated review IDs")
    parser.add_argument("--notes", default="", help="Optional free-form summary note")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print comment body and whether create/update would happen without mutating GitHub.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if args.status == "COMPLETE" and args.remaining != 0:
            raise ScriptError("status COMPLETE requires --remaining 0")
        if args.status in {"BLOCKED", "MAX_ITERATIONS_REACHED"} and args.remaining == 0:
            raise ScriptError(f"status {args.status} requires --remaining greater than 0")

        _ensure_gh_authenticated()
        pr = _current_pr_context()
        if pr is None:
            print("No open PR found for current branch; skipping CARL summary comment publish.")
            return 0
        review_ids = _parse_review_ids(args.review_ids)
        body = build_comment_body(
            status=args.status,
            base=args.base,
            iterations=args.iterations,
            fixed=args.fixed,
            deferred=args.deferred,
            remaining=args.remaining,
            checks=args.checks,
            review_ids=review_ids,
            notes=args.notes,
        )

        if args.dry_run:
            api_base_url = _propel_api_base_url()
            print(f"DRY_RUN repo={pr.repo} pr={pr.number} endpoint={api_base_url}/v1/reviews/pr-comments/upsert")
            print(body)
            return 0

        api_key = _propel_api_key()
        api_base_url = _propel_api_base_url()
        result = _post_summary_via_propel_api(
            api_base_url=api_base_url,
            api_key=api_key,
            repository=pr.repo,
            pr_number=pr.number,
            body=body,
        )

        action = str(result.get("action", "")).strip().lower()
        comment_id = str(result.get("comment_id", "")).strip()
        comment_url = str(result.get("url", "")).strip()
        if action == "updated":
            suffix = f" (id={comment_id})" if comment_id else ""
            print(f"Updated CARL summary comment{suffix} on {pr.repo}#{pr.number}")
        else:
            suffix = f" (id={comment_id})" if comment_id else ""
            print(f"Created CARL summary comment{suffix} on {pr.repo}#{pr.number}")
        if comment_url:
            print(f"Comment URL: {comment_url}")
        return 0
    except ScriptError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
