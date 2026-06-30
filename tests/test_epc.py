from london_scorer.fetchers import epc
from london_scorer import http


def test_epc_floor_area_and_detached(monkeypatch):
    """Test EPC fetcher extracts sqm, detached%, rooms from cert details."""
    def fake_get_json(url, **k):
        ck = k.get("cache_key", "")
        if "postcodes.io" in url:
            return {"result": {"postcode": "AL1 4PL"}}
        if "search" in url:
            return {"data": [
                {"certificateNumber": "CERT-1"},
                {"certificateNumber": "CERT-2"},
                {"certificateNumber": "CERT-3"},
            ]}
        # Individual cert fetch
        certs = {
            "CERT-1": {"total_floor_area": 120, "built_form": 1, "habitable_room_count": 5,
                        "dwelling_type": {"value": "Detached house"}},
            "CERT-2": {"total_floor_area": 80, "built_form": 2, "habitable_room_count": 3,
                        "dwelling_type": {"value": "Semi-Detached house"}},
            "CERT-3": {"total_floor_area": 150, "built_form": 1, "habitable_room_count": 6,
                        "dwelling_type": {"value": "Detached house"}},
        }
        cn = k.get("params", {}).get("certificate_number", "")
        return {"data": certs.get(cn, {})}

    monkeypatch.setattr(http, "get_json", fake_get_json)
    out = epc.fetch({"district": "AL1"}, "TOKEN")
    assert out["epc_n"] >= 3  # at least 3 certs (may sample multiple postcodes)
    assert out["epc_median_sqm"] == 120.0  # median of [80, 120, 150] repeated
    assert round(out["pct_detached"], 2) == 0.67  # 2/3 detached per set
    assert out["median_rooms"] == 5  # median of [3, 5, 6] repeated


def test_epc_no_token():
    out = epc.fetch({"district": "AL8"}, "")
    assert out["epc_median_sqm"] is None
    assert out["epc_n"] == 0
