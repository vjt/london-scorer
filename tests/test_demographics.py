from london_scorer.fetchers import demographics
from london_scorer import http


def test_demo_shares(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda url, **k: {
        "obs": [{"dimensions": {"c2021_eth_20": {"value": "White"}}, "value": 800},
                {"dimensions": {"c2021_eth_20": {"value": "Total"}}, "value": 1000}]} if "TS021" in url else {
        "obs": [{"dimensions": {"c2021_rel_10": {"value": "Christian"}}, "value": 500},
                {"dimensions": {"c2021_rel_10": {"value": "No religion"}}, "value": 300},
                {"dimensions": {"c2021_rel_10": {"value": "Total"}}, "value": 1000}]})
    out = demographics.fetch({"local_authority": "Welwyn Hatfield"}, lambda la: "E07000241")
    assert out["pct_white"] == 0.8
    assert out["pct_christian_or_none"] == 0.8
