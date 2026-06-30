import pandas as pd
from london_scorer.fetchers import schools


def test_fetch_school_quality():
    df = pd.DataFrame([
        {"outcode": "AL8", "phase": "primary", "rating": "Outstanding"},
        {"outcode": "AL8", "phase": "primary", "rating": "Requires improvement"},
        {"outcode": "AL8", "phase": "secondary", "rating": "Good"},
        {"outcode": "N14", "phase": "primary", "rating": "Good"},
    ])
    result = schools.fetch({"district": "AL8"}, df)
    assert result["primary_good"] == 1
    assert result["secondary_good"] == 1
    assert result["has_outstanding"] == 1
    # quality = 3*1(outstanding) + 2*min(1,3)(sec) + 1*min(1,5)(pri) = 6.0
    assert result["school_quality"] == 6.0
