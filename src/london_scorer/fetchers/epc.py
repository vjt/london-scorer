import statistics
from .. import http

def fetch(row, bearer):
    data = http.get_json("https://epc.opendatacommunities.org/api/v1/domestic/search",
                         params={"postcode": row["district"], "size": 5000},
                         headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
                         cache_key=f"epc:{row['district']}")
    rows = data.get("rows") or []
    areas = [float(r["total-floor-area"]) for r in rows if r.get("total-floor-area") not in (None, "", "0")]
    det = sum(1 for r in rows if str(r.get("built-form","")).lower().startswith("detached"))
    return {"epc_n": len(rows),
            "epc_median_sqm": round(statistics.median(areas), 1) if areas else None,
            "pct_detached": round(det/len(rows), 4) if rows else None}
