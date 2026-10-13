#!/usr/bin/env python3
"""The industry air layer against EDGAR v8.1, matched years - a comparison, never a fit (rc58 W3).

For each fiscal year FY2015-16..FY2021-22 the engine's covered industry total per species (the
panel's REF atoms, fossil fuels plus the cement kiln, captive included) is set beside EDGAR's
1.A.2 Manufacturing Industries and Construction at EDGAR's fiscal blend - half of each adjacent
calendar column, the convention the transport and boundary lanes already use. EDGAR ends in
2022, so FY2022-23 and FY2023-24 have no counterpart and are not compared (a row says so
rather than borrowing 2022). Two EDGAR columns are shown: fossil alone (the like-for-like
half) and fossil + biomass (EDGAR's industrial biomass is 5-6x its fossil PM2.5 for Pakistan,
which the engine types absent as bagasse - the reader sees both). The cement kiln's PM sits in
EDGAR's 2.A.1 rather than 1.A.2, so a third column adds 2.A.1 for the particulate species.

WHAT THE RATIO IS NOT. It is not a calibration target: no parameter, share or factor in the
registers is read back from this table, and tests/test_industry_air.py holds every register
byte-identical across a run of this script. It is evidence about where two compilations part -
EDGAR is IEA-balance-fed with global default factors; this layer is OGRA/OCAC/HDIP-fed with
source-class factors and Pakistani sulfur evidence.

Reads:  outputs/pakemis_air_annual_fy2015_16_fy2023_24.csv, data/activity/industry/edgar_pak_industry_ap_series.csv
Writes: outputs/pakemis_industry_air_edgar_comparison.csv
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows  # noqa: E402
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

PANEL = asset_path(OUTPUTS, "pakemis_air_annual_fy2015_16_fy2023_24.csv")
EDGAR = asset_path(DATA, "activity", "industry", "edgar_pak_industry_ap_series.csv")
OUT = asset_path(OUTPUTS, "pakemis_industry_air_edgar_comparison.csv")
SPECIES = ("NOx", "SO2", "CO", "NMVOC", "PM2.5", "BC", "NH3")
FIELDS = ("period_id", "fiscal_end_year", "species", "engine_industry_kt",
          "edgar_1a2_fossil_kt", "edgar_1a2_fossil_bio_kt", "edgar_1a2_fossil_plus_2a1_kt",
          "ratio_engine_over_edgar_fossil", "ratio_engine_over_edgar_fossil_bio",
          # rc59: the two other register modules against their EDGAR categories
          "engine_ippu_kt", "edgar_2b_2c_kt", "ratio_ippu_over_edgar",
          "engine_fugitives_kt", "edgar_1b2_kt", "ratio_fugitives_over_edgar",
          "edgar_basis", "reading")
HEADER = """\
# THE INDUSTRY AIR LAYER AGAINST EDGAR v8.1, MATCHED YEARS - a comparison of two compilations, never a
# calibration: nothing in the registers is read back from this table (tests hold them byte-identical).
# engine = the covered panel's industry atoms (fossil fuels, cement kiln, captive gas; REF configuration).
# EDGAR at its fiscal blend 0.5 x CY(Y-1) + 0.5 x CY(Y) for FYY-1/Y; fossil alone is the like-for-like
# half, fossil+bio adds EDGAR's industrial biomass (typed absent here as bagasse), +2.A.1 adds cement
# process particulate (which the engine's integrated kiln carries under industry). EDGAR ends 2022:
# FY2022-23 and FY2023-24 are NOT compared. scripts/build_industry_air_edgar_comparison.py
# rc59: the ippu atoms (ammonia, electric steel, soda ash) beside EDGAR's 2.B + 2.C (chemical and
# metal industry, all processes) and the fugitives atoms (segment NMVOC, refining, flaring) beside
# EDGAR's 1.B.2 (oil and gas fugitives) - the same blend, the same rule: compared, never fitted.
"""


def engine_totals(sector="industry"):
    out = defaultdict(float)
    for r in read_rows(PANEL):
        if r["sector_id"] == sector and r["configuration_id"] == "REF_2023_24":
            out[(int(r["fiscal_end_year"]), r["pollutant"])] += float(r["emissions_Gg"])
    return out


def _ratio(e, d):
    if e is None or not d:
        return ""
    return "%.3f" % (e / d)


def edgar():
    out = defaultdict(float)
    for r in read_rows(EDGAR):
        if r["emissions_Gg"] == "":
            continue
        out[(r["species"], r["ipcc_code_2006"], r["fossil_bio"], int(r["calendar_year"]))] = float(r["emissions_Gg"])
    return out


def blend(ed, species, fy_end, codes, bios):
    total = 0.0
    for cy, wgt in ((fy_end - 1, 0.5), (fy_end, 0.5)):
        for code in codes:
            for bio in bios:
                total += wgt * ed.get((species, code, bio, cy), 0.0)
    return total


def main():
    eng = engine_totals()
    ippu = engine_totals("ippu")
    fug = engine_totals("fugitives")
    ed = edgar()
    rows = []
    for fy in range(2016, 2025):
        pid = "FY%d-%02d" % (fy - 1, fy % 100)
        for sp in SPECIES:
            e = eng.get((fy, sp))
            ei, ef = ippu.get((fy, sp)), fug.get((fy, sp))
            row = {"period_id": pid, "fiscal_end_year": fy, "species": sp,
                   "engine_industry_kt": "" if e is None else "%.4f" % e,
                   "engine_ippu_kt": "" if ei is None else "%.4f" % ei,
                   "engine_fugitives_kt": "" if ef is None else "%.4f" % ef,
                   "edgar_basis": "EDGAR v8.1 IPCC 2006 sheet, Pakistan, fiscal blend of calendar %d and %d" % (fy - 1, fy)}
            if fy > 2022:
                row.update(edgar_1a2_fossil_kt="", edgar_1a2_fossil_bio_kt="", edgar_1a2_fossil_plus_2a1_kt="",
                           ratio_engine_over_edgar_fossil="", ratio_engine_over_edgar_fossil_bio="",
                           edgar_2b_2c_kt="", ratio_ippu_over_edgar="", edgar_1b2_kt="", ratio_fugitives_over_edgar="",
                           edgar_basis="EDGAR v8.1 ends in calendar 2022; no counterpart for this fiscal year",
                           reading="not compared (EDGAR has no 2023 column); the engine value stands alone")
                rows.append(row)
                continue
            f = blend(ed, sp, fy, ("1.A.2",), ("fossil",))
            fb = blend(ed, sp, fy, ("1.A.2",), ("fossil", "bio"))
            f2 = blend(ed, sp, fy, ("1.A.2", "2.A.1"), ("fossil",))
            d_ippu = blend(ed, sp, fy, ("2.B", "2.C"), ("fossil", "bio"))
            d_fug = blend(ed, sp, fy, ("1.B.2",), ("fossil", "bio"))
            row.update(edgar_1a2_fossil_kt="%.4f" % f, edgar_1a2_fossil_bio_kt="%.4f" % fb,
                       edgar_1a2_fossil_plus_2a1_kt="%.4f" % f2,
                       edgar_2b_2c_kt="%.4f" % d_ippu, ratio_ippu_over_edgar=_ratio(ei, d_ippu),
                       edgar_1b2_kt="%.4f" % d_fug, ratio_fugitives_over_edgar=_ratio(ef, d_fug))
            if e is None:
                row.update(ratio_engine_over_edgar_fossil="", ratio_engine_over_edgar_fossil_bio="",
                           reading="typed absent in the engine (%s); EDGAR's figure is shown for scale, not as a gap to fill" % sp)
            else:
                rf = e / f if f else float("nan")
                rfb = e / fb if fb else float("nan")
                row.update(ratio_engine_over_edgar_fossil="%.3f" % rf, ratio_engine_over_edgar_fossil_bio="%.3f" % rfb)
                if 0.5 <= rf <= 2.0:
                    reading = "within a factor of two of EDGAR's fossil 1.A.2"
                elif rf > 2.0:
                    reading = "above EDGAR's fossil 1.A.2 by more than a factor of two"
                else:
                    reading = "below EDGAR's fossil 1.A.2 by more than a factor of two"
                if sp == "SO2":
                    reading += "; the engine's SO2 is a sulfur balance on three as-fired Pakistani kiln-coal analyses (4.643 %S central, band 2.38-5.95, basis measured_avg since rc63; it read a 2.6-10.7 Punjab coalfield RESOURCE range until then), EDGAR's a global default"
                if sp == "PM2.5":
                    reading += "; EDGAR's industrial biomass PM2.5 (bio column) is typed absent here as bagasse"
                row["reading"] = reading
            rows.append(row)
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("industry air vs EDGAR -> %s (%d rows)" % (os.path.relpath(OUT), len(rows)))
    for r in rows:
        if r["fiscal_end_year"] == 2022 and r["ratio_engine_over_edgar_fossil"]:
            print("  FY2021-22 %-6s industry %9s / EDGAR 1.A.2 fossil %9s (%s)  ippu %8s / 2.B+2.C %8s (%s)  fugitives %8s / 1.B.2 %8s (%s)" %
                  (r["species"], r["engine_industry_kt"], r["edgar_1a2_fossil_kt"], r["ratio_engine_over_edgar_fossil"] or "-",
                   r["engine_ippu_kt"], r["edgar_2b_2c_kt"], r["ratio_ippu_over_edgar"] or "-",
                   r["engine_fugitives_kt"], r["edgar_1b2_kt"], r["ratio_fugitives_over_edgar"] or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
