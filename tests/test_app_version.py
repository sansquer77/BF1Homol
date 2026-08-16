import unittest
from pathlib import Path
import re

from app_version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class AppVersionTests(unittest.TestCase):
    def test_current_app_version(self):
        self.assertEqual(APP_VERSION, "3.3.0")
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")

    def test_product_changelog_contains_current_version(self):
        changelog = (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        declared = re.search(r"^### (\d+\.\d+\.\d+)$", changelog, re.MULTILINE)
        self.assertIsNotNone(declared)
        self.assertEqual(declared.group(1), APP_VERSION)

    def test_about_page_uses_canonical_version(self):
        source = (ROOT / "ui" / "sobre.py").read_text(encoding="utf-8")
        self.assertIn("from app_version import APP_VERSION", source)
        self.assertGreaterEqual(source.count("APP_VERSION"), 3)
        self.assertNotIn("v3.5", source)
        self.assertNotIn("3.0-2026", source)


if __name__ == "__main__":
    unittest.main()
