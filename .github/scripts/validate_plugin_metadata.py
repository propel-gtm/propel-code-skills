#!/usr/bin/env python3
"""Validate marketplace and plugin metadata files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from metadata_common import load_json, resolve_relative_path

def _missing_keys(obj: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in obj]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors: list[str] = []

    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        errors.append(f"{marketplace_path}: file does not exist")
    else:
        try:
            marketplace = load_json(marketplace_path)
        except ValueError as exc:
            errors.append(str(exc))
            marketplace = {}

        if not isinstance(marketplace, dict):
            errors.append(f"{marketplace_path}: top-level JSON must be an object")
            marketplace = {}

        for key in _missing_keys(marketplace, ("name", "plugins")):
            errors.append(f"{marketplace_path}: missing required key `{key}`")
        plugins = marketplace.get("plugins", [])
        if not isinstance(plugins, list) or not plugins:
            errors.append(f"{marketplace_path}: `plugins` must be a non-empty array")
            plugins = []

        for idx, plugin in enumerate(plugins):
            label = f"{marketplace_path} plugins[{idx}]"
            if not isinstance(plugin, dict):
                errors.append(f"{label}: item must be an object")
                continue

            missing = _missing_keys(plugin, ("name", "source", "description", "version"))
            for key in missing:
                errors.append(f"{label}: missing required key `{key}`")
            if missing:
                continue

            source = plugin["source"]
            if not isinstance(source, str):
                errors.append(f"{label}: `source` must be a string")
                continue

            plugin_root = resolve_relative_path(repo_root, source)
            if plugin_root is None:
                errors.append(
                    f"{label}: source path must be repository-relative and not escape repo ({source})"
                )
                continue

            if not plugin_root.exists():
                errors.append(f"{label}: source path does not exist ({source})")
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

            for key in _missing_keys(
                plugin_manifest, ("name", "description", "version", "skills")
            ):
                errors.append(f"{plugin_manifest_path}: missing required key `{key}`")

            if plugin_manifest.get("name") != plugin.get("name"):
                errors.append(
                    f"{plugin_manifest_path}: `name` ({plugin_manifest.get('name')}) "
                    f"does not match marketplace entry ({plugin.get('name')})"
                )
            if plugin_manifest.get("description") != plugin.get("description"):
                errors.append(
                    f"{plugin_manifest_path}: `description` does not match marketplace entry"
                )
            if plugin_manifest.get("version") != plugin.get("version"):
                errors.append(
                    f"{plugin_manifest_path}: `version` ({plugin_manifest.get('version')}) "
                    f"does not match marketplace entry ({plugin.get('version')})"
                )

            skills = plugin_manifest.get("skills", [])
            if not isinstance(skills, list) or not skills:
                errors.append(f"{plugin_manifest_path}: `skills` must be a non-empty array")
                continue

            for skill_path in skills:
                if not isinstance(skill_path, str):
                    errors.append(f"{plugin_manifest_path}: each `skills` item must be a string")
                    continue

                skill_root = resolve_relative_path(plugin_root, skill_path)
                if skill_root is None:
                    errors.append(
                        f"{plugin_manifest_path}: skill path must be plugin-relative and not "
                        f"escape plugin root ({skill_path})"
                    )
                    continue

                if not skill_root.exists():
                    errors.append(
                        f"{plugin_manifest_path}: skill path does not exist ({skill_path})"
                    )
                    continue

                skill_doc = skill_root / "SKILL.md"
                if not skill_doc.exists():
                    errors.append(
                        f"{plugin_manifest_path}: missing SKILL.md at "
                        f"{skill_doc.relative_to(repo_root)}"
                    )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Marketplace and plugin metadata validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
