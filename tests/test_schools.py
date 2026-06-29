import pandas as pd
from london_scorer.fetchers import schools

def test_fetch_counts_good_by_phase():
    df = pd.DataFrame([
        {"outcode":"AL8","phase":"primary","rating":"Outstanding"},
        {"outcode":"AL8","phase":"primary","rating":"Requires improvement"},
        {"outcode":"AL8","phase":"secondary","rating":"Good"},
        {"outcode":"N14","phase":"primary","rating":"Good"},
    ])
    assert schools.fetch({"district":"AL8"}, df) == {"primary_good":1, "secondary_good":1}
