from . import http


def outcode_centroid(outcode):
    r = http.get_json(f"https://api.postcodes.io/outcodes/{outcode}")["result"]
    las = r.get("admin_district") or []
    return {"lat": r["latitude"], "lon": r["longitude"],
            "local_authority": las[0] if las else None}


def la_gss_code(outcode):
    """Get the GSS code for the local authority covering an outcode.

    Uses a random postcode lookup in the outcode to obtain the code —
    the outcode endpoint alone doesn't return GSS codes.
    """
    try:
        r = http.get_json(
            f"https://api.postcodes.io/outcodes/{outcode}",
            cache_key=f"outcode:{outcode}")
        # Use the outcode random-postcode endpoint to find a real postcode
        rr = http.get_json(
            f"https://api.postcodes.io/random/postcodes",
            params={"outcode": outcode},
            cache_key=f"random_pc:{outcode}")
        result = rr.get("result") or {}
        codes = result.get("codes") or {}
        return codes.get("admin_district")
    except Exception:
        return None
