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

    def test_removed_streamlit_width_parameter_is_not_used(self):
        root = Path(__file__).resolve().parents[1]
        painel = (root / "ui" / "painel.py").read_text(encoding="utf-8")
        self.assertNotIn("use_container_width", painel)
