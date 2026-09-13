"""Drive the MCP server over stdio and print stdout and stderr apart."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SESSION = [
    ("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "demo", "version": "1"}}),
    ("tools/list", None),
    ("tools/call", {"name": "get_customer_record", "arguments": {"customer_id": "CUST-A1B2C"}}),
    ("tools/call", {"name": "get_customer_record", "arguments": {"customer_id": "bad-id"}}),
    ("tools/call", {"name": "trigger_refund",
                    "arguments": {"customer_id": "CUST-A1B2C", "amount": -1, "reason": "short"}}),
    ("tools/call", {"name": "admin_wipe", "arguments": {}}),
]


def main() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "fde.task1_mcp_server"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    stdout_lines = []

    for index, (method, params) in enumerate(SESSION):
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": index, "method": method,
                                        "params": params}) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        stdout_lines.append(line)

        answer = json.loads(line)
        label = params.get("name") if params and "name" in params else method
        if "error" in answer:
            print(f"  {label:<22} -> error {answer['error']['code']}: {answer['error']['message']}")
        else:
            print(f"  {label:<22} -> ok")

        if method == "initialize":
            process.stdin.write(json.dumps({"jsonrpc": "2.0",
                                            "method": "notifications/initialized"}) + "\n")
            process.stdin.flush()

    process.stdin.close()
    stderr = process.stderr.read()
    process.wait()

    print("\n  stdout check: every line is JSON-RPC")
    for line in stdout_lines:
        assert json.loads(line)["jsonrpc"] == "2.0"
    print(f"  {len(stdout_lines)} lines checked, all valid")
    print("\n  stderr (logs only):")
    for line in stderr.strip().splitlines()[:4]:
        print(f"    {line}")


if __name__ == "__main__":
    main()
