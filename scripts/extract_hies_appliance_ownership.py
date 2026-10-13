#!/usr/bin/env python3
"""Household ownership of HFC-bearing appliances from the held PBS HIES microdata.

WHAT THIS PRODUCES. data/activity/ippu/hies_appliance_ownership.csv: design-weighted
shares of Pakistani households that PRESENTLY OWN a refrigerator, deep freezer, air
conditioner, air cooler, motor car, motorcycle (and, where asked, scooter), nationally
and by urban/rural region, for each HIES round held under data/raw/pbs/hies/. This is a
STOCK indicator for the IPCC 2.F.1 refrigeration and air-conditioning equipment bank:
what matters for the bank is the number of charged units in service, not what was
bought or consumed in the year.

WHERE THE ANSWER LIVES. HIES 2018-19 and 2024-25 carry a Section 7 "Selected Durable
Consumption Items Owned / Sold by the Household": one row per (household, item code
701-735) with the number owned during the last year, the number presently owned and a
sale amount. The item codes are printed on page 22 of the held 2024-25 questionnaire
(sources/HIES/Male-Questionnaire-HIES-2024-25-English.pdf) and carried as value labels
on the code column of both releases (704 refrigerator, 705 freezer, 708 air conditioner,
709 air cooler, 728 motor cycle, 729 scooter [2024-25] / rickshaw-chingchi [2018-19],
730 car). Items a household does not own have NO row, so the household frame is taken
from the person roster (plist), not from the durables file.

HIES 2015-16 has no such section in the Stata release: all 20 .dta files were opened
(metadata + value labels) and none carries item codes 701-735 or any label naming a
refrigerator/air conditioner as an OWNED item. What 2015-16 does carry is Section 4
Part E, the value of durables ACQUIRED during the last year, itemized in sec_4abcde.dta
(itc 53101 refrigerator, 53102 deep freezers, 53103 split/window air conditioner, 53104
air cooler, 71101 car, 71201 motor cycle/scooter; values only, no quantity). That is an
acquisition FLOW, not the stock; it is reported in the 2015-16 notes and on stdout, and
kept out of the ownership columns. (2018-19 and 2024-25 lump all cooling appliances into
one Part E code 53103, so no appliance-specific flow exists there.) The 2015-16 rows are
typed absences (status not_in_release) with the household frame reported and every
ownership cell EMPTY - never zero.

WEIGHTS. 2015-16: weight.dta (psu -> weights), identical to the per-household weights
on plist. 2018-19: weight.dta (psu -> weight), identical to the plist weights within
float32 precision. 2024-25: plist_roster carries one weight per household, identical
to weight.dta (prcode -> weight). Weighted totals: 25.99 M (2015-16), 33.34 M (2018-19),
40.12 M (2024-25) households.

OWNERSHIP RULE. A household owns the item when the presently-owned count is >= 1. Where
the presently-owned cell is blank but the owned-during-the-year count is >= 1 and no
sale amount is recorded, the during-year count is used (the fallback count is written
into the note). weighted_units_owned = sum(weight x presently-owned count) over owners,
as recorded - a handful of records carry implausible counts (e.g. 11 refrigerators) and
they are counted, not edited, with their number in the note.

STATUS. The task's "verified" rule (weighted total within 5 percent of PBS's published
household count) cannot be met from the held documentation: the zips carry no
documentation and the held 2024-25 report publishes only the SAMPLE distribution
(Table 2: 30,123 households, 10,960 urban / 19,163 rural - which the release matches
exactly) and an average household size (5.98). Every populated row is therefore
status "extracted"; the 2024-25 release is PBS's "validation only" cut (30,123 of the
35,792 designed sample), stated in its note.

Reproducible from the zips alone: extracts only the needed .dta members into a scratch
directory OUTSIDE the repo (HIES_SCRATCH env var, default the session scratchpad),
never downloads, never writes into data/raw or sources.
"""

from pkinv.assets import asset_path
import os
import sys
import zipfile

import numpy as np
import pandas as pd
import pyreadstat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = asset_path(ROOT, "data", "raw", "pbs", "hies")
OUT = asset_path(ROOT, "data", "activity", "ippu", "hies_appliance_ownership.csv")
SCRATCH = os.environ.get(
    "HIES_SCRATCH",
    "/private/tmp/claude-501/-Users-rehanahmad-Desktop-emissions/"
    "500c4ae4-3141-4e4b-a076-4fd9fa3fe064/scratchpad/hies")

REGION = {1: "rural", 2: "urban"}

# appliance -> item code, common to the two rounds that ask the section
APPLIANCES = [
    ("refrigerator", 704),
    ("deep_freezer", 705),
    ("air_conditioner", 708),
    ("air_cooler", 709),
    ("motor_car", 730),
    ("motorcycle", 728),
]

SURVEYS = {
    "HIES 2015-16": dict(
        zip="hies_2015_16_stata.zip", period="FY2015-16",
        frame="data_stata_2015-16/plist.dta", frame_weight="weights",
        weight_file="data_stata_2015-16/weight.dta", weight_key="psu", weight_col="weights",
        durables=None,
        # Section 4 Part E: value of durables acquired during the year (flow, value only)
        flow_file="data_stata_2015-16/sec_4abcde.dta",
        flow_codes={"refrigerator": 53101, "deep_freezer": 53102, "air_conditioner": 53103,
                    "air_cooler": 53104, "motor_car": 71101, "motorcycle": 71201},
    ),
    "HIES 2018-19": dict(
        zip="hies_2018_19_stata.zip", period="FY2018-19",
        frame="data_in_stata/plist.dta", frame_weight=None,
        weight_file="data_in_stata/weight.dta", weight_key="psu", weight_col="weight",
        durables="data_in_stata/sec_7a.dta", code="code",
        during="c01", present="c02", sold="c03",
        extra=[],  # 729 is rickshaw/chingchi in this round; scooters sit inside 728
        note="2018-19 item 728 is printed 'motor cycle /scotter' (scooters folded in); "
             "729 is rickshaw/chingchi, not comparable with 2024-25's 729 scooter.",
    ),
    "HIES 2024-25": dict(
        zip="HIES_2024-25_Stata_validation_only.zip", period="FY2024-25",
        frame="Stata data/plist_roster.dta", frame_weight="weight",
        weight_file="Stata data/weight.dta", weight_key="prcode", weight_col="weight",
        durables="Stata data/sec_7.dta", code="itc",
        during="s7m_a", present="s7m_b", sold="s7m_c",
        extra=[("scooter", 729)],
        note="PBS 'validation only' Stata release: 30,123 households of the 35,792 in the "
             "designed sample; sample counts match the held report's Table 2 exactly "
             "(10,960 urban / 19,163 rural); no published weighted household count in the "
             "held documentation, so status stays extracted.",
    ),
}

HEADER = """\
# HOUSEHOLD OWNERSHIP OF HFC-BEARING APPLIANCES, PBS HIES microdata (restricted-microdata,
# research-use terms; see data/raw_manifest.csv rows for data/raw/pbs/hies/*.zip).
# Built by scripts/extract_hies_appliance_ownership.py from the three held zips; nothing
# downloaded. Rows: one per survey x appliance nationally (region empty) plus one per
# urban/rural region where the survey asks the item.
# SOURCE TABLE: Section 7 "Selected Durable Consumption Items Owned / Sold by the Household"
# - HIES 2018-19 sec_7a.dta (code, c01 owned during year, c02 presently owned, c03 sold),
# HIES 2024-25 sec_7.dta (itc, s7m_a, s7m_b, s7m_c). Item codes 704 refrigerator, 705 freezer,
# 708 air conditioner, 709 air cooler, 728 motor cycle, 729 scooter (2024-25 only), 730 car,
# as printed on p.22 of the held 2024-25 questionnaire and carried as value labels.
# HIES 2015-16 carries no durable-ownership section in its Stata release (all 20 .dta files
# inspected); its rows are typed absences - ownership cells EMPTY, never zero. Its note carries
# the only appliance-specific quantity that round has: the weighted share of households that
# ACQUIRED the item during the year (Section 4 Part E, sec_4abcde.dta itc 53101/53102/53103/
# 53104/71101/71201, value only) - a flow into the bank, not the bank.
# HOUSEHOLD FRAME AND WEIGHTS: households = unique hhcode on the person roster (plist);
# design weights from weight.dta (2015-16 psu->weights, 2018-19 psu->weight) or the roster's
# own household weight (2024-25), each cross-checked equal to the other file. A household with
# no row for an item does not own it; households with no Section 7 record at all are counted
# in the frame as owning nothing (their count is in the note).
# OWNERSHIP = presently-owned count >= 1 (fallback: during-year count when the present cell is
# blank and no sale is recorded). ownership_share_pct = weighted owners / weighted frame x 100.
# weighted_units_owned = sum(weight x presently-owned count), counts as recorded.
# READ THIS AS A STOCK. Ownership is the installed base of charged equipment - the HFC BANK of
# IPCC 2.F.1. Supply (imports, assembly) ENTERS the bank; the refrigerant a household 'consumes'
# is not an emission. Emissions follow from the bank via charge sizes, leak rates and
# end-of-life handling, none of which this table carries.
# status: extracted = design-weighted from microdata, no published household total to test
# against; not_in_release = the survey's held release does not carry the section.
"""


def _extract(zip_name, members):
    """Extract only the named members into the scratch tree; return their paths."""
    dest = asset_path(SCRATCH, os.path.splitext(zip_name)[0])
    os.makedirs(dest, exist_ok=True)
    paths = {}
    with zipfile.ZipFile(asset_path(RAW, zip_name)) as zf:
        names = zf.namelist()
        for m in members or names:
            # archives nest the members under one directory; match by suffix
            hit = [n for n in names if n.endswith(m)]
            if not hit:
                raise FileNotFoundError(f"{m} not in {zip_name}")
            target = asset_path(dest, hit[0])
            if not os.path.exists(target):
                zf.extract(hit[0], dest)
            paths[m] = target
    return paths


def _read(path, usecols=None):
    try:
        df, meta = pyreadstat.read_dta(path, usecols=usecols)
    except Exception:  # 2015-16 sec_1b carries non-UTF-8 label bytes
        df, meta = pyreadstat.read_dta(path, usecols=usecols, encoding="latin1")
    return df, meta


def household_frame(cfg, paths):
    cols = ["hhcode", "region", cfg["weight_key"]]
    if cfg["frame_weight"]:
        cols.append(cfg["frame_weight"])
    plist, _ = _read(paths[cfg["frame"]], usecols=cols)
    frame = plist.drop_duplicates("hhcode").copy()
    w, _ = _read(paths[cfg["weight_file"]])
    w = w.set_index(cfg["weight_key"])[cfg["weight_col"]]
    frame["weight"] = frame[cfg["weight_key"]].map(w)
    if cfg["frame_weight"]:
        if not np.allclose(frame["weight"], frame[cfg["frame_weight"]], rtol=1e-5):
            raise AssertionError("roster weight and weight.dta disagree")
    if frame["weight"].isna().any():
        raise AssertionError("households without a design weight")
    frame["region"] = frame["region"].map(REGION)
    return frame[["hhcode", "region", "weight"]]


def prove_absence(zip_name):
    """Open every member's metadata. The ownership section identifies itself by an item
    code column whose value labels put 'refrigerator' on 704 and 'air condi' on 708 (both
    rounds that have it) or by a column labelled 'presently owned'. Returns the files seen,
    the ownership hits (must be empty for the absence to be typed) and, for the note, the
    labels that DO name the appliances elsewhere (the Part E acquisition items)."""
    paths = _extract(zip_name, None)
    seen, own_hits, other = [], [], []
    for m, p in sorted(paths.items()):
        if not p.endswith(".dta"):
            continue
        _, meta = pyreadstat.read_dta(p, metadataonly=True, encoding="latin1")
        base = os.path.basename(p)
        seen.append(base)
        for lab in meta.column_labels:
            if lab and "presently owned" in str(lab).lower():
                own_hits.append(f"{base}: {lab}")
        for col, vl in meta.variable_value_labels.items():
            l704, l708 = str(vl.get(704, "")).lower(), str(vl.get(708, "")).lower()
            if "refrig" in l704 and "air cond" in l708:
                own_hits.append(f"{base}:{col} carries item codes 704/708")
            for code, lab in vl.items():
                low = str(lab).lower()
                if ("refrig" in low or "air cond" in low) and "mechanic" not in low \
                        and "supply" not in low:
                    other.append(f"{base}:{col}=={code} '{lab}'")
    return seen, own_hits, other


def acquisition_flow(cfg, frame, paths):
    """2015-16 Part E: weighted share of households reporting any value for the item in
    the year (paid, in-kind, own-produced or received). A flow, kept out of the columns."""
    df, meta = _read(paths[cfg["flow_file"]],
                     usecols=["hhcode", "itc", "v1", "v2", "v3", "v4"])
    labels = meta.variable_value_labels.get("itc", {})
    out = {}
    for appliance, code in cfg["flow_codes"].items():
        sub = df[df["itc"] == code].copy()
        vals = sub[["v1", "v2", "v3", "v4"]].apply(pd.to_numeric, errors="coerce")
        buyers = sub.loc[(vals > 0).any(axis=1), "hhcode"].drop_duplicates()
        w = frame.loc[frame["hhcode"].isin(buyers), "weight"].sum()
        out[appliance] = dict(code=code, label=str(labels.get(code, "")).strip(),
                              n=int(len(buyers)), weighted=int(round(w)),
                              share=round(100.0 * w / frame["weight"].sum(), 2))
    return out


def ownership_rows(survey, cfg, frame, durables, meta, appliances):
    code_col = cfg["code"]
    labels = meta.variable_value_labels.get(code_col, {})
    for c in (cfg["during"], cfg["present"], cfg["sold"]):
        durables[c] = pd.to_numeric(durables[c], errors="coerce")
    in_section = frame["hhcode"].isin(durables["hhcode"])
    no_record = int((~in_section).sum())
    zip_member = f"{cfg['zip']}:{cfg['durables']}"
    weight_var = (f"{os.path.basename(cfg['weight_file'])} {cfg['weight_key']}->"
                  f"{cfg['weight_col']} joined to {os.path.basename(cfg['frame'])} hhcode")
    rows = []
    for appliance, code in appliances:
        sub = durables[durables[code_col] == code].copy()
        if sub.duplicated("hhcode").any():
            raise AssertionError(f"{survey} {code}: duplicate household rows")
        present = sub[cfg["present"]]
        fallback = present.isna() & (sub[cfg["during"]] >= 1) & \
            (sub[cfg["sold"]].isna() | (sub[cfg["sold"]] == 0))
        present = present.where(~fallback, sub[cfg["during"]])
        sub["units"] = present
        owners = sub[sub["units"] >= 1][["hhcode", "units"]]
        big = int((owners["units"] > 5).sum())
        merged = frame.merge(owners, on="hhcode", how="left")
        merged["owns"] = merged["units"].notna()
        merged["units"] = merged["units"].fillna(0.0)
        label = str(labels.get(code, "")).strip()
        base_note = (f"{cfg.get('note', '')} Frame households with no Section 7 record: "
                     f"{no_record} (counted as owning nothing). Fallback to during-year "
                     f"count: {int(fallback.sum())} rows. Owner records with count >5: {big}.")
        for region, grp in [("", merged)] + [(r, merged[merged["region"] == r])
                                              for r in ("urban", "rural")]:
            w_tot = grp["weight"].sum()
            w_own = grp.loc[grp["owns"], "weight"].sum()
            rows.append({
                "survey": survey, "survey_period": cfg["period"], "region": region,
                "appliance": appliance, "appliance_label_printed": label,
                "sample_households": int(len(grp)),
                "weighted_households_owning": int(round(w_own)),
                "weighted_households_total": int(round(w_tot)),
                "ownership_share_pct": round(100.0 * w_own / w_tot, 2),
                "weighted_units_owned": int(round((grp["weight"] * grp["units"]).sum())),
                "variable_names": (f"{zip_member} {code_col}=={code}; presently owned "
                                   f"{cfg['present']} (fallback {cfg['during']} when blank "
                                   f"and {cfg['sold']} shows no sale); frame "
                                   f"{cfg['frame']} hhcode"),
                "weight_variable": weight_var,
                "status": "extracted",
                "note": base_note.strip(),
            })
    return rows


def absence_rows(survey, cfg, frame, seen, own_hits, other, flow):
    if own_hits:
        raise AssertionError(f"{survey}: an ownership section exists after all: {own_hits}")
    rows = []
    for appliance, code in APPLIANCES:
        f = flow[appliance]
        rows.append({
            "survey": survey, "survey_period": cfg["period"], "region": "",
            "appliance": appliance, "appliance_label_printed": "",
            "sample_households": int(len(frame)),
            "weighted_households_owning": "",
            "weighted_households_total": int(round(frame["weight"].sum())),
            "ownership_share_pct": "", "weighted_units_owned": "",
            "variable_names": (f"{cfg['zip']}: no durable-ownership section in the release "
                               f"(ownership item code {code} absent)"),
            "weight_variable": (f"{os.path.basename(cfg['weight_file'])} {cfg['weight_key']}->"
                                f"{cfg['weight_col']} joined to plist.dta hhcode"),
            "status": "not_in_release",
            "note": ("Durable-goods OWNERSHIP not carried by the held Stata release; every "
                     ".dta opened (metadata and value labels), none carries the Section 7 "
                     f"item codes 701-735 or a 'presently owned' column: {', '.join(seen)}. "
                     "Ownership cells empty by design. The round's only appliance-specific "
                     "quantity is the Section 4 Part E ACQUISITION value (a flow into the "
                     f"bank, not the stock): {os.path.basename(cfg['flow_file'])} itc=="
                     f"{f['code']} '{f['label']}' reported by {f['n']} sample households = "
                     f"{f['weighted']:,} weighted households = {f['share']}% of households "
                     "acquiring during the year (value only, no quantity asked)."),
        })
    return rows


def main():
    all_rows, flows = [], {}
    for survey, cfg in SURVEYS.items():
        if cfg["durables"] is None:
            seen, own_hits, other = prove_absence(cfg["zip"])
            paths = _extract(cfg["zip"], [cfg["frame"], cfg["weight_file"], cfg["flow_file"]])
            frame = household_frame(cfg, paths)
            flow = acquisition_flow(cfg, frame, paths)
            all_rows += absence_rows(survey, cfg, frame, seen, own_hits, other, flow)
            flows[survey] = (flow, other)
            continue
        paths = _extract(cfg["zip"], [cfg["frame"], cfg["weight_file"], cfg["durables"]])
        frame = household_frame(cfg, paths)
        durables, meta = _read(paths[cfg["durables"]])
        if not durables["hhcode"].isin(frame["hhcode"]).all():
            raise AssertionError(f"{survey}: durables households outside the roster frame")
        all_rows += ownership_rows(survey, cfg, frame, durables, meta,
                                   APPLIANCES + cfg["extra"])

    cols = ["survey", "survey_period", "region", "appliance", "appliance_label_printed",
            "sample_households", "weighted_households_owning", "weighted_households_total",
            "ownership_share_pct", "weighted_units_owned", "variable_names",
            "weight_variable", "status", "note"]
    table = pd.DataFrame(all_rows, columns=cols)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as handle:
        handle.write(HEADER)
        table.to_csv(handle, index=False, lineterminator="\n")

    # stdout: shares per appliance per survey, and the weighted household totals
    nat = table[table["region"] == ""]
    shares = nat.pivot(index="appliance", columns="survey", values="ownership_share_pct")
    shares = shares.reindex([a for a, _ in APPLIANCES] + ["scooter"])
    print("Ownership share of households (%), national, presently owned >= 1"
          " (empty = not in release):")
    print(shares.astype(object).where(shares.notna(), "").to_string())
    print("\nWeighted household totals (design-weighted frame) and sample households:")
    tot = table.drop_duplicates(["survey", "region"])[
        ["survey", "region", "sample_households", "weighted_households_total"]]
    tot["region"] = tot["region"].replace("", "national")
    print(tot.to_string(index=False))
    print("\nWeighted units presently owned (national):")
    units = nat.pivot(index="appliance", columns="survey", values="weighted_units_owned")
    units = units.reindex(shares.index)
    print(units.astype(object).where(units.notna(), "").to_string())
    for survey, (flow, other) in flows.items():
        print(f"\n{survey}: no ownership section; Part E ACQUISITION flow (share of households"
              " reporting a purchase/receipt value in the year - NOT stock):")
        print(pd.DataFrame(flow).T[["code", "label", "n", "weighted", "share"]].to_string())
        print("  appliance-naming labels found in the release: "
              + "; ".join(sorted(set(other))))
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}: {len(table)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
