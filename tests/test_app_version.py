import unittest
from pathlib import Path
import re

from app_version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class AppVersionTests(unittest.TestCase):
    def test_current_app_version(self):
        self.assertEqual(APP_VERSION, "4.1.1")
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")

    def test_product_changelog_contains_current_version(self):
        changelog = (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        declared = re.search(r"^### (\d+\.\d+\.\d+)$", changelog, re.MULTILINE)
        self.assertIsNotNone(declared)
        self.assertEqual(declared.group(1), APP_VERSION)

    def test_api_and_about_page_use_canonical_version(self):
        api_version = (ROOT / "api" / "version.py").read_text(encoding="utf-8")
        about = (ROOT / "frontend" / "src" / "components" / "about-version.tsx").read_text(encoding="utf-8")
        self.assertIn("from app_version import APP_VERSION", api_version)
        self.assertIn("API_VERSION = APP_VERSION", api_version)
        self.assertIn('apiRequest<About>("/api/v1/content/about")', about)


if __name__ == "__main__":
    unittest.main()
