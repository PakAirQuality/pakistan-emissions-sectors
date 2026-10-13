"""THE OLD-TO-NEW BRIDGE for the power SO2 admission: what moved, from where, and what is left.

A coverage repair changes a published series without any input changing, which is the kind of
edit a reader has no way to audit from the series alone. Nine periods of power SO2 that read
`NE` now carry a number, the national SO2 total steps up by that number, and the power screening
that used to bracket the whole oil fleet now brackets only what is left of it. This table is the
account of that, one row per fiscal year, so the step is attributable rather than merely visible.

WHAT EACH COLUMN ANSWERS:

  panel_so2_before_kt      the air panel's SO2 with no power atoms - the released series
  increment_*              the admitted mass, split by the equipment class that priced it, so a
                           reader can see that half of it rests on a boiler factor and half on
                           the complete-conversion sections for engines and turbines
  panel_so2_after_kt       the series this release publishes
  remainder_scenario_lo/hi the narrowed screening: oil and diesel SO2 on the fuel that is NOT
                           admitted, plus coal and gas, at both scenario ends. It is smaller
                           than it was, and it is still a scenario - it does not enter the panel
  admitted_share_of_fuel   how much of the national CPPA-side oil the admission covers, which is
                           the honest measure of how far this repair actually reaches

WHAT THE STEP IS NOT. It is not a correction to Lahore's SO2 trend, and it makes the national
decline STEEPER rather than shallower - furnace-oil generation collapsed over the panel, so the
mass admitted to FY2015-16 is far larger than the mass admitted to FY2023-24. The brick-coal
residual, the sulfur transition and the borrowed spatial allocations are untouched and remain
the principal repair.

Usage:  python3 scripts/build_power_admission_bridge.py [--check]
Writes: outputs/pakemis_air_power_admission_bridge.csv
"""
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check                      # noqa: E402
from pkinv.report import air_annual                                      # noqa: E402

ADMISSION = asset_path(ROOT, "data", "activity", "power", "power_so2_admission.csv")
PANEL = asset_path(ROOT, "outputs", "pakemis_air_annual_fy2015_16_fy2023_24.csv")
SCREENING = asset_path(ROOT, "outputs",
                         "power_air_screening_fy2015_16_fy2023_24.csv")
OUT = asset_path(ROOT, "outputs", "pakemis_air_power_admission_bridge.csv")
PERIODS = tuple("FY%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024))

FIELDS = ("period_id", "fiscal_end_year", "panel_so2_before_kt",
          "increment_rfo_boiler_kt", "increment_rfo_engine_kt", "increment_rfo_turbine_kt",
          "increment_hsd_turbine_kt", "increment_total_kt", "panel_so2_after_kt",
          "increment_pct_of_panel", "remainder_scenario_lo_kt", "remainder_scenario_hi_kt",
          "admitted_cppa_rfo_kt", "national_cppa_rfo_kt", "admitted_share_of_cppa_rfo",
          "stations_admitted", "stations_scenario_only", "basis")

CLASS_OF = {("RFO", "oil_fired_boiler"): "increment_rfo_boiler_kt",
            ("RFO", "reciprocating_engine"): "increment_rfo_engine_kt",
            ("RFO", "gas_turbine"): "increment_rfo_turbine_kt",
            ("HSD", "gas_turbine"): "increment_hsd_turbine_kt"}


def build():
    admission = read_rows(ADMISSION)
    panel = read_rows(PANEL)
    screening = read_rows(SCREENING)

    # The panel ships Gg and this bridge reports kt; they are the same unit and the column
    # name is the only thing that differs. ONE CONFIGURATION ONLY - the air panel's reference -
    # or every period would be counted as many times as there are configurations.
    # REF_2023_24 is the reference; L_HERD1624 differs only in sectors this change does not
    # touch, so the step is identical in both and reporting one keeps the table readable.
    configuration = "REF_2023_24"
    after = defaultdict(float)
    power_after = defaultdict(float)
    for r in panel:
        if r.get("pollutant") != "SO2" or r["configuration_id"] != configuration:
            continue
        after[r["period_id"]] += float(r["emissions_Gg"] or 0)
        if r.get("sector_id") == "power":
            power_after[r["period_id"]] += float(r["emissions_Gg"] or 0)

    scen = defaultdict(lambda: defaultdict(float))
    for r in screening:
        if r.get("pollutant") == "SO2":
            scen[r["period_id"]][r["scenario"]] += float(r["emissions_kt"] or 0)

    rows = []
    for period in PERIODS:
        fy_end = int(period[2:6]) + 1
        row = {f: "" for f in FIELDS}
        row["period_id"], row["fiscal_end_year"] = period, fy_end

        increments = defaultdict(float)
        admitted_cppa = 0.0
        stations_in, stations_out = set(), set()
        for r in admission:
            if r["period_id"] != period:
                continue
            if r["disposition"] != "provisional_estimate":
                stations_out.add(r["plant"])
                continue
            stations_in.add(r["plant"])
            increments[CLASS_OF[(r["fuel"], r["equipment_class"])]] += float(r["so2_Gg"])
            if r["fuel"] == "RFO" and r["system"] != "K-Electric":
                admitted_cppa += float(r["fuel_mass_kt"])

        total = sum(increments.values())
        for key in CLASS_OF.values():
            row[key] = round(increments.get(key, 0.0), 6)
        row["increment_total_kt"] = round(total, 6)
        row["panel_so2_after_kt"] = round(after[period], 6)
        row["panel_so2_before_kt"] = round(after[period] - power_after[period], 6)
        row["increment_pct_of_panel"] = (round(100.0 * total / after[period], 3)
                                         if after[period] else "")
        row["remainder_scenario_lo_kt"] = round(min(scen[period].values()), 6) if scen[period] else ""
        row["remainder_scenario_hi_kt"] = round(max(scen[period].values()), 6) if scen[period] else ""

        fraction, why = air_annual.admitted_remainder_fraction(fy_end, "Furnace Oil")
        national = admitted_cppa / (1.0 - fraction) if fraction < 1.0 else 0.0
        row["admitted_cppa_rfo_kt"] = round(admitted_cppa, 3)
        row["national_cppa_rfo_kt"] = round(national, 3)
        row["admitted_share_of_cppa_rfo"] = round(admitted_cppa / national, 4) if national else ""
        row["stations_admitted"] = len(stations_in)
        row["stations_scenario_only"] = len(stations_out - stations_in)
        row["basis"] = (
            "the panel-after figure is this release's own pakemis_air_by_year.csv; the "
            "before figure is it less the power atoms, which is the series as it stood while "
            "power SO2 was typed NE. The increment is the sum of the admitted rows of "
            "data/activity/power/power_so2_admission.csv and equals the difference by "
            "construction. The remainder scenario is the NARROWED power screening - oil and "
            "diesel on unadmitted fuel, plus coal and gas - at its two ends, and it is not "
            "part of any total.")
        rows.append(row)
    return rows


def main():
    rows = build()
    # LF, like every other air product in this family (tests/test_csv_terminators.py
    # freezes that set); write_or_check defaults to CRLF for the older tables.
    write_or_check(OUT, FIELDS, rows, check="--check" in sys.argv,
                   lineterminator="\n")
    print("%s: %d periods" % (os.path.relpath(OUT, ROOT), len(rows)))
    print("   %-10s %10s %10s %10s %9s  %s" % ("period", "before", "increment", "after",
                                               "step %", "remainder scenario"))
    for r in rows:
        print("   %-10s %10.3f %10.3f %10.3f %8s%%  %.1f - %.1f"
              % (r["period_id"], r["panel_so2_before_kt"], r["increment_total_kt"],
                 r["panel_so2_after_kt"], r["increment_pct_of_panel"],
                 r["remainder_scenario_lo_kt"], r["remainder_scenario_hi_kt"]))


if __name__ == "__main__":
    main()
