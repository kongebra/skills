import re

from tests.gitfixture import GitFixture


def test_commit_works_without_global_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    repo = GitFixture.create(tmp_path / "base")
    repo.write("a.txt", "a")
    assert re.fullmatch(r"[0-9a-f]{40}", repo.commit_all("first"))


def test_write_accepts_bytes(git_repo):
    git_repo.write("dir/b.bin", b"\x00\x01\xff")
    assert (git_repo.path / "dir" / "b.bin").read_bytes() == b"\x00\x01\xff"


def test_inherited_git_env_is_ignored(git_repo, tmp_path, monkeypatch):
    other = tmp_path / "other.git"
    monkeypatch.setenv("GIT_DIR", str(other))
    git_repo.write("a.txt", "a")
    sha = git_repo.commit_all("first")
    assert git_repo.git("rev-parse", "HEAD").strip() == sha
    assert not other.exists()
