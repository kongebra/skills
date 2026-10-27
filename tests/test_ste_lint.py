import subprocess
import sys

from kcommon import ste_lint
from kcommon.ste_lint import lint


def words(n):
    return " ".join(["word"] * n) + "."


def test_long_sentence_flagged():
    assert lint(words(25)) == []
    findings = lint(words(26))
    assert [f.rule for f in findings] == ["sentence-length"]
    assert findings[0].line == 1


def test_code_block_ignored():
    text = "```\n" + words(40) + "; a\n```\n"
    assert lint(text) == []


def test_backtick_span_counts_as_one_word():
    span = "`" + " ".join(["x"] * 10) + "`"
    sentence = " ".join(["word"] * 24) + " " + span + "."
    assert lint(sentence) == []


def test_semicolon_outside_code_flagged():
    findings = lint("One; two.")
    assert [f.rule for f in findings] == ["semicolon"]


def test_semicolon_in_code_ignored():
    assert lint("Use `a; b` here.\n\n```\na; b\n```\n") == []


def test_en_and_em_dash_flagged():
    findings = lint("A – b.\nC — d.")
    assert [(f.line, f.rule) for f in findings] == [(1, "dash"), (2, "dash")]


def test_markers_not_counted():
    sentence = "**[BLOCKER]** " + " ".join(["word"] * 25) + "."
    assert lint(sentence) == []


def test_frontmatter_skipped():
    text = "---\ndescription: " + " ".join(["word"] * 40) + "\n---\nShort text.\n"
    assert lint(text) == []


def test_heading_is_skipped():
    assert lint("# " + " ".join(["word"] * 40) + "\n") == []


def test_table_row_is_skipped():
    assert lint("| " + " | ".join(["word"] * 40) + " |\n") == []


def test_bullet_starts_new_sentence():
    text = "- " + words(20)[:-1] + "\n- " + words(20) + "\n"
    assert lint(text) == []
    assert [f.line for f in lint("- " + words(26))] == [1]


def test_sentence_wrapped_across_two_lines_is_one_sentence():
    text = " ".join(["word"] * 13) + "\n" + " ".join(["word"] * 13) + ".\n"
    findings = lint(text)
    assert [(f.line, f.rule) for f in findings] == [(1, "sentence-length")]


def test_wrapped_short_sentence_is_not_flagged():
    assert lint(" ".join(["word"] * 12) + "\n" + " ".join(["word"] * 12) + ".\n") == []


def test_no_arguments_exits_2_with_usage(capsys):
    assert ste_lint.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: ste_lint <file>...")


def test_missing_file_exits_2_with_one_line_error(tmp_path, capsys):
    missing = tmp_path / "nope.md"
    assert ste_lint.main([str(missing)]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert err.startswith(f"ste_lint: cannot read {missing}: ")


def test_cli_missing_file_exit_code(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "kcommon.ste_lint", str(tmp_path / "nope.md")],
        check=False, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1


def test_clean_file_exits_0_and_finding_exits_1(tmp_path, capsys):
    clean = tmp_path / "a.md"
    clean.write_text("Short text.\n", encoding="utf-8")
    bad = tmp_path / "b.md"
    bad.write_text(words(30) + "\n", encoding="utf-8")
    assert ste_lint.main([str(clean)]) == 0
    assert ste_lint.main([str(bad)]) == 1
    assert f"{bad}:1: sentence-length:" in capsys.readouterr().out
