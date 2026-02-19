from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DependencySpec:
    name: str
    commands: tuple[list[str], ...]
    required: bool
    help_url: str


SPECS: tuple[DependencySpec, ...] = (
    DependencySpec(
        name="ffmpeg",
        commands=(["ffmpeg", "-version"],),
        required=True,
        help_url="https://ffmpeg.org/download.html",
    ),
    DependencySpec(
        name="ffprobe",
        commands=(["ffprobe", "-version"],),
        required=True,
        help_url="https://ffmpeg.org/download.html",
    ),
    DependencySpec(
        name="imagemagick",
        commands=(["magick", "-version"], ["convert", "-version"]),
        required=False,
        help_url="https://imagemagick.org/script/download.php",
    ),
)


def _run_version_command(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        return False, output or f"non-zero exit ({completed.returncode})"
    first_line = output.splitlines()[0] if output else ""
    return True, first_line


def _check_one(spec: DependencySpec) -> dict[str, Any]:
    env_hint = ""
    if spec.name == "imagemagick":
        env_hint = os.getenv("IMAGEMAGICK_BINARY", "")

    found_command = None
    detail = "not found"
    for command in spec.commands:
        executable = command[0]
        if shutil.which(executable) is None and executable != "convert":
            continue
        ok, message = _run_version_command(command)
        if ok:
            found_command = " ".join(command)
            detail = message
            break
        if message:
            detail = message

    found = found_command is not None
    status = "ok" if found else ("fail" if spec.required else "warn")
    return {
        "name": spec.name,
        "required": spec.required,
        "status": status,
        "found": found,
        "version": detail if found else None,
        "checked_commands": [" ".join(c) for c in spec.commands],
        "active_command": found_command,
        "env_hint": env_hint or None,
        "help_url": spec.help_url,
    }


def check_media_dependencies() -> dict[str, Any]:
    items = [_check_one(spec) for spec in SPECS]
    statuses = {item["status"] for item in items}
    if "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"
    else:
        overall = "ok"
    return {
        "overall": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "dependencies": items,
    }
