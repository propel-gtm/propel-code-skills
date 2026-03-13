#!/usr/bin/env python3
"""Validate SKILL.md frontmatter for all skills in this repository."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


RE_FRONTMATTER = re.compile(r"^---\n(.*?)\n---(?:\n|$)", re.DOTALL)
RE_FRONTMATTER_LINE = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$")


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
        parsed: dict[str, str] = {}
        for raw_line in frontmatter.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            line_match = RE_FRONTMATTER_LINE.match(line)
            if line_match is None:
                errors.append(
                    f"{rel_path}: frontmatter must use single-line `key: value` entries "
                    "to match this repository's validation convention"
                )
                continue

            key, value = line_match.groups()
            parsed[key] = value.strip()

        for required in ("name", "description"):
            if not parsed.get(required):
                errors.append(f"{rel_path}: missing `{required}` in frontmatter")

        metadata = parsed.get("metadata")
        if metadata:
            try:
                metadata_value = json.loads(metadata)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel_path}: `metadata` must be valid single-line JSON ({exc})")
            else:
                if not isinstance(metadata_value, dict):
                    errors.append(f"{rel_path}: `metadata` JSON must decode to an object")
                else:
                    for namespace in ("clawdbot", "openclaw", "clawdis"):
                        runtime_metadata = metadata_value.get(namespace)
                        if runtime_metadata is None:
                            continue
                        if not isinstance(runtime_metadata, dict):
                            errors.append(
                                f"{rel_path}: `metadata.{namespace}` must decode to an object"
                            )
                            continue
                        homepage = runtime_metadata.get("homepage")
                        if homepage is not None and not (
                            isinstance(homepage, str)
                            and homepage.startswith(("http://", "https://"))
                        ):
                            errors.append(
                                f"{rel_path}: `metadata.{namespace}.homepage` must be an "
                                "absolute http(s) URL"
                            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated frontmatter for {len(skill_files)} SKILL.md files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
