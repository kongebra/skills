"""Compute, render, and verify the risk facts block of a change.

The level rules, the thresholds, and the owners all come from the base ref tip, never from
the head or the working tree. The level never goes down. An unknown base raises
BaseNotFound, and the CLI exits 2 (fail closed).
"""

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

from kcommon import agents_md, constants, gitutil, globs
from kcommon.agents_md import Thresholds
from kcommon.gitutil import BaseNotFound, GitError

Level = Literal["low", "medium", "high"]

LEVELS: tuple[Level, ...] = ("low", "medium", "high")
_RANK = {level: rank for rank, level in enumerate(LEVELS)}
VOLATILE_FIELDS = ("last_authors", "test_count_before", "test_count_after")

_DIFF_ARGS = ("-c", "core.quotePath=false", "diff", "--no-ext-diff", "-M")
_HEADER = re.compile(
    r"^<!-- risk-facts base=(?P<base>\S+) base_tip=(?P<tip>\S+) head=(?P<head>\S+) "
    r"previous_level=(?P<level>\S+) sha256=(?P<hash>\S+) -->$"
)
_CLOSING = "<!-- /risk-facts -->"
_USAGE = (
    "usage: k.py risk_facts --base REF --head REF [--previous-level L]\n"
    "                       [--test-count-before N] [--test-count-after N]\n"
    "       k.py risk_facts --verify FILE --head-sha SHA --base-ref REF "
    "--trusted-previous-level L"
)


@dataclass(frozen=True)
class RiskFacts:
    level: Level
    level_reasons: list[str]
    base_sha: str
    base_tip: str
    head_sha: str
    previous_level: Level
    work_tracking_at_base: bool
    protected_paths_changed: list[str]
    dependency_files_changed: list[str]
    migrations_changed: list[str]
    ci_infra_changed: list[str]
    guardrail_files_changed: list[str]
    deleted_tests: list[str]
    skipped_tests_added: list[str]
    test_count_before: int | None
    test_count_after: int | None
    lines_changed: int
    files_touched: int
    owner_teams_touched: list[str]
    test_to_prod_ratio: float | None
    last_authors: list[str]


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    message: str


@dataclass(frozen=True)
class _Change:
    status: str
    path: str
    old: str | None = None

    @property
    def entry(self) -> str:
        return self.path if self.old is None else f"{self.old} -> {self.path}"

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.path,) if self.old is None else (self.old, self.path)


def _parse_name_status(out: str) -> list[_Change]:
    tokens = out.split("\0")
    changes: list[_Change] = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if not status:
            i += 1
            continue
        if status[0] in "RC" and i + 2 < len(tokens):
            changes.append(_Change(status[0], tokens[i + 2], tokens[i + 1]))
            i += 3
        elif i + 1 < len(tokens):
            changes.append(_Change(status[0], tokens[i + 1]))
            i += 2
        else:
            break
    return changes


def _parse_numstat(out: str) -> dict[str, int]:
    """Changed lines of each text file, keyed by the new path. A binary file counts 0."""
    tokens = out.split("\0")
    counts: dict[str, int] = {}
    i = 0
    while i < len(tokens):
        parts = tokens[i].split("\t", 2)
        if len(parts) < 3:
            i += 1
            continue
        added, deleted, rest = parts
        if rest == "":
            path = tokens[i + 2] if i + 2 < len(tokens) else ""
            i += 3
        else:
            path = rest
            i += 1
        counts[path] = 0 if added == "-" or deleted == "-" else int(added) + int(deleted)
    return counts


def _skipped_tests(patch: str) -> list[str]:
    """Entries `<path>: <marker regex>` for the added lines that match a skip marker."""
    found: list[str] = []
    path: str | None = None
    in_hunk = False
    for line in patch.split("\n"):
        if line.startswith("diff --git "):
            path, in_hunk = None, False
        elif not in_hunk and line.startswith("+++ "):
            name = line[4:].rstrip("\t")
            path = name[2:] if name.startswith("b/") else None
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and path is not None and line.startswith("+"):
            for marker in constants.SKIP_MARKERS:
                entry = f"{path}: {marker}"
                if entry not in found and re.search(marker, line[1:]):
                    found.append(entry)
    return found


def _owner_rules(text: str | None) -> list[tuple[str, list[str]]]:
    rules: list[tuple[str, list[str]]] = []
    for line in (text or "").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pattern, *owners = stripped.split()
        rules.append((pattern, owners))
    return rules


def _owners_of(rules: list[tuple[str, list[str]]], path: str) -> list[str]:
    owners: list[str] = []
    for pattern, rule_owners in rules:
        if globs.match(pattern, path):
            owners = rule_owners
    return owners


def _codeowners_at(repo: Path, ref: str) -> str | None:
    for candidate in constants.CODEOWNERS_PATHS:
        text = gitutil.show(repo, ref, candidate)
        if text is not None:
            return text
    return None


def _matching(changes: list[_Change], patterns: tuple[str, ...] | list[str]) -> list[str]:
    return sorted(
        {
            c.entry
            for c in changes
            if any(globs.match(p, path) for p in patterns for path in c.paths)
        }
    )


def _is_test(path: str) -> bool:
    return any(globs.match(g, path) for g in constants.TEST_GLOBS)


def _last_authors(repo: Path, base_sha: str, changes: list[_Change]) -> list[str]:
    authors: set[str] = set()
    paths = {p for c in changes for p in c.paths}
    for path in sorted(paths):
        out = gitutil.run(
            repo, "--literal-pathspecs", "log", "-1", "--format=%aN", base_sha, "--", path
        ).strip()
        if out:
            authors.add(out)
    return sorted(authors)


def compute(
    repo: Path,
    base: str,
    head: str,
    previous_level: Level = "low",
    test_count_before: int | None = None,
    test_count_after: int | None = None,
) -> RiskFacts:
    base_sha = gitutil.merge_base(repo, base, head)
    try:
        base_tip = gitutil.rev_parse(repo, base)
        head_sha = gitutil.rev_parse(repo, head)
    except GitError as exc:
        raise BaseNotFound(str(exc)) from exc

    numstat = gitutil.run(repo, *_DIFF_ARGS, "--numstat", "-z", base_sha, head_sha, "--")
    name_status = gitutil.run(repo, *_DIFF_ARGS, "--name-status", "-z", base_sha, head_sha, "--")
    patch = gitutil.run(repo, *_DIFF_ARGS, "-U0", base_sha, head_sha, "--")

    changes = _parse_name_status(name_status)
    line_counts = _parse_numstat(numstat)
    lines_changed = sum(line_counts.values())
    test_lines = sum(n for p, n in line_counts.items() if _is_test(p))
    prod_lines = lines_changed - test_lines
    ratio = round(test_lines / prod_lines, 2) if prod_lines else None

    deleted_tests = sorted(
        c.entry
        for c in changes
        if (c.status == "D" and _is_test(c.path))
        or (c.status == "R" and c.old is not None and _is_test(c.old) and not _is_test(c.path))
    )

    work_tracking, _ = agents_md.load(repo, base_tip)
    thresholds = work_tracking.thresholds if work_tracking else Thresholds()
    protected = (work_tracking.protected_paths or ()) if work_tracking else ()
    protected_changed = _matching(changes, protected)
    guardrail_changed = _matching(changes, constants.GUARDRAIL_GLOBS)
    dependency_changed = _matching(changes, constants.DEPENDENCY_GLOBS)
    migrations_changed = _matching(changes, constants.MIGRATION_GLOBS)
    ci_infra_changed = _matching(changes, (*constants.CI_GLOBS, *constants.INFRA_GLOBS))

    rules = _owner_rules(_codeowners_at(repo, base_tip))
    owner_teams = sorted({o for c in changes for p in c.paths for o in _owners_of(rules, p)})

    level: Level = previous_level
    reasons: list[str] = []

    def fire(target: Level, reason: str) -> None:
        nonlocal level
        reasons.append(reason)
        if _RANK[target] > _RANK[level]:
            level = target

    for entry in protected_changed:
        fire("high", f"protected path: {entry}")
    for entry in guardrail_changed:
        fire("high", f"guardrail file: {entry}")
    for entry in dependency_changed:
        fire("high", f"dependency file: {entry}")
    for entry in migrations_changed:
        fire("high", f"migration: {entry}")
    for entry in ci_infra_changed:
        fire("high", f"ci or infrastructure: {entry}")
    if lines_changed > thresholds.high_lines:
        fire("high", f"lines changed {lines_changed} > {thresholds.high_lines}")
    if lines_changed > thresholds.medium_lines:
        fire("medium", f"lines changed {lines_changed} > {thresholds.medium_lines}")
    if len(owner_teams) > thresholds.medium_owner_teams:
        fire("medium", f"owner teams {len(owner_teams)} > {thresholds.medium_owner_teams}")
    if work_tracking is None:
        fire("medium", "no work tracking section at base")
    elif work_tracking.protected_paths is None:
        fire("medium", "no protected paths line at base")
    if previous_level != "low":
        reasons.append(f"previous level {previous_level}")

    return RiskFacts(
        level=level,
        level_reasons=reasons,
        base_sha=base_sha,
        base_tip=base_tip,
        head_sha=head_sha,
        previous_level=previous_level,
        work_tracking_at_base=work_tracking is not None,
        protected_paths_changed=protected_changed,
        dependency_files_changed=dependency_changed,
        migrations_changed=migrations_changed,
        ci_infra_changed=ci_infra_changed,
        guardrail_files_changed=guardrail_changed,
        deleted_tests=deleted_tests,
        skipped_tests_added=_skipped_tests(patch),
        test_count_before=test_count_before,
        test_count_after=test_count_after,
        lines_changed=lines_changed,
        files_touched=len(changes),
        owner_teams_touched=owner_teams,
        test_to_prod_ratio=ratio,
        last_authors=_last_authors(repo, base_sha, changes),
    )


def _clean(text: str) -> str:
    """Keep one value on one line, so a path cannot forge a field line."""
    return text.replace("\r", "\\r").replace("\n", "\\n")


def _value(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return _clean(" | ".join(sorted(value))) if value else "none"
    return _clean(str(value))


def _field_lines(facts: RiskFacts) -> list[str]:
    return [f"- {f.name}: {_value(getattr(facts, f.name))}" for f in fields(facts)]


def _stable(lines: list[str]) -> list[str]:
    return [
        line for line in lines if not any(line.startswith(f"- {v}:") for v in VOLATILE_FIELDS)
    ]


def _hash(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(_stable(lines)).encode("utf-8")).hexdigest()


def render(facts: RiskFacts) -> str:
    lines = _field_lines(facts)
    header = (
        f"<!-- risk-facts base={facts.base_sha} base_tip={facts.base_tip} "
        f"head={facts.head_sha} previous_level={facts.previous_level} sha256={_hash(lines)} -->"
    )
    return "\n".join([header, *lines, _CLOSING])


def _extract_block(pr_body: str) -> tuple[re.Match[str], list[str]] | str:
    """The header match and the field lines of the one block, or an error message."""
    lines = pr_body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("<!-- risk-facts ")]
    if not starts:
        return "no risk-facts block"
    if len(starts) > 1:
        return "more than one risk-facts block"
    start = starts[0]
    header = _HEADER.match(lines[start])
    if header is None:
        return "malformed risk-facts header"
    for end in range(start + 1, len(lines)):
        if lines[end] == _CLOSING:
            return header, lines[start + 1 : end]
    return "risk-facts block has no closing line"


def verify(
    repo: Path,
    pr_body: str,
    head_sha: str,
    base_ref: str,
    trusted_previous_level: Level,
) -> VerifyResult:
    block = _extract_block(pr_body)
    if isinstance(block, str):
        return VerifyResult(False, block)
    header, body_lines = block
    recorded_level = header["level"]
    if recorded_level not in _RANK:
        return VerifyResult(False, "malformed risk-facts header")
    if trusted_previous_level not in _RANK:
        return VerifyResult(False, "trusted previous level is not low, medium, or high")

    try:
        head = gitutil.rev_parse(repo, head_sha)
    except GitError:
        return VerifyResult(False, "head not found")
    if header["head"] != head:
        return VerifyResult(False, "head moved, render again")

    try:
        tip = gitutil.rev_parse(repo, base_ref)
    except GitError:
        return VerifyResult(False, "base not found")
    if header["tip"] != tip:
        return VerifyResult(False, "base moved, render again")

    try:
        merge_base = gitutil.merge_base(repo, base_ref, head)
    except BaseNotFound:
        return VerifyResult(False, "base not found")
    if header["base"] != merge_base:
        return VerifyResult(False, "base does not match")

    if _RANK[recorded_level] < _RANK[trusted_previous_level]:
        return VerifyResult(False, "previous level lower than trusted level")

    try:
        facts = compute(repo, base_ref, head, recorded_level)  # type: ignore[arg-type]
    except GitError as exc:
        return VerifyResult(False, f"cannot compute facts: {exc}")
    fresh_lines = _field_lines(facts)
    if _stable(body_lines) != _stable(fresh_lines):
        return VerifyResult(False, "facts differ from the recomputed facts")
    if header["hash"] != _hash(fresh_lines):
        return VerifyResult(False, "hash differs from the recomputed hash")
    return VerifyResult(True, "ok")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # type: ignore[override]
        raise ValueError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(add_help=False)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--previous-level", choices=LEVELS, default="low")
    parser.add_argument("--test-count-before", type=int)
    parser.add_argument("--test-count-after", type=int)
    parser.add_argument("--verify")
    parser.add_argument("--head-sha")
    parser.add_argument("--base-ref")
    parser.add_argument("--trusted-previous-level", choices=LEVELS)
    return parser


def main(argv: list[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(_USAGE)
        return 0
    try:
        args = _build_parser().parse_args(argv)
        repo = Path.cwd()
        if args.verify is not None:
            if not (args.head_sha and args.base_ref and args.trusted_previous_level):
                raise ValueError("--verify needs --head-sha, --base-ref, --trusted-previous-level")
            body = Path(args.verify).read_text(encoding="utf-8")
            result = verify(repo, body, args.head_sha, args.base_ref, args.trusted_previous_level)
            print(result.message, file=sys.stdout if result.ok else sys.stderr)
            return 0 if result.ok else 1
        if not (args.base and args.head):
            raise ValueError("--base and --head are required")
        facts = compute(
            repo, args.base, args.head, args.previous_level,
            args.test_count_before, args.test_count_after,
        )
    except ValueError as exc:
        print(f"{exc}\n{_USAGE}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cannot read file: {exc}", file=sys.stderr)
        return 2
    except GitError as exc:
        print(f"base not found, failing closed: {exc}" if isinstance(exc, BaseNotFound) else exc,
              file=sys.stderr)
        return 2
    print(render(facts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
