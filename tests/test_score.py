from london_scorer import score


def test_commute_inverted_lower_is_better():
    rows = [{"district": "A", "commute_am": 30, "school_quality": 8.0},
            {"district": "B", "commute_am": 45, "school_quality": 3.0}]
    out = score.normalise_and_score(rows, {"commute": 0.5, "schools": 0.5})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    assert a["score"] > b["score"]


def test_crime_steep_penalty():
    """Low crime (100) must score MUCH higher than high crime (1000)."""
    rows = [{"district": "X", "crime_1mi_count": 100},
            {"district": "Y", "crime_1mi_count": 1000}]
    out = score.normalise_and_score(rows, {"crime": 1.0})
    x = next(r for r in out if r["district"] == "X")
    y = next(r for r in out if r["district"] == "Y")
    assert x["score"] > y["score"]
    assert x["score"] > 0.5   # 100 crimes should score high
    assert y["score"] < 0.1   # 1000 crimes should score very low


def test_equal_values_no_crash():
    rows = [{"district": "A", "commute_am": 30},
            {"district": "B", "commute_am": 30}]
    out = score.normalise_and_score(rows, {"commute": 1.0})
    for r in out:
        assert 0.0 <= r["score"] <= 1.0


def test_missing_dimension_skipped():
    rows = [{"district": "A", "commute_am": 20},
            {"district": "B", "commute_am": 40}]
    out = score.normalise_and_score(rows, {"commute": 0.5, "schools": 0.5})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    assert a["score"] > b["score"]


def test_score_sorted_descending():
    rows = [{"district": "A", "fttp_pct": 0.2},
            {"district": "B", "fttp_pct": 0.9},
            {"district": "C", "fttp_pct": 0.5}]
    out = score.normalise_and_score(rows, {"fttp": 1.0})
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)


def test_house_bigger_is_better():
    """House dimension uses epc_median_sqm — bigger house = higher score."""
    rows = [{"district": "A", "epc_median_sqm": 120.0},
            {"district": "B", "epc_median_sqm": 60.0}]
    out = score.normalise_and_score(rows, {"house": 1.0})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    assert a["score"] > b["score"]


def test_school_quality_dimension():
    """Schools uses school_quality composite, not raw count."""
    rows = [{"district": "A", "school_quality": 11.0},  # outstanding + secondaries
            {"district": "B", "school_quality": 5.0}]
    out = score.normalise_and_score(rows, {"schools": 1.0})
    a = next(r for r in out if r["district"] == "A")
    b = next(r for r in out if r["district"] == "B")
    assert a["score"] > b["score"]


def test_none_values_skipped():
    rows = [{"district": "A", "epc_median_sqm": None},
            {"district": "B", "epc_median_sqm": 75.0}]
    out = score.normalise_and_score(rows, {"house": 1.0})
    assert "score" in out[0]
    assert "score" in out[1]
