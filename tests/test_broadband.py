import pandas as pd
from london_scorer.fetchers import broadband

def test_fttp_lookup():
    df = pd.DataFrame([{"outcode":"AL8","gigabit_pct":95.0},{"outcode":"N14","gigabit_pct":80.0}])
    assert broadband.fetch({"district":"AL8"}, df) == {"fttp_pct": 95.0}
