"""Runtime helpers for Python version support."""

from __future__ import annotations

import sys
from typing import Optional, Sequence, TextIO, Tuple


MINIMUM_PYTHON: Tuple[int, int] = (3, 11)


def _normalize_version(version_info: Optional[Sequence[int]] = None) -> Tuple[int, int, int]:
    info = version_info or sys.version_info
    parts = list(info[:3])
    while len(parts) < 3:
        parts.append(0)
    return int(parts[0]), int(parts[1]), int(parts[2])


def format_python_version(version_info: Optional[Sequence[int]] = None) -> str:
    major, minor, patch = _normalize_version(version_info)
    return "{}.{}.{}".format(major, minor, patch)


def is_supported_python(version_info: Optional[Sequence[int]] = None) -> bool:
    major, minor, _ = _normalize_version(version_info)
    return (major, minor) >= MINIMUM_PYTHON


def build_python_version_error(version_info: Optional[Sequence[int]] = None) -> str:
    current = format_python_version(version_info)
    required = "{}.{}".format(*MINIMUM_PYTHON)
    return (
        "AgentPent requires Python {} or newer. "
        "Current interpreter: {}.".format(required, current)
    )


def enforce_supported_python(
    version_info: Optional[Sequence[int]] = None,
    stream: Optional[TextIO] = None,
) -> None:
    if is_supported_python(version_info):
        return

    target = stream or sys.stderr
    target.write(build_python_version_error(version_info) + "\n")
    raise SystemExit(1)
