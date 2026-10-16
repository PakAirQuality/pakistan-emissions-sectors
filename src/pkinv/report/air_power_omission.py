"""How much of each pollutant the covered national total leaves out at power stacks, year by year.

WHY THIS EXISTS (rc69). Coal-fired power generation grew from almost nothing in FY2015-16 to
the largest single source of thermal generation, and its pollutants are outside the central
product: public plant evidence gives design values, not annual control operation
(air-power-controlled). The screening pair, an uncontrolled case and a design-controlled
case, is published, but only per fuel and per table. The review asked for the consequence of
the omission to be carried into every relevant total and trend.

The screening pair is never added to a covered total, because a covered total plus a
screening case is neither an estimate nor a bound. What this module carries is the omission
itself:
- for each period and species, the screened power-stack mass the covered panel does NOT
  contain, as a pair, of which coal;
- that mass as a share of the covered national total;
- how the share moves between FY2015-16 and the latest year.

A covered trend can then be read with the size of what it leaves out beside it. For SO2 the
covered panel admits furnace oil and diesel, so only the other fuels count as omitted. For
every other species the power stack is wholly outside the panel.

Usage:  python3 -m pkinv.report.air_power_omission [--check]
Writes: outputs/pakemis_air_power_omission.csv
"""
import argparse
import collections

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_air_power_omission.csv")
SCREENING = asset_path(OUTPUTS, "power_air_screening_fy2015_16_fy2024_25.csv")
ANNUAL = asset_path(OUTPUTS, "pakemis_air_annual_fy2015_16_fy2024_25.csv")
COVERAGE = asset_path(OUTPUTS, "pakemis_air_coverage_matrix.csv")
REFERENCE = "S_TAN"
FIRST = "FY2015-16"
# fuels whose SO2 the covered panel already holds (Table 2: power SO2 covers oil and diesel)
COVERED_SO2_FUELS = ("Furnace Oil", "Diesel Oil")
SPECIES = {"PM2.5": "PM2.5", "NOx": "NOx", "SO2": "SO2", "CO": "CO"}
FIELDS = ("period_id", "pollutant", "covered_national_Gg", "covered_power_state",
          "omitted_power_controlled_Gg", "omitted_power_uncontrolled_Gg",
          "omitted_coal_controlled_Gg", "omitted_coal_uncontrolled_Gg",
          "omitted_controlled_share_of_covered_pct", "omitted_uncontrolled_share_of_covered_pct",
          "omitted_fuels", "note")


def build():
    covered = collections.defaultdict(float)
    for r in read_rows(ANNUAL):
        if r["configuration_id"] == REFERENCE:
            covered[(r["period_id"], r["pollutant"])] += float(r["emissions_Gg"] or 0)
    state = {(r["period_id"], r["pollutant"]): r["state"] for r in read_rows(COVERAGE)
             if r["sector_id"] == "power"}
    omitted = collections.defaultdict(float)
    fuels = collections.defaultdict(set)
    for r in read_rows(SCREENING):
        pol = SPECIES.get(r["pollutant"])
        if pol is None:
            continue
        if pol == "SO2" and r["fuel"] in COVERED_SO2_FUELS:
            continue
        case = "controlled" if r["scenario"] == "controlled_case" else "uncontrolled"
        mass = float(r["emissions_kt"] or 0)
        omitted[(r["period_id"], pol, case, "all")] += mass
        if r["fuel"] == "Coal":
            omitted[(r["period_id"], pol, case, "coal")] += mass
        fuels[(r["period_id"], pol)].add(r["fuel"])
    rows = []
    for (period, pol) in sorted(fuels):
        total = covered[(period, pol)]
        c = omitted[(period, pol, "controlled", "all")]
        u = omitted[(period, pol, "uncontrolled", "all")]
        rows.append({
            "period_id": period, "pollutant": pol, "covered_national_Gg": round(total, 6),
            "covered_power_state": state.get((period, pol), ""),
            "omitted_power_controlled_Gg": round(c, 6),
            "omitted_power_uncontrolled_Gg": round(u, 6),
            "omitted_coal_controlled_Gg": round(omitted[(period, pol, "controlled", "coal")], 6),
            "omitted_coal_uncontrolled_Gg": round(omitted[(period, pol, "uncontrolled", "coal")], 6),
            "omitted_controlled_share_of_covered_pct": round(100 * c / total, 2) if total else "",
            "omitted_uncontrolled_share_of_covered_pct": round(100 * u / total, 2) if total else "",
            "omitted_fuels": ";".join(sorted(fuels[(period, pol)])),
            "note": ""})
    return rows


BANNER = [
    "WHAT THE COVERED NATIONAL TOTAL LEAVES OUT AT POWER STACKS, per period and species (rc69):",
    "the screened power-stack pair (design-controlled and uncontrolled AP-42 cases, grid only),",
    "restricted to the fuels the covered panel does not hold (for SO2, everything but furnace",
    "oil and diesel), of which coal, and as a share of the covered national total. The pair is",
    "never added to a total. Producer: pkinv.report.air_power_omission.",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return write_or_check(OUT, FIELDS, build(), check=args.check, banner=BANNER)


if __name__ == "__main__":
    raise SystemExit(main())
