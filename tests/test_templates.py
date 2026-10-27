import re
from pathlib import Path

from kcommon import agents_md

from tests.test_agents_md import TEMPLATE, golden_object

TEMPLATES = Path(__file__).resolve().parent.parent / "skills" / "k-common" / "templates"

PR_HEADINGS = [
    "Summary",
    "Risk level",
    "Risk facts",
    "Acceptance criteria",
    "Checks that ran",
    "Decisions",
    "Answered questions",
    "Review mode",
    "Guardrail proposals",
    "Work item",
]

VALUES = {
    "board": "Azure DevOps Boards, org `contoso`, project `Webshop`",
    "board-cli": "az boards",
    "code-host": "GitHub",
    "code-host-cli": "gh",
    "findings-target": "GitHub Issues, label `agent-found`",
    "visibility": "private",
    "link-format": "AB#1234",
    "branch-pattern": "feature/1234-short-name",
    "qa-plan": "docs/qa-plan.md",
    "protected-globs": "`src/auth/**`, `db/migrations/**`, `.github/**`, `infra/**`",
    "verification-commands": "`npm test`, `npm run lint`",
    "invariant-glob-1": "src/auth/**",
    "invariant-text-1": "no endpoint without an authorization check",
    "invariant-glob-2": "db/migrations/**",
    "invariant-text-2": "each migration has a down step",
    "medium-lines": "300",
    "medium-owner-teams": "2",
    "high-lines": "800",
    "spec-rounds": "3",
    "code-rounds": "2",
    "spec-attackers-low": "2",
    "spec-attackers-medium": "3",
    "spec-attackers-high": "5",
    "subagent-budget": "18",
    "cross-vendor": "off",
}


def test_pr_template_has_ten_sections_in_order():
    text = (TEMPLATES / "pr-template.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
    assert headings == PR_HEADINGS


def test_work_tracking_template_parses():
    text = TEMPLATE.read_text(encoding="utf-8")
    placeholders = set(re.findall(r"<([a-z0-9-]+)>", text))
    assert placeholders == set(VALUES)
    for name, value in VALUES.items():
        text = text.replace(f"<{name}>", value)
    assert "<" not in text
    assert agents_md.parse(text) == (golden_object(), [])
