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
