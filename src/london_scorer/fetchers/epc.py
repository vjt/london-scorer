"""EPC housing-stock fetcher — median floor area, % detached, habitable rooms.

Uses the new gov.uk EPC API:
  1. Search by postcode → list of certificate numbers
  2. Fetch each certificate → total_floor_area, built_form, habitable_room_count
  3. Aggregate per outcode: median sqm, % detached, median rooms

Requires EPC_BEARER_TOKEN in .env.
"""

import statistics
import time
from .. import http

_SEARCH = "https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search"
_CERT = "https://api.get-energy-performance-data.communities.gov.uk/api/certificate"

# built_form codes from RdSAP schema: 1=Detached, 2=Semi, 3=End-Terrace, 4=Mid-Terrace, 5=Enclosed End, 6=Enclosed Mid
# dwelling_type.value can also be "Detached house" etc.
_DETACHED_BUILT_FORMS = {1, "1"}
_DETACHED_DWELLING_TYPES = {"detached house", "detached bungalow", "detached"}

# How many postcodes to sample per outcode, how many certs to fetch details for
_POSTCODES_PER_OUTCODE = 3
_MAX_CERTS_PER_POSTCODE = 30
_MAX_DETAIL_FETCHES = 40  # cap total individual cert fetches per outcode


def _search_certs(postcode_nospace, bearer, cache_suffix):
    """Search EPC → list of {certificateNumber, ...}."""
    try:
        data = http.get_json(
            _SEARCH,
            params={"postcode": postcode_nospace, "page_size": _MAX_CERTS_PER_POSTCODE},
            headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
            cache_key=f"epc_search:{postcode_nospace}:{cache_suffix}",
        )
    except Exception:
        return []
    result = data.get("data", [])
    return result if isinstance(result, list) else []


def _fetch_cert_detail(cert_number, bearer):
    """Fetch full cert → {total_floor_area, built_form, habitable_room_count, dwelling_type}."""
    time.sleep(0.1)  # rate-limit courtesy (EPC API: 6000 req / 5 min)
    try:
        data = http.get_json(
            _CERT,
            params={"certificate_number": cert_number},
            headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
            cache_key=f"epc_cert:{cert_number}",
        )
    except Exception:
        return None
    d = data.get("data", {})
    if not isinstance(d, dict) or "error" in d:
        return None
    return d


def _is_detached(cert):
    """Check if a cert represents a detached property."""
    bf = cert.get("built_form")
    if bf in _DETACHED_BUILT_FORMS:
        return True
    dt = cert.get("dwelling_type")
    if isinstance(dt, dict):
        dt = dt.get("value", "")
    if isinstance(dt, str) and dt.lower().strip() in _DETACHED_DWELLING_TYPES:
        return True
    return False


def fetch(row, bearer):
    """Fetch EPC housing stock for a district: median sqm, % detached, median rooms.

    Samples multiple postcodes in the outcode, fetches individual cert details,
    aggregates. Returns reliable data only when epc_n >= 10.
    """
    if not bearer:
        return {"epc_median_sqm": None, "pct_detached": None, "median_rooms": None, "epc_n": 0}

    outcode = row["district"]
    all_details = []
    fetches_remaining = _MAX_DETAIL_FETCHES

    for attempt in range(_POSTCODES_PER_OUTCODE):
        if fetches_remaining <= 0:
            break
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

        certs = _search_certs(pc, bearer, attempt)
        for c in certs:
            if fetches_remaining <= 0:
                break
            cn = c.get("certificateNumber")
            if not cn:
                continue
            detail = _fetch_cert_detail(cn, bearer)
            if detail:
                all_details.append(detail)
            fetches_remaining -= 1

    n = len(all_details)
    if n == 0:
        return {"epc_median_sqm": None, "pct_detached": None, "median_rooms": None, "epc_n": 0}

    # Extract floor areas (skip zero/missing)
    areas = []
    for d in all_details:
        a = d.get("total_floor_area")
        if a is not None:
            try:
                a = float(a)
                if a > 0:
                    areas.append(a)
            except (ValueError, TypeError):
                pass

    # Extract rooms
    rooms = []
    for d in all_details:
        r = d.get("habitable_room_count")
        if r is not None:
            try:
                rooms.append(int(r))
            except (ValueError, TypeError):
                pass

    # Count detached
    det_count = sum(1 for d in all_details if _is_detached(d))

    return {
        "epc_median_sqm": round(statistics.median(areas), 1) if areas else None,
        "pct_detached": round(det_count / n, 4) if n > 0 else None,
        "median_rooms": int(statistics.median(rooms)) if rooms else None,
        "epc_n": n,
    }
