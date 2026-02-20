#!/usr/bin/env python3
"""
Fetch all PR conversation comments + reviews + review threads (inline threads)
for the PR associated with the current git branch, by shelling out to:

  gh api graphql

Requires:
  - `gh auth login` already set up
  - current branch has an associated (open) PR

Usage:
  python fetch_comments.py > pr_comments.json
"""

from __future__ import annotations

import json
import sys
from urllib.parse import urlparse
from typing import Any

from command_helpers import CommandError, run_cmd, run_json

COMMAND_TIMEOUT_SECONDS = 120

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
    return {
        "pull_request": pr_meta,
        "conversation_comments": conversation_comments,
        "reviews": reviews,
        "review_threads": review_threads,
    }


def main() -> None:
    _ensure_gh_authenticated()
    owner, repo, number = get_current_pr_ref()
    result = fetch_all(owner, repo, number)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
