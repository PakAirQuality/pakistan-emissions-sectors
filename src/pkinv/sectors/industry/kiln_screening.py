"""Brick-kiln coal: a screening estimate at a declared prior vintage (rc13).

WHY THIS EXISTS. The 11,272 mapped kilns were the inventory's largest
geometry-held-no-control claimant for three releases: the solid-fuel ledger said
"no fuel, production or firing-cycle control is held, so no emissions estimate can
honestly be made yet." The rc13 audit found the control sitting unregistered in an
analysis folder: the Pakistan Energy Yearbook's Table 4.4 carries a NATIONAL
coal-to-brick-kiln series, FY2012-13..FY2022-23, now formalized at
data/activity/industry/brick_kiln_coal.csv. This module prices it.

WHAT THIS IS AND IS NOT. A SCREENING estimate that has been SUPERSEDED: since
the rc46 activation the reference 1A2 category BOOKS measured brick-kiln coal
(HDIP coal-by-consumer, 2.78 Mt in FY2023-24), so this FY2022-23-vintage
screening is a comparator - the record of what screened the category before the
measurement arrived, and a vintage-and-method cross-check against it. The
national configuration brick_kiln_coal_in_scope that once priced the inclusion
was RETIRED at rc47 Wave 0: adding this estimate to a reference that already
contains the measured series double-counts. The constants below are
DELIBERATELY NOT in data/emission_factors.csv: nothing here enters a component
row or the factor registry.

THE UNCERTAINTY, LED BY WHAT MATTERS. First, the VINTAGE: the series ends
FY2022-23 and this inventory reports FY2023-24 - the anchor is applied one year
outside its own period, declared, and the series swings THREEFOLD across the
decade (2.7 Mt FY2013 to 8.7 Mt FY2021 to 3.0 Mt FY2023), so a one-year offset
is not small. Second, the series' own status: the Yearbook footnotes state that
sectoral coal is mostly not directly metered - the Brick-Kiln row is the
Yearbook's OWN ESTIMATE. Only after those two come the factor CIs (NCV +/-21%,
the Table 2.3 defaults). No single +/- percentage is printed for the total;
the row notes carry the pieces.

AIR POLLUTANTS, TECHNOLOGY-BRACKETED. FCBK (bull's trench family, 9,959 of the
mapped kilns) and zig-zag (1,313) differ by nearly an order of magnitude on
particulates; the bracket prices both ends per tonne of coal rather than
asserting a fleet mix conversion efficiency nobody has measured. Mass in kt,
never CO2e, never in any GHG total - this is the industrial air layer's first
content, deliberately minimal.

Usage:  python3 -m pkinv.sectors.industry.kiln_screening
Writes: outputs/industry_brick_kiln_screening_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core.gwp import GWP
from pkinv.paths import DATA, OUTPUTS

SERIES = asset_path(DATA, "activity", "industry", "brick_kiln_coal.csv")

# --- combustion constants (IPCC 2006 Vol 2, Other Bituminous Coal - kilns burn
# mixed unwashed coal and OBC is this repo's declared honest bucket for it) ------
COAL_NCV_TJ_GG = 25.8        # Table 1.2 (95% CI +/-21%)
COAL_CO2_KG_TJ = 94600.0     # Table 2.3, manufacturing/construction
COAL_CH4_KG_TJ = 10.0        # Table 2.3
COAL_N2O_KG_TJ = 1.5         # Table 2.3

# --- the one held fuel-split evidence beyond the national row -------------------
# Kiln-census cross-section (single year, workbook not held; manuscript-cited at
# sources/Papers/Punjab Industry.pdf). Used by the allocation product, published
# here so the number has exactly one home.
PUNJAB_BRICKKILN_SHARE = 0.8668

# --- air-pollutant factors, kg per tonne of coal, technology-bracketed ----------
# Rajarathnam et al. / Weyant et al. / NAMaSTE, via the archived manuscript s5.1.
# LOW = improved technology (zig-zag/VSBK bound); HIGH = FCBTK bound.
AIR_KG_PER_T = {
    "NOx": (3.75, 3.75),
    "CO": (3.00, 3.00),
    "SO2": (19.0, 19.0),     # x S_coal; sulfur content UNPINNED - printed at S=1.0
                             # and flagged, because no Pakistani kiln-coal sulfur
                             # assay is held
    "PM2.5": (2.0, 13.2),
    "NH3": (0.0, 0.429),
}


def latest_row():
    # rc41: the series carries its banner ABOVE the header now (every reader in the tree
    # is comment-tolerant and strict); the header-first form this filtered is gone
    from pkinv.activity.store import read_rows
    rows = read_rows(SERIES)
    rows.sort(key=lambda r: int(r["fiscal_year"]))
    return rows[-1], rows


def screening(data=None):
    """Return (ghg_rows, air_rows, meta). Pure arithmetic on the held series."""
    latest, rows = latest_row()
    year = int(latest["fiscal_year"])
    coal_gg = float(latest["coal_tonnes"]) / 1000.0
    tj = coal_gg * COAL_NCV_TJ_GG
    co2_gg = tj * COAL_CO2_KG_TJ / 1e6
    ch4_gg = tj * COAL_CH4_KG_TJ / 1e6
    n2o_gg = tj * COAL_N2O_KG_TJ / 1e6
    ghg = [
        ("CO2", co2_gg, co2_gg / 1000.0),
        ("CH4", ch4_gg, ch4_gg * GWP["AR5"]["CH4_fossil"] / 1000.0),
        ("N2O", n2o_gg, n2o_gg * GWP["AR5"]["N2O"] / 1000.0),
    ]
    tonnes = float(latest["coal_tonnes"])
    air = [(p, tonnes * lo / 1e6, tonnes * hi / 1e6)
           for p, (lo, hi) in AIR_KG_PER_T.items()]
    swing = (min(float(r["coal_tonnes"]) for r in rows),
             max(float(r["coal_tonnes"]) for r in rows))
    meta = {"vintage_fy_end": year, "coal_tonnes": tonnes, "tj": tj,
            "series_min_t": swing[0], "series_max_t": swing[1]}
    return ghg, air, meta


def screening_mt(data=None):
    """The headline screening magnitude, Mt CO2e AR5 - what the configuration prices."""
    ghg, _air, _meta = screening()
    return sum(mt for _gas, _gg, mt in ghg)


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    ghg, air, meta = screening()
    total = sum(mt for _g, _gg, mt in ghg)
    vintage = "screening_vintage_fy%d_%02d" % (meta["vintage_fy_end"] - 1,
                                               meta["vintage_fy_end"] % 100)
    path = asset_path(OUTPUTS, "industry_brick_kiln_screening_2024.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_kind", "name", "gas_or_pollutant", "quantity", "unit",
                    "basis", "note"])
        w.writerow(["activity", "Brick-kiln coal (national)", "",
                    round(meta["coal_tonnes"]), "t coal", vintage,
                    "PEY Table 4.4, the Yearbook's OWN ESTIMATE (sectoral coal "
                    "mostly unmetered); the series swings %.1f-%.1f Mt across "
                    "FY2013-FY2023, which outranks every factor CI below"
                    % (meta["series_min_t"] / 1e6, meta["series_max_t"] / 1e6)])
        for gas, gg, mt in ghg:
            w.writerow(["ghg_screening", "Brick-kiln coal combustion", gas,
                        round(mt, 5), "Mt CO2e (AR5)", vintage,
                        "OBC defaults: NCV %.1f TJ/Gg (+/-21%%), EF Table 2.3; "
                        "SCREENING - outside every reference total, the 1A2 "
                        "category stays NE" % COAL_NCV_TJ_GG])
        w.writerow(["ghg_screening", "Brick-kiln coal combustion", "TOTAL",
                    round(total, 5), "Mt CO2e (AR5)", vintage,
                    "COMPARATOR since rc47 Wave 0: the reference books the "
                    "measured HDIP brick coal, and the configuration that once "
                    "priced this screening is retired as a double count"])
        for pollutant, lo, hi in air:
            note = ("technology bracket: improved (zig-zag/VSBK) low bound to "
                    "FCBTK high bound, kg/t coal; MASS ONLY, never CO2e")
            if pollutant == "SO2":
                note += "; printed at S_coal=1.0 - the sulfur content is UNPINNED"
            w.writerow(["air_screening", "Brick-kiln coal combustion", pollutant,
                        "%0.2f-%0.2f" % (lo, hi), "kt", vintage, note])
    print("brick-kiln screening -> %s" % os.path.basename(path))
    print("  %.0f t coal (FY%d-%02d vintage) -> %.2f Mt CO2e central; "
          "PM2.5 %.1f-%.1f kt (technology bracket)"
          % (meta["coal_tonnes"], meta["vintage_fy_end"] - 1,
             meta["vintage_fy_end"] % 100, total,
             air[3][1], air[3][2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
