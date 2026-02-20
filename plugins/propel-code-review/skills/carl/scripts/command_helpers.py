from __future__ import annotations

import json
import subprocess
from typing import Any

# NOTE: This helper is intentionally duplicated across standalone skills.
# If you update this file, mirror the same change in:
# plugins/propel-code-review/skills/propel-address-pr-comments/scripts/command_helpers.py


class CommandError(RuntimeError):
    """Command execution failed with a user-actionable message."""


def run_cmd(
    cmd: list[str],
    *,
    stdin: str | None = None,
    timeout_seconds: int = 120,
) -> str:
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"Command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(
            f"Command timed out after {timeout_seconds}s: {' '.join(cmd)}"
        ) from exc

    if proc.returncode != 0:
        raise CommandError(f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout


def run_json(
    cmd: list[str],
    *,
    stdin: str | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any] | list[Any]:
    out = run_cmd(cmd, stdin=stdin, timeout_seconds=timeout_seconds)
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise CommandError(f"Invalid JSON output from command: {' '.join(cmd)}") from exc
