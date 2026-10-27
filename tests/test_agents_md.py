import re
from pathlib import Path

from kcommon import agents_md, globs
from kcommon.agents_md import ReviewLimits, Thresholds, WorkTracking

GOLDEN = """\
## Work tracking
- Board: Azure DevOps Boards, org `contoso`, project `Webshop` (CLI: `az boards`)
- Code host: GitHub (CLI: `gh`)
- Findings go to: GitHub Issues, label `agent-found`, visibility: private
- Link work items in PRs as: `AB#1234`
- Branch names: `feature/1234-short-name`
- Protected paths: `src/auth/**`, `db/migrations/**`, `.github/**`, `infra/**`
- Invariant: `src/auth/**`: "no endpoint without an authorization check"
- Invariant: `db/migrations/**`: "each migration has a down step"
- Risk thresholds: medium_lines=300, medium_owner_teams=2, high_lines=800
- Review limits: spec_rounds=3, code_rounds=2, spec_attackers_low=2, spec_attackers_medium=3, spec_attackers_high=5
- Subagent budget: 18
- Cross-vendor attacker: off
- Verification commands: `npm test`, `npm run lint`
- QA plan: `docs/qa-plan.md`
"""

# The example block from design section 6.1.
DESIGN_PROSE = """\
## Work tracking
- Board: Azure DevOps Boards, org `contoso`, project `Webshop` (CLI: `az boards`)
- Code host: GitHub (CLI: `gh`)
- Findings go to: GitHub Issues, label `agent-found`, visibility: private
- Link work items in PRs as: `AB#1234`
- Branch names: `feature/1234-short-name`
- Protected paths: `src/auth/**`, `db/migrations/**`, `.github/**`, `infra/**`
- Invariants: `src/auth/**`: "no endpoint without an authorization check"
- Risk thresholds: medium above 300 changed lines or 2 CODEOWNERS teams; high above 800 lines
- Review limits: spec 3 rounds, code 2 rounds; spec attackers low 2, medium 3, high 5
- Subagent budget: 18 for each review loop
- Cross-vendor attacker: off
- Verification commands: `npm test`, `npm run lint`
- QA plan: `docs/qa-plan.md`
"""

TEMPLATE = (
    Path(__file__).resolve().parent.parent
    / "skills" / "k-common" / "templates" / "agents-md-work-tracking.md"
)

BOARD_AND_HOST = (
    "## Work tracking\n"
    "- Board: Jira\n"
    "- Code host: GitHub (CLI: `gh`)\n"
)


def golden_object() -> WorkTracking:
    return WorkTracking(
        board="Azure DevOps Boards, org `contoso`, project `Webshop`",
        board_cli="az boards",
        code_host="GitHub",
        code_host_cli="gh",
        findings_target="GitHub Issues, label `agent-found`",
        findings_visibility="private",
        link_format="AB#1234",
        branch_names="feature/1234-short-name",
        protected_paths=("src/auth/**", "db/migrations/**", ".github/**", "infra/**"),
        invariants={
            "src/auth/**": "no endpoint without an authorization check",
            "db/migrations/**": "each migration has a down step",
        },
        thresholds=Thresholds(medium_lines=300, medium_owner_teams=2, high_lines=800),
        review_limits=ReviewLimits(
            spec_rounds=3, code_rounds=2,
            spec_attackers={"low": 2, "medium": 3, "high": 5},
        ),
        subagent_budget=18,
        cross_vendor_attacker=False,
        verification_commands=("npm test", "npm run lint"),
        qa_plan="docs/qa-plan.md",
    )


def test_parse_golden_fixture():
    assert agents_md.parse(GOLDEN) == (golden_object(), [])


def test_missing_section_returns_none():
    assert agents_md.parse("# Title\n\nNo section here.\n") == (None, [])


def test_defaults_for_missing_lines():
    wt, warnings = agents_md.parse(BOARD_AND_HOST)
    assert wt is not None
    assert wt.board == "Jira" and wt.board_cli is None
    assert wt.code_host == "GitHub" and wt.code_host_cli == "gh"
    assert wt.findings_visibility == "unknown"
    assert wt.link_format is None and wt.branch_names is None and wt.qa_plan is None
    assert wt.invariants == {}
    assert wt.thresholds == Thresholds(300, 2, 800)
    assert wt.review_limits == ReviewLimits(3, 2, {"low": 2, "medium": 3, "high": 5})
    assert wt.subagent_budget == 18
    assert wt.cross_vendor_attacker is False
    assert wt.verification_commands == ()
    assert warnings == ["missing key: Protected paths"]


def test_budget_default_follows_parsed_limits():
    text = BOARD_AND_HOST + (
        "- Review limits: spec_rounds=2, code_rounds=1, "
        "spec_attackers_low=1, spec_attackers_medium=2, spec_attackers_high=4\n"
    )
    wt, _ = agents_md.parse(text)
    assert wt is not None and wt.subagent_budget == 10


def test_crlf_line_endings():
    assert agents_md.parse(GOLDEN.replace("\n", "\r\n")) == (golden_object(), [])


def test_fenced_example_skipped():
    text = (
        "# Doc\n\n```markdown\n## Work tracking\n- Board: Fake\n- Code host: Fake\n"
        "- Protected paths: `fake/**`\n```\n\n" + GOLDEN
    )
    assert agents_md.parse(text) == (golden_object(), [])


def test_fenced_section_alone_is_missing():
    text = "```markdown\n" + GOLDEN + "```\n"
    assert agents_md.parse(text) == (None, [])


def test_section_ends_at_next_heading():
    text = GOLDEN + "## Other\n- Board: Intruder\n- Unknown thing: x\n"
    assert agents_md.parse(text) == (golden_object(), [])


def test_heading_inside_fence_does_not_end_section():
    text = GOLDEN + "```\n## Not a heading\n```\n- Subagent budget: 7\n"
    wt, warnings = agents_md.parse(text)
    assert wt is not None
    assert warnings == ["duplicate key: Subagent budget"]
    assert wt.subagent_budget == 18


def test_unknown_key_warns():
    wt, warnings = agents_md.parse(GOLDEN + "- Colour: blue\n")
    assert wt == golden_object()
    assert warnings == ["unknown key: Colour"]


def test_malformed_number_warns():
    text = BOARD_AND_HOST + "- Protected paths: `x`\n- Risk thresholds: medium_lines=abc\n"
    wt, warnings = agents_md.parse(text)
    assert wt is not None
    assert warnings == ["malformed value: Risk thresholds"]
    assert wt.thresholds == Thresholds(300, 2, 800)


def test_missing_protected_paths_is_none_with_warning():
    text = BOARD_AND_HOST + "- Protected path: `x`\n"
    wt, warnings = agents_md.parse(text)
    assert wt is not None and wt.protected_paths is None
    assert warnings == ["unknown key: Protected path", "missing key: Protected paths"]


def test_missing_board_and_code_host_warn():
    wt, warnings = agents_md.parse("## Work tracking\n- Protected paths: `x`\n")
    assert wt is not None
    assert warnings == ["missing key: Board", "missing key: Code host"]


def test_design_prose_example_warns():
    wt, warnings = agents_md.parse(DESIGN_PROSE)
    assert wt is not None
    assert warnings == [
        "unknown key: Invariants",
        "malformed value: Risk thresholds",
        "malformed value: Review limits",
        "malformed value: Subagent budget",
    ]
    assert wt.thresholds == Thresholds(300, 2, 800)
    assert wt.review_limits == ReviewLimits(3, 2, {"low": 2, "medium": 3, "high": 5})
    assert wt.subagent_budget == 18
    assert wt.invariants == {}
    assert wt.board_cli == "az boards"
    assert wt.protected_paths == golden_object().protected_paths
    assert wt.verification_commands == ("npm test", "npm run lint")
    assert wt.qa_plan == "docs/qa-plan.md"


def test_hyphenated_key_parses():
    wt, warnings = agents_md.parse(
        BOARD_AND_HOST + "- Protected paths: `x`\n- Cross-vendor attacker: on\n"
    )
    assert wt is not None and wt.cross_vendor_attacker is True
    assert warnings == []


def test_malformed_values_keep_defaults_and_warn():
    text = BOARD_AND_HOST + (
        "- Protected paths: none\n"
        "- Findings go to: somewhere\n"
        "- Link work items in PRs as: AB#1\n"
        "- Invariant: src/**: no quotes\n"
        "- Cross-vendor attacker: maybe\n"
        "- Subagent budget: many\n"
    )
    wt, warnings = agents_md.parse(text)
    assert wt is not None
    assert warnings == [
        "malformed value: Protected paths",
        "malformed value: Findings go to",
        "malformed value: Link work items in PRs as",
        "malformed value: Invariant",
        "malformed value: Cross-vendor attacker",
        "malformed value: Subagent budget",
    ]
    assert wt.protected_paths is None
    assert wt.findings_visibility == "unknown"
    assert wt.link_format is None
    assert wt.invariants == {}
    assert wt.cross_vendor_attacker is False


def test_bare_protected_entry_matches_at_any_depth_without_warning():
    text = BOARD_AND_HOST + "- Protected paths: `Dockerfile`, `infra`\n"
    wt, warnings = agents_md.parse(text)
    assert warnings == []
    assert wt is not None and wt.protected_paths == ("Dockerfile", "infra")
    assert globs.match("Dockerfile", "svc/Dockerfile")
    assert globs.match("infra", "infra/main.bicep")
    assert globs.match("infra", "a/infra/main.bicep")

    only_infra, warnings = agents_md.parse(BOARD_AND_HOST + "- Protected paths: `infra`\n")
    assert warnings == []
    assert only_infra is not None and only_infra.protected_paths == ("infra",)


def test_load_reads_base_ref_not_worktree(git_repo):
    git_repo.write("AGENTS.md", BOARD_AND_HOST + "- Protected paths: `path-a/**`\n")
    git_repo.commit_all("add agents")
    git_repo.write("AGENTS.md", BOARD_AND_HOST + "- Protected paths: `path-b/**`\n")
    wt, warnings = agents_md.load(git_repo.path, "HEAD")
    assert warnings == []
    assert wt is not None and wt.protected_paths == ("path-a/**",)


def test_load_without_agents_md_returns_none(git_repo):
    git_repo.write("README.md", "hi\n")
    git_repo.commit_all("one")
    assert agents_md.load(git_repo.path, "HEAD") == (None, [])


# Template

PLACEHOLDER = re.compile(r"<[a-z0-9-]+>")


def test_template_has_no_fence_and_follows_style():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert not any(line.startswith("```") for line in text.splitlines())
    for forbidden in (";", "–", "—"):
        assert forbidden not in text


def test_template_placeholders_are_each_used_once():
    found = PLACEHOLDER.findall(TEMPLATE.read_text(encoding="utf-8"))
    assert len(found) == len(set(found))
    assert set(found) == {
        "<board>", "<board-cli>", "<code-host>", "<code-host-cli>",
        "<findings-target>", "<visibility>", "<link-format>", "<branch-pattern>",
        "<qa-plan>", "<protected-globs>", "<verification-commands>",
        "<invariant-glob-1>", "<invariant-text-1>", "<invariant-glob-2>", "<invariant-text-2>",
        "<medium-lines>", "<medium-owner-teams>", "<high-lines>", "<spec-rounds>",
        "<code-rounds>", "<spec-attackers-low>", "<spec-attackers-medium>",
        "<spec-attackers-high>", "<subagent-budget>", "<cross-vendor>",
    }


def test_filled_template_parses_to_the_golden_object():
    values = {
        "<board>": "Azure DevOps Boards, org `contoso`, project `Webshop`",
        "<board-cli>": "az boards",
        "<code-host>": "GitHub",
        "<code-host-cli>": "gh",
        "<findings-target>": "GitHub Issues, label `agent-found`",
        "<visibility>": "private",
        "<link-format>": "AB#1234",
        "<branch-pattern>": "feature/1234-short-name",
        "<qa-plan>": "docs/qa-plan.md",
        "<protected-globs>": "`src/auth/**`, `db/migrations/**`, `.github/**`, `infra/**`",
        "<verification-commands>": "`npm test`, `npm run lint`",
        "<invariant-glob-1>": "src/auth/**",
        "<invariant-text-1>": "no endpoint without an authorization check",
        "<invariant-glob-2>": "db/migrations/**",
        "<invariant-text-2>": "each migration has a down step",
        "<medium-lines>": "300", "<medium-owner-teams>": "2", "<high-lines>": "800",
        "<spec-rounds>": "3", "<code-rounds>": "2",
        "<spec-attackers-low>": "2", "<spec-attackers-medium>": "3", "<spec-attackers-high>": "5",
        "<subagent-budget>": "18", "<cross-vendor>": "off",
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    assert agents_md.parse(text) == (golden_object(), [])
