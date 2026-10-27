from kcommon.structure_check import (
    StructureFinding,
    TaskEntry,
    check_plan,
    check_spec,
    parse_plan,
    parse_spec_acs,
)

SPEC = """## Current state
x
## Program design
x
## Alternatives
### Option B
x
## Acceptance criteria
- AC-1: Add returns the sum.
- AC-2: Add rejects text.
## Verification commands
- `npm test`
## In scope
x
## Out of scope
x
"""

PLAN = """### Task 1: Add
**Acceptance criteria:** AC-1
**Tests:** `test_add`, `test_add_negative`
"""


def test_valid_spec_passes():
    assert check_spec(SPEC) == []
    assert parse_spec_acs(SPEC) == ["AC-1", "AC-2"]


def test_missing_alternative_flagged():
    findings = check_spec(SPEC.replace("### Option B\n", ""))
    assert [f.code for f in findings] == ["no-alternative"]
    assert findings[0].message == "no alternative named"


def test_missing_heading_flagged():
    findings = check_spec(SPEC.replace("## In scope\n", ""))
    assert findings == [StructureFinding("missing-section", "missing section: ## In scope")]


def test_duplicate_ac_id_flagged():
    findings = check_spec(SPEC.replace("AC-2:", "AC-1:"))
    assert findings == [StructureFinding("duplicate-ac-id", "duplicate AC id: AC-1")]


def test_valid_plan_passes():
    spec = SPEC.replace("- AC-2: Add rejects text.\n", "")
    assert check_plan(spec, PLAN) == []


def test_ac_without_task_flagged():
    assert check_plan(SPEC, PLAN) == [StructureFinding("ac-without-task", "AC-2 has no task")]


def test_task_without_tests_flagged():
    plan = "### Task 1: Add\n**Acceptance criteria:** AC-1, AC-2\n"
    assert check_plan(SPEC, plan) == [StructureFinding("task-without-tests", "Task 1 names no tests")]


def test_unknown_ac_id_flagged():
    plan = PLAN.replace("AC-1", "AC-1, AC-2, AC-9")
    assert check_plan(SPEC, plan) == [StructureFinding("unknown-ac-id", "Task 1 cites unknown AC-9")]


def test_parse_plan_returns_entries():
    assert parse_plan(PLAN) == [TaskEntry(1, ("AC-1",), ("test_add", "test_add_negative"))]


def test_fenced_blocks_skipped():
    fenced = "```\n### Task 7: Fake\n```\n" + PLAN
    assert [t.number for t in parse_plan(fenced)] == [1]
