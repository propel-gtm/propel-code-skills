#!/usr/bin/env python3
"""Validate marketplace and plugin metadata files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON ({exc})") from exc


def _require_keys(obj: dict[str, Any], keys: tuple[str, ...], path: Path) -> list[str]:
    errors: list[str] = []
    for key in keys:
        if key not in obj:
            errors.append(f"{path}: missing required key `{key}`")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors: list[str] = []

    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        errors.append(f"{marketplace_path}: file does not exist")
    else:
        marketplace = _load_json(marketplace_path)
        if not isinstance(marketplace, dict):
            errors.append(f"{marketplace_path}: top-level JSON must be an object")
            marketplace = {}

        errors.extend(_require_keys(marketplace, ("name", "plugins"), marketplace_path))
        plugins = marketplace.get("plugins", [])
        if not isinstance(plugins, list) or not plugins:
            errors.append(f"{marketplace_path}: `plugins` must be a non-empty array")
            plugins = []

        for idx, plugin in enumerate(plugins):
            label = f"{marketplace_path} plugins[{idx}]"
            if not isinstance(plugin, dict):
                errors.append(f"{label}: item must be an object")
                continue

            missing = _require_keys(
                plugin, ("name", "source", "description", "version"), marketplace_path
            )
            for err in missing:
                errors.append(f"{label}: {err.split(': ', 1)[1]}")
            if missing:
                continue

            source = plugin["source"]
            if not isinstance(source, str):
                errors.append(f"{label}: `source` must be a string")
                continue

            plugin_root = repo_root / source
            if not plugin_root.exists():
                errors.append(f"{label}: source path does not exist ({source})")
                continue

            plugin_manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
            if not plugin_manifest_path.exists():
                errors.append(
                    f"{label}: missing plugin manifest ({plugin_manifest_path.relative_to(repo_root)})"
                )
                continue

            plugin_manifest = _load_json(plugin_manifest_path)
            if not isinstance(plugin_manifest, dict):
                errors.append(f"{plugin_manifest_path}: top-level JSON must be an object")
                continue

            errors.extend(
                _require_keys(
                    plugin_manifest,
                    ("name", "description", "version", "skills"),
                    plugin_manifest_path,
                )
            )

            if plugin_manifest.get("name") != plugin.get("name"):
                errors.append(
                    f"{plugin_manifest_path}: `name` ({plugin_manifest.get('name')}) "
                    f"does not match marketplace entry ({plugin.get('name')})"
                )

            skills = plugin_manifest.get("skills", [])
            if not isinstance(skills, list) or not skills:
                errors.append(f"{plugin_manifest_path}: `skills` must be a non-empty array")
                continue

            for skill_path in skills:
                if not isinstance(skill_path, str):
                    errors.append(f"{plugin_manifest_path}: each `skills` item must be a string")
                    continue

                skill_root = plugin_root / skill_path
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
