from london_scorer import geo, http

def test_outcode_centroid(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: {
        "result": {"latitude": 51.80, "longitude": -0.20, "admin_district": ["St Albans"]}})
    c = geo.outcode_centroid("AL8")
    assert c["lat"] == 51.80 and c["lon"] == -0.20
    assert c["local_authority"] == "St Albans"
