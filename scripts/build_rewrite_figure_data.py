"""The compact manuscript's figure inputs, read from the products instead of transcribed.

WHY THIS EXISTS. The editorial rewrite of October 2026 arrived with six small CSVs behind its
four figures, each row carrying an honest provenance note: "Transcribed from supplied
manuscript; not independently regenerated". Its own manifest says the transcriptions "should
not replace original inventory outputs", and its editorial notes ask, as the first author
action, to "rebuild final tables/figures from actual outputs".

That is what this does. Every value below comes from the same product, and through the same
pointer, that the registered claim for that value already uses - so a figure and the sentence
beside it cannot disagree. The transcription is kept at
paper_national/figures/rewrite_inputs/transcribed_csv/ as a record of what was delivered, and
tests/test_rewrite_figure_data.py compares the two: a divergence is then a finding about one
of them rather than a silent overwrite.

The schemas match the delivered files exactly, so the plotting scripts need no change beyond
where they look.

Usage:  python3 scripts/build_rewrite_figure_data.py [--check]
Writes: paper_national/figures/rewrite_inputs/data/*.csv
"""
import argparse
import collections
import csv
import io
import os
from pkinv.paths import PAPER_NATIONAL_FIGURES  # noqa: E402
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

# The period every row in this file describes, named once.
REFERENCE_PERIOD = "FY2023-24"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PAPER_NATIONAL_FIGURES, "rewrite_inputs", "data")

# The display label each module carries in the figure, against the sector key the product
# uses. The rewrite's prose is explicit that these are calculation modules and not reporting
# categories - power includes captive industrial generation, transport includes off-road
# machinery - so the labels say "module" where that matters and the caption repeats it.
MODULES = [("Agriculture", "agriculture"), ("Power", "power"), ("Transport", "transport"),
           ("Waste", "waste"), ("Residential", "residential"), ("IPPU", "ippu"),
           ("Oil and gas fugitives", "fugitives"), ("Industrial fuel", "industry"),
           ("Railways", "railways"), ("Domestic aviation", "aviation")]

REF = "REF_2023_24 (residential L)"


def _sector_rows():
    return {r["sector"]: r for r in read_rows("outputs/national_all_sectors.csv")}


def module_totals():
    held = _sector_rows()
    rows = []
    for label, key in MODULES:
        assert key in held, "national_all_sectors.csv has no %r sector" % key
        rows.append({
            "module": label,
            "emissions_Mt_CO2e": "%.2f" % float(held[key]["co2e_Mt_AR5"]),
            "period": "FY2023-24", "gwp": "AR5", "configuration": REF,
            "source_location": "outputs/national_all_sectors.csv (sector=%s)" % key,
            "provenance": "read from the product; the same pointer the registered claim uses",
        })
    return ("module_totals.csv",
            ["module", "emissions_Mt_CO2e", "period", "gwp", "configuration",
             "source_location", "provenance"], rows)


def annual_series():
    rows = []
    for r in read_rows("outputs/pakemis_national_series.csv"):
        if r["row_kind"] != "covered_total":
            continue
        rows.append({
            "period": r["period_label"],
            "emissions_Mt_CO2e": "%.3f" % float(r["co2e_Mt_AR5"]),
            "gwp": "AR5", "configuration": REF,
            "source_location": "outputs/pakemis_national_series.csv (row_kind=covered_total)",
            "provenance": "read from the product; covered-total scope, not a national "
                          "complete-coverage claim",
        })
    rows.sort(key=lambda r: r["period"])
    assert len(rows) == 9, "expected nine fiscal years, got %d" % len(rows)
    return ("annual_national_series.csv",
            ["period", "emissions_Mt_CO2e", "gwp", "configuration", "source_location",
             "provenance"], rows)


def national_uncertainty():
    # The dependence setting is `scenario`; `scope` and `aggregation_level` are both
    # "national" on the row that carries the national percentiles.
    mc = {}
    for r in read_rows("outputs/national_uncertainty_montecarlo.csv"):
        if r["aggregation_level"] == "national" and r["name"] == "TOTAL":
            mc[r["scenario"]] = r
    assert mc, "no national TOTAL row in national_uncertainty_montecarlo.csv"
    held = _sector_rows()
    det = sum(float(held[k]["co2e_Mt_AR5"]) for _l, k in MODULES if k in held)
    rows = [{
        "case": "Deterministic reference", "point_type": "accounting_reference",
        "point_Mt_CO2e": "%.2f" % det, "p025_Mt_CO2e": "", "p975_Mt_CO2e": "",
        "period": "FY2023-24",
        "source": "outputs/national_all_sectors.csv (sum over the ten modules)",
        "provenance": "read from the product; an accounting reference, not a draw",
    }]
    LABEL = [("within_sector", "Within-module parameter sharing"),
             ("cross_sector", "Cross-module fuel-factor sharing")]
    for scenario, label in LABEL:
        assert scenario in mc, "no %r scenario (have %s)" % (scenario, sorted(mc))
        r = mc[scenario]
        rows.append({
            "case": label, "point_type": "Monte_Carlo_median",
            "point_Mt_CO2e": "%.2f" % float(r["P50_Mt"]),
            "p025_Mt_CO2e": "%.2f" % float(r["P2.5_Mt"]),
            "p975_Mt_CO2e": "%.2f" % float(r["P97.5_Mt"]),
            "period": "FY2023-24",
            "source": "outputs/national_uncertainty_montecarlo.csv (scenario=%s, national TOTAL)"
                      % scenario,
            "provenance": "read from the product; a conditional parameter interval under the "
                          "stated dependence setting",
        })
    return ("national_uncertainty.csv",
            ["case", "point_type", "point_Mt_CO2e", "p025_Mt_CO2e", "p975_Mt_CO2e", "period",
             "source", "provenance"], rows)


def temporal_evidence():
    # THE MANUSCRIPT'S WORDS FOR THE FOUR CLASSES (Sect. 2.3), not a second set. The figure said
    # "process-based seasonal profile" and "flat or weakly informed allocation" where the text
    # defines "a process or activity-shape profile" and "a flat or weakly constrained profile".
    DESC = {"T1": "Observed source-month activity",
            "T2": "Reconstructed monthly administrative activity",
            "T3": "Process or activity-shape profile",
            "T4": "Flat or weakly constrained profile"}
    rows = []
    for r in read_rows("outputs/temporal_profile.csv"):
        key = r["temporal_method"]
        # scope=NATIONAL: the same filter the registered claim's getter uses. The product
        # also carries a per-sector breakdown under the same method letters.
        if key not in DESC or r["scope"] != "NATIONAL":
            continue
        rows.append({
            "evidence_class": key.replace("T", "TE"), "description": DESC[key],
            "share_percent": "%.2f" % float(r["share_of_scope_pct"]),
            "period": "FY2023-24", "weight_basis": "AR5 CO2e mass",
            "source_location": "outputs/temporal_profile.csv (temporal_method=%s)" % key,
            "provenance": "read from the product; a share of mass by timing evidence, not a "
                          "measure of timing accuracy",
        })
    rows.sort(key=lambda r: r["evidence_class"])
    assert len(rows) == 4, "expected four timing classes, got %d" % len(rows)
    return ("reference_temporal_evidence.csv",
            ["evidence_class", "description", "share_percent", "period", "weight_basis",
             "source_location", "provenance"], rows)


def managed_soils():
    flows = {}
    for r in read_rows("outputs/pakemis_faostat_nitrogen_flows.csv", comments=True):
        flows[r["flow"]] = r
    both = pasture = None
    for r in read_rows("outputs/eval/sensitivity.csv"):
        # selected by NAME: another scenario (EF1 0.016) gives the same 54.72
        if r["scenario"].startswith("Both 2006 direct factors"):
            both = r
        if r["scenario"].startswith("Pasture EF3PRP = 2006 aggregate"):
            pasture = r
    assert both is not None, "no 'Both 2006 direct factors' scenario in eval/sensitivity.csv"
    assert pasture is not None, "no 'Pasture EF3PRP = 2006 aggregate' scenario in eval/sensitivity.csv"
    main = flows["managed soils, as reported"]
    ef1 = flows["managed soils, at FAOSTAT's EF1 vintage"]
    # THE CASES ARE NAMED BY THEIR FACTORS. "2006 EF1 + pasture" told a reader which guideline
    # year but not what changed. The factor values are the ones src/pkinv/eval/sensitivity_table.py
    # substitutes: the reference uses the 2019 Refinement's dry-climate direct factor and its
    # pasture-deposition factors; each case replaces a disjoint set of direct factors and leaves
    # the indirect pathways alone.
    rows = [
        {"case": "PakEmis reference", "emissions_Mt_CO2e": "%.2f" % float(main["pakemis"]),
         "period": "FY2023-24", "gwp": "AR5", "group": "PakEmis",
         "figure_label": "Reference factors",
         "figure_detail": "2019, dry climate",
         "direct_factor_EF1": "0.005", "pasture_factor_EF3PRP": "0.002 cattle; 0.003 sheep, goats",
         "interpretation": "Reference uses 2019 dry-climate direct factors",
         "source": "outputs/pakemis_faostat_nitrogen_flows.csv (managed soils, as reported)"},
        {"case": "2006 EF1", "emissions_Mt_CO2e": "%.2f" % float(ef1["pakemis"]),
         "period": "FY2023-24", "gwp": "AR5", "group": "PakEmis",
         "figure_label": "2006 direct soil factor",
         "figure_detail": "fertiliser, manure, residues",
         "direct_factor_EF1": "0.010", "pasture_factor_EF3PRP": "0.002 cattle; 0.003 sheep, goats",
         "interpretation": "Replace EF1 with 2006 aggregate value; other terms held",
         "source": "outputs/pakemis_faostat_nitrogen_flows.csv (EF1 vintage)"},
        # THE SECOND SUBSTITUTION ON ITS OWN. With only "direct factor" and "direct factor and
        # pasture" the rows were nested and rose step by step toward the comparator, which reads
        # as a calibration. The two substitutions act on disjoint nitrogen pathways; shown
        # separately and then together, the figure says so.
        {"case": "2006 pasture", "emissions_Mt_CO2e": "%.2f" % float(pasture["soils"]),
         "period": "FY2023-24", "gwp": "AR5", "group": "PakEmis",
         "figure_label": "2006 pasture factors",
         "figure_detail": "grazing deposition",
         "direct_factor_EF1": "0.005", "pasture_factor_EF3PRP": "0.02 cattle; 0.01 sheep, goats",
         "interpretation": "Replace the pasture-deposition factors with the 2006 values; other terms held",
         "source": "outputs/eval/sensitivity.csv (Pasture EF3PRP = 2006 aggregate)"},
        {"case": "2006 EF1 and pasture", "emissions_Mt_CO2e": "%.2f" % float(both["soils"]),
         "period": "FY2023-24", "gwp": "AR5", "group": "PakEmis",
         "figure_label": "Both 2006 factors",
         "figure_detail": "the two rows above together",
         "direct_factor_EF1": "0.010", "pasture_factor_EF3PRP": "0.02 cattle; 0.01 sheep, goats",
         "interpretation": "EF1 0.010 and the 2006 pasture-deposition factors together",
         "source": "outputs/eval/sensitivity.csv (Both 2006 direct factors)"},
        {"case": "FAOSTAT", "emissions_Mt_CO2e": "%.2f" % float(main["faostat"]),
         "period": "CY2023", "gwp": "AR5", "group": "FAOSTAT",
         "figure_label": "FAOSTAT",
         "figure_detail": "its own factors and pathways",
         "direct_factor_EF1": "", "pasture_factor_EF3PRP": "",
         "interpretation": "Comparator, on its own calendar year and nitrogen pathways",
         "source": "outputs/pakemis_faostat_nitrogen_flows.csv (managed soils, as reported)"},
    ]
    for r in rows:
        r["provenance"] = ("read from the product; factor substitutions are structural "
                           "alternatives, not calibration steps")
    return ("managed_soils_factor_scenarios.csv",
            ["case", "emissions_Mt_CO2e", "period", "gwp", "group", "figure_label",
             "figure_detail", "direct_factor_EF1", "pasture_factor_EF3PRP", "interpretation",
             "source", "provenance"], rows)


def provincial_so2():
    REGIONS = ["pakistan", "Punjab", "Khyber Pakhtunkhwa", "Balochistan", "Sindh"]
    # The region is the `scope` column - the product has no separate province field, and
    # "pakistan" is the national row beside the four provinces.
    held = {}
    for r in read_rows("outputs/pakemis_air_provincial_external_comparison.csv"):
        if r["period_id"] == "FY2021-22" and r["row_kind"] == "comparison":
            held[r["scope"]] = r
    rows = []
    for region in REGIONS:
        r = held.get(region)
        assert r is not None, "no FY2021-22 comparison row for %r (have %s)" % (
            region, sorted(held)[:8])
        rows.append({
            "region": "Pakistan" if region == "pakistan" else region,
            "pakemis_to_edgar_ratio": "%.2f" % float(r["ratio_engine_over_edgar"]),
            "period": "FY2021-22", "pollutant": "SO2", "comparator": "EDGAR v8.1",
            "period_harmonization": "Approximate fiscal blend of calendar-year estimates",
            "source_location": "outputs/pakemis_air_provincial_external_comparison.csv",
            "provenance": "read from the product; a comparison of covered-source estimates, "
                          "not an observational validation",
        })
    return ("provincial_so2_ratios.csv",
            ["region", "pakemis_to_edgar_ratio", "period", "pollutant", "comparator",
             "period_harmonization", "source_location", "provenance"], rows)


def btr_comparison():
    """PakEmis against Pakistan's own submission, for the figure panel that replaced SO2.

    WHY THIS PANEL EXISTS. Figure 4(b) compared SO2 ratios against EDGAR: an AIR POLLUTANT
    used to support a greenhouse-gas dataset, on an approximate fiscal blend of two calendar
    years. The review was right that it carries little weight for the claim being made. This
    comparison is greenhouse gas against greenhouse gas, and it needs no harmonisation at
    all: the BTR's inventory year 2020-21 is a Pakistani FISCAL year by its own statement
    and it reports on AR5 GWPs, so there is no calendar blend and no GWP conversion between
    the two sides.

    Only subjects where BOTH sides carry a value are plotted. A row where one side is NE is
    not a disagreement about magnitude - it is a coverage difference, and plotting it as a
    ratio would turn an absence into a number. Those rows stay in the product, which the
    caption points at, and the count of them is carried here so the panel can say how many
    it leaves out rather than quietly dropping them.
    """
    rows, excluded = [], 0
    for r in read_rows("outputs/pakemis_btr_comparison.csv"):
        # v3: an aggregate-restated row compares one side's category against the other's
        # WIDER aggregate; it has a ratio, but the ratio is not like-for-like and it goes
        # to the qualified panel (btr_qualified_rows.csv), not into this ranking.
        if r["tier"] == "aggregate-restated":
            excluded += 1
            continue
        btr, ours = (r["btr_Mt_co2e"] or "").strip(), (r["pakemis_Mt_co2e"] or "").strip()
        # The ratio column is blank wherever either side is - it is not computed for a
        # pair that does not exist - so a row with no ratio is excluded on the same
        # footing as a row with no value.
        if not btr or not ours or not (r["ratio_pakemis_over_btr"] or "").strip() \
                or float(btr) <= 0:
            excluded += 1
            continue
        rows.append({
            "subject": r["subject"],
            "btr_Mt_co2e": "%.2f" % float(btr),
            "pakemis_Mt_co2e": "%.2f" % float(ours),
            "ratio_pakemis_over_btr": "%.2f" % float(r["ratio_pakemis_over_btr"]),
            "within_half_to_double": r["within_0.5_2.0x"],
            "tier": r["tier"],
            "ratio_ch4_uniform_28": ("%.2f" % float(r["ratio_ch4_uniform_28"]))
                                    if (r.get("ratio_ch4_uniform_28") or "").strip() else "",
            "pakemis_Mt_co2e_ch4_uniform_28": ("%.2f" % float(r["pakemis_Mt_co2e_ch4_uniform_28"]))
                                    if (r.get("pakemis_Mt_co2e_ch4_uniform_28") or "").strip() else "",
            "fossil_ch4_share_of_pakemis_pct": (r.get("fossil_ch4_share_of_pakemis_pct") or "").strip(),
            "period": "FY2020-21",
            "comparator": "Pakistan BTR1 / CRT, inventory year 2020-21",
            # THE PERIOD NEEDS NO HARMONISATION; THE METRIC IS NOT MATCHED. This field said
            # "None required: both sides are the same Pakistani fiscal year on AR5 GWPs" while
            # the product it is read from says the comparison is not CH4-convention-matched:
            # PakEmis weights fossil methane at 30 and the submission's weighting cannot be
            # recovered from its published table. Both statements are now carried.
            "period_harmonization": "Period: none required, both sides are the Pakistani "
                                    "fiscal year 2020-21",
            "metric_harmonization": "AR5 GWP100 on both sides, but not CH4-convention-matched: "
                                    "PakEmis weights fossil CH4 at 30; the ratio at a uniform "
                                    "28 is carried beside the as-reported one",
            "subjects_not_comparable": str(excluded),
            "source_location": "outputs/pakemis_btr_comparison.csv",
            "provenance": "read from the product; a comparison against a national "
                          "submission, not an observational validation",
        })
    # THE TOTAL OF WHAT IS PLOTTED. The product's "TOTAL on categories both accounts estimate"
    # (1.02) also contains "Other sectors", a scope-gap subject that is NOT among the like-for-
    # like rows; drawn under those rows it read as their total, and the manuscript said so. The
    # like-for-like rows themselves sum to a different ratio, computed here from the product's
    # unrounded masses and drawn as its own row.
    like = [r for r in read_rows("outputs/pakemis_btr_comparison.csv")
            if r["tier"] in ("exact", "aggregate") and (r["btr_Mt_co2e"] or "").strip()
            and (r["pakemis_Mt_co2e"] or "").strip() and float(r["btr_Mt_co2e"]) > 0]
    assert len(like) == len([r for r in rows if r["tier"] != "total"]), "the like-for-like set drifted"
    sum_btr = sum(float(r["btr_Mt_co2e"]) for r in like)
    sum_ours = sum(float(r["pakemis_Mt_co2e"]) for r in like)
    sum_ours_28 = sum(float(r["pakemis_Mt_co2e_ch4_uniform_28"]) for r in like)
    template = dict(rows[0])
    template.update({
        "subject": "TOTAL of the like-for-like categories", "tier": "total-of-plotted",
        "btr_Mt_co2e": "%.2f" % sum_btr, "pakemis_Mt_co2e": "%.2f" % sum_ours,
        "ratio_pakemis_over_btr": "%.2f" % (sum_ours / sum_btr),
        "within_half_to_double": "YES" if 0.5 <= sum_ours / sum_btr <= 2.0 else "REVIEW",
        "ratio_ch4_uniform_28": "%.2f" % (sum_ours_28 / sum_btr),
        "pakemis_Mt_co2e_ch4_uniform_28": "%.2f" % sum_ours_28,
        "fossil_ch4_share_of_pakemis_pct": "",
        "source_location": "outputs/pakemis_btr_comparison.csv (sum over the %d rows of tiers exact and aggregate)" % len(like),
        "provenance": "computed here: the sum of the plotted rows' masses on each side, and their ratio",
    })
    rows.append(template)
    for r in rows:
        r["subjects_not_comparable"] = str(excluded)
    rows.sort(key=lambda r: -float(r["ratio_pakemis_over_btr"]))
    return ("btr_subject_comparison.csv",
            ["subject", "btr_Mt_co2e", "pakemis_Mt_co2e", "ratio_pakemis_over_btr",
             "within_half_to_double", "tier", "ratio_ch4_uniform_28",
             "pakemis_Mt_co2e_ch4_uniform_28", "fossil_ch4_share_of_pakemis_pct", "period",
             "comparator", "period_harmonization", "metric_harmonization",
             "subjects_not_comparable", "source_location", "provenance"], rows)


def construction_quantities():
    """The closure Figure 1 states, PER GAS, from the ledger that owns it.

    THE FIRST VERSION OF THIS WAS WRONG AND THE 23rd REVIEW CAUGHT IT WITH AN INEQUALITY.
    It read pakemis_adm2_monthly_sector.csv filtered to spatial_view == "physical" and
    summed the three gases to 125,692.0 Gg, which it called the placed mass. But each
    module publishes only the view its geography supports: transport is ACCOUNTING-only
    (road emissions are allocated where the fuel is sold, not where a road is) and waste is
    ORIGIN-only. The filter therefore dropped both modules silently, losing 43,040 Gg of
    CO2. The reviewer needed no access to the code to see it: the figure printed
    125,692.0 + 249.5 Gg of "native gas" while the companion reported 160,944 Gg of CO2
    alone, and three nonnegative masses cannot sum to less than one of them.

    AND THE SUM ITSELF WAS THE DEEPER DEFECT. CO2 + CH4 + N2O in gigagrams is not a
    quantity: it adds masses of gases whose radiative effects differ by two orders of
    magnitude, so the total answers no question. Reporting it invited exactly the
    comparison that exposed it. The closure is therefore stated PER GAS, which is how the
    grid's own provenance (fig_ghg_grid_provenance.json, closure_detail) already asserts
    it: grid + unallocated == the national stream ledger, per period and per gas.

    The source is pakemis_stream_support_ledger.csv with NO view filter - every stream on
    the view it publishes - which reproduces the grid's ledger figure exactly.
    """
    LEDGER = "outputs/pakemis_stream_support_ledger.csv"
    UNALLOC = "outputs/pakemis_spatial_unallocated.csv"
    ledger, unallocated = collections.Counter(), collections.Counter()
    for r in read_rows(LEDGER):
        if (r.get("period_id") or REFERENCE_PERIOD) != REFERENCE_PERIOD:
            continue
        value = (r.get("emissions_Gg") or "").strip()
        if value:
            ledger[r["gas"]] += float(value)
    for r in read_rows(UNALLOC):
        value = (r.get("emissions_Gg") or "").strip()
        if value and (r.get("level") or "").strip():
            unallocated[r["gas"]] += float(value)

    reference = None
    for r in read_rows("outputs/national_all_sectors.csv"):
        if r.get("row_kind") == "national_total":
            assert reference is None, "two national_total rows; the file needs a key"
            reference = float(r["co2e_Mt_AR5"])
    assert reference is not None, "national_all_sectors.csv has no national_total row"

    rows = [{
        "node": "annual_emissions", "gas": "all", "quantity": "%.2f" % reference,
        "unit": "Mt CO2e (AR5)",
        "what": "the reference configuration, summed over its ten calculation modules",
        "source_location": "outputs/national_all_sectors.csv#row_kind=national_total",
    }]
    for gas in ("CO2", "CH4", "N2O"):
        total = ledger[gas]
        unplaced = unallocated.get(gas, 0.0)
        rows.append({
            "node": "ledger_mass", "gas": gas, "quantity": "%.6f" % total,
            "unit": "Gg %s" % gas,
            "what": "the national stream ledger for this gas: what the closure must account "
                    "for",
            "source_location": LEDGER,
        })
        rows.append({
            "node": "placed_mass", "gas": gas, "quantity": "%.6f" % (total - unplaced),
            "unit": "Gg %s" % gas,
            "what": "placed below the first administrative level: the ledger less the "
                    "unallocated mass",
            "source_location": "%s less %s" % (LEDGER, UNALLOC),
        })
        rows.append({
            # SIX DECIMALS, NOT ONE. At %.1f the unallocated CH4 (0.001741 Gg) and N2O (0.006963 Gg)
            # printed as 0.0, and Figure 1 then asserted the two gases were fully placed. A rounded
            # zero is not an exact zero; the product decides what is zero.
            "node": "unallocated_mass", "gas": gas, "quantity": "%.6f" % unplaced,
            "unit": "Gg %s" % gas,
            "what": "mass with no supported placement below the first administrative level",
            "source_location": UNALLOC,
        })
    for r in rows:
        r["period"] = REFERENCE_PERIOD
        r["provenance"] = ("read from the product; the figure states these and derives "
                           "nothing. Masses are NOT summed across gases: CO2, CH4 and N2O "
                           "in Gg are not commensurable and a total of them answers no "
                           "question")
    return ("construction_quantities.csv",
            ["node", "gas", "quantity", "unit", "what", "period", "source_location",
             "provenance"], rows)


def period_change_intervals():
    """The full-panel change FY2015-16 -> FY2023-24 under the three dependence settings,
    from pakemis_trend_uncertainty.csv - the ONLY uncertainty the panel can state about a
    change. No per-year interval exists (the longitudinal product says the panel cannot
    resolve a year-on-year change), so Figure 2 shows the change interval in its own panel
    rather than attaching bands to the annual points."""
    rows = []
    LABEL = {"time_correlated": "Time-correlated parameters",
             "parameter_typed": "Parameter-typed dependence",
             "time_independent": "Time-independent draws"}
    for r in read_rows("outputs/pakemis_trend_uncertainty.csv"):
        if r["pair_kind"] != "window_full_panel":
            continue
        rows.append({
            "scenario": r["scenario"], "label": LABEL.get(r["scenario"], r["scenario"]),
            "from_period": r["from_period"], "to_period": r["to_period"],
            # the difference of the two deterministic totals: one value, the same in every row
            "difference_Mt_CO2e": "%.2f" % float(r["difference_Mt"]),
            "difference_is": "deterministic: the later covered total less the earlier",
            "p025_Mt_CO2e": "%.2f" % float(r["P2.5_Mt"]),
            # each setting's own ensemble median, which is NOT the deterministic difference
            "p50_Mt_CO2e": "%.2f" % float(r["P50_Mt"]),
            "p975_Mt_CO2e": "%.2f" % float(r["P97.5_Mt"]),
            "significant_at_95": r["significant_at_95"],
            "comparable_sectors": r["comparable_sectors"],
            "source": "outputs/pakemis_trend_uncertainty.csv (pair_kind=window_full_panel, scenario=%s)" % r["scenario"],
            "provenance": "read from the product; a conditional interval on the CHANGE under the stated dependence setting, not a per-year band",
        })
    order = ["time_correlated", "parameter_typed", "time_independent"]
    rows.sort(key=lambda r: order.index(r["scenario"]) if r["scenario"] in order else 9)
    assert len(rows) == 3, "expected the three dependence settings, got %d" % len(rows)
    return ("period_change_intervals.csv",
            ["scenario", "label", "from_period", "to_period", "difference_Mt_CO2e",
             "difference_is", "p025_Mt_CO2e", "p50_Mt_CO2e", "p975_Mt_CO2e", "significant_at_95",
             "comparable_sectors", "source", "provenance"], rows)


def btr_qualified_rows():
    """The BTR rows the ranked panel must NOT plot as ratios, for a qualified panel of
    their own: aggregate-restated (a wider aggregate on one side), scope-gap, btr-only,
    btr-zero, btr-elsewhere and out-of-scope. Each carries whatever masses exist and its
    tier, so the figure can show the coverage difference as a coverage difference."""
    rows = []
    KEEP = ("aggregate-restated", "scope-gap", "btr-only", "btr-zero", "btr-elsewhere",
            "out-of-scope")
    for r in read_rows("outputs/pakemis_btr_comparison.csv"):
        if r["tier"] not in KEEP:
            continue
        rows.append({
            "subject": r["subject"], "tier": r["tier"],
            "btr_Mt_co2e": ("%.2f" % float(r["btr_Mt_co2e"])) if r["btr_Mt_co2e"].strip() else "",
            "pakemis_Mt_co2e": ("%.2f" % float(r["pakemis_Mt_co2e"])) if r["pakemis_Mt_co2e"].strip() else "",
            "ratio_pakemis_over_btr": ("%.2f" % float(r["ratio_pakemis_over_btr"]))
                                      if r["ratio_pakemis_over_btr"].strip() else "",
            "period": "FY2020-21",
            "source_location": "outputs/pakemis_btr_comparison.csv (tier=%s)" % r["tier"],
            "provenance": "read from the product; a coverage or boundary difference, not a magnitude disagreement",
        })
    order = {k: i for i, k in enumerate(KEEP)}
    rows.sort(key=lambda r: (order[r["tier"]], r["subject"]))
    assert rows, "no qualified BTR rows"
    return ("btr_qualified_rows.csv",
            ["subject", "tier", "btr_Mt_co2e", "pakemis_Mt_co2e", "ratio_pakemis_over_btr",
             "period", "source_location", "provenance"], rows)


BUILDERS = (module_totals, annual_series, national_uncertainty, temporal_evidence,
            managed_soils, provincial_so2, btr_comparison, construction_quantities, period_change_intervals, btr_qualified_rows)


def render(fields, rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="compare the shipped files with a fresh build; write nothing")
    args = ap.parse_args(argv)
    if not args.check:
        os.makedirs(OUT, exist_ok=True)
    stale = []
    for build in BUILDERS:
        name, fields, rows = build()
        text = render(fields, rows)
        path = os.path.join(OUT, name)
        if args.check:
            held = io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
            if held != text:
                stale.append(name)
            else:
                print("checked: %s" % os.path.relpath(path, ROOT))
        else:
            io.open(path, "w", encoding="utf-8").write(text)
            print("%-42s %d rows" % (os.path.relpath(path, ROOT), len(rows)))
    if args.check and stale:
        print("stale: %s" % ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
