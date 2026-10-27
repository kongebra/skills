"""Check the structure of specs and plans against the team marker format."""

import re
import sys
from dataclasses import dataclass

SPEC_HEADINGS = (
    "## Current state",
    "## Program design",
    "## Alternatives",
    "## Acceptance criteria",
    "## Verification commands",
    "## In scope",
    "## Out of scope",
)

_AC_LINE = re.compile(r"^- (AC-\d+): (.+)$")
_COMMAND_LINE = re.compile(r"^- `[^`]+`$")
_TASK_START = re.compile(r"^### Task (\d+):")
_PLAN_AC = re.compile(r"^\*\*Acceptance criteria:\*\* (AC-\d+(?:, AC-\d+)*)$")
_PLAN_TESTS = re.compile(r"^\*\*Tests:\*\* (`[^`]+`(?:, `[^`]+`)*)$")
_TEST_NAME = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class StructureFinding:
    code: str
    message: str


@dataclass(frozen=True)
class TaskEntry:
    number: int
    acs: tuple[str, ...]
    tests: tuple[str, ...]


def _lines_outside_fences(text: str) -> list[str]:
    lines = []
    fence = None
    for raw in text.splitlines():
        line = raw.rstrip()
        marker = line.lstrip()[:3]
        if marker in ("```", "~~~"):
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return lines


def _sections(text: str) -> dict[str, list[str]]:
    """Map each `## ` heading to its body lines. The first duplicate heading wins."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in _lines_outside_fences(text):
        if line.startswith("## "):
            current = line if line not in sections else None
            if current is not None:
                sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def parse_spec_acs(spec_text: str) -> list[str]:
    body = _sections(spec_text).get("## Acceptance criteria", [])
    return [m.group(1) for line in body if (m := _AC_LINE.match(line))]


def parse_plan(plan_text: str) -> list[TaskEntry]:
    blocks: list[tuple[int, list[str]]] = []
    current = None
    for line in _lines_outside_fences(plan_text):
        start = _TASK_START.match(line)
        if start:
            current = (int(start.group(1)), [])
            blocks.append(current)
        elif line.startswith(("### ", "## ")):
            current = None
        elif current is not None:
            current[1].append(line)
    entries = []
    for number, body in blocks:
        acs: list[str] = []
        tests: list[str] = []
        for line in body:
            if m := _PLAN_AC.match(line):
                acs.extend(m.group(1).split(", "))
            elif m := _PLAN_TESTS.match(line):
                tests.extend(_TEST_NAME.findall(m.group(1)))
        entries.append(TaskEntry(number, tuple(acs), tuple(tests)))
    return entries


def check_spec(text: str) -> list[StructureFinding]:
    sections = _sections(text)
    findings = []
    for heading in SPEC_HEADINGS:
        if heading not in sections:
            findings.append(StructureFinding("missing-section", f"missing section: {heading}"))
    commands = "## Verification commands"
    if commands in sections and not any(_COMMAND_LINE.match(x) for x in sections[commands]):
        findings.append(StructureFinding("missing-section", f"missing section: {commands}"))
    if "## Alternatives" in sections and not any(
        x.startswith("### ") for x in sections["## Alternatives"]
    ):
        findings.append(StructureFinding("no-alternative", "no alternative named"))
    if "## Acceptance criteria" in sections:
        ids = parse_spec_acs(text)
        if not ids:
            findings.append(StructureFinding("no-acceptance-criteria", "no acceptance criteria"))
        seen: set[str] = set()
        for ac_id in ids:
            if ac_id in seen:
                findings.append(StructureFinding("duplicate-ac-id", f"duplicate AC id: {ac_id}"))
            seen.add(ac_id)
    return findings


def check_plan(spec_text: str, plan_text: str) -> list[StructureFinding]:
    spec_acs = list(dict.fromkeys(parse_spec_acs(spec_text)))
    tasks = parse_plan(plan_text)
    cited = {ac for task in tasks for ac in task.acs}
    findings = [
        StructureFinding("ac-without-task", f"{ac} has no task") for ac in spec_acs if ac not in cited
    ]
    findings += [
        StructureFinding("task-without-tests", f"Task {t.number} names no tests")
        for t in tasks
        if not t.tests
    ]
    known = set(spec_acs)
    findings += [
        StructureFinding("unknown-ac-id", f"Task {t.number} cites unknown {ac}")
        for t in tasks
        for ac in t.acs
        if ac not in known
    ]
    return findings


_USAGE = (
    "usage: structure_check spec <spec.md>\n"
    "       structure_check plan <spec.md> <plan.md>\n"
    "Prints one finding per line. Exits 1 on any finding."
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def main(argv: list[str]) -> int:
    if any(a in ("-h", "--help") for a in argv) or not argv:
        print(_USAGE)
        return 0
    if argv[0] == "spec" and len(argv) == 2:
        findings = check_spec(_read(argv[1]))
    elif argv[0] == "plan" and len(argv) == 3:
        findings = check_plan(_read(argv[1]), _read(argv[2]))
    else:
        print(_USAGE, file=sys.stderr)
        return 2
    for f in findings:
        print(f"{f.code}: {f.message}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
