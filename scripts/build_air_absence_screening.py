#!/usr/bin/env python3
"""The air absence-screening ledger: what the panel's typed absences plausibly hold, per period
and pollutant, published BESIDE the covered panel and never inside it.

THE COMPLETENESS-MASS RULE, APPLIED TO AIR. The covered panel types power NE; this ledger prices
that absence as SCENARIO ENDS - power's controlled-case and uncontrolled screenings, the two ends
the grid fleet lies between given its control inventory is unknown. Scenario ends, NOT
mathematical bounds (AP-42 defaults are typical rates, not worst cases), and NEVER summed into
the covered panel - a panel total plus an uncontrolled end would be a number that is neither an
estimate nor a bound, which is the laundering this ledger exists to prevent. The acquisition
that would replace power's pair with an estimate is named per row (gap air-power-controlled:
NEPRA licensee environmental submissions, unpublished rather than unmeasured).

INDUSTRY SINCE rc58. Industry is no longer a screened absence: its combustion layer is a covered
estimate inside the panel (pkinv.sectors.industry.air_pollutants). What remains typed NE for
industry is read from the coverage matrix - the species no register class prices (NH3) - and
carries NO scenario number, only the reason and the gap: a ledger row for a cell that is E would
invite exactly the double count the rule forbids. The rc55-rc57 uncontrolled industry screening
file is retired; its rows were floors on three fuels and the estimate supersedes them.

Reads:  outputs/power_air_screening_fy2015_16_fy2023_24.csv (both scenarios, grid only)
        outputs/pakemis_air_coverage_matrix.csv (which industry cells are still NE, and why)
        data/data_gaps.csv (the acquisition that would close the power pair, so the reason
        the ledger publishes is the register's own words and not a second copy of them)
Writes: outputs/pakemis_air_absence_screening_by_year.csv
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows     # noqa: E402
from pkinv.paths import DATA, OUTPUTS    # noqa: E402

POWER_IN = asset_path(OUTPUTS, "power_air_screening_fy2015_16_fy2023_24.csv")
COVERAGE_IN = asset_path(OUTPUTS, "pakemis_air_coverage_matrix.csv")
GAPS_IN = asset_path(DATA, "data_gaps.csv")
OUT = asset_path(OUTPUTS, "pakemis_air_absence_screening_by_year.csv")

# the panel's core species; the ledger carries exactly these so its rows pair with
# the coverage matrix's cells
CORE7 = ("BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2")
FIELDS = ("period_id", "sector_id", "pollutant", "scenario_controlled_kt",
          "scenario_uncontrolled_kt", "controlled_absence_reason", "factor_basis",
          "gap_id")

POWER_GAP = "air-power-controlled"
UNSCREENED_REASON = "not in the screening's priced set (no held factor row)"


def _paired_reason():
    """Why a row with BOTH scenario ends still records an absence.

    THE FIELD WAS BLANK EXACTLY WHERE IT MATTERED MOST. Its old rule was "explain a MISSING
    scenario end", so a row that successfully priced a pair got an empty string - which is
    every power row for CO, NOx, PM2.5 and SO2, all nine periods, thirty-six rows, and
    precisely the four pollutants whose absence IS the control-device question. The engine
    serves this field in query_air's completeness block, so a reader asking for power SO2
    received two scenario numbers and a gap id with nothing saying in words what the gap was.
    A field named `controlled_absence_reason` should say why the controlled estimate is
    absent, and when both ends exist that reason is the strongest one available: neither end
    is the estimate.

    Built from data/data_gaps.csv rather than retyped, so the sentence cannot drift from the
    register that owns the acquisition.
    """
    row = next((r for r in read_rows(GAPS_IN) if r.get("gap_id") == POWER_GAP), None)
    if row is None:
        raise SystemExit("data_gaps.csv has no %s row, so the paired-absence reason cannot "
                         "be built from the register that owns it" % POWER_GAP)
    return ("both ends are priced and NEITHER IS THE ESTIMATE: %s is recorded NE because the "
            "grid fleet's control inventory is unpublished, so these two rows bracket the "
            "absence rather than reporting it. What would close it: %s (%s, held by %s)."
            % (row["category"], row["unblocks"], row["access"], row["holder"]))


def _sums(path):
    """{(period, scenario, pollutant): kt} over the priced rows."""
    out = collections.defaultdict(float)
    periods = set()
    for r in read_rows(path):
        if not r.get("emissions_kt") or not r["period_id"]:
            continue
        scen = r.get("scenario", "uncontrolled") or "uncontrolled"
        if scen == "typed_absence":
            continue
        out[(r["period_id"], scen, r["pollutant"])] += float(r["emissions_kt"])
        periods.add(r["period_id"])
    return out, sorted(periods)


REGISTER_MODULES = ("industry", "ippu", "fugitives")     # rc59: the source-class register's sectors


def _industry_absences():
    """{(period, sector, pollutant): (gap_id, note)} for the register-module cells the
    matrix types NE (industry NH3, fugitives NH3; ippu prices every core species)."""
    out = {}
    for r in read_rows(COVERAGE_IN):
        if r["sector_id"] in REGISTER_MODULES and r["state"] != "E":
            out[(r["period_id"], r["sector_id"], r["pollutant"])] = (r["gap_id"], r["note"])
    return out


def main():
    paired = _paired_reason()
    power, periods = _sums(POWER_IN)
    industry_ne = _industry_absences()
    rows = []
    for pid in periods:
        for pol in CORE7:
            un = power.get((pid, "uncontrolled", pol))
            co = power.get((pid, "controlled_case", pol))
            rows.append({
                "period_id": pid, "sector_id": "power", "pollutant": pol,
                "scenario_controlled_kt": "" if co is None else "%.4f" % co,
                "scenario_uncontrolled_kt": "" if un is None else "%.4f" % un,
                "controlled_absence_reason": (UNSCREENED_REASON if un is None
                                              else paired if co is not None
                                              else UNSCREENED_REASON),
                "factor_basis": ("" if un is None else
                                 "AP-42 held-table pair, GRID ONLY (captive generation is "
                                 "priced in the industry layer); see power_air_screening_"
                                 "fy2015_16_fy2023_24.csv per fuel and table"),
                "gap_id": POWER_GAP})
            for sector in REGISTER_MODULES:
                if (pid, sector, pol) not in industry_ne:
                    continue
                gap, note = industry_ne[(pid, sector, pol)]
                rows.append({
                    "period_id": pid, "sector_id": sector, "pollutant": pol,
                    "scenario_controlled_kt": "", "scenario_uncontrolled_kt": "",
                    "controlled_absence_reason": note,
                    "factor_basis": "no scenario end: the species is a typed absence of the "
                                    "covered %s layer, not a screened one" % sector,
                    "gap_id": gap})
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write(
            "# WHAT THE PANEL'S TYPED ABSENCES PLAUSIBLY HOLD, per period and species -\n"
            "# SCENARIO ENDS, NOT MATHEMATICAL BOUNDS, and NEVER summed into the covered\n"
            "# panel: a covered total plus an uncontrolled end is neither an estimate nor\n"
            "# a bound. Power's pair (controlled_case..uncontrolled, grid only) brackets a\n"
            "# fleet whose control inventory exists at NEPRA unpublished (gap air-power-\n"
            "# controlled). Industry (rc58), IPPU and fugitives (rc59) are COVERED estimates\n"
            "# from the source-class register; their rows here are the remaining typed\n"
            "# absences per species (no number, a reason and a gap).\n"
            "# Empty numeric cells are typed absences, never zeros.\n")
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    n_pairs = sum(1 for r in rows if r["scenario_controlled_kt"] and r["scenario_uncontrolled_kt"])
    print("air absence-screening ledger -> %s (%d rows, %d full pairs, %d register-module absences)"
          % (os.path.relpath(OUT), len(rows), n_pairs, len(industry_ne)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
