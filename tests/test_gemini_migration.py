import os
import unittest
from pathlib import Path
from unittest.mock import patch

from services import gemini_service


ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    text = "resposta Gemini"


class _FakeModels:
    def __init__(self):
        self.call = None

    def generate_content(self, **kwargs):
        self.call = kwargs
        return _FakeResponse()


class _FakeClient:
    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.models = _FakeModels()
        self.closed = False

    def close(self):
        self.closed = True


class _FakeGenai:
    def __init__(self):
        self.client = None

    def Client(self, **kwargs):
        self.client = _FakeClient(**kwargs)
        return self.client


class _FakeTypes:
    class HttpOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class GeminiMigrationTests(unittest.TestCase):
    def test_repository_has_no_perplexity_runtime_contract(self):
        searchable = [ROOT / "services", ROOT / "ui", ROOT / "docs", ROOT / "requirements.txt"]
        matches = []
        for path in searchable:
            files = path.rglob("*") if path.is_dir() else [path]
            for file_path in files:
                if file_path.is_file() and file_path.suffix in {".py", ".md", ".txt"}:
                    if "perplexity" in file_path.read_text(encoding="utf-8").lower():
                        matches.append(str(file_path.relative_to(ROOT)))
        self.assertEqual([], matches)

    def test_official_client_uses_gemini_environment_and_is_closed(self):
        fake_genai = _FakeGenai()
        with (
            patch.object(gemini_service, "genai", fake_genai),
            patch.object(gemini_service, "types", _FakeTypes),
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-test"}, clear=False),
        ):
            result = gemini_service.gerar_conteudo_gemini(
                system_instruction="sistema",
                prompt="entrada",
                temperature=0.2,
                max_output_tokens=50,
            )

        self.assertEqual("resposta Gemini", result)
        self.assertEqual("test-key", fake_genai.client.init_kwargs["api_key"])
        self.assertEqual("gemini-test", fake_genai.client.models.call["model"])
        self.assertTrue(fake_genai.client.closed)


if __name__ == "__main__":
    unittest.main()
