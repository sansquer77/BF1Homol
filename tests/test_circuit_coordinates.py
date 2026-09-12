from db.circuitos_utils import _extract_circuit_entries_from_season


def test_jolpica_circuit_coordinates_are_normalized_for_persistence():
    payload = {"MRData": {"RaceTable": {"Races": [{
        "raceName": "Madrid Grand Prix",
        "Circuit": {"circuitId": "madrid", "circuitName": "Madring", "Location": {
            "locality": "Madrid", "country": "Spain", "lat": "40.467", "long": "-3.617",
        }},
    }]}}}
    circuit = _extract_circuit_entries_from_season(payload)["madrid"]
    assert circuit["latitude"] == 40.467
    assert circuit["longitude"] == -3.617
