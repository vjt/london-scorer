from .. import http

# Nomis Census 2021 dataset IDs
# NM_2041_1 = TS021 Ethnic group (20 categories)
# NM_2051_1 = TS030 Religion (10 categories)
_TS021_URL = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2041_1.jsonstat.json"
_TS030_URL = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2051_1.jsonstat.json"

_TS021_GEOGRAPHY = "geography"
_TS030_GEOGRAPHY = "geography"


def _find_value(obs, dim_key, label):
    """Return the numeric value for a given category label in an obs list."""
    for item in obs:
        dims = item.get("dimensions", {})
        for key, val in dims.items():
            if val.get("value") == label:
                return item["value"]
    return None


def fetch(district_row, la_code_lookup):
    """Fetch Census 2021 ethnicity (TS021) and religion (TS030) shares for a LA.

    Args:
        district_row: dict with at least a "local_authority" key.
        la_code_lookup: callable(la_name) -> ONS code string (e.g. "E07000241").

    Returns:
        dict with "pct_white" and "pct_christian_or_none" as floats (or None on error).
    """
    la_name = district_row["local_authority"]
    la_code = la_code_lookup(la_name)

    pct_white = None
    pct_christian_or_none = None

    # --- TS021: Ethnicity ---
    try:
        eth_data = http.get_json(
            f"{_TS021_URL}?TS021&geography={la_code}",
            cache_key=f"nomis:TS021:{la_code}",
        )
        obs = eth_data.get("obs", [])
        white = _find_value(obs, "c2021_eth_20", "White")
        total = _find_value(obs, "c2021_eth_20", "Total")
        if white is not None and total:
            pct_white = white / total
    except Exception:
        pass

    # --- TS030: Religion ---
    try:
        rel_data = http.get_json(
            f"{_TS030_URL}?TS030&geography={la_code}",
            cache_key=f"nomis:TS030:{la_code}",
        )
        obs = rel_data.get("obs", [])
        christian = _find_value(obs, "c2021_rel_10", "Christian")
        no_religion = _find_value(obs, "c2021_rel_10", "No religion")
        total = _find_value(obs, "c2021_rel_10", "Total")
        if christian is not None and no_religion is not None and total:
            pct_christian_or_none = (christian + no_religion) / total
    except Exception:
        pass

    return {"pct_white": pct_white, "pct_christian_or_none": pct_christian_or_none}
