# london-scorer — design

## Purpose

Rank **postcode districts north of King's Cross (KX)** by how worth-visiting they are
for a house hunt. Primary dimensions: **real AM/PM commute** to KX and
**schools**; plus **housing stock**, **crime**, **demographics** and **broadband (FTTP)**.

**It answers "which areas should we go look at?" — NOT "which house should we rent?".**
No property listings, no scraping.

## Scope / non-goals

- Open data + free APIs only. No Rightmove/Zoopla scraping.
- Granularity = **postcode district / outcode** (e.g. `AL8`, `N14`, `NW7`), not address.
- Not a real-time house finder. Picking actual houses stays manual / via Aires.

## Inputs (`config/zones.yaml`)

- `destination` (KX), `am_arrive_by` (09:30), `pm_depart_at` (17:30), `office_walk_min` (~12).
- `commute_threshold_min` (e.g. 45 door-to-door, AM), `north_only` (true).
- `kx_lines` — seed of lines serving KX/St Pancras/Moorgate, for station discovery.
- `school_radius_km`, `school_phases`.
- `weights` — per-dimension weights for the optional composite score.

## District discovery (no hand-listed config)

Districts are **derived from the commute constraint**, not pre-listed:

1. Enumerate stations on `kx_lines` from open station data (TfL StopPoint / NaPTAN).
2. Keep stations **north of KX** (`north_only`).
3. Journey-plan each station → KX via TfL Unified API, **twice**:
   - **AM**: arrive-by `am_arrive_by` (home→station→train→office walk).
   - **PM**: depart-at `pm_depart_at` (return leg; AM and PM timetables differ).
4. Keep stations with door-to-door ≤ `commute_threshold_min`.
5. Map each kept station → its postcode **outcode** → the candidate district set.

## Dimensions & sources

| Dimension | Source | Key | Mode |
|---|---|---|---|
| Commute AM **and** PM (door-to-door) | TfL Unified API | yes (`.env`) | live |
| Schools — Ofsted Good/Outstanding, split **primary/secondary**, **count of options** (catchment flexibility) | DfE GIAS + Ofsted ratings | no | bulk |
| Housing stock — median floor area (m²), % detached, habitable rooms | EPC Open Data | yes (`.env`) | bulk |
| Rents by bedroom count | ONS PIPR / VOA | no | bulk |
| Crime — counts by category, normalised | data.police.uk | no | live (point) |
| Demographics — ethnicity / religion | ONS Census 2021 (Nomis) | no | bulk/live |
| Broadband — % premises FTTP / gigabit | Ofcom Connected Nations | no | bulk |
| Council tax — band D charge | gov.uk / councils | no | static |
| Flood risk | Environment Agency | no | live (point) |
| Geo — centroid, LSOA, local authority | postcodes.io | no | live |

## Architecture

- `config` — load + validate `zones.yaml` and `.env`.
- `geo` — postcodes.io: outcode/postcode → centroid, LSOA, local authority.
- `discovery` — stations → AM/PM journey-plan → qualifying districts.
- `fetchers/` — one module per source, common interface `fetch(district) -> dict`,
  each cache-backed. Bulk sources load once into a local store, then query per district.
- `aggregate` — join all dimensions into one row per district.
- `score` — normalise each metric 0–1; **raw columns always emitted**; optional
  weighted composite (`weights`). House dimension comes from EPC (+ ONS rents).
- `output` — `out/zone-scorecard.md` (ranked Markdown table) + `out/zone-scorecard.csv`.
- `cache/` — every fetch cached locally → fast, offline-capable re-runs.

Each unit is independently testable: a fetcher takes a district and returns a dict;
the scorer takes rows and returns ranked rows; output takes rows and writes files.

## Secret & privacy hygiene (repo is public)

- `TFL_APP_KEY`, `EPC_API_KEY` live in `.env` (**gitignored**); `.env.example` committed.
- **No personal/family/colleague data in the repo.** The recce notes
  (`../london-move-context.md`, `../zone-shortlist.md`) stay OUT of this repo.
- `.gitignore`: `.env`, `cache/`, `data/`, `out/`, `__pycache__/`.

## Build order

**v1 = all dimensions** (commute + schools + house-EPC + crime + demographics + FTTP),
output as a ranked scorecard. The district-discovery (commute) runs first because it
defines the set; the per-district fetchers then fill every dimension.

- Blocked on user action: **EPC account/key** (free registration) for the housing dimension.
- Everything else is fetchable without user action.
- Publish polish (tests, CI, docs) follows once v1 produces a trusted table.

## Stack

Python 3.13, `requests`, `PyYAML`, `pandas`. Local CLI: `python -m london_scorer`.
