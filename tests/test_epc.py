from london_scorer.fetchers import epc
from london_scorer import http


def test_epc_band_score(monkeypatch):
    """Test new EPC API: energy band distribution scoring."""
    call_count = {"n": 0}

    def fake_get_json(url, **k):
        call_count["n"] += 1
        if "postcodes.io" in url:
            return {"result": {"postcode": "AL8 6HA"}}
        # EPC search response
        return {"data": [
            {"currentEnergyEfficiencyBand": "B", "postcode": "AL8 6HA"},
            {"currentEnergyEfficiencyBand": "C", "postcode": "AL8 6HA"},
            {"currentEnergyEfficiencyBand": "D", "postcode": "AL8 6HB"},
        ]}

    monkeypatch.setattr(http, "get_json", fake_get_json)
    out = epc.fetch({"district": "AL8"}, "TOKEN")
    assert out["epc_n"] == 3
    # B=6, C=5, D=4 → mean = 5.0
    assert out["epc_band_score"] == 5.0


def test_epc_no_token():
    out = epc.fetch({"district": "AL8"}, "")
    assert out["epc_band_score"] is None
    assert out["epc_n"] == 0
