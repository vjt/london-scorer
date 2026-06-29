from . import http

def outcode_centroid(outcode):
    r = http.get_json(f"https://api.postcodes.io/outcodes/{outcode}")["result"]
    las = r.get("admin_district") or []
    return {"lat": r["latitude"], "lon": r["longitude"],
            "local_authority": las[0] if las else None}
