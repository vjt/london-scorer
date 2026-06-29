from london_scorer import commute, http

def test_journey_minutes_picks_shortest(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: {"journeys":[{"duration":40},{"duration":33}]})
    assert commute.journey_minutes(51.8,-0.2,"KEY","0930","Arriving","20260703") == 33

def test_door_to_door_adds_office_walk(monkeypatch):
    monkeypatch.setattr(commute, "journey_minutes", lambda *a, **k: 25)
    cfg = {"am_arrive_by":"0930","pm_depart_at":"1730","office_walk_min":12}
    d = commute.door_to_door(51.8,-0.2,"KEY",cfg,"20260703")
    assert d == {"am": 37, "pm": 37}
