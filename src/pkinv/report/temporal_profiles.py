"""The temporal profile registry: every month's weight, and what it is evidence OF.

WHY A REGISTRY AND NOT TEN MODULES. The monthly weights lived inside ten sector modules,
which was tolerable while one fiscal year was published: a reader who wanted to know why
February 2024 carried what it carried could read one function. Nine years multiplies that by
nine and adds a second question the code cannot answer at all - is this year's shape this
year's evidence, or last year's shape wearing this year's label? A registry answers both by
writing the weight down beside its provenance, so a profile can be audited without reading
any sector code.

WHAT A ROW MEANS. One row per (profile, sector, component, fiscal year, month):

    monthly emission = annual emission x weight

The weights of a (profile, component, year) sum to exactly one, so the registry can only
decide WHEN, never how much. That is the same contract core/monthly.py enforces per stream;
this is where it is published.

THE TWO AXES THAT ARE NOT THE SAME AXIS. `temporal_evidence_class` says how well the timing
is evidenced. `timing_target` says what the timing is evidence OF - and they come apart
constantly. NFDC's urea offtake is a good monthly administrative series (TE2) of when urea
LEFT THE DEPOT (commodity_offtake), which is not when nitrogen reached a field and is not
when the soil emitted. OCAC's customer-class petroleum is a good series (TE1/TE2) of fuel
SALES, not of combustion. Without the second column, a strong class reads as a strong claim
about the emitting process, and this inventory would be asserting soil chemistry from a
depot ledger.

WHAT IS NOT HERE, DELIBERATELY. No profile is borrowed from another year to fill a year with
no evidence of its own. Six fiscal years have no monthly petroleum series - the OCAC panel
begins in July 2021 - and they carry a days-weighted TE4 profile with observed_month_count
zero, not FY2021-22's shape wearing their label. Days-weighting is not evidence: it is the
correct division of a calendar between months of unequal length, which an equal-twelfths
profile gets wrong by up to 10.7 percent while claiming nothing at all.

Usage:  python3 -m pkinv.report.temporal_profiles
Writes: outputs/pakemis_temporal_profiles.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import collections
import csv
import os
import re

from pkinv.core import evidence, monthly as core_monthly, ocac_monthly, period
from pkinv.paths import OUTPUTS
from pkinv.report import periods
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_temporal_profiles.csv")
ATOM = asset_path(OUTPUTS, "pakemis_atomic_annual.csv")

FIELDS = ("profile_id", "sector", "component_id", "category", "subitem", "gas",
          "fiscal_year", "month", "weight", "temporal_evidence_class", "timing_target",
          "temporal_behavior", "behavior_basis",
          "temporal_status", "source_id", "observed_month_count", "borrowed_from_year",
          "benchmark_method", "profile_variant", "validation_status", "basis")

REFERENCE_VARIANT = "reference"

# The days-weighted fallback, named once. Every stream that reaches it is declaring that it
# has no monthly evidence for this year - which is a statement about the evidence, not about
# the source, and the basis line has to say which.
DAYS_BASIS = ("days-weighted: no monthly series for this stream and year, so the year is "
              "divided by elapsed time rather than into equal twelfths")


class Spec(object):
    """One resolved profile: the twelve weights plus what they are evidence of."""

    def __init__(self, profile_id, weights, classes, timing_target, source_id, basis,
                 observed_month_count=0, borrowed_from_year="", benchmark_method="",
                 validation_status="unvalidated"):
        self.profile_id = profile_id
        self.weights = weights
        self.classes = classes            # {month: TE class}
        self.timing_target = timing_target
        self.source_id = source_id
        self.basis = basis
        self.observed_month_count = observed_month_count
        self.borrowed_from_year = borrowed_from_year
        self.benchmark_method = benchmark_method
        self.validation_status = validation_status


def _te(method_map):
    """T-codes from the sector modules, as the TE codes this product publishes."""
    return {m: evidence.TEMPORAL_TO_EVIDENCE[c] for m, c in method_map.items()}


def _days_spec(fy_start, profile_id="days_weighted", timing_target="stock_exposure",
               basis=DAYS_BASIS, source_id="data/months.csv"):
    weights = core_monthly.days_weighted_profile(fy_start)
    return Spec(profile_id, weights, {m: "TE4" for m in weights}, timing_target,
                source_id, basis)


def _ocac_spec(sector_row, products, fy_start, profile_id, timing_target="fuel_sale"):
    """An OCAC customer-class shape, or None where the panel does not reach the year."""
    try:
        weights, method = ocac_monthly.profile(sector_row, products, fy_start)
    except (KeyError, ValueError):
        return None
    classes = _te(method)
    return Spec(profile_id, weights, classes, timing_target,
                "ocac_sectoral_provincial.csv",
                "OCAC %s customer class, monthly editions differenced" % sector_row,
                observed_month_count=sum(1 for c in classes.values() if c in ("TE1", "TE2")),
                benchmark_method="cumulative differencing where the edition is cumulative")


# --- resolution -------------------------------------------------------------------------
# The shapes come from the SECTOR'S OWN monthly layer, not from a second implementation
# here. Each registered layer already knows how to build its year's profile and what class
# that profile deserves; re-deriving either in this file would be a second arithmetic path
# for the same quantity, which is the failure this repository has watched happen twice with
# declared tables. What this module adds is the metadata the layers have no place for - the
# timing target, the observed-month count, the borrowing - and a days-weighted default for
# every stream and year the layers cannot serve.
#
# Only `share` and `temporal_method` are read from a layer. Its emission columns are
# IGNORED: a layer called for a non-reference year returns that year's shape carried on the
# REFERENCE year's mass, and taking the mass from it would publish FY2023-24 nine times.

_SHAPE_CACHE = {}


def sector_shapes(sector, fy_start):
    """{(category, subitem, gas): {month: (share, T-class)}} for one sector-year.

    Empty where the layer cannot serve the year - a missing OCAC panel, an unheld fertiliser
    annex - which is the caller's signal to fall back to the calendar.
    """
    key = (sector, fy_start)
    if key in _SHAPE_CACHE:
        return _SHAPE_CACHE[key]
    from pkinv.core import registry
    shapes = collections.defaultdict(dict)
    # No catch. This used to swallow everything a layer raised, on the reasoning that a
    # missing panel, an absent annex and an unreadable edition all mean the same thing - no
    # monthly evidence for this sector-year. They do not. A layer that cannot serve one of
    # its streams can usually still serve the others, and the catch turned that into
    # sector-wide silence: agriculture's rice calendar needs no fertiliser annex and was
    # discarded with it for eight of nine years, three percent of the national inventory left
    # flat by an exception handler. Every layer now declares its own absences and returns
    # twelve months for every year, so anything raising here is a defect and should say so.
    _components, month_rows = registry.monthly_layer(sector).rows(fy_start=fy_start)
    for row in month_rows:
        shapes[(row["category"], row["subitem"], row["gas"])][row["month"]] = (
            row["share"], row["temporal_method"], row["basis"])
    _SHAPE_CACHE[key] = dict(shapes)
    return _SHAPE_CACHE[key]


# What a profile is evidence OF, by sector and by what the shape was built from. The OCAC
# panel times fuel SALES; the fertiliser annex times urea leaving a DEPOT; degree days and
# crop calendars time the emitting process itself.
def timing_target_for(sector, category, subitem, classes):
    if set(classes.values()) == {"TE4"}:
        return FALLBACK_TARGET.get(sector, "proxy_only")
    if sector in ("transport", "railways", "power", "industry", "aviation"):
        return "fuel_sale"
    if sector == "ippu":
        return "production"
    if sector == "fugitives":
        # The shaped upstream streams ride PBS production months. A cubic foot produced is
        # not a cubic foot leaked at a metered point, so the strong classes here claim the
        # throughput record, never the emitting process.
        return "production"
    if sector == "agriculture":
        if category.startswith("Rice") or "burning" in category.lower():
            return "emitting_process"
        if "crop residues" in (subitem or ""):
            # the mineralization kernel models the SOIL's nitrogen release after
            # harvest - a process model, not a depot record (Wave 3)
            return "emitting_process"
        return "commodity_offtake"
    return "emitting_process"


# ---------------------------------------------------------------------------
# THE THIRD AXIS: what the PROCESS does in time, as opposed to what the evidence says.
#
# WHY IT HAD TO BE SEPARATE. 80.2 per cent of the monthly product's mass was reported as
# TE4, and that single figure was hiding two unlike populations: 6,132 rows genuinely
# unresolved, and 4,896 rows whose flat, days-weighted profile is close to the PHYSICAL
# TRUTH because the process runs continuously and the activity datum is a stock. A rumen
# emits every day of the year; a landfill decays every day; a city produces sewage every
# day. Calling those "weakly timed" understates the product exactly as badly as calling
# them TE1 would overstate it.
#
# AND WHY IT IS NOT DERIVED FROM timing_target. Deriving one column from another makes the
# new one say nothing that the old one did not, and the temptation here is specific: a rule
# mapping stock_exposure -> continuous would move a third of the inventory's mass out of
# the weakly-timed count in one line, with no new observation and no adjudication. So each
# (sector, category) is decided on its own physics, with the reason written down, and an
# undeclared pair RAISES rather than defaulting - the discipline coverage_matrix.BASIS_STATE
# and longitudinal_uncertainty.GROUP_TYPE already keep.
#
# THE EVIDENCE CLASS DOES NOT MOVE. temporal_evidence_class remains a statement about
# evidence and is untouched by anything here. What this column changes is what the release
# can HONESTLY REPORT: three figures instead of one, so a reader can see which part of the
# product rests on observation, which on defensible physics, and which on neither.
CONTINUOUS = "continuous"          # runs at a near-constant rate; a day is like any other
STOCK_DRIVEN = "stock_driven"      # rate set by an accumulated stock, not a monthly flow
SEASONAL = "seasonal"              # a real annual cycle exists, whether or not it is observed
EVENT_DRIVEN = "event_driven"      # concentrated in short episodes
UNKNOWN = "unknown"                # no defensible statement about its shape in time
BEHAVIORS = (CONTINUOUS, STOCK_DRIVEN, SEASONAL, EVENT_DRIVEN, UNKNOWN)

# Only these two mean "flat is close to right". SEASONAL and EVENT_DRIVEN processes have a
# shape whether or not this inventory observes it, so a flat profile for them is ignorance
# and must count as such.
PHYSICALLY_FLAT = (CONTINUOUS, STOCK_DRIVEN)

# THE REFINEMENT, and the only judgement this module adds. temporal_decomposition.PHYSICS
# already adjudicates every component's physics with a reason - I wrote a second table here
# before finding it, which would have been two registers of one judgement and the exact
# failure this repository has paid for repeatedly. That table is the source; this maps its
# three classes onto the five-word vocabulary the reviewer asked for, and declares the one
# distinction the coarser vocabulary cannot express: which time-variable processes are
# concentrated in episodes rather than spread over a season.
EVENT_DRIVEN_REFINEMENT = {
    ("agriculture", "Field burning"):
        "burning is concentrated in the days after each harvest and is near zero between "
        "them, which is an episode structure rather than a season",
    ("fugitives", "LNG import terminals"):
        "terminal receipts are cargo-driven and lumpy, as the PHYSICS basis line says",
}


def temporal_behavior_for(sector, category, subitem):
    """(behaviour, reason) for one component, DERIVED from the physics table that owns it.

    Deriving from temporal_decomposition.PHYSICS is right where deriving from `timing_target`
    would have been wrong: PHYSICS is itself the physical adjudication, with a written reason
    per component, while timing_target is a statement about the evidence. One is the source of
    this claim; the other only looks like it.

    Its own `grain_of` and `_classify` are reused rather than re-matched here. PHYSICS is keyed
    per STREAM for fugitives ("Gas production", "Oil refining") and per CATEGORY elsewhere,
    and a second matcher in this module would have got that wrong - it did, on the first run.
    Its unclassified default is also kept rather than replaced by a raise: it resolves to
    time-variable, which counts the component as a gap, and defaulting toward "this is a
    weakness" is the safe direction.
    """
    from pkinv.report import temporal_decomposition as decomposition
    grain = decomposition.grain_of({"sector_id": sector, "category": category,
                                  "subitem": subitem})
    physics, _driver, basis = decomposition._classify(sector, grain)
    if physics == decomposition.CONTINUOUS:
        return CONTINUOUS, basis
    if physics == decomposition.STOCK:
        return STOCK_DRIVEN, basis
    for (sector_key, prefix), reason in EVENT_DRIVEN_REFINEMENT.items():
        if sector_key == sector and grain.startswith(prefix):
            return EVENT_DRIVEN, reason
    return SEASONAL, basis


# What a days-weighted fallback is timing, per sector. A landfill and a herd are both
# continuous, but saying so is the difference between "we had no data" and "the source has
# no month", and only the first is a gap.
FALLBACK_TARGET = {
    "waste": "stock_exposure", "fugitives": "stock_exposure",
    "agriculture": "stock_exposure", "aviation": "proxy_only",
    "power": "proxy_only", "industry": "proxy_only", "transport": "proxy_only",
    "residential": "proxy_only", "railways": "proxy_only", "ippu": "proxy_only",
}

# What a layer's own basis line says about which source it used. A sector is NOT one source:
# power reads PBS's plant-month generation in the years the publication reaches and OCAC's
# petroleum panel in the years after it, and a per-sector constant labelled both of them
# OCAC - which is how a test asserting "no OCAC profile before the panel opens" came to fail
# on a PBS profile. The basis is written by the layer that built the shape, so it is what
# gets read.
BASIS_SOURCE = (
    ("PBS Electricity Generation Data", "pbs_electricity_generation_monthly.pdf"),
    # The SIR lane of the same panel (FY2021-22 onward). The basis is written by
    # pbs_generation.shapes() from the rows' own source_file column, so the needle can
    # never match a PBS-lane year.
    ("Detail of Generation listings",
     "sir_companies_20xx_xx.htm (NEPRA SIR Detail-of-Generation plant-month listings)"),
    ("OCAC", "ocac_sectoral_provincial.csv"),
    # The rc30 bagasse lane: the basis names PBS QIM's sugar months, and the needle
    # must be that phrase - a bare sector fallback routed these rows to the OCAC
    # liquids label, which the panel-boundary guard correctly refused.
    ("PBS QIM sugar months", "pbs_qim_month_item.csv (PBS QIM Table 2 sugar group, "
                             "the crushing season)"),
    # Three NFDC lanes, each named by a phrase only its own basis carries. The old
    # bare "NFDC" needle credited Annex-7 on every NFDC basis - including the Table 3.4
    # years that never touched it (Pass 2 Wave 2: the same mislabel class the power
    # lane's needle comment below records).
    ("NFDC Table 3.4", "nfdc_month_product_offtake.csv (Fertilizer Statistics "
                       "Table 3.4, consolidated volume)"),
    ("AFR 2023-24 Annex-5", "nfdc_month_product_offtake.csv (Annual Fertilizer Review "
                            "2023-24 Annex-5, the reference year's own twelve months)"),
    ("NFDC Annex-7", "nfdc_annex7 urea offtake"),
    ("degree day", "monthly_degree_days.csv (NASA POWER)"),
    # Both are PBS QIM, so the needle for the borrowed one must name the VINTAGE and not the
    # publication. Matching on "QIM" alone credited both files on every cement row - naming a
    # source the shape had not been built from, which is exactly the provenance error this
    # table exists to prevent.
    ("own fiscal months", "pbs_qim_month_item.csv (PBS QIM Table 2, nine fiscal editions)"),
    ("PBS monthly provincial", "pbs_minerals_month_province.csv (PBS minerals, monthly "
                               "provincial production)"),
    ("calendar 2022", "cement_monthly_2022.csv (PBS QIM, calendar 2022)"),
    # The old needle here was ("crop calendar", "rice_calendar.csv") and it NEVER
    # matched - the rice basis said "Punjab rice calendar", so every rice row's
    # source_id fell through to the sector fallback and credited the FERTILIZER
    # annex the profile never reads. Found in the Wave-3 survey; the new needle is a
    # phrase only the rice basis carries.
    ("cultivation area-days", "rice_calendar.csv + province_shares.csv (rice_area, "
                              "harvested-area weights)"),
    ("nitrogen-mineralization kernel",
     "fao_crop_calendar harvest windows + residue_params.csv (returned-N weights; "
     "declared e-folding parameter)"),
    # rc20's new profiles, each named by a needle its basis line actually carries
    # (an unrecognised basis falls back to SOURCE_OF, which for industry names the
    # OCAC panel - and mislabelled the QIM-timed gas rows as OCAC in years the
    # panel never reaches, which is exactly what the boundary test caught).
    ("VIIRS active-fire", "firms_fire.csv (NASA FIRMS VIIRS_SNPP_SP detections)"),
    ("QIM billets/ingots and glass-sheet",
     "pbs_qim_month_item.csv (PBS QIM Table 2: billets_ingots + glass_plates_sheets)"),
    ("QIM cement production months",
     "pbs_qim_month_item.csv (PBS QIM Table 2, cement)"),
    ("continuous monthly state engine",
     "swds.monthly_state (one FOD recursion from the 1960 spin-up)"),
)


def source_of(sector, bases):
    """The source id for a spec, from the basis lines its own months carry."""
    found = []
    for basis in sorted(bases):
        for needle, source in BASIS_SOURCE:
            if needle.lower() in basis.lower() and source not in found:
                found.append(source)
    return "; ".join(found) if found else SOURCE_OF.get(sector, "")


# The per-sector fallback, for a layer whose basis names no source this recognises.
SOURCE_OF = {
    "transport": "ocac_sectoral_provincial.csv (Road customer class)",
    "railways": "ocac_sectoral_provincial.csv (Railways customer class)",
    "power": "ocac_sectoral_provincial.csv (Total Power liquids)",
    "industry": "ocac_sectoral_provincial.csv (Total Industry liquids)",
    "aviation": "OCAC JP-1 monthly editions",
    "residential": "monthly_degree_days.csv (NASA POWER)",
    "agriculture": "nfdc_annex7 urea offtake; rice_calendar.csv",
    "ippu": "pbs_qim_month_item.csv (PBS QIM Table 2, nine fiscal editions)",
    "waste": "", "fugitives": "",
}

# A shape carried from another year, READ FROM THE LAYER'S OWN BASIS LINE rather than declared
# per sector here.
#
# WHY IT STOPPED BEING A CONSTANT. `{"ippu": "2022"}` was true while the only QIM edition held
# was a hand-transcribed calendar-2022 window, and it forced every cement row to TE4 - correctly,
# because a shape mapped month-of-year out of another year is borrowed whatever the layer calls
# it. All nine fiscal editions are now parsed, so cement takes each year's own months and the
# borrowing is gone; a per-sector constant would have kept asserting it, and would have held
# cement at TE4 against the evidence. The reverse error is the one to fear more: a constant
# quietly dropped here while some year still borrows would publish TE2 over a borrowed shape.
#
# Deriving it removes both. The layer already writes what it did into its basis, because that
# is the string a reader sees, and a second declaration of the same fact is a second vintage.
BORROWED_MARKER = re.compile(r"borrowed shape", re.I)
BORROWED_YEAR = re.compile(r"calendar\s+(\d{4})", re.I)


def borrowed_year(bases):
    """The year a shape was imported from, or "" - from the layer's own words."""
    for basis in sorted(bases):
        if BORROWED_MARKER.search(basis):
            match = BORROWED_YEAR.search(basis)
            return match.group(1) if match else "unstated"
    return ""


def _atom_rows(path=None):
    return [r for r in read_rows(path or ATOM, comments=False) if r["co2e_Mt_AR5"]]


_CATEGORY_CACHE = {}


def category_shapes(sector, fy_start):
    """{(category, gas): shape} where every subitem under it carries the SAME shape.

    The reference year splits agriculture's categories into components - rice by water
    regime, soils by nitrogen source - and the eight years before it do not: they carry one
    row per category, subitem `(no component split)`, which is 41 percent of the nine-year
    monthly product's mass. A shape keyed on the subitem misses all of it, which is how rice
    came to be TE4 in eight years after its calendar had already been made to serve them.

    The identity requirement is what makes this exact rather than an approximation: if every
    subitem under a category shares one shape, applying that shape to their SUM moves no mass
    anywhere it would not already have gone. Where subitems differ - power's fuels, soils'
    nitrogen sources in a year the annex reaches - there is no category shape and the row
    falls through to the calendar, as it should.
    """
    key = (sector, fy_start)
    if key in _CATEGORY_CACHE:
        return _CATEGORY_CACHE[key]
    grouped = collections.defaultdict(list)
    for (category, _subitem, gas), shape in sector_shapes(sector, fy_start).items():
        grouped[(category, gas)].append(shape)
    out = {}
    for group, shapes in grouped.items():
        first = shapes[0]
        if all(s == first for s in shapes):
            out[group] = first
    _CATEGORY_CACHE[key] = out
    return out


def resolve(row, fy_start):
    """The Spec for one atomic row in one fiscal year. Never None."""
    sector = row["sector_id"]
    shapes = sector_shapes(sector, fy_start)
    shape = shapes.get((row["category"], row["subitem"], row["gas"]))
    if not shape:
        shape = category_shapes(sector, fy_start).get((row["category"], row["gas"]))
    if not shape:
        return _days_spec(fy_start, timing_target=FALLBACK_TARGET.get(sector, "proxy_only"))

    weights = {m: s for m, (s, _c, _b) in shape.items()}
    classes = {m: evidence.TEMPORAL_TO_EVIDENCE[c] for m, (_s, c, _b) in shape.items()}
    bases = {b for (_s, _c, b) in shape.values()}
    borrowed = borrowed_year(bases)
    if borrowed:
        # Borrowed is TE4 by definition, whatever the layer called it.
        classes = {m: "TE4" for m in classes}
    if set(classes.values()) == {"TE4"} and not borrowed:
        # The layer served this stream with its own declared-flat profile; record it as the
        # calendar default so two products cannot describe the same shape differently.
        return _days_spec(fy_start, timing_target=FALLBACK_TARGET.get(sector, "proxy_only"))
    return Spec("%s_%s" % (sector, _slug(row["category"])), weights, classes,
                timing_target_for(sector, row["category"], row["subitem"], classes),
                source_of(sector, bases),
                "shape from the %s monthly layer for this fiscal year" % sector,
                observed_month_count=sum(1 for c in classes.values()
                                         if c in ("TE1", "TE2")),
                borrowed_from_year=borrowed,
                validation_status="crosschecked" if sector in ("agriculture", "residential")
                                  else "unvalidated")


def _slug(text):
    keep = "".join(ch if ch.isalnum() else "-" for ch in text.lower())
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-")


def build(atom=None):
    """One row per (component, fiscal year, month), in atom order."""
    atom = atom if atom is not None else _atom_rows()
    by_period = {r["period_id"]: r for r in periods.rows()}
    out = []
    for row in atom:
        fy_start = int(by_period[row["period_id"]]["fiscal_start_year"])
        spec = resolve(row, fy_start)
        behavior, behavior_reason = temporal_behavior_for(
            row["sector_id"], row["category"], row["subitem"])
        for month in core_monthly.months_for(fy_start):
            out.append({
                "profile_id": spec.profile_id,
                "sector": row["sector_id"],
                "component_id": row["component_id"],
                "category": row["category"],
                "subitem": row["subitem"],
                "gas": row["gas"],
                "fiscal_year": row["period_id"],
                "month": month,
                "weight": "%.12f" % spec.weights[month],
                "temporal_evidence_class": spec.classes[month],
                "timing_target": spec.timing_target,
                # Adjudicated per component from physics, never inferred from the two
                # columns beside it - see TEMPORAL_BEHAVIOR for why that distinction is
                # the whole point of the field.
                "temporal_behavior": behavior,
                "behavior_basis": behavior_reason,
                "temporal_status": "final",
                "source_id": spec.source_id,
                "observed_month_count": spec.observed_month_count,
                "borrowed_from_year": spec.borrowed_from_year,
                "benchmark_method": spec.benchmark_method,
                "profile_variant": REFERENCE_VARIANT,
                "validation_status": spec.validation_status,
                "basis": spec.basis,
            })
    return out


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    print("temporal profile registry -> %s" % OUT)
    print("  %d rows over %d component-years"
          % (len(rows), len({(r["component_id"], r["fiscal_year"]) for r in rows})))
    classes = collections.Counter(r["temporal_evidence_class"] for r in rows)
    print("  class rows: %s" % ", ".join("%s %d" % kv for kv in sorted(classes.items())))
    by_year = collections.defaultdict(collections.Counter)
    for r in rows:
        by_year[r["fiscal_year"]][r["temporal_evidence_class"]] += 1
    for year in sorted(by_year):
        counts = by_year[year]
        total = sum(counts.values())
        evidenced = total - counts["TE4"]
        print("  %s  %4d rows, %5.1f%% carry monthly evidence"
              % (year, total, 100.0 * evidenced / total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
