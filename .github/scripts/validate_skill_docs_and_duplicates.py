#!/usr/bin/env python3
"""Validate SKILL.md script references and duplicated helper consistency."""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path


SCRIPT_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9._/-])((?:\.\./|\.\/)?scripts/(?:[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)?/?)"
)

DUPLICATED_HELPER_GROUPS = (
    (
        Path("plugins/propel-code-review/skills/carl/scripts/command_helpers.py"),
        Path(
            "plugins/propel-code-review/skills/propel-address-pr-comments/scripts/command_helpers.py"
        ),
    ),
    (
        Path("plugins/propel/skills/carl/scripts/command_helpers.py"),
        Path("plugins/propel/skills/propel-address-pr-comments/scripts/command_helpers.py"),
    ),
    (
        Path("plugins/propel-code-review/skills/carl/SKILL.md"),
        Path("plugins/propel/skills/carl/SKILL.md"),
    ),
    (
        Path("plugins/propel-code-review/skills/carl/scripts/post_carl_summary_comment.py"),
        Path("plugins/propel/skills/carl/scripts/post_carl_summary_comment.py"),
    ),
    (
        Path(
            "plugins/propel-code-review/skills/carl/scripts/tests/test_post_carl_summary_comment.py"
        ),
        Path("plugins/propel/skills/carl/scripts/tests/test_post_carl_summary_comment.py"),
    ),
    (
        Path("plugins/propel-code-review/skills/propel-address-pr-comments/SKILL.md"),
        Path("plugins/propel/skills/propel-address-pr-comments/SKILL.md"),
    ),
    (
        Path(
            "plugins/propel-code-review/skills/propel-address-pr-comments/scripts/fetch_comments.py"
        ),
        Path("plugins/propel/skills/propel-address-pr-comments/scripts/fetch_comments.py"),
    ),
    (
        Path(
            "plugins/propel-code-review/skills/propel-address-pr-comments/scripts/tests/test_fetch_comments_filters.py"
        ),
        Path("plugins/propel/skills/propel-address-pr-comments/scripts/tests/test_fetch_comments_filters.py"),
    ),
    (
        Path("plugins/propel-code-review/skills/propel-code-review/scripts/create_review.sh"),
        Path("plugins/propel/skills/propel-code-review/scripts/create_review.sh"),
    ),
    (
        Path("plugins/propel-code-review/skills/propel-code-review/scripts/poll_review.sh"),
        Path("plugins/propel/skills/propel-code-review/scripts/poll_review.sh"),
    ),
    (
        Path(
            "plugins/propel-code-review/skills/propel-code-review/scripts/post_comment_feedback.sh"
        ),
        Path("plugins/propel/skills/propel-code-review/scripts/post_comment_feedback.sh"),
    ),
    (
        Path(
            "plugins/propel-code-review/skills/propel-code-review/scripts/smoke_test_permissions.sh"
        ),
        Path("plugins/propel/skills/propel-code-review/scripts/smoke_test_permissions.sh"),
    ),
    (
        Path(
            "plugins/propel-code-review/skills/propel-code-review/scripts/test_poll_status_parsing.sh"
        ),
        Path("plugins/propel/skills/propel-code-review/scripts/test_poll_status_parsing.sh"),
    ),
)


def _script_references(skill_doc: Path) -> list[str]:
    content = skill_doc.read_text(encoding="utf-8")
    refs = {match.group(1) for match in SCRIPT_REFERENCE_RE.finditer(content)}
    return sorted(refs)


def _validate_skill_script_references(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for skill_doc in sorted(repo_root.glob("plugins/**/SKILL.md")):
        skill_dir = skill_doc.parent
        rel_skill_doc = skill_doc.relative_to(repo_root)
        refs = _script_references(skill_doc)

        for ref in refs:
            resolved = (skill_dir / ref).resolve()
            try:
                resolved.relative_to(repo_root)
            except ValueError:
                errors.append(
                    f"{rel_skill_doc}: script reference escapes repository root ({ref})"
                )
                continue

            if not resolved.exists():
                errors.append(
                    f"{rel_skill_doc}: missing referenced script path {ref} "
                    f"(resolved to {resolved.relative_to(repo_root)})"
                )
                continue

            is_ref_directory = ref.endswith("/")
            if is_ref_directory and not resolved.is_dir():
                errors.append(f"{rel_skill_doc}: expected directory for reference {ref}")
                continue
            if not is_ref_directory and resolved.is_dir():
                errors.append(
                    f"{rel_skill_doc}: expected file reference but found directory ({ref})"
                )
                continue

            if resolved.is_file() and "scripts" in resolved.parts:
                if resolved.stat().st_mode & 0o111 == 0:
                    errors.append(
                        f"{rel_skill_doc}: referenced script file is not executable "
                        f"({resolved.relative_to(repo_root)})"
                    )

    return errors


def _validate_duplicated_helpers(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for group in DUPLICATED_HELPER_GROUPS:
        abs_paths = [repo_root / rel for rel in group]
        missing = [path for path in abs_paths if not path.exists()]
        if missing:
            for path in missing:
                errors.append(f"Missing duplicated helper file: {path.relative_to(repo_root)}")
            continue

        baseline = abs_paths[0].read_text(encoding="utf-8")
        baseline_rel = abs_paths[0].relative_to(repo_root)
        for other in abs_paths[1:]:
            other_content = other.read_text(encoding="utf-8")
            if other_content == baseline:
                continue

            other_rel = other.relative_to(repo_root)
            diff = list(
                difflib.unified_diff(
                    baseline.splitlines(),
                    other_content.splitlines(),
                    fromfile=str(baseline_rel),
                    tofile=str(other_rel),
                    lineterm="",
                )
            )
            preview = "\n".join(diff[:20])
            errors.append(
                "Duplicated helper drift detected between "
                f"{baseline_rel} and {other_rel}.\n{preview}"
            )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = [
        *_validate_skill_script_references(repo_root),
        *_validate_duplicated_helpers(repo_root),
    ]

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("SKILL script references and duplicated helpers validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
