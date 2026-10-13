"""The species-resolved HFC bank: the kernel run over the populated import contract.

Moved here from the Wave 4 script so the ippu SECTOR owns the computation - the screening
file's configuration row and the per-stratum product must come from one arithmetic, and a
sector module importing from scripts/ would be the dependency arrow pointing backwards.
scripts/run_hfc_bank.py remains as the thin hand-run entry point.

2.F REMAINS OUTSIDE EVERY TOTAL: this prices the configuration lane only, superseding the
rc30 one-stratum bounded bank; the activation judgement is the rc47 review's (Rule 3).
Blends are priced at their published component shares - quoting a blend at one component's
GWP is the 17-percent class of error the nitric-acid CER conversion documents.
"""
import csv
import os
import sys
from collections import defaultdict

from pkinv.core.gwp import GWP
from pkinv.activity.store import read_rows
from pkinv.core.io import write_or_check
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.ippu.fgases import run_bank
from pkinv.assets import asset_path

ROWS = asset_path(DATA, "activity", "ippu", "hfc_inventory_rows.csv")
OUT = asset_path(OUTPUTS, "ippu_hfc_species_bank.csv")

# Blend compositions by mass, from ASHRAE designations (published, fixed by definition)
BLENDS = {
    "R-410A": {"HFC-32": 0.50, "HFC-125": 0.50},
    "R-404A": {"HFC-125": 0.44, "HFC-143a": 0.52, "HFC-134a": 0.04},
    "R-407C": {"HFC-32": 0.23, "HFC-125": 0.25, "HFC-134a": 0.52},
    "R-507A": {"HFC-125": 0.50, "HFC-143a": 0.50},
    "R-417A": {"HFC-125": 0.466, "HFC-134a": 0.500},   # + 3.4% n-butane, ~zero GWP
    "R-508B": {"HFC-23": 0.46},                        # + 54% PFC-116; HFC share only
}


def gwp_ar5(species):
    if species in GWP["AR5"]:
        return GWP["AR5"][species]
    if species in BLENDS:
        return sum(GWP["AR5"][c] * share for c, share in BLENDS[species].items())
    return 0.0    # hydrocarbons: negligible, and flagged is_hfc=no upstream


def build():
    by_stratum = defaultdict(list)
    for r in read_rows(ROWS):
        by_stratum[(r["species"], r["application"])].append(r)
    out = []
    for (species, application), rows in sorted(by_stratum.items()):
        if rows[0].get("is_hfc") == "no":
            continue
        gwp = gwp_ar5(species)
        # resolve RETIRE_FRACTION against the running bank, one pass in year order
        bank = 0.0
        resolved = []
        for r in sorted(rows, key=lambda x: int(x["year"])):
            r = dict(r)
            frac = float(r["retired_charge_t"].split(":", 1)[1])
            r["retired_charge_t"] = "%.6f" % (bank * frac)
            r["supplied_charge_t"] = float(r["new_equipment_charge_t"]) + float(r["servicing_charge_t"])
            resolved.append(r)
            # advance a shadow bank with the same arithmetic the kernel applies
            supplied = r["supplied_charge_t"] * (1.0 - float(r["manufacturing_loss_fraction"]))
            bank = (bank + supplied) * (1.0 - float(r["operating_loss_fraction"])) - float(r["retired_charge_t"])
            bank = max(bank, 0.0)
        ledgers, _components = run_bank(species, application, resolved)
        for led in ledgers:
            out.append({
                "year": led["year"], "species": species, "application": application,
                "gwp_ar5": "%.1f" % gwp,
                "bank_end_t": "%.3f" % led["bank_end_t"],
                "emissions_t": "%.3f" % led["total_emissions_t"],
                "emissions_Mt_co2e_AR5": "%.6f" % (led["total_emissions_t"] * gwp / 1e6),
                "data_status": next(r["data_status"] for r in resolved
                                    if int(r["year"]) == led["year"]),
            })
    return out


def main():
    rows = build()
    by_year = defaultdict(float)
    for r in rows:
        by_year[r["year"]] += float(r["emissions_Mt_co2e_AR5"])
    banner = [
        "SPECIES-RESOLVED HFC BANK (rc46 Wave 4): per (species, application, year) bank and",
        "emissions from the fgases.py kernel over the populated import contract. Supersedes",
        "the rc30 one-stratum bounded bank IN THE CONFIGURATION LANE ONLY - 2.F contributes",
        "zero to every national total pending the rc47 activation review (Rule 3).",
        "Latest-year total: %.3f Mt CO2e AR5 (%d)." % (
            by_year[max(by_year)], max(by_year)),
    ]
    write_or_check(OUT, list(rows[0]), rows, banner=banner, lineterminator="\n")
    for y in sorted(by_year):
        print("  %s  %.4f Mt CO2e AR5" % (y, by_year[y]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
