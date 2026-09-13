import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class ServerSession:
    """Drives the server over real pipes and keeps stdin open until every reply arrives."""

    def __init__(self) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-m", "fde.task1_mcp_server"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
        )
        self.stdout_lines: list[str] = []
        self._send(INITIALIZE)
        self._read()
        self._send(INITIALIZED)

    def _send(self, message: dict) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def _read(self) -> dict:
        assert self.process.stdout is not None
        line = self.process.stdout.readline()
        assert line, "the server closed stdout"
        self.stdout_lines.append(line)
        return json.loads(line)

    def request(self, method: str, params: dict | None = None, request_id: int = 1) -> dict:
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        return self._read()

    def call_tool(self, name: str, arguments: dict, request_id: int = 1) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments}, request_id)

    def close(self) -> tuple[list[str], str]:
        assert self.process.stdin is not None
        self.process.stdin.close()
        stderr = self.process.stderr.read() if self.process.stderr else ""
        self.process.wait(timeout=10)
        return self.stdout_lines, stderr


@pytest.fixture
def session():
    server = ServerSession()
    yield server
    server.close()
