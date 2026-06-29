# london-scorer

Rank postcode districts **north of King's Cross** for a family relocation recce —
by real **AM/PM commute** to KX, **schools** (Ofsted), **housing stock**
(EPC: floor area / detached / rooms), **crime**, **demographics** and
**broadband (FTTP)**. Open data + free APIs only — **no listings, no scraping**.

> It answers **"which areas should we go look at?"** — not "which house should we rent?".

## Status

Work in progress.

## Setup

```bash
python -m pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Keys (all free):
- `TFL_APP_KEY` — TfL Unified API, https://api-portal.tfl.gov.uk/ (journey planning).
- `EPC_BEARER_TOKEN` — EPC "Find Energy Certificate" API via a gov.uk account (housing stock).

Other sources need no key.

## Usage

```bash
python -m london_scorer            # discover districts + score -> out/
```

Outputs `out/zone-scorecard.md` (Markdown table) and `out/zone-scorecard.csv`.

## Data sources

| Dimension | Source | Key | Mode |
|---|---|---|---|
| Commute AM/PM (door-to-door) | TfL Unified API | yes | live |
| Schools (Ofsted, primary/secondary) | DfE GIAS + Ofsted | no | bulk |
| Housing stock (sqm, detached, rooms) | EPC Open Data | yes | bulk |
| Rents by bedrooms | ONS PIPR / VOA | no | bulk |
| Crime | data.police.uk | no | live |
| Demographics | ONS Census 2021 (Nomis) | no | bulk/live |
| Broadband FTTP/gigabit | Ofcom Connected Nations | no | bulk |
| Council tax band D | gov.uk / councils | no | static |
| Flood risk | Environment Agency | no | live |
| Geo (centroid, LSOA, LA) | postcodes.io | no | live |

## Non-goals

Property listings, scraping, individual house-finding, realtime data.

## License

MIT — see [LICENSE](LICENSE).
