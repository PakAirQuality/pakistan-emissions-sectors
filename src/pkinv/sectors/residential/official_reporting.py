"""Cell-audited extraction of Pakistan's UNFCCC CRT for households (1.A.4.b), the
official benchmark register, and the CCAC particulate bridge.

THE HEADLINE, READ OFF THE FILING'S OWN CELLS: BIOMASS IS NE. Pakistan's first Common
Reporting Tables (filed 2024, inventory year 2022) report residential combustion at
311,724 TJ and 17,681 kt CO2 - and every Biomass cell in the 1.A.4.b block reads NE. The
country's two largest household fuels, dung cake and firewood, are not estimated in the
national filing at all: not their methane, not their nitrous oxide, not a memo. This
inventory puts those two streams at 1,041,627 TJ - 3.3 times the filing's entire
residential activity - and 10.7 Mt CO2e of counted CH4 and N2O. The filing's residential
sector is, by its own notation keys, the metered-fossil sliver of the sector.

WHERE THE FILING AND THIS INVENTORY AGREE, INDEPENDENTLY. The filing's gaseous-fuels row
carries 288,493 TJ against this inventory's 284,553 from OGRA's domestic gas table - a
1.4 percent gap across a CY2022-versus-FY2023-24 vintage difference, two derivations of
the same metered quantity that have never seen each other. The gaseous IEFs are exactly
IPCC Table 2.5 (56.1/5/0.1), so the corroboration is about the activity, not the factors.

TWO SMALLER READINGS OFF THE SAME BLOCK. The liquid IEF cells (CO2 64.37 t/TJ, CH4 5.55
kg/TJ) sit between the Table 2.5 LPG and kerosene anchors, an LPG-dominated blend
implying roughly 14 percent kerosene by energy - the same qualitative split OGRA's
tables give this inventory, and unlike the railway block, the RIGHT factor family. The
solid-fuels row books 29.5 TJ on IEFs of 101/300/1.5 - the Table 2.5 LIGNITE factor set,
where this inventory carries household coal as other-bituminous (94.6) on the HIES
quantity of 341 TJ; both are rounding errors on the sector, but the filing's lignite
choice and 11.6x-smaller activity are stated rather than smoothed over.

Everything is re-derived from the workbook bytes on each run, rows located by label
search rather than pinned row numbers, and the archive hash is pinned by a test - the
railways/power/fugitives discipline, unchanged.

THE CCAC BRIDGE first reports the unexplained gap with NO fuel-set subtraction.
PakEmis is moved from FY2023-24 to a CY2021 straddle-mean approximation; treating the
assessment's published "2021" as calendar year is an alignment assumption, because
the retrieved source does not establish the year convention. The comparator is
641 kt national PM2.5 times an approximate 35% household share, not a separately
reported exact household mass. Slater et al. (2024), doi:10.1021/acsestair.4c00003,
describe a LEAP assessment with EMEP/EEA factors. Table 3 explicitly includes
"Other Biomass" cooking. It therefore does not establish that household crop
residues are absent: removing this inventory's crop residues is a SEPARATE
conditional diagnostic, not a demonstrated boundary correction. Both the original
gap and the signed residual under that assumption remain visible. Configuration L
is a memo, not a preferred alternative selected by agreement with another inventory.

Usage:  python3 -m pkinv.sectors.residential.official_reporting
        python3 -m pkinv.sectors.residential.official_reporting --ccac-only
Writes: outputs/residential_unfccc_crt_cell_audit_2024.csv,
        outputs/residential_official_comparison_2024.csv,
        outputs/residential_ccac_bridge_2024.csv
"""

from pkinv.assets import asset_path
import argparse
import csv
import hashlib
import io
import os
import re
import sys
import zipfile

from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.sectors.residential import air_pollutants, combustion, engine, hies
from pkinv.sectors.residential.data import ResidentialData
from pkinv.core.io import read_rows, write_table
from pkinv.core import documents
from pkinv.core.source_extracts import materialized

CRT_SOURCE = asset_path(ROOT, "sources", "Aviation", "PAK_CRT_2024.zip")
CRT_WORKBOOK = "ENERGY-PAK-CRT.xlsx"
SHEET = "Table1.A(a)s4"
CRT_INVENTORY_YEAR = "CY2022"   # calendar 2022, straddling fiscal 2021-22 and 2022-23

REGISTER = asset_path(DATA, "activity", "residential", "official_benchmarks.csv")

# CRT totals are stated on UNFCCC AR5 metrics without the fossil-methane adjustment this
# inventory otherwise applies; comparisons against a filing must use the filing's basis.
CRT_GWP = {"CH4": 28.0, "N2O": 265.0}

COLS = {"activity_TJ": 2, "basis": 3, "ief_co2_t_per_TJ": 4, "ief_ch4_kg_per_TJ": 5,
        "ief_n2o_kg_per_TJ": 6, "co2_kt": 7, "ch4_kt": 8, "n2o_kt": 9}

FUEL_ROWS = ("Liquid fuels", "Solid fuels", "Gaseous fuels", "Biomass")

# The CCAC/SEI integrated assessment (Slater, Malley et al. 2022, held as
# sources/Papers/ccac_sei_pakistan_assessment.pdf; peer-reviewed as Slater et al. 2024,
# doi:10.1021/acsestair.4c00003): national PM2.5 641 kt in 2021 (Table 12, p.60) and households
# "around 35 %" (p.59), read from the transcription of that report rather than typed here. Their
# product is a rounded implied mass; the published "2021" does not itself establish a
# calendar-year convention. See the benchmark register for source scope.
CCAC_EXTRACT = asset_path(DATA, "sectors", "residential", "evidence", "ccac_sei_2022_household.csv")


def _ccac_printed(path=CCAC_EXTRACT):
    rows = read_rows(path)
    national = [r for r in rows if r["record_kind"] == "national_total" and r["quantity"] == "PM2.5"
                and r["year"] == "2021"]
    share = [r for r in rows if r["record_kind"] == "statement"
             and r["quantity"] == "residential share of national PM2.5"]
    if len(national) != 1 or len(share) != 1:
        raise ValueError("%s must print one 2021 PM2.5 total and one residential share" % path)
    return (float(national[0]["value"].replace(",", "")),
            float(re.search(r"[0-9.]+", share[0]["value"]).group()) / 100.0)


CCAC_NATIONAL_PM25_KT_2021, CCAC_RESIDENTIAL_SHARE = _ccac_printed()


def payload_sha256(path=CRT_SOURCE):
    return documents.digest(path, quiet=True)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None            # notation keys: NE, NA, NO


@materialized("residential_extract")
def extract(path=CRT_SOURCE):
    """The 1.A.4.b block, located by label, every value carrying its cell coordinate.

    Returns {"category": {...}, "liquid": ..., "solid": ..., "gaseous": ...,
    "biomass": ...}; each holds the COLS fields plus "raw" (the untyped cell values,
    so notation keys like NE survive), "row" and "cells".
    """
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    documents.require(path, "the UNFCCC CRT tables are read here")
    with zipfile.ZipFile(path) as z:
        wb = load_workbook(io.BytesIO(z.read(CRT_WORKBOOK)), read_only=True,
                           data_only=True)
    ws = wb[SHEET]
    grid = {r: [c.value for c in row]
            for r, row in enumerate(ws.iter_rows(min_row=1, max_row=120, max_col=12), 1)}
    cat_row = next(r for r, vals in sorted(grid.items())
                   if str(vals[1] or "").strip().startswith("1.A.4.b."))
    out = {}
    for name, r in [("category", cat_row)] + [
            (label.split()[0].lower(), next(
                rr for rr in range(cat_row + 1, cat_row + 8)
                if str(grid[rr][1] or "").strip().startswith(label)))
            for label in FUEL_ROWS]:
        vals = grid[r]
        rec = {k: (_num(vals[i]) if k != "basis" else str(vals[i] or "").strip())
               for k, i in COLS.items()}
        rec["raw"] = {k: str(vals[i]).strip() for k, i in COLS.items()}
        rec["label"] = str(vals[1]).strip()
        rec["row"] = r
        rec["cells"] = {k: "%s%d" % (get_column_letter(i + 1), r)
                        for k, i in COLS.items()}
        out[name] = rec
    return out


def arithmetic_check(rows=None):
    """activity x the filing's own IEF must reproduce the filing's emissions, for every
    fuel row that carries numbers. Proves we read the cells the filing computes with."""
    rows = rows or extract()
    failures = []
    for name in ("liquid", "solid", "gaseous"):
        r = rows[name]
        if r["activity_TJ"] is None:
            continue
        for gas, ief_key, out_key, scale in (
                ("CO2", "ief_co2_t_per_TJ", "co2_kt", 1e-3),
                ("CH4", "ief_ch4_kg_per_TJ", "ch4_kt", 1e-6),
                ("N2O", "ief_n2o_kg_per_TJ", "n2o_kt", 1e-6)):
            want = r[out_key]
            got = r["activity_TJ"] * r[ief_key] * scale
            if want and abs(got - want) / want > 1e-6:
                failures.append("%s %s: %.6g vs %.6g" % (name, gas, got, want))
    return failures


def biomass_is_ne(rows=None):
    """The headline finding, asserted off the cells rather than remembered."""
    r = (rows or extract())["biomass"]
    return all(r["raw"][k] == "NE" for k in ("activity_TJ", "co2_kt", "ch4_kt",
                                             "n2o_kt"))


def crt_co2e_Mt(rows=None):
    """The filing's 1.A.4.b total on its own GWP basis (AR5, unadjusted CH4)."""
    r = (rows or extract())["category"]
    return (r["co2_kt"] + r["ch4_kt"] * CRT_GWP["CH4"]
            + r["n2o_kt"] * CRT_GWP["N2O"]) / 1000.0


def own_fossil_scope_Mt(data):
    """This inventory on the FILING'S scope: fossil streams only, the filing's GWPs.

    The filing's biomass is NE, so a like-for-like comparison must drop this
    inventory's biomass CH4/N2O too - that is the point of the comparison, not a
    concession to it.
    """
    total = 0.0
    for c in engine.build_components(data):
        if c["subitem"].split()[0] in ("Dung", "Firewood", "Charcoal", "Crop"):
            continue
        gwp = CRT_GWP.get(c["gas"])
        if gwp is None:                      # CO2
            total += c["emissions_Gg"] / 1000.0
        else:
            total += c["emissions_Gg"] * gwp / 1000.0
    return total


def own_fossil_scope_cy(data, cal_year):
    """The fossil scope at the FILING'S year: straddle-mean of the two fiscal years,
    on the time-series gas (the one fossil stream that moves) and the filing's GWPs."""
    from pkinv.sectors.residential import combustion, timeseries
    series = timeseries.fuel_TJ_series(data)
    total = 0.0
    for fy in (cal_year, cal_year + 1):
        tj = series[fy]
        for stream, item, _ad in combustion.FOSSIL_FUELS:
            t = tj[stream]
            total += t * data.efv("residential_combustion_co2", item) / 1e9
            total += (t * data.efv("residential_combustion_ch4", item) / 1e9
                      * CRT_GWP["CH4"])
            total += (t * data.efv("residential_combustion_n2o", item) / 1e9
                      * CRT_GWP["N2O"])
    return total / 2.0


def gaseous_corroboration(data, rows=None):
    """The filing's gaseous TJ against OGRA's domestic gas, two independent readings."""
    crt_tj = (rows or extract())["gaseous"]["activity_TJ"]
    own_tj = combustion.fuel_TJ(data)["Natural gas"]
    return {"crt_TJ": crt_tj, "own_TJ": own_tj, "ratio_own_over_crt": own_tj / crt_tj}


def liquid_blend_implied_kerosene_share(data, rows=None):
    """Where the filing's liquid CO2 IEF sits between the Table 2.5 LPG and kerosene
    anchors, as an implied kerosene energy share - a diagnostic of their fuel mix."""
    ief = (rows or extract())["liquid"]["ief_co2_t_per_TJ"]
    lpg = data.efv("residential_combustion_co2", "Liquefied Petroleum Gases") / 1000.0
    kero = data.efv("residential_combustion_co2", "Other Kerosene") / 1000.0
    return (ief - lpg) / (kero - lpg)


def register(path=REGISTER):
    return read_rows(path, comments=False)


def comparison(data, rows=None):
    """One row per official benchmark. No matched-year value exists yet - this sector
    reports FY2023-24 only until the time-series phase - so every ratio is labelled
    with its vintage gap instead of silently pretending the years align."""
    rows = rows or extract()
    own_full = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data))
    out = []
    for b in register():
        rec = {"benchmark_id": b["benchmark_id"], "source": b["source"],
               "year_label": b["year_label"], "official_Mt_co2e": "",
               "own_Mt_co2e": "", "ratio_official_over_own": "", "match_basis": ""}
        if b["benchmark_id"] == "ccac2021":
            rec["match_basis"] = ("air benchmark, not CO2e: decomposed in the CCAC "
                                  "bridge output (residential_ccac_bridge_2024.csv), "
                                  "never on this table")
            out.append(rec)
            continue
        if b["benchmark_id"] == "crt2022":
            official = crt_co2e_Mt(rows)
            own = own_fossil_scope_cy(data, 2022)
            rec.update({
                "official_Mt_co2e": round(official, 3),
                "own_Mt_co2e": round(own, 3),
                "ratio_official_over_own": round(official / own, 3),
                "match_basis": "MATCHED SCOPE AND STRADDLE-MEAN YEAR: the filing's "
                               "biomass is NE, so own value is this inventory's "
                               "fossil streams at the mean of FY2021-22 and "
                               "FY2022-23 (the time-series gas; LPG/kerosene/minor "
                               "streams held), on the filing's GWPs. Full-scope "
                               "FY2023-24 value is %.2f Mt - %.1fx the filing." % (
                                   own_full, own_full / official)})
        elif (b["value_Mt_co2e"] or "").strip():
            from pkinv.sectors.residential import timeseries
            official = float(b["value_Mt_co2e"])
            sy = int(b["series_year"])
            own = timeseries.co2e_Mt(data, timeseries.fuel_TJ_series(data)[sy])
            rec.update({
                "official_Mt_co2e": official,
                "own_Mt_co2e": round(own, 3),
                "ratio_official_over_own": round(official / own, 3),
                "match_basis": "MATCHED FISCAL YEAR (%s) from the time series - gas "
                               "measured, biomass herd/survey-scaled, minor fossil "
                               "streams held at reference values - but possibly "
                               "unmatched scope: BUR-1 does not publish its "
                               "residential fuel list, so whether its figure carries "
                               "biomass CH4/N2O is undeterminable" % b["year_label"]})
        else:
            rec["match_basis"] = ("residential not separately reported - 1.A.4 "
                                  "aggregate only (36.80 Mt CO2e CY2021 across "
                                  "commercial, residential and agriculture)")
        out.append(rec)
    return out


def ccac_bridge(data):
    """Keep the unadjusted gap separate from an unverified fuel-boundary scenario.

    The ``unadjusted`` case closes A - year approximation - unexplained gap = B.
    The ``hypothetical_crop_residue_removal`` rows then state a separate conditional
    gap = unadjusted gap - removed residue. They do not establish that the source
    omitted household residues or that agreement selects a correct dung quantity.
    ``pm25_kt`` is signed PakEmis minus comparator for both gap rows.
    """
    from pkinv.sectors.residential import timeseries

    air = air_pollutants.compute(data)
    own = sum(r["emissions_kt"] for r in air if r["pollutant"] == "PM2.5")
    residue_pm = sum(r["emissions_kt"] for r in air
                     if r["subitem"].startswith("Crop residues")
                     and r["pollutant"] == "PM2.5")
    implied = CCAC_NATIONAL_PM25_KT_2021 * CCAC_RESIDENTIAL_SHARE
    matched = timeseries.matched_cy(2021, data)["pm25_kt"]

    # Stream scalings at the matched year, from the same series the matched total uses.
    herd_2021 = (timeseries.herd_scale(2021) + timeseries.herd_scale(2022)) / 2.0
    residue_2021 = (timeseries.residue_scale(2021)
                    + timeseries.residue_scale(2022)) / 2.0
    survey_2021 = (timeseries.dung_survey_air_dry_kg(2021)
                   + timeseries.dung_survey_air_dry_kg(2022)) / 2.0

    w_year = own - matched
    w_fuelset = residue_pm * residue_2021
    unadjusted_gap = matched - implied
    residual = unadjusted_gap - w_fuelset

    # Configuration L at the matched year, as a MEMO: the matched total with the dung
    # stream on the ledger (all diverted dung) instead of the survey.
    ledger_air = air_pollutants.compute(data, dung_basis="ledger")

    def dung(rows):
        return sum(r["emissions_kt"] for r in rows if r["subitem"] == "Dung cake PM2.5")

    dung_survey_2021 = dung(air) * survey_2021 / timeseries.dung_survey_air_dry_kg(data.year)
    matched_ledger = matched - dung_survey_2021 + dung(ledger_air) * herd_2021

    return [
        {"item": "ENDPOINT A: this inventory, FY2023-24 (reference)",
         "case": "unadjusted", "row_kind": "endpoint",
         "pm25_kt": round(own, 3),
         "note": "Andreae mass-basis factors; household dung on the HIES survey "
                 "series (the reference since rc67); gross emitted mass at the "
                 "appliance"},
        {"item": "WEDGE: inventory year (CY approximation)",
         "case": "unadjusted", "row_kind": "year_approximation",
         "pm25_kt": round(w_year, 3),
         "note": "PakEmis CY2021 approximation (%.3f kt): equal mean of FY2020-21 "
                 "and FY2021-22. The assessment labels its endpoint 2021; its "
                 "calendar/fiscal convention is unverified. This is an alignment "
                 "assumption, not an observed year correction." % matched},
        {"item": "UNEXPLAINED RESIDUAL: before fuel-set assumptions",
         "case": "unadjusted", "row_kind": "unexplained_gap",
         "pm25_kt": round(unadjusted_gap, 3),
         "note": "SIGNED PakEmis CY2021 approximation minus the rounded implied "
                 "household comparator, never redistributed: %.2f%% of endpoint B. "
                 "No crop-residue subtraction. Differences may include activity, "
                 "technology, EMEP/EEA versus Andreae factors, PM definition "
                 "(filterable/condensable scope unresolved), and unmatched periods. "
                 "Another inventory is not an observation of emissions."
                 % (100.0 * unadjusted_gap / implied)},
        {"item": "ENDPOINT B: CCAC/SEI implied residential, 2021",
         "case": "unadjusted", "row_kind": "endpoint",
         "pm25_kt": round(implied, 3),
         "note": "641 kt national primary PM2.5 times approximate 35% household "
                 "share: an implied mass from rounded inputs, not a separately "
                 "tabulated household measurement. Slater et al. (2024), "
                 "doi:10.1021/acsestair.4c00003, section 3.1, Figure 2 and Table 11. "
                 "LEAP model with EMEP/EEA 2019 air factors; calendar/fiscal "
                 "convention of published 2021 unverified."},
        {"item": "CANDIDATE: remove household crop residues",
         "case": "hypothetical_crop_residue_removal", "row_kind": "conditional_subtraction",
         "pm25_kt": round(w_fuelset, 3),
         "note": "NOT A STEP OF THE UNADJUSTED BRIDGE. Hypothetically remove "
                 "PakEmis household crop-residue PM2.5. This is not verified scope "
                 "alignment: Slater Table 3 includes Other Biomass cooking "
                 "(1.7 t per household per year), whose fuel composition is not "
                 "resolved by that label. Residue exclusion is therefore unconfirmed."},
        {"item": "CANDIDATE RESIDUAL: after hypothetical crop-residue removal",
         "case": "hypothetical_crop_residue_removal", "row_kind": "conditional_gap",
         "pm25_kt": round(residual, 3),
         "note": "SIGNED conditional residual = unadjusted gap minus the "
                 "hypothetical residue subtraction; %.2f%% of endpoint B. This "
                 "scenario can reverse the gap sign without supplying evidence "
                 "for the subtraction. It is not the remaining error after "
                 "established harmonization." % (100.0 * residual / implied)},
        {"item": "MEMO: configuration L at the matched year",
         "case": "ledger_dung_memo", "row_kind": "memo",
         "pm25_kt": round(matched_ledger, 3),
         "note": "NOT A STEP OF THE BRIDGE. The CY2021 approximation with all the dung "
                 "agriculture diverts burned in households: %.1f times endpoint B. "
                 "Closeness to a partly shared-input inventory does not validate "
                 "either dung quantity."
                 % (matched_ledger / implied)},
    ]


def write_ccac_bridge(data=None):
    """Regenerate only the public-source particulate comparison."""
    bridge = ccac_bridge(data or ResidentialData())
    write_table(asset_path(OUTPUTS, "residential_ccac_bridge_2024.csv"), list(bridge[0]), bridge)
    return bridge


def main(argv=()):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ccac-only", action="store_true",
                        help="Regenerate only the particulate comparison; no CRT extraction")
    args = parser.parse_args(argv)
    os.makedirs(OUTPUTS, exist_ok=True)
    data = ResidentialData()
    if args.ccac_only:
        bridge = write_ccac_bridge(data)
        for row in bridge:
            print("%s: %.3f kt" % (row["item"], row["pm25_kt"]))
        return
    rows = extract()
    failures = arithmetic_check(rows)
    if failures:
        raise SystemExit("CRT arithmetic check failed: %s" % "; ".join(failures))

    with open(asset_path(OUTPUTS, "residential_unfccc_crt_cell_audit_2024.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["block", "label", "row", "field", "cell", "value"])
        for name, rec in rows.items():
            for field in COLS:
                w.writerow([name, rec["label"], rec["row"], field,
                            rec["cells"][field], rec["raw"][field]])

    comp = comparison(data, rows)
    write_table(asset_path(OUTPUTS, "residential_official_comparison_2024.csv"), list(comp[0]), comp)

    bridge = write_ccac_bridge(data)

    print("CRT %s 1.A.4.b (%s):" % (CRT_INVENTORY_YEAR, SHEET))
    print("  arithmetic check: every fuel row reproduces the filing's own emissions")
    print("  BIOMASS = NE: %s - the filing does not estimate dung or firewood at all"
          % biomass_is_ne(rows))
    g = gaseous_corroboration(data, rows)
    print("  gaseous: filing %.0f TJ vs OGRA-derived %.0f TJ (ratio %.3f)"
          % (g["crt_TJ"], g["own_TJ"], g["ratio_own_over_crt"]))
    print("  liquid IEF %.2f t/TJ = LPG/kerosene blend, implied kerosene share %.0f%%"
          % (rows["liquid"]["ief_co2_t_per_TJ"],
             100 * liquid_blend_implied_kerosene_share(data, rows)))
    print("  solid: %.1f TJ on the LIGNITE factor set (101/300/1.5) vs our 341 TJ "
          "as other-bituminous" % rows["solid"]["activity_TJ"])
    print("  filing total %.2f Mt CO2e vs our fossil-scope %.2f Mt (full scope %.2f)"
          % (crt_co2e_Mt(rows), own_fossil_scope_Mt(data),
             sum(c["co2e_Mt_AR5"] for c in engine.build_components(data))))
    for b in comp:
        print("  benchmark %-8s official %s vs own %s - %s"
              % (b["benchmark_id"], b["official_Mt_co2e"] or "-",
                 b["own_Mt_co2e"] or "-", b["match_basis"][:60]))
    print("  CCAC comparison: %.1f kt (reference, FY2023-24) -> %.1f kt (implied 2021); "
          "year alignment is assumed; unadjusted unexplained gap %.1f kt"
          % (next(r["pm25_kt"] for r in bridge if r["item"].startswith("ENDPOINT A")),
             next(r["pm25_kt"] for r in bridge if r["item"].startswith("ENDPOINT B")),
             next(r["pm25_kt"] for r in bridge if "RESIDUAL" in r["item"])))


if __name__ == "__main__":
    main(sys.argv[1:])
