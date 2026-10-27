"""Shared helpers for the red record and red check tests."""

import sys
from pathlib import Path

from tests.gitfixture import GitFixture

PLAN = """# Plan

### Task 1: Add

**Acceptance criteria:** AC-1, AC-2

**Tests:** `test_a`, `test_b`
"""

TWO_TESTS = '''def test_a():
    assert 1 == 2


def test_b():
    assert 2 == 3
'''

TEST_FILE = "tests/test_x.py"


def runner_script(
    repo: Path, body: str, test_file: str = TEST_FILE, test_id: str = "test_x"
) -> list[str]:
    """Write a POSIX sh script that ignores its argument. The argument is the selector."""
    (repo / "run-tests.sh").write_text(body + "\n", encoding="utf-8")
    return ["sh", "run-tests.sh", f"{test_file}::{test_id}"]


def pytest_command(test_id: str, test_file: str = TEST_FILE) -> list[str]:
    return [sys.executable, "-m", "pytest", f"{test_file}::{test_id}"]


def make_repo(git_repo: GitFixture, test_text: str = TWO_TESTS, plan: str = PLAN) -> Path:
    git_repo.write(TEST_FILE, test_text)
    git_repo.write("plan.md", plan)
    git_repo.commit_all("initial")
    return git_repo.path
