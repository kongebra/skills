import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_FILES = sorted((ROOT / "skills").glob("*/SKILL.md"))


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path} has no frontmatter"
    end = lines.index("---", 1)
    data = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()
    return data


def git_ls_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def test_skills_exist():
    assert SKILL_FILES


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_each_skill_has_matching_name(path):
    meta = frontmatter(path)
    assert meta.get("name") == path.parent.name
    assert meta.get("description")


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_user_invoked_skills_have_codex_policy(path):
    if frontmatter(path).get("disable-model-invocation") != "true":
        pytest.skip("skill is model-invoked")
    policy = path.parent / "agents" / "openai.yaml"
    assert policy.is_file()
    assert "allow_implicit_invocation: false" in policy.read_text(encoding="utf-8")


def test_no_working_files_tracked():
    banned = ("docs/superpowers/", ".agent-work/", ".superpowers/")
    bad = [f for f in git_ls_files() if f.startswith(banned)]
    assert bad == []


def test_k_common_pyproject_has_no_dependencies():
    data = tomllib.loads((ROOT / "skills/k-common/pyproject.toml").read_text())
    project = data["project"]
    assert project["name"] == "kcommon"
    assert project["requires-python"] == ">=3.11"
    assert project.get("dependencies", []) == []


def test_root_pyproject_links_k_common_editable():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    dev = data["dependency-groups"]["dev"]
    assert any(str(d).startswith("pytest") for d in dev)
    source = data["tool"]["uv"]["sources"]["kcommon"]
    assert source["path"] == "skills/k-common"
    assert source["editable"] is True
    assert "uv.lock" in git_ls_files()
