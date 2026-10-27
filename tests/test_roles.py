import re
from pathlib import Path

import pytest
from kcommon.ste_lint import lint

ROOT = Path(__file__).resolve().parent.parent
COMMON = ROOT / "skills" / "k-common"
ROLES = ["zoom-out", "naive-reader", "critic", "reality-check", "readiness",
         "test-quality", "standards", "invariant"]
BRIEFS = ["attacker", "judge", "finding-format", "roles-by-level"]
ALL_FILES = [COMMON / "roles" / f"{r}.md" for r in ROLES] + [
    COMMON / "briefs" / f"{b}.md" for b in BRIEFS
]


def role_text(name):
    return (COMMON / "roles" / f"{name}.md").read_text(encoding="utf-8")


def brief_text(name):
    return (COMMON / "briefs" / f"{name}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("role", ROLES)
def test_each_role_has_three_sections(role):
    text = role_text(role)
    for heading in ("## On a spec", "## On a plan", "## On code"):
        assert heading in text.splitlines()


@pytest.mark.parametrize("role", ROLES)
def test_each_role_has_attacker_sentence(role):
    assert "Find what is wrong. Do not confirm." in role_text(role)


def test_roles_by_level_names_existing_roles():
    rows = brief_text("roles-by-level").splitlines()
    header = "| Level | k-spec-review roles | k-code-review roles |"
    assert header in rows
    body = rows[rows.index(header) + 2:]
    body = [r for r in body if r.startswith("|")]
    assert [r.split("|")[1].strip() for r in body] == ["Low", "Medium", "High"]
    for row in body:
        for cell in row.split("|")[2:-1]:
            cell = re.sub(r"\s*\(.*?\)", "", cell)
            for name in cell.strip().split(", "):
                slug = name.lower().replace(" ", "-")
                assert (COMMON / "roles" / f"{slug}.md").is_file(), name


def test_finding_format_has_four_fields():
    text = brief_text("finding-format")
    for field in ("Location", "What fails", "Suggested fix", "Guardrail"):
        assert field in text


def test_attacker_brief_has_required_rules():
    text = brief_text("attacker")
    assert "Find what is wrong. Do not confirm" in text
    assert "Strongest finding" in text
    for field in ("ID", "Location", "What fails", "Suggested fix", "Guardrail",
                  "Proposed severity"):
        assert field in text


def test_judge_brief_has_required_rules():
    text = brief_text("judge").lower()
    for word in ("blocking", "merge", "reject", "data"):
        assert word in text


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_role_files_pass_ste_lint(path):
    text = path.read_text(encoding="utf-8")
    assert lint(text) == []
    assert len(text.splitlines()) < 60
