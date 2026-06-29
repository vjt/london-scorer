from .. import http

def fetch(row, month=None):
    params = {"lat": row["centroid"]["lat"], "lng": row["centroid"]["lon"]}
    if month: params["date"] = month
    data = http.get_json("https://data.police.uk/api/crimes-street/all-crime",
                         params=params, cache_key=f"crime:{params}")
    return {"crime_1mi_count": len(data)}
