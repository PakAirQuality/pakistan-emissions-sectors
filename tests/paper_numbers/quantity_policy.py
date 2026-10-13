"""The quantity-protection policy: every printed number is registered or constant.

Split from tests/test_paper_numbers.py in rc35; the shim of that name
re-exports the data and helpers. Test modules import only from the four data
modules (_common, doc_claims, tables, quantity_policy), never from each other.
"""
import collections
import csv
import io
import filecmp
import glob
import json
import math
import os
import re
import sys
import unittest

from pkinv import paths
from pkinv.core.io import read_rows
from paper_numbers._common import (
    DOCS,
    _doc_path)
from paper_numbers.doc_claims import (
    DOC_CLAIMS,
    MOVEMENTS)
from paper_numbers.tables import (
    LABELLED_TABLES,
    TABLES,
    _cell_value,
    _tex_table)


# =========================================================================================
# Coverage: which printed quantities are protected, and which are only protected by memory.
# =========================================================================================
#
# WHY THIS EXISTS. A release-integrity review found the manuscript quoting 81 category-gas
# combinations where the generated table said 82, 39 estimated where it said 40, 88 percent
# of EDGAR where the ratio was 89, and a Monte-Carlo mean of 454.99 against a simulation
# that reports 458.47. Every one of those numbers had been superseded by a run of the engine
# and none of them failed a test - while forty-four OTHER stale numbers in the same documents
# were re-anchored automatically in the same session.
#
# The difference was not importance. It was registration. DOC_CLAIMS and TABLES protect the
# numbers somebody remembered to add, so coverage was a function of memory and the honest
# answer to "what do the manuscript-number tests protect?" was "an unknown subset".
#
# This inverts that. Every printed quantity must be covered, and the exceptions are a
# committed list with a reason on each line. The reviewer's question now has an answer: the
# tests protect every reported quantity, and MANUSCRIPT_CONSTANTS is the audited remainder.
#
# SCOPE is deliberately quantities rather than every digit in the source. A siunitx argument
# or a numeric tabular cell is a reported result; `[3pt]`, `p{0.52\linewidth}`, `CO$_2$` and
# `\citep{pakbur1}` are typesetting and cannot go stale. Restricting to the former keeps the
# test about drift instead of about LaTeX parsing.
#
# COVERED_DOCUMENTS starts at the flagship: 432 quantities across fifteen sections, against
# roughly 6,500 in the nine sector documents. Those are next, and the test takes a document
# list precisely so adding them is a one-line change rather than a rewrite.
COVERED_DOCUMENTS = ("national", "national-supplement", "ippu", "aviation", "fugitives",
                     "waste", "railways", "power", "residential", "transport",
                     "agriculture",
                     # national-v3 joins on 2026-10-07 (the review's item 1). It is the
                     # version going to the journal and roughly 250 printed quantities
                     # checked against nothing, which is where the coal re-base left a
                     # number behind: the paper paired the re-based power reading with the
                     # legacy control's national total while printing the correct one two
                     # sentences earlier. An unswept document is where that happens.
                     "national-v3")


# In-place tier-1 coverage each document must hold, measured at its inclusion commit and
# ratcheted -- never loosened -- afterwards. Pooling all documents into one ratio (the old
# form) would let nine newly included sector papers crush the national bound, or let the
# national paper's quality hide a sector's; each document answers for itself.
TIER1_FLOOR = {"national": 0.75, "national-supplement": 0.95,
               # Measured at inclusion: 245 of 254 quantities resolve in place, 2 are
               # tier-2 repeats and 2 are the constants above. The floor is set just below
               # the measurement, as every other entry here is, and ratchets only upward.
               "national-v3": 0.96,
               "ippu": 0.62, "aviation": 0.90, "fugitives": 0.83, "waste": 0.75,
               "railways": 0.65, "power": 0.56, "residential": 0.73, "transport": 0.82,
               "agriculture": 0.73}


# Sections whose EVERY BYTE is asserted equal to a fresh render of a generator script (the
# test_transport_paper.py / test_waste_paper.py byte-equality modules). That is coverage
# STRONGER than tier 1 -- every cell, not every number -- so the sweep treats their
# quantities as verified rather than demanding duplicate registrations. The backing test
# below fails any entry whose generator does not exist or does not name the section, so an
# exemption cannot outlive its generator.
GENERATED_SECTIONS = {
    ("fugitives", "S6_conditional_table.tex"): "make_fugitives_conditional_table.py",
    ("transport", "S2_factors.tex"): "make_transport_factor_table.py",
    ("transport", "S3_completeness.tex"): "make_transport_completeness_table.py",
    ("transport", "S4_tiers.tex"): "make_transport_tier_table.py",
    ("transport", "S5_classes.tex"): "make_transport_class_table.py",
    ("waste", "S2_tiers.tex"): "make_waste_tier_table.py",
    ("waste", "S3_factors.tex"): "make_waste_factor_table.py",
    ("waste", "S4_completeness.tex"): "make_waste_completeness_table.py",
    ("residential", "S2_factors.tex"): "make_residential_factor_table.py",
    ("residential", "S3_completeness.tex"): "make_residential_completeness_table.py",
    ("residential", "S4_air_matrix.tex"): "make_residential_air_matrix.py",
}


# v1.0.0 Wave 4: the national manuscript's generated tables are STORED QUERIES against the
# semantic release. Every gen_*.tex that paper_national/queries/paper_artefacts.csv lists is
# rendered by scripts/make_paper_artefacts.py from query envelopes and byte-checked by
# tests/paper_numbers/test_paper_artefacts.py, so its digits are verified rather than typed;
# the exemption is read from the registry so a new stored table cannot be forgotten here.
def _stored_query_sections():
    path = os.path.join(paths.ROOT, "paper_national", "queries", "paper_artefacts.csv")
    out = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] == "table" and row["output_file"].startswith("sections/"):
                out[("national", os.path.basename(row["output_file"]))] = "make_paper_artefacts.py"
    return out


GENERATED_SECTIONS.update(_stored_query_sections())


# value -> why it is a constant rather than a result. Anything here is exempt from the
# engine-agreement check, so an entry is a claim that the number cannot go stale.
# Constants EVERY manuscript may cite -- fixed by the assessment reports or by statistics
# itself, never by any one paper's argument. value -> reason.
SHARED_CONSTANTS = {
    "28": "AR5 GWP100 for biogenic CH4 (IPCC AR5 Table 8.7)",
    "30": "AR5 GWP100 for fossil CH4",
    "265": "AR5 GWP100 for N2O",
    "27": "AR6 GWP100 for biogenic CH4 (IPCC AR6 Table 7.15)",
    "273": "AR6 GWP100 for N2O",
    "100": "the GWP time horizon, in years, and the definition of a percentage",
    "10000": "Monte-Carlo iteration count for a sector-scoped run, core.montecarlo.N_ITER",
    "100000": "iteration count for the PUBLISHED national run, "
              "report.uncertainty_all.NATIONAL_N_ITER",
    "42": "the national Monte-Carlo seed, core.montecarlo.SEED",
    "95": "the confidence level every interval in this inventory is reported at",
    "2.5": "the lower percentile of a 95% interval",
    "97.5": "the upper percentile of a 95% interval",
    "1.96": "the standard normal 95% half-width",
    "0.5": "the lower bound of the automatic benchmark review criterion",
    "2.0": "the upper bound of the automatic benchmark review criterion",
    "1": "IPCC Approach 1, and the Tier 1 method label",
    "2": "IPCC Approach 2, and the Tier 2 method label",
    "1.0": "IPCC Vol 2 Ch 1 Table 1.4 oxidation factor, unity for every fuel",
    "12": "months in a reporting period",
    "29.8": "AR6 GWP100 for fossil CH4 (IPCC AR6 Table 7.15)",
}


# (document, value) -> why it is a constant rather than a result, SCOPED to the document
# whose argument quotes it. The old value-keyed dict was a cross-document weakening: a
# railways history figure exempted the same digits in every other paper, and with nine
# sector papers joining the sweep that hole would have grown nine-fold. An entry is still
# a claim that the number cannot go stale -- now it also says where it is allowed to
# appear. (The duplicate "47" key the old dict silently collapsed is resolved here: the
# waste-ratio history entry was dead on arrival and is gone.)
MANUSCRIPT_CONSTANTS = {
    # 88.9 is the GCD-Rice product's OWN reported classification accuracy, cited from its
    # publication (doi:10.57760/sciencedb.21665). It is a property of an external dataset,
    # not of anything this release computes, so there is no output that could make it stale
    # and no getter that would not simply restate a literal held somewhere else. It is cited
    # because a crosscheck instrument's accuracy is what tells the reader how much weight the
    # disagreement carries.
    ("national-v3", "88.9"): "GCD-Rice 2023's own reported classification accuracy, cited",

    # ---- 2026-10-07, the twenty-second review's item 1: national-v3 enters the sweep.
    # Two constants, and only two. Every other printed quantity in v2 resolves against an
    # output - the power control family through national_configurations.csv, the effluent
    # tail and the estimator sweep through their new products, the validation register's
    # counts through the catalog itself, and the sewer-connected-population alternative
    # through the waste engine's own population and sanitation tables.
    #
    # 632.9 describes a VOCABULARY THAT NO LONGER EXISTS. The sentence says that an earlier
    # spatial time-basis vocabulary labelled 196 stream-years and 632.9 Mt in a way that
    # invited the wrong reading. The present registry cannot produce it, because the
    # labelling it measures was replaced - and recomputing it under the new vocabulary would
    # give a different number and quietly change what the sentence claims. A statement about
    # a superseded state belongs here rather than bound to a live output.
    ("national-v3", "632.9"): "the mass an earlier spatial time-basis vocabulary labelled; "
                              "that vocabulary was replaced, so no live output carries it",
    # 99.9 NAMES A PERCENTILE, it is not a measured quantity: "the ensemble's 99.9 per cent
    # point". The point's VALUE is a bound claim; which point it is is the author's choice of
    # where to look, exactly as 97.5 is throughout these documents.
    ("national-v3", "99.9"): "names which percentile is being read, not a measured value; "
                             "the percentile's own value is a bound claim",
    # 5 NAMES A SHARE OF HOUSEHOLDS (rc67): "the top 5 per cent of reporting households hold
    # ...". What they hold in each survey round is a bound claim; which slice of households
    # is read is the diagnostic's own definition, as 99.9 is above.
    ("national-v3", "5"): "names which slice of reporting households is being read, not a "
                          "measured value; the share that slice holds is a bound claim",
    # ---- rc63: the sulfur adoption added NO constants. Every printed quantity in the new
    # supplement passage is a bound claim in doc_claims.py - including the RETIRED furnace-oil
    # central and the ratio it forms with the live one, which are bindable precisely because the
    # retired row was kept in the register rather than deleted. Five figures that no output
    # carries (a superseded level, a before-share, two derived percentages and a transcribed
    # ratio) were removed from the prose instead of parked here: the supplement's tier-1 floor
    # is 0.95, and ten constants would have taken it to 0.74.
    # The spatial-derivation narrative's two historical figures (Wave 5): 91.2 is
    # what the hand-written letter CLAIMED about electricity generation before the
    # class became derived, and 96.59 is the administrative share of the previous
    # release, quoted as the state the facility flip moved away from. Neither is
    # reproducible from the current build by construction.
    ("national", "91.2"): "the hand-written spatial letter's superseded claim",
    # rc65: what the pointer gap read BEFORE the audit looked in the second place a
    # pointer lives. It is the count a defective method produced - every registered
    # source with no pointer in its register row, ignoring the per-row citations the
    # ingests carry - and no output carries it because none should. It is printed so a
    # reader can see the size of the measurement error rather than only the result.
    ("national", "157"): "the pointer gap as a register-only scan reported it, before "
                         "the ingest layer was checked; a superseded measurement",
    # rc64: the width of a grid cell, printed so the reader can see why a station within a
    # kilometre of a district line can land on the wrong side of it. 0.05 degrees of longitude
    # is 5.5 km at Pakistan's latitudes - a property of the grid's DEFINITION, fixed in
    # pkinv.core.gis.grid, not a result of any run. Every other quantity in that passage (77
    # stations, 7 misplaced, 3.4 km, 1.5-10.3 percent) is a bound claim read from the audit.
    ("national", "5.5"): "0.05 degrees of longitude in km; a grid-definition constant",
    # rc64: the 2006 Guidelines' EF3PRP default for cattle, quoted so a reader can see the
    # tenfold cut the 2019 Refinement made to the factor that drives two-thirds of the
    # FAOSTAT managed-soils gap. The repository's parameter register holds the 2019 value
    # (0.002, soils_ef3prp_cattle) because that is what it burns; 0.02 is the COMPARATOR's
    # published default and no output here carries it. The EF1 pair is bound live instead,
    # because the repository prices that one as a scenario.
    ("national", "0.02"): "the 2006 Guidelines' EF3PRP for cattle; the comparator's "
                          "published default, which no output of this build carries",
    # rc60: the two furnace-oil placement figures the results section quotes as HISTORY, beside
    # the live ones the claims registry checks. 17.0 is the unlocated share this release
    # retired, and 1.24 Mt the substituted mass that went with it - both are what the previous
    # release said, and both stopped being reproducible the moment Lal Pir's name was fixed and
    # its GEM point finally matched. Quoting them is the point: the paragraph explains that the
    # share fell without any coordinate being acquired, which cannot be said without the number
    # it fell from.
    ("national", "17.0"): "the previous release's unlocated furnace-oil share, quoted as history",
    ("national", "1.24"): "the previous release's substituted grid mass, quoted as history",
    # and the power paper's own: the uncontrolled screening bound before rc60 narrowed the oil
    # and diesel share of it to the fuel the admission register does not price. The live bound
    # is a registered claim; this token covers the sentence that says what it moved from.
    ("power", "399.4"): "the pre-rc60 uncontrolled screening bound, quoted as history",
    # 2026-10-07: the capacity-proxy error the plant-wise provincial allocation replaced.
    # It measures a proxy that no longer exists in the build, so no getter can read it; it
    # had been covered only as a tier-2 coincidence with an unrelated live value, which the
    # coal re-base broke. Parked here with its reason rather than quietly dropped, because
    # the sentence's point is that the proxy was wrong by a large amount.
    ("power", "7.9"): "the superseded capacity proxy's provincial error, quoted as history; "
                      "the proxy it measures is not in the current build",
    # rc62: the six-product industrial-liquids blend the product split replaced. Quoting it is
    # the point - the sentence explains that furnace oil was riding the geography of fuels it
    # does not burn, which cannot be said without naming the number it was riding.
    ("national", "0.657"): "the superseded all-liquids province blend, quoted as history",
    ("national", "96.59"): "the previous release's administrative share, quoted as history",
    ("national", "29"): "the previous editions' 1A2 residual (~29 Mt), quoted as history "
                        "beside the rc46 activation that halved it to 15.85; the live "
                        "residual is claimed from the fuel ledger, this token covers the "
                        "historical mentions only",
    # rc42 (T-2): the resampling share the previous edition printed from the sum-of-squares
    # arithmetic, quoted beside the covariance-aware figure as the number it replaced.
    ("national", "10.67"): "the previous edition's sum-of-squares resampling share, quoted as history",
    # rc60: the superseded key-category screening's own two row counts. The sentence is about a
    # PREVIOUS edition - it screened the engine's own categories, which split 1.A.2 between the
    # power and industry modules - so neither number is reproducible from this build, by
    # construction. The 19 was passing only by coincidence until rc60: the validation catalogue
    # happened to print the same integer elsewhere in the document, and a collision is not a check.
    ("national", "19"): "the superseded engine-category screening's category-table row count, "
                        "quoted as history beside the 23 it produced",

    # The comparable-sectors artefact's corrected-but-superseded figures (rc20): the
    # eight-sector-restricted first step and full window, quoted as the middle state of
    # a three-step history (defective 77.92 -> restricted 16.83 -> recovered ten-sector
    # 21.92; defective 131.27 -> restricted 80.33 -> recovered 75.33). The restricted
    # numbers describe a scope the recovered panel no longer has, so no current output
    # reproduces them by construction.
    ("national", "16.83"): "the eight-sector-restricted first step, history of the "
                           "comparable_sectors artefact; superseded by the recovered "
                           "ten-sector panel",
    ("national", "80.33"): "the eight-sector-restricted full window, same history; "
                           "superseded by the recovered ten-sector panel",
    # The stale-decomposition incident's headline (rc19): the sentence narrating
    # the gas ledger that printed 455.14 beside the then-current headline quotes
    # that headline as history. The rc19 net-of-leakage re-base moved the live
    # total to 447.72, so the historical 448.00 no longer scores against any
    # registered value; it is the total OF THE RELEASES THE DEFECT SHIPPED IN,
    # reproduced by no current output by construction.
    ("national", "448.00"): "the gross-booking headline of the releases the "
                            "stale gas decomposition shipped against, quoted "
                            "as history in the incident narrative; the rc19 "
                            "reference books net and no current output "
                            "reproduces it",
    # The superseded edition's variance-attribution surface (rc18): the unnamed
    # share before agriculture's factors were named, quoted beside the current
    # 13.5 so the reader sees what the naming moved. No output reproduces a
    # superseded run, and re-deriving it would mean unnaming the parameters.
    ("national", "75.4"): "the unnamed-variance share of the superseded edition, "
                          "quoted as the before of the naming; reproduced by no "
                          "current output by construction",
    ("national", "75"): "the same superseded share, rounded in the points "
                        "arithmetic beside it",
    ("national", "61"): "agriculture's residual points within the superseded "
                        "75.4, same sentence, same reasoning",
    ("national", "0.61"): "agriculture's residual total-effect index in the "
                          "superseded edition, quoted as the before",
    ("national", "81"): "the previous edition's longitudinal row-private "
                        "residual share, quoted as the before of the naming; "
                        "no current output reproduces a superseded run",
    # The month-by-cell ensemble the release deliberately does not build:
    # 10,000 draws x 108 months x 90,780 cells x 3 gases x 4 bytes. Order-of-
    # magnitude arithmetic stated to justify the marginal design; no output
    # reproduces a product that must not exist.
    ("national", "118"): "the infeasibility arithmetic for a month-by-cell "
                         "ensemble, stated to justify the marginal design",
    # The national bound under the WRONG aggregation rule - linear addition of the twenty
    # category intervals - quoted so the sentence can show what deferring to the Monte Carlo's
    # own national row is worth. It describes a method this release rejects, so no output
    # reproduces it and a claim anchor would be meaningless.
    ("national", "22.0"): "the national lower bound that linear cross-category addition "
                          "would give; quoted to show the cost of the wrong correlation "
                          "rule, and reproduced by no output because the rule is not used",
    ("national", "45.3"): "the national upper bound under the same rejected rule, quoted "
                          "in the same sentence for the same reason",
    # The national S3 share BEFORE the spatial class was derived rather than declared,
    # quoted in the same sentence as the current 98.6 so a reader can see that the movement
    # cost no allocation change at all - only the letters were wrong. Same reasoning as the
    # 1.26 below: a claim anchor would update it to the new share and erase the comparison.
    ("national", "86.9"): "the national S3 share the previous release published, quoted as "
                          "history beside the derived 98.6; recomputing it from this "
                          "release would erase the movement the sentence describes",
    # The peak-to-trough ratio BEFORE declared-flat profiles were days-weighted, quoted in
    # the same sentence as the current 1.288 so a reader can see what the correction was
    # worth. It must not track the engine: it is the superseded value, and a claim anchor
    # would silently update it to the new one and erase the movement being described.
    ("national", "1.26"): "the pre-days-weighting monthly peak-to-trough ratio, quoted as "
                          "history beside what days-weighting made of it; no current output "
                          "reproduces it, which is the sentence's point",
    ("national", "131.27"): "the nine-year change AS PUBLISHED BEFORE the trend product was "
                            "restricted to comparable sectors. A statement about a defect that "
                            "has been fixed; the corrected figure is registered as 'trend "
                            "window corrected' and checked against the product",
    ("national", "77.92"): "the first step as published before the same fix - see 131.27",
    ("national", "61.08"): "how much of that 77.92 was two sectors entering the record; the "
                           "difference between two historical figures, not a live one",
    ("national", "39"): "the percentage of the old headline that was scope entry, quoted to "
                        "size a corrected defect. Both figures behind it are historical",
    ("transport", "3.86"): "the FY2021-22 bracket bound offered for the borrowed FY2024-25 "
                           "provincial shape, quoted as history beside the borrowing's "
                           "measured 0.45-point error; the live drift figure is registered "
                           "as 'transport provincial shape bracket'",
    ("national", "41.2"): "the share of nine-year mass that carried NO evidence class before "
                          "this release graded it. A statement about a past state of the "
                          "product, quoted to size what the grading closed; the live split is "
                          "registered as 'evidence share e1'..'e4' and checked against the "
                          "atomic annual table",
    ("national", "1.288"): "the peak-to-trough ratio AFTER days-weighting and BEFORE cement "
                           "took its own fiscal months. It was the current value for several "
                           "releases and is now a middle term of a four-step history "
                           "(1.26 -> 1.288 -> 1.32 -> 1.42); the live ratio is registered as "
                           "'monthly peak trough ratio' and is checked against the engine",
    ("national", "1.32"): "the peak-to-trough ratio after cement took its own fiscal months "
                          "and before the grid's plant-month generation arrived (rc21) - the "
                          "third term of the same four-step history; the live ratio is "
                          "registered as 'monthly peak trough ratio' and is checked against "
                          "the engine",
    # (31 - 28) / 28. A property of the Gregorian calendar, not of Pakistan.
    ("national", "10.7"): "the percentage by which February is shorter than July, the "
                          "arithmetic the days-weighted profile corrects; a calendar "
                          "constant with no output behind it",
    ("waste", "58.2"): "the RETIRED rc11 lognormal surrogate's symmetric band for "
                       "this module, quoted as history beside the injected 92.2; "
                       "no current output reproduces it, which is the sentence's "
                       "point",
    ("waste", "63.5"): "the retired surrogate's national upper arm in Mt, same "
                       "historical quote (the compression the eighth review "
                       "flagged); the current national arm is ~99.3 and is "
                       "claim-anchored",
    # The rc12-era 99/126/27 name-match whitelist entries are DELETED (rc14):
    # the choropleth resolves through the canonical crosswalk now and the caption
    # counts are claim-anchored to the map-audit product instead of whitelisted.
    ("residential", "126"): "the ADM2 boundary layer's polygon count on the "
                            "district map (claim-anchored to the map audit)",
    ("aviation", "40600"): "PCAA's reported FY2023-24 domestic commercial movement "
                           "count, the sector's not-sampled activity control; an "
                           "external report figure, also held in the uncertainty-inputs "
                           "register",
    ("ippu", "9.815266"): "Pakistan's HFC consumption for 2024 as published in the "
                          "national ozone-unit profile, Mt CO2e; an external filing, "
                          "quoted as the magnitude of an NE category",
    ("ippu", "6442"): "the urea production the CRT's own recovery term implies "
                      "(4724.4 kt CO2 x 60/44), kt; derived in prose from the filing to "
                      "show the recovery leg is self-consistent while the activity leg "
                      "is not - it tracks the FILING, not this model",
    ("fugitives", "25.812"): "Pakistan Economic Survey 2025-26 crude oil, million "
                             "barrels FY2023-24; the external report figure the engine's "
                             "converted activity derives from",
    ("fugitives", "1.141"): "Pakistan Economic Survey 2025-26 natural gas, million MMCF "
                            "FY2023-24; external report figure behind the converted "
                            "activity",
    ("fugitives", "9320.69"): "SNGPL Annual Report FY2023-24 transmission km; a utility "
                              "component whose SUM (with SSGCL's 4206) is the engine's "
                              "13526.69 km activity",
    ("fugitives", "4206"): "SSGCL FY2023-24 transmission km; component of the combined "
                           "13526.69 km engine activity",
    ("fugitives", "151419"): "SNGPL FY2023-24 distribution km; component of the "
                             "combined 201230 km engine activity",
    ("fugitives", "49811"): "SSGCL FY2023-24 distribution km; component of the combined "
                            "201230 km engine activity",
    ("fugitives", "91925"): "OGRA FY2023-24 commercial customer count; contextual "
                            "external statistic, not an activity input (the post-meter "
                            "basis is consumption, not meters)",
    ("fugitives", "11318"): "OGRA FY2023-24 industrial customer count; contextual "
                            "external statistic beside the commercial count",
    ("fugitives", "0.85"): "the declared t/m3 density converting OGRA refinery product "
                           "output to IPCC volumetric crude feed; a fixed conversion "
                           "choice documented in the text",
    ("fugitives", "10"): "the declared km radius for matching MARS sources to World "
                         "Bank flares; an analysis choice, not an engine output",
    ("waste", "0.0005"): "IPCC 2006 Vol 5 Ch 6 Table 6.11's published FLOOR of the "
                         "effluent N2O factor range - the transcribed endpoint the rc11 "
                         "bounded draw and the effluent_ef_low scenario both price; the "
                         "scenario row itself is table-checked",
    ("waste", "0.25"): "Table 6.11's published CEILING of the effluent N2O factor range; "
                       "the transcribed upper endpoint behind effluent_ef_high",
    ("waste", "47.8"): "the pre-rc11 published Approach-1 band, quoted as the before "
                       "side of the repair comparison in S1; a historical vintage kept "
                       "deliberately, with the after side claim-checked",
    ("waste", "6.6"): "the 95% fold-span (p97.5/p2.5) of the OLD symmetric lognormal at "
                      "102.6% - exp(2 x 1.96 x 0.482) - quoted as the before side of the "
                      "rc11 repair comparison; the after side (124) is claim-checked "
                      "against the bounded distribution's closed form",
    ("waste", "0.98"): "the Revised 1996 Guidelines' burning oxidation value, quoted in "
                       "a methodological aside about what NOT to apply on top of 2006 "
                       "factors; a literature constant, not an engine result",
    ("railways", "4.06"): "BUR-1's railway figure, Mt CO2e - the OFFICIAL submission "
                          "this paper evaluates; also held in the official-comparison "
                          "output, where the abstract's claim anchors",
    ("railways", "16"): "the MSDS temperature (deg C) at which PSO states HSD specific "
                        "gravity; part of the quoted external specification",
    ("railways", "0.35"): "UIC Rail Diesel Study idle consumption, litres per "
                          "brake-horsepower-hour; literature context for the Tier-2 "
                          "duty-cycle diagnostic",
    ("railways", "4000"): "the locomotive horsepower the UIC figure is quoted for; "
                          "literature context, not an activity input",
    ("railways", "3"): "the span of IPCC Table 3.4.1's rail diesel CO2 factor 95% "
                       "interval (72.6-74.8 about 74.1), quoted from the guidelines "
                       "in percent",
    ("railways", "0.2"): "declared lower bound of the sector-total plausibility test "
                         "(Mt) and of the rail share of national HSD (percent); test "
                         "thresholds, not engine results",
    ("railways", "5"): "declared test thresholds: the two-source agreement tolerance "
                       "and the N2O share floor, both percent",
    ("railways", "10"): "the Euro-V sulfur specification (ppm), the upper "
                        "litres-per-train-km plausibility bound and the passenger "
                        "intensity ceiling (g/pkm); specification values and declared "
                        "bounds",
    ("railways", "99"): "declared floor for diesel's share of traction energy in the "
                        "every-run assertion, percent",
    ("railways", "0.001"): "declared materiality bound for the furnace-oil stream, Mt",
    ("railways", "0.0001"): "the table caption's cutoff for displaying furnace-oil "
                            "rows, Mt; a display threshold",
    ("railways", "1316"): "the diesel implied by the BUR's 56609 TJ at standard NCV, "
                          "kt; derived in prose from the official filing's own numbers",
    ("railways", "18584.4"): "the Initial National Communication's stated total "
                             "energy-sector CO2, Gg; an official filing figure",
    ("railways", "710143"): "AGP audit: litres consumed against quota across six "
                            "formations, FY2023-24; an audit-report figure",
    ("railways", "316664"): "AGP audit: the litre quota those formations held",
    ("railways", "393554"): "AGP audit: litres above per-class trip rations",
    ("railways", "23250"): "AGP audit: litres pilfered from stabled locomotives",
    ("railways", "138587"): "what the misprinted FY2023-24 locomotive cell (136.988 "
                            "read as 136988) makes the detail sum; the anomaly the "
                            "limitations section documents, settled by the next "
                            "edition's restatement",
    ("railways", "140000"): "the rhetorical denominator 'three parts in 140000' for "
                            "the two near-exact year reconciliations",
    ("railways", "79.907"): "Year Book narrative furnace-oil statement, M.T; the "
                            "external cell the unit-ambiguity note quotes",
    ("railways", "15.083"): "Year Book detail-table locomotive furnace oil, thousand "
                            "tonnes reading; external cell under the same ambiguity",
    ("railways", "64.824"): "Year Book detail-table other furnace oil, the companion "
                            "external cell",
    ("power", "6.8"): "the per-energy spread between IPCC bituminous (94.6 kg/TJ x "
                      "25.8 TJ/Gg) and lignite (101.0 x 11.9): a factor-table "
                      "derivation the paper quotes at five sites",
    ("power", "94600"): "IPCC Vol 2 Ch 2 Table 2.2 other-bituminous CO2, kg/TJ",
    ("power", "101000"): "IPCC lignite CO2, kg/TJ",
    ("power", "25.8"): "IPCC Vol 2 Ch 1 Table 1.2 other-bituminous NCV, TJ/Gg",
    ("power", "11.9"): "IPCC lignite NCV, TJ/Gg",
    ("power", "2440"): "bituminous kg CO2 per tonne (94.6 x 25.8), the tab:coals "
                       "derivation",
    ("power", "1200"): "lignite kg CO2 per tonne (101.0 x 11.9), the tab:coals "
                       "derivation",
    ("power", "1.07"): "the per-TJ coal factor ratio (101.0/94.6), tab:coals",
    ("power", "2.03"): "the per-tonne coal factor ratio (2440/1200), tab:coals",
    ("power", "54"): "the NCV difference between the two IPCC coals (1 - 11.9/25.8), "
                     "percent",
    ("power", "5.50"): "the lower end of lignite's published NCV range, TJ/Gg; a "
                       "literature span",
    ("power", "21.6"): "the upper end of lignite's published NCV range, TJ/Gg",
    ("power", "56100"): "IPCC natural-gas CO2 factor, kg/TJ, quoted in the factor "
                        "table",
    ("power", "0.1"): "IPCC stationary-combustion N2O factors quoted in the factor "
                      "table, kg/TJ",
    ("power", "0.98"): "the Revised 1996 oxidation value quoted in the same "
                       "methodological aside as the waste sector's",
    ("power", "900"): "the lower end of Pakistani pipeline-gas heating values, "
                      "Btu/scf; a declared assumption bound",
    ("power", "1000"): "the nominal gas heating value (Btu/scf) and the material-year "
                       "GWh threshold; declared choices",
    ("power", "10"): "approximate NCV-below-gross for natural gas and the "
                     "gross-basis overstatement bound, percent",
    ("power", "11"): "what omitting the net-of-gross step would overstate the "
                     "captive category by, percent; a rounding of 1/0.9",
    ("power", "5"): "approximate gross-basis CO2 overstatement for coal and oil, "
                    "percent",
    ("power", "0.041868"): "the Eurostat/IEA tonne-of-oil-equivalent constant, TJ/t",
    ("power", "35"): "the superseded lignite-share inference this revision replaced; "
                     "quoted as history",
    ("power", "40"): "the superseded inference's uncertainty band (percent) and the "
                     "combined-cycle efficiency at 9000 kJ/kWh; two quoted values "
                     "sharing a string",
    ("power", "324724"): "the CRT's CY2022 solid-fuel activity cell, TJ; an official "
                         "filing figure",
    ("power", "97.57"): "the CRT's implied solid-fuel CO2 factor, t/TJ; official "
                        "filing arithmetic",
    ("power", "46"): "Thar lignite moisture (percent) in the geological literature; "
                     "also the CRT-implied lignite share, which is separately claimed",
    ("power", "6.4"): "Thar lignite ash, percent, from the geological literature",
    ("power", "3030"): "Thar lignite calorific value, kcal/kg, from the geological "
                       "literature",
    ("power", "0.26"): "the lower end of published Thar lignite sulfur, percent",
    ("power", "2.90"): "the upper end of published Thar lignite sulfur, percent",
    ("power", "6.42"): "GSP composite Thar sulfur, percent, quoted from the "
                       "literature",
    ("power", "6.83"): "GSP composite Thar ash alternative, percent",
    ("power", "1100"): "the physical ceiling for coal-combustion carbon intensity, "
                       "g/kWh; a stoichiometric bound",
    ("power", "570"): "the distance between Climate TRACE's two duplicate cement "
                      "rows, km; a data-quality observation",
    ("power", "15000"): "the assumed bagasse heat rate, kJ/kWh; a declared "
                        "assumption",
    ("power", "9000"): "the heat-rate threshold below which only a combined cycle is "
                       "physical, kJ/kWh",
    ("power", "6"): "AP-42 Table 1.1-6 cumulative fraction of filterable mass at or "
                    "below 2.5 microns, percent",
    ("power", "23"): "AP-42 cumulative fraction at or below 10 microns, percent",
    ("power", "253.2"): "the consolidated plant workbook's own grid SO2 for 2024, "
                        "kt; an external computation this layer converges with",
    ("power", "99"): "assumed particulate control efficiency (percent) and the "
                     "ledger coverage rounding; the coverage is separately claimed "
                     "at 99.0",
    ("power", "90"): "assumed sulphur control efficiency, percent",
    ("power", "13"): "the gas-NOx turbine-resolution effect and the share of the "
                     "EDGAR industrial gap the captive category closed; both "
                     "derivations are stated in place",
    ("power", "33"): "EDGAR's 43.98 Mt for 1A2 minus the two metered-gas legs; the "
                     "specifically non-gas remainder, Mt",
    ("power", "12.6"): "what plant-wise assignment moves from Punjab to Sindh "
                       "relative to the proxy, Mt; the same revision record",
    ("power", "3.24"): "the published capacity-proxy share this revision replaced; "
                       "quoted as history",
    ("power", "2.5"): "the parser's per-fuel validation tolerance, percent",
    ("power", "0.2"): "the coal validation agreement, GWh; a parser check threshold",
    ("power", "21.5"): "GW listed in the superseded global power-plant database; "
                       "quoted as history",
    ("power", "45"): "GW actually installed at the time of the revision; context "
                     "for the proxy's staleness",
    ("power", "49.67"): "superseded FY2022-output Punjab share, percent; the S1 "
                        "revision record",
    ("power", "34.22"): "superseded FY2022-output Sindh share, percent",
    ("power", "16.09"): "superseded FY2022-output Balochistan share, percent",
    ("power", "0.02"): "superseded FY2022-output KP share (percent) and the bagasse "
                       "non-CO2 magnitude, which is separately claimed",
    ("power", "32.95"): "the capacity proxy's Punjab share, percent; revision record",
    ("power", "43.61"): "the capacity proxy's Sindh share, percent",
    ("power", "9.20"): "the capacity proxy's Balochistan share, percent",
    ("power", "14.24"): "the capacity proxy's KP share, percent; also quoted in the "
                        "results discussion of the same revision",
    ("power", "9.7"): "FY2022 coal Punjab share in the S1 fuel split, percent; "
                      "revision record",
    ("power", "89.4"): "FY2022 coal Sindh share, percent",
    ("power", "0.8"): "FY2022 coal Balochistan share, percent",
    ("power", "59.8"): "FY2022 gas Punjab share, percent",
    ("power", "22.8"): "FY2022 gas Sindh share, percent",
    ("power", "17.4"): "FY2022 gas Balochistan share, percent",
    ("residential", "39728"): "household electricity, GWh, from the national power "
                              "statistics; quoted context for a stream this sector "
                              "does NOT estimate",
    ("residential", "24.7"): "the upper end of the HIES residue-expenditure price "
                             "bracket, Mt air-dry; a survey-priced bound",
    ("residential", "0.38"): "share of households reporting generator expenses in "
                             "HIES, percent; a survey cell",
    ("residential", "80"): "what Table 2.2's factor would understate household "
                           "methane by relative to Table 2.5 (1 - 5/25), percent; a "
                           "factor-table derivation",
    ("residential", "0.98"): "the Revised 1996 oxidation value, quoted in the same "
                             "aside as the waste and power sectors'",
    ("residential", "56100"): "IPCC natural-gas CO2 factor, kg/TJ, factor table",
    ("residential", "71900"): "IPCC kerosene CO2 factor, kg/TJ, factor table",
    ("residential", "10"): "IPCC Table 2.5 residential kerosene CH4, kg/TJ",
    ("residential", "0.6"): "IPCC Table 2.5 residential N2O factors, kg/TJ",
    ("residential", "3"): "IPCC Table 2.2 kerosene CH4, kg/TJ, shown for contrast",
    ("residential", "0.12"): "declared air-dry moisture of cake and residues; a "
                             "stated conversion choice",
    ("residential", "0.25"): "declared cake ash fraction (dry basis); a stated "
                             "conversion choice",
    ("residential", "0.15"): "declared firewood air-dry moisture; a stated "
                             "conversion choice",
    ("residential", "20"): "the hypothetical error magnitude in the EDGAR scope "
                           "discussion, percent; a rhetorical device",
    ("residential", "11.3"): "BUR-1's agriculture 1A4 component, Mt; an official "
                             "filing figure",
    ("residential", "3.8"): "BUR-1's commercial 1A4 component, Mt; an official "
                            "filing figure",
    ("residential", "288493"): "the CRT's residential gas activity cell, TJ; an "
                               "official filing figure the 1.4 percent claim "
                               "compares against",
    ("residential", "641"): "the CCAC/SEI assessment's national PM2.5 total, kt; an "
                            "external assessment figure",
    ("residential", "35"): "the CCAC assessment's residential share of its national "
                           "total (percent) and the firewood stream's priced "
                           "uncertainty; quoted values",
    ("residential", "0.01"): "the display threshold for minor gas rows, Mt",
    ("residential", "0.05"): "the grid resolution (degrees) and the fossil methane "
                             "magnitude, which is separately claimed",
    ("residential", "150"): "the stated floor for biomass CH4/N2O factor "
                            "uncertainties, percent; the by-stream rows carry the "
                            "exact values",
    ("transport", "10162"): "the superseded PES-derived petrol control (x16/9 defect), kt; the provenance-audit record",
    ("transport", "8820"): "the superseded PES-derived diesel control, kt; the same audit record",
    ("transport", "270"): "the administered petrol price used to price HIES generator expenditure, Rs/litre; an external administered rate",
    ("transport", "0.0999"): "the superseded distance-only off-road weighting; the reweighting record",
    ("transport", "900"): "the lower Pakistani pipeline-gas heating value, Btu/scf; a declared assumption bound",
    ("transport", "1000"): "the nominal gross gas heating value, Btu/scf; a declared assumption",
    ("transport", "0.90"): "the IPCC gross-to-net factor for natural gas; a documented convention (also a provincial magnitude, separately claimed)",
    ("transport", "0.98"): "the Revised 1996 oxidation value, quoted in the same aside as three other sectors",
    ("transport", "74100"): "IPCC diesel CO2 factor, kg/TJ, factor table",
    ("transport", "3.9"): "IPCC Table 3.2.2 road diesel N2O, kg/TJ",
    ("transport", "28.6"): "IPCC Table 3.4.1 rail/off-road N2O, kg/TJ",
    ("transport", "1.6"): "published CNG three-wheeler consumption, MJ/km; a literature rate",
    ("transport", "42.3"): "the previous distance-only edition's two-wheeler share, percent; the revision record",
    ("transport", "21.9"): "the previous edition's two-wheeler CO2, Mt; the same record",
    ("transport", "12.2"): "the share the sector carried under the mixed-vintage denominator; the harmonisation record",
    ("transport", "9128"): "the FY2021-22 OCAC Road petrol row, kt; the demand-peak figure the re-basing left behind",
    ("transport", "7887"): "the FY2021-22 OCAC Road diesel row, kt; same record",
    ("transport", "9.43"): "the share the fuel series predicted for the common period before it was adopted; the harmonisation record",
    ("transport", "9.02"): "the realised common-period share as recorded at harmonisation; the same record",
    ("transport", "43"): "three-wheeler share of CNG energy as recorded from the proxy computation; the published proxy file currently prints a degenerate share set, flagged for the spatial round",
    ("transport", "4.7"): "points the energy weighting moved out of Punjab in the same computation; same flag",
    ("transport", "6.3"): "the resulting Punjab CNG share of road activity; same flag",
    ("agriculture", "0.05"): "the grid resolution, degrees; the product's declared "
                             "geometry",
    ("agriculture", "0.1"): "the South Asian benchmark's grid resolution (degrees) "
                            "and a small percentage aside; external product facts",
    ("agriculture", "55"): "IPCC 2006 T10.10 buffalo enteric CH4 (kg/hd/yr) and the "
                           "Punjab share rounding, the latter separately claimed",
    ("agriculture", "40"): "IPCC factor uncertainties (percent) quoted through the "
                           "factor and TAN tables, and the limitations aside's ~40 Mt",
    ("agriculture", "58"): "IPCC 2006 T10.10 cattle enteric CH4, kg/hd/yr",
    ("agriculture", "46"): "IPCC 2006 T10.10 dairy-cattle enteric CH4, kg/hd/yr",
    ("agriculture", "0.005"): "IPCC EF3 solid/liquid and 2019 EF1 dry and EF4 "
                              "volatilisation defaults, factor-table cells",
    ("agriculture", "0.02"): "IPCC 2006 T10.21 EF3 drylot, kg N/kg N",
    ("agriculture", "1.30"): "IPCC 2006 T5.11 rice baseline EFc, kg/ha/day",
    ("agriculture", "53"): "IPCC T5.11 EFc uncertainty, percent",
    ("agriculture", "1.00"): "IPCC T5.12 SFw continuously flooded scaling",
    ("agriculture", "26"): "IPCC T5.12 SFw uncertainty band, percent",
    ("agriculture", "0.52"): "IPCC T5.12 SFw intermittent-irrigation scaling",
    ("agriculture", "0.004"): "2019 Refinement T11.1 EF1FR flooded rice, kg N2O-N/kg N",
    ("agriculture", "110"): "2019 T11.1 EF1 uncertainty (percent); also a combined "
                            "AD+EF quadrature cell in S3",
    ("agriculture", "120"): "2019 T11.1 EF1FR uncertainty (percent); also an S3 "
                            "quadrature cell",
    ("agriculture", "0.010"): "the 2006 aggregate EF1 default carried as a "
                              "sensitivity, kg N2O-N/kg N",
    ("agriculture", "0.0055"): "Cui et al. 2021 empirical EF1 for Pakistan",
    ("agriculture", "0.011"): "2019 T11.3 EF5 leaching, kg N2O-N/kg N",
    ("agriculture", "0.295"): "the FAOSTAT QCL dairy share splitting the cattle herd; "
                              "a declared parameter also carried in the S2 generator",
    ("agriculture", "0.70"): "the declared warm-zone share for manure-management "
                             "climate blending",
    ("agriculture", "0.16"): "the declared cool-zone MCF blend component",
    ("agriculture", "0.17"): "EMEP buffalo storage TAN fraction, factor-table cell",
    ("agriculture", "0.14"): "EMEP cattle grazing TAN fraction, factor-table cell",
    ("agriculture", "20"): "EMEP TAN-factor uncertainty, percent",
    ("agriculture", "0.007"): "EMEP soil NO factor, kg NO-N per kg N applied",
    ("agriculture", "92"): "EMEP/Akagi residue-burning CO factor, g/kg dry matter",
    ("agriculture", "7.6"): "Akagi 2011 residue PM2.5 factor, g/kg dry matter",
    ("agriculture", "60"): "residue-factor uncertainties (percent) and the "
                           "rice-record matched-district count, the latter "
                           "separately claimed",
    ("agriculture", "1.3"): "Akagi residue NOx factor, g/kg dry matter",
    ("agriculture", "37"): "synthetic fertiliser's share of leached nitrogen in the "
                           "superseded aggregate allocation; the revision record",
    ("agriculture", "21"): "the apparent managed-N volatilisation share before the "
                           "chain alignment; the S5 correction record",
    ("agriculture", "49.5"): "the air-pollutant chain's volatilisation share before "
                             "alignment; the same record",
    ("agriculture", "0.24"): "the CO2e difference between the two NH3 "
                             "representations, Mt; a recorded diagnostic",
    ("agriculture", "2.72"): "manure N reaching soils before the boundary "
                             "correction, Mt N; the S5 record",
    ("agriculture", "2.721"): "the same pre-correction F_ON at three decimals, S5",
    ("agriculture", "0.62"): "what the boundary correction removed, Mt CO2e; S5",
    ("agriculture", "221.71"): "the pre-correction total the S5 note documents, Mt",
    ("agriculture", "221.09"): "the post-correction total of that era, Mt",
    ("agriculture", "221.2"): "the published rc2-era total the S5 note documents; "
                              "quoted as history beside the current 223.3",
    ("agriculture", "784"): "the 1990 NH3 reconstruction value, kt; the trend series "
                            "behind the chart (CSV publication deferred)",
    ("agriculture", "250"): "the 1990 residue-burning CO value, kt; same series",
    ("agriculture", "0.0132"): "the N:C threshold above which net mineralisation "
                               "occurs, IPCC/EMEP residue chemistry",
    ("agriculture", "0.0120"): "cotton residue nitrogen content, fraction",
    ("agriculture", "0.0070"): "rice residue nitrogen content, fraction",
    ("agriculture", "0.0060"): "wheat and maize residue nitrogen content, fraction",
    ("agriculture", "0.0040"): "sugarcane residue nitrogen content, fraction",
    ("agriculture", "0.03"): "what a +50% residue-N sensitivity would add, kt NH3; "
                             "a worked bound",
    ("agriculture", "1.4"): "the benchmark's residues-left-in-field estimate, kt; an "
                            "external inventory figure",
    ("agriculture", "764"): "the SANH benchmark's 2015 interval lower bound, kt",
    ("agriculture", "1322"): "the SANH benchmark's 2015 interval upper bound, kt",
    ("agriculture", "1423"): "this inventory's 2015 parametric interval lower bound, "
                             "kt; recorded from the matched-year run",
    ("agriculture", "2307"): "this inventory's 2015 parametric interval upper bound, "
                             "kt; same record",
    ("agriculture", "295"): "IPCC default buffalo typical mass, kg",
    ("agriculture", "275"): "IPCC default dairy-cattle typical mass, kg",
    ("agriculture", "3.9"): "the maximum implied per-buffalo NH3 the benchmark's "
                            "residual supports, kg/head/yr; the S4 derivation",
    ("agriculture", "6.33"): "the benchmark's own dairy-cattle implied factor, "
                             "kg/head/yr",
    ("agriculture", "9.8"): "this inventory's reference per-buffalo NH3, kg/head/yr; "
                            "recorded implied factor",
    ("agriculture", "9.83"): "the same reference implied factor at two decimals, S4",
    ("agriculture", "11.7"): "the GLEAM-configuration per-buffalo NH3, kg/head/yr",
    ("agriculture", "11.69"): "the same GLEAM implied factor at two decimals, S4",
    ("agriculture", "495.7"): "the benchmark's Pakistan livestock NH3 total, kt; the "
                              "S4 decomposition opening line",
    ("agriculture", "-102.4"): "less broiler chickens, kt; benchmark table cell",
    ("agriculture", "-77.0"): "less commercial layers, kt; benchmark table cell",
    ("agriculture", "-75.9"): "less cattle, kt; benchmark table cell",
    ("agriculture", "-60.2"): "less goats, kt; benchmark table cell",
    ("agriculture", "-42.4"): "less sheep, kt; benchmark table cell",
    ("agriculture", "137.8"): "the benchmark residual unattributed by its published "
                              "table, kt; S4 arithmetic on the cells above",
    ("agriculture", "3.76"): "the residual spread per unattributed head, lower "
                             "reading, kg/head/yr; S4 derivation",
    ("agriculture", "3.87"): "the residual spread per unattributed head, upper "
                             "reading, kg/head/yr",
    ("agriculture", "43"): "combined AD+EF quadrature for cattle enteric, percent; "
                           "S3 worked cell",
    ("agriculture", "56"): "combined quadrature for camels enteric, percent; S3",
    ("agriculture", "101"): "combined quadrature for direct manure N2O, percent; S3",
    ("agriculture", "102"): "combined quadrature cells for indirect and synthetic "
                            "streams, percent; S3",
    ("agriculture", "114"): "combined quadrature for organic and residue soil "
                            "streams, percent; S3",
    ("agriculture", "7.7"): "dry matter reaching the fire before the 0.85 combustion "
                            "factor, Mt; the appendix's worked chain",
    ("agriculture", "7.9"): "excreted N approximation quoted in the appendix "
                            "activity column, Mt; also the AWD delta, separately "
                            "claimed",
    ("national", "0.05"): "the cube's grid resolution, degrees; the product's "
                          "declared geometry",
    ("ippu", "0.05"): "the national cube's grid resolution, degrees, quoted in the "
                      "two-claims spatial statements",
    ("national", "3"): "IPCC Vol 2 Ch 2 Table 2.2 kerosene CH4, kg/TJ",
    ("national", "5"): "IPCC Vol 2 Ch 2 Table 2.5 residential natural-gas CH4, kg/TJ",
    ("national", "10"): "IPCC Vol 2 Ch 2 Table 2.5 residential kerosene CH4, kg/TJ",
    ("national", "3.9"): "IPCC Vol 2 Ch 3 Table 3.2.2 road-diesel N2O, kg/TJ",
    ("national", "28.6"): "IPCC Vol 2 Ch 3 Table 3.4.1 railway-diesel N2O, kg/TJ",
    ("national", "80"): "the CH4 understatement the residential table swap produces, a ratio of the two",
    ("national", "86"): "the N2O understatement the railway table swap produces, a ratio of the two",
    ("national", "99"): "the upper end of the CO2 share of a fossil combustion category",
    ("national", "9"): "the sector-total movement the factor trap produces, and the sector count",
    ("national", "8"): "the lower end of that movement",
    ("national", "0.98"): "the superseded 1996-vintage oxidation factor, quoted to say it is not used",
    ("national", "0.71"): "the waste sector's open-burning oxidation factor, IPCC Vol 5 Ch 5",
    ("national", "6.8"): "the per-terajoule difference between IPCC bituminous and lignite CO2 factors",
    ("national", "54"): "the per-tonne calorific difference between them",
    ("national", "5.50"): "IPCC Vol 2 Ch 1 Table 1.2 lignite NCV lower bound, TJ/Gg",
    ("national", "21.6"): "the same table's lignite NCV upper bound",
    ("national", "900"): "the lower end of the Pakistani pipeline-gas heating-value range, Btu/scf",
    ("national", "1000"): "the upper end, and the reported basis",
    ("national", "4.06"): "BUR-1's railways figure for FY2017-18, Mt CO2e",
    ("national", "144631"): "rail diesel in FY2017, kilolitres, Pakistan Railways Year Book",
    ("national", "132588"): "rail diesel in FY2024, same source",
    ("national", "1280"): "the fuel BUR-1's railways figure would require, kt",
    ("national", "4.0"): "the operator's implied litres per train-km",
    ("national", "46"): "the litres per train-km BUR-1's figure would imply",
    ("national", "33.1"): "Pakistan Railways published train-km, millions",
    ("national", "11.54"): "EDGAR's Pakistani F-gas estimate, Mt CO2e",
    ("national", "756"): "OGRA's fertiliser row, MMCFD, quoted to explain why it is excluded",
    ("national", "39728"): "household electricity, GWh, quoted as an included-elsewhere magnitude",
    ("national", "233"): "FAOSTAT's Pakistani agriculture total, Mt CO2e, in the comparator range",
    ("national", "261"): "EDGAR's, the other end of that range",
    ("national", "37"): "the number of IPCC codes the completeness table spans",
    ("national", "2023"): "quoted in the sector-table caption as the year the SUPERSEDED column printed "
            "for power and aviation, to explain the ambiguity that column carried",
    ("national", "2024"): "the same, for the sectors that numbered the fiscal year by its closing year",
    ("national", "26"): "the number of rows in the benchmark register",
    ("national", "3.81"): "the FY2019-20 fugitives figure a retired output vintage was still quoting in "
            "outputs/ beside the current 24.69; it is history and must not track the model",
    ("national", "34"): "component rows whose declared temporal class the monthly layer moved when the "
          "two were first reconciled; it is history and must not track the current model",
    ("national", "33"): "the 1A2 residual as stated in the previous edition, quoted as history",
    ("national", "38"): "the 1A2 residual as stated in the edition before that",
    ("national", "11.96"): "the road-category band a SUPERSEDED edition printed in prose beside 11.54 in "
             "its table, quoted in the caption to say what the ambiguity was; it is history",
    ("national", "14.24"): "the share of national capacity the RETIRED provincial power proxy gave Khyber "
             "Pakhtunkhwa, quoted to say what the correction removed; it is history",
    ("national", "8.8"): "the megatonnes that correction moved out of the province, at an unchanged total",
    ("national", "18.46"): "the road band the SUPERSEDED single-correlation-group model reported, quoted in "
             "Section 7 to say what the parameter model overturned; it is history",
    ("national", "12.0"): "the road band that same superseded edition reported as its baseline, the other "
            "half of that pair",
    ("national", "1.61"): "the transport correlation ratio AS MEASURED when the stale 'doubles' was found, "
            "quoted in the QA table; it is history and must not track the current model",
    ("national", "104"): "the points by which a table overran the page before the layout guard existed, "
           "quoted in the QA table as the size of the defect; it is history",
    ("national", "1.01"): "the Overseas/Export furnace-oil line of the national petroleum statistics, Mt, "
            "quoted to describe a trap in the source rather than as a result",
    ("national", "1.11"): "commercial trade data's furnace-oil exports for the same period, Mt, the "
            "independent match to that line",
    ("national", "6.9"): "OCAC's Domestic Bunkers diesel row for FY2021-22, kt, the transport paper's "
           "study-year value; the category is screened per edition in "
           "outputs/transport_navigation_screen_2024.csv and remains outside every total",
    ("national", "9100"): "Pakistani ammonia-plant fertiliser production, kt, quoted as available activity "
            "for an NE category",
    ("national", "651"): "Pakistani soda-ash production, kt, the same",
    ("national", "47"): "the inventory's named absences, Mt, rounded; the components are 1A2, F-gases, "
          "the newly declared commercial/institutional floor and the categories listed "
          "beside it in the same paragraph",
    ("national", "0.005"): "the dash threshold of the category x gas table, in Mt, quoted in its caption",
    ("national", "455.14"): "the national total of a SUPERSEDED release, quoted in Section 6 to say what "
              "the stale gas decomposition summed to; it is history and must not move",
}


# THERE IS NO DEBT LIST ANY MORE, AND THAT IS THE POINT OF THIS ROUND.
#
# There was one: COVERAGE_DEBT held quantities printed in the manuscript and checked against
# nothing, keyed "section:value", bounded by two tests - nothing may be added, and an entry
# must be deleted once its quantity is registered. As a way to run down a backlog that is a
# sound discipline, and it worked: the list fell from 59 entries to zero over two rounds.
#
# It was still the wrong shape for a printed number, and an external reviewer found out how.
# The gas-decomposition paragraph in Section 6 - CO2, CH4, N2O and methane's share - sat in
# that list for three releases. It was from a superseded run: its three parts summed to 455.14
# against a printed national total of 448.00, CO2 was wrong by 9.5 Mt, and the methane share
# was wrong by more than a point. Both bounding tests passed the whole time, because NEITHER
# COMPARES A LISTED ENTRY AGAINST ANYTHING. A declared debt reads as "tracked" and behaves as
# "unchecked", and the paper's central methodological claim - that its numbers are read from
# outputs and cannot drift - is exactly what it undermined.
#
# Working the list down found five more stale figures nothing else had caught: waste generation
# and its two partition masses (2.6 percent low, left behind when the population panel moved),
# mixed off-road at 2.77 Mt against a live 1.73, the river-discharge wastewater sensitivity in
# two sections, the fossil-methane share, and a Khyber Pakhtunkhwa provincial share that was
# in fact the "Other" row of the same table.
#
# So the rule is now unconditional: every printed quantity is either registered in DOC_CLAIMS
# or TABLES, or listed in MANUSCRIPT_CONSTANTS with a reason it cannot go stale. There is no
# third state. If a new quantity has no output behind it yet, the answer is to generate one -
# which is what pkinv.report.category_ledger exists for.


def _quantities(doc, section):
    """Every printed quantity in one section, as (value, line).

    A quantity is a siunitx argument or a purely numeric tabular cell. See the note above
    for why the scope is not every digit in the file.
    """
    path = _doc_path(doc, section)
    if not os.path.exists(path):
        return []
    raw = open(path, encoding="utf-8").read()
    out = []
    for lineno, line in enumerate(raw.split("\n"), 1):
        line = re.sub(r"(?<!\\)%.*", "", line)
        for value in re.findall(r"\\SI\{\s*([\d.]+)\s*\}", line):
            out.append((value, lineno))
        for lo, hi in re.findall(r"\\SIrange\{\s*([\d.]+)\s*\}\{\s*([\d.]+)\s*\}", line):
            out += [(lo, lineno), (hi, lineno)]
        for value in re.findall(r"\\num\{\s*([\d.]+)\s*\}", line):
            out.append((value, lineno))
        # N\,\si{unit} - the same quantity written with a manual thin space instead of
        # \SI. The scanner missed it for as long as it has existed, so three printed
        # quantities were outside every guard: two temperature bands in the transport
        # paper and one megatonne figure. A detector blind to a notation measures the
        # notation, not the corpus.
        for value in re.findall(r"([\d.]+)\s*\\,\\si\{", line):
            out.append((value, lineno))
        for lo, hi in re.findall(r"([\d.]+)\s*--\s*([\d.]+)\s*\\,\\si\{", line):
            out += [(lo, lineno), (hi, lineno)]

    text = re.sub(r"(?<!\\)%.*", "", raw)
    offsets = [0]
    for line in raw.split("\n"):
        offsets.append(offsets[-1] + len(line) + 1)
    for m in re.finditer(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", text, re.S):
        pos = m.start(1)
        for chunk in m.group(1).split("\\\\"):
            for cell in chunk.split("&"):
                value = _cell_value(re.sub(r"\\(top|mid|bottom)rule", "", cell))
                if value is not None:
                    lineno = sum(1 for o in offsets if o <= pos)
                    out.append((value, lineno))
            pos += len(chunk) + 2
    return out


def _covered_values(doc, section):
    """Values in one section already checked against the engine, as printed strings."""
    covered = set()
    path = _doc_path(doc, section)
    if os.path.exists(path):
        # RAW text, deliberately. test_every_claim_still_matches_its_output searches the file
        # as written, and DOC_CLAIMS patterns are authored for it -- they carry \s* exactly
        # where a line break falls. Normalising here made the two disagree: a pattern with a
        # literal space where the file has a newline matched nothing in the authoritative
        # test and matched a DIFFERENT quantity here, so the sweep recorded the wrong number
        # as covered and reported the right one as unprotected. One reader, one answer.
        flat = open(path, encoding="utf-8").read()
        for _label, cdoc, csection, pattern, _getter, _tol in DOC_CLAIMS:
            if cdoc != doc or csection != section:
                continue
            m = re.search(pattern, flat)
            if m:
                covered.add(m.group(1))
        # Both ends of a registered movement are checked IN PLACE. Without this the second
        # endpoint scores tier 2 off a same-looking number registered in another section,
        # which is precisely how the conclusion's 11.1 survived beside Table 5's 11.29.
        # MOVEMENTS is authored against NORMALISED text, because that is what
        # TestRestatedMovementsKeepTheirDirection searches. Each registry is read here exactly
        # as its own authoritative test reads it; mixing the two is what caused the defect
        # described above.
        normalised = " ".join(flat.split())
        for _name, mdoc, msection, pattern, _from, _to in MOVEMENTS:
            if mdoc != doc or msection != section:
                continue
            m = re.search(pattern, normalised)
            if m:
                covered.update((m.group(1), m.group(2)))
    # rc42 (M-7): a table joined by label protects its cells exactly as an ordinal one does
    for tdoc, tsection, label, _fn in list(TABLES) + list(LABELLED_TABLES):
        if tdoc != doc or tsection != section:
            continue
        rows = _tex_table(tdoc, tsection, label)
        for row in rows or []:
            covered.update(row)
    return covered


def _document_registered_values(doc):
    """Every value in this document that IS checked against the engine, from any section.

    Generated sections count in full: their bytes equal a fresh render, so a prose repeat
    of one of their cells is a repeat of a verified value."""
    out = set()
    for section in os.listdir(DOCS[doc]):
        if section.endswith(".tex"):
            out |= _covered_values(doc, section)
            if (doc, section) in GENERATED_SECTIONS:
                out |= {value for value, _lineno in _quantities(doc, section)}
    return out
