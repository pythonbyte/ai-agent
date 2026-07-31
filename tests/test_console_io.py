"""Tests for console I/O helpers."""

from __future__ import annotations

import fcntl
import os
import sys

import pytest

from ai_agent.console_io import console_print, restore_blocking_stdio


def test_restore_blocking_stdio_is_noop_safe() -> None:
    restore_blocking_stdio()  # must not raise even under pytest capture


def test_console_print_writes(capsys: pytest.CaptureFixture[str]) -> None:
    console_print("hello-operator")
    captured = capsys.readouterr()
    assert "hello-operator" in captured.out


def test_restore_clears_nonblock_when_possible() -> None:
    """If stdout is a real tty fd, clearing O_NONBLOCK must succeed."""
    try:
        fd = sys.stdout.fileno()
    except (OSError, ValueError):
        return
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    except OSError:
        return
    restore_blocking_stdio()
    new_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    assert not (new_flags & os.O_NONBLOCK)
