"""PBS's plant-month generation, as a monthly shape the power layer can apply.

WHY THIS EXISTS AT ALL. Grid electricity was the largest flat item in the inventory - twelve
percent of the mass carried on a days-weighted line - and the layer's own docstring said why:
NEPRA publishes fuel consumed plant by plant for the YEAR, and no plant-month generation series
had been obtained. One had been published all along. PBS's Electricity Generation Data runs
plant by plant and month by month from FY1999-2000 to FY2020-21, which covers six of this
inventory's nine years and exactly the six with no OCAC monthly panel.

WHAT THIS MODULE WILL AND WILL NOT SHAPE.

  * It shapes a subitem in a year only where scripts/ingest_pbs_generation.py measured enough
    of that subitem's annual control inside plants the file actually labels. That measurement
    is in generation_monthly_coverage.csv and it is read, never re-derived: the ingest already
    decided, against the control, whether a shape is worth more than the flat line it replaces.
  * It shapes GENERATION, so the timing target is production - when electricity was made -
    rather than fuel_sale, which is what the OCAC panel times.
  * It never touches captive self-generation. An industrial plant burning its own gas behind
    the meter does not follow national dispatch, and the grid's shape applied to it would be a
    borrowed profile wearing an observed profile's grade.

A SHARE IS NOT AN EMISSION. The annual control is untouched: E(f,m) = E(f,FY) x G(f,m) / SUM
G(f,m), so each subitem's twelve months still sum to exactly the annual figure the inventory
already published. This changes WHEN, never HOW MUCH.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import input_exists as _input_exists
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import os

from pkinv.paths import ROOT

GENERATION = asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv")
COVERAGE = asset_path(ROOT, "data", "activity", "power",
                        "generation_monthly_coverage.csv")

# Mirrors FUEL_GROUPS in scripts/ingest_pbs_generation.py, which is what wrote the coverage
# file this module reads; the fuel words are carried in the file itself so the two cannot
# drift apart silently.
CAPTIVE_CATEGORY = "Captive gas self-generation (1A2)"


def _label(fy_start):
    return "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)


def coverage(fy_start=None):
    """The ingest's own verdict per subitem-year: rows straight out of the file."""
    if not _input_exists(COVERAGE):
        return []
    rows = list(_activity_rows(COVERAGE, comments=False))
    if fy_start is None:
        return rows
    return [r for r in rows if r["fiscal_year"] == _label(fy_start)]


def _generation(fy_start):
    """{fuel word: {month: GWh}} for one fiscal year, labelled plants only."""
    if not _input_exists(GENERATION):
        return {}
    label = _label(fy_start)
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    for row in _activity_rows(GENERATION, comments=False):
        if row["fiscal_year"] != label or not row["fuel"]:
            continue
        out[row["fuel"]][row["month"]] += float(row["gwh"])
    return out


def _source_name(fy_start):
    """The publication behind this year's panel rows, read from the rows themselves.

    The panel carries two lanes - PBS's PDF to FY2020-21, NEPRA's SIR Detail-of-Generation
    listings from FY2021-22 - and the basis line must name the one the year actually came
    from. Deciding by fiscal year would silently mislabel the day either lane's window
    moves, so the answer comes from the rows' own source_file column.
    """
    label = _label(fy_start)
    files = set()
    for row in _activity_rows(GENERATION, comments=False):
        if row["fiscal_year"] == label:
            files.add(row["source_file"])
    sir = {f for f in files if "sir_detail" in f}
    if sir and sir != files:
        raise ValueError("%s mixes source lanes: %s" % (label, sorted(files)))
    if sir:
        return "NEPRA State of Industry, Detail of Generation listings"
    return "PBS Electricity Generation Data"


def shapes(fy_start):
    """{subitem: (shares, temporal_method, basis)} for the subitems this year can carry.

    A subitem the ingest graded TE4 is absent from the result, which is the layer's signal to
    leave it on the profile it already had rather than to invent a weak one.
    """
    graded = [row for row in coverage(fy_start) if row["temporal_class"] != "TE4"]
    if not graded:
        return {}
    generation = _generation(fy_start)
    source = _source_name(fy_start)
    out = {}
    for row in graded:
        months = collections.defaultdict(float)
        for fuel in row["fuel_words"].split("+"):
            for month, gwh in generation.get(fuel, {}).items():
                months[month] += gwh
        total = sum(months.values())
        if total <= 0 or len(months) != 12:
            # The coverage file says this subitem is observed; the generation file must then
            # carry twelve months of it. Silence here would publish a flat line under an
            # observed grade, so it raises.
            raise ValueError(
                "%s %s is graded %s but its generation covers %d months totalling %.3f GWh"
                % (row["fiscal_year"], row["subitem"], row["temporal_class"],
                   len(months), total))
        shares = {month: gwh / total for month, gwh in months.items()}
        out[row["subitem"]] = (
            shares,
            "T2" if row["temporal_class"] == "TE2" else "T3",
            "%s, plant-month generation for %s (%.0f%% of the annual control observed in "
            "labelled plants)"
            % (source, row["fuel_words"].replace("+", " and "),
               100 * float(row["coverage"])),
        )
    return out


def shape_for(component, available):
    """The shape for one component, or None - and never the grid's shape for captive plant.

    A component's subitem carries its gas - "Coal CO2", "Gas N2O" - and the fuel is the part
    in front. The three gases of one fuel are burned in the same boilers in the same months,
    so they share the fuel's shape. The match is on the whole first word or words rather than
    a bare prefix, so that "Captive natural gas CO2" can never be answered by "Gas".
    """
    if component["category"] == CAPTIVE_CATEGORY:
        return None
    for fuel, shape in available.items():
        if component["subitem"].startswith(fuel + " "):
            return shape
    return None


# Public name (rc34): the monthly cross-checks read this across the sector boundary.
generation = _generation
