import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_install_contract_copy_install_runs_preflight_help(tmp_path):
    if shutil.which("npx") is None or shutil.which("uv") is None:
        pytest.skip("npx or uv is missing")
    lkg = json.loads(
        (ROOT / "skills" / "k-common" / "last-known-good.json").read_text(encoding="utf-8")
    )
    version = lkg["skills_cli"]["version"]
    install = subprocess.run(
        ["npx", "--yes", f"skills@{version}", "add", str(ROOT), "--copy", "-s", "k-common", "-y"],
        cwd=tmp_path, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    found = list(tmp_path.rglob("k-common/scripts/kcommon/preflight.py"))
    assert found, "installed k-common has no preflight.py"
    k_common = found[0].parents[2]
    result = subprocess.run(
        ["uv", "run", "--no-project", "python",
         str(k_common / "scripts" / "k.py"), "preflight", "--help"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not (k_common / ".venv").exists()
    assert not (k_common / "uv.lock").exists()
