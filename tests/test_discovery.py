from london_scorer import discovery, stations, geo, commute


def test_discover_filters_by_threshold(monkeypatch):
    monkeypatch.setattr(stations, "north_stations", lambda *a, **k: [{"id":"S1","lat":51.8,"lon":-0.2}])
    monkeypatch.setattr(discovery, "station_outcode", lambda lat,lon: "AL8")
    monkeypatch.setattr(discovery, "_SEED_OUTCODES", [])  # disable seeds for unit test
    monkeypatch.setattr(geo, "outcode_centroid", lambda oc: {"lat":51.8,"lon":-0.2,"local_authority":"Welwyn Hatfield"})
    monkeypatch.setattr(commute, "door_to_door", lambda *a, **k: {"am":35,"pm":38})
    cfg = {"kx_lines":["x"], "commute_threshold_min":45, "am_arrive_by":"0930","pm_depart_at":"1730","office_walk_min":12}
    out = discovery.discover(cfg, "KEY", "20260703")
    assert out[0]["district"] == "AL8" and out[0]["commute_am"] == 35


def test_discover_drops_over_threshold(monkeypatch):
    monkeypatch.setattr(stations, "north_stations", lambda *a, **k: [{"id":"S1","lat":51.9,"lon":-0.3}])
    monkeypatch.setattr(discovery, "station_outcode", lambda lat,lon: "SG6")
    monkeypatch.setattr(discovery, "_SEED_OUTCODES", [])
    monkeypatch.setattr(geo, "outcode_centroid", lambda oc: {"lat":51.9,"lon":-0.3,"local_authority":"North Herts"})
    monkeypatch.setattr(commute, "door_to_door", lambda *a, **k: {"am":52,"pm":55})
    cfg = {"kx_lines":["x"], "commute_threshold_min":45, "am_arrive_by":"0930","pm_depart_at":"1730","office_walk_min":12}
    assert discovery.discover(cfg, "KEY", "20260703") == []
