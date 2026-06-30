"""Write scored district rows as a ranked Markdown table and CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


# Columns shown in the Markdown table (in order); extra columns go to CSV only.
_MD_COLUMNS = [
    "district",
    "local_authority",
    "score",
    "commute_am",
    "commute_pm",
    "epc_median_sqm",
    "pct_detached",
    "median_rooms",
    "epc_n",
    "school_quality",
    "has_outstanding",
    "primary_good",
    "secondary_good",
    "crime_1mi_count",
    "fttp_pct",
    "pct_white",
]

# Columns to exclude from output entirely (nested dicts, internal state)
_EXCLUDE = {"centroid"}


def write(rows: list[dict], md_path: str, csv_path: str) -> None:
    """Write *rows* (already scored) to a Markdown table and a CSV file.

    Args:
        rows:     List of district dicts each containing at least a ``score`` key.
                  The list is sorted by ``score`` descending before writing.
        md_path:  Destination path for the Markdown file.
        csv_path: Destination path for the CSV file.

    Both parent directories are created automatically if they do not exist.
    """
    # Sort descending by score (defensive — should already be sorted by score.py)
    sorted_rows = sorted(rows, key=lambda r: r.get("score", 0.0), reverse=True)

    df = pd.DataFrame(sorted_rows)

    # Drop internal columns (nested dicts etc.)
    for col in _EXCLUDE:
        if col in df.columns:
            df = df.drop(columns=[col])

    # ---- CSV: all columns ----
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)

    # ---- Markdown: selected columns only ----
    Path(md_path).parent.mkdir(parents=True, exist_ok=True)

    # Keep only columns that actually exist in the data, in our preferred order
    md_cols = [c for c in _MD_COLUMNS if c in df.columns]
    # Append any extra columns not in our list (so nothing is lost from the table)
    extra = [c for c in df.columns if c not in md_cols]
    md_cols = md_cols + extra

    md_df = df[md_cols]

    lines: list[str] = []
    # Header
    lines.append("| " + " | ".join(str(c) for c in md_df.columns) + " |")
    # Separator
    lines.append("| " + " | ".join("---" for _ in md_df.columns) + " |")
    # Data rows
    for _, row in md_df.iterrows():
        lines.append("| " + " | ".join(str(v) if v is not None else "" for v in row) + " |")

    Path(md_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
