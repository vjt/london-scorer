"""Schools fetcher: GIAS establishment data + Ofsted inspection ratings."""

import pandas as pd

# Ofsted "good" = Outstanding (1) or Good (2)
GOOD_NUMERIC = {"1", "2"}
GOOD_TEXT = {"Outstanding", "Good"}


def load(gias_csv, ofsted_csv):
    """Load and join GIAS schools + Ofsted ratings into a compact DataFrame.

    Returns DataFrame with columns [outcode, phase, rating] where rating is
    normalised to "Outstanding" / "Good" / "Requires improvement" / "Inadequate".
    """
    g = pd.read_csv(gias_csv, encoding="latin-1", low_memory=False)
    g = g[g["EstablishmentStatus (name)"] == "Open"]
    g["outcode"] = g["Postcode"].astype(str).str.split().str[0]
    g["phase"] = g["PhaseOfEducation (name)"].str.lower().map(
        lambda s: "primary" if "primary" in str(s) else ("secondary" if "secondary" in str(s) else "other"))

    o = pd.read_csv(ofsted_csv, encoding="latin-1", low_memory=False)

    # The Ofsted column name varies between exports — try both known variants
    rating_col = None
    for candidate in ["Overall effectiveness", "Latest OEIF overall effectiveness"]:
        if candidate in o.columns:
            rating_col = candidate
            break
    if rating_col is None:
        # Fallback: find any column with "overall" and "effectiveness" in it
        for col in o.columns:
            if "overall" in col.lower() and "effect" in col.lower():
                rating_col = col
                break

    if rating_col:
        o = o.rename(columns={rating_col: "rating"})[["URN", "rating"]]
        # Normalise numeric Ofsted grades to text
        _GRADE_MAP = {"1": "Outstanding", "2": "Good", "3": "Requires improvement", "4": "Inadequate"}
        o["rating"] = o["rating"].astype(str).str.strip().map(
            lambda v: _GRADE_MAP.get(v, v))
    else:
        o = o[["URN"]].copy()
        o["rating"] = None

    m = g.merge(o, on="URN", how="left")
    return m[["outcode", "phase", "rating"]]


def fetch(row, schools_df):
    """Schools quality metric for a district.

    Returns raw counts + a composite quality score:
      school_quality = 3 × has_outstanding + 2 × has_good_secondary + 1 × has_good_primary
    This rewards QUALITY (having at least one Outstanding school and secondary
    options) over raw COUNT (which favours dense urban areas).
    """
    district = row["district"]
    all_schools = schools_df[schools_df["outcode"] == district]
    good = all_schools[all_schools["rating"].isin(GOOD_TEXT)]

    primary_good = int((good["phase"] == "primary").sum())
    secondary_good = int((good["phase"] == "secondary").sum())

    # Quality components
    has_outstanding = int((all_schools["rating"] == "Outstanding").any())
    has_good_secondary = min(secondary_good, 3)  # cap at 3, diminishing returns
    has_good_primary = min(primary_good, 5)      # cap at 5

    # Composite: outstanding is worth a lot, secondary options matter, primary caps
    school_quality = 3.0 * has_outstanding + 2.0 * has_good_secondary + 1.0 * has_good_primary

    return {
        "primary_good": primary_good,
        "secondary_good": secondary_good,
        "has_outstanding": has_outstanding,
        "school_quality": round(school_quality, 1),
    }
