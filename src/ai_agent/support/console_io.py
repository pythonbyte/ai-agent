"""Console I/O helpers — aioconsole leaves stdout non-blocking on macOS."""

from __future__ import annotations

import fcntl
import os
import sys
from typing import Any, TextIO


def restore_blocking_stdio() -> None:
    """
    Clear O_NONBLOCK on stdin/stdout/stderr.

    ``aioconsole.ainput`` sets stdout non-blocking; a subsequent large
    ``print`` can raise ``BlockingIOError: [Errno 35]``.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            fd = stream.fileno()
        except (AttributeError, OSError, ValueError):
            continue
        try:
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        except OSError:
            continue
        if flags & os.O_NONBLOCK:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)


def console_print(*args: Any, file: TextIO | None = None, **kwargs: Any) -> None:
    """Print after restoring blocking stdio (safe after ``ainput``)."""
    restore_blocking_stdio()
    kwargs.setdefault("flush", True)
    print(*args, file=file, **kwargs)
