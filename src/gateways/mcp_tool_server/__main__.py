"""Entry point. The guard is installed before anything else can print."""

from io import TextIOWrapper

import anyio

from gateways.mcp_tool_server import stdout_guard

REAL_STDOUT = stdout_guard.install()

from mcp.server.stdio import stdio_server  # noqa: E402

from gateways.core.logging import get_logger  # noqa: E402
from gateways.mcp_tool_server.server import build_server  # noqa: E402

log = get_logger(__name__)


async def main() -> None:
    server = build_server()
    log.info("mcp server starting on stdio")
    transport_stdout = anyio.wrap_file(TextIOWrapper(REAL_STDOUT.buffer, encoding="utf-8"))
    async with stdio_server(stdout=transport_stdout) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
