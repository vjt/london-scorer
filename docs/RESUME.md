# Resuming london-scorer

This repository is **self-contained** and **implemented** (v1 complete + extended).

> Earlier versions of this file said "no implementation yet" — that is obsolete.
> The tool works end-to-end and has been run many times. See the root `../CLAUDE.md`
> for the full project picture; this file is the repo-local quickstart.

## What it does

Autonomously **discovers** UK postcode districts north of King's Cross (no hardcoded
whitelist) and scores them for a family relocation to a Meta Kings Cross commute.

## Run it

```bash
python -m pip install -r requirements.txt   # into a venv (.venv/)
cp .env.example .env                          # fill in TFL_APP_KEY + EPC_BEARER_TOKEN
# put bulk CSVs in data/ (see below), then:
python -m london_scorer                       # -> out/zone-scorecard.csv + .md
```

## Architecture (all under `src/london_scorer/`)

- `discovery.py` — station enumeration (85km north of KX) → nearby-outcode expansion
  (>30km stations, 5km radius) → **nonstop-commute filter** → candidate districts.
- `commute.py` — TfL journey planner, door-to-door to KX; `_is_nonstop()` keeps only
  journeys with a single rail/tube leg (bus-to-station allowed).
- `stations.py` — national-rail CSV loader (`data/uk-stations.csv`) + TfL StopPoints,
  north filter, dedup.
- `fetchers/` — `crime.py` (police.uk), `schools.py` (GIAS+Ofsted; quality + raw density),
  `epc.py` (gov.uk EPC, council-bulk + houses-only trimmed median), `demographics.py`
  (Nomis TS021/TS030), `broadband.py` (Ofcom LA-level fallback), `gp.py` (NHS ODS + NHS.UK,
  coverage capped at 5).
- `score.py` — 8-dim weighted score; crime is a steep `exp(-c/150)` penalty. `_DIM_MAP`
  ties each weight to a column.
- `output.py` — Markdown + CSV. `__main__.py` — pipeline: discover → fetch → LA-median
  gap-fill → score → write.
- `config/zones.yaml` — weights + commute window/threshold. **Tune weights here.**

## Secrets & data (both gitignored)

- `.env`: `TFL_APP_KEY` (+ `_FALLBACK`), `EPC_BEARER_TOKEN`. Never commit.
- `data/`: `uk-stations.csv` (doogal.co.uk), `edubasealldata.csv` (DfE GIAS), `ofsted.csv`.
- `cache/`, `out/`: generated; safe to delete to force a fresh run.

## Gotchas

- Caches make resume instant but go **stale** — delete `cache/` for fresh crime/schools/EPC.
- EPC bearer can 401 → re-check header/endpoint in `fetchers/epc.py`.
- GIAS/Ofsted CSV headers vary between exports → `schools.py` has a rename-map fallback.
- postcodes.io outcode centroids are sometimes off (e.g. AL3/AL4, MK) → `discovery.py`
  has `_SEED_STATION_COORDS` overrides for commute accuracy.

## Extensions beyond the original v1 plan

- **GP** dimension (NHS data) and **school_density** (catchment probability) added.
- **Listing scrapers** (`scripts/search_*.py`, `evaluate_listing.py`) via Chrome CDP on
  localhost:9222 — these DO scrape Rightmove. The original "no scraping" rule was relaxed
  for listings only; the scorecard itself stays open-data-only.

## Future improvement (not built)

With per-premises **FTTB availability data** → could replace LA-level Ofcom fttp with real per-outcode
fibre availability. Not built yet.
