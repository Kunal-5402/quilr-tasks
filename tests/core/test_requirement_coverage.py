"""Prove that every requirement in design/requirements.md has a test."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "design" / "requirements.md"
ID_PATTERN = re.compile(r"\bT\d-R\d+\b")


def _documented_ids() -> set[str]:
    return set(ID_PATTERN.findall(REQUIREMENTS.read_text()))


def _tested_ids() -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "tests").rglob("test_*.py"):
        found.update(ID_PATTERN.findall(path.read_text()))
    return found


def test_every_requirement_has_at_least_one_test():
    missing = sorted(_documented_ids() - _tested_ids())
    assert not missing, f"no test covers: {missing}"
