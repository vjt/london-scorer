"""Discover candidate postcode districts via station enumeration + commute filter."""

from . import http, geo, stations, commute

# Backstop seed outcodes — ALWAYS included in output regardless of threshold.
_SEED_OUTCODES = [
    "AL1", "AL3", "AL4",   # St Albans
    "AL5",                  # Harpenden
    "AL8",                  # Welwyn Garden City
    "WD7",                  # Radlett
    "NW7",                  # Mill Hill
    "AL9",                  # Hatfield / Brookmans Park
    "N14",                  # Southgate / Arnos Grove
    "N21",                  # Winchmore Hill
    "WD6",                  # Borehamwood / Elstree
    "EN6",                  # Potters Bar / Cuffley
    "N20",                  # Oakleigh Park area
    "EN5",                  # New Barnet / Hadley Wood
]


def station_outcode(lat, lon):
    r = http.get_json("https://api.postcodes.io/outcodes",
                      params={"lat": lat, "lon": lon, "limit": 1},
                      cache_key=f"oc:{lat},{lon}")
    res = r.get("result") or []
    return res[0]["outcode"] if res else None


def _resolve_district(oc, cfg, app_key, date, force=False):
    """Resolve an outcode → centroid + commute. Returns row dict or None.

    If force=True (seeds), include even if commute exceeds threshold.
    """
    try:
        c = geo.outcode_centroid(oc)
    except Exception:
        return None
    d = commute.door_to_door(c["lat"], c["lon"], app_key, cfg, date)
    if d["am"] is None:
        if not force:
            return None
        # For seeds with no journey result, estimate high commute
        d = {"am": 90, "pm": 90}

    threshold = cfg.get("commute_threshold_min", 60)
    if not force and d["am"] > threshold:
        return None

    return {
        "district": oc,
        "centroid": c,
        "local_authority": c["local_authority"],
        "commute_am": d["am"],
        "commute_pm": d["pm"],
    }


def discover(cfg, app_key, date):
    """Discover candidate districts: station-based + seed backstop.

    1. Enumerate stations (national rail CSV + TfL lines), map → outcodes.
    2. Add seed outcodes as backstop (ALWAYS included, not threshold-filtered).
    3. Journey-plan each → KX, keep within threshold (except seeds).
    """
    out, seen, discovered = [], set(), set()

    # 1) Station-based discovery (threshold-filtered)
    all_stations = stations.north_stations(cfg["kx_lines"], app_key)
    print(f"  Enumerating {len(all_stations)} stations north of KX …")
    for s in all_stations:
        oc = station_outcode(s["lat"], s["lon"])
        if not oc or oc in seen:
            continue
        seen.add(oc)
        row = _resolve_district(oc, cfg, app_key, date, force=False)
        if row:
            out.append(row)
            discovered.add(oc)

    # 2) Seed backstop — ALWAYS included even if over threshold or already seen-but-dropped
    seed_added = 0
    for oc in _SEED_OUTCODES:
        if oc in discovered:
            continue  # already in output
        row = _resolve_district(oc, cfg, app_key, date, force=True)
        if row:
            out.append(row)
            discovered.add(oc)
            seed_added += 1
    if seed_added:
        print(f"  Added {seed_added} districts from seed backstop (no threshold filter)")

    print(f"  {len(out)} total districts")
    return sorted(out, key=lambda r: r["commute_am"])
