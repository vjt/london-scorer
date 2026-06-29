from london_scorer import stations, http


def test_north_filter_and_dedup(monkeypatch):
    """Test TfL line_stations + north_stations with no CSV (TfL-only mode)."""
    fake = {
        "gn": [{"id": "S1", "commonName": "Hatfield", "lat": 51.76, "lon": -0.22},
               {"id": "S2", "commonName": "Finsbury Park", "lat": 51.56, "lon": -0.10}],
        "tl": [{"id": "S1", "commonName": "Hatfield", "lat": 51.76, "lon": -0.22},
               {"id": "S3", "commonName": "Sutton", "lat": 51.35, "lon": -0.19}],
    }
    monkeypatch.setattr(http, "get_json", lambda url, **k: fake["gn" if "great-northern" in url else "tl"])
    # Disable CSV loading so we only test TfL path
    monkeypatch.setattr(stations, "load_national_rail_stations", lambda *a, **k: [])
    out = stations.north_stations(["great-northern", "thameslink"], "KEY")
    ids = {s["id"] for s in out}
    assert ids == {"S1", "S2"}        # S3 (Sutton, south) dropped; S1 deduped
