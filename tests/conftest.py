import pytest

from tests.gitfixture import GitFixture


@pytest.fixture(autouse=True)
def hermetic_git(monkeypatch):
    monkeypatch.setenv("K_GIT_HERMETIC", "1")


@pytest.fixture
def git_repo(tmp_path) -> GitFixture:
    return GitFixture.create(tmp_path)
