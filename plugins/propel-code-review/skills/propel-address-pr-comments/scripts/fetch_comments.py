#!/usr/bin/env python3
"""
Fetch all PR conversation comments + reviews + review threads (inline threads)
for the PR associated with the current git branch, by shelling out to:

  gh api graphql

Requires:
  - `gh auth login` already set up
  - current branch has an associated (open) PR

Usage:
  ./fetch_comments.py > pr_comments_addressable.json
  python3 fetch_comments.py > pr_comments_addressable.json
  python3 fetch_comments.py --all-comments > pr_comments_full.json

Note:
  `gh pr view --json` is used only to resolve the current PR number/URL.
  Inline review threads are fetched via GraphQL because `gh pr view` does not
  expose `reviewThreads`.
  The `addressable` payload excludes resolved review threads and Propel-authored
  summary-like comments/reviews.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

from command_helpers import CommandError, run_cmd, run_json

COMMAND_TIMEOUT_SECONDS = 120
PROPEL_AUTHOR_TOKEN = "propel"
KNOWN_PROPEL_AUTHOR_LOGINS = {
    "propel",
    "propel-ai",
    "propel-code-bot",
    "propelcodebot",
}
SUMMARY_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:overall\s+)?summary\b")
SUMMARY_SIGNALS = (
    "<!-- carl-local-loop -->",
    "### carl local loop summary",
    "overall, this pr",
    "overall this pr",
    "overall, this change",
    "overall this change",
    "high-level summary",
    "summary of findings",
    "findings summary",
    "no blocking issues",
    "no major issues found",
    "looks good overall",
)
SUMMARY_EXACT_MATCHES = {"lgtm", "lgtm.", "lgtm!"}

QUERY = """\
query(
  $owner: String!,
  $repo: String!,
  $number: Int!,
  $commentsCursor: String,
  $reviewsCursor: String,
  $threadsCursor: String
) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      url
      title
      state

      # Top-level "Conversation" comments (issue comments on the PR)
      comments(first: 100, after: $commentsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          body
          createdAt
          updatedAt
          author { login }
        }
      }

      # Review submissions (Approve / Request changes / Comment), with body if present
      reviews(first: 100, after: $reviewsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          state
          body
          submittedAt
          author { login }
        }
      }

      # Inline review threads (grouped), includes resolved state
      reviewThreads(first: 100, after: $threadsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          diffSide
          startLine
          startDiffSide
          originalLine
          originalStartLine
          resolvedBy { login }
          comments(first: 100) {
            nodes {
              id
              body
              createdAt
              updatedAt
              author { login }
            }
          }
        }
      }
    }
  }
}
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch PR comments/reviews/threads and emit an addressable subset "
            "that excludes resolved threads and Propel summary-like comments."
        )
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--addressable-only",
        dest="addressable_only",
        action="store_true",
        default=True,
        help="Print only the filtered addressable payload (default).",
    )
    mode_group.add_argument(
        "--all-comments",
        dest="addressable_only",
        action="store_false",
        help="Print the full payload (raw comments/reviews/threads plus addressable subset).",
    )
    return parser.parse_args(argv)


def _author_login(node: dict[str, Any]) -> str:
    author = node.get("author")
    if not isinstance(author, dict):
        return ""
    login = author.get("login")
    if not isinstance(login, str):
        return ""
    return login.strip()


def is_propel_author(login: str | None) -> bool:
    if not isinstance(login, str):
        return False
    normalized = login.strip().lower()
    if normalized == "":
        return False
    if normalized in KNOWN_PROPEL_AUTHOR_LOGINS:
        return True
    return normalized.startswith(f"{PROPEL_AUTHOR_TOKEN}-") or normalized.startswith(f"{PROPEL_AUTHOR_TOKEN}_")


def _first_non_empty_line(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line:
            return line.lower()
    return ""


def looks_like_propel_summary_comment(body: str | None) -> bool:
    if not isinstance(body, str):
        return False
    stripped = body.strip()
    if stripped == "":
        return False

    lowered = stripped.lower()
    normalized = " ".join(lowered.split())
    first_line = _first_non_empty_line(lowered)
    if SUMMARY_HEADING_RE.match(first_line):
        return True

    if normalized in SUMMARY_EXACT_MATCHES:
        return True

    return any(signal in normalized for signal in SUMMARY_SIGNALS)


def _review_is_propel_summary_like(review: dict[str, Any]) -> bool:
    body = review.get("body")
    state = str(review.get("state") or "").strip().upper()
    if (body is None or (isinstance(body, str) and body.strip() == "")) and state in {"APPROVED", "COMMENTED"}:
        return True
    return looks_like_propel_summary_comment(body if isinstance(body, str) else None)


def build_addressable_payload(result: dict[str, Any]) -> dict[str, Any]:
    conversation_comments = result.get("conversation_comments") or []
    reviews = result.get("reviews") or []
    review_threads = result.get("review_threads") or []

    eligible_conversation_comments: list[dict[str, Any]] = []
    eligible_reviews: list[dict[str, Any]] = []
    eligible_review_threads: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for comment in conversation_comments:
        if not isinstance(comment, dict):
            continue
        login = _author_login(comment)
        if is_propel_author(login) and looks_like_propel_summary_comment(comment.get("body")):
            excluded.append(
                {
                    "source": "conversation_comment",
                    "id": comment.get("id"),
                    "author_login": login,
                    "reason": "propel_summary_like_comment",
                }
            )
            continue
        eligible_conversation_comments.append(comment)

    for review in reviews:
        if not isinstance(review, dict):
            continue
        login = _author_login(review)
        if is_propel_author(login) and _review_is_propel_summary_like(review):
            excluded.append(
                {
                    "source": "review",
                    "id": review.get("id"),
                    "author_login": login,
                    "reason": "propel_summary_like_comment",
                }
            )
            continue
        eligible_reviews.append(review)

    for thread in review_threads:
        if not isinstance(thread, dict):
            continue
        if thread.get("isResolved") is True:
            excluded.append(
                {
                    "source": "review_thread",
                    "id": thread.get("id"),
                    "reason": "resolved_review_thread",
                    "path": thread.get("path"),
                    "line": thread.get("line"),
                }
            )
            continue
        eligible_review_threads.append(thread)

    addressable_payload = {
        "filters": {
            "skip_resolved_review_threads": True,
            "skip_summary_like_propel_comments": True,
        },
        "conversation_comments": eligible_conversation_comments,
        "reviews": eligible_reviews,
        "review_threads": eligible_review_threads,
        "excluded": excluded,
        "counts": {
            "conversation_comments": len(eligible_conversation_comments),
            "reviews": len(eligible_reviews),
            "review_threads": len(eligible_review_threads),
            "excluded": len(excluded),
        },
    }
    pull_request = result.get("pull_request")
    if isinstance(pull_request, dict):
        addressable_payload["pull_request"] = pull_request
    return addressable_payload


def _ensure_gh_authenticated() -> None:
    try:
        run_cmd(["gh", "auth", "status"], timeout_seconds=COMMAND_TIMEOUT_SECONDS)
    except CommandError:
        print("run `gh auth login` to authenticate the GitHub CLI", file=sys.stderr)
        raise RuntimeError("gh auth status failed; run `gh auth login` to authenticate the GitHub CLI") from None


def gh_pr_view_json(fields: str) -> dict[str, Any]:
    # fields is a comma-separated list like: "number,headRepositoryOwner,headRepository"
    payload = run_json(
        ["gh", "pr", "view", "--json", fields],
        timeout_seconds=COMMAND_TIMEOUT_SECONDS,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected response from gh pr view")
    return payload


def get_current_pr_ref() -> tuple[str, str, int]:
    """
    Resolve the PR for the current branch (whatever gh considers associated).
    Works for fork-based PRs by parsing owner/repo from the PR URL (base repo).
    """
    pr = gh_pr_view_json("number,url")
    url = pr["url"]
    path_parts = urlparse(url).path.strip("/").split("/")
    if len(path_parts) < 4 or path_parts[2] != "pull":
        raise RuntimeError(f"Unexpected PR URL format: {url}")

    owner = path_parts[0]
    repo = path_parts[1]
    number = int(pr["number"])
    return owner, repo, number


def gh_api_graphql(
    owner: str,
    repo: str,
    number: int,
    comments_cursor: str | None = None,
    reviews_cursor: str | None = None,
    threads_cursor: str | None = None,
) -> dict[str, Any]:
    """
    Call `gh api graphql` using -F variables, avoiding JSON blobs with nulls.
    Query is passed via stdin using query=@- to avoid shell newline/quoting issues.
    """
    cmd = [
        "gh",
        "api",
        "graphql",
        "-F",
        "query=@-",
        "-F",
        f"owner={owner}",
        "-F",
        f"repo={repo}",
        "-F",
        f"number={number}",
    ]
    if comments_cursor:
        cmd += ["-F", f"commentsCursor={comments_cursor}"]
    if reviews_cursor:
        cmd += ["-F", f"reviewsCursor={reviews_cursor}"]
    if threads_cursor:
        cmd += ["-F", f"threadsCursor={threads_cursor}"]

    payload = run_json(cmd, stdin=QUERY, timeout_seconds=COMMAND_TIMEOUT_SECONDS)
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected response from gh api graphql")
    return payload


def fetch_all(owner: str, repo: str, number: int) -> dict[str, Any]:
    conversation_comments: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    review_threads: list[dict[str, Any]] = []

    comments_cursor: str | None = None
    reviews_cursor: str | None = None
    threads_cursor: str | None = None
    has_more_comments = True
    has_more_reviews = True
    has_more_threads = True

    pr_meta: dict[str, Any] | None = None

    while has_more_comments or has_more_reviews or has_more_threads:
        payload = gh_api_graphql(
            owner=owner,
            repo=repo,
            number=number,
            comments_cursor=comments_cursor,
            reviews_cursor=reviews_cursor,
            threads_cursor=threads_cursor,
        )

        if "errors" in payload and payload["errors"]:
            raise RuntimeError(f"GitHub GraphQL errors:\n{json.dumps(payload['errors'], indent=2)}")

        pr = payload["data"]["repository"]["pullRequest"]
        if pr_meta is None:
            pr_meta = {
                "number": pr["number"],
                "url": pr["url"],
                "title": pr["title"],
                "state": pr["state"],
                "owner": owner,
                "repo": repo,
            }

        if has_more_comments:
            c = pr["comments"]
            conversation_comments.extend(c.get("nodes") or [])
            comments_cursor = c["pageInfo"]["endCursor"]
            has_more_comments = c["pageInfo"]["hasNextPage"]

        if has_more_reviews:
            r = pr["reviews"]
            reviews.extend(r.get("nodes") or [])
            reviews_cursor = r["pageInfo"]["endCursor"]
            has_more_reviews = r["pageInfo"]["hasNextPage"]

        if has_more_threads:
            t = pr["reviewThreads"]
            review_threads.extend(t.get("nodes") or [])
            threads_cursor = t["pageInfo"]["endCursor"]
            has_more_threads = t["pageInfo"]["hasNextPage"]

    assert pr_meta is not None
    result = {
        "pull_request": pr_meta,
        "conversation_comments": conversation_comments,
        "reviews": reviews,
        "review_threads": review_threads,
    }
    result["addressable"] = build_addressable_payload(result)
    return result


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _ensure_gh_authenticated()
    owner, repo, number = get_current_pr_ref()
    result = fetch_all(owner, repo, number)
    output: dict[str, Any] = result["addressable"] if args.addressable_only else result
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
