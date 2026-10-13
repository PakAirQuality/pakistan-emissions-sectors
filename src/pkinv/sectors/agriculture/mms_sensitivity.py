"""Manure-management-system (MMS) cross-check + sensitivity: current vs FAO GLEAM 3.0 (South Asia).

The inventory's MMS split (data/mms_shares.csv) is Tier-2/literature and FAOSTAT-consistent. GLEAM 3.0
(FAO's global livestock model) publishes a very different South-Asia split -- dry-lot-heavy for cattle,
no pasture for buffalo. Because IPCC EF3(dry lot)=0.02 is the largest management factor, GLEAM's split
roughly TRIPLES the manure direct N2O and pushes the manure category to ~2x FAOSTAT. That is a taxonomy/EF
mismatch (GLEAM's smallholder "dry lot" != IPCC open-feedlot EF3), not a refinement -- so we keep the
FAOSTAT-consistent split as primary and report GLEAM here as an independent cross-check that surfaces MMS
as a large hidden uncertainty in the manure N2O. It changes NO control total.

Usage:  python3 -m pkinv.sectors.agriculture.mms_sensitivity
Writes: outputs/eval/mms_sensitivity.json
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import json
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture import manure  # noqa: E402
from pkinv.core import gwp  # noqa: E402

from pkinv.paths import ROOT

GLEAM_CSV = asset_path(ROOT, "data", "gleam_mms.csv")
OUT_JSON = asset_path(ROOT, "outputs", "eval", "mms_sensitivity.json")
FAOSTAT_MANURE = 14.6            # Mt CO2e (CH4+N2O), FAOSTAT GT Pakistan 2023 (data/benchmarks.csv)


def _load_gleam_mms():
    mms = {}
    for r in _activity_rows(GLEAM_CSV, comments=False):
        mms.setdefault(r["species"], {})[r["system"]] = float(r["share"])
    return mms


def _manure_summary(data):
    g = gwp.GWP["AR5"]
    comps, npools = manure.compute(data)
    n2o_gg = {c["subitem"]: c["emissions_Gg"] for c in comps if c["gas"] == "N2O"}
    ch4_gg = sum(c["emissions_Gg"] for c in comps if c["gas"] == "CH4")
    n2o_mt = sum(n2o_gg.values()) * g["N2O"] / 1000.0
    ch4_mt = ch4_gg * g["CH4"] / 1000.0
    return {"direct_n2o_Gg": round(sum(v for k, v in n2o_gg.items() if "Direct" in k), 3),
            "indirect_n2o_Gg": round(sum(v for k, v in n2o_gg.items() if "Indirect" in k), 3),
            "n2o_Mt_co2e": round(n2o_mt, 3), "ch4_Mt_co2e": round(ch4_mt, 3),
            "manure_total_Mt_co2e": round(ch4_mt + n2o_mt, 3),
            "pasture_N_kg": round(npools["FPRP_cattle_N"] + npools["FPRP_other_N"], 1)}


def compute():
    data = InventoryData()
    base = _manure_summary(data)
    data.mms = _load_gleam_mms()
    gleam = _manure_summary(data)
    ratio = round(gleam["direct_n2o_Gg"] / base["direct_n2o_Gg"], 2) if base["direct_n2o_Gg"] else None
    return {
        "layer": "MMS cross-check: current (primary) vs GLEAM 3.0 South Asia",
        "primary_source": "data/mms_shares.csv (Tier-2 / FAOSTAT-consistent)",
        "crosscheck_source": "GLEAM 3.0 South Asia (data/gleam_mms.csv; FAO GLEAM Ref Doc v1.0 T3.2-3.5)",
        "current": base, "gleam": gleam,
        "gleam_vs_current_direct_n2o_ratio": ratio,
        "faostat_manure_Mt_co2e": FAOSTAT_MANURE,
        "dairy_split_crosscheck": ("dairy_cattle_share=0.295 kept (FAOSTAT milk-animals/stock). GLEAM 3.0 "
                                   "publishes no comparable in-milk fraction -- it derives herd structure "
                                   "endogenously (SA fertility 75%%, replacement 21%%, calving 3.1yr) -- so "
                                   "the FAOSTAT value is retained as primary; enteric (151.5 Mt) unchanged."),
        "finding": ("GLEAM's dry-lot-heavy South-Asia split (56%% cattle dry lot, EF3=0.02) raises manure "
                    "direct N2O %.1fx (%.1f->%.1f Gg) and the manure category to %.1f Mt vs FAOSTAT %.1f. "
                    "This is a GLEAM-MMS-vs-IPCC-EF3 taxonomy mismatch, not a refinement: the current "
                    "FAOSTAT-consistent split stays primary; GLEAM surfaces MMS as a large hidden "
                    "uncertainty. No control total changes." % (ratio, base["direct_n2o_Gg"],
                    gleam["direct_n2o_Gg"], gleam["manure_total_Mt_co2e"], FAOSTAT_MANURE)),
        "adds_magnitude": False,
    }


def main():
    card = compute()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(card, f, indent=2)
    c, g = card["current"], card["gleam"]
    print("MMS cross-check -> outputs/eval/mms_sensitivity.json")
    print("  manure direct N2O: current %.1f Gg | GLEAM %.1f Gg (%.1fx)"
          % (c["direct_n2o_Gg"], g["direct_n2o_Gg"], card["gleam_vs_current_direct_n2o_ratio"]))
    print("  manure total: current %.1f Mt | GLEAM %.1f Mt | FAOSTAT %.1f Mt (current stays primary)"
          % (c["manure_total_Mt_co2e"], g["manure_total_Mt_co2e"], FAOSTAT_MANURE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
