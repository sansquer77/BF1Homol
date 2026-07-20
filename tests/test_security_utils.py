import unittest

from utils.security_utils import MAX_EMAIL_LENGTH, normalize_email_identifier


class SecurityUtilsTests(unittest.TestCase):
    def test_email_is_normalized_before_security_keys(self):
        self.assertEqual(normalize_email_identifier("  User@Example.COM "), "user@example.com")

    def test_oversized_email_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_email_identifier("a" * (MAX_EMAIL_LENGTH + 1))

