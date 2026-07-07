from . import http
from .stations import KX


def _is_nonstop(journey: dict) -> bool:
    """True if this journey has exactly one rail/tube leg (direct train to KX).

    A bus leg to the station doesn't count as a change — only the
    rail/tube ride to KX must be nonstop.
    """
    rail_legs = [l for l in journey.get("legs", [])
                 if l.get("mode", {}).get("name") in
                 ("national-rail", "tube", "elizabeth-line", "overground", "dlr")]
    return len(rail_legs) == 1


def journey_minutes(from_lat, from_lon, app_key, when, time_is, date):
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{from_lat},{from_lon}/to/{KX['lat']},{KX['lon']}"
    try:
        data = http.get_json(url, params={"app_key": app_key, "time": when,
                                          "timeIs": time_is, "date": date},
                             cache_key=f"jp:{from_lat},{from_lon}:{when}:{time_is}:{date}")
    except Exception:
        return None
    js = data.get("journeys") or []
    # Prefer nonstop (walk → train → walk) journeys only
    nonstop = [j["duration"] for j in js if _is_nonstop(j)]
    if nonstop:
        return min(nonstop)
    # No nonstop available — return None (zone will get penalised)
    return None

def door_to_door(lat, lon, app_key, cfg, date):
    walk = cfg["office_walk_min"]
    am = journey_minutes(lat, lon, app_key, cfg["am_arrive_by"].replace(":",""), "Arriving", date)
    pm = journey_minutes(lat, lon, app_key, cfg["pm_depart_at"].replace(":",""), "Departing", date)
    return {"am": am + walk if am is not None else None,
            "pm": pm + walk if pm is not None else None}
