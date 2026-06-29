from . import http
from .stations import KX

def journey_minutes(from_lat, from_lon, app_key, when, time_is, date):
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{from_lat},{from_lon}/to/{KX['lat']},{KX['lon']}"
    try:
        data = http.get_json(url, params={"app_key": app_key, "time": when,
                                          "timeIs": time_is, "date": date},
                             cache_key=f"jp:{from_lat},{from_lon}:{when}:{time_is}:{date}")
    except Exception:
        return None
    js = data.get("journeys") or []
    return min((j["duration"] for j in js), default=None)

def door_to_door(lat, lon, app_key, cfg, date):
    walk = cfg["office_walk_min"]
    am = journey_minutes(lat, lon, app_key, cfg["am_arrive_by"].replace(":",""), "Arriving", date)
    pm = journey_minutes(lat, lon, app_key, cfg["pm_depart_at"].replace(":",""), "Departing", date)
    return {"am": am + walk if am is not None else None,
            "pm": pm + walk if pm is not None else None}
