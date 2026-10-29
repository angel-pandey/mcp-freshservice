"""The release guard must itself be right: a wrong 'OK' wastes a PyPI version number."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def guard():
    spec = importlib.util.spec_from_file_location("check_release", ROOT / "scripts" / "check_release.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def files(tmp_path):
    def make(version="2.0.1", changelog="# Changelog\n\n## 2.0.1\n\n- something\n"):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")
        log = tmp_path / "CHANGELOG.md"
        log.write_text(changelog, encoding="utf-8")
        return pyproject, log

    return make


@pytest.mark.parametrize("tag", ["v2.0.1", "2.0.1", "refs/tags/v2.0.1", " v2.0.1 "])
def test_matching_tag_forms_pass(guard, files, tag):
    assert guard.check(tag, *files()) == []


def test_a_tag_for_a_different_version_fails(guard, files):
    problems = guard.check("v2.0.2", *files())
    assert len(problems) == 1 and "does not match" in problems[0] and "2.0.1" in problems[0]


def test_forgetting_to_bump_the_version_fails(guard, files):
    # pyproject still says 2.0.0 but someone tags v2.0.1
    problems = guard.check("v2.0.1", *files(version="2.0.0", changelog="## 2.0.0\n\n## 2.0.1\n"))
    assert any("does not match" in p for p in problems)


def test_a_missing_changelog_entry_fails(guard, files):
    problems = guard.check("v2.0.1", *files(changelog="# Changelog\n\n## 2.0.0\n"))
    assert problems == ["CHANGELOG.md has no '## 2.0.1' section."]


def test_a_longer_version_does_not_satisfy_a_shorter_one(guard, files):
    assert guard.check("v2.0.1", *files(changelog="## 2.0.10\n"))  # 2.0.10 is not 2.0.1


def test_both_problems_are_reported_together(guard, files):
    assert len(guard.check("v9.9.9", *files(changelog="## 2.0.0\n"))) == 2


def test_this_repository_is_release_ready(guard):
    """pyproject's version must always have a changelog entry (CI runs the same check)."""
    import tomllib

    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert guard.check(f"v{version}") == []


def test_cli_exit_codes(guard, files, capsys):
    assert guard.main(["--current"]) == 0
    assert guard.main(["v0.0.0-nonexistent"]) == 1
    assert "ERROR" in capsys.readouterr().err
    assert guard.main([]) == 2
