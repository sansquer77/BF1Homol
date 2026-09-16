import unittest

from services.report_image_service import generate_bets_coverage_image


class ReportImageServiceTests(unittest.TestCase):
    def test_generate_bets_coverage_image_returns_png_bytes(self):
        reports = [
            {"name": "Ana Silva", "manual_total": 12, "automatic_total": 3, "missing_total": 1, "bets_total": 15},
            {"name": "Bruno Costa", "manual_total": 8, "automatic_total": 5, "missing_total": 3, "bets_total": 13},
            {"name": "Carlos Lima", "manual_total": 16, "automatic_total": 0, "missing_total": 0, "bets_total": 16},
        ]
        image_bytes = generate_bets_coverage_image("2026", 16, reports)
        self.assertIsInstance(image_bytes, bytes)
        self.assertTrue(image_bytes.startswith(b"\x89PNG"))
        self.assertGreater(len(image_bytes), 1000)

    def test_generate_bets_coverage_image_handles_empty_reports(self):
        image_bytes = generate_bets_coverage_image("2026", 0, [])
        self.assertTrue(image_bytes.startswith(b"\x89PNG"))

    def test_generate_bets_coverage_image_handles_zero_races_total(self):
        reports = [{"name": "Ana", "manual_total": 0, "automatic_total": 0, "missing_total": 0, "bets_total": 0}]
        image_bytes = generate_bets_coverage_image("2026", 0, reports)
        self.assertTrue(image_bytes.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
