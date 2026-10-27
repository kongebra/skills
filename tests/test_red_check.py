import json
from pathlib import Path

import pytest

from kcommon import red_check, red_record
from kcommon.red_check import CheckEntry
from kcommon.red_record import slug
from tests.red_helpers import PLAN, TEST_FILE, TWO_TESTS, make_repo, pytest_command

WORK = "W-1"


def record_test(repo, test_id, monkeypatch):
    monkeypatch.chdir(repo)
    code = red_record.main(
        ["--work-item", WORK, "--test-id", test_id, "--test-file", TEST_FILE,
         "--plan", "plan.md", "--", *pytest_command(test_id)]
    )
    assert code == 0


def run_check(repo):
    report = red_check.check(WORK, Path("spec.md"), Path("plan.md"), repo)
    return {e.test_id: e for e in report.entries}


def write_record(repo, test_id, **fields):
    data = {
        "work_item": WORK, "acs": [], "test_id": test_id, "test_file": TEST_FILE,
        "test_block_sha256": "0" * 64, "test_block_lines": [1, 2], "command": [],
        "exit_code": 1, "category": "red", "output_head": "", "output_tail": "",
        "output_truncated": False, "head_at_record": "x", "recorded_at": "x",
    }
    data.update(fields)
    path = repo / ".agent-work" / WORK / "evidence" / f"red-{slug(test_id)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_two_tests_one_file_both_pass(git_repo, monkeypatch):
    repo = make_repo(git_repo)
    record_test(repo, "test_a", monkeypatch)
    record_test(repo, "test_b", monkeypatch)
    entries = run_check(repo)
    assert list(entries) == ["test_a", "test_b"]
    assert entries["test_a"] == CheckEntry("test_a", ("AC-1", "AC-2"), "pass", "ok")
    assert entries["test_b"].status == "pass"


def test_edit_first_test_fails_only_first(git_repo, monkeypatch):
    repo = make_repo(git_repo)
    record_test(repo, "test_a", monkeypatch)
    record_test(repo, "test_b", monkeypatch)
    path = repo / TEST_FILE
    path.write_text(path.read_text().replace("1 == 2", "1 == 1"))
    entries = run_check(repo)
    assert entries["test_a"].status == "fail"
    assert entries["test_a"].reason == "test changed after the red record"
    assert entries["test_b"].status == "pass"


def test_check_missing_record_fails(git_repo):
    repo = make_repo(git_repo)
    entries = run_check(repo)
    assert entries["test_a"].status == "fail"
    assert entries["test_a"].reason == "no red record"


def test_check_exit_code_zero_fails(git_repo):
    repo = make_repo(git_repo)
    write_record(repo, "test_a", exit_code=0)
    assert run_check(repo)["test_a"] == CheckEntry(
        "test_a", ("AC-1", "AC-2"), "fail", "record shows exit code 0"
    )


def test_check_missing_symbol_needs_review(git_repo):
    repo = make_repo(git_repo)
    write_record(repo, "test_a", category="missing-symbol")
    entry = run_check(repo)["test_a"]
    assert (entry.status, entry.reason) == ("needs-review", "missing symbol, reviewer decides")


def test_check_no_run_needs_review(git_repo):
    repo = make_repo(git_repo)
    write_record(repo, "test_a", category="no-run")
    entry = run_check(repo)["test_a"]
    assert (entry.status, entry.reason) == (
        "needs-review", "run did not reach the test, reviewer decides"
    )


def test_check_syntax_fails(git_repo):
    repo = make_repo(git_repo)
    write_record(repo, "test_a", category="syntax")
    entry = run_check(repo)["test_a"]
    assert (entry.status, entry.reason) == ("fail", "category is syntax")


def test_check_unknown_category_fails(git_repo):
    repo = make_repo(git_repo)
    write_record(repo, "test_a", category="assertion")
    entry = run_check(repo)["test_a"]
    assert (entry.status, entry.reason) == ("fail", "category is assertion")


def test_check_duplicate_test_id_fails(git_repo, monkeypatch):
    repo = make_repo(git_repo)
    record_test(repo, "test_a", monkeypatch)
    path = repo / TEST_FILE
    path.write_text(path.read_text() + "\n\ndef test_a():\n    pass\n")
    entry = run_check(repo)["test_a"]
    assert (entry.status, entry.reason) == ("fail", "duplicate test id")


def test_check_block_not_found_needs_review(git_repo, monkeypatch):
    repo = make_repo(git_repo)
    record_test(repo, "test_a", monkeypatch)
    path = repo / TEST_FILE
    path.write_text(path.read_text().replace("def test_a", "def test_renamed"))
    entry = run_check(repo)["test_a"]
    assert (entry.status, entry.reason) == ("needs-review", "test block not found")


def test_check_null_hash_needs_review(git_repo):
    repo = make_repo(git_repo)
    write_record(repo, "test_a", test_block_sha256=None, test_block_lines=None)
    assert run_check(repo)["test_a"].reason == "test block not found"


def test_check_missing_test_file_needs_review(git_repo):
    repo = make_repo(git_repo)
    write_record(repo, "test_a", test_file="tests/gone.py")
    assert run_check(repo)["test_a"].status == "needs-review"


def test_check_unreadable_record_fails(git_repo):
    repo = make_repo(git_repo)
    path = repo / ".agent-work" / WORK / "evidence" / "red-test-a.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    assert run_check(repo)["test_a"].status == "fail"


def test_check_lists_each_distinct_test_once_in_plan_order(git_repo):
    plan = PLAN + "\n### Task 2: More\n\n**Acceptance criteria:** AC-3\n\n**Tests:** `test_b`, `test_c`\n"
    repo = make_repo(git_repo, TWO_TESTS, plan)
    entries = run_check(repo)
    assert list(entries) == ["test_a", "test_b", "test_c"]
    assert entries["test_b"].acs == ("AC-1", "AC-2", "AC-3")


def test_main_writes_report_and_exits_one_on_fail(git_repo, monkeypatch, capsys):
    repo = make_repo(git_repo)
    record_test(repo, "test_a", monkeypatch)
    code = red_check.main(["--work-item", WORK, "--spec", "spec.md", "--plan", "plan.md"])
    assert code == 1
    report = json.loads((repo / ".agent-work" / WORK / "evidence" / "red-check.json").read_text())
    statuses = {e["test_id"]: e["status"] for e in report["entries"]}
    assert statuses == {"test_a": "pass", "test_b": "fail"}
    assert "fail: test_b: no red record" in capsys.readouterr().out


def test_main_exits_zero_without_fail(git_repo, monkeypatch):
    repo = make_repo(git_repo)
    record_test(repo, "test_a", monkeypatch)
    record_test(repo, "test_b", monkeypatch)
    assert red_check.main(["--work-item", WORK, "--spec", "spec.md", "--plan", "plan.md"]) == 0


def test_main_needs_review_does_not_fail(git_repo, monkeypatch):
    repo = make_repo(git_repo)
    monkeypatch.chdir(repo)
    write_record(repo, "test_a", category="no-run")
    write_record(repo, "test_b", category="missing-symbol")
    assert red_check.main(["--work-item", WORK, "--spec", "spec.md", "--plan", "plan.md"]) == 0


def test_main_help_and_usage(capsys):
    assert red_check.main(["--help"]) == 0
    assert "usage: red_check" in capsys.readouterr().out
    assert red_check.main(["--work-item", WORK]) == 2


def test_main_missing_plan_exits_two(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo.path)
    assert red_check.main(["--work-item", WORK, "--spec", "s.md", "--plan", "nope.md"]) == 2
