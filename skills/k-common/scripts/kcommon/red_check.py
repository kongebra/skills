"""Check the red records of a work item against the plan and the current test files.

Known limit: a record of a test that fails for an environment reason counts as red, and a
hand-written record file cannot be stopped by a local script. The test quality reviewer
owns that risk (see red_record).
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from kcommon.red_record import (
    DuplicateTestId,
    evidence_dir,
    extract_block,
    slug,
    valid_work_item,
)
from kcommon.structure_check import parse_plan

Status = Literal["pass", "needs-review", "fail"]


@dataclass(frozen=True)
class CheckEntry:
    test_id: str
    acs: tuple[str, ...]
    status: Status
    reason: str


@dataclass
class CheckReport:
    entries: list[CheckEntry] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(e.status == "fail" for e in self.entries)


def _plan_tests(plan_text: str) -> dict[str, tuple[str, ...]]:
    """Distinct named tests in plan order, each with the AC IDs of the tasks that name it."""
    tests: dict[str, list[str]] = {}
    for task in parse_plan(plan_text):
        for test_id in task.tests:
            acs = tests.setdefault(test_id, [])
            acs.extend(ac for ac in task.acs if ac not in acs)
    return {test_id: tuple(acs) for test_id, acs in tests.items()}


def _judge(test_id: str, record_path: Path, repo: Path) -> tuple[Status, str]:
    if not record_path.is_file():
        return "fail", "no red record"
    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "fail", "record is not readable"
    if not isinstance(data, dict):
        return "fail", "record is not readable"
    exit_code = data.get("exit_code")
    if exit_code == 0:
        return "fail", "record shows exit code 0"
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return "fail", "record has no exit code"
    category = data.get("category")
    if category == "syntax":
        return "fail", "category is syntax"
    if category == "missing-symbol":
        return "needs-review", "missing symbol, reviewer decides"
    if category == "no-run":
        return "needs-review", "run did not reach the test, reviewer decides"
    if category != "red":
        return "fail", f"category is {category}"
    test_file = data.get("test_file")
    text = None
    if isinstance(test_file, str) and test_file:
        try:
            text = (repo / test_file).read_bytes().decode("utf-8", errors="replace")
        except OSError:
            text = None
    try:
        block = extract_block(text, test_id) if text is not None else None
    except DuplicateTestId:
        return "fail", "duplicate test id"
    recorded = data.get("test_block_sha256")
    if recorded is None or block is None:
        return "needs-review", "test block not found"
    if block.sha256 != recorded:
        return "fail", "test changed after the red record"
    return "pass", "ok"


def check(work_item: str, spec: Path, plan: Path, repo: Path) -> CheckReport:
    """One entry per distinct named test in the plan. `spec` is accepted for the CLI
    contract; the rules read the plan and the records only."""
    plan_text = (repo / plan).read_bytes().decode("utf-8", errors="replace")
    directory = evidence_dir(repo, work_item)
    report = CheckReport()
    for test_id, acs in _plan_tests(plan_text).items():
        status, reason = _judge(test_id, directory / f"red-{slug(test_id)}.json", repo)
        report.entries.append(CheckEntry(test_id, acs, status, reason))
    return report


_USAGE = (
    "usage: red_check --work-item <id> --spec <path> --plan <path>\n"
    "Checks the red records of every test the plan names. Writes\n"
    ".agent-work/<id>/evidence/red-check.json. Exits 1 when any entry is fail."
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # type: ignore[override]
        raise ValueError(message)


def main(argv: list[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(_USAGE)
        return 0
    parser = _Parser(add_help=False)
    for name in ("--work-item", "--spec", "--plan"):
        parser.add_argument(name, required=True)
    try:
        args = parser.parse_args(argv)
    except ValueError as exc:
        print(f"{exc}\n{_USAGE}", file=sys.stderr)
        return 2
    if not valid_work_item(args.work_item):
        print("bad work item id", file=sys.stderr)
        return 2
    repo = Path.cwd()
    try:
        report = check(args.work_item, Path(args.spec), Path(args.plan), repo)
    except OSError as exc:
        print(f"cannot read plan: {exc}", file=sys.stderr)
        return 2
    target = evidence_dir(repo, args.work_item)
    target.mkdir(parents=True, exist_ok=True)
    payload = {"work_item": args.work_item, "entries": [asdict(e) for e in report.entries]}
    (target / "red-check.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for e in report.entries:
        print(f"{e.status}: {e.test_id}: {e.reason}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
