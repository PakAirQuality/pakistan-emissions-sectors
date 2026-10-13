"""Climate TRACE, plant by plant - the 56 Mt coal anomaly resolved into its structure.

THE BENCHMARK AND ITS PROBLEM. Climate TRACE reports 56.19 Mt CO2e for Pakistani assets
it labels 'coal' - 2,431 g/kWh on its own activity figures, against a physical ceiling
near 1,100 for coal combustion. This inventory's coal is near 32 Mt, and the gap has been
regression-tested as a total since the benchmark entered the repo. What the total could
not show is WHERE the anomaly lives, and the per-asset file has been sitting unread in
sources/ the whole time.

WHAT READING IT PER PLANT SHOWS. Three structural findings, each carried as a flag column
rather than prose only:

  IMPUTATION. Three pairs of assets report IDENTICAL activity and emissions to the MWh:
  Balloki/Bhikki/HBS (three distinct combined cycles, one number three times), ThalNova
  with Thar Energy, and Lucky with Thar Block II. Model output, not measurement, and the
  duplicated values sit exactly where the coal anomaly is largest.

  LABEL, NOT PLANT. The 2,431 g/kWh intensity attaches to everything TRACE types 'coal' -
  including FFBL's and Pakistan Steel's captive units, which are not grid plants at all -
  so the anomaly tracks the label's implied factor, not any particular plant's operation.
  Consistent with the standing hypothesis (upstream Thar mine methane folded into the
  plant rows, or a modelling artefact), and inconsistent with missing combustion.

  MISASSIGNMENT. TRACE carries Hubco as a coal asset alongside a separate 'Hub power
  plant' oil asset (the plant burned zero fuel in FY2023-24 per the ledger), and two
  'Dera Ghazi Khan Cement' rows 570 km apart. The file also carries NO year column at
  all, so every comparison here is TRACE's undated asset values against this inventory's
  FY2023-24 - a vintage mismatch that bounds rather than tests.

ENGINE SIDE. Per-plant CO2 is the point-source register's energy (implied-CV coal, exact
MMBTU gas, declared-HHV volumes) times the origin's Table 2.2 factor - the same numbers
the provincial split rides, so the benchmark and the geography cannot drift apart.

DIAGNOSTIC ONLY; the emissions path never imports it. The hardcoded 56.19 in the old
benchmark test is replaced by a sum read from the file itself, so the CSV, the README's
table and the test can no longer drift apart silently.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.sectors.power import plant_ledger, point_sources
from pkinv.activity.store import read_rows

TRACE_SOURCE = asset_path(os.path.dirname(DATA), "sources", "Power Plants",
                            "climatetrace_power_assets_PAK.csv")
# rc41: the engine reads the CONSUMED DERIVATIVE - the document's 72 rows, every
# column, under a provenance banner (scripts/ingest_climatetrace_power.py,
# data/consumed_derivatives.csv) - so a tree that registers the document without
# holding it builds the same diagnostic.
TRACE_CSV = asset_path(DATA, "activity", "power", "climatetrace_power_assets_pak.csv")

# TRACE asset name -> ledger plant. Coal assets (the finding) plus the grid gas/oil
# assets large enough to matter; captive/industrial assets are flagged, not joined.
TRACE_ALIAS = {
    "Thar Block I power station": "Thar Coal Block-I",
    "Sahiwal power station": "Huaneng Shandong Ruyi (Sahiwal Imported Coal)",
    "Port Qasim EPC power station": "Port Qasim Electric Power",
    "Port Qasim Lucky power station": "Lucky Electric",
    "Thar Block II power station": "Engro Powergen Thar",
    "ThalNova power station": "ThalNova",
    "Thar Energy Limited power station": "Thar Energy",
    "Hubco power station": "Hub",             # typed coal by TRACE; an RFO plant
    "Hub power plant": "Hub",
    "Balloki power station": "NPPMCL (Balloki)",
    "Bhikki power station": "QATPL (Bhikki)",
    "Haveli Bahadur Shah (HBS) power station": "NPPMCL (HBS)",
    "Trimmu power station": "Punjab Thermal",
    "Uch power station": "Uch",
}

# Non-grid assets TRACE types 'coal': the label's implied factor, not grid combustion.
NON_GRID_COAL = {"Fauji Fertilizer power station", "PSM WORKS",
                 "Muzaffargarh sugar mill power station",
                 "Dera Ghazi Khan Cement power station", "Maple Leaf power station",
                 "Faisalabad Sitara Chemical power plant", "Sheikhupura power station"}

CO2_KG_PER_TJ = {("Coal", "Thar lignite"): 101000.0,
                 ("Coal", "imported"): 94600.0,
                 # Lucky's origin is officially unstated; the blend factor, though its
                 # implied CV reads lignite (Section impliedcv).
                 ("Coal", "unknown"): 99656.0}
FUEL_CO2 = {"Gas": 56100.0, "RLNG": 56100.0, "RFO": 77400.0, "HSD": 74100.0}


def trace_rows(path=TRACE_CSV):
    return read_rows(path)


def coal_label_total_Mt(path=TRACE_CSV):
    """The benchmark total, read from the file rather than hardcoded."""
    return sum(float(r["co2e_t"]) for r in trace_rows(path)
               if r["asset_type"] == "coal") / 1e6


def _engine_plant_co2(data):
    """{ledger plant: engine Mt CO2, FY2023-24} from the point-source register."""
    origin = {r["plant"]: r["fuel_origin"] for r in plant_ledger.rows(data.year)
              if r["fuel"] == "Coal"}
    led = {}
    for r in point_sources.rows(data):
        if r["fuel"] == "Coal":
            ef = CO2_KG_PER_TJ[("Coal", origin.get(r["plant"], "unknown"))]
        else:
            ef = FUEL_CO2[r["fuel"]]
        led[r["plant"]] = led.get(r["plant"], 0.0) + r["energy_TJ"] * ef / 1e9
    return led


def comparison(data):
    """One row per TRACE asset: its values, its flags, and the engine figure beside it."""
    engine_co2 = _engine_plant_co2(data)
    by_value = {}
    for r in trace_rows():
        key = (r["activity_MWh"], r["co2e_t"])
        by_value.setdefault(key, []).append(r["name"])
    out = []
    for r in trace_rows():
        mwh, co2t = float(r["activity_MWh"]), float(r["co2e_t"])
        flags = []
        twins = [n for n in by_value[(r["activity_MWh"], r["co2e_t"])] if n != r["name"]]
        if twins and co2t > 0:
            flags.append("identical values to: %s (imputation signature)"
                         % "; ".join(twins))
        if r["name"] in NON_GRID_COAL:
            flags.append("not a grid plant; the coal label's factor, not 1A1a combustion")
        if r["name"] == "Hubco power station":
            flags.append("typed coal; the plant is RFO and burned zero fuel in FY2023-24")
        ledger = TRACE_ALIAS.get(r["name"], "")
        eng = engine_co2.get(ledger)
        out.append({"trace_name": r["name"], "asset_type": r["asset_type"],
                    "activity_MWh": mwh, "trace_co2e_t": co2t,
                    "trace_g_per_kwh": co2t * 1e6 / mwh / 1e3 if mwh else "",
                    "ledger_plant": ledger,
                    "engine_co2_Mt_fy2023": round(eng, 3) if eng is not None else "",
                    "trace_over_engine": round(co2t / 1e6 / eng, 2)
                    if (eng and eng > 0.01) else "",
                    "flags": "; ".join(flags)})
    return out
