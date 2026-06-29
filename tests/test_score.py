from london_scorer import score


def test_commute_inverted_lower_is_better():
    rows = [{"district": "A", "commute_am": 30, "primary_good": 4},
            {"district": "B", "commute_am": 45, "primary_good": 1}]
    out = score.normalise_and_score(rows, {"commute": 0.5, "schools": 0.5})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    assert a["score"] > b["score"]   # A: faster commute + more good schools


def test_crime_inverted_lower_is_better():
    rows = [{"district": "X", "crime_1mi_count": 10},
            {"district": "Y", "crime_1mi_count": 100}]
    out = score.normalise_and_score(rows, {"crime": 1.0})
    x = next(r for r in out if r["district"] == "X")
    y = next(r for r in out if r["district"] == "Y")
    assert x["score"] > y["score"]   # lower crime → higher score


def test_equal_values_no_crash():
    """When all values are equal, min==max edge case must not crash."""
    rows = [{"district": "A", "commute_am": 30},
            {"district": "B", "commute_am": 30}]
    out = score.normalise_and_score(rows, {"commute": 1.0})
    for r in out:
        assert 0.0 <= r["score"] <= 1.0


def test_missing_dimension_skipped():
    """Rows without a dimension column should have it skipped gracefully."""
    rows = [{"district": "A", "commute_am": 20},
            {"district": "B", "commute_am": 40}]
    # schools weight given but no primary_good in data → ignored
    out = score.normalise_and_score(rows, {"commute": 0.5, "schools": 0.5})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    assert a["score"] > b["score"]
    assert "score" in a and "score" in b


def test_score_sorted_descending():
    rows = [{"district": "A", "fttp_pct": 0.2},
            {"district": "B", "fttp_pct": 0.9},
            {"district": "C", "fttp_pct": 0.5}]
    out = score.normalise_and_score(rows, {"fttp": 1.0})
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)


def test_secondary_good_added_to_schools():
    """schools dimension uses primary_good + secondary_good when both present."""
    rows = [
        {"district": "A", "primary_good": 2, "secondary_good": 3},  # total 5
        {"district": "B", "primary_good": 8, "secondary_good": 0},  # total 8
    ]
    out = score.normalise_and_score(rows, {"schools": 1.0})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    assert b["score"] > a["score"]


def test_none_values_skipped():
    """None values for a dimension should be treated as missing for that row."""
    rows = [{"district": "A", "epc_band_score": None},
            {"district": "B", "epc_band_score": 5.0}]
    out = score.normalise_and_score(rows, {"house": 1.0})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    # B has a value; A has None → A's score comes entirely from available dims
    assert "score" in a
    assert "score" in b
