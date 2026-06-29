"""EPC housing-stock fetcher using the new gov.uk API.

Uses the search endpoint at api.get-energy-performance-data.communities.gov.uk.
The new API search returns only certificate summaries (no floor area / built form),
so we compute an energy-band quality score as a housing stock proxy.
"""

import statistics
from .. import http

_BASE = "https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search"

_BAND_SCORE = {"A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1}

# Number of random postcodes to try per outcode
_MAX_ATTEMPTS = 3


def _try_postcode(pc_nospace, bearer, outcode, attempt):
    """Query EPC API for a single postcode. Returns cert list or []."""
    try:
        data = http.get_json(
            _BASE,
            params={"postcode": pc_nospace, "page_size": 100},
            headers={
                "Authorization": f"Bearer {bearer}",
                "Accept": "application/json",
            },
            cache_key=f"epc_new:{outcode}:{attempt}",
        )
    except Exception:
        return []
    result = data.get("data", [])
    if isinstance(result, dict):  # error response like {"error": "..."}
        return []
    return result


def fetch(row, bearer):
    """Fetch EPC housing stock metrics for a district.

    Tries multiple random postcodes in the outcode to maximise hit rate.
    Returns dict with epc_band_score (mean energy band quality, 1–7 scale)
    and epc_n (number of certificates sampled).
    """
    if not bearer:
        return {"epc_band_score": None, "epc_n": 0}

    outcode = row["district"]
    all_certs = []

    for attempt in range(_MAX_ATTEMPTS):
        # Get a random postcode in this outcode
        try:
            rr = http.get_json(
                "https://api.postcodes.io/random/postcodes",
                params={"outcode": outcode},
                cache_key=f"random_pc_epc:{outcode}:{attempt}",
            )
            pc = rr.get("result", {}).get("postcode", "").replace(" ", "")
        except Exception:
            continue
        if not pc:
            continue

        certs = _try_postcode(pc, bearer, outcode, attempt)
        if certs:
            all_certs.extend(certs)
            break  # got data, no need to retry

    if not all_certs:
        return {"epc_band_score": None, "epc_n": 0}

    scores = [_BAND_SCORE[c["currentEnergyEfficiencyBand"]]
              for c in all_certs
              if c.get("currentEnergyEfficiencyBand") in _BAND_SCORE]

    if not scores:
        return {"epc_band_score": None, "epc_n": len(all_certs)}

    return {
        "epc_band_score": round(statistics.mean(scores), 2),
        "epc_n": len(all_certs),
    }
