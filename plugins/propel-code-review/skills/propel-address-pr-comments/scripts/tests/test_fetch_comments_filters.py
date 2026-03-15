from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fetch_comments import (  # noqa: E402
    build_addressable_payload,
    is_propel_author,
    looks_like_propel_summary_comment,
)


def test_is_propel_author_heuristic():
    assert is_propel_author("propel-code-bot")
    assert is_propel_author("propel-ai")
    assert is_propel_author("PropelCodeBot")
    assert not is_propel_author("propelled_dev")
    assert not is_propel_author("im-propeller")
    assert not is_propel_author("octocat")
    assert not is_propel_author("")
    assert not is_propel_author(None)


def test_looks_like_propel_summary_comment_markers():
    assert looks_like_propel_summary_comment("### Summary\nOverall this PR looks good.")
    assert looks_like_propel_summary_comment("In summary, no blocking issues found.")
    assert looks_like_propel_summary_comment("<!-- carl-local-loop -->")
    assert looks_like_propel_summary_comment("LGTM")
    assert not looks_like_propel_summary_comment("LGTM, but add bounds check.")
    assert not looks_like_propel_summary_comment("Fix null pointer in parser. Otherwise LGTM.")
    assert not looks_like_propel_summary_comment("Handle null pointer in parser at line 42.")


def test_build_addressable_payload_filters_resolved_and_summary_like():
    payload = {
        "pull_request": {"number": 123, "url": "https://github.com/acme/repo/pull/123"},
        "conversation_comments": [
            {
                "id": "c1",
                "body": "### Summary\nOverall this PR looks good.",
                "author": {"login": "propel-ai"},
            },
            {
                "id": "c2",
                "body": "Please guard this call when user is None.",
                "author": {"login": "propel-ai"},
            },
            {
                "id": "c3",
                "body": "### Summary\nHuman note.",
                "author": {"login": "octocat"},
            },
        ],
        "reviews": [
            {"id": "r1", "state": "APPROVED", "body": "", "author": {"login": "propel-ai"}},
            {"id": "r2", "state": "COMMENTED", "body": "Add bounds check.", "author": {"login": "propel-ai"}},
            {"id": "r3", "state": "COMMENTED", "body": "LGTM", "author": {"login": "octocat"}},
            {"id": "r4", "state": "COMMENTED", "body": None, "author": {"login": "propel-ai"}},
            {
                "id": "r5",
                "state": "COMMENTED",
                "body": "LGTM, but add bounds check.",
                "author": {"login": "propel-ai"},
            },
        ],
        "review_threads": [
            {"id": "t1", "isResolved": True, "path": "src/a.py", "line": 7},
            {"id": "t2", "isResolved": False, "path": "src/b.py", "line": 11},
        ],
    }

    addressable = build_addressable_payload(payload)

    assert addressable["pull_request"]["number"] == 123
    assert [c["id"] for c in addressable["conversation_comments"]] == ["c2", "c3"]
    assert [r["id"] for r in addressable["reviews"]] == ["r2", "r3", "r5"]
    assert [t["id"] for t in addressable["review_threads"]] == ["t2"]

    excluded = addressable["excluded"]
    excluded_ids = {item["id"] for item in excluded}
    assert excluded_ids == {"c1", "r1", "r4", "t1"}
    assert addressable["counts"]["excluded"] == 4
