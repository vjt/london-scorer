from london_scorer.fetchers import demographics
from london_scorer import http


def test_demo_shares(monkeypatch):
    """Test with Nomis-format obs_value structure."""
    def fake_nomis(url, **k):
        if "TS021" in k.get("cache_key", ""):
            return {"obs": [
                {"obs_value": {"value": 1000, "description": "Persons Value for Welwyn Hatfield (geography) for 2021 from TS021 - Ethnic group"}},
                {"obs_value": {"value": 800, "description": "Persons Value for Welwyn Hatfield (geography), White (Ethnic group) for 2021 from TS021 - Ethnic group"}},
            ]}
        else:
            return {"obs": [
                {"obs_value": {"value": 1000, "description": "Persons Value for Welwyn Hatfield (geography) for 2021 from TS030 - Religion"}},
                {"obs_value": {"value": 500, "description": "Persons Value for Welwyn Hatfield (geography), Christian (Religion) for 2021 from TS030 - Religion"}},
                {"obs_value": {"value": 300, "description": "Persons Value for Welwyn Hatfield (geography), No religion (Religion) for 2021 from TS030 - Religion"}},
            ]}

    monkeypatch.setattr(http, "get_json", fake_nomis)
    out = demographics.fetch({"local_authority": "Welwyn Hatfield"}, lambda la: "E07000241")
    assert out["pct_white"] == 0.8
    assert out["pct_christian_or_none"] == 0.8
