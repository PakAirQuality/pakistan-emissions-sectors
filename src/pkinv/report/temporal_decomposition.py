"""Why each flat month is flat: physics, or ignorance, and never the two under one label.

THE PROBLEM THIS SOLVES. Some eighty-five percent of the inventory's mass carries a TE4
monthly profile, and that single number is uninformative to the point of being misleading. A
cow's enteric
fermentation is flat because the animal eats every day; a coal plant's monthly profile is flat
because nobody has read the generation records. Both are TE4, and only the second is a gap. A
reader given the aggregate cannot tell how much of the monthly product is weak and how much is
correct, and neither can a compiler deciding what to acquire next.

So every component is classed on a second axis, orthogonal to the evidence grade:

  continuous_by_process   the emission runs at a rate per unit time and has no within-year
                          event structure. Flat - properly, days-weighted - is the RIGHT
                          answer, and acquiring a monthly series would not change it.
  stock_driven            an exposed stock decays or leaks at a rate set by its size, not by
                          any monthly activity. Landfill methane is the case: since Wave 3
                          the first-order decay runs as one continuous monthly state engine
                          from the 1960 spin-up (swds.monthly_state), and the measured
                          within-year spread is computed into the layer's basis at build -
                          an earlier edition of this docstring quoted a spread no code
                          computed, which is why no number lives here.
  time_variable           the activity genuinely moves within the year. Whether that movement
                          is CARRIED is not a property of the source, so the table does not
                          declare it: the mass of every time-variable component is split into
                          `time_variable_observed` and `time_variable_unobserved` by reading
                          the grade its own months were published with. The unobserved half is
                          the only class that is a gap, and the only one where a flat profile
                          is a weakness rather than a finding.

WHY THE SPLIT IS READ AND NOT WRITTEN DOWN. It used to be written down, and that was wrong in
a way that took an acquisition to expose. `power/Electricity` was declared unobserved; PBS's
plant-month generation then arrived and carried three of the nine years, and the headline did
not move by a thousandth, because the headline was quoting the declaration rather than the
product. A component that is observed in some years and flat in others is the normal case here
- OCAC's panel opens in July 2021, PBS's closes in June 2021 - so a per-component yes-or-no
cannot be right for either. Physics stays declared, because physics does not change when a
spreadsheet is found. Coverage is measured, because it does.

WHAT THIS IS NOT. It is not a way to make the TE4 share look smaller. The physical classes are
assigned from the physics of each source, the shares are computed from the published monthly
product rather than asserted, and the honest headline of this table is the size of
`time_variable_unobserved` - the part that should not be flat and is.

Usage:  python3 -m pkinv.report.temporal_decomposition
Writes: outputs/pakemis_temporal_decomposition.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import collections
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_temporal_decomposition.csv")
MONTHLY = asset_path(OUTPUTS, "pakemis_monthly_fy2015_16_fy2023_24.csv")
SEARCH_LOG = asset_path(DATA, "source_search_log.csv")

FIELDS = ("sector_id", "component", "flatness_class", "flatness_physically_appropriate",
          "activity_should_vary_but_unobserved", "expected_temporal_driver",
          "source_searched", "request_status", "fallback_profile", "evidence_grade",
          "observed_Mt_AR5", "unobserved_Mt_AR5", "months_observed_pct",
          "share_of_sector_pct", "share_of_national_pct", "co2e_Mt_AR5", "basis")

CONTINUOUS = "continuous_by_process"
STOCK = "stock_driven"
TIME_VARIABLE = "time_variable"
UNOBSERVED = "time_variable_unobserved"
OBSERVED = "time_variable_observed"
# What a COMPONENT is classed as - the physics, which the table declares.
PHYSICS_CLASSES = (CONTINUOUS, STOCK, TIME_VARIABLE)
# What MASS is summarised into - the four buckets, two of which are measured from the product.
CLASSES = (CONTINUOUS, STOCK, UNOBSERVED, OBSERVED)
# The grade at which a month is carried on nothing but the calendar.
FLAT_GRADE = "TE4"

# (sector, category prefix) -> (class, expected driver, basis). Assigned from the physics of
# the source, not from what the profile happens to be: the point of the table is that the two
# can disagree, and where they do it is either a finding or a gap.
PHYSICS = {
    ("agriculture", "Enteric"): (
        CONTINUOUS, "none: rumination is continuous",
        "a ruminant emits every day it is alive. The herd is a census stock with no monthly "
        "dimension, and a seasonal profile would be an invention. Days-weighting is the "
        "complete answer here"),
    ("agriculture", "Manure"): (
        CONTINUOUS, "temperature, weakly: storage decay rises with heat",
        "continuous decay of a continuously replenished store. A temperature-driven variant "
        "is defensible and is a profile variant, not a correction"),
    ("agriculture", "Rice"): (
        TIME_VARIABLE, "provincial flooded window",
        "already carried on the crop calendar: flooding starts and drains on dates"),
    ("agriculture", "Managed soils"): (
        TIME_VARIABLE, "fertiliser offtake and application calendar",
        "SPLIT IN TWO, AND ONLY ONE HALF IS TIMED. The synthetic-fertiliser share now rides "
        "NFDC Table 3.4 offtake in all nine years and is fully observed - 90 Mt that was flat "
        "one release ago. It was never blocked by missing data: the annual table claimed "
        "agriculture had no component split before the reference year while the engine was "
        "computing all thirty-five components every run and discarding them, and removing "
        "that false absence was the whole fix. What remains unobserved here is the "
        "DEPOSITED AND APPLIED CENSUS NITROGEN - pasture, organic manure, crop residues - "
        "which rides a livestock count and a harvest rather than a dealer's depot, and which "
        "the offtake shape must never be allowed to reach. The timing target stays the "
        "depot, not the soil"),
    ("agriculture", "Field burning"): (
        TIME_VARIABLE, "VIIRS active-fire acquisition dates (held), FAO calendar as comparator",
        "since rc20 EVERY YEAR's profile IS its own fire record - nine distinct FRP-weighted "
        "monthly shares from the 109,693 held detections, none borrowed between years; T3 "
        "rather than T2 because the two fetched windows are "
        "the calendar's claim; the FAO-calendar crosscheck in monthly_crosschecks.csv "
        "bounds what those windows cannot see (cotton, maize and cane residues)"),
    # rc39 A4: keyed on "Liming" until the category split, while its own driver and basis
    # named the fertiliser calendar and urea offtake - the classification was describing the
    # urea half all along, under the liming half's name. 3.G is NE and has no timing because
    # it has no emission.
    ("agriculture", "Urea application"): (
        TIME_VARIABLE, "urea offtake", "shares the fertiliser calendar"),
    ("waste", "Solid waste disposal"): (
        STOCK, "none: the stock decays continuously",
        "a first-order-decay stock accumulated over decades. Since Wave 3 the FOD "
        "runs as ONE continuous monthly state engine from the 1960 spin-up "
        "(swds.monthly_state): stock flows across fiscal boundaries, each month "
        "deposits its own calendar year's tonnage, and the reaction delay is a "
        "declared parameter. The measured within-year spread is computed into the "
        "layer's own basis string at build - never quoted from prose, which is how "
        "an earlier edition carried 2.3 percent from a computation that did not "
        "exist"),
    ("waste", "Domestic wastewater"): (
        CONTINUOUS, "temperature, through the methane correction factor",
        "load is continuous; the MCF is temperature-dependent, which is a variant worth "
        "publishing and not a gap in activity data"),
    ("waste", "Open burning"): (
        TIME_VARIABLE, "dry-season concentration and municipal collection failure",
        "burning is weather- and collection-driven and the inventory spreads it evenly; the "
        "flat profile is declared a placeholder in the sector's own basis line"),
    ("fugitives", "Gas production"): (
        TIME_VARIABLE, "monthly field gas production",
        "production moves month to month and the emission tracks it. An earlier edition of "
        "this row said PBS does not publish the series monthly; PBS's minerals tables do, and "
        "the upstream streams now ride them (T2) in the five fiscal years the panel covers, "
        "days-weighted T4 in the rest, no year borrowing another's shape"),
    ("fugitives", "Gas gathering"): (
        TIME_VARIABLE, "monthly production entering each gathering system", "as production"),
    ("fugitives", "Sour-gas"): (
        TIME_VARIABLE, "monthly throughput at the sour-gas treatment plants",
        "the CO2 vented when sour gas is sweetened tracks how much sour gas is processed "
        "that month; carried on the PBS gas-production months where the panel covers the "
        "year, as the nearest observed upstream throughput"),
    ("fugitives", "Gas processing"): (
        TIME_VARIABLE, "monthly throughput at processing plants", "as production"),
    ("fugitives", "Gas transmission"): (
        TIME_VARIABLE, "indigenous production plus monthly RLNG send-out", "as production"),
    ("fugitives", "Gas distribution"): (
        TIME_VARIABLE, "utility system throughput and gas sold",
        "supply is not delivery: a production profile applied here would be a named TE3 "
        "alternative at best, never a TE2 reconstruction"),
    ("fugitives", "Post-meter"): (
        TIME_VARIABLE, "monthly consumer-class deliveries", "as distribution"),
    ("fugitives", "Oil production"): (
        TIME_VARIABLE, "monthly crude production", "as gas production"),
    ("fugitives", "Oil refining"): (
        TIME_VARIABLE, "monthly refinery throughput", "as gas production"),
    ("fugitives", "Oil pipeline"): (
        CONTINUOUS, "pipeline length times days",
        "leakage from a pipe is set by how much pipe exists and how long it exists for, not "
        "by what flows through it in a given month. Days-weighting is the physical model"),
    ("power", "Electricity"): (
        TIME_VARIABLE, "plant-month generation by fuel",
        "the monthly fuel mixture moves substantially, so a flat profile misplaces emissions "
        "between high- and low-carbon months. PBS publishes plant-month generation for six of "
        "the nine years and NEPRA's monthly filings cover the rest"),
    ("fugitives", "LNG import terminals"): (
        TIME_VARIABLE, "monthly RLNG terminal receipts",
        "receipts are cargo-driven and lumpy; OGRA publishes monthly RLNG decisions and "
        "recent reports carry terminal receipts"),
    ("power", "Captive gas self-generation"): (
        TIME_VARIABLE, "monthly captive gas deliveries by utility",
        "captive generation follows its host industry, not the grid. The grid profile must "
        "NOT be applied here unless the correspondence is demonstrated, which it is not"),
    ("transport", "Mixed off-road"): (
        TIME_VARIABLE, "a claimant-specific profile: agricultural machinery follows the crop "
                    "calendar and construction plant does not",
        "off-road diesel is carved out of the road total and has no monthly claimant "
        "profile; borrowing the road shape would assert a seasonality nobody has measured"),
    ("railways", "Railway non-traction"): (
        CONTINUOUS, "workshop and power-house activity, weakly",
        "non-traction energy is workshop and yard load, which runs on an operating "
        "timetable rather than a season"),
    ("transport", "Road"): (
        TIME_VARIABLE, "OCAC customer-class monthly sales",
        "carried where the panel reaches; the six years before July 2021 have no panel"),
    ("industry", "Industrial"): (
        TIME_VARIABLE, "OCAC monthly industrial liquids and utility gas deliveries",
        "partly carried: the liquid half rides OCAC where the panel reaches"),
    ("ippu", "Cement"): (
        TIME_VARIABLE, "monthly clinker or cement production",
        "carried in full: all nine fiscal QIM editions are parsed and cement rides its own "
        "year's months everywhere (TE2); the borrowed calendar-2022 shape is a retired "
        "vintage - an earlier edition of this note said the borrowing was current, which "
        "the fifteenth review could have falsified by grep"),
    # rc52: the three IPPU categories that entered the reference
    ("ippu", "Ammonia"): (
        CONTINUOUS, "none: ammonia plants run continuously",
        "a synthesis plant runs base-load between turnarounds; NFDC prints annual production "
        "and no monthly plant record is held, so the declared flat profile (T4) is defended by "
        "the physics rather than observed - a plant-month record would grade it TE2"),
    ("ippu", "Iron and steel"): (
        TIME_VARIABLE, "monthly billets and ingots (PBS QIM)",
        "melt shops follow demand and power availability; carried on the year's OWN QIM billet "
        "months (TE2) wherever the panel covers the year"),
    ("ippu", "Lubricant"): (
        TIME_VARIABLE, "monthly lubricant sales (not published)",
        "oxidation in use follows vehicle and machinery activity, which is seasonal; OCAC's "
        "non-energy sales table is annual, so the flat profile (T4) is a declared gap, not a "
        "physical claim"),
    ("railways", "Railway"): (
        TIME_VARIABLE, "OCAC railway diesel, monthly", "carried where the panel reaches"),
    ("aviation", "Domestic aviation"): (
        TIME_VARIABLE, "OCAC JP-1 monthly", "carried where the panel reaches; movements would be "
                                        "the stronger driver and are not held monthly"),
    ("residential", "Residential"): (
        TIME_VARIABLE, "degree days, per year",
        "carried on ten years of NASA POWER degree days; the heating half is process-driven "
        "and the cooking half is continuous"),
}

# Where the search for each driver stands, from the log rather than from memory.
REQUEST_STATE = {
    "power": ("PBS detail tables ingested for six fiscal years; NEPRA's SIR "
              "Detail-of-Generation LISTING SHEETS parsed at rc21 "
              "(scripts/ingest_sir_generation.py) - the archive's own index carries the "
              "whole plant-month table for FY2021-22..FY2023-24, so grid coal is TE2 and "
              "gas TE3 (annual-control bound) at the reference year; five sheet rows "
              "whose printed Sum fails its own months are arbitrated against the plants' "
              "daily reports in data/activity/power/sir_month_corrections.csv. The "
              "4,644-document daily-PDF archive stays typed per document in "
              "data/manifests/power_sir_document_manifest.csv as the verification "
              "instrument (68 fetched). The archive's GENCO directories "
              "(CPGCL/JPCL/NPGCL) remain the named crosswalk source for the fuel PBS "
              "never labels in FY2016-17/FY2017-18. Residual request: fuel quantities, "
              "definitions, K-Electric own generation (MON-CPPAG-01)",
              "partially_ingested"),
    "fugitives": ("PBS province-month oil and gas production ingested (upstream streams "
                  "TE2 in covered years); OGRA/SNGPL/SSGC network throughput remains "
                  "operationally held only - specific request drafted",
                  "partially_ingested"),
    "ippu": ("PBS QIM monthly cement held and parsed for all nine fiscal editions; own-year\n             months everywhere (TE2)", "ingested"),
    "waste": ("no municipal monthly disposal series sought this pass", "not_attempted"),
    "agriculture": ("NFDC monthly offtake ingested for all nine years; VIIRS fire record "
                    "drives the reference year's burning profile (rc20); crop calendars "
                    "held as comparators", "partially_ingested"),
    "industry": ("OCAC monthly panel held from July 2021", "held_partially"),
    "transport": ("OCAC monthly panel held from July 2021", "held_partially"),
    "railways": ("OCAC monthly panel held from July 2021", "held_partially"),
    "aviation": ("OCAC JP-1 monthly held; PCAA movements not held monthly", "held_partially"),
    "residential": ("NASA POWER degree days retrieved for ten years", "retrieved"),
}


def _monthly_rows():
    return read_rows(MONTHLY, comments=False)


# Sectors whose SEGMENTS live in the subitem rather than the category. Fugitives is one
# category - "Fugitive emissions from oil and gas" - covering production, gathering,
# processing, transmission, distribution, post-meter and LNG terminals, and those segments
# have different physics and different drivers. Classing them together would be exactly the
# single universal gas curve this decomposition exists to refuse.
SEGMENT_SECTORS = ("fugitives",)


def grain_of(row):
    """What a decomposition row is keyed on for this sector."""
    if row["sector_id"] in SEGMENT_SECTORS:
        # strip the trailing gas name: "Gas production CH4" -> "Gas production"
        parts = row["subitem"].rsplit(" ", 1)
        return parts[0] if len(parts) == 2 and parts[1] in ("CH4", "CO2", "N2O") \
            else row["subitem"]
    return row["category"]


def _classify(sector, grain):
    for (sector_key, prefix), value in PHYSICS.items():
        if sector_key == sector and grain.startswith(prefix):
            return value
    return (TIME_VARIABLE, "unassigned",
            "no physical basis recorded for this component - which is itself a finding, "
            "because an unclassified component cannot be defended as correctly flat")


def build(period_id=None):
    """The decomposition over the nine-year product, or over ONE period of it.

    `period_id` restricts the classing to that fiscal year's months (rc41, T-1): the
    reference-year product and the eight historical years carry different evidence, and
    the grade the release sets itself is stated for each."""
    rows = [r for r in _monthly_rows() if period_id is None or r["period_id"] == period_id]
    mass = collections.defaultdict(float)
    flat = collections.defaultdict(float)
    grades = collections.defaultdict(collections.Counter)
    months = collections.defaultdict(set)
    carried_months = collections.defaultdict(set)
    for row in rows:
        key = (row["sector_id"], grain_of(row))
        value = float(row["co2e_Mt_AR5"])
        mass[key] += value
        grades[key][row["temporal_evidence_class"]] += value
        months[key].add(row["month"])
        if row["temporal_evidence_class"] == FLAT_GRADE:
            flat[key] += value
        else:
            carried_months[key].add(row["month"])

    national = sum(mass.values())
    by_sector = collections.defaultdict(float)
    for (sector, _category), value in mass.items():
        by_sector[sector] += value

    out = []
    for key, value in sorted(mass.items(), key=lambda kv: -kv[1]):
        sector, grain = key
        physics, driver, basis = _classify(sector, grain)
        searched, status = REQUEST_STATE.get(sector, ("not recorded", "unknown"))
        dominant = grades[key].most_common(1)[0][0]
        # A component that is physically flat has no gap to measure: its mass is neither
        # observed nor unobserved seasonality, it is correctly aseasonal. Only time-variable
        # mass is split, and it is split by the grade the product actually carries.
        unobserved = flat[key] if physics == TIME_VARIABLE else 0.0
        observed = (value - unobserved) if physics == TIME_VARIABLE else 0.0
        # How much of the calendar the component is carried over at all - a different
        # question from how much of its MASS is carried, and the one that says which years a
        # panel reaches. Road is 36 of 108 months because OCAC opens in July 2021.
        carried = len(carried_months[key])
        out.append({
            "sector_id": sector,
            "component": grain,
            "flatness_class": physics,
            "flatness_physically_appropriate": ("yes" if physics in (CONTINUOUS, STOCK)
                                                else "no"),
            "activity_should_vary_but_unobserved": ("yes" if unobserved > 0 else "no"),
            "expected_temporal_driver": driver,
            "source_searched": searched,
            "request_status": status,
            "fallback_profile": ("days-weighted" if dominant == FLAT_GRADE
                                 else "carried profile"),
            "evidence_grade": dominant,
            "observed_Mt_AR5": round(observed, 5),
            "unobserved_Mt_AR5": round(unobserved, 5),
            "months_observed_pct": round(100.0 * carried / max(len(months[key]), 1), 1),
            "share_of_sector_pct": round(100.0 * value / by_sector[sector], 2),
            "share_of_national_pct": round(100.0 * value / national, 3),
            "co2e_Mt_AR5": round(value, 5),
            "basis": basis,
        })
    return out


def variable_unobserved(period_id=None, rows=None):
    """(moved_Mt, total_Mt, pct): mass that should vary within the year and is carried flat,
    over the nine-year product or over one period of it. The scorecard's outcome-2 metric,
    computed from the same classing the shipped decomposition publishes."""
    rows = build(period_id) if rows is None else rows
    total = sum(float(r["co2e_Mt_AR5"]) for r in rows)
    moved = sum(float(r["unobserved_Mt_AR5"]) for r in rows
                if r["activity_should_vary_but_unobserved"] == "yes")
    return moved, total, (100.0 * moved / total if total else 0.0)


def summary(rows=None):
    """Mass by the four buckets, over the whole nine-year monthly product.

    Two of the four are read off the product rather than declared, so this moves when the
    inventory acquires a monthly series - which is the only reason to publish it.
    """
    rows = rows if rows is not None else build()
    total = sum(r["co2e_Mt_AR5"] for r in rows)
    out = collections.defaultdict(float)
    for row in rows:
        if row["flatness_class"] == TIME_VARIABLE:
            out[OBSERVED] += row["observed_Mt_AR5"]
            out[UNOBSERVED] += row["unobserved_Mt_AR5"]
        else:
            out[row["flatness_class"]] += row["co2e_Mt_AR5"]
    return {k: (v, 100.0 * v / total) for k, v in sorted(out.items())}


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    print("temporal decomposition -> %s" % OUT)
    print("  %d components over the nine-year monthly product" % len(rows))
    for name, (mass, share) in summary(rows).items():
        print("    %-24s %9.1f Mt  %5.1f%%" % (name, mass, share))
    total = sum(r["co2e_Mt_AR5"] for r in rows)
    gap = [r for r in rows if r["unobserved_Mt_AR5"] > 0]
    gap_share = 100.0 * sum(r["unobserved_Mt_AR5"] for r in gap) / total
    print("  THE GAP: %.1f%% of monthly mass should vary within the year and is carried flat"
          % gap_share)
    for row in sorted(gap, key=lambda r: -r["unobserved_Mt_AR5"])[:6]:
        print("    %-12s %-30s %5.2f%% (%3.0f%% of its months carried)  <- %s"
              % (row["sector_id"], row["component"][:30],
                 100.0 * row["unobserved_Mt_AR5"] / total, row["months_observed_pct"],
                 row["expected_temporal_driver"][:44]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
