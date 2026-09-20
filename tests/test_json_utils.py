from utils.json_utils import extract_json_object


def test_extract_json_object_accepts_plain_object():
    assert extract_json_object('{"value": 7}') == {"value": 7}


def test_extract_json_object_accepts_object_wrapped_in_text():
    assert extract_json_object('Resposta:\n```json\n{"value": 7}\n```') == {"value": 7}


def test_extract_json_object_rejects_non_object_or_invalid_payload():
    assert extract_json_object('[1, 2]') is None
    assert extract_json_object("sem JSON") is None
    assert extract_json_object("") is None
