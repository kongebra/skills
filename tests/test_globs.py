import pytest

from kcommon import gitutil
from kcommon.globs import match

FIXTURES = [
    ("src/auth/**", "src/auth/x.py", True),
    ("src/auth/**", "src/auth", False),
    ("*.csproj", "a/b/x.csproj", True),
    ("**/migrations/**", "migrations/1.sql", True),
    ("docs/*.md", "docs/a/b.md", False),
    ("/docs/x", "a/docs/x", False),
    ("azure-pipelines*.yml", "azure-pipelines-ci.yml", True),
    ("/src/auth/", "src/auth/login.py", True),
    ("auth/", "src/auth/login.py", True),
    ("/src/auth/", "x/src/auth/a.py", False),
    ("infra/**", "a/infra/x.tf", False),
    ("Dockerfile", "svc/Dockerfile", True),
    ("infra", "a/infra/main.bicep", True),
]


@pytest.mark.parametrize(("pattern", "path", "expected"), FIXTURES)
def test_fixture(pattern, path, expected):
    assert match(pattern, path) is expected


def test_trailing_double_star_needs_a_segment():
    assert not match("src/auth/**", "src/auth")
    assert match("src/auth/**", "src/auth/a/b.py")


def test_directory_pattern_never_matches_the_file_itself():
    assert not match("auth/", "auth")
    assert match("auth/", "auth/x")


def test_wildcards_stay_inside_one_segment():
    assert match("docs/*.md", "docs/a.md")
    assert match("docs/?.md", "docs/a.md")
    assert not match("docs/?.md", "docs/ab.md")
    assert match("docs/[ab].md", "docs/b.md")
    assert not match("docs/[!ab].md", "docs/b.md")
    assert match("a/**/z", "a/z")
    assert match("a/**/z", "a/b/c/z")


@pytest.mark.parametrize(("pattern", "path", "expected"), FIXTURES)
def test_match_agrees_with_git_check_ignore(git_repo, pattern, path, expected):
    git_repo.write(path, "x\n")
    git_repo.write(".gitignore", pattern + "\n")
    code, _ = gitutil.run_code(git_repo.path, "check-ignore", "-q", "--no-index", "--", path)
    assert code in (0, 1)
    assert (code == 0) is expected
    assert (code == 0) is match(pattern, path)
