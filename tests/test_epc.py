from london_scorer.fetchers import epc
from london_scorer import http


def test_epc_council_query(monkeypatch):
    """Test EPC fetcher: council search → cert detail → houses-only sqm."""
    def fake_get_json(url, **k):
        params = k.get("params", {})
        # Council search returns cert numbers with postcodes
        if "council[]" in params:
            return {
                "data": [
                    {"certificateNumber": "C1", "postcode": "AL1 1AA"},
                    {"certificateNumber": "C2", "postcode": "AL1 2BB"},
                    {"certificateNumber": "C3", "postcode": "AL1 3CC"},
                    {"certificateNumber": "C4", "postcode": "AL4 9ZZ"},  # different outcode
                ],
                "pagination": {"totalPages": 1, "currentPage": 1},
            }
        # Individual cert detail
        cn = params.get("certificate_number", "")
        certs = {
            "C1": {"total_floor_area": 120, "built_form": 1, "habitable_room_count": 5,
                    "dwelling_type": {"value": "Detached house"}},
            "C2": {"total_floor_area": 80, "built_form": 2, "habitable_room_count": 3,
                    "dwelling_type": {"value": "Semi-Detached house"}},
            "C3": {"total_floor_area": 55, "built_form": 3, "habitable_room_count": 2,
                    "dwelling_type": {"value": "Flat"}},  # FLAT — excluded from sqm
        }
        return {"data": certs.get(cn, {})}

    monkeypatch.setattr(http, "get_json", fake_get_json)
    # Clear module cache
    epc._council_cache.clear()

    out = epc.fetch({"district": "AL1", "local_authority": "St Albans"}, "TOKEN")
    assert out["epc_n"] == 3  # C1, C2, C3 all in AL1
    # Houses only for sqm: C1=120, C2=80 (C3 is a Flat, excluded)
    assert out["epc_median_sqm"] == 100.0  # median of [80, 120]
    assert round(out["pct_detached"], 2) == 0.33  # 1 detached out of 3
    assert out["median_rooms"] == 4  # median of [3, 5] from houses


def test_epc_no_token():
    out = epc.fetch({"district": "AL8", "local_authority": "Welwyn Hatfield"}, "")
    assert out["epc_median_sqm"] is None
    assert out["epc_n"] == 0
