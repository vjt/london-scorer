from london_scorer.fetchers import crime
from london_scorer import http

def test_crime_counts(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: [{"id":1},{"id":2},{"id":3}])
    row = {"centroid":{"lat":51.8,"lon":-0.2}}
    assert crime.fetch(row) == {"crime_1mi_count": 3}
