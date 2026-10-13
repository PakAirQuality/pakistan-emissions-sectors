"""Ingest HIES microdata into committed fuel-quantity CSVs.

WHAT THIS PRODUCES. The design-weighted household fuel statistics the residential sector
reconciles against: physical quantities (kg or litres per month, four acquisition routes -
paid, wages-in-kind, own-produced, gifts/assistance - annualised x12) and expenditure for
the value-only items (piped gas, generator fuel, agricultural wastes, cotton sticks), by
survey round, province and urban/rural stratum. The microdata zips are gitignored and
hash-pinned in sources/HIES/MANIFEST.csv; these derived CSVs are committed, so the package
never needs pandas or pyreadstat - both are quarantined to this script.

BOTH ROUNDS, ONE ITEM VOCABULARY. HIES 2018-19 and 2024-25 use the same 045xxx item codes
(confirmed against the 2024-25 questionnaire, Section 6 Part C, 'during the last 1 month'):
045202 LPG kg, 045301 kerosene litres, 045401 firewood kg, 045402 charcoal kg, 045403 coal
kg, 045404 dung cake kg; value-only 045101/02 electricity and GENERATOR FUEL, 045201 piped
gas, 045405 agricultural wastes, 045406 cotton sticks.

WEIGHTS. 2024-25 carries a household weight on the person roster; 2018-19 publishes PSU
weights joined on the household code's PSU. Weighted household totals land near 40 million
households for 2024-25, which is the sanity anchor.

Usage:  python3 scripts/ingest_hies.py
Writes: data/activity/residential/hies/hies_fuel_quantities.csv
        data/activity/residential/hies/hies_national_totals.csv
"""

from pkinv.assets import asset_path
import os

import pandas as pd
import pyreadstat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = asset_path(ROOT, "sources", "HIES")
OUT = asset_path(ROOT, "data", "activity", "residential", "hies")

PROVINCE = {1: "Khyber Pakhtunkhwa", 2: "Punjab", 3: "Sindh", 4: "Balochistan",
            6: "Islamabad Capital Territory", 7: "Gilgit-Baltistan",
            8: "Azad Jammu & Kashmir"}
REGION = {1: "rural", 2: "urban"}

# item code -> (fuel name, unit, kind). Quantity items report physical q1..q4; value-only
# items carry only rupee values (the questionnaire prints no Unit for them).
ITEMS = {
    45202: ("lpg", "kg", "quantity"),
    45301: ("kerosene", "litre", "quantity"),
    45401: ("firewood", "kg", "quantity"),
    45402: ("charcoal", "kg", "quantity"),
    45403: ("coal", "kg", "quantity"),
    45404: ("dung_cake", "kg", "quantity"),
    45101: ("electricity", "rupees", "value"),
    45102: ("generator_fuel", "rupees", "value"),
    45201: ("natural_gas", "rupees", "value"),
    45405: ("agricultural_waste", "rupees", "value"),
    45406: ("cotton_sticks", "rupees", "value"),
}

SURVEYS = {
    "hies2019": {
        "consumption": asset_path(SRC, "HIES_2018-19", "data_in_spss", "sec 6a.sav"),
        "label": "HIES 2018-19 (PBS microdata, sources/HIES/MANIFEST.csv)",
    },
    "hies2025": {
        "consumption": asset_path(SRC, "HIES_2024-25", "SPSS data",
                                    "Sec 6a-consum-Exp.sav"),
        "label": "HIES 2024-25 (PBS microdata, first digital round, "
                 "sources/HIES/MANIFEST.csv)",
    },
}


def _weights_2025():
    df, _ = pyreadstat.read_sav(
        asset_path(SRC, "HIES_2024-25", "SPSS data", "plist_roster.sav"),
        usecols=["hhcode", "weight"])
    return df.drop_duplicates("hhcode").set_index("hhcode")["weight"]


def _weights_2019():
    w, _ = pyreadstat.read_sav(
        asset_path(SRC, "HIES_2018-19", "data_in_spss", "weight.sav"))
    w.columns = [c.lower() for c in w.columns]
    return w.set_index("psu")["weight"]


def load(survey):
    cfg = SURVEYS[survey]
    df, _ = pyreadstat.read_sav(cfg["consumption"])
    df.columns = [c.lower() for c in df.columns]
    df = df[df.itc.isin(ITEMS)].copy()
    for c in ("q1", "q2", "q3", "q4", "v1", "v2", "v3", "v4"):
        df[c] = df[c].fillna(0.0)
    df["qty_month"] = df[["q1", "q2", "q3", "q4"]].sum(axis=1)
    df["value_month"] = df[["v1", "v2", "v3", "v4"]].sum(axis=1)
    df["own_share_qty"] = df["q3"]

    if survey == "hies2025":
        w = _weights_2025()
        df["weight"] = df["hhcode"].map(w)
    else:
        df["psu_key"] = df["psu"]
        df["weight"] = df["psu_key"].map(_weights_2019())
    df = df[df.weight.notna()].copy()
    df["province"] = df["province"].map(PROVINCE)
    df["region"] = df["region"].map(REGION)
    return df


def summarise(df, survey):
    strata_rows, national_rows = [], []
    total_hh = df.drop_duplicates("hhcode")[["hhcode", "weight"]]
    n_hh_by = df.drop_duplicates("hhcode").groupby(["province", "region"])["weight"].sum()

    for itc, (fuel, unit, kind) in ITEMS.items():
        sub = df[df.itc == itc]
        col = "qty_month" if kind == "quantity" else "value_month"
        using = sub[sub[col] > 0]
        for (prov, region), grp in using.groupby(["province", "region"]):
            hh_total = n_hh_by.get((prov, region), 0.0)
            w_users = grp["weight"].sum()
            strata_rows.append({
                "survey": survey, "province": prov, "region": region, "fuel": fuel,
                "unit": unit, "kind": kind,
                "users_weighted": round(w_users),
                "users_share": round(w_users / hh_total, 4) if hh_total else "",
                "mean_monthly_per_using_hh":
                    round((grp[col] * grp["weight"]).sum() / w_users, 3),
                "annual_total": round((grp[col] * grp["weight"]).sum() * 12.0),
                "own_produced_share_of_qty":
                    round((grp["own_share_qty"] * grp["weight"]).sum()
                          / (grp["qty_month"] * grp["weight"]).sum(), 3)
                    if kind == "quantity"
                    and (grp["qty_month"] * grp["weight"]).sum() else "",
                "n_obs": len(grp),
            })
        w_users_nat = using["weight"].sum()
        # Weighted rupee total for every item (for quantity items this is the value the
        # survey attaches to the same consumption, all four routes; own-produced and
        # gifted consumption carries PBS's imputed value). Enables unit values (Rs/kg)
        # and the expenditure->quantity route for the value-only residue items.
        value_annual = (using["value_month"] * using["weight"]).sum() * 12.0
        national_rows.append({
            "survey": survey, "fuel": fuel, "unit": unit, "kind": kind,
            "users_weighted": round(w_users_nat),
            "users_share": round(w_users_nat / total_hh["weight"].sum(), 4),
            "annual_total": round((using[col] * using["weight"]).sum() * 12.0),
            "value_annual_rs": round(value_annual),
            "n_obs": len(using),
        })
    return strata_rows, national_rows


def diagnostics(df, survey):
    """Per-fuel survey diagnostics: the numbers that make a design-weighted total
    checkable rather than assertable.

    Design SEs are stratum-clustered linearized totals (strata = province x region,
    clusters = the PSU where the round publishes one, else the enumeration-area code
    prefix of the household ID as the closest available cluster proxy - labelled).
    Top-share columns report how much of the weighted total rides the heaviest 1 and 5
    percent of reporting households: outlier concentration, the kerosene failure mode.
    """
    import numpy as np
    if "psu" in df.columns:
        df = df.assign(_cluster=df["psu"], _clabel="published PSU")
    else:
        df = df.assign(_cluster=df["hhcode"].astype(int) // 100,
                       _clabel="hhcode/100 enumeration-block proxy")
    rows = []
    for itc, (fuel, unit, kind) in ITEMS.items():
        sub = df[df.itc == itc]
        col = "qty_month" if kind == "quantity" else "value_month"
        using = sub[sub[col] > 0].copy()
        if not len(using):
            continue
        using["annual"] = using[col] * 12.0
        using["wx"] = using["weight"] * using["annual"]
        total = using["wx"].sum()
        # stratum-clustered linearized variance of the weighted total
        var = 0.0
        for (_p, _r), grp in using.groupby(["province", "region"]):
            z = grp.groupby("_cluster")["wx"].sum().values
            n = len(z)
            if n > 1:
                var += n / (n - 1.0) * ((z - z.mean()) ** 2).sum()
        se = var ** 0.5
        ranked = using.sort_values("annual", ascending=False)
        n_obs = len(ranked)
        top1 = ranked.head(max(1, int(np.ceil(0.01 * n_obs))))["wx"].sum() / total
        top5 = ranked.head(max(1, int(np.ceil(0.05 * n_obs))))["wx"].sum() / total
        w_users = using["weight"].sum()
        quarters = (sorted(using["quater"].dropna().unique())
                    if "quater" in using.columns else None)
        rows.append({
            "survey": survey, "fuel": fuel, "unit": unit, "kind": kind,
            "n_reporting_households": n_obs,
            "weighted_users": round(w_users),
            "per_user_hh_day": round(total / w_users / 365.0, 3),
            "design_se_pct_of_total": round(100.0 * se / total, 2),
            "top1pct_hh_share_of_total": round(top1, 3),
            "top5pct_hh_share_of_total": round(top5, 3),
            "interview_quarters_covered": (len(quarters) if quarters is not None
                                           else "not recorded in this round"),
            "cluster_basis": using["_clabel"].iloc[0],
        })
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    all_strata, all_national, all_diag = [], [], []
    for survey in ("hies2019", "hies2025"):
        df = load(survey)
        strata, national = summarise(df, survey)
        all_strata += strata
        all_national += national
        all_diag += diagnostics(df, survey)
        hh = df.drop_duplicates("hhcode")["weight"].sum()
        print("%s: %d fuel rows, %.1fM weighted households"
              % (survey, len(df), hh / 1e6))
    pd.DataFrame(all_diag).to_csv(
        asset_path(OUT, "hies_diagnostics.csv"), index=False)

    pd.DataFrame(all_strata).to_csv(
        asset_path(OUT, "hies_fuel_quantities.csv"), index=False)
    nat = pd.DataFrame(all_national)
    nat["source"] = nat["survey"].map(lambda s: SURVEYS[s]["label"])
    nat.to_csv(asset_path(OUT, "hies_national_totals.csv"), index=False)

    for _, r in nat[nat.kind == "quantity"].iterrows():
        print("  %-9s %-10s %12.0f %s/yr  (users %4.1f%%)"
              % (r.survey, r.fuel, r.annual_total, r.unit, 100 * r.users_share))


if __name__ == "__main__":
    main()
