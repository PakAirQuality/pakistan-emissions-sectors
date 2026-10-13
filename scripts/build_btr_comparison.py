#!/usr/bin/env python3
"""The year-matched comparison against Pakistan's own national submission.

WHY THIS PRODUCT EXISTS. outputs/national_benchmark_comparison.csv compares this inventory
against EDGAR, Climate TRACE, FAOSTAT and one published study, and every one of those rows
needs an approximation: a calendar year read against a fiscal one, or an AR6 comparator read
against an AR5 account, or both. The one comparator that needs NEITHER APPROXIMATION was missing. Pakistan's
First Biennial Transparency Report publishes a full IPCC-category inventory on AR5 GWPs for
2020-21, and it states its own convention plainly - "the fiscal year 1993-94 (referred to as
1994)", "Pakistan's 2020-21 inventory (referred to as 2021)" - so its year IS a Pakistani
fiscal year and matches FY2020-21 exactly. Same period, same reporting basis, and it is
the account the country itself files.

ONE THING IS STILL NOT MATCHED, and the first version of this file said it was. "Same
metric" was too strong: this inventory weights FOSSIL CH4 at AR5's 30 and biogenic CH4
at 28 (core/gwp.py, chosen per component by core/components.py), while the BTR prints
AR5 CO2e per gas with no fossil/biogenic split and no native gas mass, so its own CH4
weighting cannot be recovered from the published table. It matters in exactly one place:
1.B.2 oil and gas fugitives is 96.2 per cent fossil CH4 by CO2e, and the ratio moves
from 7.27 to 6.80 on a uniform 28. Transport moves 1.03 to 1.02; the national ratio
1.008 to 1.004. Every row therefore carries BOTH readings - the as-published pair and a
`_ch4_uniform_28` pair - because the first is what the two documents say and the second
is what they would say on one convention. Neither is a correction of the other, and the
comparison does not assert which weighting the BTR used.

It could not simply be added to that register: benchmark_comparison() resolves the engine side
from registry.build_all(), which is the reference year and only the reference year, and the
register's own engine_period column is not read (tests/test_national_rollup.py refuses a row
that would exploit this). The rollup also runs before the nine-year annual product is built, so
teaching it to resolve a historical period would invert the build order. This is therefore a
product downstream of the annual table, where the history it needs already exists.

WHAT IT REFUSES TO DO. A code join between these two accounts is WRONG, and silently so: the
BTR books rice cultivation at 3.D and managed soils at 3.C, while this inventory books rice at
3.C and soils at 3.D. The codes are SWAPPED, so joining on the code compares rice against soil
N2O and produces two plausible-looking ratios. Every comparison here is therefore an explicit
crosswalk entry with a declared tier, and a ratio is emitted only for the tiers where the
boundaries support one:

  exact         one category each side, same scope
  aggregate     a sum on one or both sides - the BTR books indirect manure N2O separately at
                3.C.5 where this inventory keeps it inside manure management, so only the sum
                is comparable
  scope-gap     the BTR's category is wider than this inventory's and the difference is a
                declared absence, not a disagreement; no ratio
  btr-only      the BTR books it and this inventory declares it NE; the magnitude is an
                official bound on a declared absence, never an estimate to adopt
  btr-zero      the BTR prints 0 where a zero is not credible; recorded as a question about
                the official account, not about this one
  pakemis-only  this inventory estimates it and the BTR has no line for it at all
  out-of-scope  LULUCF, excluded here by declared scope and from every total

Usage:  python3 scripts/build_btr_comparison.py [--check]
Writes: outputs/pakemis_btr_comparison.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                    # noqa: E402
from pkinv.core.io import read_rows, write_table                       # noqa: E402
from pkinv.paths import DATA, OUTPUTS                                  # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_btr_comparison.csv")
# Reached by the legacy identity its siblings use, which is what data/catalog/assets.csv
# resolves. That registration is not cosmetic: pkinv.report.data_provenance classifies a data
# file by the directory of its LEGACY path, so an unregistered table under
# data/shared/evidence/ classifies "unregistered" while benchmarks.csv beside it classifies
# "hand:parameter" purely because the catalog gives it an identity at data/.
INVENTORY = "btr1_national_inventory.csv"

# The BTR's inventory year, as a PakEmis period. Not a guess: see the module docstring.
MATCHED_PERIOD = "FY2020-21"
CONFIGURATION = "REF_2023_24"
GWP = "AR5"
SOURCE = "Pakistan BTR1 (2024), national inventory 2020-21"

FIELDS = ("btr_codes", "pakemis_codes", "subject", "tier", "btr_Mt_co2e",
          "pakemis_Mt_co2e", "ratio_pakemis_over_btr", "within_0.5_2.0x",
          # THE HARMONISED VIEW (2026-10-08, the 23rd review's item 3). Published
          # BESIDE the as-published pair, never instead of it: the as-published ratio
          # is what the two documents actually say, and the harmonised one is what
          # they would say on one CH4 convention.
          "pakemis_Mt_co2e_ch4_uniform_28", "ratio_ch4_uniform_28",
          "fossil_ch4_share_of_pakemis_pct", "ch4_convention_note", "note")

# (btr codes, pakemis codes, subject, tier, note). Order is the BTR's own table order.
CROSSWALK = [
    (["1.A.1"], ["1.A.1.a"], "Public electricity and heat", "exact", ""),
    (["1.A.2"], ["1.A.2"], "Manufacturing and construction", "exact", ""),
    (["1.A.3"], ["1.A.3.a", "1.A.3.b", "1.A.3.c", "1.A.4.c", "1.A.2/1.A.4.c"],
     "Transport", "aggregate",
     "the BTR publishes 1.A.3 as one line; this inventory splits transport across four codes "
     "plus the unresolved 1A2/1A4c share, so the sum is what faces it"),
    (["1.A.4"], ["1.A.4.b"], "Other sectors", "scope-gap",
     "the BTR's 1.A.4 includes commercial and institutional buildings, which this inventory "
     "declares NE; its off-road share is counted under transport above. The difference is a "
     "declared absence, so no ratio is emitted"),
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
     "direct and indirect managed-soil N2O. FAOSTAT independently gives about twice this "
     "inventory's figure for the same quantity, and the published cause is the dry-climate "
     "EF1 against the 2006 aggregate value"),
    (["3.D"], ["3.C.7"], "Rice cultivation", "exact",
     "CODE SWAP, and it survives the migration in a new form: the BTR books rice at 3.D, while "
     "IPCC 2006 puts rice at 3.C.7 and uses 3.D for the Other block (3.D.1 is harvested wood "
     "products). A join on the code compares rice against harvested wood"),
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
     "THE SAME QUANTITY FILED IN TWO PLACES BY ONE SUBMISSION. The agriculture CRT books crop "
     "residue burning at 3253.17 kt CO2e while the BTR carries it inside cropland, whose "
     "non-CO2 is 3.16 Mt - the same number to within 3 percent. Compared against that, this "
     "inventory's field burning is 0.18 of the submission, not the surplus the earlier "
     "reading implied. Restated and excluded from both totals: 3.B is excluded wholesale by "
     "scope, so counting part of it here would partially re-admit the land block. It is also "
     "the double-count hazard the land lane identified - a PakEmis land layer that adopted "
     "the BTR cropland figure beside this inventory's existing residue burning would count "
     "the burning twice"),
    (["4.A"], ["4.A"], "Solid waste disposal", "exact",
     "read with the solid-waste-fate row below before quoting this: the two accounts route "
     "the same municipal stream differently between disposal and burning"),
    (["4.C.1"], [], "Waste incineration", "btr-only", "4.C.1 is NE here"),
    (["4.C.2"], ["4.C.2"], "Open burning of waste", "exact",
     "read with the solid-waste-fate row below before quoting this"),
    (["4.A", "4.C.1", "4.C.2"], ["4.A", "4.C.2"], "Solid-waste fate (disposal + burning)",
     "aggregate-restated",
     "THE TWO ROWS ABOVE ARE ONE DISAGREEMENT, not two. Taken alone this inventory is 0.49 "
     "of the submission on landfill methane and 17.74 times it on open burning - an apparent "
     "order-of-magnitude error in opposite directions on adjacent categories. Summed over "
     "the solid stream the ratio is 0.68, so what the two accounts mainly disagree about is "
     "the FATE SPLIT of the same waste: how much is collected to a disposal site against how "
     "much is burned where it falls. That is a question about collection statistics, not "
     "about an emission factor, and it is why neither individual ratio should be quoted as a "
     "level error. 4.C.1 is on the BTR side only and is carried here so the sum is complete"),
    (["4.D.1"], ["4.D.1"], "Domestic wastewater", "exact", ""),
    (["4.D.2"], [], "Industrial wastewater", "btr-only", "4.D.2 is NE here"),
]

RATIO_TIERS = ("exact", "aggregate", "aggregate-restated")

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
    agree exactly where both exist - 479.51051 Mt over 22 codes for FY2020-21 - which is the
    check that this is a cheaper route to the same numbers and not a different number.
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


def build():
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
                          "the same number and the harmonised columns repeat the published one")
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

    # THE DECOMPOSITION THAT MATTERS, and the reason this product is not just a ratio table.
    # The headline national ratio mixes two different things: categories the two accounts both
    # estimate and disagree about, and categories one account books and the other declares
    # absent. Separating them answers a question a single ratio cannot - is the national
    # difference an estimation difference or a completeness difference? - and it joins this
    # comparison to the completeness-mass ledger, where those same absences sit without a
    # bound. On this release the answer is that most of the gap is completeness.
    both = [r for r in in_scope
            if r["tier"] in ("exact", "aggregate", "scope-gap")]
    lb = sum(float(r["btr_Mt_co2e"]) for r in both if r["btr_Mt_co2e"] != "")
    lp = sum(float(r["pakemis_Mt_co2e"]) for r in both if r["pakemis_Mt_co2e"] != "")
    only_btr = sum(float(r["btr_Mt_co2e"]) for r in in_scope
                   if r["tier"] == "btr-only" and r["btr_Mt_co2e"] != "")
    # btr-elsewhere is deliberately NOT here. The submission books that mass; it books it
    # inside a block this comparison excludes by scope, which is a boundary asymmetry and not
    # a category the submission omits. Counting it as "estimated here and absent there" would
    # restate the error the reclassification corrected.
    only_pk = sum(float(r["pakemis_Mt_co2e"]) for r in in_scope
                  if r["tier"] in ("pakemis-only", "btr-zero")
                  and r["pakemis_Mt_co2e"] != "")

    # The same two totals on a uniform CH4 = 28, summed from the per-row harmonised column so
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
        "note": "excludes LULUCF (outside this inventory's scope) and the restated "
                "solid-waste-fate row (its parts are already counted). The national "
                "agreement this conceals is the point: the category ratios above span more "
                "than an order of magnitude"})
    rows.append({
        "btr_codes": "", "pakemis_codes": "", "tier": "total",
        "subject": "TOTAL on categories both accounts estimate",
        "btr_Mt_co2e": round(lb, 3), "pakemis_Mt_co2e": round(lp, 3),
        "ratio_pakemis_over_btr": round(lp / lb, 4),
        "within_0.5_2.0x": "YES" if 0.5 <= lp / lb <= 2.0 else "REVIEW",
        "pakemis_Mt_co2e_ch4_uniform_28": round(lp28, 3),
        "ratio_ch4_uniform_28": round(lp28 / lb, 4),
        "fossil_ch4_share_of_pakemis_pct": round(100.0 * (lp - lp28) / 2.0 * 30.0 / lp, 1),
        "ch4_convention_note": CONVENTION,
        "note": "excludes the %.2f Mt the BTR books and this inventory declares NE, and the "
                "%.2f Mt this inventory estimates where the BTR books nothing or zero. On the "
                "categories both accounts actually estimate they agree far more closely than "
                "the headline row above, so most of the national difference is COMPLETENESS "
                "rather than estimation - and those absences are the same rows that sit in "
                "pakemis_completeness_mass.csv without a bound"
                % (only_btr, only_pk)})
    return rows


# write_table takes the banner as a SEQUENCE OF LINES and prefixes each with "# ". Handing it
# one string makes it iterate characters and emit one "# c" line per character, which is how
# the first build of this product came out 300 lines of single letters.
BANNER = (
    "PakEmis against Pakistan's own national submission: year-matched, and reported on",
    "one GWP family (AR5) - but NOT CH4-convention-matched. This inventory weights fossil",
    "CH4 at 30 and biogenic at 28; the BTR prints AR5 CO2e per gas with no fossil split",
    "and no native mass, so its weighting is not recoverable. Each row carries both the",
    "as-published ratio and the ratio at a uniform CH4 = 28. 1.B.2 is where it bites:",
    "96.2 per cent fossil CH4 by CO2e, ratio 7.27 as published and 6.80 harmonised.",
    "The BTR's inventory year 2020-21 is a Pakistani FISCAL year by its own statement, and it",
    "reports on AR5 GWPs, so this comparison needs no calendar blend and no GWP conversion -",
    "the only comparator in this release of which that is true.",
    "A ratio is emitted only for the exact, aggregate and aggregate-restated tiers; see the",
    "builder's docstring for why a join on the IPCC code would be wrong (the two accounts swap",
    "rice cultivation and managed soils).",
    "The restated solid-waste-fate row re-sums categories already counted above and is excluded",
    "from both totals, as a contained claimant is in the completeness-mass ledger.",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = build()
    if args.check:
        current = io.open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        write_table(OUT + ".tmp", FIELDS, rows, banner=BANNER)
        fresh = io.open(OUT + ".tmp", encoding="utf-8").read()
        os.remove(OUT + ".tmp")
        if current != fresh:
            raise SystemExit("outputs/pakemis_btr_comparison.csv is stale")
        print("checked: %d rows" % len(rows))
        return
    write_table(OUT, FIELDS, rows, banner=BANNER)
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
