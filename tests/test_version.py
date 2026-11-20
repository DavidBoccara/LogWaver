"""Cohérence de l'identification de version (gestion de configuration)."""

from __future__ import annotations

import re
import unittest

from logwaver import __version__
from tests.helpers import PROJECT_ROOT

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", re.MULTILINE)


class VersionTests(unittest.TestCase):
    """La version du code et celle du CHANGELOG doivent concorder."""

    def test_version_is_semantic(self) -> None:
        """``__version__`` respecte le format MAJEUR.MINEUR.CORRECTIF."""
        self.assertRegex(__version__, SEMVER_PATTERN)

    def test_changelog_matches_version(self) -> None:
        """La dernière version du CHANGELOG est ``__version__``."""
        changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        releases = RELEASE_HEADING.findall(changelog)
        self.assertTrue(releases, "Aucune version publiée dans CHANGELOG.md")
        self.assertEqual(releases[0], __version__)


if __name__ == "__main__":
    unittest.main()
