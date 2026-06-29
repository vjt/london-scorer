import pandas as pd

GOOD = {"Outstanding", "Good"}

def load(gias_csv, ofsted_csv):
    g = pd.read_csv(gias_csv, encoding="latin-1", low_memory=False)
    g = g[g["EstablishmentStatus (name)"] == "Open"]
    g["outcode"] = g["Postcode"].astype(str).str.split().str[0]
    g["phase"] = g["PhaseOfEducation (name)"].str.lower().map(
        lambda s: "primary" if "primary" in str(s) else ("secondary" if "secondary" in str(s) else "other"))
    o = pd.read_csv(ofsted_csv, encoding="latin-1", low_memory=False)
    o = o.rename(columns={"Overall effectiveness": "rating"})[["URN", "rating"]]
    m = g.merge(o, on="URN", how="left")
    return m[["outcode", "phase", "rating"]]

def fetch(row, schools_df):
    d = schools_df[(schools_df["outcode"] == row["district"]) & (schools_df["rating"].isin(GOOD))]
    return {"primary_good": int((d["phase"] == "primary").sum()),
            "secondary_good": int((d["phase"] == "secondary").sum())}
