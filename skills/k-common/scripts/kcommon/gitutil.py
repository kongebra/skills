"""Hardened git calls. Every call uses --no-pager and a cleaned environment."""

import os
import subprocess
from pathlib import Path

from kcommon.constants import RUN_TIMEOUT_SECONDS

_INHERITED_VARS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY")
_DIFF_FLAGS = ("--no-color", "--src-prefix=a/", "--dst-prefix=b/")


class GitError(Exception):
    pass


class BaseNotFound(GitError):
    pass


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _INHERITED_VARS}
    if os.environ.get("K_GIT_HERMETIC") == "1":
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _harden(args: tuple[str, ...]) -> list[str]:
    """Add the diff flags after the subcommand when the subcommand is diff."""
    i = 0
    while i + 1 < len(args) and args[i] == "-c":
        i += 2
    if i < len(args) and args[i] == "diff":
        return [*args[: i + 1], *_DIFF_FLAGS, *args[i + 1 :]]
    return list(args)


def _call(repo: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[bytes]:
    cmd = ["git", "--no-pager", *_harden(args)]
    try:
        return subprocess.run(
            cmd,
            cwd=repo,
            env=git_env(),
            capture_output=True,
            check=False,
            timeout=RUN_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {' '.join(args)} could not run: {exc}") from exc


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def run(repo: Path, *args: str) -> str:
    result = _call(repo, args)
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({result.returncode}): {_text(result.stderr).strip()}"
        )
    return _text(result.stdout)


def run_code(repo: Path, *args: str) -> tuple[int, str]:
    result = _call(repo, args)
    return result.returncode, _text(result.stdout)


def run_bytes(repo: Path, *args: str) -> bytes:
    result = _call(repo, args)
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({result.returncode}): {_text(result.stderr).strip()}"
        )
    return result.stdout


def show(repo: Path, ref: str, path: str) -> str | None:
    """File text at a ref, or None when the file does not exist there."""
    result = _call(repo, ("show", f"{ref}:{path}"))
    if result.returncode != 0:
        return None
    return _text(result.stdout)


def rev_parse(repo: Path, ref: str) -> str:
    return run(repo, "rev-parse", "--verify", "--end-of-options", ref).strip()


def merge_base(repo: Path, base: str, head: str) -> str:
    try:
        base_sha = rev_parse(repo, base)
        head_sha = rev_parse(repo, head)
    except GitError as exc:
        raise BaseNotFound(str(exc)) from exc
    code, out = run_code(repo, "merge-base", base_sha, head_sha)
    if code != 0 or not out.strip():
        raise BaseNotFound(f"no merge base between {base} and {head}")
    return out.strip()
