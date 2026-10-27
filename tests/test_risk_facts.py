import dataclasses
import os
import re
import subprocess
from pathlib import Path

import pytest
from kcommon import risk_facts
from kcommon.gitutil import BaseNotFound

from tests.test_agents_md import GOLDEN

ROOT = Path(__file__).resolve().parent.parent
K_PY = ROOT / "skills" / "k-common" / "scripts" / "k.py"

CODEOWNERS = "* @org/all\n/src/auth/ @org/security\n*.md @org/docs\n"
TEST_APP = "def test_app():\n    assert True\n"


@pytest.fixture
def repo(git_repo):
    git_repo.write("AGENTS.md", GOLDEN)
    git_repo.write("CODEOWNERS", CODEOWNERS)
    git_repo.write("src/auth/login.py", "a = 1\nb = 2\n")
    git_repo.write("src/app.py", "print('app')\n")
    git_repo.write("tests/test_app.py", TEST_APP)
    git_repo.commit_all("base")
    return git_repo


def branch(repo, name="feature"):
    repo.git("checkout", "-b", name)


def head_of(repo, change):
    """Branch off main, apply the change, commit, and return (repo path, head sha)."""
    branch(repo)
    change()
    return repo.path, repo.commit_all("head")


def compute(repo, change, **kwargs):
    path, head = head_of(repo, change)
    return risk_facts.compute(path, "main", head, **kwargs)


def test_protected_path_sets_high(repo):
    facts = compute(
        repo, lambda: repo.write("src/auth/login.py", "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n")
    )
    assert facts.level == "high"
    assert facts.level_reasons == ["protected path: src/auth/login.py"]
    assert facts.lines_changed == 3
    assert facts.files_touched == 1
    assert facts.protected_paths_changed == ["src/auth/login.py"]
    assert facts.owner_teams_touched == ["@org/security"]
    assert facts.work_tracking_at_base is True


@pytest.mark.parametrize("renames", [None, "false"])
def test_renamed_test_is_not_deleted(repo, renames):
    if renames:
        repo.git("config", "diff.renames", renames)

    def change():
        (repo.path / "tests/test_app.py").unlink()
        repo.write("tests/test_main.py", TEST_APP)

    facts = compute(repo, change)
    assert facts.level == "low"
    assert facts.lines_changed == 0
    assert facts.files_touched == 1
    assert facts.deleted_tests == []


def test_deleted_test_is_listed(repo):
    facts = compute(repo, lambda: (repo.path / "tests/test_app.py").unlink())
    assert facts.deleted_tests == ["tests/test_app.py"]
    assert facts.level == "low"


def test_rename_from_test_path_to_prod_path_is_deleted(repo):
    def change():
        (repo.path / "tests/test_app.py").unlink()
        repo.write("src/helper.py", TEST_APP)

    facts = compute(repo, change)
    assert facts.deleted_tests == ["tests/test_app.py -> src/helper.py"]


def test_rename_out_of_protected_path_is_high(repo):
    def change():
        (repo.path / "src/auth/login.py").unlink()
        repo.write("src/login.py", "a = 1\nb = 2\n")

    facts = compute(repo, change)
    assert facts.level == "high"
    assert facts.protected_paths_changed == ["src/auth/login.py -> src/login.py"]
    assert facts.files_touched == 1
    assert facts.lines_changed == 0


def test_binary_file_counts_as_touched(repo):
    facts = compute(repo, lambda: repo.write("assets/logo.png", b"\x89PNG\x00\x00data\x00"))
    assert facts.lines_changed == 0
    assert facts.files_touched == 1


def test_path_with_space_and_non_ascii_handled(repo):
    facts = compute(repo, lambda: repo.write("dir with space/æøå.py", "x = 1\ny = 2\n"))
    assert facts.lines_changed == 2
    assert facts.files_touched == 1


def test_path_with_space_and_non_ascii_listed_unchanged(repo):
    path = "dir with space/migrations/æøå.py"
    facts = compute(repo, lambda: repo.write(path, "x = 1\n"))
    assert facts.migrations_changed == [path]
    assert f"migration: {path}" in facts.level_reasons


def test_thresholds_count_deleted_lines(repo):
    facts = compute(repo, lambda: repo.write("src/app.py", "x\n" * 301))
    assert facts.level == "medium"
    # the file had one line before, so 301 added plus 1 deleted
    assert facts.lines_changed == 302
    assert facts.level_reasons == ["lines changed 302 > 300"]


def test_thresholds_set_medium(repo):
    def change():
        with (repo.path / "src/app.py").open("a") as handle:
            handle.write("x\n" * 301)

    facts = compute(repo, change)
    assert facts.level == "medium"
    assert facts.level_reasons == ["lines changed 301 > 300"]


def test_thresholds_set_high(repo):
    def change():
        with (repo.path / "src/app.py").open("a") as handle:
            handle.write("x\n" * 801)

    facts = compute(repo, change)
    assert facts.level == "high"
    assert facts.level_reasons == ["lines changed 801 > 800", "lines changed 801 > 300"]


def test_skip_marker_listed(repo):
    facts = compute(
        repo,
        lambda: repo.write("tests/x.test.js", '    xit("a", fn)\n    process.exit(1)\n'),
    )
    assert facts.skipped_tests_added == [r"tests/x.test.js: \bxit\("]


def test_skip_marker_found_with_hostile_repo_config(repo):
    repo.git("config", "diff.noprefix", "true")
    repo.git("config", "diff.mnemonicPrefix", "true")
    repo.git("config", "color.ui", "always")
    repo.git("config", "color.diff", "always")
    facts = compute(
        repo,
        lambda: repo.write("tests/x.test.js", '    xit("a", fn)\n    process.exit(1)\n'),
    )
    assert facts.skipped_tests_added == [r"tests/x.test.js: \bxit\("]
    assert facts.lines_changed == 2


def test_codeowners_last_match_wins(repo):
    def change():
        repo.write("docs/a.md", "a\n")
        repo.write("README", "r\n")
        repo.write("src/auth/x.py", "x = 1\n")

    facts = compute(repo, change)
    assert facts.owner_teams_touched == ["@org/all", "@org/docs", "@org/security"]
    assert "owner teams 3 > 2" in facts.level_reasons


def test_codeowners_is_read_at_base_tip(repo):
    repo.git("checkout", "-b", "feature")
    repo.write("CODEOWNERS", "* @org/evil\n")
    repo.write("src/app.py", "print('changed')\n")
    head = repo.commit_all("head")
    facts = risk_facts.compute(repo.path, "main", head)
    assert facts.owner_teams_touched == ["@org/all"]


def test_agents_md_change_sets_high(repo):
    facts = compute(repo, lambda: repo.write("AGENTS.md", GOLDEN + "\nmore\n"))
    assert facts.level == "high"
    assert "guardrail file: AGENTS.md" in facts.level_reasons


def test_reads_protected_paths_from_base(repo):
    def change():
        repo.write("AGENTS.md", GOLDEN.replace("`src/auth/**`, ", "", 1))
        repo.write("src/auth/x.py", "x = 1\n")

    facts = compute(repo, change)
    assert facts.level == "high"
    assert facts.protected_paths_changed == ["src/auth/x.py"]
    assert "protected path: src/auth/x.py" in facts.level_reasons


def test_reads_policy_at_base_tip(repo):
    repo.git("checkout", "-b", "feature")
    repo.write("lib/core.py", "x = 1\n")
    head = repo.commit_all("head")
    repo.git("checkout", "main")
    repo.write("AGENTS.md", GOLDEN.replace("`src/auth/**`", "`src/auth/**`, `lib/**`"))
    repo.commit_all("protect lib")
    facts = risk_facts.compute(repo.path, "main", head)
    assert facts.level == "high"
    assert facts.protected_paths_changed == ["lib/core.py"]


def test_guardrail_skill_folder_sets_high(repo):
    def change():
        repo.write(".claude/skills/x/SKILL.md", "---\nname: x\n---\n")
        repo.write("skills-lock.json", "{}\n")

    facts = compute(repo, change)
    assert facts.level == "high"
    assert sorted(facts.guardrail_files_changed) == [".claude/skills/x/SKILL.md", "skills-lock.json"]
    assert "guardrail file: skills-lock.json" in facts.level_reasons


def test_dependency_migration_ci_set_high(repo):
    for name, field, reason in (
        ("package.json", "dependency_files_changed", "dependency file: package.json"),
        ("app/migrations/001.sql", "migrations_changed", "migration: app/migrations/001.sql"),
        ("azure-pipelines.yml", "ci_infra_changed", "ci or infrastructure: azure-pipelines.yml"),
        ("main.tf", "ci_infra_changed", "ci or infrastructure: main.tf"),
    ):
        repo.git("checkout", "-q", "main")
        repo.git("checkout", "-q", "-B", f"b-{abs(hash(name))}")
        repo.write(name, "x\n")
        head = repo.commit_all("head")
        facts = risk_facts.compute(repo.path, "main", head)
        assert facts.level == "high", name
        assert getattr(facts, field) == [name]
        assert reason in facts.level_reasons


def test_level_never_goes_down(repo):
    facts = compute(
        repo, lambda: repo.write("src/app.py", "print('b')\n"), previous_level="high"
    )
    assert facts.level == "high"
    assert facts.level_reasons == ["previous level high"]
    assert facts.previous_level == "high"


def test_missing_section_at_base_sets_medium(git_repo):
    git_repo.write("src/app.py", "print('app')\n")
    git_repo.commit_all("base")
    facts = compute(git_repo, lambda: git_repo.write("src/app.py", "print('b')\n"))
    assert facts.level == "medium"
    assert facts.work_tracking_at_base is False
    assert facts.level_reasons == ["no work tracking section at base"]
    assert facts.protected_paths_changed == []


def test_missing_protected_paths_line_sets_medium(git_repo):
    git_repo.write(
        "AGENTS.md", "## Work tracking\n- Board: Jira\n- Code host: GitHub (CLI: `gh`)\n"
    )
    git_repo.write("src/app.py", "print('app')\n")
    git_repo.commit_all("base")
    facts = compute(git_repo, lambda: git_repo.write("src/app.py", "print('b')\n"))
    assert facts.level == "medium"
    assert facts.work_tracking_at_base is True
    assert facts.level_reasons == [
        "no protected paths line at base",
        "policy warning: missing key: Protected paths",
    ]
    assert facts.policy_warnings == ["missing key: Protected paths"]


BAD_THRESHOLDS = GOLDEN.replace(
    "- Risk thresholds: medium_lines=300, medium_owner_teams=2, high_lines=800",
    "- Risk thresholds: medium_lines=abc",
)


def test_policy_warning_at_base_is_reported_and_raises_level(repo):
    assert BAD_THRESHOLDS != GOLDEN
    repo.write("AGENTS.md", BAD_THRESHOLDS)
    repo.commit_all("bad thresholds")
    facts = compute(repo, lambda: repo.write("src/app.py", "print('b')\n"))
    assert facts.policy_warnings == ["malformed value: Risk thresholds"]
    assert facts.level == "medium"
    assert "policy warning: malformed value: Risk thresholds" in facts.level_reasons
    lines = risk_facts.render(facts).split("\n")
    assert "- policy_warnings: malformed value: Risk thresholds" in lines


def test_policy_warnings_are_none_for_a_clean_policy(repo):
    facts = compute(repo, small(repo))
    assert facts.policy_warnings == []
    assert "- policy_warnings: none" in risk_facts.render(facts).split("\n")


def test_policy_warning_is_in_the_hash(repo):
    repo.write("AGENTS.md", BAD_THRESHOLDS)
    repo.commit_all("bad thresholds")
    path, head = head_of(repo, small(repo))
    facts = risk_facts.compute(path, "main", head)
    forged = dataclasses.replace(facts, policy_warnings=[])
    assert risk_facts.render(facts).split("\n")[0] != risk_facts.render(forged).split("\n")[0]


def test_verify_accepts_block_with_policy_warning(repo):
    repo.write("AGENTS.md", BAD_THRESHOLDS)
    repo.commit_all("bad thresholds")
    *_, result = verified(repo, small(repo))
    assert result.ok, result.message


def test_verify_rejects_block_with_policy_warning_removed(repo):
    repo.write("AGENTS.md", BAD_THRESHOLDS)
    repo.commit_all("bad thresholds")
    *_, result = verified(
        repo,
        small(repo),
        edit=lambda t, h, p: t.replace(
            "- policy_warnings: malformed value: Risk thresholds", "- policy_warnings: none"
        ),
    )
    assert not result.ok
    assert result.message == "facts differ from the recomputed facts"


def test_unknown_base_raises_base_not_found(repo):
    path, head = head_of(repo, lambda: repo.write("src/app.py", "print('b')\n"))
    with pytest.raises(BaseNotFound):
        risk_facts.compute(path, "no-such-ref", head)
    with pytest.raises(BaseNotFound):
        risk_facts.compute(path, "main", "no-such-head")
    result = subprocess.run(
        ["uv", "run", "--no-project", "python", str(K_PY), "risk_facts",
         "--base", "no-such-ref", "--head", head],
        check=False, cwd=path, capture_output=True, text=True, env=os.environ.copy(),
    )
    assert result.returncode == 2, result.stderr


def test_cli_prints_block(repo):
    path, head = head_of(repo, lambda: repo.write("src/app.py", "print('b')\n"))
    result = subprocess.run(
        ["uv", "run", "--no-project", "python", str(K_PY), "risk_facts",
         "--base", "main", "--head", head, "--previous-level", "medium",
         "--test-count-before", "3", "--test-count-after", "4"],
        check=False, cwd=path, capture_output=True, text=True, env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("<!-- risk-facts base=")
    assert "- test_count_before: 3" in result.stdout
    assert "- previous_level: medium" in result.stdout
    assert result.stdout.rstrip().endswith("<!-- /risk-facts -->")


def test_cli_verify_exit_codes(repo, tmp_path):
    path, head = head_of(repo, lambda: repo.write("src/app.py", "print('b')\n"))
    block = risk_facts.render(risk_facts.compute(path, "main", head))
    good = tmp_path / "good.md"
    good.write_text("text\n" + block + "\n", encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text(block.replace("- lines_changed: 2", "- lines_changed: 0"), encoding="utf-8")

    def run(body):
        return subprocess.run(
            ["uv", "run", "--no-project", "python", str(K_PY), "risk_facts",
             "--verify", str(body), "--head-sha", head, "--base-ref", "main",
             "--trusted-previous-level", "low"],
            check=False, cwd=path, capture_output=True, text=True, env=os.environ.copy(),
        )

    assert run(good).returncode == 0
    assert run(bad).returncode == 1


def test_ratio_is_none_without_production_lines(repo):
    facts = compute(repo, lambda: repo.write("tests/test_app.py", TEST_APP + "# more\n"))
    assert facts.test_to_prod_ratio is None
    assert "- test_to_prod_ratio: none" in risk_facts.render(facts).split("\n")


def test_ratio_is_computed(repo):
    def change():
        repo.write("tests/test_new.py", "a\nb\nc\n")
        repo.write("src/new.py", "a\nb\nc\nd\ne\nf\n")

    facts = compute(repo, change)
    assert facts.test_to_prod_ratio == 0.5


def test_render_hash_ignores_volatile_fields(repo):
    path, head = head_of(repo, lambda: repo.write("src/app.py", "print('b')\n"))
    one = risk_facts.compute(path, "main", head, test_count_before=1, test_count_after=2)
    two = dataclasses.replace(
        one, test_count_before=9, test_count_after=10, last_authors=["Someone Else"]
    )
    text_one, text_two = risk_facts.render(one), risk_facts.render(two)
    assert text_one != text_two
    assert text_one.split("\n")[0] == text_two.split("\n")[0]
    lines = text_one.split("\n")
    assert lines[0].startswith("<!-- risk-facts base=")
    assert lines[-1] == "<!-- /risk-facts -->"
    assert [line.split(":")[0] for line in lines[1:-1]] == [
        f"- {f.name}" for f in dataclasses.fields(one)
    ]


def test_render_value_formats(repo):
    def change():
        repo.write("src/auth/z.py", "x\n")
        repo.write("src/auth/a.py", "x\n")

    facts = compute(repo, change)
    lines = risk_facts.render(facts).split("\n")
    assert "- protected_paths_changed: src/auth/a.py | src/auth/z.py" in lines
    assert "- work_tracking_at_base: true" in lines
    assert "- migrations_changed: none" in lines
    assert "- test_count_before: none" in lines


def test_render_neutralizes_newlines_in_paths(repo):
    facts = compute(repo, lambda: repo.write("a\n- level: low\nb.tf", "x\n"))
    text = risk_facts.render(facts)
    assert sum(1 for line in text.split("\n") if line.startswith("- level:")) == 1


def verified(repo, change, previous="low", trusted="low", edit=None):
    path, head = head_of(repo, change)
    text = risk_facts.render(risk_facts.compute(path, "main", head, previous_level=previous))
    if edit:
        text = edit(text, head, path)
    body = f"Some description\n\n{text}\n\nMore text\n"
    return path, head, text, risk_facts.verify(path, body, head, "main", trusted)


def small(repo):
    return lambda: repo.write("src/app.py", "print('b')\n")


def test_verify_accepts_untouched_block(repo):
    *_, result = verified(repo, small(repo))
    assert result.ok, result.message


def test_verify_accepts_crlf_body(repo):
    path, head = head_of(repo, small(repo))
    text = risk_facts.render(risk_facts.compute(path, "main", head)).replace("\n", "\r\n")
    assert risk_facts.verify(path, f"x\r\n{text}\r\n", head, "main", "low").ok


def test_verify_edited_visible_field_fails(repo):
    *_, result = verified(
        repo, small(repo), edit=lambda t, h, p: t.replace("- lines_changed: 2", "- lines_changed: 0")
    )
    assert not result.ok
    assert result.message == "facts differ from the recomputed facts"


def test_verify_edited_hash_fails(repo):
    *_, result = verified(
        repo, small(repo), edit=lambda t, h, p: re.sub(r"sha256=\w+", "sha256=" + "0" * 64, t)
    )
    assert not result.ok
    assert result.message == "hash differs from the recomputed hash"


def test_verify_edited_volatile_line_still_passes(repo):
    *_, result = verified(
        repo,
        small(repo),
        edit=lambda t, h, p: re.sub(r"- test_count_after: .*", "- test_count_after: 7", t),
    )
    assert result.ok, result.message


def test_verify_extra_line_fails(repo):
    *_, result = verified(
        repo, small(repo), edit=lambda t, h, p: t.replace("<!-- /risk", "- extra: 1\n<!-- /risk")
    )
    assert not result.ok
    assert result.message == "facts differ from the recomputed facts"


def test_verify_missing_block_fails(repo):
    path, head = head_of(repo, small(repo))
    result = risk_facts.verify(path, "no block here", head, "main", "low")
    assert not result.ok
    assert result.message == "no risk-facts block"


def test_verify_new_commit_fails_with_head_moved(repo):
    path, _head, text, result = verified(repo, small(repo))
    assert result.ok
    repo.write("src/app.py", "print('c')\n")
    new_head = repo.commit_all("more")
    again = risk_facts.verify(path, text, new_head, "main", "low")
    assert not again.ok
    assert again.message == "head moved, render again"


def test_verify_raised_previous_level_passes(repo):
    *_, result = verified(repo, small(repo), previous="high", trusted="high")
    assert result.ok, result.message


def test_verify_header_level_higher_than_trusted_passes(repo):
    *_, result = verified(repo, small(repo), previous="high", trusted="low")
    assert result.ok, result.message


def test_verify_lowered_previous_level_fails(repo):
    *_, result = verified(repo, small(repo), previous="low", trusted="high")
    assert not result.ok
    assert result.message == "previous level lower than trusted level"


def test_verify_header_edited_high_to_low_fails(repo):
    *_, result = verified(
        repo,
        small(repo),
        previous="high",
        trusted="high",
        edit=lambda t, h, p: t.replace("previous_level=high", "previous_level=low", 1),
    )
    assert not result.ok
    assert result.message == "previous level lower than trusted level"


def test_verify_forged_base_fails(repo):
    *_, result = verified(
        repo,
        small(repo),
        edit=lambda t, h, p: re.sub(r" base=\w+", f" base={h}", t, count=1),
    )
    assert not result.ok
    assert result.message == "base does not match"


def test_verify_base_moved_fails(repo):
    path, head, text, result = verified(repo, small(repo))
    assert result.ok
    repo.git("checkout", "main")
    repo.write("README", "new\n")
    repo.commit_all("main moved")
    again = risk_facts.verify(path, text, head, "main", "low")
    assert not again.ok
    assert again.message == "base moved, render again"


def test_verify_unknown_base_ref_fails_closed(repo):
    path, head, text, _ = verified(repo, small(repo))
    result = risk_facts.verify(path, text, head, "no-such-ref", "low")
    assert not result.ok
    assert result.message == "base not found"
