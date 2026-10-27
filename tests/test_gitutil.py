import pytest
from kcommon import gitutil


def test_show_missing_file_returns_none(git_repo):
    git_repo.write("a.txt", "a\n")
    git_repo.commit_all("one")
    assert gitutil.show(git_repo.path, "HEAD", "nope.txt") is None
    assert gitutil.show(git_repo.path, "HEAD", "a.txt") == "a\n"


def test_merge_base_unknown_ref_raises(git_repo):
    git_repo.write("a.txt", "a\n")
    git_repo.commit_all("one")
    with pytest.raises(gitutil.BaseNotFound):
        gitutil.merge_base(git_repo.path, "origin/nope", "HEAD")
    with pytest.raises(gitutil.BaseNotFound):
        gitutil.merge_base(git_repo.path, "HEAD", "nope")


def test_merge_base_returns_common_ancestor(git_repo):
    git_repo.write("a.txt", "a\n")
    first = git_repo.commit_all("one")
    git_repo.git("checkout", "-b", "topic")
    git_repo.write("b.txt", "b\n")
    git_repo.commit_all("two")
    assert gitutil.merge_base(git_repo.path, "main", "topic") == first
    assert gitutil.rev_parse(git_repo.path, "main") == first


def test_run_non_zero_raises(git_repo):
    with pytest.raises(gitutil.GitError):
        gitutil.run(git_repo.path, "rev-parse", "--verify", "nope")


def test_run_code_returns_exit_code_without_raising(git_repo):
    git_repo.write("a.txt", "a\n")
    code, out = gitutil.run_code(git_repo.path, "check-ignore", "-q", "--no-index", "--", "a.txt")
    assert code == 1
    assert out == ""


def test_run_bytes_returns_raw_output(git_repo):
    git_repo.write("a.txt", "a\n")
    git_repo.commit_all("one")
    assert gitutil.run_bytes(git_repo.path, "ls-files", "-z") == b"a.txt\0"


def test_missing_git_program_raises_git_error(git_repo, monkeypatch):
    monkeypatch.setenv("PATH", str(git_repo.path))
    with pytest.raises(gitutil.GitError):
        gitutil.run_code(git_repo.path, "status")


def test_git_env_drops_repo_variables(monkeypatch):
    for name in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.setenv(name, "/somewhere")
    env = gitutil.git_env()
    for name in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"):
        assert name not in env


def test_git_env_hermetic_mode(monkeypatch):
    env = gitutil.git_env()
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    monkeypatch.delenv("K_GIT_HERMETIC")
    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    env = gitutil.git_env()
    assert "GIT_CONFIG_GLOBAL" not in env
    assert "GIT_CONFIG_NOSYSTEM" not in env


def _repo_with_change(git_repo):
    git_repo.git("config", "diff.noprefix", "true")
    git_repo.git("config", "color.ui", "always")
    git_repo.write("a.txt", "one\n")
    git_repo.commit_all("one")
    git_repo.write("a.txt", "two\n")


def test_diff_ignores_repo_config(git_repo):
    _repo_with_change(git_repo)
    out = gitutil.run(git_repo.path, "diff", "-U0", "--", "a.txt")
    assert "+++ b/a.txt" in out
    assert "--- a/a.txt" in out
    assert "\x1b[" not in out


def test_diff_hardening_applies_after_config_pairs_and_to_all_runners(git_repo):
    _repo_with_change(git_repo)
    out = gitutil.run(git_repo.path, "-c", "core.quotepath=false", "diff", "-U0")
    assert "+++ b/a.txt" in out
    code, out = gitutil.run_code(git_repo.path, "diff", "-U0")
    assert code == 0 and "+++ b/a.txt" in out and "\x1b[" not in out
    raw = gitutil.run_bytes(git_repo.path, "diff", "-U0")
    assert b"+++ b/a.txt" in raw and b"\x1b[" not in raw
