"""Min-max normalise numeric dimensions and compute a weighted score per district.

Crime uses a steep non-linear penalty so high-crime zones are strongly penalised.
"""

from __future__ import annotations

import math
from typing import Any


# Dimension → (column, inverted, steep)
# steep=True uses exponential penalty instead of linear min-max
_DIM_MAP: dict[str, tuple[Any, bool, bool]] = {
    "commute":      ("commute_am",        True,  False),
    "schools":      ("school_quality",     False, False),
    "house":        ("epc_median_sqm",     False, False),
    "crime":        ("crime_1mi_count",    True,  True),   # STEEP penalty
    "fttp":         ("fttp_pct",           False, False),
    "demographics": ("pct_white",          False, False),
}


def _raw_value(row: dict, col: Any) -> float | None:
    if isinstance(col, tuple):
        values = [row.get(c) for c in col]
        non_none = [v for v in values if v is not None]
        if not non_none:
            return None
        return sum(non_none)
    val = row.get(col)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _steep_crime_norm(crime_count: float) -> float:
    """Steep normalisation: low crime (~0-200) scores near 1.0,
    high crime (~600+) scores near 0.

    Uses exponential decay: score = exp(-crime / 200).
    At 58→0.75, 118→0.55, 200→0.37, 332→0.19, 600→0.05, 1000→0.007, 1500→0.0006.
    """
    return math.exp(-crime_count / 200.0)


def normalise_and_score(rows: list[dict], weights: dict[str, float]) -> list[dict]:
    if not rows:
        return rows

    active_dims = [d for d in weights if d in _DIM_MAP and weights[d] > 0]

    dim_raw: dict[str, list[float | None]] = {}
    for dim in active_dims:
        col, _, _ = _DIM_MAP[dim]
        dim_raw[dim] = [_raw_value(row, col) for row in rows]

    # min/max for linear dimensions
    dim_stats: dict[str, tuple[float, float]] = {}
    for dim in active_dims:
        vals = [v for v in dim_raw[dim] if v is not None]
        if not vals:
            dim_stats[dim] = (0.0, 0.0)
        else:
            dim_stats[dim] = (min(vals), max(vals))

    for i, row in enumerate(rows):
        total_weight = 0.0
        weighted_sum = 0.0

        for dim in active_dims:
            raw = dim_raw[dim][i]
            if raw is None:
                continue

            col, inverted, steep = _DIM_MAP[dim]
            w = weights[dim]

            if steep:
                # Exponential decay — already 0-1 (high crime → near 0)
                norm = _steep_crime_norm(raw)
            else:
                lo, hi = dim_stats[dim]
                if hi == lo:
                    norm = 0.5
                else:
                    norm = (raw - lo) / (hi - lo)
                if inverted:
                    norm = 1.0 - norm

            weighted_sum += w * norm
            total_weight += w

        if total_weight == 0.0:
            row["score"] = 0.0
        else:
            row["score"] = round(weighted_sum / total_weight, 6)

    rows.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    return rows
