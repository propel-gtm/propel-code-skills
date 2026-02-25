#!/usr/bin/env python3
"""Validate SKILL.md frontmatter for all skills in this repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path


RE_FRONTMATTER = re.compile(r"^---\n(.*?)\n---(?:\n|$)", re.DOTALL)
RE_KEY = re.compile(r"^([A-Za-z0-9_-]+)\s*:", re.MULTILINE)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    skill_files = sorted(repo_root.glob("plugins/**/SKILL.md"))

    if not skill_files:
        print("ERROR: no SKILL.md files found under plugins/", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in skill_files:
        rel_path = path.relative_to(repo_root)
        content = path.read_text(encoding="utf-8")
        match = RE_FRONTMATTER.match(content)
        if not match:
            errors.append(f"{rel_path}: missing or malformed YAML frontmatter block")
            continue

        frontmatter = match.group(1)
        keys = set(RE_KEY.findall(frontmatter))

        for required in ("name", "description"):
            if required not in keys:
                errors.append(f"{rel_path}: missing `{required}` in frontmatter")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated frontmatter for {len(skill_files)} SKILL.md files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
