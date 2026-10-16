"""Road exhaust PM2.5 and BC if the fleet's technology were what Pakistan's standards suggest.

WHY THIS EXISTS (rc69). Road exhaust PM2.5 is 0.23-0.33 times, and BC 0.16-0.23 times, the
matched HTAP v3.2 road sector. The review asked whether fleet, technology, factor definitions
or fuel applicability explain the gap. The engine applies the EMEP/EEA 2023 Tier 1 MEAN
factors, which the guidebook states represent a typical 2010 EU-27 fleet. Pakistan's new
vehicles met Euro II at most through the core period, and much of the fleet predates that.

This module recomputes road exhaust PM2.5 and BC with technology-specific factors from the
same chapter's Tier 2 tables, which give PM2.5 and fuel use per vehicle-km and f-BC by
technology (data/sectors/transport/activity/emep_tier2_road_pm_by_technology.csv,
transcribed from the held PDF with table and page). Each road class keeps its own fuel; only
the factor changes. There are two cases:
  euro_ii_fleet        every diesel and petrol class at its Euro II (Euro 2) factor
  conventional_fleet   every class at its pre-Euro ("Conventional"/PRE ECE) factor; 3-wheelers
                       as 2-stroke motorcycles, the technology of the older rickshaw fleet
CNG classes keep the central factor; the Tier 2 tables give none.

WHAT IT ESTABLISHES. Only how far technology alone moves the comparison. Neither case is a
fleet estimate, because no held source gives the fleet's composition by emission standard. The
central inventory is unchanged.

Usage:  python3 -m pkinv.report.road_technology_case [--check]
Writes: outputs/pakemis_road_technology_case.csv
"""
import argparse
import collections

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_road_technology_case.csv")
ATOMS = asset_path(OUTPUTS, "pakemis_air_atomic_annual.csv")
HTAP = asset_path(OUTPUTS, "pakemis_air_htap_species_comparison.csv")
TIER2 = asset_path(DATA, "sectors", "transport", "activity",
                   "emep_tier2_road_pm_by_technology.csv")
REFERENCE = "S_TAN"
CASES = ("euro_ii_fleet", "conventional_fleet")
FIELDS = ("period_id", "pollutant", "case", "central_Gg", "case_Gg", "case_over_central",
          "htap_Gg", "central_over_htap", "case_over_htap", "classes_changed", "note")


def _factors():
    """{(engine_class, fuel, case): (pm2.5 g per kg fuel, BC fraction of PM2.5)}."""
    out = {}
    for r in read_rows(TIER2):
        out[(r["engine_class"], r["fuel"], r["case"])] = (float(r["pm25_g_per_kg_fuel"]),
                                                          float(r["f_bc"]))
    return out


def _class(subitem):
    # "Road transport HDV diesel exhaust ..." -> ("HDV", "Diesel")
    words = subitem.split()
    return words[2], words[3].capitalize()


def build():
    factors = _factors()
    fuel = collections.defaultdict(float)
    central = collections.defaultdict(float)
    for r in read_rows(ATOMS):
        if (r["configuration_id"] != REFERENCE or r["sector_id"] != "transport"
                or r["process"] != "exhaust" or r["pollutant"] not in ("PM2.5", "BC")):
            continue
        cls, fl = _class(r["subitem"])
        central[(r["period_id"], r["pollutant"], cls, fl)] += float(r["emissions_Gg"])
        if r["pollutant"] == "PM2.5":
            fuel[(r["period_id"], cls, fl)] = float(r["activity_value"])
    htap = {(r["period_id"], r["pollutant"]): float(r["htap_Gg"])
            for r in read_rows(HTAP) if r["configuration_id"] == REFERENCE
            and r["comparison_group"] == "road_exhaust" and r["htap_Gg"]}
    periods = sorted({k[0] for k in fuel})
    rows = []
    for period in periods:
        for pol in ("PM2.5", "BC"):
            base = sum(v for k, v in central.items() if k[0] == period and k[1] == pol)
            for case in CASES:
                total, changed = 0.0, []
                for (p, cls, fl), kt in sorted(fuel.items()):
                    if p != period:
                        continue
                    f = factors.get((cls, fl, case))
                    if f is None:                       # CNG and anything without a Tier 2 row
                        total += central.get((period, pol, cls, fl), 0.0)
                        continue
                    pm = kt * f[0] / 1000.0             # kt fuel x g/kg = t; /1000 = Gg
                    total += pm if pol == "PM2.5" else pm * f[1]
                    changed.append("%s %s" % (cls, fl.lower()))
                h = htap.get((period, pol))
                rows.append({"period_id": period, "pollutant": pol, "case": case,
                             "central_Gg": round(base, 6), "case_Gg": round(total, 6),
                             "case_over_central": round(total / base, 4) if base else "",
                             "htap_Gg": round(h, 6) if h else "",
                             "central_over_htap": round(base / h, 4) if h else "",
                             "case_over_htap": round(total / h, 4) if h else "",
                             "classes_changed": "; ".join(changed),
                             "note": "" if h else "no matched HTAP year (HTAP v3.2 ends with FY2019-20)"})
    return rows


BANNER = [
    "ROAD EXHAUST PM2.5 AND BC UNDER TECHNOLOGY-SPECIFIC TIER 2 FACTORS (rc69): the central",
    "Tier 1 means describe a 2010 EU-27 fleet. The same fuel per class is recomputed with every",
    "class at its Euro II factor and at its pre-Euro factor (EMEP/EEA 2023 Tier 2 tables, held",
    "chapter, data/sectors/transport/activity/emep_tier2_road_pm_by_technology.csv). The cases",
    "test how far technology alone moves the HTAP comparison; neither is a fleet estimate, and",
    "the central inventory is unchanged. Producer: pkinv.report.road_technology_case.",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return write_or_check(OUT, FIELDS, build(), check=args.check, banner=BANNER)


if __name__ == "__main__":
    raise SystemExit(main())
