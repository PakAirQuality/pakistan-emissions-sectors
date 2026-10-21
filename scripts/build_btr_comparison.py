#!/usr/bin/env python3
"""Year-matched comparison with Pakistan's First Biennial Transparency Report.

The BTR states that its inventory year 2020-21 is a Pakistani fiscal year, so
PakEmis FY2020-21 can be compared without a calendar/fiscal blend. Both report
AR5 CO2e, but their CH4 conventions cannot be assumed identical: PakEmis uses
30 for fossil CH4 and 28 for biogenic CH4, whereas the BTR table gives neither
native gas masses nor a fossil/biogenic split. A PakEmis-only uniform-28
sensitivity shows this convention's effect; it does not harmonise the BTR.

The explicit subject crosswalk is essential. For example, the BTR books rice
at 3.D, urea application at 3.C.2, and indirect manure N2O at 3.C.5; PakEmis
uses 3.C.7, 3.C.3, and 3.C.6 respectively. A code join would compare different
processes. Tiers distinguish the support for each comparison:

  exact               corresponding category scopes as documented here
  aggregate           corresponding subject after explicit aggregation;
                      see row notes for allocation qualifications
  scope-gap           BTR scope is wider; no category ratio is emitted
  btr-only            BTR estimate for a category PakEmis declares NE;
                      an external comparator, not an uncertainty bound
  btr-zero            BTR prints zero; a discrepancy to investigate
  pakemis-only        PakEmis estimates a category with no BTR counterpart
  btr-elsewhere       counterpart is inside the excluded BTR land block
  aggregate-restated  a useful re-sum, excluded from totals to avoid overlap
  out-of-scope        LULUCF, excluded from totals

The headline total preserves each inventory's stated non-LULUCF scope and
therefore retains scope asymmetries. The exact+aggregate subtotal excludes
scope-gap and restated rows. Neither total is independent validation: the
inventories share national statistics, and a small net difference can hide
large opposing category differences. The category-offset product reports
those signed differences without treating BTR as ground truth or attributing
them to particular causes.

Usage:  python3 scripts/build_btr_comparison.py [--check]
Writes: outputs/pakemis_btr_comparison.csv
        outputs/pakemis_btr_category_offsets.csv
"""
from __future__ import annotations

import argparse
import collections
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                    # noqa: E402
from pkinv.core.io import read_rows, write_table, table_text                       # noqa: E402
from pkinv.paths import DATA, OUTPUTS                                  # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_btr_comparison.csv")
OFFSETS_OUT = asset_path(OUTPUTS, "pakemis_btr_category_offsets.csv")
COMPARABLE_TOTAL = "TOTAL on exact and aggregate crosswalk categories"
# Reached by the legacy identity its siblings use, which is what data/catalog/assets.csv
# resolves. That registration is not cosmetic: pkinv.report.data_provenance classifies a data
# file by the directory of its LEGACY path, so an unregistered table under
# data/shared/evidence/ classifies "unregistered" while benchmarks.csv beside it classifies
# "hand:parameter" purely because the catalog gives it an identity at data/.
INVENTORY = "btr1_national_inventory.csv"

# The BTR's inventory year, as a PakEmis period. Not a guess: see the module docstring.
MATCHED_PERIOD = "FY2020-21"
from pkinv.core.configurations import REFERENCE as CONFIGURATION
GWP = "AR5"
SOURCE = "Pakistan BTR1 (2024), national inventory 2020-21"

FIELDS = ("btr_codes", "pakemis_codes", "subject", "tier", "btr_Mt_co2e",
          "pakemis_Mt_co2e", "ratio_pakemis_over_btr", "within_0.5_2.0x",
          # PakEmis-only CH4 sensitivity: BTR weighting remains unknown.
          "pakemis_Mt_co2e_ch4_uniform_28", "ratio_ch4_uniform_28",
          "fossil_ch4_share_of_pakemis_pct", "ch4_convention_note", "note")

# (btr codes, pakemis codes, subject, tier, note). Order is the BTR's own table order.
CROSSWALK = [
    (["1.A.1"], ["1.A.1.a"], "Public electricity and heat", "exact", ""),
    (["1.A.2"], ["1.A.2"], "Manufacturing and construction", "exact", ""),
    (["1.A.3"], ["1.A.3.a", "1.A.3.b", "1.A.3.c", "1.A.4.c", "1.A.2/1.A.4.c"],
     "Transport", "aggregate",
     "the BTR publishes 1.A.3 as one line; this inventory aggregates its transport allocation, "
     "including off-road 1.A.4.c and the unresolved 1.A.2/1.A.4.c share. This is a subject-level "
     "comparison conditional on that allocation, not an exact code-boundary match"),
    (["1.A.4"], ["1.A.4.b"], "Other sectors", "scope-gap",
     "the BTR's 1.A.4 includes commercial and institutional buildings, which this inventory "
     "declares NE; PakEmis counts its off-road share under transport above. Coverage and "
     "allocation differences prevent attributing the numerical gap solely to an absence; "
     "no ratio is emitted and this row is excluded from the exact+aggregate subtotal"),
    (["1.B.1"], [], "Solid-fuel fugitives", "btr-only", "1.B.1 is NE here"),
    (["1.B.2"], ["1.B.2"], "Oil and natural gas fugitives", "exact", ""),
    (["2.A.1"], ["2.A.1"], "Cement production", "exact", ""),
    (["2.A.2"], [], "Lime production", "btr-only", "2.A.2 is NE here"),
    (["2.A.3"], [], "Glass production", "btr-only", "2.A.3 is NE here"),
    (["2.A.4"], [], "Other process uses of carbonates", "btr-only", "2.A.4 is NE here"),
    (["2.B.1"], ["2.B.1"], "Ammonia production", "exact", ""),
    (["2.C"], ["2.C.1"], "Metal industry", "btr-zero",
     "the BTR reports the whole metal industry as 0 while this inventory estimates iron and "
     "steel. A zero is a claim about the world, and Pakistan has steel production"),
    (["2.D.1"], ["2.D.1"], "Lubricant use", "exact", ""),
    (["2.F"], [], "ODS substitutes (F-gases)", "btr-zero",
     "the BTR reports 0; this inventory declares 2.F NE and carries an external bound beside "
     "it. A typed absence with a bound says more than a bare zero"),
    (["2.H"], [], "Other industrial processes", "btr-only", "2.H is NE here"),
    (["3.A.1"], ["3.A.1"], "Enteric fermentation", "exact", ""),
    # THESE TWO USED TO BE ONE AGGREGATE ROW, and the migration made them exact. The BTR
    # books indirect manure N2O separately and, before 2026-10-06, this inventory kept it
    # inside manure management, so only the sum was boundary-safe. Both accounts now separate
    # it, so each half faces its counterpart directly. The codes still differ - the BTR puts
    # it at 3.C.5, which IPCC 2006 Table 8.2 uses for indirect SOILS N2O, while indirect
    # manure N2O is 3.C.6 - which is exactly why this file crosswalks instead of joining.
    (["3.A.2"], ["3.A.2"], "Manure management (CH4 and direct N2O)", "exact", ""),
    (["3.C.5"], ["3.C.6"], "Indirect N2O from manure management", "exact",
     "the BTR codes this 3.C.5; IPCC 2006 books indirect MANURE N2O at 3.C.6 and reserves "
     "3.C.5 for indirect SOILS N2O, so a code join here compares manure against soil"),
    (["3.C.2"], ["3.C.3"], "Urea application", "exact",
     "the BTR codes urea 3.C.2; IPCC 2006 Table 8.2 uses 3.C.2 for Liming and 3.C.3 for Urea "
     "Application, so this pair is one code apart on the same quantity"),
    (["3.C.3", "3.C.4"], ["3.C.4", "3.C.5"], "Managed soils", "aggregate",
     "direct plus indirect managed-soil N2O; this is an aggregate comparison and does not "
     "attribute differences to activity data, nitrogen routing, or emission factors"),
    (["3.D"], ["3.C.7"], "Rice cultivation", "exact",
     "the BTR books rice at 3.D; PakEmis follows IPCC 2006 with 3.C.7. A code-only join "
     "does not identify the same process"),
    (["3.B"], [], "Land (LULUCF)", "out-of-scope",
     "outside this inventory by declared scope; excluded from every total comparison. NOT "
     "purely land-use CO2, which matters for anyone reading the exclusion as clean: 3.47 of "
     "its 34.82 Mt is CH4 and N2O, and for a land account that is biomass burning - 3.16 Mt "
     "of it in cropland, which is residue burning this inventory also estimates. So the "
     "exclusion withholds about 3.5 Mt that is comparable in kind, and the restated residue "
     "row above is where that part is actually compared"),
    ([], ["3.C.1.b"], "Field burning of residues", "btr-elsewhere",
     "the submission has no biomass-burning LINE, and an earlier version of this crosswalk "
     "read that as an absence and called this inventory the more complete account. It is "
     "not: the submission folds residue burning into its land block at 3.B.2, whose non-CO2 "
     "half is 3.16 Mt against 2.50 Mt of land-use CO2 in the same row. The comparison is in "
     "the restated row below; this row stays in the PakEmis subtotal because the mass is "
     "this inventory's and emits no ratio because its counterpart is inside a block excluded "
     "by scope"),
    (["3.B.2"], ["3.C.1.b"], "Residue burning, against the submission's cropland non-CO2",
     "aggregate-restated",
     "compares PakEmis field burning with the CH4 plus N2O part of the BTR cropland row "
     "under the declared residue-burning mapping; land-use CO2 is excluded. This is a "
     "restatement, not an additional category in either subtotal. The full BTR land block "
     "is excluded by scope; including this part in a total beside existing residue burning "
     "would require explicit boundary reconciliation to avoid double counting. Calendar-year "
     "CRT crop-residue values are not used in this fiscal-year comparison"),
    (["4.A"], ["4.A"], "Solid waste disposal", "exact",
     "read with the solid-waste-fate row below: disposal and burning are related fates, "
     "and this category comparison alone does not identify the cause of a difference"),
    (["4.C.1"], [], "Waste incineration", "btr-only", "4.C.1 is NE here"),
    (["4.C.2"], ["4.C.2"], "Open burning of waste", "exact",
     "read with the solid-waste-fate row below before quoting this"),
    (["4.A", "4.C.1", "4.C.2"], ["4.A", "4.C.2"], "Solid-waste fate (disposal + burning)",
     "aggregate-restated",
     "disposal, incineration and open burning are related waste-management fates, so their "
     "sum is informative alongside individual ratios. Opposing differences can reflect "
     "allocation, activity, methods or emission factors; this comparison alone does not "
     "identify the cause. Incineration is estimated only by BTR, so even this re-sum has a "
     "coverage difference. Excluded from all totals because its parts are counted above"),
    (["4.D.1"], ["4.D.1"], "Domestic wastewater", "exact", ""),
    (["4.D.2"], [], "Industrial wastewater", "btr-only", "4.D.2 is NE here"),
]

COMPARABLE_TIERS = ("exact", "aggregate")
RATIO_TIERS = COMPARABLE_TIERS + ("aggregate-restated",)

# A RESTATED row re-sums categories that are already counted individually above, so it carries
# a ratio and must be EXCLUDED from the subtotal - adding it would count the same waste twice.
# Same rule as the completeness-mass ledger's contained_in: a claimant inside another row's
# bound is listed with its container named and left out of every sum.
RESTATED_TIERS = ("aggregate-restated",)


# Codes whose comparable part is the NON-CO2 half, not the printed total. 3.B.2 is the only
# one: its row mixes land-use CO2 with the biomass burning the submission folded in, and only
# the second is comparable to this inventory's field burning. Recorded as a table rather than
# special-cased in the loop, so a second such code is a line here and not a branch.
NON_CO2_PART = {"3.B.2"}


def _btr():
    rows = read_rows(asset_path(DATA, INVENTORY))
    out = {}
    for r in rows:
        if r["btr_code"] in NON_CO2_PART:
            if not (r["ch4_Mt_co2e"] and r["n2o_Mt_co2e"]):
                raise SystemExit(
                    "%s needs the non-CO2 part of %s, and the transcription records no gas "
                    "split for it - the row prints a dash for one of the gases, so the split "
                    "cannot be recovered" % (INVENTORY, r["btr_code"]))
            out[r["btr_code"]] = float(r["ch4_Mt_co2e"]) + float(r["n2o_Mt_co2e"])
        else:
            out[r["btr_code"]] = float(r["total_Mt_co2e"])
    if not out:
        raise SystemExit("%s is empty; the comparison would compare against nothing"
                         % INVENTORY)
    return out


def _pakemis():
    """{ipcc_code: Mt CO2e AR5} for the matched period, from the atomic annual table.

    The atomic table rather than the semantic layer, deliberately: it is built at the annual
    stage and the semantic release is assembled after it, so reading the semantic copy would
    make this product depend on a later phase to say something about an earlier one. The two
    share the same underlying inventory; no emissions are recalibrated to the BTR here.
    """
    agg = collections.defaultdict(float)
    fossil_ch4_Gg = collections.defaultdict(float)
    for r in read_rows(asset_path(OUTPUTS, "pakemis_atomic_annual.csv")):
        if r["period_id"] == MATCHED_PERIOD and r["configuration_id"] == CONFIGURATION:
            agg[r["ipcc_code"]] += float(r["co2e_Mt_AR5"] or 0.0)
            # THE ONE PLACE THE TWO ACCOUNTS CANNOT BE ASSUMED TO AGREE. This inventory
            # weights fossil CH4 at AR5's 30 and biogenic CH4 at 28 (core/gwp.py, selected
            # per component by core/components.py); the BTR reports "AR5" without printing a
            # fossil/biogenic split or any native gas mass, so its own CH4 weighting cannot
            # be recovered from the published table. Carrying the fossil mass here lets the
            # engine side be restated at a uniform 28 so the reader can see the size of the
            # convention rather than be told it does not matter.
            if r["gas"] == "CH4" and r["gas_origin"] == "fossil":
                fossil_ch4_Gg[r["ipcc_code"]] += float(r["emission_native_mass"] or 0.0)
    if not agg:
        raise SystemExit(
            "no %s/%s rows in the atomic annual table - the comparison would read the engine "
            "side as zero and print every ratio as 0.00" % (MATCHED_PERIOD, CONFIGURATION))
    return agg, fossil_ch4_Gg


def validate_crosswalk():
    """Fail before summing a repeated code or a parent beside its child."""
    counted = [r for r in CROSSWALK if r[3] not in ("out-of-scope",) + RESTATED_TIERS]
    for index, side in ((0, "BTR"), (1, "PakEmis")):
        codes = [c for r in counted for c in r[index]]
        duplicates = sorted(c for c, count in collections.Counter(codes).items() if count > 1)
        nested = sorted((a, b) for a in codes for b in codes if b.startswith(a + "."))
        if duplicates or nested:
            raise ValueError("overlapping %s crosswalk entries: repeated=%s, parent/child=%s"
                             % (side, duplicates, nested))


def build():
    validate_crosswalk()
    btr, (pk, fossil_ch4) = _btr(), _pakemis()
    missing = sorted({c for entry in CROSSWALK for c in entry[0]} - set(btr))
    if missing:
        raise SystemExit("the crosswalk names BTR codes the transcription does not hold: %s"
                         % ", ".join(missing))
    unmapped = sorted(set(pk) - {c for entry in CROSSWALK for c in entry[1]})
    if unmapped:
        raise SystemExit(
            "these PakEmis codes face no crosswalk entry, so the comparison would silently "
            "omit them from its own subtotal: %s" % ", ".join(unmapped))
    rows = []
    for bc, pc, subject, tier, note in CROSSWALK:
        b = sum(btr[c] for c in bc)
        p = sum(pk.get(c, 0.0) for c in pc)
        ratio = ""
        verdict = "not comparable"
        if tier in RATIO_TIERS and b:
            ratio = round(p / b, 2)
            verdict = "YES" if 0.5 <= p / b <= 2.0 else "REVIEW"
        # The same engine mass restated at a uniform CH4 = 28: subtract 2 t CO2e per tonne
        # of fossil CH4, which is exactly the 30-vs-28 difference. Only the fossil part moves,
        # because biogenic CH4 is already weighted at 28 on both readings.
        fossil = sum(fossil_ch4.get(c, 0.0) for c in pc)
        p28 = p - fossil * 2.0 / 1000.0
        ratio28 = ""
        if tier in RATIO_TIERS and b:
            ratio28 = round(p28 / b, 2)
        share = round(100.0 * fossil * 30.0 / 1000.0 / p, 1) if (pc and p) else ""
        if not pc:
            convention = ""
        elif not fossil:
            convention = ("no fossil CH4 in this subject, so the two CH4 conventions give "
                          "the same number and the sensitivity columns repeat the published one")
        else:
            convention = ("fossil CH4 present: this inventory weights it at AR5's 30, the BTR "
                          "prints AR5 CO2e with no fossil/biogenic split and no native mass, "
                          "so its own weighting cannot be recovered from the published table. "
                          "The uniform-28 columns show the size of the convention; neither "
                          "column is a correction of the other")
        rows.append({
            "btr_codes": "+".join(bc), "pakemis_codes": "+".join(pc),
            "subject": subject, "tier": tier,
            "btr_Mt_co2e": round(b, 3) if bc else "",
            "pakemis_Mt_co2e": round(p, 3) if pc else "",
            "ratio_pakemis_over_btr": ratio, "within_0.5_2.0x": verdict,
            "pakemis_Mt_co2e_ch4_uniform_28": round(p28, 3) if pc else "",
            "ratio_ch4_uniform_28": ratio28,
            "fossil_ch4_share_of_pakemis_pct": share,
            "ch4_convention_note": convention,
            "note": note})

    in_scope = [r for r in rows
                if r["tier"] not in ("out-of-scope",) + RESTATED_TIERS]
    tb = sum(float(r["btr_Mt_co2e"]) for r in in_scope if r["btr_Mt_co2e"] != "")
    tp = sum(float(r["pakemis_Mt_co2e"]) for r in in_scope if r["pakemis_Mt_co2e"] != "")

    # The scope-gap row has two numbers but NOT a common boundary. Excluding it,
    # one-sided rows and restatements makes the subtotal's rule explicit.
    both = [r for r in in_scope if r["tier"] in COMPARABLE_TIERS]
    lb = sum(float(r["btr_Mt_co2e"]) for r in both)
    lp = sum(float(r["pakemis_Mt_co2e"]) for r in both)

    # The same two totals on a PakEmis-only uniform CH4 = 28 sensitivity, summed so
    # the totals cannot disagree with the rows beneath them.
    def _sum28(subset):
        return sum(float(r["pakemis_Mt_co2e_ch4_uniform_28"]) for r in subset
                   if r["pakemis_Mt_co2e_ch4_uniform_28"] != "")
    tp28, lp28 = _sum28(in_scope), _sum28(both)
    CONVENTION = ("the engine side restated at a uniform CH4 = 28; the BTR's own CH4 "
                  "weighting is not recoverable from its published table, which prints "
                  "AR5 CO2e per gas and no native mass")
    rows.append({
        "btr_codes": "", "pakemis_codes": "", "subject": "TOTAL (excluding LULUCF)",
        "tier": "total", "btr_Mt_co2e": round(tb, 3), "pakemis_Mt_co2e": round(tp, 3),
        "ratio_pakemis_over_btr": round(tp / tb, 3),
        "within_0.5_2.0x": "YES" if 0.5 <= tp / tb <= 2.0 else "REVIEW",
        "pakemis_Mt_co2e_ch4_uniform_28": round(tp28, 3),
        "ratio_ch4_uniform_28": round(tp28 / tb, 3),
        "fossil_ch4_share_of_pakemis_pct": round(100.0 * (tp - tp28) / 2.0 * 30.0 / tp, 1),
        "ch4_convention_note": CONVENTION,
        "note": "excludes the full BTR LULUCF block and all aggregate-restated rows; "
                "retains scope-gap and one-sided rows. PakEmis residue burning is counted "
                "while its BTR counterpart remains inside excluded LULUCF, so this is not "
                "a common-boundary national total. Close totals do not establish category "
                "agreement or independent validation"})
    rows.append({
        "btr_codes": "", "pakemis_codes": "", "tier": "total",
        "subject": COMPARABLE_TOTAL,
        "btr_Mt_co2e": round(lb, 3), "pakemis_Mt_co2e": round(lp, 3),
        "ratio_pakemis_over_btr": round(lp / lb, 4),
        "within_0.5_2.0x": "YES" if 0.5 <= lp / lb <= 2.0 else "REVIEW",
        "pakemis_Mt_co2e_ch4_uniform_28": round(lp28, 3),
        "ratio_ch4_uniform_28": round(lp28 / lb, 4),
        "fossil_ch4_share_of_pakemis_pct": round(100.0 * (lp - lp28) / 2.0 * 30.0 / lp, 1),
        "ch4_convention_note": CONVENTION,
        "note": comparison_note(tb, tp, lb, lp)})
    return rows


def comparison_note(headline_btr, headline_pk, subtotal_btr, subtotal_pk):
    """Describe the two actual gaps, without hardcoding which is closer."""
    headline_gap = 100.0 * abs(headline_pk - headline_btr) / headline_btr
    subtotal_gap = 100.0 * abs(subtotal_pk - subtotal_btr) / subtotal_btr
    direction = ("larger" if subtotal_gap > headline_gap else
                 "smaller" if subtotal_gap < headline_gap else "equal")
    return (
        "only nonoverlapping exact and aggregate crosswalk rows; excludes 1.A.4 scope-gap, "
        "one-sided categories, the residue-burning boundary asymmetry, and restated rows. "
        "Absolute relative differences from BTR are %.2f%% for the headline total and %.2f%% "
        "for this subtotal: the subtotal difference is %s. This does not identify a "
        "completeness or estimation cause. Aggregates retain the allocation qualifications "
        "in their row notes; shared national statistics and unknown BTR CH4 weighting "
        "prevent treating agreement as independent validation"
        % (headline_gap, subtotal_gap, direction))


def banner(rows):
    fugitives = next(r for r in rows if r["subject"] == "Oil and natural gas fugitives")
    return (
        "PakEmis against Pakistan BTR1, FY2020-21: matched fiscal year and AR5 family;",
        "CH4 conventions are not known to match. PakEmis uses fossil CH4 = 30 and biogenic",
        "CH4 = 28; BTR gives no native masses or fossil split. Uniform-28 columns change",
        "PakEmis only and are a sensitivity, not a harmonisation or correction of BTR.",
        "Oil/gas fugitives: %.1f%% fossil CH4 by PakEmis CO2e; ratio %.2f as published,"
        % (float(fugitives["fossil_ch4_share_of_pakemis_pct"]),
           float(fugitives["ratio_pakemis_over_btr"])),
        "%.2f with PakEmis CH4 uniformly 28. Ratios only for exact/aggregate/restated tiers;"
        % float(fugitives["ratio_ch4_uniform_28"]),
        "allocation qualifications remain in row notes. Both restated rows are excluded",
        "from totals. The exact+aggregate subtotal also excludes scope-gap and one-sided",
        "categories; the headline retains scope asymmetries. Category offsets are in",
        "pakemis_btr_category_offsets.csv. Close totals can conceal opposing differences;",
        "shared statistics mean this is not independent validation.",
    )


OFFSET_FIELDS = (
    "period_id", "configuration_id", "gwp_basis", "row_type", "subject", "tier",
    "btr_codes", "pakemis_codes", "btr_Mt_co2e", "pakemis_Mt_co2e",
    "difference_Mt_co2e", "positive_difference_Mt_co2e", "negative_difference_Mt_co2e",
    "absolute_difference_Mt_co2e", "difference_Mt_co2e_ch4_uniform_28", "note")
OFFSET_BANNER = (
    "Signed category differences, PakEmis minus BTR1, FY2020-21; Mt CO2e, AR5 family.",
    "Arithmetic uses the comparison table's displayed values (0.001 Mt); BTR inputs are rounded.",
    "Only nonoverlapping exact and aggregate crosswalk rows; scope-gap, one-sided,",
    "out-of-scope and restated rows are excluded. Aggregate allocation caveats still apply.",
    "The total row sums positive, negative, net and absolute category differences separately.",
    "Absolute differences describe disagreement, not estimation error, accuracy or uncertainty.",
    "BTR is not independent ground truth; uniform-28 is a PakEmis-only CH4 sensitivity.",
)


def category_offsets(rows):
    """Decompose the subtotal into opposing differences, without causal attribution."""
    out = []
    for r in rows:
        if r["tier"] not in COMPARABLE_TIERS:
            continue
        b, p = float(r["btr_Mt_co2e"]), float(r["pakemis_Mt_co2e"])
        d = round(p - b, 3)
        out.append({
            "period_id": MATCHED_PERIOD, "configuration_id": CONFIGURATION,
            "gwp_basis": "AR5 family; CH4 convention unresolved", "row_type": "category",
            "subject": r["subject"], "tier": r["tier"],
            "btr_codes": r["btr_codes"], "pakemis_codes": r["pakemis_codes"],
            "btr_Mt_co2e": b, "pakemis_Mt_co2e": p, "difference_Mt_co2e": d,
            "positive_difference_Mt_co2e": max(d, 0.0),
            "negative_difference_Mt_co2e": min(d, 0.0),
            "absolute_difference_Mt_co2e": abs(d),
            "difference_Mt_co2e_ch4_uniform_28":
                round(float(r["pakemis_Mt_co2e_ch4_uniform_28"]) - b, 3),
            "note": r["note"]})
    total = dict.fromkeys(OFFSET_FIELDS, "")
    total.update(period_id=MATCHED_PERIOD, configuration_id=CONFIGURATION,
                 gwp_basis="AR5 family; CH4 convention unresolved", row_type="total",
                 subject=COMPARABLE_TOTAL, tier="total",
                 note="positive plus negative differences equal the net difference; their "
                      "absolute magnitudes sum to absolute category disagreement. This is "
                      "an arithmetic decomposition, not a validation score or causal attribution")
    for key in ("btr_Mt_co2e", "pakemis_Mt_co2e", "difference_Mt_co2e",
                "positive_difference_Mt_co2e", "negative_difference_Mt_co2e",
                "absolute_difference_Mt_co2e", "difference_Mt_co2e_ch4_uniform_28"):
        total[key] = round(sum(r[key] for r in out), 3)
    return out + [total]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = build()
    products = (
        (OUT, FIELDS, rows, banner(rows)),
        (OFFSETS_OUT, OFFSET_FIELDS, category_offsets(rows), OFFSET_BANNER),
    )
    for path, fields, data, heading in products:
        if args.check:
            current = io.open(path, encoding="utf-8", newline="").read() if os.path.exists(path) else ""
            if current != table_text(fields, data, banner=heading):
                raise SystemExit("%s is stale" % os.path.relpath(path, ROOT))
            print("checked: %s (%d rows)" % (os.path.relpath(path, ROOT), len(data)))
        else:
            write_table(path, fields, data, banner=heading)
    if args.check:
        return
    totals = [r for r in rows if r["tier"] == "total"]
    print("BTR comparison -> %s" % OUT)
    for t in totals:
        print("  %-44s %8.2f vs %8.2f = %s"
              % (t["subject"], float(t["pakemis_Mt_co2e"]), float(t["btr_Mt_co2e"]),
                 t["ratio_pakemis_over_btr"]))
    print("  %d crosswalk entries" % (len(rows) - len(totals)))
    for t in ("exact", "aggregate", "btr-only", "btr-zero", "pakemis-only", "scope-gap"):
        n = sum(1 for r in rows if r["tier"] == t)
        mass = sum(float(r["btr_Mt_co2e"] or 0) for r in rows if r["tier"] == t)
        print("    %-14s %2d entries, BTR mass %6.2f Mt" % (t, n, mass))


if __name__ == "__main__":
    main()
