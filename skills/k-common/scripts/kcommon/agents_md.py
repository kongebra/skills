"""Parser for the `## Work tracking` section of AGENTS.md. Never raises on bad input."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from kcommon import gitutil

SECTION_HEADING = "## Work tracking"

_KEY_LINE = re.compile(r"^- (?P<key>[A-Za-z][A-Za-z -]*): (?P<value>.*)$")
_NAMED_CLI = re.compile(r"^(?P<name>.+?)(?: \(CLI: `(?P<cli>[^`]+)`\))?$")
_FINDINGS = re.compile(r"^(?P<target>.+?), visibility: (?P<vis>public|private|unknown)$")
_INVARIANT = re.compile(r'^`(?P<glob>[^`]+)`: "(?P<text>.*)"$')
_SPAN = re.compile(r"`([^`]+)`")
_THRESHOLDS = re.compile(
    r"^medium_lines=(?P<ml>\d+), medium_owner_teams=(?P<mo>\d+), high_lines=(?P<hl>\d+)$"
)
_LIMITS = re.compile(
    r"^spec_rounds=(?P<sr>\d+), code_rounds=(?P<cr>\d+), spec_attackers_low=(?P<lo>\d+), "
    r"spec_attackers_medium=(?P<me>\d+), spec_attackers_high=(?P<hi>\d+)$"
)

_REQUIRED_KEYS = ("Board", "Code host", "Protected paths")
_KNOWN_KEYS = frozenset({
    "Board", "Code host", "Findings go to", "Link work items in PRs as", "Branch names",
    "Protected paths", "Invariant", "Risk thresholds", "Review limits", "Subagent budget",
    "Cross-vendor attacker", "Verification commands", "QA plan",
})


@dataclass(frozen=True)
class Thresholds:
    medium_lines: int = 300
    medium_owner_teams: int = 2
    high_lines: int = 800


def _default_attackers() -> dict[str, int]:
    return {"low": 2, "medium": 3, "high": 5}


@dataclass(frozen=True)
class ReviewLimits:
    spec_rounds: int = 3
    code_rounds: int = 2
    spec_attackers: dict[str, int] = field(default_factory=_default_attackers)


@dataclass(frozen=True)
class WorkTracking:
    board: str
    board_cli: str | None
    code_host: str
    code_host_cli: str | None
    findings_target: str
    findings_visibility: Literal["public", "private", "unknown"]
    link_format: str | None
    branch_names: str | None
    protected_paths: tuple[str, ...] | None
    invariants: dict[str, str]
    thresholds: Thresholds
    review_limits: ReviewLimits
    subagent_budget: int
    cross_vendor_attacker: bool
    verification_commands: tuple[str, ...]
    qa_plan: str | None


def _section_lines(text: str) -> list[str] | None:
    """Lines of the first Work tracking section outside a fence, or None."""
    lines = [line.replace("\r", "") for line in text.lstrip("﻿").split("\n")]
    in_fence = False
    start: int | None = None
    for index, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if start is None:
            if line.rstrip() == SECTION_HEADING:
                start = index + 1
        elif line.startswith("## "):
            return _without_fenced(lines[start:index])
    return None if start is None else _without_fenced(lines[start:])


def _without_fenced(lines: list[str]) -> list[str]:
    kept: list[str] = []
    in_fence = False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            kept.append(line)
    return kept


def parse(text: str) -> tuple[WorkTracking | None, list[str]]:
    lines = _section_lines(text)
    if lines is None:
        return None, []

    warnings: list[str] = []
    seen: set[str] = set()
    board = ("", None)
    code_host = ("", None)
    findings = ("", "unknown")
    link_format: str | None = None
    branch_names: str | None = None
    qa_plan: str | None = None
    protected: tuple[str, ...] | None = None
    verification: tuple[str, ...] = ()
    invariants: dict[str, str] = {}
    thresholds = Thresholds()
    limits = ReviewLimits()
    budget: int | None = None
    cross_vendor = False

    for line in lines:
        found = _KEY_LINE.match(line)
        if not found:
            continue
        key, value = found["key"], found["value"].strip()
        if key not in _KNOWN_KEYS:
            warnings.append(f"unknown key: {key}")
            continue
        if key != "Invariant":
            if key in seen:
                warnings.append(f"duplicate key: {key}")
                continue
            seen.add(key)

        ok = True
        if key in ("Board", "Code host"):
            m = _NAMED_CLI.match(value)
            if m:
                pair = (m["name"], m["cli"])
                if key == "Board":
                    board = pair
                else:
                    code_host = pair
            ok = m is not None
        elif key == "Findings go to":
            m = _FINDINGS.match(value)
            if m:
                findings = (m["target"], m["vis"])
            ok = m is not None
        elif key in ("Link work items in PRs as", "Branch names", "QA plan"):
            m = _SPAN.search(value)
            if m:
                if key == "Link work items in PRs as":
                    link_format = m[1]
                elif key == "Branch names":
                    branch_names = m[1]
                else:
                    qa_plan = m[1]
            ok = m is not None
        elif key in ("Protected paths", "Verification commands"):
            spans = tuple(_SPAN.findall(value))
            if spans:
                if key == "Protected paths":
                    protected = spans
                else:
                    verification = spans
            ok = bool(spans)
        elif key == "Invariant":
            m = _INVARIANT.match(value)
            if m:
                invariants[m["glob"]] = m["text"]
            ok = m is not None
        elif key == "Risk thresholds":
            m = _THRESHOLDS.match(value)
            if m:
                thresholds = Thresholds(int(m["ml"]), int(m["mo"]), int(m["hl"]))
            ok = m is not None
        elif key == "Review limits":
            m = _LIMITS.match(value)
            if m:
                limits = ReviewLimits(
                    int(m["sr"]), int(m["cr"]),
                    {"low": int(m["lo"]), "medium": int(m["me"]), "high": int(m["hi"])},
                )
            ok = m is not None
        elif key == "Subagent budget":
            ok = re.fullmatch(r"\d+", value) is not None
            if ok:
                budget = int(value)
        elif key == "Cross-vendor attacker":
            ok = value in ("on", "off")
            if ok:
                cross_vendor = value == "on"
        if not ok:
            warnings.append(f"malformed value: {key}")

    for key in _REQUIRED_KEYS:
        if key not in seen:
            warnings.append(f"missing key: {key}")

    if budget is None:
        budget = limits.spec_rounds * (limits.spec_attackers["high"] + 1)

    visibility: Literal["public", "private", "unknown"] = findings[1]  # type: ignore[assignment]
    return (
        WorkTracking(
            board=board[0],
            board_cli=board[1],
            code_host=code_host[0],
            code_host_cli=code_host[1],
            findings_target=findings[0],
            findings_visibility=visibility,
            link_format=link_format,
            branch_names=branch_names,
            protected_paths=protected,
            invariants=invariants,
            thresholds=thresholds,
            review_limits=limits,
            subagent_budget=budget,
            cross_vendor_attacker=cross_vendor,
            verification_commands=verification,
            qa_plan=qa_plan,
        ),
        warnings,
    )


def load(repo: Path, ref: str) -> tuple[WorkTracking | None, list[str]]:
    """Parse AGENTS.md as committed at the ref, never the working tree."""
    text = gitutil.show(repo, ref, "AGENTS.md")
    if text is None:
        return None, []
    return parse(text)
