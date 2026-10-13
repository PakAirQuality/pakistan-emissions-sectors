"""Ingest the HIES 2024-25 household waste-management module into a committed CSV.

WHAT THIS PRODUCES. Design-weighted household disposal-route shares from HIES 2024-25
Section 5 Module 3 (s5m3q01, "How your household waste been collected or disposed of?"),
by urban/rural stratum nationally and by province. This is the first Pakistani survey
evidence in the repository bearing on the waste sector's load-bearing partition
parameters - the 0.30 urban / 0.70 rural uncollected fractions from the World Bank
What a Waste Pakistan row - and it disagrees with them materially: design-weighted
uncollected shares are 0.42 urban and 0.93 rural. The sector does NOT adopt these as
central values; they are published as a validation comparison and priced as a named
structural scenario (hies_route_shares in pkinv.sectors.waste.uncertainty).

TWO DECLARED CAVEATS, both directions stated.
  * Household route shares are not waste-MASS shares: generation per household varies
    with household size and income, and the survey weights households, not tonnes.
    Converting route shares to mass shares needs stratum generation rates it does not
    carry.
  * "Public Bin/Collection point" (route 3) is counted as COLLECTED even though q03
    shows some bins are cleared less than daily; "Other Specify" (route 7) is counted
    as UNCOLLECTED because its free-text answers cannot be classified. The first choice
    overstates collection, the second understates it; both are small against the
    urban 0.30-vs-0.42 gap.

WEIGHTS. The household weight on the person roster (plist_roster.sav), joined on
hhcode exactly as scripts/ingest_hies.py does; weighted households land near 40
million, the round's sanity anchor. pandas/pyreadstat are quarantined to this script;
the committed CSV is what the package reads.

Usage:  python3 scripts/ingest_hies_waste.py
Writes: data/activity/waste/hies_disposal_routes.csv
"""

from pkinv.assets import asset_path
import os

import pandas as pd
import pyreadstat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = asset_path(ROOT, "sources", "HIES", "HIES_2024-25", "SPSS data")
OUT = asset_path(ROOT, "data", "activity", "waste")

PROVINCE = {1: "Khyber Pakhtunkhwa", 2: "Punjab", 3: "Sindh", 4: "Balochistan",
            6: "Islamabad Capital Territory", 7: "Gilgit-Baltistan",
            8: "Azad Jammu & Kashmir"}
REGION = {1: "rural", 2: "urban"}

ROUTES = {
    1: "Collected by Municipality van from door step",
    2: "Collected by Private van/cart from door step",
    3: "Public Bin/Collection point",
    4: "Road/street",
    5: "Lake/River/Nullah",
    6: "Open space",
    7: "Other (unclassified)",
}
COLLECTED = {1, 2, 3}

SOURCE = "HIES 2024-25 Sec 5 Mod 3 (PBS microdata, sources/HIES/MANIFEST.csv)"


def load():
    df, _ = pyreadstat.read_sav(asset_path(SRC, "Sec 05M3-wasteManagment.sav"),
                                usecols=["hhcode", "Province", "Region", "s5m3q01"])
    w, _ = pyreadstat.read_sav(asset_path(SRC, "plist_roster.sav"),
                               usecols=["hhcode", "weight"])
    weights = w.drop_duplicates("hhcode").set_index("hhcode")["weight"]
    df["weight"] = df["hhcode"].map(weights)
    df = df[df.weight.notna() & df.s5m3q01.notna()].copy()
    df["province"] = df["Province"].map(PROVINCE)
    df["region"] = df["Region"].map(REGION)
    df["route"] = df["s5m3q01"].astype(int)
    return df


def _rows(df, scope):
    out = []
    for region, grp in df.groupby("region"):
        total = grp["weight"].sum()
        by_route = grp.groupby("route")["weight"].sum()
        for code, label in ROUTES.items():
            hh = by_route.get(code, 0.0)
            out.append({"survey": "hies2025", "scope": scope, "region": region,
                        "route": code, "route_label": label,
                        "households_weighted": round(hh),
                        "share_of_region": round(hh / total, 4),
                        "source": SOURCE})
        collected = sum(by_route.get(c, 0.0) for c in COLLECTED)
        for name, hh in (("collected", collected), ("uncollected", total - collected)):
            out.append({"survey": "hies2025", "scope": scope, "region": region,
                        "route": name,
                        "route_label": "derived: routes 1-3 door-step and public-bin"
                        if name == "collected" else "derived: routes 4-7",
                        "households_weighted": round(hh),
                        "share_of_region": round(hh / total, 4),
                        "source": SOURCE})
    return out


def main():
    df = load()
    hh = df.drop_duplicates("hhcode")["weight"].sum()
    print("HIES 2024-25 waste module: %d households, %.2fM weighted"
          % (df["hhcode"].nunique(), hh / 1e6))

    rows = _rows(df, "national")
    for province, grp in df.groupby("province"):
        rows += _rows(grp, province)

    os.makedirs(OUT, exist_ok=True)
    path = asset_path(OUT, "hies_disposal_routes.csv")
    pd.DataFrame(rows).to_csv(path, index=False)
    print("wrote %s (%d rows)" % (path, len(rows)))

    nat = {(r["region"], r["route"]): r["share_of_region"]
           for r in rows if r["scope"] == "national"}
    print("  uncollected: urban %.3f (What a Waste says 0.30), rural %.3f (0.70)"
          % (nat[("urban", "uncollected")], nat[("rural", "uncollected")]))
    print("  waterway (Lake/River/Nullah): urban %.3f, rural %.3f"
          % (nat[("urban", 5)], nat[("rural", 5)]))


if __name__ == "__main__":
    main()
