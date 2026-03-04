#!/usr/bin/env python3
"""Validate README install instructions and skill listing against metadata."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from metadata_common import load_json, resolve_relative_path


RE_CODE_BLOCK = re.compile(r"```[^\n]*\n(?P<body>.*?)\n```", re.DOTALL)
RE_SKILL_INSTALLER = re.compile(r"^\$skill-installer\s+(?P<slug>\S+)\s*$")
RE_SKILL_BULLET = re.compile(r"^- `(?P<name>[^`]+)`:")


def _extract_h3_section(markdown: str, heading: str) -> str | None:
    match = re.search(rf"^### {re.escape(heading)}\s*$", markdown, re.MULTILINE)
    if match is None:
        return None

    start = match.end()
    next_match = re.search(r"^### .+\s*$", markdown[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(markdown)
    return markdown[start:end]


def _extract_first_code_block_lines(section: str) -> list[str] | None:
    match = RE_CODE_BLOCK.search(section)
    if match is None:
        return None
    return [line.strip() for line in match.group("body").splitlines() if line.strip()]


def _extract_shipped_skill_bullets(readme: str) -> list[str] | None:
    marker = "This repo ships these skills:"
    idx = readme.find(marker)
    if idx == -1:
        return None

    lines = readme[idx + len(marker) :].splitlines()
    bullets: list[str] = []
    in_bullet_block = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if in_bullet_block:
                break
            continue

        if line.startswith("- "):
            in_bullet_block = True
            match = RE_SKILL_BULLET.match(line)
            if match is None:
                return []
            bullets.append(match.group("name"))
            continue

        if in_bullet_block:
            break

    return bullets if bullets else None


def _read_expected_plugin_and_skill_names(
    repo_root: Path,
) -> tuple[str | None, list[str], list[str], list[str]]:
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    errors: list[str] = []

    if not marketplace_path.exists():
        return None, [], [], [f"{marketplace_path}: file does not exist"]

    try:
        marketplace = load_json(marketplace_path)
    except ValueError as exc:
        return None, [], [], [str(exc)]

    if not isinstance(marketplace, dict):
        return None, [], [], [f"{marketplace_path}: top-level JSON must be an object"]

    marketplace_name = marketplace.get("name")
    if not isinstance(marketplace_name, str) or not marketplace_name:
        errors.append(f"{marketplace_path}: missing or invalid `name`")
        marketplace_name = None

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(f"{marketplace_path}: missing or invalid `plugins` array")
        return marketplace_name, [], [], errors

    plugin_names: list[str] = []
    skill_names: list[str] = []

    for idx, plugin in enumerate(plugins):
        label = f"{marketplace_path} plugins[{idx}]"
        if not isinstance(plugin, dict):
            errors.append(f"{label}: item must be an object")
            continue

        plugin_name = plugin.get("name")
        if not isinstance(plugin_name, str) or not plugin_name:
            errors.append(f"{label}: missing or invalid `name`")
            continue
        plugin_names.append(plugin_name)

        source = plugin.get("source")
        if not isinstance(source, str):
            errors.append(f"{label}: missing or invalid `source`")
            continue

        plugin_root = resolve_relative_path(repo_root, source)
        if plugin_root is None:
            errors.append(
                f"{label}: source path must be repo-relative and not escape repo ({source})"
            )
            continue

        plugin_manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
        if not plugin_manifest_path.exists():
            errors.append(
                f"{label}: missing plugin manifest ({plugin_manifest_path.relative_to(repo_root)})"
            )
            continue

        try:
            plugin_manifest = load_json(plugin_manifest_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        if not isinstance(plugin_manifest, dict):
            errors.append(f"{plugin_manifest_path}: top-level JSON must be an object")
            continue

        skills = plugin_manifest.get("skills")
        if not isinstance(skills, list) or not skills:
            errors.append(f"{plugin_manifest_path}: missing or invalid `skills` array")
            continue

        for skill_path in skills:
            if not isinstance(skill_path, str):
                errors.append(f"{plugin_manifest_path}: each `skills` item must be a string")
                continue

            skill_root = resolve_relative_path(plugin_root, skill_path)
            if skill_root is None:
                errors.append(
                    f"{plugin_manifest_path}: invalid skill path (escapes plugin root): "
                    f"{skill_path}"
                )
                continue

            skill_name = skill_root.name
            if not skill_name:
                errors.append(
                    f"{plugin_manifest_path}: invalid skill path name for {skill_path}"
                )
                continue

            if skill_name not in skill_names:
                skill_names.append(skill_name)

    return marketplace_name, plugin_names, skill_names, errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    readme_path = repo_root / "README.md"
    errors: list[str] = []

    if not readme_path.exists():
        print(f"ERROR: {readme_path}: file does not exist", file=sys.stderr)
        return 1

    readme = readme_path.read_text(encoding="utf-8")

    marketplace_name, plugin_names, expected_skill_names, metadata_errors = (
        _read_expected_plugin_and_skill_names(repo_root)
    )
    errors.extend(metadata_errors)

    readme_skills = _extract_shipped_skill_bullets(readme)
    if readme_skills is None:
        errors.append("README.md: missing 'This repo ships these skills' bullet list")
    elif readme_skills == []:
        errors.append("README.md: malformed bullet list under 'This repo ships these skills'")
    elif expected_skill_names and readme_skills != expected_skill_names:
        errors.append(
            "README.md: skill bullets are out of sync with plugin metadata "
            f"(expected {expected_skill_names}, found {readme_skills})"
        )

    codex_section = _extract_h3_section(readme, "Codex")
    marketplace_repo_slug: str | None = None
    if codex_section is None:
        errors.append("README.md: missing `### Codex` section")
    else:
        codex_lines = _extract_first_code_block_lines(codex_section)
        if not codex_lines:
            errors.append("README.md: missing command block under `### Codex`")
        elif len(codex_lines) != 1:
            errors.append(
                "README.md: Codex install block must contain exactly one command line"
            )
        else:
            codex_match = RE_SKILL_INSTALLER.match(codex_lines[0])
            if codex_match is None:
                errors.append(
                    "README.md: Codex install command must match "
                    "`$skill-installer <owner>/<repo>`"
                )
            else:
                marketplace_repo_slug = codex_match.group("slug")

    claude_section = _extract_h3_section(readme, "Claude Code")
    if claude_section is None:
        errors.append("README.md: missing `### Claude Code` section")
    else:
        claude_lines = _extract_first_code_block_lines(claude_section)
        if not claude_lines:
            errors.append("README.md: missing command block under `### Claude Code`")
        elif (
            marketplace_repo_slug is not None
            and marketplace_name is not None
            and plugin_names
        ):
            expected_claude_lines = [
                f"/plugin marketplace add {marketplace_repo_slug}",
                *[
                    f"/plugin install {plugin_name}@{marketplace_name}"
                    for plugin_name in plugin_names
                ],
            ]
            if claude_lines != expected_claude_lines:
                errors.append(
                    "README.md: Claude install commands are out of sync.\n"
                    f"Expected: {expected_claude_lines}\n"
                    f"Found:    {claude_lines}"
                )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("README install instruction validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
