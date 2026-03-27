"""Runtime support tests."""

from __future__ import annotations

import io

import pytest

from core.runtime import (
    build_python_version_error,
    enforce_supported_python,
    format_python_version,
    is_supported_python,
)


def test_format_python_version():
    assert format_python_version((3, 11, 7)) == "3.11.7"


def test_is_supported_python():
    assert is_supported_python((3, 11, 0)) is True
    assert is_supported_python((3, 12, 1)) is True
    assert is_supported_python((3, 10, 14)) is False


def test_build_python_version_error():
    message = build_python_version_error((3, 10, 14))
    assert "Python 3.11 or newer" in message
    assert "3.10.14" in message


def test_enforce_supported_python_raises_for_old_runtime():
    stream = io.StringIO()

    with pytest.raises(SystemExit):
        enforce_supported_python((3, 10, 14), stream=stream)

    assert "Current interpreter: 3.10.14." in stream.getvalue()
