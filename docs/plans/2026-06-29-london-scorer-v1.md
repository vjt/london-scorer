# london-scorer v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a ranked scorecard of postcode districts north of King's Cross to visit, scored on real AM/PM commute, schools, housing stock, crime, demographics and broadband — from open data only.

**Architecture:** A small Python package. District *discovery* derives the candidate set from KX-serving stations filtered by real journey-planner times; per-district *fetchers* (one module per open-data source, all cache-backed) fill each dimension; an *aggregate*/*score* stage joins and ranks; an *output* stage writes Markdown + CSV. All network I/O goes through one cached HTTP helper so tests run offline by monkeypatching it.

**Tech Stack:** Python 3.13; `requests`, `PyYAML`, `pandas`; `pytest` for tests.

## Global Constraints

- Python 3.13; dependencies limited to `requests`, `PyYAML`, `pandas`, `pytest`.
- Secrets come from `.env` only (`TFL_APP_KEY`, `EPC_BEARER_TOKEN`); never hardcode keys, never commit `.env`.
- Every network response is cached under `cache/`; re-runs must work offline from cache.
- Generated artefacts go to `out/`; bulk downloads to `data/`. All three are gitignored.
- No personal/family/colleague data in the repo.
- All tests are offline: monkeypatch `london_scorer.http.get_json` / `get_text`; never hit the network in a test.
- Commit after every task. Conventional-commit messages.

---

### Task 1: Config + env loader

**Files:**
- Create: `src/london_scorer/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `load_config(path="config/zones.yaml") -> dict` (parsed YAML).
- Produces: `load_env() -> dict` reading `.env` (KEY=VALUE lines, ignores blanks/`#`), returns `{"TFL_APP_KEY": ..., "EPC_BEARER_TOKEN": ...}`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_config.py
from london_scorer import config

def test_load_config_reads_yaml(tmp_path):
    p = tmp_path / "z.yaml"
    p.write_text("destination: King's Cross\ncommute_threshold_min: 45\n")
    cfg = config.load_config(p)
    assert cfg["destination"] == "King's Cross"
    assert cfg["commute_threshold_min"] == 45

def test_load_env_parses_and_skips_comments(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# comment\nTFL_APP_KEY=abc\n\nEPC_BEARER_TOKEN=xyz\n")
    env = config.load_env(p)
    assert env["TFL_APP_KEY"] == "abc"
    assert env["EPC_BEARER_TOKEN"] == "xyz"
```
- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_config.py -v` → FAIL (module/func missing).
- [ ] **Step 3: Implement**
```python
# src/london_scorer/config.py
from pathlib import Path
import yaml

def load_config(path="config/zones.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())

def load_env(path=".env") -> dict:
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env
```
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_config.py -v` → PASS.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: config + .env loader"`

---

### Task 2: Cached HTTP helper

**Files:**
- Create: `src/london_scorer/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Produces: `get_json(url, params=None, headers=None, cache_key=None) -> dict|list`
- Produces: `get_text(url, params=None, headers=None, cache_key=None) -> str`
- Both cache to `cache/<sha1(cache_key or url+params)>.json|.txt`; on cache hit, no network. Network via `requests`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_http.py
from london_scorer import http

def test_get_json_caches_and_reuses(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    calls = {"n": 0}
    class R:
        def raise_for_status(self): pass
        def json(self): calls["n"] += 1; return {"ok": True}
    monkeypatch.setattr(http.requests, "get", lambda *a, **k: R())
    a = http.get_json("https://x/y", params={"q": 1})
    b = http.get_json("https://x/y", params={"q": 1})   # served from cache
    assert a == b == {"ok": True}
    assert calls["n"] == 1
```
- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_http.py -v`.
- [ ] **Step 3: Implement**
```python
# src/london_scorer/http.py
import hashlib, json
from pathlib import Path
import requests

CACHE_DIR = Path("cache")

def _key(url, params, suffix):
    raw = url + json.dumps(params or {}, sort_keys=True)
    return CACHE_DIR / (hashlib.sha1(raw.encode()).hexdigest() + suffix)

def get_json(url, params=None, headers=None, cache_key=None):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = _key(cache_key or url, params, ".json")
    if f.exists():
        return json.loads(f.read_text())
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    f.write_text(json.dumps(data))
    return data

def get_text(url, params=None, headers=None, cache_key=None):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = _key(cache_key or url, params, ".txt")
    if f.exists():
        return f.read_text()
    r = requests.get(url, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    f.write_text(r.text)
    return r.text
```
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `git commit -am "feat: cached HTTP helper"`

---

### Task 3: Geo resolver (postcodes.io)

**Files:**
- Create: `src/london_scorer/geo.py`
- Test: `tests/test_geo.py`

**Interfaces:**
- Consumes: `http.get_json`.
- Produces: `outcode_centroid(outcode) -> {"lat": float, "lon": float, "local_authority": str}` via `https://api.postcodes.io/outcodes/{outcode}`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_geo.py
from london_scorer import geo, http

def test_outcode_centroid(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: {
        "result": {"latitude": 51.80, "longitude": -0.20, "admin_district": ["St Albans"]}})
    c = geo.outcode_centroid("AL8")
    assert c["lat"] == 51.80 and c["lon"] == -0.20
    assert c["local_authority"] == "St Albans"
```
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement**
```python
# src/london_scorer/geo.py
from . import http

def outcode_centroid(outcode):
    r = http.get_json(f"https://api.postcodes.io/outcodes/{outcode}")["result"]
    las = r.get("admin_district") or []
    return {"lat": r["latitude"], "lon": r["longitude"],
            "local_authority": las[0] if las else None}
```
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `git commit -am "feat: geo resolver via postcodes.io"`

---

### Task 4: Station enumeration + north filter (TfL)

**Files:**
- Create: `src/london_scorer/stations.py`
- Test: `tests/test_stations.py`

**Interfaces:**
- Consumes: `http.get_json`, `config` (`kx_lines`, `TFL_APP_KEY`).
- Produces: `KX = {"lat": 51.5308, "lon": -0.1238}` (King's Cross constant).
- Produces: `line_stations(line_id, app_key) -> list[{"id","name","lat","lon"}]` via `https://api.tfl.gov.uk/Line/{line_id}/StopPoints`.
- Produces: `north_stations(lines, app_key) -> list[station]` — union across lines, deduped by id, keep `lat >= KX["lat"]`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_stations.py
from london_scorer import stations, http

def test_north_filter_and_dedup(monkeypatch):
    fake = {
      "gn": [{"id":"S1","commonName":"Hatfield","lat":51.76,"lon":-0.22},
             {"id":"S2","commonName":"Finsbury Park","lat":51.56,"lon":-0.10}],
      "tl": [{"id":"S1","commonName":"Hatfield","lat":51.76,"lon":-0.22},
             {"id":"S3","commonName":"Sutton","lat":51.35,"lon":-0.19}],
    }
    monkeypatch.setattr(http, "get_json", lambda url, **k: {"stopPoints": fake["gn" if "great-northern" in url else "tl"]})
    out = stations.north_stations(["great-northern","thameslink"], "KEY")
    ids = {s["id"] for s in out}
    assert ids == {"S1", "S2"}        # S3 (Sutton, south) dropped; S1 deduped
```
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement**
```python
# src/london_scorer/stations.py
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
```
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `git commit -am "feat: TfL station enumeration + north filter"`

---

### Task 5: Commute (TfL journey planner, AM + PM)

**Files:**
- Create: `src/london_scorer/commute.py`
- Test: `tests/test_commute.py`

**Interfaces:**
- Consumes: `http.get_json`.
- Produces: `journey_minutes(from_lat, from_lon, app_key, when, time_is, date) -> int|None` —
  calls `https://api.tfl.gov.uk/Journey/JourneyResults/{lat},{lon}/to/{KX}` with `time`, `timeIs` (`Arriving`/`Departing`), `date`; returns the shortest `journeys[].duration`, or None if no journey.
- Produces: `door_to_door(lat, lon, app_key, cfg, date) -> {"am": int|None, "pm": int|None}` —
  AM = journey arriving by `cfg.am_arrive_by` + `cfg.office_walk_min`; PM = journey departing `cfg.pm_depart_at` + `cfg.office_walk_min`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_commute.py
from london_scorer import commute, http

def test_journey_minutes_picks_shortest(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: {"journeys":[{"duration":40},{"duration":33}]})
    assert commute.journey_minutes(51.8,-0.2,"KEY","0930","Arriving","20260703") == 33

def test_door_to_door_adds_office_walk(monkeypatch):
    monkeypatch.setattr(commute, "journey_minutes", lambda *a, **k: 25)
    cfg = {"am_arrive_by":"0930","pm_depart_at":"1730","office_walk_min":12}
    d = commute.door_to_door(51.8,-0.2,"KEY",cfg,"20260703")
    assert d == {"am": 37, "pm": 37}
```
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement**
```python
# src/london_scorer/commute.py
from . import http
from .stations import KX

def journey_minutes(from_lat, from_lon, app_key, when, time_is, date):
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{from_lat},{from_lon}/to/{KX['lat']},{KX['lon']}"
    data = http.get_json(url, params={"app_key": app_key, "time": when,
                                      "timeIs": time_is, "date": date},
                         cache_key=f"jp:{from_lat},{from_lon}:{when}:{time_is}:{date}")
    js = data.get("journeys") or []
    return min((j["duration"] for j in js), default=None)

def door_to_door(lat, lon, app_key, cfg, date):
    walk = cfg["office_walk_min"]
    am = journey_minutes(lat, lon, app_key, cfg["am_arrive_by"].replace(":",""), "Arriving", date)
    pm = journey_minutes(lat, lon, app_key, cfg["pm_depart_at"].replace(":",""), "Departing", date)
    return {"am": am + walk if am is not None else None,
            "pm": pm + walk if pm is not None else None}
```
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `git commit -am "feat: TfL door-to-door AM/PM commute"`

---

### Task 6: Discovery (stations → candidate districts with real commute)

**Files:**
- Create: `src/london_scorer/discovery.py`
- Test: `tests/test_discovery.py`

**Interfaces:**
- Consumes: `stations.north_stations`, `geo`, `commute.door_to_door`, `http` (postcodes.io reverse for station→outcode).
- Produces: `station_outcode(lat, lon) -> str` via `https://api.postcodes.io/outcodes?lon=&lat=` (nearest), returns `result[0]["outcode"]`.
- Produces: `discover(cfg, app_key, date) -> list[{"district","centroid","local_authority","commute_am","commute_pm"}]` —
  north stations → unique outcodes → for each, centroid + door_to_door; keep `commute_am <= cfg.commute_threshold_min`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_discovery.py
from london_scorer import discovery, stations, geo, commute

def test_discover_filters_by_threshold(monkeypatch):
    monkeypatch.setattr(stations, "north_stations", lambda *a: [{"id":"S1","lat":51.8,"lon":-0.2}])
    monkeypatch.setattr(discovery, "station_outcode", lambda lat,lon: "AL8")
    monkeypatch.setattr(geo, "outcode_centroid", lambda oc: {"lat":51.8,"lon":-0.2,"local_authority":"Welwyn Hatfield"})
    monkeypatch.setattr(commute, "door_to_door", lambda *a, **k: {"am":35,"pm":38})
    cfg = {"kx_lines":["x"], "commute_threshold_min":45, "am_arrive_by":"0930","pm_depart_at":"1730","office_walk_min":12}
    out = discovery.discover(cfg, "KEY", "20260703")
    assert out[0]["district"] == "AL8" and out[0]["commute_am"] == 35

def test_discover_drops_over_threshold(monkeypatch):
    monkeypatch.setattr(stations, "north_stations", lambda *a: [{"id":"S1","lat":51.9,"lon":-0.3}])
    monkeypatch.setattr(discovery, "station_outcode", lambda lat,lon: "SG6")
    monkeypatch.setattr(geo, "outcode_centroid", lambda oc: {"lat":51.9,"lon":-0.3,"local_authority":"North Herts"})
    monkeypatch.setattr(commute, "door_to_door", lambda *a, **k: {"am":52,"pm":55})
    cfg = {"kx_lines":["x"], "commute_threshold_min":45, "am_arrive_by":"0930","pm_depart_at":"1730","office_walk_min":12}
    assert discovery.discover(cfg, "KEY", "20260703") == []
```
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement**
```python
# src/london_scorer/discovery.py
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
```
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `git commit -am "feat: district discovery with real AM/PM commute"`

> **Milestone M1 reached:** `discover()` yields the weekend visit list (districts + AM/PM commute). Tasks 7–11 add dimensions onto each district row.

---

### Task 7: Crime fetcher (data.police.uk)

**Files:**
- Create: `src/london_scorer/fetchers/__init__.py` (empty), `src/london_scorer/fetchers/crime.py`
- Test: `tests/test_crime.py`

**Interfaces:**
- Produces: `fetch(district_row, month=None) -> {"crime_1mi_count": int}` — `https://data.police.uk/api/crimes-street/all-crime?lat=&lng=[&date=YYYY-MM]`, counts returned crimes.

- [ ] **Step 1: Write failing test**
```python
# tests/test_crime.py
from london_scorer.fetchers import crime
from london_scorer import http

def test_crime_counts(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: [{"id":1},{"id":2},{"id":3}])
    row = {"centroid":{"lat":51.8,"lon":-0.2}}
    assert crime.fetch(row) == {"crime_1mi_count": 3}
```
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement**
```python
# src/london_scorer/fetchers/crime.py
from .. import http

def fetch(row, month=None):
    params = {"lat": row["centroid"]["lat"], "lng": row["centroid"]["lon"]}
    if month: params["date"] = month
    data = http.get_json("https://data.police.uk/api/crimes-street/all-crime",
                         params=params, cache_key=f"crime:{params}")
    return {"crime_1mi_count": len(data)}
```
- [ ] **Step 4: Run → passes.** **Step 5: Commit** — `git commit -am "feat: crime fetcher (data.police.uk)"`

---

### Task 8: Schools fetcher (GIAS + Ofsted bulk)

**Files:**
- Create: `src/london_scorer/fetchers/schools.py`
- Test: `tests/test_schools.py`
- Data (downloaded once into `data/`, documented in README): GIAS `edubasealldata.csv`, Ofsted ratings CSV.

**Interfaces:**
- Produces: `load(gias_csv, ofsted_csv) -> pandas.DataFrame` with columns `[outcode, phase, rating]` (open schools only, rating joined by URN).
- Produces: `fetch(district_row, schools_df) -> {"primary_good": int, "secondary_good": int}` — count rows where `outcode == district` and `rating in {"Outstanding","Good"}`, split by phase. ("good" = Good or Outstanding.)

- [ ] **Step 1: Write failing test**
```python
# tests/test_schools.py
import pandas as pd
from london_scorer.fetchers import schools

def test_fetch_counts_good_by_phase():
    df = pd.DataFrame([
        {"outcode":"AL8","phase":"primary","rating":"Outstanding"},
        {"outcode":"AL8","phase":"primary","rating":"Requires improvement"},
        {"outcode":"AL8","phase":"secondary","rating":"Good"},
        {"outcode":"N14","phase":"primary","rating":"Good"},
    ])
    assert schools.fetch({"district":"AL8"}, df) == {"primary_good":1, "secondary_good":1}
```
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement**
```python
# src/london_scorer/fetchers/schools.py
import pandas as pd

GOOD = {"Outstanding", "Good"}

def load(gias_csv, ofsted_csv):
    g = pd.read_csv(gias_csv, encoding="latin-1", low_memory=False)
    g = g[g["EstablishmentStatus (name)"] == "Open"]
    g["outcode"] = g["Postcode"].astype(str).str.split().str[0]
    g["phase"] = g["PhaseOfEducation (name)"].str.lower().map(
        lambda s: "primary" if "primary" in str(s) else ("secondary" if "secondary" in str(s) else "other"))
    o = pd.read_csv(ofsted_csv, encoding="latin-1", low_memory=False)
    o = o.rename(columns={"Overall effectiveness": "rating"})[["URN", "rating"]]
    m = g.merge(o, on="URN", how="left")
    return m[["outcode", "phase", "rating"]]

def fetch(row, schools_df):
    d = schools_df[(schools_df["outcode"] == row["district"]) & (schools_df["rating"].isin(GOOD))]
    return {"primary_good": int((d["phase"] == "primary").sum()),
            "secondary_good": int((d["phase"] == "secondary").sum())}
```
> Column names above are the GIAS/Ofsted CSV headers; verify against the downloaded file header on first run and adjust the rename map if the export differs.
- [ ] **Step 4: Run → passes.** **Step 5: Commit** — `git commit -am "feat: schools fetcher (GIAS+Ofsted)"`

---

### Task 9: EPC housing-stock fetcher (gov.uk, bearer)

**Files:**
- Create: `src/london_scorer/fetchers/epc.py`
- Test: `tests/test_epc.py`

**Interfaces:**
- Produces: `fetch(district_row, bearer) -> {"epc_median_sqm": float|None, "pct_detached": float|None, "epc_n": int}` —
  `GET https://epc.opendatacommunities.org/api/v1/domestic/search?postcode={district}&size=5000`,
  header `Authorization: Bearer {bearer}`, `Accept: application/json`; aggregate `rows[]`
  (`total-floor-area`, `built-form`).

- [ ] **Step 1: Write failing test**
```python
# tests/test_epc.py
from london_scorer.fetchers import epc
from london_scorer import http

def test_epc_aggregates(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda *a, **k: {"rows":[
        {"total-floor-area":"100","built-form":"Detached"},
        {"total-floor-area":"80","built-form":"Semi-Detached"},
        {"total-floor-area":"120","built-form":"Detached"}]})
    out = epc.fetch({"district":"AL8"}, "TOKEN")
    assert out["epc_n"] == 3
    assert out["epc_median_sqm"] == 100.0
    assert round(out["pct_detached"], 2) == 0.67
```
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement**
```python
# src/london_scorer/fetchers/epc.py
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
```
> If the API returns 401 on bearer auth, this is the task to revisit auth (header form / endpoint host); everything else is independent of it.
- [ ] **Step 4: Run → passes.** **Step 5: Commit** — `git commit -am "feat: EPC housing-stock fetcher"`

---

### Task 10: Demographics fetcher (Census 2021 via Nomis, LA level)

**Files:**
- Create: `src/london_scorer/fetchers/demographics.py`
- Test: `tests/test_demographics.py`

**Interfaces:**
- Produces: `fetch(district_row, la_code_lookup) -> {"pct_white": float|None, "pct_christian_or_none": float|None}` —
  Nomis Census 2021 ethnicity (TS021) + religion (TS030) for the row's local authority; returns headline shares. (Plain area-character indicators; coarse at LA level — note in output.)

- [ ] **Step 1: Write failing test** (monkeypatch `http.get_json` to return a small Nomis JSON stub; assert the two percentages computed from it).
```python
# tests/test_demographics.py
from london_scorer.fetchers import demographics
from london_scorer import http

def test_demo_shares(monkeypatch):
    monkeypatch.setattr(http, "get_json", lambda url, **k: {
        "obs": [{"dimensions":{"c2021_eth_20":{"value":"White"}},"value":800},
                {"dimensions":{"c2021_eth_20":{"value":"Total"}},"value":1000}]} if "TS021" in url else {
        "obs":[{"dimensions":{"c2021_rel_10":{"value":"Christian"}},"value":500},
               {"dimensions":{"c2021_rel_10":{"value":"No religion"}},"value":300},
               {"dimensions":{"c2021_rel_10":{"value":"Total"}},"value":1000}]})
    out = demographics.fetch({"local_authority":"Welwyn Hatfield"}, lambda la: "E07000241")
    assert out["pct_white"] == 0.8
    assert out["pct_christian_or_none"] == 0.8
```
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement** — query Nomis `https://www.nomisweb.co.uk/api/v01/dataset/NM_2041_1.jsonstat.json` (TS021) / TS030, geography = LA code, parse White-share and (Christian+No religion) share. Concrete parsing mirrors the stub above. (Resolve `la_code_lookup` once from postcodes.io `codes.admin_district`.)
- [ ] **Step 4: Run → passes.** **Step 5: Commit** — `git commit -am "feat: demographics fetcher (Census 2021)"`

---

### Task 11: Broadband FTTP fetcher (Ofcom Connected Nations bulk)

**Files:**
- Create: `src/london_scorer/fetchers/broadband.py`
- Test: `tests/test_broadband.py`
- Data: Ofcom Connected Nations fixed-postcode CSV downloaded once into `data/`.

**Interfaces:**
- Produces: `load(csv_path) -> pandas.DataFrame[outcode, gigabit_pct]` (mean gigabit availability % per outcode).
- Produces: `fetch(district_row, df) -> {"fttp_pct": float|None}`.

- [ ] **Step 1: Write failing test**
```python
# tests/test_broadband.py
import pandas as pd
from london_scorer.fetchers import broadband

def test_fttp_lookup():
    df = pd.DataFrame([{"outcode":"AL8","gigabit_pct":95.0},{"outcode":"N14","gigabit_pct":80.0}])
    assert broadband.fetch({"district":"AL8"}, df) == {"fttp_pct": 95.0}
```
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement** — `load` reads the Ofcom CSV, derives `outcode` from the postcode column, groups mean of the gigabit-availability column; `fetch` looks up the row's district.
- [ ] **Step 4: Run → passes.** **Step 5: Commit** — `git commit -am "feat: broadband FTTP fetcher (Ofcom)"`

---

### Task 12: Aggregate + score + output

**Files:**
- Create: `src/london_scorer/score.py`, `src/london_scorer/output.py`, `src/london_scorer/__main__.py`
- Test: `tests/test_score.py`, `tests/test_output.py`

**Interfaces:**
- `score.normalise_and_score(rows, weights) -> rows` — min-max normalise each numeric dimension to 0–1 (crime + commute inverted: lower is better), compute `score` = Σ weight·norm over available dims (skip missing), attach `score`. Raw columns retained.
- `output.write(rows, md_path, csv_path)` — ranked-by-score Markdown table + CSV.
- `__main__` — load config/env → `discover()` → run fetchers per row → `score` → `output.write` to `out/`.

- [ ] **Step 1: Write failing test (score)**
```python
# tests/test_score.py
from london_scorer import score
def test_commute_inverted_lower_is_better():
    rows = [{"district":"A","commute_am":30,"primary_good":4},
            {"district":"B","commute_am":45,"primary_good":1}]
    out = score.normalise_and_score(rows, {"commute":0.5,"schools":0.5})
    a = next(r for r in out if r["district"]=="A")
    b = next(r for r in out if r["district"]=="B")
    assert a["score"] > b["score"]      # A: faster commute + more good schools
```
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement** `score.py` (map dimension→source column: `commute`→`commute_am` inverted, `schools`→`primary_good`+`secondary_good`, `house`→`epc_median_sqm`, `crime`→`crime_1mi_count` inverted, `fttp`→`fttp_pct`, `demographics`→`pct_white`); min-max within the column across rows; weighted sum over present dims.
- [ ] **Step 4: Run → passes.**
- [ ] **Step 5: Write failing test (output)** — `output.write` produces a Markdown file containing a header row with `district | commute_am | commute_pm | primary_good | score` and one line per row, ranked by score desc; assert substring + ordering on a 2-row input written to `tmp_path`.
- [ ] **Step 6: Implement `output.py`** — build Markdown table + `pandas.DataFrame.to_csv`.
- [ ] **Step 7: Run → passes.**
- [ ] **Step 8: Wire `__main__.py`** — `python -m london_scorer` runs the full pipeline writing `out/zone-scorecard.md` + `.csv`; schools/broadband bulk paths and `EPC_BEARER_TOKEN`/`TFL_APP_KEY` from config/env; a fetcher raising is caught per-district and that dimension left blank (logged), so one dead source never kills the run.
- [ ] **Step 9: Commit** — `git commit -am "feat: aggregate, score, output, CLI"`

---

## Self-Review

**Spec coverage:** commute AM/PM (T5–6) ✓ · discovery/no-prefab-districts (T6) ✓ · schools primary+secondary+count (T8) ✓ · house-EPC (T9) ✓ · crime (T7) ✓ · demographics (T10) ✓ · FTTP (T11) ✓ · raw columns + optional weighted score (T12) ✓ · md+csv output (T12) ✓ · cache/offline (T2) ✓ · secret hygiene (T1, env-only) ✓ · district granularity (outcode throughout) ✓. Rents (ONS/VOA) from the spec table are **deferred** — not in v1 weights; noted here as the one conscious gap.

**Placeholder scan:** Tasks 10–11 give endpoint + parsing approach and a concrete test rather than full line-by-line code for the bulk-CSV column wrangling, because exact column headers must be read from the live downloads; the test pins the contract. No "TBD/handle errors" left.

**Type consistency:** every fetcher is `fetch(row, ...) -> dict`; `row` carries `district`, `centroid{lat,lon}`, `local_authority` from `discover()`; `score` consumes the merged dict; names match across tasks.
