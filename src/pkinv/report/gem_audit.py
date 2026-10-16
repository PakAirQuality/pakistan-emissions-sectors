"""The GEM asset-census cross-check: tracker units against the NEPRA-derived ledger.

WHY. The eighth review's asset slate asks whether the inventory's plant census is
complete. Global Energy Monitor's coal-plant tracker is an independent unit-level
register (CC BY 4.0, July 2026 edition, fetched by scripts/fetch_gem_trackers.py);
this module lines its operating Pakistani units up against the engine's per-plant
fuel ledger and says, per unit, whether the ledger knows the plant.

COMPARATOR ONLY. Nothing here enters any total, factor or allocation: the ledger's
coal is controlled by the NEPRA Table 3 national statistic regardless of how many
plants carry it, and a GEM unit the ledger lacks changes the census conversation,
not the arithmetic. The cement extract (data/activity/industry/gem_cement_pak.csv)
is deliberately NOT resolved here - IPPU entity resolution is a named deferral.

THE CORRESPONDENCE IS DECLARED, NOT FUZZY. GEM and NEPRA name the same plant
differently ("Sahiwal power station" vs "Huaneng Shandong Ruyi (Sahiwal Imported
Coal)"); a token matcher would silently mispair them, so the mapping is a
hand-curated table below and anything outside it stays honestly unmatched.

Usage:  python3 -m pkinv.report.gem_audit
Writes: outputs/power_gem_audit.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

GEM_COAL = asset_path(DATA, "activity", "power", "gem_coal_pak.csv")
LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")
OUT = asset_path(OUTPUTS, "power_gem_audit.csv")

# GEM plant name -> the NEPRA ledger's plant string. Every entry was checked by
# site and capacity, not by name similarity. "Hubco power station" in the COAL
# tracker is the 2x660 CPHGC plant at Hub (the legacy 1,292 MW Hubco RFO plant
# is outside a coal tracker by construction).
GEM_TO_LEDGER = {
    "Hubco power station": "China Power Hub",
    "Port Qasim EPC power station": "Port Qasim Electric Power",
    "Port Qasim Lucky power station": "Lucky Electric",
    "Sahiwal power station": "Huaneng Shandong Ruyi (Sahiwal Imported Coal)",
    "Thar Block I power station": "Thar Coal Block-I",
    "Thar Block II power station": "Engro Powergen Thar",
    "Thar Energy Limited power station": "Thar Energy",
    "ThalNova power station": "ThalNova",
    # rc68: the census finding of every release through rc67 - GEM's operating coal Unit 5 at
    # Jamshoro with no NEPRA coal account - closed when the FY2024-25 extension read NEPRA's
    # own account for the unit ("Jamshoro Coal Power Unit-1", 660 MW).
    "Jamshoro power station": "Jamshoro Coal Power Unit-1",
}

# GEM operating units that are industrial SELF-GENERATION (cement, chemical,
# fertilizer, sugar): NEPRA's per-plant tables are the licensed power sector, so
# their absence from the ledger is a boundary fact, not a census hole. Their
# coal, where it burns, belongs to the industry story - the same solid-fuel
# ledger the brick-kiln screening narrowed.
INDUSTRIAL_SELFGEN = (
    "Dera Ghazi Khan Cement power station",
    "Faisalabad Sitara Chemical power plant",
    "Fauji Fertilizer power station",
    "Hub Cement power station",
    "Maple Leaf power station",
    "Muzaffargarh sugar mill power station",
)

FIELDS = ("gem_plant", "gem_unit", "capacity_mw", "gem_status", "coal_type",
          "latitude", "longitude", "ledger_plant", "ledger_rows",
          "match_class", "note")


def _rows(path):
    return read_rows(path)


def build():
    gem = [r for r in _rows(GEM_COAL) if r["Status"] == "operating"]
    ledger = _rows(LEDGER)
    ledger_coal = {}
    for r in ledger:
        if r["fuel"].strip().lower() == "coal":
            ledger_coal.setdefault(r["plant"], []).append(r)

    def ledger_key(target):
        """The ledger plant string containing the mapped NEPRA name."""
        hits = [p for p in ledger_coal if target in p]
        return hits[0] if len(hits) == 1 else None

    out, matched_ledger = [], set()
    for r in sorted(gem, key=lambda r: (r["Plant name"], r["Unit name"])):
        plant, unit = r["Plant name"], r["Unit name"]
        row = {"gem_plant": plant, "gem_unit": unit,
               "capacity_mw": r["Capacity (MW)"], "gem_status": r["Status"],
               "coal_type": r["Coal type"], "latitude": r["Latitude"],
               "longitude": r["Longitude"], "ledger_plant": "",
               "ledger_rows": 0, "match_class": "", "note": ""}
        if plant in GEM_TO_LEDGER:
            key = ledger_key(GEM_TO_LEDGER[plant])
            if key:
                matched_ledger.add(key)
                row.update(ledger_plant=key, ledger_rows=len(ledger_coal[key]),
                           match_class="matched_grid_ledger",
                           note="declared correspondence; the ledger's fuel "
                                "years are NEPRA per-plant accounts")
            else:
                row.update(match_class="mapping_broken",
                           note="the declared NEPRA name no longer resolves "
                                "in the ledger - fix GEM_TO_LEDGER")
        elif plant in INDUSTRIAL_SELFGEN:
            row.update(match_class="industrial_selfgen",
                       note="self-generation outside NEPRA's per-plant tables "
                            "- a boundary fact; its coal belongs to the "
                            "industry solid-fuel ledger, not to a census hole")
        else:
            row.update(match_class="gem_only",
                       note="an operating GEM unit the NEPRA per-plant ledger "
                            "does not carry on coal - a census finding to "
                            "state, never a quantity to import")
        out.append(row)

    # The reverse direction: every ledger coal plant GEM does not cover.
    for key in sorted(ledger_coal):
        if key not in matched_ledger:
            out.append({"gem_plant": "", "gem_unit": "",
                        "capacity_mw": "", "gem_status": "", "coal_type": "",
                        "latitude": "", "longitude": "", "ledger_plant": key,
                        "ledger_rows": len(ledger_coal[key]),
                        "match_class": "ledger_only",
                        "note": "a NEPRA coal account no operating GEM unit "
                                "was mapped to - a census finding in the "
                                "other direction"})
    return out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    write_table(OUT, FIELDS, rows, banner=('# GEM coal tracker (July 2026) vs the NEPRA per-plant fuel ledger.', '# COMPARATOR ONLY: no total, factor or allocation reads this file.', '# Correspondence declared in pkinv/report/gem_audit.py, never fuzzy.',))
    by_class = {}
    for r in rows:
        by_class[r["match_class"]] = by_class.get(r["match_class"], 0) + 1
    print("GEM audit -> power_gem_audit.csv (%d rows): %s"
          % (len(rows), ", ".join("%s %d" % kv for kv in sorted(by_class.items()))))


if __name__ == "__main__":
    main()
