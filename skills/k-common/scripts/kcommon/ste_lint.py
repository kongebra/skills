"""Lint Markdown against the team writing standard (ASD-STE100 subset)."""

import re
import sys
from dataclasses import dataclass
from typing import Literal

Rule = Literal["sentence-length", "semicolon", "dash"]

_SPAN = re.compile(r"`[^`]*`")
_MARKER = re.compile(r"\*\*\[[^\]]*\]\*\*")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_PLACEHOLDER = "\x00"


@dataclass(frozen=True)
class LintFinding:
    line: int
    rule: Rule
    text: str


def _skip_frontmatter(lines: list[str]) -> int:
    """Return the index of the first line after the frontmatter, or 0."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i + 1
    return 0


def _count_words(sentence: str) -> int:
    sentence = _MARKER.sub(" ", sentence)
    sentence = _SPAN.sub(_PLACEHOLDER, sentence)
    return len(sentence.split())


def lint(text: str, max_words: int = 25) -> list[LintFinding]:
    lines = text.splitlines()
    findings: list[LintFinding] = []
    in_fence = False
    # Prose lines are joined into paragraphs: (first line number, text).
    paragraph: list[tuple[int, str]] = []

    def flush() -> None:
        if not paragraph:
            return
        start = paragraph[0][0]
        joined = " ".join(part for _, part in paragraph)
        paragraph.clear()
        for sentence in _SENTENCE_END.split(joined):
            if _count_words(sentence) > max_words:
                findings.append(LintFinding(start, "sentence-length", sentence.strip()))

    for index in range(_skip_frontmatter(lines), len(lines)):
        number = index + 1
        line = lines[index]
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for char in ("–", "—"):
            if char in line:
                findings.append(LintFinding(number, "dash", line.strip()))
                break
        if not stripped or stripped.startswith(("#", "|")):
            flush()
            continue
        if ";" in _SPAN.sub("", line):
            findings.append(LintFinding(number, "semicolon", line.strip()))
        if _BULLET.match(line):
            flush()
        paragraph.append((number, _BULLET.sub("", line).strip()))
    flush()
    return sorted(findings, key=lambda f: f.line)


def main(argv: list[str]) -> int:
    if any(a in ("-h", "--help") for a in argv) or not argv:
        print("usage: ste_lint <file>...\nPrints one finding per line. Exits 1 on any finding.")
        return 0
    found = False
    for path in argv:
        with open(path, encoding="utf-8") as handle:
            for f in lint(handle.read()):
                found = True
                print(f"{path}:{f.line}: {f.rule}: {f.text}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
