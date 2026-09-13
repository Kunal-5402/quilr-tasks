import io
import sys

import pytest

from fde.task1_mcp_server import stdout_guard


@pytest.mark.req("T1-R7", "T1-R8")
def test_a_stray_print_goes_to_stderr(monkeypatch):
    fake_stdout, fake_stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    real_stdout = stdout_guard.install()
    print("a debug line from a dependency")

    assert real_stdout is fake_stdout
    assert fake_stdout.getvalue() == ""
    assert "[stdout-leak] a debug line from a dependency" in fake_stderr.getvalue()
