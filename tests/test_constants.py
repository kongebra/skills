import re

from kcommon import constants


def test_ci_globs_exclude_agents_md():
    assert "AGENTS.md" not in constants.CI_GLOBS


def test_ci_globs_are_subset_of_guardrail_globs():
    assert set(constants.CI_GLOBS) <= set(constants.GUARDRAIL_GLOBS)


def test_guardrail_globs_cover_agent_instruction_files():
    for glob in (
        "CLAUDE.md",
        ".mcp.json",
        ".claude/agents/**",
        ".claude/commands/**",
        ".github/copilot-instructions.md",
    ):
        assert glob in constants.GUARDRAIL_GLOBS


def test_ci_globs_cover_other_ci_hosts():
    for glob in (
        "azure-pipelines.yaml",
        "pipelines/**/*.yml",
        ".azuredevops/**",
        "bitbucket-pipelines.yml",
        ".github/actions/**",
    ):
        assert glob in constants.CI_GLOBS


def _skip_hit(line: str) -> bool:
    return any(re.search(marker, line) for marker in constants.SKIP_MARKERS)


def test_skip_marker_does_not_match_process_exit():
    assert not _skip_hit("process.exit(1)")
    assert _skip_hit('xit("a")')


def test_scalar_constants():
    assert constants.EVIDENCE_HEAD_CHARS == 5000
    assert constants.EVIDENCE_TAIL_CHARS == 15000
    assert constants.RUN_TIMEOUT_SECONDS == 600
    assert constants.MATT_SKILLS == ("grilling", "grill-with-docs", "domain-modeling")
    assert constants.IGNORE_PROBES == (
        "docs/superpowers/x",
        ".agent-work/x",
        ".superpowers/x",
    )
