"""Record the red run of one named test as evidence.

`record` runs a command that must select exactly one test, checks that the run failed,
and returns a RedRecord. It never writes a file. `main` is the only writer.

Known limit: a selected test that fails for an environment reason (for example a missing
fixture file) counts as red, because the script cannot tell the reason without a parser
for each framework. A deliberate fake command, such as a script that ignores its
arguments, or a hand-written record file, cannot be stopped by a local script either.
All these cases share one trust boundary. The test quality reviewer owns that risk and
reads the output tail of the record.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from kcommon import gitutil
from kcommon.constants import (
    EVIDENCE_HEAD_CHARS,
    EVIDENCE_TAIL_CHARS,
    RUN_TIMEOUT_SECONDS,
)
from kcommon.structure_check import parse_plan

Category = Literal["red", "missing-symbol", "syntax", "no-run"]

EXIT_NOT_FAILING = 3
EXIT_NO_BINDING = 4
EXIT_TIMEOUT = 5
EXIT_COMMAND_NOT_FOUND = 6
EXIT_DUPLICATE = 7


class NotFailing(Exception):
    exit_code = EXIT_NOT_FAILING


class NoBinding(Exception):
    exit_code = EXIT_NO_BINDING


class Timeout(Exception):
    exit_code = EXIT_TIMEOUT


class CommandNotFound(Exception):
    exit_code = EXIT_COMMAND_NOT_FOUND


class DuplicateTestId(Exception):
    exit_code = EXIT_DUPLICATE


def slug(test_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", test_id).strip("-").lower()


# --- Block extraction -------------------------------------------------------------

@dataclass(frozen=True)
class Block:
    first_line: int
    last_line: int
    sha256: str


_DECORATOR = re.compile(r"^\s*(?:@|\[[A-Za-z])")
_COMMENT_ONLY = re.compile(r"^\s*(?:#|//)")
_CLOSING_LINE = re.compile(r"^(?:\}|\}\);|\))$")
_OPENERS = "([{"
_CLOSERS = ")]}"


def _definition_patterns(name: str) -> list[re.Pattern[str]]:
    """Definition-line patterns. `name` is a regex for the test name."""
    return [re.compile(p) for p in (
        rf"^\s*(?:async\s+)?def\s+{name}(?!\w)",
        rf"^\s*func\s+{name}(?!\w)",
        rf"^\s*(?:[\w<>\[\],.]+\s+)+{name}\s*\(",
        rf"^\s*(?:it|test|describe)(?:\.(?:skip|only))?\(\s*[\"'`][^\"'`]*(?<!\w){name}(?!\w)",
        rf"^\s*(?:it|test)\.each\b.*[\"'`][^\"'`]*(?<!\w){name}(?!\w)",
    )]


def _any_definition_patterns() -> list[re.Pattern[str]]:
    return [re.compile(p) for p in (
        r"^\s*(?:async\s+)?def\s+\w+\b",
        r"^\s*func\s+\w+\b",
        r"^\s*(?:[\w<>\[\],.]+\s+)+\w+\s*\(",
        r"^\s*(?:it|test|describe)(?:\.(?:skip|only))?\(\s*[\"'`]",
        r"^\s*(?:it|test)\.each\b",
    )]


_ANY_DEFINITION = _any_definition_patterns()


def _is_definition(line: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(line) for p in patterns)


def _is_boundary(line: str) -> bool:
    return _is_definition(line, _ANY_DEFINITION) or bool(_DECORATOR.match(line))


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _balance(line: str) -> int:
    """Closing brackets add 1, opening brackets subtract 1, over the whole line."""
    return sum(line.count(c) for c in _CLOSERS) - sum(line.count(c) for c in _OPENERS)


def _starts_decorator(line: str) -> bool:
    return line.lstrip().startswith(("@", "["))


def _block_start(lines: list[str], def_index: int) -> int:
    """First line of the block: the definition line plus the decorator span above it."""
    start = def_index
    i = def_index - 1
    while i >= 0:
        line = lines[i]
        text = line.strip()
        if not text or _COMMENT_ONLY.match(line):
            break
        if _starts_decorator(line) and _balance(line) == 0:
            start = i
            i -= 1
            continue
        if text.rstrip(",").endswith(tuple(_CLOSERS)):
            top = _span_top(lines, i)
            if top is None:
                break
            start = top
            i = top - 1
            continue
        break
    return start


def _span_top(lines: list[str], bottom: int) -> int | None:
    """Walk up from the closing line of a multi-line span to the line that opens it."""
    depth = 0
    j = bottom
    while j >= 0:
        line = lines[j]
        if j != bottom and _is_definition(line, _ANY_DEFINITION):
            return None
        depth += _balance(line)
        if depth == 0 and _starts_decorator(line):
            return j
        j -= 1
    return None


def _block_end(lines: list[str], def_index: int) -> int:
    indent = _indent(lines[def_index])
    last = def_index
    for i in range(def_index + 1, len(lines)):
        line = lines[i]
        if not line.strip() or _COMMENT_ONLY.match(line):
            continue
        here = _indent(line)
        if indent == 0:
            if here == 0 and not _CLOSING_LINE.match(line.rstrip()):
                break
        elif here < indent or (here == indent and _is_boundary(line)):
            break
        last = i
    return last


def _split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").split("\n")


def _hash(block_lines: list[str]) -> str:
    cleaned = [line.rstrip(" \t\r") for line in block_lines]
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    return hashlib.sha256("\n".join(cleaned).encode("utf-8")).hexdigest()


def extract_block(text: str, test_id: str) -> Block | None:
    lines = _split_lines(text)
    patterns = _definition_patterns(re.escape(test_id))
    found = [i for i, line in enumerate(lines) if _is_definition(line, patterns)]
    if len(found) > 1:
        raise DuplicateTestId("duplicate test id")
    if not found:
        return None
    start = _block_start(lines, found[0])
    end = _block_end(lines, found[0])
    return Block(start + 1, end + 1, _hash(lines[start : end + 1]))


# --- Selector binding -------------------------------------------------------------

def _regex_escape(test_id: str) -> str:
    return re.sub(r"([\\.^$|?*+()\[\]{}])", r"\\\1", test_id)


def _flag_values(command: list[str], flags: tuple[str, ...]) -> list[str]:
    """Values given to any of `flags`, as `flag value` or `flag=value`."""
    values = []
    for i, arg in enumerate(command):
        for flag in flags:
            if arg == flag and i + 1 < len(command):
                values.append(command[i + 1])
            elif arg.startswith(flag + "="):
                values.append(arg[len(flag) + 1 :])
    return values


def _is_keyword_option(arg: str) -> bool:
    """`-k` and the attached form `-kexpr` select by substring."""
    return arg.startswith("-k") and not arg.startswith("--")


def binds(command: list[str], test_id: str, test_file: str) -> bool:
    if any(_is_keyword_option(arg) for arg in command):
        return False
    wanted_file = os.path.normpath(test_file)
    anchored = f"^{_regex_escape(test_id)}$"
    for arg in command:
        parts = arg.split("::")
        if len(parts) in (2, 3) and parts[-1] == test_id and os.path.normpath(parts[0]) == wanted_file:
            return True
        if not arg.startswith("-") and re.fullmatch(rf"\w+(?:\.\w+)*\.{re.escape(test_id)}", arg):
            return True
    if anchored in _flag_values(command, ("-t", "--testNamePattern")):
        return True
    if anchored in _flag_values(command, ("-run",)):
        return True
    for value in _flag_values(command, ("--filter",)):
        if value == f"Name={test_id}":
            return True
        if (
            value.startswith("FullyQualifiedName=")
            and not re.search(r"[~&|!()]", value)
            and value.endswith("." + test_id)
            and len(value) > len("FullyQualifiedName=") + len(test_id) + 1
        ):
            return True
    return False


# --- Classification ---------------------------------------------------------------

_SYNTAX = ("SyntaxError", "IndentationError", "error CS1002", "error CS1513", "TS1005")
_MISSING_SYMBOL = (
    "ModuleNotFoundError", "ImportError", "NameError", "AttributeError", "ReferenceError",
    "Cannot find module", "CS0103", "CS0246", "CS0117", "TS2304", "TS2305", "TS2339",
    "undefined:", "cannot find symbol",
)
_NO_RUN = (
    "No module named", "no tests ran", "collected 0 items", "No tests found", "not found:",
    "Build FAILED", "[build failed]",
)
_NO_RUN_PATTERN = re.compile(r"error (?:CS|TS)\d")
_NO_RUN_EXIT_CODES = (4, 5, 126, 127)


def classify(output: str, exit_code: int) -> Category:
    """Category of a failed run. Call it only for a non-zero exit code."""
    if any(marker in output for marker in _SYNTAX):
        return "syntax"
    if any(marker in output for marker in _MISSING_SYMBOL):
        return "missing-symbol"
    if (
        any(marker in output for marker in _NO_RUN)
        or _NO_RUN_PATTERN.search(output)
        or exit_code in _NO_RUN_EXIT_CODES
        or exit_code < 0
    ):
        return "no-run"
    return "red"


# --- Record -----------------------------------------------------------------------

@dataclass
class RedRecord:
    work_item: str
    acs: list[str]
    test_id: str
    test_file: str
    test_block_sha256: str | None
    test_block_lines: list[int] | None
    command: list[str]
    exit_code: int
    category: Category
    output_head: str
    output_tail: str
    output_truncated: bool
    head_at_record: str
    recorded_at: str


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _command_exists(command: list[str], repo: Path) -> bool:
    if not command or not command[0]:
        return False
    first = command[0]
    if os.sep in first:
        candidate = (repo / first) if not os.path.isabs(first) else Path(first)
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil.which(first, path=gitutil.git_env().get("PATH")) is not None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


def _plan_acs(plan_text: str, test_id: str) -> list[str]:
    acs: list[str] = []
    for task in parse_plan(plan_text):
        if test_id in task.tests:
            acs.extend(ac for ac in task.acs if ac not in acs)
    return acs


def record(
    work_item: str,
    test_id: str,
    test_file: Path,
    command: list[str],
    repo: Path,
    plan: Path,
) -> RedRecord:
    if not _command_exists(command, repo):
        raise CommandNotFound(f"command not found: {command[0] if command else ''}")
    if not binds(command, test_id, str(test_file)):
        raise NoBinding(f"no exact selector for {test_id}")
    file_text = _read_text(repo / test_file)
    block = extract_block(file_text, test_id) if file_text is not None else None

    try:
        result = subprocess.run(
            command,
            cwd=repo,
            env=gitutil.git_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise Timeout(f"command timed out after {RUN_TIMEOUT_SECONDS} seconds") from exc
    except OSError as exc:
        raise CommandNotFound(f"command could not start: {exc}") from exc
    if result.returncode == 0:
        raise NotFailing("the command exited 0, so the test did not fail")

    output = _ANSI.sub("", result.stdout.decode("utf-8", errors="replace"))
    category = classify(output, result.returncode)
    limit = EVIDENCE_HEAD_CHARS + EVIDENCE_TAIL_CHARS
    if len(output) <= limit:
        head, tail, truncated = output, "", False
    else:
        head, tail, truncated = output[:EVIDENCE_HEAD_CHARS], output[-EVIDENCE_TAIL_CHARS:], True

    plan_text = _read_text(repo / plan) or ""
    return RedRecord(
        work_item=work_item,
        acs=_plan_acs(plan_text, test_id),
        test_id=test_id,
        test_file=str(test_file),
        test_block_sha256=block.sha256 if block else None,
        test_block_lines=[block.first_line, block.last_line] if block else None,
        command=list(command),
        exit_code=result.returncode,
        category=category,
        output_head=head,
        output_tail=tail,
        output_truncated=truncated,
        head_at_record=gitutil.rev_parse(repo, "HEAD"),
        recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def evidence_dir(repo: Path, work_item: str) -> Path:
    return repo / ".agent-work" / work_item / "evidence"


def valid_work_item(work_item: str) -> bool:
    return (
        bool(work_item)
        and work_item not in (".", "..")
        and not re.search(r"[/\\\x00]", work_item)
    )


_USAGE = (
    "usage: red_record --work-item <id> --test-id <name> --test-file <path> --plan <path>"
    " -- <command...>\n"
    "Runs the command, which must select only the named test with an exact selector.\n"
    "Writes .agent-work/<id>/evidence/red-<slug>.json when the test fails.\n"
    "Exit codes: 3 test did not fail, 4 no exact selector, 5 timeout, 6 command not found,\n"
    "7 duplicate test id, 2 bad usage."
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # type: ignore[override]
        raise ValueError(message)


def main(argv: list[str]) -> int:
    own = argv[: argv.index("--")] if "--" in argv else argv
    if any(a in ("-h", "--help") for a in own):
        print(_USAGE)
        return 0
    if "--" not in argv or not argv[argv.index("--") + 1 :]:
        print(_USAGE, file=sys.stderr)
        return 2
    split = argv.index("--")
    parser = _Parser(add_help=False)
    for name in ("--work-item", "--test-id", "--test-file", "--plan"):
        parser.add_argument(name, required=True)
    try:
        args = parser.parse_args(argv[:split])
    except ValueError as exc:
        print(f"{exc}\n{_USAGE}", file=sys.stderr)
        return 2
    command = argv[split + 1 :]
    if not valid_work_item(args.work_item) or not slug(args.test_id):
        print("bad work item id or test id", file=sys.stderr)
        return 2
    repo = Path.cwd()
    try:
        result = record(
            args.work_item, args.test_id, Path(args.test_file), command, repo, Path(args.plan)
        )
    except (NotFailing, NoBinding, Timeout, CommandNotFound, DuplicateTestId) as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except gitutil.GitError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    target = evidence_dir(repo, args.work_item)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"red-{slug(args.test_id)}.json"
    path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    print(f"recorded {path} ({result.category})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
