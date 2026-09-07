import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/characterization_v4.json"


def test_characterization_manifest_references_existing_tests():
    contract = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert contract["baseline"]["failures"] == 0
    assert contract["baseline"]["tests_passed"] >= 126
    assert contract["baseline"]["subtests_passed"] >= 139
    assert len(contract["domains"]) >= 7
    for test_files in contract["domains"].values():
        assert test_files
        for relative_path in test_files:
            assert (ROOT / relative_path).is_file(), relative_path


def test_every_critical_v4_domain_has_a_gate():
    domains = json.loads(MANIFEST.read_text(encoding="utf-8"))["domains"]
    assert {
        "authentication_and_authorization",
        "bets_and_deadlines",
        "scoring_and_classification",
        "data_contracts_and_seasons",
        "backup_and_restore",
        "architecture_and_security",
        "performance",
    } == set(domains)
