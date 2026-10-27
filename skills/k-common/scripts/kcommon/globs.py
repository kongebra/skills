"""Gitignore-style path matching for repo-relative file paths."""

import re
from functools import lru_cache


def _segment_regex(segment: str) -> re.Pattern[str]:
    """Translate one pattern segment. Wildcards never cross a path separator."""
    out: list[str] = []
    i, n = 0, len(segment)
    while i < n:
        c = segment[i]
        if c == "*":
            while i + 1 < n and segment[i + 1] == "*":
                i += 1
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "\\" and i + 1 < n:
            i += 1
            out.append(re.escape(segment[i]))
        elif c == "[":
            j = i + 1
            if j < n and segment[j] in "!^":
                j += 1
            if j < n and segment[j] == "]":
                j += 1
            while j < n and segment[j] != "]":
                j += 1
            if j >= n:
                out.append(re.escape(c))
            else:
                body = segment[i + 1 : j]
                negate = body[:1] in ("!", "^")
                if negate:
                    body = body[1:]
                body = body.replace("\\", "\\\\")
                out.append("[" + ("^" if negate else "") + body + "]")
                i = j
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("".join(out), re.DOTALL)


@lru_cache(maxsize=512)
def _compile(pattern: str) -> tuple[bool, tuple[str, ...] | None]:
    """Return (dir_only, segments). Segments start with ** for an unanchored name."""
    dir_only = pattern.endswith("/")
    if dir_only:
        pattern = pattern[:-1]
    anchored = False
    if pattern.startswith("/"):
        pattern = pattern[1:]
        anchored = True
    if "/" in pattern:
        anchored = True
    segments = tuple(s for s in pattern.split("/") if s != "")
    if not segments:
        return dir_only, None
    if not anchored:
        segments = ("**", *segments)
    return dir_only, segments


def _match_segments(pats: tuple[str, ...], parts: tuple[str, ...]) -> bool:
    """Match whole segments. A ** segment matches zero or more segments, but a
    trailing ** needs at least one segment."""
    if not pats:
        return not parts
    head, rest = pats[0], pats[1:]
    if head == "**":
        if not rest:
            return len(parts) >= 1
        return any(_match_segments(rest, parts[k:]) for k in range(len(parts) + 1))
    if not parts:
        return False
    return bool(_segment_regex(head).fullmatch(parts[0])) and _match_segments(rest, parts[1:])


def match(pattern: str, path: str) -> bool:
    """True when the gitignore-style pattern matches the file path or one of its
    ancestor directories."""
    dir_only, segments = _compile(pattern)
    if segments is None:
        return False
    parts = tuple(p for p in path.split("/") if p != "")
    if not parts:
        return False
    last = len(parts) - 1 if dir_only else len(parts)
    return any(_match_segments(segments, parts[:k]) for k in range(1, last + 1))
