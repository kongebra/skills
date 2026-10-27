import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.gitfixture import GitFixture

ROOT = Path(__file__).resolve().parent.parent


def _require_tools() -> None:
    missing = [tool for tool in ("npx", "uv") if shutil.which(tool) is None]
    if not missing:
        return
    message = f"missing tools: {', '.join(missing)}"
    if os.environ.get("CI"):
        pytest.fail(f"{message} (the install contract must run in CI)")
    pytest.skip(message)


def _install(project: Path, *mode: str) -> Path:
    lkg = json.loads(
        (ROOT / "skills" / "k-common" / "last-known-good.json").read_text(encoding="utf-8")
    )
    version = lkg["skills_cli"]["version"]
    install = subprocess.run(
        ["npx", "--yes", f"skills@{version}", "add", str(ROOT), *mode, "-s", "k-common", "-y"],
        check=False, cwd=project, capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=300,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    return project / ".claude" / "skills"


def _k(skills_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--no-project", "python",
         str(skills_root / "k-common" / "scripts" / "k.py"), *args],
        check=False, cwd=cwd, capture_output=True, text=True, timeout=120,
    )


@pytest.mark.parametrize(
    ("mode", "expect_symlink"),
    [(("--copy",), False), ((), True)],
    ids=["copy", "symlink"],
)
def test_install_contract(tmp_path, mode, expect_symlink):
    _require_tools()
    project = tmp_path / "project"
    project.mkdir()
    skills_root = _install(project, *mode)
    k_common = skills_root / "k-common"
    assert k_common.is_dir(), f"no k-common under {skills_root}"
    assert k_common.is_symlink() is expect_symlink

    sibling = skills_root / "k-other"
    sibling.mkdir()
    assert (sibling / ".." / "k-common" / "scripts" / "k.py").is_file()

    result = _k(skills_root, project, "preflight", "--help")
    assert result.returncode == 0, result.stderr

    repo = GitFixture.create(tmp_path)
    repo.write("app.py", "a = 1\n")
    repo.commit_all("base")
    repo.git("checkout", "-q", "-b", "feature")
    repo.write("app.py", "a = 2\n")
    head = repo.commit_all("change")
    result = _k(skills_root, repo.path, "risk_facts", "--base", "main", "--head", "HEAD")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0].startswith("<!-- risk-facts ")
    assert f"- head_sha: {head}" in lines
    assert "- lines_changed: 2" in lines
    assert lines[-1] == "<!-- /risk-facts -->"

    real = k_common.resolve()
    assert not (real / ".venv").exists()
    assert not (real / "uv.lock").exists()
