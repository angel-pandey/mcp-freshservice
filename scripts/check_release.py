"""Refuse a release whose git tag, package version and changelog disagree.

PyPI never accepts the same version twice, so a mismatch found after uploading costs a version number.

    python scripts/check_release.py v2.0.1     # what the publish workflow runs with the release tag
    python scripts/check_release.py --current   # CI: the version in pyproject.toml must have a changelog entry
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(
    tag: str, pyproject: Path = ROOT / "pyproject.toml", changelog: Path = ROOT / "CHANGELOG.md"
) -> list[str]:
    """Return a list of problems; an empty list means the release is consistent."""
    version = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    wanted = tag.strip().removeprefix("refs/tags/").removeprefix("v")
    problems = []
    if wanted != version:
        problems.append(
            f"tag {tag!r} does not match the package version {version!r} in pyproject.toml. "
            f"Bump the version before tagging, or tag v{version}."
        )
    if not re.search(
        rf"^##\s+{re.escape(version)}(\s|$)", changelog.read_text(encoding="utf-8"), re.MULTILINE
    ):
        problems.append(f"CHANGELOG.md has no '## {version}' section.")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    tag = argv[0]
    if tag == "--current":
        tag = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    problems = check(tag)
    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)
    if not problems:
        print(f"OK: {tag} matches pyproject.toml and CHANGELOG.md")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
