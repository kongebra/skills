import hashlib
import json
import sys
from pathlib import Path

import pytest
from kcommon import red_record
from kcommon.red_record import (
    CommandNotFound,
    DuplicateTestId,
    NoBinding,
    NotFailing,
    RedRecord,
    Timeout,
    binds,
    classify,
    extract_block,
    slug,
)

from tests.red_helpers import TEST_FILE, make_repo, pytest_command, runner_script

FIXTURE_A = """class T(unittest.TestCase):
    def test_a(self):
        self.assertEqual(add(1, 1), 2)

    def test_b(self):
        self.assertEqual(add(1, 2), 3)
"""

FIXTURE_B = FIXTURE_A.replace(
    "    def test_b(self):", '    @unittest.skip("later")\n    def test_b(self):'
)

FIXTURE_C = FIXTURE_A + '\nif __name__ == "__main__":\n    unittest.main()\n'

FIXTURE_D = """class T:
    def test_a(self):
        assert add(1, 1) == 2

    @pytest.mark.parametrize(
        "x, y",
        [(1, 2), (2, 3)],
    )
    def test_b(self, x, y):
        assert add(x, 1) == y
"""

FIXTURE_E = FIXTURE_A.replace(
    "    def test_b(self):", "    # about test_b\n    def test_b(self):"
)

FIXTURE_F = """def test_a():
    assert add(1, 1) == 2


def test_b():
    assert add(1, 2) == 3


result = add(1, 2)
print(result)
"""

FIXTURE_G = """package x

func TestAdd(t *testing.T) {
\tif Add(1, 1) != 2 {
\t\tt.Fatal("bad")
\t}
}

func TestSub(t *testing.T) {
\tif Sub(2, 1) != 1 {
\t\tt.Fatal("bad")
\t}
}
"""

CSHARP = """public class T
{
    [Fact]
    public void TestAdd()
    {
        Assert.Equal(2, Add(1, 1));
    }

    [Fact]
    public void TestSub()
    {
        Assert.Equal(1, Sub(2, 1));
    }
}
"""


def lines(text, test_id):
    block = extract_block(text, test_id)
    return None if block is None else (block.first_line, block.last_line)


def block_hash(text, test_id):
    return extract_block(text, test_id).sha256


def test_slug_formula():
    assert slug("test_add_negative") == "test-add-negative"
    assert slug("  Test Add!! ") == "test-add"
    assert slug("TestAdd") == "testadd"


def test_extract_block_fixture_a():
    assert lines(FIXTURE_A, "test_a") == (2, 3)
    assert lines(FIXTURE_A, "test_b") == (5, 6)
    assert extract_block(FIXTURE_A, "test_c") is None


def test_extract_block_decorator_changes_only_its_test():
    assert lines(FIXTURE_B, "test_a") == (2, 3)
    assert lines(FIXTURE_B, "test_b") == (5, 7)
    assert block_hash(FIXTURE_B, "test_a") == block_hash(FIXTURE_A, "test_a")
    assert block_hash(FIXTURE_B, "test_b") != block_hash(FIXTURE_A, "test_b")


def test_extract_block_last_test_before_module_code():
    assert lines(FIXTURE_C, "test_b") == (5, 6)
    assert block_hash(FIXTURE_C, "test_b") == block_hash(FIXTURE_A, "test_b")


def test_extract_block_multiline_decorator():
    assert lines(FIXTURE_D, "test_a") == (2, 3)
    assert lines(FIXTURE_D, "test_b") == (5, 10)
    changed = FIXTURE_D.replace("(2, 3)", "(2, 4)")
    assert block_hash(changed, "test_b") != block_hash(FIXTURE_D, "test_b")
    assert block_hash(changed, "test_a") == block_hash(FIXTURE_D, "test_a")


def test_extract_block_comment_above_next_test_not_in_previous():
    assert lines(FIXTURE_E, "test_a") == (2, 3)
    assert lines(FIXTURE_E, "test_b") == (6, 7)
    edited = FIXTURE_E.replace("# about test_b", "# something else")
    assert block_hash(edited, "test_a") == block_hash(FIXTURE_E, "test_a")
    assert block_hash(edited, "test_b") == block_hash(FIXTURE_E, "test_b")


def test_extract_block_indent_zero_pytest():
    assert lines(FIXTURE_F, "test_a") == (1, 2)
    assert lines(FIXTURE_F, "test_b") == (5, 6)
    edited = FIXTURE_F.replace("print(result)", "print(result, 1)")
    assert block_hash(edited, "test_b") == block_hash(FIXTURE_F, "test_b")
    assert block_hash(edited, "test_a") == block_hash(FIXTURE_F, "test_a")


def test_extract_block_indent_zero_go():
    assert lines(FIXTURE_G, "TestAdd") == (3, 7)
    assert lines(FIXTURE_G, "TestSub") == (9, 13)


def test_extract_block_csharp_attribute():
    assert lines(CSHARP, "TestAdd") == (3, 7)
    assert lines(CSHARP, "TestSub") == (9, 13)
    edited = CSHARP.replace("    [Fact]\n    public void TestSub", "    [Fact(Skip = \"x\")]\n    public void TestSub")
    assert block_hash(edited, "TestSub") != block_hash(CSHARP, "TestSub")
    assert block_hash(edited, "TestAdd") == block_hash(CSHARP, "TestAdd")


def test_extract_block_csharp_no_blank_line_between_methods():
    text = CSHARP.replace("    }\n\n    [Fact]", "    }\n    [Fact]")
    assert lines(text, "TestAdd") == (3, 7)
    assert lines(text, "TestSub") == (8, 12)


@pytest.mark.parametrize(
    "opener",
    [
        'it.skip("test_a", () => {',
        'it.only("test_a", () => {',
        'test.skip("test_a", () => {',
        'test.only("test_a", () => {',
        'test.each([1, 2])("test_a %s", (n) => {',
        'it.each([[1, 2]])("test_a %s", (a, b) => {',
        'describe("test_a", () => {',
        'it("test_a", () => {',
    ],
)
def test_extract_block_js_skip_only_each_describe(opener):
    text = (
        'describe("suite", () => {\n'
        f"  {opener}\n"
        "    expect(1).toBe(1);\n"
        "  });\n"
        "\n"
        '  it("test_b", () => {\n'
        "    expect(2).toBe(2);\n"
        "  });\n"
        "});\n"
    )
    assert lines(text, "test_a") == (2, 4)
    assert lines(text, "test_b") == (6, 8)


def test_extract_block_duplicate_raises():
    text = FIXTURE_A + "\n    def test_a(self):\n        pass\n"
    with pytest.raises(DuplicateTestId):
        extract_block(text, "test_a")
    assert extract_block(text, "test_b") is not None


def test_extract_block_line_matching_two_patterns_counts_once():
    # `def test_a(` matches both the Python and the typed-method pattern.
    assert lines("def test_a():\n    pass\n", "test_a") == (1, 2)


def test_extract_block_hash_ignores_crlf_and_trailing_blanks():
    crlf = FIXTURE_A.replace("\n", "\r\n")
    assert block_hash(crlf, "test_a") == block_hash(FIXTURE_A, "test_a")
    padded = FIXTURE_A.replace("assertEqual(add(1, 1), 2)", "assertEqual(add(1, 1), 2)   ")
    assert block_hash(padded, "test_a") == block_hash(FIXTURE_A, "test_a")
    expected = hashlib.sha256(
        b"    def test_a(self):\n        self.assertEqual(add(1, 1), 2)"
    ).hexdigest()
    assert block_hash(FIXTURE_A, "test_a") == expected


@pytest.mark.parametrize(
    ("command", "test_id", "test_file"),
    [
        (["uv", "run", "pytest", "tests/x.py::test_add"], "test_add", "tests/x.py"),
        (["pytest", "tests/x.py::T::test_add"], "test_add", "tests/x.py"),
        (["pytest", "./tests/x.py::test_add"], "test_add", "tests/x.py"),
        (["jest", "-t", "^test_add$"], "test_add", "tests/x.test.js"),
        (["vitest", "--testNamePattern", "^test_add$"], "test_add", "tests/x.test.js"),
        (["jest", "--testNamePattern=^test_add$"], "test_add", "tests/x.test.js"),
        (["jest", "-t", "^a\\.b$"], "a.b", "tests/x.test.js"),
        (["go", "test", "-run", "^TestAdd$"], "TestAdd", "x_test.go"),
        (["go", "test", "-run=^TestAdd$"], "TestAdd", "x_test.go"),
        (["dotnet", "test", "--filter", "Name=TestAdd"], "TestAdd", "T.cs"),
        (["dotnet", "test", "--filter", "FullyQualifiedName=Ns.T.TestAdd"], "TestAdd", "T.cs"),
        (["dotnet", "test", "--filter=Name=TestAdd"], "TestAdd", "T.cs"),
        (["uv", "run", "python", "-m", "unittest", "tests.test_x.T.test_add"], "test_add", "tests/test_x.py"),
    ],
)
def test_binds_exact_selector_forms(command, test_id, test_file):
    assert binds(command, test_id, test_file) is True


@pytest.mark.parametrize(
    ("command", "test_id", "test_file"),
    [
        (["pytest", "-k", "test_add"], "test_add", "tests/x.py"),
        (["pytest", "tests/x.py::test_add", "-k", "test_add"], "test_add", "tests/x.py"),
        (["pytest", "tests/x.py::test_add", "-ktest_add"], "test_add", "tests/x.py"),
        (["dotnet", "test", "--filter", "FullyQualifiedName~TestAdd"], "TestAdd", "T.cs"),
        (["dotnet", "test", "--filter", "FullyQualifiedName=Ns.T.TestAddMore"], "TestAdd", "T.cs"),
        (["dotnet", "test", "--filter", "Name~TestAdd"], "TestAdd", "T.cs"),
        (["jest", "-t", "test_add"], "test_add", "tests/x.test.js"),
        (["jest", "-t", "^test_add"], "test_add", "tests/x.test.js"),
        (["jest", "-t", "^a.b$"], "a.b", "tests/x.test.js"),
        (["go", "test", "-run", "TestAdd"], "TestAdd", "x_test.go"),
        (["go", "test", "-run", "^TestAdd"], "TestAdd", "x_test.go"),
        (["pytest", "tests/other.py::test_add"], "test_add", "tests/x.py"),
        (["pytest", "tests/x.py::test_add_negative"], "test_add", "tests/x.py"),
        (["pytest", "tests/x.py"], "test_add", "tests/x.py"),
        (["unittest", "tests.test_x.T.test_add_negative"], "test_add", "tests/x.py"),
        (["echo", "hello"], "test_add", "tests/x.py"),
    ],
)
def test_binds_refuses_substring_selectors(command, test_id, test_file):
    assert binds(command, test_id, test_file) is False


_SYNTAX_MARKERS = ["SyntaxError", "IndentationError", "error CS1002", "error CS1513", "TS1005"]
_MISSING_MARKERS = [
    "ModuleNotFoundError", "ImportError", "NameError", "AttributeError", "ReferenceError",
    "Cannot find module", "CS0103", "CS0246", "CS0117", "TS2304", "TS2305", "TS2339",
    "undefined:", "cannot find symbol",
]
_NO_RUN_MARKERS = [
    "No module named", "no tests ran", "collected 0 items", "No tests found", "not found:",
    "Build FAILED", "[build failed]", "error CS0128", "error TS2322",
]


@pytest.mark.parametrize(
    ("marker", "expected"),
    [(m, "syntax") for m in _SYNTAX_MARKERS]
    + [(m, "missing-symbol") for m in _MISSING_MARKERS]
    + [(m, "no-run") for m in _NO_RUN_MARKERS],
)
def test_classify_each_marker(marker, expected):
    assert classify(f"boom {marker} here", 1) == expected


def test_classify_syntax_wins_over_missing_symbol():
    assert classify("SyntaxError\nImportError", 1) == "syntax"


@pytest.mark.parametrize(
    ("output", "exit_code", "expected"),
    [
        ("FAILED tests/x.py::test_add - assert 1 == 2", 1, "red"),
        ("expect(received).toBe(expected)\nExpected: 2\nReceived: 1", 1, "red"),
        ("FAIL: test_add (tests.test_x.T.test_add)\nAssertionError: 1 != 2", 1, "red"),
        ("--- FAIL: TestAdd (0.00s)", 1, "red"),
        ("Failed TestAdd [3 ms]\nAssert.Equal() Failure", 1, "red"),
    ],
)
def test_classify_real_runner_failures_are_red(output, exit_code, expected):
    assert classify(output, exit_code) == expected


def test_classify_go_panic_is_red():
    assert classify("--- FAIL: TestAdd (0.00s)\npanic: runtime error", 2) == "red"


def test_classify_jest_reference_error_is_missing_symbol():
    output = "ReferenceError: add is not defined\n\n  > 1 | expect(add(1,1)).toBe(2)\n"
    assert classify(output, 1) == "missing-symbol"


def test_classify_dotnet_compile_error():
    assert classify("error CS0103: The name 'Add' does not exist", 1) == "missing-symbol"


def test_classify_python_syntax_error():
    assert classify('File "t.py", line 1\n SyntaxError: invalid syntax', 1) == "syntax"


@pytest.mark.parametrize(
    "output",
    [
        "/venv/bin/python: No module named pytest",
        "no tests ran in 0.01s",
        "collected 0 items",
        "No tests found, exiting with code 1",
        "ERROR: not found: /repo/tests/x.py::test_add",
        "Build FAILED.",
        "FAIL example.com/x [build failed]",
        "error CS0128: A local variable named 'a' is already defined",
        "error TS2322: Type 'string' is not assignable to type 'number'",
    ],
)
def test_classify_no_run_markers(output):
    assert classify(output, 1) == "no-run"


@pytest.mark.parametrize("exit_code", [4, 5, 126, 127, -9])
def test_classify_no_run_exit_codes(exit_code):
    assert classify("", exit_code) == "no-run"


def test_classify_missing_symbol_wins_over_no_run():
    assert classify("ModuleNotFoundError: No module named 'x'", 1) == "missing-symbol"


def failing_repo(git_repo, test_text="def test_x():\n    assert 1 == 2\n", plan=None):
    from tests.red_helpers import PLAN

    return make_repo(git_repo, test_text, PLAN if plan is None else plan)


def run_record(repo, command, test_id="test_x", test_file=TEST_FILE):
    return red_record.record("W-1", test_id, Path(test_file), command, repo, Path("plan.md"))


def run_main(repo, command, monkeypatch, test_id="test_x", test_file=TEST_FILE):
    monkeypatch.chdir(repo)
    return red_record.main(
        ["--work-item", "W-1", "--test-id", test_id, "--test-file", test_file,
         "--plan", "plan.md", "--", *command]
    )


def record_file(repo, test_id="test_x"):
    return repo / ".agent-work" / "W-1" / "evidence" / f"red-{slug(test_id)}.json"


def test_record_writes_json_with_block_hash(git_repo, monkeypatch):
    repo = failing_repo(git_repo)
    assert run_main(repo, pytest_command("test_x"), monkeypatch) == 0
    data = json.loads(record_file(repo).read_text())
    assert data["exit_code"] == 1
    assert data["category"] == "red"
    text = (repo / TEST_FILE).read_text()
    assert data["test_block_sha256"] == extract_block(text, "test_x").sha256
    assert data["test_block_lines"] == [1, 2]
    assert data["work_item"] == "W-1"
    assert data["test_file"] == TEST_FILE
    assert data["command"] == pytest_command("test_x")
    assert data["head_at_record"] == git_repo.git("rev-parse", "HEAD").strip()
    assert data["recorded_at"].endswith("+00:00")
    assert data["output_truncated"] is False
    assert "assert 1 == 2" in data["output_head"]
    assert data["output_tail"] == ""
    assert set(data) == set(RedRecord.__dataclass_fields__)


def test_record_fills_acs_from_plan(git_repo):
    repo = make_repo(git_repo)
    result = run_record(repo, pytest_command("test_a"), "test_a")
    assert result.acs == ["AC-1", "AC-2"]
    assert result.test_block_lines == [1, 2]


def test_record_acs_empty_when_no_task_names_the_test(git_repo):
    repo = failing_repo(git_repo)
    assert run_record(repo, pytest_command("test_x")).acs == []


def test_record_refuses_passing_command(git_repo, monkeypatch):
    repo = failing_repo(git_repo, "def test_x():\n    assert True\n")
    with pytest.raises(NotFailing):
        run_record(repo, pytest_command("test_x"))
    assert run_main(repo, pytest_command("test_x"), monkeypatch) == 3
    assert not (repo / ".agent-work").exists()


def test_record_refuses_unbound_test_id(git_repo, monkeypatch):
    repo = failing_repo(git_repo)
    command = [sys.executable, "-m", "pytest", TEST_FILE]
    with pytest.raises(NoBinding, match="no exact selector for test_x"):
        run_record(repo, command)
    assert run_main(repo, command, monkeypatch) == 4
    assert not (repo / ".agent-work").exists()


def test_record_refuses_k_selector(git_repo, monkeypatch):
    repo = failing_repo(git_repo)
    command = [*pytest_command("test_x"), "-k", "test_x"]
    with pytest.raises(NoBinding):
        run_record(repo, command)
    assert run_main(repo, command, monkeypatch) == 4
    assert not (repo / ".agent-work").exists()


def test_record_word_boundary(git_repo):
    text = "def test_add():\n    assert 1 == 2\n\n\ndef test_add_negative():\n    assert 1 == 2\n"
    repo = failing_repo(git_repo, text)
    command = pytest_command("test_add_negative")
    assert binds(command, "test_add", TEST_FILE) is False
    with pytest.raises(NoBinding):
        run_record(repo, command, "test_add")


def test_record_duplicate_definition_exits_7(git_repo, monkeypatch):
    repo = failing_repo(git_repo, "def test_x():\n    assert 1 == 2\n\n\ndef test_x():\n    assert 1 == 3\n")
    with pytest.raises(DuplicateTestId, match="duplicate test id"):
        run_record(repo, pytest_command("test_x"))
    assert run_main(repo, pytest_command("test_x"), monkeypatch) == 7
    assert not (repo / ".agent-work").exists()


def test_record_exit_code_order(git_repo, monkeypatch):
    repo = failing_repo(git_repo, "def test_x():\n    assert 1 == 2\n\n\ndef test_x():\n    assert 1 == 3\n")
    assert run_main(repo, ["no-such-command-k", TEST_FILE], monkeypatch) == 6
    assert run_main(repo, [sys.executable, "-m", "pytest", TEST_FILE], monkeypatch) == 4


def test_record_raises_but_never_writes(git_repo, monkeypatch):
    repo = failing_repo(git_repo)
    result = run_record(repo, pytest_command("test_x"))
    assert isinstance(result, RedRecord)
    assert not (repo / ".agent-work").exists()
    assert run_main(repo, pytest_command("test_x"), monkeypatch) == 0
    assert record_file(repo).is_file()


def test_record_keeps_head_and_tail(git_repo, monkeypatch):
    repo = failing_repo(git_repo)
    body = (
        "i=0\n"
        "while [ $i -lt 500 ]; do printf '%0100d' $i; i=$((i+1)); done\n"
        "exit 1"
    )
    full = "".join(f"{i:0100d}" for i in range(500))
    result = run_record(repo, runner_script(repo, body))
    assert result.output_truncated is True
    assert len(result.output_head) == 5000
    assert len(result.output_tail) == 15000
    assert result.output_head == full[:5000]
    assert result.output_tail == full[-15000:]
    assert result.category == "red"


def test_record_keeps_all_output_at_the_limit(git_repo):
    repo = failing_repo(git_repo)
    body = (
        "i=0\n"
        "while [ $i -lt 200 ]; do printf '%0100d' $i; i=$((i+1)); done\n"
        "exit 1"
    )
    result = run_record(repo, runner_script(repo, body))
    assert result.output_truncated is False
    assert len(result.output_head) == 20000
    assert result.output_tail == ""


def test_record_classifies_before_cutting(git_repo):
    repo = failing_repo(git_repo)
    body = (
        "i=0\n"
        "while [ $i -lt 500 ]; do\n"
        "  [ $i -eq 100 ] && printf 'SyntaxError: bad\\n'\n"
        "  printf '%0100d' $i; i=$((i+1))\n"
        "done\n"
        "exit 1"
    )
    result = run_record(repo, runner_script(repo, body))
    assert result.output_truncated is True
    assert "SyntaxError" not in result.output_head + result.output_tail
    assert result.category == "syntax"


def test_record_handles_non_utf8_and_ansi(git_repo):
    repo = failing_repo(git_repo)
    body = "printf '\\033[31mred\\033[0m \\377\\376 end\\n'\nexit 1"
    result = run_record(repo, runner_script(repo, body))
    assert "\x1b" not in result.output_head
    assert "�" in result.output_head
    assert result.output_head.startswith("red ")
    assert json.dumps(result.output_head)


def test_record_timeout_and_missing_command(git_repo, monkeypatch):
    repo = failing_repo(git_repo)
    monkeypatch.setattr(red_record, "RUN_TIMEOUT_SECONDS", 1)
    hang = runner_script(repo, "exec sleep 30")
    with pytest.raises(Timeout):
        run_record(repo, hang)
    assert run_main(repo, hang, monkeypatch) == 5
    missing = ["no-such-command-k", f"{TEST_FILE}::test_x"]
    with pytest.raises(CommandNotFound):
        run_record(repo, missing)
    assert run_main(repo, missing, monkeypatch) == 6
    assert not (repo / ".agent-work").exists()


def test_record_uses_exit_code_not_output(git_repo):
    repo = failing_repo(git_repo)
    with pytest.raises(NotFailing):
        run_record(repo, runner_script(repo, "echo 'FAILED assert 1 == 2'\nexit 0"))


def test_record_no_run_category(git_repo):
    repo = failing_repo(git_repo)
    assert run_record(repo, runner_script(repo, "exit 127")).category == "no-run"


def test_environment_failure_counts_as_red_known_limit(git_repo):
    repo = failing_repo(git_repo, "def test_x():\n    open('fixture.json')\n")
    result = run_record(repo, pytest_command("test_x"))
    assert "FileNotFoundError" in result.output_head
    assert result.category == "red"


def test_main_help_exits_zero(capsys):
    assert red_record.main(["--help"]) == 0
    assert "usage: red_record" in capsys.readouterr().out


def test_main_bad_usage_exits_two(capsys):
    assert red_record.main(["--work-item", "W-1"]) == 2
    assert red_record.main(["--work-item", "W-1", "--", "x"]) == 2
    assert (
        red_record.main(
            ["--work-item", "../x", "--test-id", "t", "--test-file", "f", "--plan", "p", "--", "x"]
        )
        == 2
    )
