"""Logging that never touches stdout.

Task 1 reserves stdout for JSON-RPC. Every task uses the same rule.
"""

import logging
import os
import sys

_CONFIGURED = False


def configure() -> None:
    """Attach a single stderr handler to the root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("FDE_LOG_LEVEL", "INFO").upper())
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure()
    return logging.getLogger(name)
