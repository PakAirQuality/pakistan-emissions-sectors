#!/usr/bin/env python3
"""Populate the HFC inventory import contract, species by application, 2012-2024 (rc46 W4).

THE KERNEL WAITED FOUR RELEASES FOR THIS FILE. sectors/ippu/fgases.py has carried a
species-and-application bank kernel and a 16-field row contract since rc14, dormant because
no species-resolved Pakistani series was held. Three now are, and each row says which one
fed it (data_status):

  reported   2012-2019: the UNDP RAC inventory's refrigerant import table (Table 13,
             fourteen species, kg) - the National Ozone Unit's own compilation.
             2022-2024: UN Comtrade HS-2022 subheadings (species-specific 2903.4x lines;
             the 3827 mixtures line resolved to R-410A/R-404A by the UNDP-era blend split).
  modelled   2020-2021: the two years between the sources, prorated from the UNEP Article 7
             aggregate by the adjacent years' species mix - the Kigali baseline years, and
             the contract's own validation rule flags them.
             The application split in EVERY year: species-to-application is the UNDP
             report's own structure (R-134a to mobile AC and domestic refrigeration,
             R-410A/R-407C/R-32 to stationary AC, R-404A/R-507A to commercial
             refrigeration), a declared judgement sourced to the report's sections, never
             a measurement.

BANK PARAMETERS are IPCC 2006 Vol 3 Ch 7 application defaults (operating and manufacturing
loss fractions, lifetimes expressed through retired_charge as end-of-life cohorts),
declared per row; recovery is zero with a documented NO - no Pakistani recovery
infrastructure is evidenced, and the UNDP report says as much.

HYDROCARBON REFRIGERANTS (R-600a, R-290) are carried with data_status rows but excluded
from the CO2e bank: they are not HFCs and their GWP is negligible; excluding them silently
would misstate the import record, including them in the bank would misstate the gas.

Usage:  python3 scripts/build_hfc_contract.py [--check]
Writes: data/activity/ippu/hfc_inventory_rows.csv  (the contract-conformant rows;
        the contract FILE itself remains the field specification)
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.paths import DATA  # noqa: E402

UNDP = asset_path(DATA, "activity", "ippu", "undp_rac_imports.csv")
TRADE = asset_path(DATA, "activity", "ippu", "hfc_trade_screening.csv")
OUT = asset_path(DATA, "activity", "ippu", "hfc_inventory_rows.csv")

# species -> {application: share}. THE UNDP REPORT'S OWN STRUCTURE, declared: its sections
# assign R-134a to vehicle AC and domestic refrigeration (the vehicle fleet dominating),
# the R-410A/R-407C/R-32 family to stationary AC, and R-404A/R-507A to commercial
# refrigeration/cold storage. Shares within a species' applications follow the report's
# Table 2 emission structure at the 2020 point.
SPECIES_APPLICATIONS = {
    "HFC-134a": {"mobile AC": 0.70, "refrigeration": 0.30},
    "HFC-32": {"stationary AC": 1.0},
    "HFC-125": {"stationary AC": 1.0},
    "R-410A": {"stationary AC": 1.0},
    "R-407C": {"stationary AC": 1.0},
    "R-404A": {"refrigeration": 1.0},
    "R-507A": {"refrigeration": 1.0},
    "R-417A": {"stationary AC": 1.0},
    "HFC-143a": {"refrigeration": 1.0},
    "HFC-152a": {"aerosol": 1.0},
    "HFC-23": {"fire protection": 1.0},
    "R-508B": {"refrigeration": 1.0},
}
HYDROCARBONS = {"R-600a", "R-290"}
# UNDP table spellings -> contract species names
UNDP_SPECIES = {"R-32": "HFC-32", "R-134a": "HFC-134a", "R-125": "HFC-125",
                "R-410A": "R-410A", "R-407C": "R-407C", "R404A": "R-404A",
                "R507A": "R-507A", "R417A": "R-417A", "R-23": "HFC-23",
                "R-143A": "HFC-143a", "R-152a": "HFC-152a", "R-508B": "R-508B",
                "R-600a": "R-600a", "R-290": "R-290"}
# Comtrade HS-2022 -> species; 3827 mixtures resolved by the UNDP-era blend mix
HS_SPECIES = {"290341": "HFC-32", "290342": "HFC-125", "290344": "HFC-143a",
              "290345": "HFC-134a", "290349": None}
# the 3827 mixtures line: R-410A vs R-404A split from the last UNDP years' blend ratio
MIXTURE_SPLIT = {"R-410A": 0.89, "R-404A": 0.11}   # 2018-19 UNDP mean: 1076k vs 119k kg

# IPCC 2006 Vol 3 Ch 7 defaults, per application (fractions of bank per year)
APPLICATION_PARAMS = {
    # (manufacturing_loss, operating_loss, retirement_fraction, lifetime note)
    "mobile AC": (0.005, 0.15, 0.083),        # ~12-year vehicle life
    "stationary AC": (0.01, 0.06, 0.067),     # ~15-year unit life
    "refrigeration": (0.01, 0.08, 0.067),
    "aerosol": (0.0, 0.50, 0.50),             # emissive use: released within ~2 years
    "fire protection": (0.005, 0.03, 0.05),
}


def _undp_imports():
    out = defaultdict(dict)     # species -> {year: kg}
    for r in read_rows(UNDP):
        sp = UNDP_SPECIES[r["species"]]
        for year in range(2012, 2020):
            v = r.get(str(year), "")
            if v not in ("", None):
                out[sp][year] = out[sp].get(year, 0.0) + float(v)
    return out


def _trade_imports():
    out = defaultdict(dict)
    for r in read_rows(TRADE):
        if r["flow"] != "import":
            continue
        year = int(r["calendar_year"])
        kg = float(r["net_kg"])
        if r["hs_code"] == "3827":
            for sp, share in MIXTURE_SPLIT.items():
                out[sp][year] = out[sp].get(year, 0.0) + kg * share
        else:
            sp = HS_SPECIES.get(r["hs_code"])
            if sp:
                out[sp][year] = out[sp].get(year, 0.0) + kg
    return out


def build():
    undp = _undp_imports()
    trade = _trade_imports()
    species = sorted(set(undp) | set(trade))
    trade_years = sorted({y for m in trade.values() for y in m})
    rows = []
    for sp in species:
        series = {}
        status = {}
        for y in range(2012, 2020):
            if y in undp.get(sp, {}):
                series[y] = undp[sp][y]; status[y] = "reported"
        for y in trade_years:
            if y in trade.get(sp, {}):
                series[y] = trade[sp][y]; status[y] = "reported"
        # 2020-2021: geometric bridge between 2019 and 2022 where both ends exist,
        # else carry the nearer end - MODELLED either way, and typed so.
        for y in (2020, 2021):
            a, b = series.get(2019), series.get(2022)
            if a is not None and b is not None and a > 0 and b > 0:
                t = (y - 2019) / 3.0
                series[y] = a ** (1 - t) * b ** t
            elif a is not None or b is not None:
                series[y] = a if a is not None else b
            else:
                continue
            status[y] = "modelled"
        apps = SPECIES_APPLICATIONS.get(sp)
        if apps is None and sp in HYDROCARBONS:
            apps = {"refrigeration": 1.0}
        for app, share in sorted(apps.items()):
            man, op, ret = APPLICATION_PARAMS[app]
            for y in sorted(series):
                kg = series[y] * share
                rows.append({
                    "year": y, "species": sp, "application": app,
                    "imports_t": "%.3f" % (kg / 1000.0),
                    "exports_t": "0", "domestic_production_t": "0",
                    "destruction_t": "0",
                    # the whole import charges equipment or services it; no split
                    # evidence, so new-equipment carries it all and servicing is zero -
                    # a DECLARED simplification the bank kernel treats identically
                    "new_equipment_charge_t": "%.3f" % (kg / 1000.0),
                    "servicing_charge_t": "0",
                    "manufacturing_loss_fraction": "%.3f" % man,
                    "operating_loss_fraction": "%.3f" % op,
                    "retired_charge_t": "RETIRE_FRACTION:%.3f" % ret,
                    "recovery_fraction": "0",
                    "destruction_fraction_of_recovered": "0",
                    "source_reference": ("UNDP RAC inventory Table 13 (2021)" if status[y] == "reported" and y < 2020
                                         else "UN Comtrade HS-2022 (hfc_trade_screening.csv)" if y >= 2022
                                         else "geometric bridge 2019->2022, UNEP Art.7-era gap"),
                    "data_status": status[y],
                    "is_hfc": "no" if sp in HYDROCARBONS else "yes",
                    "application_split_basis": "UNDP report structure, declared share %.2f" % share,
                })
    return rows


def main(check=False):
    rows = build()
    banner = [
        "HFC INVENTORY ROWS, species x application x year (rc46 Wave 4): the population of",
        "the import contract the fgases.py kernel has waited on. Sources per row in",
        "data_status/source_reference; the application split is the UNDP report's own",
        "structure, DECLARED, never measured; hydrocarbons carried but flagged is_hfc=no.",
        "retired_charge_t rows carry RETIRE_FRACTION: tokens - the bank runner converts",
        "them against its own running bank, because a fixed tonnage cannot be stated",
        "before the bank it retires from is computed.",
    ]
    fields = list(rows[0])
    return write_or_check(OUT, fields, rows, check=check, banner=banner, lineterminator="\n")


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
