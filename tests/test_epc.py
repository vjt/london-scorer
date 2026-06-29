from london_scorer.fetchers import epc
from london_scorer import http

def test_epc_aggregates(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: {"rows":[
        {"total-floor-area":"100","built-form":"Detached"},
        {"total-floor-area":"80","built-form":"Semi-Detached"},
        {"total-floor-area":"120","built-form":"Detached"}]})
    out = epc.fetch({"district":"AL8"}, "TOKEN")
    assert out["epc_n"] == 3
    assert out["epc_median_sqm"] == 100.0
    assert round(out["pct_detached"], 2) == 0.67
