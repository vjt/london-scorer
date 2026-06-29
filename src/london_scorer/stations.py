from . import http

KX = {"lat": 51.5308, "lon": -0.1238}


def line_stations(line_id, app_key):
    data = http.get_json(f"https://api.tfl.gov.uk/Line/{line_id}/StopPoints",
                         params={"app_key": app_key})
    out = []
    for sp in data.get("stopPoints", data if isinstance(data, list) else []):
        if "lat" in sp and "lon" in sp:
            out.append({"id": sp["id"], "name": sp.get("commonName"),
                        "lat": sp["lat"], "lon": sp["lon"]})
    return out


def north_stations(lines, app_key):
    seen, out = set(), []
    for ln in lines:
        for s in line_stations(ln, app_key):
            if s["id"] in seen or s["lat"] < KX["lat"]:
                continue
            seen.add(s["id"]); out.append(s)
    return out
