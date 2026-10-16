"""Category/species coverage across the declared core and configurations.

The completeness register defines the source universe, including estimates,
notation keys and unestimated categories. Each source-category/gas/year cell
retains its evidence, activity status and any declared gap; a ten-module
rectangle does not imply complete national source coverage.

The four integrated household/nitrogen configurations share source coverage and
are implemented for every core fiscal year. Separate source-specific structural
cases in the national case register retain their actual detailed reference-year
scope. The reference year comes from the reporting-window declaration, never
from the latest year present in an extended annual panel. Those cases are
unresolved in other years unless their annual implementation is built; a case
endpoint is not a probabilistic completeness bound.

Writes pakemis_coverage_matrix.csv and pakemis_coverage_summary.csv.
"""
from __future__ import annotations

from pkinv.assets import asset_path

import collections
import csv
import os

from pkinv.paths import OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_coverage_matrix.csv")
SUMMARY = asset_path(OUTPUTS, "pakemis_coverage_summary.csv")

from pkinv.core import configurations as _conf
from pkinv.core.reporting_window import REFERENCE_FY_START
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table
REFERENCE_CONFIGURATION = _conf.REFERENCE

STATES = ("estimated", "interpolated", "held", "screened", "NE", "NO", "IE", "unresolved")

# WHERE A STATE CAME FROM, as a closed vocabulary rather than as a sentence to be parsed.
# NE arrives two ways and they are not the same fact: a category this inventory never
# estimates is NE for good, while a sector-year with no number because its evidence is not
# held is NE until the evidence lands. Both are correctly NE - IPCC has one key for "not
# estimated" - and a reader who wants to count what is closeable needs to tell them apart
# without reading the prose column.
STATE_BASES = ("annual-product-row", "register-notation-key", "sector-year-absent",
               "no-engine-category", "configuration-pricing")

FIELDS = ("period_label", "fiscal_end_year", "ipcc_code", "category", "gas", "sector",
          "configuration_id", "state", "state_basis", "activity_basis", "held_constant",
          "gap_id", "evidence")

# activity_basis (annual product) -> state. A basis this map does not know is a schema
# change, and the builder raises rather than guessing.
BASIS_STATE = {
    "observed": "estimated",
    "change-of-basis": "estimated",
    "reconstructed": "interpolated",
    # Agriculture's history, on Pakistani fiscal activity. The sector word and the three
    # per-category words all land on `estimated` EXCEPT the livestock one: enteric
    # fermentation and manure management ride an inter-census projection rather than an
    # enumeration, which is what `interpolated` has always meant in this column, and rounding
    # them up to `estimated` because their neighbours are would be the exact confusion the
    # per-category basis was introduced to end.
    "reconstructed-fiscal": "estimated",
    "observed_fiscal": "estimated",
    "observed_fiscal_mixed": "estimated",
    "calendar_projection": "interpolated",
    "census_anchored_reconstruction": "interpolated",
}

# WHAT THIS SAID BEFORE WAS FALSE, and it was mine. It read "which the sector engines do
# not support", which is a general excuse where the truth is sector-specific: fugitives
# runs twelve of its thirteen structural scenarios across all nine years, 111 of 117
# scenario-years computing in twelve milliseconds. The engines are not the constraint. The
# constraint is that the per-sector scenario RUNNERS write their alternatives only for the
# reference year, so the national configuration register has one year of deltas to read.
# Saying "unsupported" made an unbuilt product sound like a blocked one.
NOT_PRICED = ("this configuration is priced at the reference year only: its source-specific "
              "annual case has not been built for this cell. The four integrated household/"
              "nitrogen configurations are separate and run over the complete core")

# The greenhouse gases this inventory reports as CO2e. The completeness register's gas
# column is a SLASH-JOINED STRING, not an atomic value - "CO2/CH4/N2O" on 27 rows, and on
# the air rows a seven-species list - so it is split here and filtered to the gases the
# annual product actually carries. Air pollutants are estimated and reported in native
# mass by a separate layer; folding them into a CO2e coverage matrix would count species
# that have no CO2e and make the denominator meaningless.
GHG = ("CO2", "CH4", "N2O", "HFC", "PFC", "SF6")


def _gases(field):
    """The GHG species a completeness row covers, from its slash-joined gas string."""
    return [g for g in (part.strip() for part in field.split("/")) if g in GHG]


def _rows(name):
    return read_rows(asset_path(OUTPUTS, name), comments=False)


def _annual_index(annual):
    """(category, gas, fiscal_end_year) -> the annual product's row."""
    index = {}
    for row in annual:
        if row["grain"] != "category_gas":
            continue
        index[(row["category"], row["gas"], int(row["fiscal_end_year"]))] = row
    return index


def _sector_of(annual):
    """category -> the module that emits it, learned from the annual product itself."""
    out = {}
    for row in annual:
        if row["category"]:
            out.setdefault(row["category"], row["sector"])
    return out


def _series_index(series):
    """(sector, fiscal_end_year) -> the national-series row, for absence and held text."""
    return {(r["sector"], int(r["fiscal_end_year"])): r for r in series}


# IPCC code -> the configurations that price part of it. The screened state was
# module-keyed until Wave 4, which had two defects the code map fixes: the F-gas
# screening (id without the `in_scope` substring) never lit 2.F at all, and any
# module-wide gate lights every NE cell the module owns - a commercial screening
# under a buildings custodian would have flipped residential biogas to screened.
# Both directions are validated: a named configuration that stops shipping fails
# the build, and an `in_scope`/screening configuration missing from this map fails
# it too, so a new screen cannot silently stay invisible to the matrix again.
SCREEN_CONFIGURATIONS = {
    # brick_kiln_coal_in_scope and captive_coal_in_scope retired rc47 Wave 0
    # (their mass entered the reference at the rc46 activation); cement stays,
    # re-priced as the transferred-model EXCESS over the measured series.
    "1.A.2": ("cement_kiln_fuel_in_scope", "bagasse_ceiling_in_scope"),
    "1.A.5.b": ("military_government_in_scope", "general_aviation_in_scope",
                "unresolved_jp1_in_scope"),
    "2.F": ("scope_plus_fgas_screening",),
    "1.A.4.a": ("commercial_institutional_in_scope",),
    "1.B.1": ("coal_mining_fugitives_in_scope",),
    # ammonia_feedstock_in_scope retired rc52: 2.B.1 entered the reference (Tier 1 calibrated)
    "2.B.2": ("nitric_acid_unabated_in_scope", "nitric_acid_abated_in_scope"),
}


def _screened(configurations):
    """IPCC codes carrying a configuration that prices something the reference does not.

    The brick-kiln case is the reason this state came to exist (rc13-rc45: 1.A.2 solid
    fuel was NE and `brick_kiln_coal_in_scope` put a bounded number on part of it - not
    estimated, not unexamined either). That configuration retired at rc47 Wave 0 when the
    measured series entered the reference; the state survives for the claimants that are
    still outside it (the cement-model excess, the bagasse ceiling, and the non-1A2 rows).
    """
    shipped = {c["configuration_id"] for c in configurations}
    mapped = {cid for ids in SCREEN_CONFIGURATIONS.values() for cid in ids}
    missing = mapped - shipped
    if missing:
        raise SystemExit("SCREEN_CONFIGURATIONS names configurations that do not "
                         "ship: %s" % sorted(missing))
    screening_like = {c["configuration_id"] for c in configurations
                      if "in_scope" in c["configuration_id"]
                      or "screening" in c["configuration_id"]}
    unmapped = screening_like - mapped
    if unmapped:
        raise SystemExit("screening configurations invisible to the coverage "
                         "matrix - add them to SCREEN_CONFIGURATIONS: %s"
                         % sorted(unmapped))
    return set(SCREEN_CONFIGURATIONS)


def build():
    completeness = _rows("completeness.csv")
    annual = [r for r in _rows("pakemis_annual_fy2015_16_fy2024_25.csv")
              # rc31: the matrix's frame is the REFERENCE configuration; the S rows
              # carry their own configuration_id and their coverage is the
              # reference's by construction (an engine re-run on the same activity
              # panel), so they are not a second coverage claim to score
              if r.get("configuration_id", REFERENCE_CONFIGURATION)
              == REFERENCE_CONFIGURATION]
    series = _rows("pakemis_national_series.csv")
    configurations = _rows("national_configurations.csv")

    periods = sorted({(int(r["fiscal_end_year"]), r["period_label"]) for r in series})
    by_cell = _annual_index(annual)
    ever_reported = {r["category"] for r in annual if r["category"]}
    sector_of = _sector_of(annual)
    series_at = _series_index(series)
    screened_codes = _screened(configurations)
    reference_year = REFERENCE_FY_START + 1

    # THE REGISTER IS FINER THAN THE PRODUCT, and reading it naively cries wolf. Under one
    # IPCC code the completeness register lists the streams separately - 1.A.4.b carries a
    # row each for piped gas, LPG, kerosene, dung cake, firewood and the rest - but only
    # the first names an engine category, because the annual product reports them summed
    # as "Residential fuel combustion". Taking the blank literally marked 162 estimated
    # cells unresolved. A row with no engine category inherits its CODE's, and says in its
    # evidence that it is reported inside a coarser category rather than separately.
    category_for_code = {}
    for entry in completeness:
        if entry["engine_category"].strip():
            category_for_code.setdefault(entry["code"],
                                         entry["engine_category"].strip())

    # rc17: the sector-4 register rows with no estimated sibling under their own
    # code (4.B, 4.C.1, 4.D) carried a BLANK sector, so the waste module's own
    # completeness views never showed them - an absence hidden from the sector
    # that owns it. The custodial assignment says which module would estimate
    # the category; it does not claim any module computes it (the state does).
    CUSTODIAL_SECTOR = {"4.B": "waste", "4.C.1": "waste", "4.D": "waste",
                        # rc18: aviation's 1.A.5.b row had no sector either,
                        # which is why its three in_scope configurations never
                        # lit the screened state.
                        "1.A.5.b": "aviation"}
    # rc18: code-level inheritance picks the FIRST estimated sibling under a
    # code, and 1.A.2's first sibling is POWER's captive row - so the
    # "Manufacturing - all other" NE cell spent two releases labelled power and
    # the screened state (whose configurations are industry's) never fired for
    # it. A category-level custodial override outranks the sibling inheritance.
    CUSTODIAL_BY_CATEGORY = {
        ("1.A.2", "Manufacturing industries and construction - all other"):
            "industry",
    }

    rows = []
    for year, label in periods:
        for entry in completeness:
          own = entry["engine_category"].strip()
          category = own or category_for_code.get(entry["code"], "")
          rolled_up = bool(category) and not own
          sector = (CUSTODIAL_BY_CATEGORY.get((entry["code"], entry["category"]))
                    or sector_of.get(category, "")
                    or CUSTODIAL_SECTOR.get(entry["code"], ""))
          for gas in _gases(entry["gas"]):
              base = {"period_label": label, "fiscal_end_year": year,
                      "ipcc_code": entry["code"], "category": entry["category"],
                      "gas": gas, "sector": sector,
                      "configuration_id": REFERENCE_CONFIGURATION,
                      "gap_id": entry["gap_id"], "activity_basis": "", "held_constant": ""}
              notation = entry["notation_key"]

              if notation in ("NO", "IE"):
                  rows.append({**base, "state": notation,
                               "state_basis": "register-notation-key",
                               "evidence": entry["justification"][:400]})
                  continue
              if notation == "NE":
                  state = "screened" if entry["code"] in screened_codes else "NE"
                  evidence = entry["justification"][:400]
                  if state == "screened":
                      evidence = ("not estimated, but a bounded configuration prices part "
                                  "of it - see national_configurations.csv. " + evidence)
                  rows.append({**base, "state": state,
                               "state_basis": "register-notation-key",
                               "evidence": evidence})
                  continue

              # notation_key == E: the annual product decides, year by year.
              row = by_cell.get((category, gas, year)) if category else None
              series_row = series_at.get((sector, year)) if sector else None
              held = ""
              if series_row and series_row["held_constant"] not in ("", "not-applicable",
                                                                   "absent"):
                  held = series_row["held_constant"][:300]
              if row is None:
                  gap = entry["gap_id"]
                  why = "no row in the annual product for this category-gas-year"
                  if category and category not in ever_reported:
                      # Not a missing YEAR - a category the product never carries in any
                      # year. LULUCF is the case: the land module estimates forest land
                      # and mangrove blue carbon, and the national total reports
                      # excluding LULUCF by construction, so these cells are outside the
                      # reported boundary rather than absent from it. Saying "no row" of
                      # them would read as a hole in the series, which it is not.
                      why = ("estimated outside the reported national total: %r is "
                             "carried by a module the annual product excludes by "
                             "construction, so no year of it appears here" % category)
                  # A whole module absent for a year is NE, not "unresolved". The
                  # distinction is not cosmetic: unresolved reads as a loose end in a
                  # product that otherwise has a number, while NE is the notation key for
                  # a quantity this inventory does not estimate - which is exactly what an
                  # absent sector-year is. Reporting it as anything softer invites the
                  # opposite error, filling the hole from a neighbouring year, which for
                  # cement would mean reading a silent trade month as zero and biasing the
                  # balance in one direction. The gap travels with the cell.
                  absent_module = (series_row is not None
                                   and series_row["activity_basis"] == "absent")
                  if absent_module:
                      gap = series_row["note"][:120] or gap
                      why = ("the whole %s module is absent in this year, so the category "
                             "is not estimated: %s" % (sector, series_row["note"][:240]))
                  elif not category:
                      why = ("the completeness register marks this E but names no engine "
                             "category, so no module claims it")
                  rows.append({**base, "state": "NE" if absent_module else "unresolved",
                               "state_basis": ("sector-year-absent" if absent_module
                                               else "no-engine-category"),
                               "gap_id": gap, "held_constant": held, "evidence": why})
                  continue
              basis = row["activity_basis"]
              if basis not in BASIS_STATE:
                  raise ValueError("unknown activity_basis %r in the annual product; the "
                                   "coverage matrix must be taught what it means" % basis)
              evidence = "annual product row, source series %s" % row["source_series"]
              if rolled_up:
                  evidence = ("reported inside the coarser engine category %r rather than "
                              "as its own row; %s" % (category, evidence))
              rows.append({**base, "state": BASIS_STATE[basis],
                           "state_basis": "annual-product-row", "activity_basis": basis,
                           "held_constant": held, "gap_id": row["gap_id"],
                           "evidence": evidence})

    # The four implemented configurations have identical category coverage, with
    # different household dung and nitrogen equations. Missing sources stay missing.
    reference_rows = list(rows)
    for configuration_id in _conf.ALL:
        if configuration_id == REFERENCE_CONFIGURATION:
            continue
        rows.extend(dict(row, configuration_id=configuration_id,
                         evidence=row["evidence"] + "; household dung=" +
                         _conf.dung_basis(configuration_id) + "; nitrogen method=" +
                         _conf.nitrogen_method(configuration_id)) for row in reference_rows)

    # Other structural cases retain their explicitly limited reference-year scope.
    estimated_cells = {(r["ipcc_code"], r["category"], r["gas"], r["sector"])
                       for r in rows if r["state"] in ("estimated", "interpolated")}
    for configuration in configurations:
        if configuration["configuration_id"] in _conf.ALL:
            continue
        module = configuration["module"]
        if not module:
            continue                                  # the reference row itself
        for year, label in periods:
            for code, category, gas, sector in sorted(estimated_cells):
                if sector != module:
                    continue
                priced = year == reference_year
                rows.append({
                    "period_label": label, "fiscal_end_year": year, "ipcc_code": code,
                    "category": category, "gas": gas, "sector": sector,
                    "configuration_id": configuration["configuration_id"],
                    "state": "estimated" if priced else "unresolved",
                    "state_basis": "configuration-pricing",
                    "activity_basis": "", "held_constant": "", "gap_id": "",
                    "evidence": ("priced: national total %s Mt under this configuration"
                                 % configuration["national_total_Mt"]) if priced
                                else NOT_PRICED})
    return rows


def summarise(rows):
    counts = collections.Counter((r["fiscal_end_year"], r["state"]) for r in rows
                                 if r["configuration_id"] == REFERENCE_CONFIGURATION)
    years = sorted({y for y, _ in counts})
    out = []
    for year in years:
        total = sum(v for (y, _), v in counts.items() if y == year)
        row = {"fiscal_end_year": year, "cells": total}
        for state in STATES:
            row[state] = counts.get((year, state), 0)
        row["reported_pct"] = round(
            100.0 * (row["estimated"] + row["interpolated"] + row["held"]) / total, 2)
        out.append(row)
    return out


def main():
    rows = build()
    blank = [r for r in rows if not r["state"]]
    if blank:
        raise AssertionError("%d coverage cells carry no state" % len(blank))
    unknown = {r["state"] for r in rows} - set(STATES)
    if unknown:
        raise AssertionError("states outside the closed vocabulary: %s" % sorted(unknown))

    write_table(OUT, FIELDS, rows, extrasaction="ignore")

    summary = summarise(rows)
    write_table(SUMMARY, ["fiscal_end_year", "cells"] + list(STATES)
                                           + ["reported_pct"], summary)

    base = [r for r in rows if r["configuration_id"] == REFERENCE_CONFIGURATION]
    print("coverage matrix -> %s" % OUT)
    print("  %d rows: %d reference-configuration cells over %d years, %d configuration cells"
          % (len(rows), len(base), len(summary), len(rows) - len(base)))
    states = collections.Counter(r["state"] for r in base)
    print("  reference configuration: %s"
          % ", ".join("%s %d" % (s, states[s]) for s in STATES if states[s]))
    print("  reported share by year: %s"
          % ", ".join("%d %.0f%%" % (r["fiscal_end_year"], r["reported_pct"])
                      for r in summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
