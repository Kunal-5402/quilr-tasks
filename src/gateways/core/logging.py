"""Logging that never touches stdout.

The MCP tool server reserves stdout for JSON-RPC. Every service keeps the same
rule, so a container log reads the same way for all of them.
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
    root.setLevel(os.getenv("GATEWAYS_LOG_LEVEL", "INFO").upper())
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure()
    return logging.getLogger(name)
