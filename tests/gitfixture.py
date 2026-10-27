"""Temporary git repos for tests. Never reads or writes the real git config."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

INHERITED_VARS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY")
GIT_ARGS = (
    "--no-pager",
    "-c", "user.name=k-test",
    "-c", "user.email=k-test@example.invalid",
    "-c", "commit.gpgsign=false",
    "-c", "core.hooksPath=/dev/null",
)


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in INHERITED_VARS}
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


@dataclass
class GitFixture:
    path: Path

    @classmethod
    def create(cls, base: Path) -> "GitFixture":
        path = Path(base) / "repo"
        path.mkdir(parents=True)
        fixture = cls(path)
        fixture.git("init", "-b", "main")
        return fixture

    def write(self, path: str, content: str | bytes) -> None:
        target = self.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *GIT_ARGS, *args],
            cwd=self.path, env=_env(), capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout

    def commit_all(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD").strip()
