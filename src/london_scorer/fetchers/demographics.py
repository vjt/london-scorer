"""Census 2021 ethnicity + religion shares via Nomis API (LA level)."""

from .. import http

# Nomis dataset IDs for Census 2021
_TS021_ID = "NM_2041_1"  # Ethnic group
_TS030_ID = "NM_2049_1"  # Religion

_BASE = "https://www.nomisweb.co.uk/api/v01/dataset"


def _nomis_query(dataset_id, geography, cache_tag):
    """Query Nomis and return list of obs dicts."""
    url = f"{_BASE}/{dataset_id}.data.json"
    data = http.get_json(
        url,
        params={"date": "latest", "geography": geography, "measures": "20100"},
        cache_key=f"nomis:{cache_tag}:{geography}",
    )
    return data.get("obs", [])


def _obs_to_map(obs):
    """Parse Nomis obs into {description_keyword: value}.

    Nomis descriptions look like:
      "Persons Value for Camden (geography), White (Ethnic group) for 2021 ..."
    We extract the category between the first ", " and the next " (" to get "White".
    The total row has no comma category — its desc starts with "Persons Value for ... (geography) for ...".
    """
    result = {}
    for o in obs:
        val_block = o.get("obs_value", {})
        value = val_block.get("value")
        desc = val_block.get("description", "")
        if value is None:
            continue
        # Try to extract category from desc
        # Pattern: "... (geography), CATEGORY (DimName) for ..."
        # or total: "... (geography) for ..."
        parts = desc.split("(geography)")
        if len(parts) < 2:
            continue
        after = parts[1].strip()
        if after.startswith(", "):
            # Has a category
            cat_part = after[2:]  # strip ", "
            # Category is everything before the next " ("
            paren_idx = cat_part.find(" (")
            if paren_idx > 0:
                cat = cat_part[:paren_idx].strip().lower()
            else:
                cat = cat_part.strip().lower()
            result[cat] = value
        elif after.startswith(" for ") or after.startswith("for "):
            result["_total"] = value
    return result


def fetch(district_row, la_code_lookup):
    """Fetch Census 2021 ethnicity + religion shares for a local authority."""
    la_name = district_row["local_authority"]
    la_code = la_code_lookup(la_name)

    if not la_code:
        return {"pct_white": None, "pct_christian_or_none": None}

    pct_white = None
    pct_christian_or_none = None

    # --- TS021: Ethnicity ---
    try:
        obs = _nomis_query(_TS021_ID, la_code, "TS021")
        m = _obs_to_map(obs)
        total = m.get("_total")
        white = m.get("white")
        if white is not None and total and total > 0:
            pct_white = round(white / total, 4)
    except Exception:
        pass

    # --- TS030: Religion ---
    try:
        obs = _nomis_query(_TS030_ID, la_code, "TS030")
        m = _obs_to_map(obs)
        total = m.get("_total")
        christian = m.get("christian")
        no_rel = m.get("no religion")
        if christian is not None and no_rel is not None and total and total > 0:
            pct_christian_or_none = round((christian + no_rel) / total, 4)
    except Exception:
        pass

    return {"pct_white": pct_white, "pct_christian_or_none": pct_christian_or_none}
