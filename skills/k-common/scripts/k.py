"""Launcher for the kcommon modules.

Usage: uv run --no-project python <skills-root>/k-common/scripts/k.py <module> ...
"""

import runpy
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: k.py <module> [arguments...]")
    module = sys.argv[1]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.argv = [f"kcommon.{module}", *sys.argv[2:]]
    runpy.run_module(f"kcommon.{module}", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
