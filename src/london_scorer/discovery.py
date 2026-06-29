from . import http, geo, stations, commute


def station_outcode(lat, lon):
    r = http.get_json("https://api.postcodes.io/outcodes",
                      params={"lat": lat, "lon": lon, "limit": 1},
                      cache_key=f"oc:{lat},{lon}")
    res = r.get("result") or []
    return res[0]["outcode"] if res else None


def discover(cfg, app_key, date):
    out, seen = [], set()
    for s in stations.north_stations(cfg["kx_lines"], app_key):
        oc = station_outcode(s["lat"], s["lon"])
        if not oc or oc in seen:
            continue
        seen.add(oc)
        c = geo.outcode_centroid(oc)
        d = commute.door_to_door(c["lat"], c["lon"], app_key, cfg, date)
        if d["am"] is None or d["am"] > cfg["commute_threshold_min"]:
            continue
        out.append({"district": oc, "centroid": c, "local_authority": c["local_authority"],
                    "commute_am": d["am"], "commute_pm": d["pm"]})
    return sorted(out, key=lambda r: r["commute_am"])
