import pandas as pd

def load(csv_path):
    """Load Ofcom CSV and derive gigabit availability % per outcode."""
    df = pd.read_csv(csv_path, low_memory=False)
    # Derive outcode from postcode column (first part before space)
    df["outcode"] = df["postcode"].astype(str).str.split().str[0]
    # Group by outcode, take mean of gigabit availability
    return df.groupby("outcode")["gigabit_pct"].mean().reset_index()

def fetch(row, df):
    """Look up FTTP availability % for a district."""
    match = df[df["outcode"] == row["district"]]
    if match.empty:
        return {"fttp_pct": None}
    return {"fttp_pct": float(match.iloc[0]["gigabit_pct"])}
