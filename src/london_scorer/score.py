"""Min-max normalise numeric dimensions and compute a weighted score per district."""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Dimension → raw column(s) mapping
# ---------------------------------------------------------------------------
# Each entry: (column_or_columns, inverted)
#   column_or_columns: str (single) or tuple[str, str] (summed pair)
#   inverted: True means lower raw value → higher score
# ---------------------------------------------------------------------------
_DIM_MAP: dict[str, tuple[Any, bool]] = {
    "commute":      ("commute_am",                        True),
    "schools":      (("primary_good", "secondary_good"),  False),
    "house":        ("epc_band_score",                    False),
    "crime":        ("crime_1mi_count",                   True),
    "fttp":         ("fttp_pct",                          False),
    "demographics": ("pct_white",                         False),
}


def _raw_value(row: dict, col: Any) -> float | None:
    """Extract the raw numeric value for a dimension from a row.

    For tuple columns the values are summed; any None component is treated as 0
    only when at least one component is present and non-None.
    """
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


def normalise_and_score(rows: list[dict], weights: dict[str, float]) -> list[dict]:
    """Min-max normalise each weighted dimension, compute a composite score.

    Args:
        rows:    List of district row dicts (mutated in-place with a ``score`` key).
        weights: Mapping of dimension name → weight (e.g. ``{"commute": 0.25}``).
                 Only dimensions present in both *weights* and *_DIM_MAP* are used.

    Returns:
        The same rows list, sorted by ``score`` descending.
    """
    if not rows:
        return rows

    # Determine which dimensions are active (in both weights map and our dim map)
    active_dims = [d for d in weights if d in _DIM_MAP and weights[d] > 0]

    # For each active dimension, gather the raw values per row
    dim_raw: dict[str, list[float | None]] = {}
    for dim in active_dims:
        col, _ = _DIM_MAP[dim]
        dim_raw[dim] = [_raw_value(row, col) for row in rows]

    # Compute min/max per dimension (ignoring None)
    dim_stats: dict[str, tuple[float, float]] = {}
    for dim in active_dims:
        vals = [v for v in dim_raw[dim] if v is not None]
        if not vals:
            dim_stats[dim] = (0.0, 0.0)
        else:
            dim_stats[dim] = (min(vals), max(vals))

    # Normalise and score each row
    for i, row in enumerate(rows):
        total_weight = 0.0
        weighted_sum = 0.0

        for dim in active_dims:
            raw = dim_raw[dim][i]
            if raw is None:
                continue   # skip this dimension for this row

            col, inverted = _DIM_MAP[dim]
            lo, hi = dim_stats[dim]
            w = weights[dim]

            if hi == lo:
                # All values equal — assign neutral 0.5 to avoid division by zero
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
