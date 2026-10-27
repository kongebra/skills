import json
import subprocess
from pathlib import Path

import pytest
from kcommon import constants, preflight

ROOT = Path(__file__).resolve().parent.parent
K_PY = ROOT / "skills" / "k-common" / "scripts" / "k.py"
PINS = json.loads((ROOT / "skills" / "k-common" / "last-known-good.json").read_text())

AGENTS = """\
## Work tracking
- Board: Test (CLI: `git`)
- Code host: GitHub (CLI: `git`)
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
GITIGNORE = "docs/superpowers/\n.agent-work/\n.superpowers/\n"
CHECKS = [
    "k-common", "work-tracking", "clis", "ci", "ignored-paths",
    "user-level-collisions", "superpowers-version", "matt-skills",
]


def write_claude_plugins(config_dir: Path, records: dict[str, list[str]]) -> None:
    plugins = {
        key: [{"scope": "user", "version": v} for v in versions]
        for key, versions in records.items()
    }
    target = config_dir / "plugins" / "installed_plugins.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8")


@pytest.fixture(autouse=True)
def no_config_env(monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("COPILOT_HOME", raising=False)


@pytest.fixture
def env(tmp_path, git_repo):
    """A repo, a home, and a skills root that all pass preflight."""
    git_repo.write("AGENTS.md", AGENTS)
    git_repo.write(".github/workflows/ci.yml", "name: ci\n")
    git_repo.write(".gitignore", GITIGNORE)
    for name in constants.MATT_SKILLS:
        git_repo.write(f".agents/skills/{name}/SKILL.md", f"---\nname: {name}\n---\n")
    git_repo.commit_all("base")
    home = tmp_path / "home"
    write_claude_plugins(home / ".claude", {"superpowers@claude-plugins-official": ["7.0.1"]})
    skills_root = tmp_path / "skills"
    (skills_root / "k-common" / "scripts" / "kcommon").mkdir(parents=True)
    return type("Env", (), {"repo": git_repo, "home": home, "skills_root": skills_root})()


def run(env, agent="claude-code", **kwargs):
    kwargs.setdefault("claude_config_dir", None)
    report = preflight.run(env.repo.path, env.home, agent, PINS, env.skills_root, **kwargs)
    return {e.check: e for e in report.entries}


def run_cli(env, *extra, cwd=None):
    return subprocess.run(
        ["uv", "run", "--no-project", "python", str(K_PY), "preflight",
         "--agent", "claude-code", "--home", str(env.home), *extra],
        cwd=cwd or env.repo.path, capture_output=True, text=True, check=False,
    )


def test_all_checks_pass(env):
    report = preflight.run(env.repo.path, env.home, "claude-code", PINS, env.skills_root)
    assert [e.check for e in report.entries] == CHECKS
    assert [e.status for e in report.entries] == ["ok"] * 8, report.entries


def test_missing_k_common_fails(env, tmp_path):
    empty = tmp_path / "empty-root"
    empty.mkdir()
    result = run_cli(env, "--skills-root", str(empty))
    assert result.returncode == 1, result.stderr
    assert "FAIL" in result.stdout and "k-common" in result.stdout
    env.skills_root = empty
    assert run(env)["k-common"].status == "fail"


def test_missing_section_fails(env):
    env.repo.write("AGENTS.md", "# Nothing here\n")
    env.repo.commit_all("no section")
    assert run(env)["work-tracking"].status == "fail"


def test_section_with_warnings_warns(env):
    env.repo.write("AGENTS.md", AGENTS.replace("- Subagent budget: 18\n", "- Subagent budget: lots\n"))
    env.repo.commit_all("bad budget")
    entry = run(env)["work-tracking"]
    assert entry.status == "warn"
    assert "budget" in entry.message.lower()


def test_work_tracking_reads_head_not_working_tree(env):
    env.repo.write("AGENTS.md", "# gone\n")
    assert run(env)["work-tracking"].status == "ok"


def test_cli_with_path_fails(env):
    env.repo.write("AGENTS.md", AGENTS.replace("Test (CLI: `git`)", "Test (CLI: `./bin/x`)"))
    env.repo.commit_all("path cli")
    entry = run(env)["clis"]
    assert entry.status == "fail"
    assert "./bin/x" in entry.message


def test_cli_not_found_fails(env):
    env.repo.write("AGENTS.md", AGENTS.replace("Test (CLI: `git`)", "Test (CLI: `no-such-cli-k7`)"))
    env.repo.commit_all("missing cli")
    entry = run(env)["clis"]
    assert entry.status == "fail"
    assert "no-such-cli-k7" in entry.message


def test_cli_with_dotted_name_fails(env):
    env.repo.write("AGENTS.md", AGENTS.replace("Test (CLI: `git`)", "Test (CLI: `x.sh arg`)"))
    env.repo.commit_all("dotted cli")
    assert run(env)["clis"].status == "fail"


def test_ci_check_ignores_agents_md(tmp_path, git_repo):
    git_repo.write("AGENTS.md", "## Work tracking\n- CI: runs in GitHub Actions workflows\n")
    git_repo.commit_all("only agents")
    listing = git_repo.git("ls-files").split()
    assert listing == ["AGENTS.md"]
    env = type("Env", (), {"repo": git_repo, "home": tmp_path / "home", "skills_root": tmp_path})()
    entry = run(env)["ci"]
    assert entry.status == "warn"
    assert "no CI file" in entry.message


def test_no_ci_file_warns_and_cli_exits_zero(env):
    env.repo.git("rm", "-q", ".github/workflows/ci.yml")
    env.repo.commit_all("drop ci")
    result = run_cli(env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN" in result.stdout and "ci" in result.stdout
    assert "FAIL" not in result.stdout


def test_unignored_path_fails(env):
    env.repo.write(".gitignore", "docs/superpowers/\n.superpowers/\n")
    env.repo.commit_all("drop one")
    entry = run(env)["ignored-paths"]
    assert entry.status == "fail"
    assert ".agent-work/x" in entry.message


@pytest.mark.parametrize("source", ["excludes-file", "info-exclude"])
def test_globally_ignored_path_fails(env, tmp_path, source):
    env.repo.write(".gitignore", "")
    env.repo.commit_all("empty gitignore")
    if source == "excludes-file":
        excludes = tmp_path / "global-ignore"
        excludes.write_text(GITIGNORE, encoding="utf-8")
        env.repo.git("config", "core.excludesFile", str(excludes))
    else:
        info = env.repo.path / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "exclude").write_text(GITIGNORE, encoding="utf-8")
    entry = run(env)["ignored-paths"]
    assert entry.status == "fail"
    assert "docs/superpowers/x" in entry.message


def test_user_level_collision_fails(env):
    (env.home / ".claude" / "skills" / "grilling").mkdir(parents=True)
    entry = run(env)["user-level-collisions"]
    assert entry.status == "fail"
    assert "grilling" in entry.message


def test_claude_config_dir_is_honoured(env, tmp_path):
    config = tmp_path / "custom-claude"
    write_claude_plugins(config, {"superpowers@claude-plugins-official": ["7.0.1"]})
    (env.home / ".claude" / "plugins" / "installed_plugins.json").unlink()
    assert run(env)["superpowers-version"].status == "fail"
    assert run(env, claude_config_dir=config)["superpowers-version"].status == "ok"
    (config / "skills" / "domain-modeling").mkdir(parents=True)
    entry = run(env, claude_config_dir=config)["user-level-collisions"]
    assert entry.status == "fail"
    assert "domain-modeling" in entry.message


def test_claude_config_dir_from_environment(env, tmp_path, monkeypatch):
    config = tmp_path / "custom-claude"
    write_claude_plugins(config, {"superpowers@claude-plugins-official": ["7.0.1"]})
    (env.home / ".claude" / "plugins" / "installed_plugins.json").unlink()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    result = run_cli(env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK   superpowers-version" in result.stdout


def test_older_superpowers_version_fails(env):
    write_claude_plugins(env.home / ".claude", {"superpowers@claude-plugins-official": ["7.0.0"]})
    assert run(env)["superpowers-version"].status == "fail"


def test_not_installed_fails(env):
    write_claude_plugins(env.home / ".claude", {"other@market": ["1.0.0"]})
    assert run(env)["superpowers-version"].status == "fail"


def test_any_marketplace_is_accepted(env):
    write_claude_plugins(env.home / ".claude", {"superpowers@some-fork": ["7.0.1"]})
    assert run(env)["superpowers-version"].status == "ok"


def test_newer_superpowers_version_warns(env):
    write_claude_plugins(env.home / ".claude", {"superpowers@claude-plugins-official": ["7.1.0"]})
    entry = run(env)["superpowers-version"]
    assert entry.status == "warn"
    assert "untested superpowers version" in entry.message


def test_version_compare_is_numeric(env):
    write_claude_plugins(env.home / ".claude", {"superpowers@claude-plugins-official": ["7.0.10"]})
    assert run(env)["superpowers-version"].status == "warn"


def test_conflicting_records_warn(env):
    write_claude_plugins(
        env.home / ".claude",
        {"superpowers@claude-plugins-official": ["7.0.1"], "superpowers@fork": ["7.0.0"]},
    )
    entry = run(env)["superpowers-version"]
    assert entry.status == "warn"
    assert "7.0.1" in entry.message and "7.0.0" in entry.message


def write_copilot(home: Path, body: str) -> None:
    target = home / ".copilot" / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


COPILOT_JSONC = """\
// User settings
// This file is managed automatically.
{
  "installedPlugins": [
    {"name": "other", "version": "1.0.0", "marketplace": "x"},
    {"name": "superpowers", "version": "7.0.1", "marketplace": "claude-plugins-official"}
  ]
}
"""


def test_copilot_reader_parses_jsonc(env):
    write_copilot(env.home, COPILOT_JSONC)
    assert run(env, agent="copilot-cli")["superpowers-version"].status == "ok"
    write_copilot(env.home, COPILOT_JSONC.replace('"7.0.1"', '"7.0.0"'))
    assert run(env, agent="copilot-cli")["superpowers-version"].status == "fail"


def test_copilot_home_is_honoured(env, tmp_path):
    other = tmp_path / "copilot-elsewhere"
    other.mkdir()
    (other / "config.json").write_text(COPILOT_JSONC, encoding="utf-8")
    assert run(env, agent="copilot-cli")["superpowers-version"].status == "fail"
    assert run(env, agent="copilot-cli", copilot_home=other)["superpowers-version"].status == "ok"


def test_unreadable_record_file_warns(env):
    (env.home / ".claude" / "plugins" / "installed_plugins.json").write_text("{nope", encoding="utf-8")
    assert run(env)["superpowers-version"].status == "warn"


def test_unknown_agent_version_reader_warns(env):
    entry = run(env, agent="codex")["superpowers-version"]
    assert entry.status == "warn"
    assert "unknown" in entry.message


def test_missing_matt_skill_fails(env):
    env.repo.git("rm", "-rq", ".agents/skills/grill-with-docs")
    env.repo.commit_all("drop skill")
    entry = run(env)["matt-skills"]
    assert entry.status == "fail"
    assert "grill-with-docs" in entry.message


def test_matt_skill_in_skills_root_counts(env):
    env.repo.git("rm", "-rq", ".agents/skills/grill-with-docs")
    env.repo.commit_all("drop skill")
    (env.skills_root / "grill-with-docs").mkdir()
    assert run(env)["matt-skills"].status == "ok"
