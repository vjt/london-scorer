"""Entry point: python -m london_scorer

Runs the full pipeline:
  discover candidate districts → fetch all data dimensions per district →
  normalise + score → write ranked Markdown + CSV to out/.
"""

import sys
from pathlib import Path
from . import config, discovery, geo, score, output
from .fetchers import crime, schools, epc, demographics, broadband, gp


_OUT_DIR = Path("out")
_MD_PATH = str(_OUT_DIR / "zone-scorecard.md")
_CSV_PATH = str(_OUT_DIR / "zone-scorecard.csv")

_DATE = "20260702"


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
        print(f"⚠ Broadband bulk CSV not available, using LA-level estimates")

    epc_token = env.get("EPC_BEARER_TOKEN", "")
    if not epc_token:
        print("⚠ EPC_BEARER_TOKEN not set — house size data will be missing")

    # Build a GSS code lookup cache for demographics
    _gss_cache = {}

    def _la_code_lookup(la_name, district=None):
        if la_name in _gss_cache:
            return _gss_cache[la_name]
        code = geo.la_gss_code(district) if district else None
        if code:
            _gss_cache[la_name] = code
        return code

    # ------------------------------------------------------------------ #
    # Fetch per-district dimensions                                       #
    # ------------------------------------------------------------------ #
    fetchers = [
        ("crime",        lambda r: crime.fetch(r)),
        ("schools",      lambda r: schools.fetch(r, schools_df) if schools_df is not None else {}),
        ("epc",          lambda r: epc.fetch(r, epc_token)),
        ("demographics", lambda r: demographics.fetch(r, lambda la: _la_code_lookup(la, r.get("district")))),
        ("broadband",    lambda r: broadband.fetch(r, broadband_df)),
        ("gp",           lambda r: gp.fetch(r)),
    ]

    for i, row in enumerate(rows):
        print(f"\r  Fetching dimensions: {i+1}/{len(rows)} ({row['district']}) …", end="", flush=True)
        for name, fn in fetchers:
            try:
                row.update(fn(row))
            except Exception as exc:
                print(f"\n⚠ {name} failed for {row['district']}: {exc}")
    print()

    # ------------------------------------------------------------------ #
    # Fill gaps with LA-level medians (honest: for demographics + FTTP)   #
    # ------------------------------------------------------------------ #
    _fill_cols = ["fttp_pct", "pct_white", "pct_christian_or_none",
                  "epc_median_sqm", "pct_detached", "median_rooms", "school_quality",
                  "school_density", "gp_accepting_pct", "gp_coverage"]
    for col in _fill_cols:
        la_vals = {}
        for row in rows:
            la = row.get("local_authority", "")
            v = row.get(col)
            if v is not None:
                la_vals.setdefault(la, []).append(v)
        la_medians = {la: sorted(vs)[len(vs) // 2] for la, vs in la_vals.items() if vs}
        all_vals = [v for vs in la_vals.values() for v in vs]
        global_median = sorted(all_vals)[len(all_vals) // 2] if all_vals else 0

        filled = 0
        for row in rows:
            if row.get(col) is None:
                la = row.get("local_authority", "")
                row[col] = la_medians.get(la, global_median)
                filled += 1
        if filled:
            print(f"  Filled {filled} {col} gaps with LA/global median")

    # ------------------------------------------------------------------ #
    # Mark low-confidence EPC (n < 10)                                    #
    # ------------------------------------------------------------------ #
    low_conf = sum(1 for r in rows if r.get("epc_n", 0) < 10)
    if low_conf:
        print(f"  ⚠ {low_conf} districts have epc_n < 10 (low confidence house data)")

    # ------------------------------------------------------------------ #
    # Score and write output                                              #
    # ------------------------------------------------------------------ #
    weights = cfg.get("weights", {})
    rows = score.normalise_and_score(rows, weights)
    output.write(rows, _MD_PATH, _CSV_PATH)
    print(f"Wrote {_MD_PATH} + {_CSV_PATH} ({len(rows)} districts)")


if __name__ == "__main__":
    main()
