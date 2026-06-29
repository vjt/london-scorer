"""Entry point: python -m london_scorer

Runs the full pipeline:
  discover candidate districts → fetch all data dimensions per district →
  normalise + score → write ranked Markdown + CSV to out/.
"""

import sys
from pathlib import Path
from . import config, discovery, score, output
from .fetchers import crime, schools, epc, demographics, broadband


_OUT_DIR = Path("out")
_MD_PATH = str(_OUT_DIR / "zone-scorecard.md")
_CSV_PATH = str(_OUT_DIR / "zone-scorecard.csv")

# Next Thursday (adjust as needed; will be made configurable later)
_DATE = "20260703"


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    cfg = config.load_config()
    try:
        env = config.load_env()
    except FileNotFoundError:
        print("⚠ .env file not found — continuing with empty env")
        env = {}

    app_key = env.get("TFL_APP_KEY", "")
    if not app_key:
        print("⚠ TFL_APP_KEY not set in .env — TfL API calls may fail")

    print("Discovering candidate districts …")
    rows = discovery.discover(cfg, app_key, _DATE)
    print(f"Found {len(rows)} candidate districts")

    if not rows:
        print("No districts found — check commute_threshold_min and kx_lines in config.")
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # Load bulk datasets once (failures are non-fatal)                    #
    # ------------------------------------------------------------------ #
    schools_df = None
    broadband_df = None

    try:
        schools_df = schools.load("data/edubasealldata.csv", "data/ofsted.csv")
        print(f"Schools data loaded ({len(schools_df)} rows)")
    except Exception as exc:
        print(f"⚠ Schools data not available: {exc}")

    try:
        broadband_df = broadband.load("data/ofcom.csv")
        print(f"Broadband data loaded ({len(broadband_df)} rows)")
    except Exception as exc:
        print(f"⚠ Broadband data not available: {exc}")

    epc_token = env.get("EPC_BEARER_TOKEN", "")

    # ------------------------------------------------------------------ #
    # Fetch per-district dimensions; a failing fetcher never kills the run #
    # ------------------------------------------------------------------ #
    fetchers = [
        ("crime",        lambda r: crime.fetch(r)),
        ("schools",      lambda r: schools.fetch(r, schools_df) if schools_df is not None else {}),
        ("epc",          lambda r: epc.fetch(r, epc_token)),
        ("demographics", lambda r: demographics.fetch(r, lambda la: la)),  # LA code lookup TBD
        ("broadband",    lambda r: broadband.fetch(r, broadband_df) if broadband_df is not None else {}),
    ]

    for row in rows:
        for name, fn in fetchers:
            try:
                row.update(fn(row))
            except Exception as exc:
                print(f"⚠ {name} failed for {row['district']}: {exc}")

    # ------------------------------------------------------------------ #
    # Score and write output                                              #
    # ------------------------------------------------------------------ #
    weights = cfg.get("weights", {})
    rows = score.normalise_and_score(rows, weights)
    output.write(rows, _MD_PATH, _CSV_PATH)
    print(f"Wrote {_MD_PATH} + {_CSV_PATH} ({len(rows)} districts)")


if __name__ == "__main__":
    main()
