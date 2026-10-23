# london-scorer

Rank postcode districts **north of King's Cross** for people commuting to Meta King's Cross —
by real **AM/PM commute** to KX, **schools** (Ofsted), **housing stock**
(EPC: floor area / detached / rooms), **crime**, **demographics**, **GP coverage**
and **broadband (FTTP)**. The scorer itself uses open data and free APIs only.

> It answers **"which areas should we go look at?"** — not "which house should we rent?".

## How it works

1. **Discovery** — enumerates National Rail / TfL stations north of KX (no hardcoded
   whitelist), keeps those with a **nonstop** train and a door-to-door AM commute under
   `commute_threshold_min`, and maps them to postcode districts.
2. **Fetch** — for each district: TfL journeys (AM arrive-by and PM depart-at, the two
   timetables differ), schools, EPC housing stock, crime, Census demographics, GPs, FTTP.
3. **Score** — each dimension is normalised and combined with the weights in
   `config/zones.yaml`. Crime takes a steep exponential penalty; outliers are capped.

## Setup

```bash
python -m pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Keys (all free):
- `TFL_APP_KEY` — TfL Unified API, https://api-portal.tfl.gov.uk/ (journey planning).
- `EPC_BEARER_TOKEN` — EPC "Find Energy Certificate" API via a gov.uk account (housing stock).

Other sources need no key. `.env`, `cache/`, `data/` and `out/` are gitignored.

## Usage

```bash
python -m london_scorer            # discover districts + score -> out/
python -m pytest                   # tests
```

Outputs `out/zone-scorecard.md` (Markdown table) and `out/zone-scorecard.csv`.
Tune the commute window, threshold and weights in `config/zones.yaml`.

## Data sources

| Dimension | Source | Key | Mode |
|---|---|---|---|
| Commute AM/PM (door-to-door) | TfL Unified API | yes | live |
| Stations | National Rail station list + TfL | no | bulk |
| Schools (Ofsted, primary/secondary) | DfE GIAS + Ofsted | no | bulk |
| Housing stock (sqm, detached, rooms) | EPC (get-energy-performance-data) | yes | live |
| Crime | data.police.uk | no | live |
| Demographics | ONS Census 2021 (Nomis) | no | live |
| GP practices | NHS ODS + nhs.uk | no | live |
| Broadband FTTP/gigabit | Ofcom Connected Nations | no | bulk |
| Geo (centroid, LSOA, LA) | postcodes.io | no | live |

## Extras: `scripts/`

Outside the scorer, a few one-off helpers used during the recce. They drive a local
Chrome over CDP (`localhost:9222`) to read rental listings for the top-scoring zones,
and cross-reference a single listing against the scorecard (`evaluate_listing.py`).
They are personal tooling, not part of the package: mind the listing site's terms
before running them.

## Status

v1 done and used for a real recce (summer 2026). Not maintained as a product.

## License

MIT — see [LICENSE](LICENSE).
