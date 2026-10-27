"""Preflight check: is this repo and machine ready for the k- skills.

Eight checks, always in the same order, each giving one entry. The CLI exits 1 when any
entry is `fail`. A `warn` does not fail.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kcommon import agents_md, constants, gitutil, globs
from kcommon.gitutil import GitError

Status = Literal["ok", "warn", "fail"]

CLI_TIMEOUT_SECONDS = 10
_AGENTS = ("claude-code", "copilot-cli")
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]  # the k-common folder
_USAGE = (
    "usage: k.py preflight --agent claude-code|copilot-cli [--home PATH] "
    "[--skills-root PATH] [--last-known-good PATH]"
)


@dataclass(frozen=True)
class PreflightEntry:
    check: str
    status: Status
    message: str


@dataclass(frozen=True)
class PreflightReport:
    entries: list[PreflightEntry]

    @property
    def failed(self) -> bool:
        return any(e.status == "fail" for e in self.entries)


def _k_common(skills_root: Path) -> PreflightEntry:
    folder = skills_root / "k-common" / "scripts" / "kcommon"
    if folder.is_dir():
        return PreflightEntry("k-common", "ok", f"found {folder}")
    return PreflightEntry("k-common", "fail", f"{folder} does not exist")


def _work_tracking(repo: Path) -> tuple[PreflightEntry, list[str]]:
    """The entry, and the CLI values the section names."""
    tracking, warnings = agents_md.load(repo, "HEAD")
    if tracking is None:
        detail = f" ({'; '.join(warnings)})" if warnings else ""
        return PreflightEntry(
            "work-tracking", "fail", f"no usable '## Work tracking' section in AGENTS.md at HEAD{detail}"
        ), []
    clis = [c for c in (tracking.board_cli, tracking.code_host_cli) if c]
    if warnings:
        return PreflightEntry("work-tracking", "warn", "; ".join(warnings)), clis
    return PreflightEntry("work-tracking", "ok", "section found at HEAD"), clis


def _clis(clis: list[str]) -> PreflightEntry:
    problems: list[str] = []
    for cli in clis:
        words = cli.split()
        if not words:
            problems.append("empty CLI value")
            continue
        first = words[0]
        if "/" in first or "\\" in first or "." in first:
            problems.append(f"'{cli}' is not a bare command name")
            continue
        found = shutil.which(first)
        if found is None:
            problems.append(f"'{first}' is not on PATH")
            continue
        try:
            result = subprocess.run(
                [found, *words[1:], "--version"],
                capture_output=True,
                check=False,
                timeout=CLI_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            problems.append(f"'{cli} --version' could not run: {exc}")
            continue
        if result.returncode != 0:
            problems.append(f"'{cli} --version' exited {result.returncode}")
    if problems:
        return PreflightEntry("clis", "fail", "; ".join(problems))
    if not clis:
        return PreflightEntry("clis", "ok", "the section names no CLI")
    return PreflightEntry("clis", "ok", f"{', '.join(clis)} answered --version")


def _ci(repo: Path) -> PreflightEntry:
    try:
        listing = gitutil.run(repo, "ls-tree", "-r", "--name-only", "-z", "HEAD")
    except GitError as exc:
        return PreflightEntry("ci", "warn", f"cannot list files at HEAD ({exc}), so no CI file is known")
    for path in listing.split("\0"):
        if path and any(globs.match(glob, path) for glob in constants.CI_GLOBS):
            return PreflightEntry("ci", "ok", f"found {path}")
    return PreflightEntry("ci", "warn", "the repo has no CI file, so a risk gate cannot run")


def _is_repo_gitignore(source: str) -> bool:
    if source.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", source):
        return False
    return source == ".gitignore" or source.endswith("/.gitignore")


def _ignored_paths(repo: Path) -> PreflightEntry:
    problems: list[str] = []
    for probe in constants.IGNORE_PROBES:
        code, out = gitutil.run_code(repo, "check-ignore", "-v", probe)
        if code == 1:
            problems.append(f"{probe} is not ignored")
        elif code != 0:
            problems.append(f"{probe}: git check-ignore failed (exit {code})")
        else:
            # Output is "<source>:<line>:<pattern>\t<path>".
            source = out.split("\t", 1)[0].rsplit(":", 2)[0]
            if not _is_repo_gitignore(source):
                problems.append(f"{probe} is ignored by {source}, not by a repo .gitignore")
    if problems:
        return PreflightEntry("ignored-paths", "fail", "; ".join(problems))
    return PreflightEntry("ignored-paths", "ok", "every working path is ignored by the repo .gitignore")


def _skill_names(base: Path) -> list[str]:
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def _user_level_collisions(repo: Path, home: Path, claude_config_dir: Path | None) -> PreflightEntry:
    names = sorted({n for d in constants.REPO_SKILL_DIRS for n in _skill_names(repo / d)})
    user_dirs = [home / d for d in constants.USER_SKILL_DIRS]
    if claude_config_dir is not None:
        user_dirs.append(claude_config_dir / "skills")
    collisions = [
        f"{name} (also in {user_dir})"
        for name in names
        for user_dir in user_dirs
        if os.path.lexists(user_dir / name)
    ]
    if collisions:
        return PreflightEntry(
            "user-level-collisions", "fail", "skill name collides with a user-level skill: " + "; ".join(collisions)
        )
    return PreflightEntry("user-level-collisions", "ok", "no repo skill name exists at user level")


def _parse_version(text: str) -> tuple[int, ...] | None:
    parts = text.strip().split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def _compare(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    width = max(len(a), len(b))
    a, b = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
    return (a > b) - (a < b)


class _Unreadable(Exception):
    pass


def _read_json(path: Path, strip_comments: bool = False) -> object | None:
    """Parsed JSON, None when the file is missing, _Unreadable when it cannot be parsed."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if strip_comments:
            text = "\n".join(line for line in text.split("\n") if not line.lstrip().startswith("//"))
        return json.loads(text)
    except (OSError, ValueError) as exc:
        raise _Unreadable(f"{path} cannot be read: {exc}") from exc


def _claude_records(home: Path, claude_config_dir: Path | None) -> list[str] | None:
    base = claude_config_dir if claude_config_dir is not None else home / ".claude"
    data = _read_json(base / "plugins" / "installed_plugins.json")
    if data is None:
        return []
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict):
        raise _Unreadable(f"{base / 'plugins' / 'installed_plugins.json'} has no plugins table")
    versions: list[str] = []
    for key, records in plugins.items():
        if key.split("@", 1)[0] != "superpowers" or not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict):
                versions.append(str(record.get("version", "")))
    return versions


def _copilot_records(home: Path, copilot_home: Path | None) -> list[str]:
    base = copilot_home if copilot_home is not None else home / ".copilot"
    data = _read_json(base / "config.json", strip_comments=True)
    if data is None:
        return []
    plugins = data.get("installedPlugins") if isinstance(data, dict) else None
    if not isinstance(plugins, list):
        return []
    return [
        str(p.get("version", ""))
        for p in plugins
        if isinstance(p, dict) and str(p.get("name", "")).split("@", 1)[0] == "superpowers"
    ]


def _superpowers_version(
    agent: str,
    home: Path,
    last_known_good: dict,
    claude_config_dir: Path | None,
    copilot_home: Path | None,
) -> PreflightEntry:
    name = "superpowers-version"
    tested = str(last_known_good["superpowers"]["tested_version"])
    tested_parts = _parse_version(tested)
    try:
        if agent == "claude-code":
            found = _claude_records(home, claude_config_dir)
        elif agent == "copilot-cli":
            found = _copilot_records(home, copilot_home)
        else:
            return PreflightEntry(name, "warn", f"no version reader for agent '{agent}': version unknown")
    except _Unreadable as exc:
        return PreflightEntry(name, "warn", f"version unknown: {exc}")
    if not found:
        return PreflightEntry(name, "fail", "superpowers is not installed")
    distinct = list(dict.fromkeys(found))
    if len(distinct) > 1:
        return PreflightEntry(
            name,
            "warn",
            f"superpowers records disagree: {' and '.join(distinct)} "
            f"(the first record wins at load time, tested {tested})",
        )
    installed = distinct[0]
    parts = _parse_version(installed)
    if parts is None or tested_parts is None:
        return PreflightEntry(name, "warn", f"cannot compare version '{installed}' with tested {tested}")
    order = _compare(parts, tested_parts)
    if order == 0:
        return PreflightEntry(name, "ok", f"superpowers {installed}")
    if order > 0:
        return PreflightEntry(name, "warn", f"untested superpowers version {installed} (tested {tested})")
    return PreflightEntry(name, "fail", f"superpowers {installed} is older than tested {tested}")


def _matt_skills(repo: Path, skills_root: Path) -> PreflightEntry:
    missing = [
        name
        for name in constants.MATT_SKILLS
        if not any((repo / d / name).is_dir() for d in constants.REPO_SKILL_DIRS)
        and not (skills_root / name).is_dir()
    ]
    if missing:
        return PreflightEntry("matt-skills", "fail", f"missing skill folder: {', '.join(missing)}")
    return PreflightEntry("matt-skills", "ok", "all required skill folders exist")


def run(
    repo: Path,
    home: Path,
    agent: str,
    last_known_good: dict,
    skills_root: Path,
    claude_config_dir: Path | None = None,
    copilot_home: Path | None = None,
) -> PreflightReport:
    work_tracking, clis = _work_tracking(repo)
    entries = [
        _k_common(skills_root),
        work_tracking,
        _clis(clis),
        _ci(repo),
        _ignored_paths(repo),
        _user_level_collisions(repo, home, claude_config_dir),
        _superpowers_version(agent, home, last_known_good, claude_config_dir, copilot_home),
        _matt_skills(repo, skills_root),
    ]
    return PreflightReport(entries)


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="k.py preflight", usage=_USAGE)
    parser.add_argument("--agent", required=True, choices=_AGENTS)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--skills-root", type=Path, default=_PACKAGE_ROOT.parent)
    parser.add_argument("--last-known-good", type=Path, default=_PACKAGE_ROOT / "last-known-good.json")
    return parser


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    try:
        pins = json.loads(args.last_known_good.read_text(encoding="utf-8"))
        str(pins["superpowers"]["tested_version"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"cannot read the version pins {args.last_known_good}: {exc}", file=sys.stderr)
        return 2
    report = run(
        Path.cwd(),
        args.home,
        args.agent,
        pins,
        args.skills_root,
        _env_path("CLAUDE_CONFIG_DIR"),
        _env_path("COPILOT_HOME"),
    )
    for entry in report.entries:
        print(f"{entry.status.upper():<4} {entry.check}: {entry.message}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
