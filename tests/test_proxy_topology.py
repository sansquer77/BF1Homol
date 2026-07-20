import unittest

from utils.request_utils import select_client_ip


class ProxyTopologyTests(unittest.TestCase):
    def test_direct_mode_ignores_spoofed_headers(self):
        self.assertEqual(select_client_ip("direct", {"x-forwarded-for": "203.0.113.9"}, "127.0.0.1"), "127.0.0.1")

    def test_xff_requires_explicit_hops(self):
        with self.assertRaises(RuntimeError):
            select_client_ip("xff", {"x-forwarded-for": "203.0.113.9"}, "127.0.0.1", 0)

    def test_xff_uses_configured_topology(self):
        headers = {"x-forwarded-for": "198.51.100.4, 203.0.113.9"}
        self.assertEqual(select_client_ip("xff", headers, "127.0.0.1", 1), "203.0.113.9")
        self.assertEqual(select_client_ip("xff", headers, "127.0.0.1", 2), "198.51.100.4")

