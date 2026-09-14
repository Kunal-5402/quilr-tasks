"""Keep stdout clean for JSON-RPC.

The stdio transport owns the real stdout. Anything that prints after the guard
is installed lands on stderr with a visible prefix, instead of corrupting the
protocol stream in silence.
"""

import sys
from typing import TextIO


class _StderrTee:
    """A minimal stdout replacement that redirects writes to stderr."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def write(self, text: str) -> int:
        if text.strip():
            sys.stderr.write(f"{self._prefix}{text}")
        return len(text)

    def flush(self) -> None:
        sys.stderr.flush()

    def isatty(self) -> bool:
        return False


def install() -> TextIO:
    """Replace sys.stdout and return the real stdout for the transport."""
    real_stdout = sys.stdout
    sys.stdout = _StderrTee(prefix="[stdout-leak] ")  # type: ignore[assignment]
    return real_stdout
