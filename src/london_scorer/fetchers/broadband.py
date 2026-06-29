"""Broadband FTTP/gigabit fetcher.

Primary source: Ofcom Connected Nations postcode CSV (bulk, loaded once).
Fallback: known FTTP availability % by local authority (from Ofcom published stats).
"""

import pandas as pd

# Fallback: Ofcom Connected Nations 2024 published LA-level gigabit availability %
# Source: Ofcom Connected Nations Update Spring 2025 / Autumn 2024 reports
# These are approximate and will be superseded by bulk CSV when available.
_LA_FTTP_FALLBACK = {
    "Camden": 96.0,
    "Islington": 97.0,
    "Hackney": 96.0,
    "Haringey": 94.0,
    "Enfield": 85.0,
    "Barnet": 82.0,
    "Brent": 90.0,
    "Harrow": 78.0,
    "Waltham Forest": 90.0,
    "Newham": 95.0,
    "Redbridge": 80.0,
    "St Albans": 72.0,
    "Welwyn Hatfield": 68.0,
    "Hertsmere": 70.0,
    "East Hertfordshire": 55.0,
    "North Hertfordshire": 50.0,
    "Central Bedfordshire": 45.0,
    "Broxbourne": 75.0,
    "Three Rivers": 65.0,
    "Watford": 88.0,
    "Dacorum": 60.0,
    "Stevenage": 72.0,
    "Luton": 78.0,
}


def load(csv_path):
    """Load Ofcom CSV and derive gigabit availability % per outcode."""
    df = pd.read_csv(csv_path, low_memory=False)
    # Try known column name variants
    pc_col = None
    for c in ["postcode", "Postcode", "POSTCODE"]:
        if c in df.columns:
            pc_col = c
            break
    gb_col = None
    for c in ["gigabit_pct", "% Gigabit availability", "gigabit_available", "Gigabit availability"]:
        if c in df.columns:
            gb_col = c
            break
    if pc_col is None or gb_col is None:
        raise ValueError(f"Cannot find postcode/gigabit columns in {csv_path}. Columns: {list(df.columns)[:10]}")
    df["outcode"] = df[pc_col].astype(str).str.split().str[0]
    return df.groupby("outcode")[gb_col].mean().reset_index().rename(columns={gb_col: "gigabit_pct"})


def fetch(row, df=None):
    """Look up FTTP availability % for a district.

    Uses bulk DataFrame if available, otherwise falls back to LA-level estimates.
    """
    if df is not None and not df.empty:
        match = df[df["outcode"] == row["district"]]
        if not match.empty:
            return {"fttp_pct": round(float(match.iloc[0]["gigabit_pct"]), 1)}

    # Fallback: LA-level estimate
    la = row.get("local_authority", "")
    if la in _LA_FTTP_FALLBACK:
        return {"fttp_pct": _LA_FTTP_FALLBACK[la]}

    return {"fttp_pct": None}
