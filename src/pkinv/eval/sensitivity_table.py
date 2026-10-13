"""Sensitivity of the national agricultural total to the main methodological choices.

The referee asked for the promised soil-EF1, rice-water-regime, and manure-management sensitivities to be
shown numerically. Each scenario re-slices the audited 2024 inventory; none is a full re-run, because the
affected terms scale linearly in the varied parameter:

  * Soil EF1  -- only the upland direct-N2O subitems that use EF1 (synthetic-fertiliser upland, organic
                manure, crop residues) scale by EF1/EF1_default; the flooded-rice EF1FR, pasture EF3, and
                indirect (EF4/EF5) terms are unchanged. This reproduces the documented ~40 Mt at EF1=0.010
                and ~29.6 Mt (the Cui empirical anchor) at EF1=0.0055.
  * Rice SFw  -- rice methane is linear in the (uniform) water-regime scaling factor, so the category
                scales by SFw/SFw_default (default = continuously flooded, 1.0).
  * Manure MMS -- the GLEAM 3.0 South-Asia management split from the MMS cross-check
                (outputs/eval/mms_sensitivity.json), which raises manure direct N2O 2.6x.

Usage:  python3 -m pkinv.eval.sensitivity_table
Writes: outputs/eval/sensitivity.csv
"""

from pkinv.assets import asset_path
import csv
import json
import os

from pkinv.paths import ROOT, OUTPUTS

BYCAT = asset_path(OUTPUTS, "by_category.csv")
NAT = asset_path(OUTPUTS, "national_totals_2024.csv")
MMS = asset_path(ROOT, "outputs", "eval", "mms_sensitivity.json")
OUT = asset_path(ROOT, "outputs", "eval", "sensitivity.csv")

EF1_DEFAULT = 0.005                       # soils_ef1_dry (data/emission_factors.csv)
SFW_DEFAULT = 1.0                         # rice_sfw_continuous
# managed-soils subitems whose direct N2O scales linearly with the upland EF1
EF1_SUBITEMS = ("Direct N2O - synthetic fertiliser (upland)",
                "Direct N2O - organic manure",
                "Direct N2O - crop residues")

# rc64: the pasture-deposition factor, which had no scenario at all while EF1 had three.
# It is the larger lever of the two - the 2019 Refinement cut the cattle value TENFOLD from
# the 2006 default where it halved EF1 - and the FAOSTAT comparison put two-thirds of the
# managed-soils gap in this pool. Unlike EF1 it cannot be scaled by one ratio: the two
# species groups carry different defaults, and the Refinement gives sheep and other animals a
# single value with NO climate split, so a wet scenario moves cattle alone.
EF3PRP_DEFAULT = {"Direct N2O - pasture deposition (cattle-type)": 0.002,
                  "Direct N2O - pasture deposition (sheep/goat/other)": 0.003}
EF3PRP_CASES = [
    ("Pasture EF3PRP wet climate (2019 Refinement)",
     {"Direct N2O - pasture deposition (cattle-type)": 0.006,
      "Direct N2O - pasture deposition (sheep/goat/other)": 0.003}),
    ("Pasture EF3PRP = 2006 aggregate",
     {"Direct N2O - pasture deposition (cattle-type)": 0.02,
      "Direct N2O - pasture deposition (sheep/goat/other)": 0.01}),
]


def _national():
    n = {}
    for r in csv.DictReader(open(NAT, newline="", encoding="utf-8")):
        n[r["category"]] = float(r["co2e_Mt_AR5"])
    return n


def _ef1_linked_soils():
    """Sum of the managed-soils subitems that scale with the upland EF1 (Mt CO2e, at EF1_DEFAULT)."""
    s = 0.0
    for r in csv.DictReader(open(BYCAT, newline="", encoding="utf-8")):
        if r["category"] == "Managed soils" and r["subitem"] in EF1_SUBITEMS:
            s += float(r["co2e_Mt_AR5"])
    return s


def _prp_subitems():
    """{subitem: Mt CO2e} for the two pasture-deposition subitems, at their own defaults."""
    out = {}
    for r in csv.DictReader(open(BYCAT, newline="", encoding="utf-8")):
        if r["category"] == "Managed soils" and r["subitem"] in EF3PRP_DEFAULT:
            out[r["subitem"]] = float(r["co2e_Mt_AR5"])
    missing = sorted(set(EF3PRP_DEFAULT) - set(out))
    if missing:
        raise SystemExit("by_category.csv holds no pasture-deposition row for %s, so the "
                         "EF3PRP scenarios cannot be priced" % "; ".join(missing))
    return out


def scenarios():
    n = _national()
    total0 = n["TOTAL"]
    soils0, rice0, manure0 = n["Managed soils"], n["Rice cultivation"], n["Manure management"]
    ef1_linked = _ef1_linked_soils()
    rows = [{"scenario": "Main case (EF1=0.005 dry; rice continuously flooded)",
             "rice": rice0, "soils": soils0, "manure": manure0, "total": total0}]

    def soils_at(ef1):
        return soils0 + ef1_linked * (ef1 / EF1_DEFAULT - 1.0)

    for label, ef1 in [("Soil EF1 = 0.010 (2006 aggregate)", 0.010),
                       ("Soil EF1 = 0.016 (2019 wet climate)", 0.016),
                       ("Soil EF1 = 0.0055 (Cui 2021 empirical)", 0.0055)]:
        soils = soils_at(ef1)
        rows.append({"scenario": label, "rice": rice0, "soils": soils, "manure": manure0,
                     "total": total0 - soils0 + soils})

    # The pasture factor, scaled per species group because their defaults differ. Direct
    # subitems only, exactly as the EF1 cases do: the indirect legs run on EF4 and EF5, which
    # these scenarios do not touch, so the numbers here understate what a whole-vintage swap
    # would do and say so rather than pretending otherwise.
    prp = _prp_subitems()
    for label, efs in EF3PRP_CASES:
        delta = sum(prp[k] * (efs[k] / EF3PRP_DEFAULT[k] - 1.0) for k in prp)
        soils = soils0 + delta
        rows.append({"scenario": label, "rice": rice0, "soils": soils, "manure": manure0,
                     "total": total0 - soils0 + soils})

    # Both 2006 direct factors together, because that is the comparator's actual vintage and
    # the two scenarios above are disjoint: EF1 scales synthetic, organic manure and residues,
    # EF3PRP scales the two pasture rows, and no subitem is in both sets.
    prp_2006 = dict(EF3PRP_CASES[1][1])
    delta_prp = sum(prp[k] * (prp_2006[k] / EF3PRP_DEFAULT[k] - 1.0) for k in prp)
    soils_both = soils_at(0.010) + delta_prp
    rows.append({"scenario": "Both 2006 direct factors (EF1 0.010 + EF3PRP aggregate)",
                 "rice": rice0, "soils": soils_both, "manure": manure0,
                 "total": total0 - soils0 + soils_both})

    for label, sfw in [("Rice intermittent SFw = 0.52 (AWD)", 0.52),
                       ("Rice rainfed SFw = 0.28", 0.28)]:
        rice = rice0 * sfw / SFW_DEFAULT
        rows.append({"scenario": label, "rice": rice, "soils": soils0, "manure": manure0,
                     "total": total0 - rice0 + rice})

    # The manure-management scenario CANNOT be re-sliced like the others. EF1 and SFw touch one
    # category each, so swapping that category's total is exact. A different management split is not
    # like that: the nitrogen ledger is coupled, so it changes how much manure nitrogen reaches the
    # field and therefore moves managed soils as well as manure management. Re-slicing the manure
    # category alone -- which this did before the ledger coupled them -- silently held soils fixed
    # and produced a total 0.9 Mt from the full rerun. The scenario is now taken from the rerun.
    for row in _gleam_full_rerun():
        rows.append(row)

    for r in rows:
        r["delta"] = r["total"] - total0
    return rows, total0


def _gleam_full_rerun():
    """The GLEAM manure-split scenario, from a full engine rerun rather than a category re-slice.

    Returns [] if the structural-uncertainty module is unavailable, so the sensitivity table still
    builds; the missing row is visible rather than silently wrong.
    """
    try:
        from pkinv.eval import mms_structural_uncertainty as msu
    except Exception:
        return []
    for r in msu.scenarios():
        if "GLEAM" not in r["configuration"]:
            continue
        return [{"scenario": "Manure MMS = GLEAM 3.0 South-Asia split",
                 "rice": r["rice_Mt"], "soils": r["managed_soils_Mt"],
                 "manure": r["manure_Mt"], "total": r["national_total_Mt"]}]
    return []


def main():
    rows, total0 = scenarios()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "rice", "soils", "manure", "total", "delta"])
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
    print("Sensitivity of the national agricultural total -> outputs/eval/sensitivity.csv")
    print("  %-46s %6s %6s %6s %8s" % ("scenario", "rice", "soils", "manure", "total"))
    for r in rows:
        print("  %-46s %6.1f %6.1f %6.1f %8.1f (%+.1f)"
              % (r["scenario"][:46], r["rice"], r["soils"], r["manure"], r["total"], r["delta"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
