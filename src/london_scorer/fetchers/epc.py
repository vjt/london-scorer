"""EPC housing-stock fetcher — query by LOCAL AUTHORITY, bucket by outcode.

Strategy: one paginated bulk search per council → all cert numbers → bucket
by outcode → fetch detail for a sample of ~30 certs per outcode → compute
median sqm (HOUSES ONLY), % detached, median rooms.
"""

import statistics
import sys
from collections import defaultdict
from .. import http

_SEARCH = "https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search"
_CERT = "https://api.get-energy-performance-data.communities.gov.uk/api/certificate"

_DETACHED_BUILT_FORMS = {1, "1"}
_DETACHED_DWELLING_TYPES = {"detached house", "detached bungalow", "detached"}
_FLAT_KEYWORDS = {"flat", "maisonette"}

_SAMPLE_PER_OUTCODE = 30  # how many cert details to fetch per outcode
_PAGE_SIZE = 5000
_MAX_PAGES = 1  # ONE page of 5000 certs is enough — gives ~500+ per outcode


# ── council-level bulk search (cached per council, paginated) ──────────

def _fetch_council_certs(council_name, bearer):
    """Paginate council search, return {outcode: [cert_number, ...]}."""
    buckets = defaultdict(list)
    page = 1
    while True:
        try:
            data = http.get_json(
                _SEARCH,
                params={"council[]": council_name, "page_size": _PAGE_SIZE, "current_page": page},
                headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
                cache_key=f"epc_council:{council_name}:p{page}",
                timeout=30,
            )
        except Exception as e:
            sys.stderr.write(f"    EPC council search {council_name} p{page}: {e}\n")
            break

        rows = data.get("data", [])
        if isinstance(rows, dict):  # error
            sys.stderr.write(f"    EPC council {council_name}: {rows.get('error', '?')}\n")
            break
        if not rows:
            break

        for r in rows:
            pc = r.get("postcode", "")
            if " " in pc:
                oc = pc.split()[0]
            else:
                oc = pc[:3] if len(pc) > 3 else pc
            cn = r.get("certificateNumber")
            if cn:
                buckets[oc].append(cn)

        pag = data.get("pagination", {})
        total_pages = pag.get("totalPages", 1)
        total_recs = pag.get("totalRecords", "?")
        sys.stderr.write(f"    {council_name} p{page} ({sum(len(v) for v in buckets.values())} certs of {total_recs})\n")
        sys.stderr.flush()
        if page >= min(total_pages, _MAX_PAGES):
            break
        page += 1

    return dict(buckets)


# ── individual cert detail fetch ───────────────────────────────────────

def _fetch_cert(cert_number, bearer):
    try:
        data = http.get_json(
            _CERT,
            params={"certificate_number": cert_number},
            headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
            cache_key=f"epc_cert:{cert_number}",
            timeout=12,
        )
    except Exception:
        return None
    d = data.get("data", {})
    if not isinstance(d, dict) or "error" in d:
        return None
    return d


def _is_detached(cert):
    bf = cert.get("built_form")
    if bf in _DETACHED_BUILT_FORMS:
        return True
    dt = cert.get("dwelling_type")
    if isinstance(dt, dict):
        dt = dt.get("value", "")
    if isinstance(dt, str) and dt.lower().strip() in _DETACHED_DWELLING_TYPES:
        return True
    return False


def _is_house(cert):
    dt = cert.get("dwelling_type")
    if isinstance(dt, dict):
        dt = dt.get("value", "")
    if not isinstance(dt, str):
        pt = cert.get("property_type")
        return pt not in (2, "2", 3, "3")
    return not any(kw in dt.lower() for kw in _FLAT_KEYWORDS)


# ── per-outcode aggregation from sampled cert details ──────────────────

def _aggregate(details):
    """Compute trimmed-median sqm (houses only, cap 400), pct_detached, median rooms."""
    n = len(details)
    if n == 0:
        return {"epc_median_sqm": None, "pct_detached": None, "median_rooms": None, "epc_n": 0}

    houses = [d for d in details if _is_house(d)]

    areas = []
    for d in houses:
        try:
            a = float(d.get("total_floor_area", 0))
            if 10 < a <= 400:  # drop implausible: <10 sqm or >400 sqm (commercial/mansion)
                areas.append(a)
        except (TypeError, ValueError):
            pass

    # Trimmed median: drop top and bottom 10% to remove outliers
    if len(areas) >= 5:
        areas.sort()
        trim = max(1, len(areas) // 10)
        areas = areas[trim:-trim]

    rooms = []
    for d in houses:
        try:
            r = int(d.get("habitable_room_count", 0))
            if 0 < r <= 20:  # sanity cap
                rooms.append(r)
        except (TypeError, ValueError):
            pass

    det = sum(1 for d in details if _is_detached(d))

    return {
        "epc_median_sqm": round(statistics.median(areas), 1) if areas else None,
        "pct_detached": round(det / n, 4) if n else None,
        "median_rooms": int(statistics.median(rooms)) if rooms else None,
        "epc_n": n,
    }


# ── public API: council-level bulk, then per-outcode sample ────────────

# Module-level cache: council → {outcode: [cert_numbers]}
_council_cache = {}


def load_council(council_name, bearer):
    """Ensure council certs are loaded (cached across calls)."""
    if council_name not in _council_cache:
        _council_cache[council_name] = _fetch_council_certs(council_name, bearer)
    return _council_cache[council_name]


def fetch(row, bearer):
    """Fetch EPC housing stock for a district via its council's bulk data."""
    if not bearer:
        return {"epc_median_sqm": None, "pct_detached": None, "median_rooms": None, "epc_n": 0}

    outcode = row["district"]
    council = row.get("local_authority", "")
    if not council:
        return {"epc_median_sqm": None, "pct_detached": None, "median_rooms": None, "epc_n": 0}

    # Load all cert numbers for this council (cached)
    buckets = load_council(council, bearer)
    cert_numbers = buckets.get(outcode, [])

    if not cert_numbers:
        return {"epc_median_sqm": None, "pct_detached": None, "median_rooms": None, "epc_n": 0}

    # Sample up to _SAMPLE_PER_OUTCODE certs, spread evenly across the list
    step = max(1, len(cert_numbers) // _SAMPLE_PER_OUTCODE)
    sample = cert_numbers[::step][:_SAMPLE_PER_OUTCODE]

    details = []
    for cn in sample:
        d = _fetch_cert(cn, bearer)
        if d:
            details.append(d)

    result = _aggregate(details)
    sys.stderr.write(f"    {outcode} epc_n={result['epc_n']} sqm={result.get('epc_median_sqm')} det={result.get('pct_detached')}\n")
    sys.stderr.flush()
    return result
