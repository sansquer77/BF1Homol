from pathlib import Path
import tomllib
import unittest


class StreamlitSecurityConfigTests(unittest.TestCase):
    def test_cors_and_xsrf_are_both_enabled(self):
        config_path = Path(__file__).parents[1] / ".streamlit" / "config.toml"
        with config_path.open("rb") as config_file:
            server = tomllib.load(config_file)["server"]
        self.assertIs(server.get("enableCORS"), True)
        self.assertIs(server.get("enableXsrfProtection"), True)

