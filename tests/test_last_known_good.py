import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "skills" / "k-common" / "last-known-good.json"


def load() -> dict:
    return json.loads(PINS.read_text(encoding="utf-8"))


def test_shas_are_full():
    data = load()
    for commit in (data["superpowers"]["commit"], data["mattpocock_skills"]["commit"]):
        assert re.fullmatch(r"[0-9a-f]{40}", commit)


def test_superpowers_commit_is_verified_value():
    data = load()
    assert data["superpowers"]["commit"] == "2ce8aa15d05bd57213e6f746f953aafb7ded7a8b"
    assert data["superpowers"]["tested_version"] == "7.0.1"
    assert data["skills_cli"]["version"] == "1.7.4"
