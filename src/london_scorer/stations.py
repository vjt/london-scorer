"""Station enumeration from comprehensive UK stations CSV + TfL StopPoints.

Uses doogal.co.uk/UkStationsCSV (all 2,595 GB railway stations with lat/lon)
as the PRIMARY source, with TfL StopPoints as supplementary for Tube/DLR.
"""

import csv
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path

from . import http

KX = {"lat": 51.5308, "lon": -0.1238}

_STATIONS_CSV = Path("data/uk-stations.csv")


def _haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def load_national_rail_stations(csv_path=None, max_km=65):
    """Load all GB railway stations north of KX within *max_km* from a CSV.

    Returns list[{"id": str, "name": str, "lat": float, "lon": float}].
    """
    path = Path(csv_path) if csv_path else _STATIONS_CSV
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                lat = float(r["Latitude"])
                lon = float(r["Longitude"])
            except (ValueError, KeyError):
                continue
            if lat < KX["lat"]:
                continue
            dist = _haversine_km(KX["lat"], KX["lon"], lat, lon)
            if dist > max_km:
                continue
            station_id = r.get("TLC") or r["Station"]
            out.append({
                "id": f"NR:{station_id}",
                "name": r["Station"],
                "lat": lat,
                "lon": lon,
            })
    return out


def line_stations(line_id, app_key):
    """Fetch TfL StopPoints for a single line (Tube/DLR/Overground)."""
    try:
        data = http.get_json(
            f"https://api.tfl.gov.uk/Line/{line_id}/StopPoints",
            params={"app_key": app_key},
        )
    except Exception as exc:
        print(f"⚠ Skipping TfL line {line_id}: {exc}")
        return []
    stops = data if isinstance(data, list) else data.get("stopPoints", [])
    out = []
    for sp in stops:
        if "lat" in sp and "lon" in sp:
            out.append({
                "id": sp["id"],
                "name": sp.get("commonName"),
                "lat": sp["lat"],
                "lon": sp["lon"],
            })
    return out


def north_stations(lines, app_key, stations_csv=None, max_km=65):
    """Union of TfL StopPoints (for configured lines) + national rail CSV.

    Deduplicates by name proximity (stations within 200m are considered same).
    Keeps only stations north of KX.
    """
    seen_ids, out = set(), []

    # 1) National rail CSV — primary source (wide coverage)
    for s in load_national_rail_stations(stations_csv, max_km):
        if s["id"] in seen_ids or s["lat"] < KX["lat"]:
            continue
        seen_ids.add(s["id"])
        out.append(s)

    # 2) TfL StopPoints — supplementary (Tube, DLR, Overground)
    for ln in lines:
        for s in line_stations(ln, app_key):
            if s["id"] in seen_ids or s["lat"] < KX["lat"]:
                continue
            # Dedup: skip if a national rail station is within 200m
            too_close = False
            for existing in out:
                if _haversine_km(s["lat"], s["lon"], existing["lat"], existing["lon"]) < 0.2:
                    too_close = True
                    break
            if too_close:
                continue
            seen_ids.add(s["id"])
            out.append(s)

    return out
