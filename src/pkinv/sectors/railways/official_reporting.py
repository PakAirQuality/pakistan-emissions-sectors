"""Cell-audited extraction of Pakistan's UNFCCC CRT for railways (1.A.3.c), plus the
official benchmark register.

THE FINDING, READ OFF THE FILING'S OWN CELLS. Pakistan's first Common Reporting Tables
(filed 2024, inventory year 2022) report 1.A.3.c at 56,609 TJ and 4,194.75 kt CO2. Two
things follow, both from the workbook's own numbers rather than from any modelling here:

  THE ACTIVITY IS AN ORDER OF MAGNITUDE ABOVE THE OPERATOR'S FUEL ACCOUNT. 56,609 TJ at the
  rail NCV is about 1,316 kt of diesel. Pakistan Railways' Year Book reports roughly 120 kt
  consumed across the overlapping fiscal years - the filing implies eleven times the fuel
  the operator meters. This is the BUR-1 divergence, alive in the current submission.

  THE FILING'S OWN IMPLIED-EMISSION-FACTOR CELLS SHOW THE ROAD TABLE ON RAIL. The Liquid
  fuels row under 1.A.3.c carries IEF cells reading CO2 74.10 t/TJ, CH4 3.9 kg/TJ, N2O
  3.8995 kg/TJ. Those non-CO2 values are IPCC Table 3.2.2 (road); the rail table 3.4.1 says
  4.15 and 28.6. The factor-table trap this paper documents is not a hypothesis about how
  the BUR went wrong - it is visible in the current filing's implied-factor column, where
  N2O sits at a seventh of the rail default.

Everything is re-derived from the workbook bytes on each run, rows located by label search
rather than pinned row numbers (a workbook revision must break loudly, not silently), and
the archive hash is pinned by a test so a substituted file cannot masquerade as the filing.

The register (data/activity/railways/official_benchmarks.csv) carries the hand-transcribed
official values - BUR-1's 4.06 Mt for FY2017-18 - and the comparison output states every
benchmark against this inventory's value for the SAME year by the identical method, which
is the hierarchy the paper reports: matched-year first, reference year separately.

Usage:  python3 -m pkinv.sectors.railways.official_reporting
Writes: outputs/railways_unfccc_crt_cell_audit_2024.csv,
        outputs/railways_official_comparison_2024.csv
"""

from pkinv.assets import asset_path
import csv
import hashlib
import io
import os
import zipfile

from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.sectors.railways import engine
from pkinv.sectors.railways.data import RailwaysData
from pkinv.core.io import read_rows
from pkinv.core import documents
from pkinv.core.source_extracts import materialized

CRT_SOURCE = asset_path(ROOT, "sources", "Aviation", "PAK_CRT_2024.zip")
CRT_WORKBOOK = "ENERGY-PAK-CRT.xlsx"
SHEET = "Table1.A(a)s3"
CRT_INVENTORY_YEAR = "CY2022"   # calendar 2022, straddling fiscal 2021-22 and 2022-23

REGISTER = asset_path(DATA, "activity", "railways", "official_benchmarks.csv")

# CRT totals are stated on UNFCCC AR5 metrics without the fossil-methane adjustment this
# inventory otherwise applies; comparisons against a filing must use the filing's basis.
CRT_GWP = {"CH4": 28.0, "N2O": 265.0}

COLS = {"activity_TJ": 2, "basis": 3, "ief_co2_t_per_TJ": 4, "ief_ch4_kg_per_TJ": 5,
        "ief_n2o_kg_per_TJ": 6, "co2_kt": 7, "ch4_kt": 8, "n2o_kt": 9}


def payload_sha256(path=CRT_SOURCE):
    return documents.digest(path, quiet=True)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None            # notation keys: NE, NA, NO


@materialized("railways_extract")
def extract(path=CRT_SOURCE):
    """The 1.A.3.c rows, located by label, every value carrying its cell coordinate.

    Returns {"category": {...}, "liquid": {...}} where each holds the COLS fields plus
    "row" and "cells" ({field: "C79"-style coordinate}).
    """
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    documents.require(path, "the UNFCCC CRT tables are read here")
    with zipfile.ZipFile(path) as z:
        wb = load_workbook(io.BytesIO(z.read(CRT_WORKBOOK)), read_only=True, data_only=True)
    ws = wb[SHEET]
    grid = {r: [c.value for c in row]
            for r, row in enumerate(ws.iter_rows(min_row=1, max_row=120, max_col=12), 1)}
    cat_row = next(r for r, vals in sorted(grid.items())
                   if str(vals[1] or "").strip().startswith("1.A.3.c"))
    liq_row = next(r for r in range(cat_row + 1, cat_row + 6)
                   if str(grid[r][1] or "").strip().startswith("Liquid fuels"))
    out = {}
    for name, r in (("category", cat_row), ("liquid", liq_row)):
        vals = grid[r]
        rec = {k: (_num(vals[i]) if k != "basis" else str(vals[i] or "").strip())
               for k, i in COLS.items()}
        rec["label"] = str(vals[1]).strip()
        rec["row"] = r
        rec["cells"] = {k: "%s%d" % (get_column_letter(i + 1), r)
                        for k, i in COLS.items()}
        out[name] = rec
    return out


def arithmetic_check(rows=None):
    """activity x the filing's own IEF must reproduce the filing's emissions.

    Proves we are reading the cells the filing computes with, before comparing anything
    against them - the discipline the power and fugitives CRT extractions established.
    """
    rows = rows or extract()
    r = rows["liquid"]
    failures = []
    for gas, ief_key, out_key, scale in (
            ("CO2", "ief_co2_t_per_TJ", "co2_kt", 1e-3),
            ("CH4", "ief_ch4_kg_per_TJ", "ch4_kt", 1e-6),
            ("N2O", "ief_n2o_kg_per_TJ", "n2o_kt", 1e-6)):
        want = r[out_key]
        got = r["activity_TJ"] * r[ief_key] * scale
        if want and abs(got - want) / want > 1e-6:
            failures.append("%s: %.6g vs %.6g" % (gas, got, want))
    return failures


def crt_co2e_Mt(rows=None):
    """The filing's 1.A.3.c total on its own GWP basis (AR5, unadjusted CH4)."""
    r = (rows or extract())["category"]
    return (r["co2_kt"] + r["ch4_kt"] * CRT_GWP["CH4"]
            + r["n2o_kt"] * CRT_GWP["N2O"]) / 1000.0


def implied_activity(data, rows=None):
    """What the filing's activity would mean in fuel, stated in the operator's units."""
    r = (rows or extract())["category"]
    ncv = data.efv("railway_ncv", "Gas/Diesel Oil")
    kt = r["activity_TJ"] / ncv
    thousand_litres = kt * 1e6 / data.p("hsd_density_kg_per_l") / 1e3
    return {"activity_TJ": r["activity_TJ"], "implied_diesel_kt": kt,
            "implied_thousand_litres": thousand_litres}


def register(path=REGISTER):
    return read_rows(path, comments=False)


def _own_Mt(data, year):
    return sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, year))


def comparison(data, rows=None):
    """One row per official benchmark, matched to this inventory's value for the same year.

    A calendar inventory year straddles two fiscal years; those rows carry the mean of the
    two fiscal values and say so - a bound, not a point match, exactly like the power
    sector's CRT comparison.
    """
    rows = rows or extract()
    out = []
    for b in register():
        if b["benchmark_id"] == "crt2022":
            official = crt_co2e_Mt(rows)
            fy_pair = (2022, 2023)
            own = (_own_Mt(data, 2022) + _own_Mt(data, 2023)) / 2.0
            basis = "calendar 2022 straddles FY2021-22 and FY2022-23; own value is their mean"
            implied_kt = implied_activity(data, rows)["implied_diesel_kt"]
        elif not (b["value_Mt_co2e"] or "").strip():
            # The TNC and the BTR1 narrative report 1.A.3 as one aggregate line. The
            # absence of a railway row is itself the finding, and the table says so.
            out.append({
                "benchmark_id": b["benchmark_id"], "source": b["source"],
                "year_label": b["year_label"], "official_Mt_co2e": "",
                "own_Mt_co2e": "", "ratio_official_over_own": "",
                "implied_diesel_kt": "", "metered_diesel_kt": "",
                "implied_over_metered": "",
                "match_basis": "railways not separately reported - 1.A.3 aggregate only"})
            continue
        elif not (b["series_year"] or "").strip():
            # FY1993-94 sits far outside the annual series; the quinquennial history
            # layer is the honest comparator - indicative, average-resolution, and it
            # includes the furnace-oil traction the INC's rail share also covered.
            from pkinv.sectors.railways import history
            hist_row = next(r for r in history.load() if r["period"] == "1990-95")
            own = history.co2e_Mt(data, hist_row)
            official = float(b["value_Mt_co2e"])
            out.append({
                "benchmark_id": b["benchmark_id"], "source": b["source"],
                "year_label": b["year_label"], "official_Mt_co2e": official,
                "own_Mt_co2e": own, "ratio_official_over_own": official / own,
                "implied_diesel_kt": "", "metered_diesel_kt": "",
                "implied_over_metered": "",
                "match_basis": "point year against the 1990-95 quinquennial indicative "
                               "value (fuel history incl. furnace-oil traction); a "
                               "magnitude check, not a point match"})
            continue
        else:
            official = float(b["value_Mt_co2e"])
            sy = int(b["series_year"])
            fy_pair = (sy,)
            own = _own_Mt(data, sy)
            basis = "matched fiscal year, identical method and GWP basis"
            # CO2e treated as CO2 for the fuel implication - conservative, since any CH4
            # or N2O share would imply even more fuel per Mt at rail factors.
            implied_kt = official * 1e3 / (data.efv("railway_traction_co2",
                                                    "Gas/Diesel Oil")
                                           * data.efv("railway_ncv", "Gas/Diesel Oil")
                                           / 1e6)
        metered = [data.quantity("Gas/Diesel Oil", y) * 1000.0
                   * data.p("hsd_density_kg_per_l") / 1e6 for y in fy_pair]
        metered_kt = sum(metered) / len(metered)
        out.append({
            "benchmark_id": b["benchmark_id"], "source": b["source"],
            "year_label": b["year_label"], "official_Mt_co2e": official,
            "own_Mt_co2e": own, "ratio_official_over_own": official / own,
            "implied_diesel_kt": implied_kt, "metered_diesel_kt": metered_kt,
            "implied_over_metered": implied_kt / metered_kt, "match_basis": basis})
    return out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()
    rows = extract()
    bad = arithmetic_check(rows)
    if bad:
        raise SystemExit("CRT arithmetic check failed: %s" % "; ".join(bad))

    with open(asset_path(OUTPUTS, "railways_unfccc_crt_cell_audit_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["workbook", "sheet", "row_label", "field", "cell", "value"])
        for name in ("category", "liquid"):
            r = rows[name]
            for field in COLS:
                w.writerow([CRT_WORKBOOK, SHEET, r["label"], field,
                            r["cells"][field], r[field]])
        w.writerow([CRT_WORKBOOK, "", "archive", "sha256", "", payload_sha256()])

    comp = comparison(data, rows)
    with open(asset_path(OUTPUTS, "railways_official_comparison_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(comp[0].keys()))
        w.writeheader()
        for r in comp:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                        for k, v in r.items()})

    ief = rows["liquid"]
    print("CRT 1.A.3.c (inventory year %s): %.0f TJ, %.1f kt CO2"
          % (CRT_INVENTORY_YEAR, rows["category"]["activity_TJ"],
             rows["category"]["co2_kt"]))
    print("  filing's own IEF cells: CO2 %.2f t/TJ, CH4 %.2f, N2O %.4f kg/TJ"
          % (ief["ief_co2_t_per_TJ"], ief["ief_ch4_kg_per_TJ"],
             ief["ief_n2o_kg_per_TJ"]))
    print("  N2O IEF is the ROAD table's 3.9; the rail table says 28.6")
    for r in comp:
        if r["official_Mt_co2e"] == "":
            print("  %-8s %-9s railways not separately reported (1.A.3 aggregate only)"
                  % (r["benchmark_id"], r["year_label"]))
        elif r["implied_over_metered"] == "":
            print("  %-8s %-9s official %.3f vs own %.3f Mt (x%.2f); %s"
                  % (r["benchmark_id"], r["year_label"], r["official_Mt_co2e"],
                     r["own_Mt_co2e"], r["ratio_official_over_own"],
                     "history-layer basis"))
        else:
            print("  %-8s %-9s official %.3f vs own %.3f Mt (x%.1f); implied fuel x%.1f"
                  % (r["benchmark_id"], r["year_label"], r["official_Mt_co2e"],
                     r["own_Mt_co2e"], r["ratio_official_over_own"],
                     r["implied_over_metered"]))


if __name__ == "__main__":
    main()
