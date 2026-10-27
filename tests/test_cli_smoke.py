import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "k-common" / "scripts"
CLI_MODULES = [
    "ste_lint",
    "structure_check",
    "red_record",
    "red_check",
    "risk_facts",
    "preflight",
]


@pytest.mark.parametrize("module", CLI_MODULES)
def test_help_exits_zero(module):
    if not (SCRIPTS / "kcommon" / f"{module}.py").exists():
        pytest.skip(f"{module} does not exist yet")
    result = subprocess.run(
        ["uv", "run", "--no-project", "python",
         "skills/k-common/scripts/k.py", module, "--help"],
        check=False, cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_no_cli_module_skipped():
    missing = [m for m in CLI_MODULES if not (SCRIPTS / "kcommon" / f"{m}.py").exists()]
    assert missing == []
