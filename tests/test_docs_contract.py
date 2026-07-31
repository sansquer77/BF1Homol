import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class DocumentationContractTests(unittest.TestCase):
    def test_every_document_follows_the_sdd_envelope(self):
        required_frontmatter = {
            "tipo", "area", "status", "versao", "atualizado",
            "relacionados", "tags",
        }
        failures = []

        for path in sorted(DOCS.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---\n"):
                failures.append(f"{path.relative_to(ROOT)}: sem frontmatter")
                continue
            parts = text.split("---", 2)
            if len(parts) < 3:
                failures.append(f"{path.relative_to(ROOT)}: frontmatter incompleto")
                continue
            frontmatter = parts[1]
            fields = {
                match.group(1)
                for match in re.finditer(r"^([a-z_]+):", frontmatter, re.MULTILINE)
            }
            missing = sorted(required_frontmatter - fields)
            if missing:
                failures.append(
                    f"{path.relative_to(ROOT)}: campos ausentes {', '.join(missing)}"
                )
            if "> [!info] Status" not in text and "> [!info] Como usar" not in text:
                failures.append(f"{path.relative_to(ROOT)}: sem callout de status")
            if not re.search(r"^#{2,3} Changelog(?: do template)?$", text, re.MULTILINE):
                failures.append(f"{path.relative_to(ROOT)}: sem Changelog")
            if not re.search(r"^#{2,3} Relacionados$", text, re.MULTILINE):
                failures.append(f"{path.relative_to(ROOT)}: sem Relacionados")

        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_agents_and_sdd_keep_the_shared_flow_in_sync(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        sdd = (DOCS / "sdd.md").read_text(encoding="utf-8")

        for marker in ("fluxo-bf1", "versionamento-bf1"):
            pattern = re.compile(
                rf"<!-- sync:{marker} -->(.*?)<!-- /sync:{marker} -->",
                re.DOTALL,
            )
            agents_block = pattern.search(agents)
            sdd_block = pattern.search(sdd)
            self.assertIsNotNone(agents_block)
            self.assertIsNotNone(sdd_block)
            self.assertEqual(
                agents_block.group(1).strip(),
                sdd_block.group(1).strip(),
            )

    def test_canonical_navigation_files_exist(self):
        focused_specs = [
            "autenticacao-e-sessao.md",
            "controle-de-acesso.md",
            "apostas-de-prova.md",
            "deadline-de-apostas.md",
            "pontuacao-de-provas.md",
            "resultados-de-provas.md",
            "apostas-automaticas.md",
            "apostas-de-campeonato.md",
            "classificacao.md",
            "gestao-de-usuarios.md",
            "gestao-de-temporadas-e-regras.md",
            "calendario-provas-e-pilotos.md",
            "historico-do-participante.md",
            "logs-e-auditoria.md",
            "backup-e-restauracao.md",
            "notificacoes-por-email.md",
            "analises-e-dashboard.md",
            "hall-da-fama.md",
            "pwa-e-preferencias-do-cliente.md",
        ]
        expected = [
            ROOT / "AGENTS.md",
            DOCS / "README.md",
            DOCS / "sdd.md",
            DOCS / "glossario.md",
            DOCS / "CHANGELOG.md",
            DOCS / "templates" / "spec-template.md",
            DOCS / "adr" / "0001-streamlit-postgresql.md",
            DOCS / "adr" / "0002-limites-de-camadas.md",
        ] + [DOCS / "specs" / name for name in focused_specs]
        self.assertEqual([str(path) for path in expected if not path.is_file()], [])


if __name__ == "__main__":
    unittest.main()
