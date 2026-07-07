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

# Non-residential or junk outcodes to always exclude
_JUNK_OUTCODES = {"N1C", "N1P", "N81", "NW26"}

# Override incorrect LA mappings (postcodes.io sometimes picks the wrong LA)
_LA_OVERRIDES = {
    "AL3": "St Albans",
    "AL4": "St Albans",
    "AL5": "St Albans",   # Harpenden IS St Albans district, NOT Central Bedfordshire
    "SG6": "North Hertfordshire",
    "MK3": "Milton Keynes",
    "MK8": "Milton Keynes",
    "MK10": "Milton Keynes",
    "MK14": "Milton Keynes",
}

# For seeds with wrong centroid, use a known station's coords for commute
_SEED_STATION_COORDS = {
    "AL3": (51.7505, -0.3414),   # St Albans City station
    "AL4": (51.7505, -0.3414),   # St Albans City (AL4 is nearby)
    "AL9": (51.7211, -0.1084),   # Brookmans Park station
    # Milton Keynes — all use MK Central (Avanti West Coast to Euston)
    "MK1": (52.0343, -0.7744),
    "MK2": (52.0343, -0.7744),
    "MK3": (52.0343, -0.7744),
    "MK4": (52.0343, -0.7744),
    "MK5": (52.0343, -0.7744),
    "MK6": (52.0343, -0.7744),
    "MK7": (52.0343, -0.7744),
    "MK8": (52.0343, -0.7744),
    "MK9": (52.0343, -0.7744),
    "MK10": (52.0343, -0.7744),
    "MK11": (52.0343, -0.7744),
    "MK12": (52.0343, -0.7744),
    "MK13": (52.0343, -0.7744),
    "MK14": (52.0343, -0.7744),
    "MK15": (52.0343, -0.7744),
    "MK16": (52.0343, -0.7744),
}


def station_outcode(lat, lon):
    r = http.get_json("https://api.postcodes.io/outcodes",
                      params={"lat": lat, "lon": lon, "limit": 1},
                      cache_key=f"oc:{lat},{lon}")
    res = r.get("result") or []
    return res[0]["outcode"] if res else None


def nearby_outcodes(lat, lon, radius_km=5):
    """Get all outcodes within radius_km of a point."""
    # postcodes.io /outcodes?lon=...&lat=...&radius= returns nearby outcodes
    r = http.get_json("https://api.postcodes.io/outcodes",
                      params={"lat": lat, "lon": lon,
                              "limit": 20, "radius": int(radius_km * 1000)},
                      cache_key=f"nearby_oc:{lat:.4f},{lon:.4f}:{radius_km}")
    return [item["outcode"] for item in (r.get("result") or [])]


def _resolve_district(oc, cfg, app_key, date, force=False):
    """Resolve an outcode → centroid + commute. Returns row dict or None."""
    try:
        c = geo.outcode_centroid(oc)
    except Exception:
        return None

    # Use station coords for commute if outcode centroid gives bad results
    if oc in _SEED_STATION_COORDS:
        lat, lon = _SEED_STATION_COORDS[oc]
    else:
        lat, lon = c["lat"], c["lon"]

    d = commute.door_to_door(lat, lon, app_key, cfg, date)
    if d["am"] is None:
        if not force:
            return None
        d = {"am": 90, "pm": 90}

    threshold = cfg.get("commute_threshold_min", 60)
    if not force and d["am"] > threshold:
        return None

    # Apply LA overrides
    la = _LA_OVERRIDES.get(oc, c["local_authority"])

    return {
        "district": oc,
        "centroid": c,
        "local_authority": la,
        "commute_am": d["am"],
        "commute_pm": d["pm"],
    }


def discover(cfg, app_key, date):
    """Discover candidate districts: station-based + seed backstop."""
    out, seen, discovered = [], set(), set()

    # 1) Station-based discovery (threshold-filtered)
    all_stations = stations.north_stations(cfg["kx_lines"], app_key)
    print(f"  Enumerating {len(all_stations)} stations north of KX …")
    for s in all_stations:
        dist_from_kx = stations._haversine_km(
            stations.KX["lat"], stations.KX["lon"], s["lat"], s["lon"])

        # For far-out stations (>30km), also grab nearby outcodes (5km)
        # — one station like MK Central should discover all MK1-MK16
        # For inner stations, just use the station's own outcode
        if dist_from_kx > 30:
            outcodes = nearby_outcodes(s["lat"], s["lon"], radius_km=5)
        else:
            outcodes = []
        if not outcodes:
            oc = station_outcode(s["lat"], s["lon"])
            outcodes = [oc] if oc else []

        for oc in outcodes:
            if not oc or oc in seen or oc in _JUNK_OUTCODES:
                continue
            seen.add(oc)
            row = _resolve_district(oc, cfg, app_key, date, force=False)
            if row:
                out.append(row)
                discovered.add(oc)

    # 2) Seed backstop — ALWAYS included
    seed_added = 0
    for oc in _SEED_OUTCODES:
        if oc in discovered:
            continue
        row = _resolve_district(oc, cfg, app_key, date, force=True)
        if row:
            out.append(row)
            discovered.add(oc)
            seed_added += 1
    if seed_added:
        print(f"  Added {seed_added} seeds (bypass threshold)")

    print(f"  {len(out)} total districts (junk excluded: {_JUNK_OUTCODES})")
    return sorted(out, key=lambda r: r["commute_am"])
