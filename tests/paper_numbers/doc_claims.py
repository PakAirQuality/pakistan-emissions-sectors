"""DOC_CLAIMS - every printed quantity anchored on the engine - and its getters.

Split from tests/test_paper_numbers.py in rc35; the shim of that name
re-exports the data and helpers. Test modules import only from the four data
modules (_common, doc_claims, tables, quantity_policy), never from each other.
"""

from pkinv.assets import asset_path
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
from pkinv.report.artifact_inventory import as_a_reader_sees_it
from paper_numbers._common import (
    OUT,
    ROOT,
    _cell,
    _csv_rows,
    _data_rows,
    _data_rows_nocomment,
    _first_where,
    _max_where,
    _min_where,
    _rows,
    _rows_banner,
    _sector,
    _sector_alt,
    _sector_row,
    _sum_prefix,
    _sum_where,
    _transport_year,
    _waste_year)


def _product_fact(fact_id):
    """One authoritative answer per fact about the shape of the release.

    An external reviewer graded the monthly product D because the supplement said a 108-month
    product did not exist. It does, and had for several releases. Every count a manuscript
    makes about the SHAPE of this release now resolves through outputs/pakemis_product_facts.csv
    so a sentence and a product cannot disagree in silence again - in either direction.
    """
    row = next(r for r in _csv_rows("pakemis_product_facts.csv") if r["fact_id"] == fact_id)
    return float(row["value"])


def _ocac_parse_fact(column):
    """One column of the OCAC parse's single summary row.

    The summary exists so that a count printed in the paper carries its denominator and its
    positive control from the same run that produced it. Reading them back through here means
    a re-parse that changed any of the five numbers fails the claim rather than leaving the
    paragraph quietly describing an older run.
    """
    rows = _csv_rows("ocac_parse_summary.csv")
    assert len(rows) == 1, "ocac_parse_summary.csv is a one-row accounting, not a table"
    return float(rows[0][column])


def _cement_shape_ratio(which):
    """Peak-to-trough of a cement monthly shape, computed from the shape itself.

    Both ratios in the sentence are live: `own` is what the reference year's QIM months give,
    `borrowed` is what the calendar-2022 window it replaced gave. Neither is retyped, so the
    claim that borrowing overstated the seasonality cannot survive the shapes changing.
    """
    from pkinv.sectors.ippu import monthly as ippu_monthly
    shares = (ippu_monthly.shape()[0] if which == "own"
              else ippu_monthly.borrowed_shape())
    return max(shares.values()) / min(shares.values())


def _managed_soils_observed():
    """Mt of managed-soils mass whose within-year variation is carried by an observed series.

    Read from the decomposition rather than retyped, so the sentence claiming 90.3 Mt moved
    cannot outlive the movement. The paragraph quotes the CHANGE, and the change is this
    figure minus the 12.2 Mt the category carried before the annual grain was corrected -
    that earlier value is a historical constant and is exempted with its reason.
    """
    row = next(r for r in _csv_rows("pakemis_temporal_decomposition.csv")
               if r["component"] == "Managed soils")
    return float(row["observed_Mt_AR5"]) - 12.2


def _agriculture_series_cells():
    """(year, category, gas) cells the atom's agriculture subitems are re-aggregated against."""
    from pkinv.sectors.agriculture import fiscal_series
    return float(sum(len(cells) for cells in fiscal_series.series_by_gas().values()))


def _era5_by_city():
    """{city: [(era5 C, nasa power C)]} from the published cross-check.

    Computed here rather than imported from scripts/: this module does not put scripts/ on
    the path, and a getter that depends on it fails as an ERROR rather than a mismatch, which
    reads like a broken test instead of a moved number.
    """
    out = collections.defaultdict(list)
    for row in _csv_rows("era5_degree_day_crosscheck.csv"):
        out[row["city"]].append((float(row["era5_t2m_C"]), float(row["nasa_power_t2m_C"])))
    return out


def _era5_correlation(which):
    values = []
    for series in _era5_by_city().values():
        ours = [a for a, _b in series]
        theirs = [b for _a, b in series]
        mean_ours, mean_theirs = sum(ours) / len(ours), sum(theirs) / len(theirs)
        numerator = sum((a - mean_ours) * (b - mean_theirs) for a, b in zip(ours, theirs))
        denominator = ((sum((a - mean_ours) ** 2 for a in ours)
                        * sum((b - mean_theirs) ** 2 for b in theirs)) ** 0.5)
        values.append(numerator / denominator if denominator else 0.0)
    return min(values) if which == "min" else max(values)


def _era5_offset(which):
    """Smallest or largest per-city level offset, as a positive magnitude."""
    values = [abs(sum(a - b for a, b in series) / len(series))
              for series in _era5_by_city().values()]
    return min(values) if which == "min" else max(values)


def _era5_months():
    return float(len({r["month"] for r in _csv_rows("era5_degree_day_crosscheck.csv")}))


def _apcma_fact(which):
    rows = _csv_rows("apcma_qim_cement_crosscheck.csv")
    if which == "months":
        return float(len(rows))
    return sum(abs(float(r["difference_pp"])) for r in rows) / len(rows)


def _apcma_defect(which):
    """The two halves of APCMA's published digit-grouping error, read from the quarantine.

    Not exempted as constants: they are numbers a live parse recovers from the page every run,
    and if the association ever corrects the page this claim should fail rather than keep
    describing a defect that is gone.
    """
    for row in _csv_rows("apcma_dispatch_quarantine.csv"):
        if row["scope"] == "column" and row["column"] == "South export" \
                and row["fiscal_year_start"] == "2015":
            return float(row["months_sum"] if which == "months" else row["printed"])
    raise AssertionError("the APCMA South-export column defect is no longer in the quarantine")


REPORTED_SCENARIO = "parameter_typed"   # the paper's "typed from the parameter graph"


def _trend_rows():
    return [r for r in _csv_rows("pakemis_trend_uncertainty.csv")
            if r["scenario"] == REPORTED_SCENARIO]


def _trend_pair(kind, field="difference_Mt"):
    row = next(r for r in _trend_rows() if r["pair_kind"] == kind)
    return float(row[field])


def _sector_uncertainty(sector):
    """One sector's published 95% uncertainty, from the national roll-up it ships in."""
    row = next(r for r in _csv_rows("national_all_sectors.csv")
               if r["row_kind"] == "sector" and r["sector"] == sector)
    return float(row["uncert_pct_95"])


def _limestone_fact(which):
    rows = _csv_rows("limestone_qim_cement_crosscheck.csv")
    clean = [abs(float(r["difference_pp"])) for r in rows if not r["flag"]]
    if which == "mean":
        return sum(clean) / len(clean)
    flagged = [r for r in rows if r["flag"]]
    return 100.0 * float(flagged[0]["limestone_share"])


def _fugitives_moved():
    """Mt of fugitive mass the production wiring moved to observed, from the decomposition."""
    upstream = ("Gas production", "Gas gathering", "Gas processing", "Sour-gas processing",
                "Oil production")
    return sum(float(r["observed_Mt_AR5"])
               for r in _csv_rows("pakemis_temporal_decomposition.csv")
               if r["sector_id"] == "fugitives" and r["component"] in upstream)


def _fugitives_t2_share():
    """T2 share of the fugitives reference-year monthly layer, from the layer itself."""
    import collections
    masses = collections.Counter()
    for row in _csv_rows("fugitives_monthly_2024.csv"):
        masses[row["temporal_method"]] += float(row["co2e_Mt_AR5"])
    return 100.0 * masses["T2"] / sum(masses.values())


def _coverage_summary():
    return _csv_rows("pakemis_monthly_coverage_summary.csv")


def _coverage_share(which):
    """Observed (TE1+TE2) or flat (TE4) share of the nine-year mass, from the 108-month report.

    Summed from the published rows rather than read off a stored percentage, so the sentence
    and the table cannot drift: if the report changes, the claim moves with it.
    """
    rows = _coverage_summary()
    total = sum(float(r["co2e_Mt_AR5"]) for r in rows)
    if which == "observed":
        part = sum(float(r["TE1_Mt"]) + float(r["TE2_Mt"]) for r in rows)
    else:
        part = sum(float(r["TE4_Mt"]) for r in rows)
    return 100.0 * part / total


def _coverage_share_before_or_after_the_panel(side):
    """The concentration the single figure hides: observed share before and after July 2021."""
    rows = _coverage_summary()
    keep = [r for r in rows
            if (r["period_id"] < "FY2021-22") == (side == "before")]
    total = sum(float(r["co2e_Mt_AR5"]) for r in keep)
    part = sum(float(r["TE1_Mt"]) + float(r["TE2_Mt"]) for r in keep)
    return 100.0 * part / total


def _evidence_share(grade):
    """Share of the nine-year mass at one evidence class, from the atomic annual table."""
    rows = [r for r in _csv_rows("pakemis_atomic_annual.csv") if r["co2e_Mt_AR5"]]
    total = sum(float(r["co2e_Mt_AR5"]) for r in rows)
    part = sum(float(r["co2e_Mt_AR5"]) for r in rows if r["evidence_class"] == grade)
    return 100.0 * part / total


def _qim_parse_fact(column):
    """One column of the PBS QIM parse's single summary row - same contract as the OCAC one."""
    rows = _csv_rows("pbs_qim_parse_summary.csv")
    assert len(rows) == 1, "pbs_qim_parse_summary.csv is a one-row accounting, not a table"
    return float(rows[0][column])


def _joint_national(resolution, side):
    """The national envelope at one resolution, from the module that owns the rule.

    Read through joint_uncertainty.national_envelope rather than re-summed here: the
    cross-category step is exactly where this is easy to get wrong, and a second arithmetic
    path in the claims file would be a second vintage waiting to disagree.
    """
    from pkinv.report import joint_uncertainty
    _total, low, high = joint_uncertainty.national_envelope()[resolution]
    return abs(low) if side == "low" else high


def _view_share(view):
    """The national share of one spatial view, from the profile the ledger writes."""
    return next(float(r["share_of_scope_pct"])
                for r in _csv_rows("spatial_view_profile.csv")
                if r["scope"] == "NATIONAL" and r["spatial_view"] == view)


def _first_where_data(relpath, column, **where):
    for r in _data_rows(relpath):
        if all(r.get(k) == v for k, v in where.items()):
            return r[column]
    raise KeyError((relpath, where))


def _msu(configuration, column):
    """A cell of the regenerated structural-uncertainty eval product (make eval)."""
    return float(_first_where(os.path.join("eval", "mms_structural_uncertainty.csv"), column,
                              configuration=configuration))


def _sensitivity_scenario(label):
    from pkinv.eval import sensitivity_table
    rows, _total = sensitivity_table.scenarios()
    return next(r for r in rows if r["scenario"] == label)


def _sensitivity_total(label):
    return _sensitivity_scenario(label)["total"]


def _sensitivity_soils(label):
    return _sensitivity_scenario(label)["soils"]


def _residue_total(column):
    return _cell("agriculture_crop_residue_ledger_2024.csv", "crop", "TOTAL", column)


def _agri_cy2023():
    """The engine's calendar-2023 agriculture categories (the basis tab:benchmark prints)."""
    got = {}
    for r in _rows(os.path.join("districts", "district_totals_by_year.csv")):
        if r["year"] == "2023":
            got[r["category"]] = got.get(r["category"], 0.0) + float(r["co2e_Mt_AR5"])
    return got


def _agri_cy2023_ratio(category):
    return _agri_cy2023()[category] / _first_where(
        "national_benchmark_comparison.csv", "benchmark_Mt_co2e",
        source="FAOSTAT", engine_category=category)


def _captive_registry_count(what):
    """The captive fleet's three counts, read from the registers the allocation uses.

    They are the evidence behind captive power's S2: the geometry is opened below the
    province, but only four fifths of the located plants carry an activity to weight them by,
    which is a facility proxy rather than an observed one. `members` and `geocoded` come from
    the published facility registry; `weighted` from the activity register the cube actually
    reads, because that is where the gas allocation lives.
    """
    if what == "weighted":
        rows = _data_rows(os.path.join("activity", "power", "captive_register.csv"))
        return sum(1 for r in rows if r["latitude"].strip()
                   and float(r["gas_mmcfd"] or 0.0) > 0)
    rows = [r for r in _csv_rows("pakemis_facility_registry.csv")
            if r["facility_id"].startswith("captive_")]
    if what == "members":
        return len(rows)
    return sum(1 for r in rows if r["geocode_status"] == "exact_coordinate_resolved")


def _source_register_count(state):
    """Rows in data/source_documents.csv, all of them or one archival state."""
    import csv as _csv
    with open(asset_path(ROOT, "data", "source_documents.csv"),
              newline="", encoding="utf-8") as handle:
        rows = list(_csv.DictReader(handle))
    return len([r for r in rows if state is None or r["archival_state"] == state])


def _prov_so2(period, row_kind, scope, field):
    """One cell of the provincial SO2 external comparison."""
    for r in read_rows("outputs/pakemis_air_provincial_external_comparison.csv"):
        if (r["period_id"] == period and r["row_kind"] == row_kind
                and r["scope"] == scope):
            return float(r[field])
    raise AssertionError("no %s/%s/%s row" % (period, row_kind, scope))


def _power_so2_screen(period, scenario):
    """The power SO2 screening total for one scenario, summed over fuels."""
    return sum(float(r["emissions_kt"]) for r in
               read_rows("outputs/power_air_screening_fy2015_16_fy2023_24.csv")
               if r["period_id"] == period and r["pollutant"] == "SO2"
               and r["scenario"] == scenario)


def _hub_coal(fiscal_start_year, field):
    """China Power Hub's coal row in the plant fuel ledger, and the fleet it sits in."""
    rows = [r for r in read_rows("data/sectors/power/activity/plant_fuel_ledger.csv")
            if r["fiscal_year"] == fiscal_start_year and "oal" in r["fuel"]]
    def num(rs, k):
        return sum(float(r[k]) for r in rs if r[k])
    hub = [r for r in rows if r["plant"] == "China Power Hub"]
    if field == "generation_share_pct":
        return 100.0 * num(hub, "net_generation_GWh") / num(rows, "net_generation_GWh")
    if field == "co2_Mt":
        # the repo's own IPCC Other Bituminous Coal values: 25.8 TJ/Gg, 94,600 kg CO2/TJ
        return num(hub, "quantity") * 25.8 * 94600.0 / 1e9
    raise AssertionError(field)


def _boundary_audit(kind, field=None, period=None):
    """The power province boundary audit: counts and per-year exposure."""
    rows = read_rows("outputs/pakemis_power_province_boundary_audit.csv")
    stations = [r for r in rows if r["row_kind"] == "station"]
    if kind == "stations":
        return float(len(stations))
    if kind == "misplaced":
        return float(sum(1 for r in stations if r["verdict"].startswith("MISPLACED")))
    if kind == "max_km":
        return max(float(r["km_to_nearest_adm2_vertex"]) for r in stations
                   if r["verdict"].startswith("MISPLACED"))
    if kind in ("exposure_min", "exposure_max"):
        vals = [float(r["value"]) for r in rows
                if r["row_kind"] == "period_exposure" and r["value"]]
        return min(vals) if kind == "exposure_min" else max(vals)
    raise AssertionError(kind)


def _cited_intermediate(scope=None):
    """Files typed `intermediate` that a manuscript names - all, or for one document."""
    rows = [r for r in read_rows("outputs/pakemis_artifact_inventory.csv")
            if r["role"] == "intermediate" and r["cited_in"] and r["cited_in"] != "none"]
    if scope:
        rows = [r for r in rows if scope in r["cited_in"].split(";")]
    return float(len(rows))


def _n_grazing_pct():
    """The share of excreted nitrogen the ledger routes to grazing, from the ledger itself."""
    for r in read_rows("outputs/n_ledger_2024.csv"):
        if r["flow"].startswith("to grazing"):
            return float(r["pct_of_excreted"])
    raise AssertionError("n_ledger_2024.csv has no 'to grazing' flow")


def _n_excreted_Mt():
    """Total nitrogen excreted, from the ledger that publishes it as its opening row."""
    for r in read_rows("outputs/n_ledger_2024.csv"):
        if r["flow"] == "Total N excreted":
            return float(r["Mt_N"])
    raise AssertionError("n_ledger_2024.csv has no 'Total N excreted' opening row")


def _faostat_ef1():
    """FAOSTAT's EF1, read out of the scenario label that names it.

    Bound to the repository's own scenario rather than parked as a constant: the prose says
    taking FAOSTAT's vintage moves managed soils to a stated figure, and that figure comes
    from this scenario, so the factor and the result should not be able to disagree.
    """
    for r in read_rows("outputs/eval/sensitivity.csv"):
        m = re.search(r"EF1 = ([\d.]+)", r["scenario"])
        if m and "2006" in r["scenario"]:
            return float(m.group(1))
    raise AssertionError("no 2006-aggregate EF1 scenario in outputs/eval/sensitivity.csv")


def _sens_soils(scenario):
    """One scenario's managed-soils total from the sensitivity table."""
    for r in read_rows("outputs/eval/sensitivity.csv"):
        if r["scenario"] == scenario:
            return float(r["soils"])
    raise AssertionError("no %r scenario in outputs/eval/sensitivity.csv" % scenario)


def _npool(pool, field):
    """One pool row of the FAOSTAT nitrogen-flow comparison (the acquired per-item split)."""
    for r in read_rows("outputs/pakemis_faostat_nitrogen_flows.csv", comments=True):
        if r["row_kind"] == "pool" and r["flow"] == pool:
            return float(r[field])
    raise AssertionError("no pool row %r" % pool)


def _npool_gap_share(pool):
    rows = [r for r in read_rows("outputs/pakemis_faostat_nitrogen_flows.csv", comments=True)
            if r["row_kind"] == "pool"]
    gaps = {r["flow"]: float(r["faostat"]) - float(r["pakemis"]) for r in rows}
    return 100.0 * gaps[pool] / sum(gaps.values())


def _nflow(flow, field):
    """One cell of the FAOSTAT nitrogen-flow comparison."""
    for r in read_rows("outputs/pakemis_faostat_nitrogen_flows.csv", comments=True):
        if r["flow"] == flow:
            return float(r[field])
    raise AssertionError("no %r row in the nitrogen-flow comparison" % flow)


def _coal_alloc(row_kind, period, subject, field):
    """One cell of the HDIP coal allocation identity."""
    for r in read_rows("outputs/pakemis_coal_allocation_identity.csv", comments=True):
        if (r["row_kind"] == row_kind and r["period_id"] == period
                and r["subject"] == subject):
            return float(r[field])
    raise AssertionError("no %s/%s/%s row" % (row_kind, period, subject))


def _coal_alloc_closes(limit=1.0):
    """How many of the balance years close to within `limit` kt."""
    return float(sum(1 for r in read_rows("outputs/pakemis_coal_allocation_identity.csv",
                                          comments=True)
                     if r["row_kind"] == "balance"
                     and abs(float(r["supply_minus_consumption_kt"])) <= limit))


def _coal_alloc_years():
    return float(sum(1 for r in read_rows("outputs/pakemis_coal_allocation_identity.csv",
                                          comments=True) if r["row_kind"] == "balance"))


def _coal_adjudication(period, field):
    """One cell of the Table 3 vs Table 21 coal energy adjudication."""
    for r in read_rows("outputs/pakemis_power_coal_energy_adjudication.csv",
                       comments=True):
        if r["period_id"] == period:
            return float(r[field])
    raise AssertionError("no %s row in the adjudication" % period)


def _coal_adjudication_range(field, which):
    vals = [float(r[field]) for r in
            read_rows("outputs/pakemis_power_coal_energy_adjudication.csv", comments=True)
            if r[field]]
    return min(vals) if which == "min" else max(vals)


def _coal_reallocation(period, field):
    """One cell of the power-to-industry coal reallocation."""
    for r in read_rows("outputs/pakemis_coal_sector_reallocation.csv", comments=True):
        if r["period_id"] == period:
            return abs(float(r[field]))
    raise AssertionError("no %s row in the coal reallocation" % period)


def _coal_config_ratio(which):
    """The extreme of C1/C0 across the panel - the non-circular route against the published
    energy. Read from the product rather than remembered, because the whole claim is that the
    ratio crosses unity and a stale endpoint would hide that."""
    vals = []
    for r in read_rows("outputs/pakemis_power_coal_configurations.csv", comments=True):
        if r["configuration_id"] != "C1_stations_rank_default" or not r["ratio_to_C0"]:
            continue
        vals.extend(float(x) for x in r["ratio_to_C0"].split("-"))
    return min(vals) if which == "min" else max(vals)


def _reference_audit(test_id, period, field="value"):
    """One cell of the power reference audit (the six rescue bases and the signature rows)."""
    for r in read_rows("outputs/pakemis_power_reference_audit.csv", comments=True):
        if r["test_id"] == test_id and (period is None or r["period_id"] == period):
            return float(r[field])
    raise AssertionError("no %s / %s row in the reference audit" % (test_id, period))


def _reference_audit_tjgg(period):
    """The TJ/Gg the signature row implies: Table 3's TOE per tonne x 41.868 GJ/TOE.

    Printed in section 7 as the factor Table 3 applies, so it is derived here from the same
    product rather than remembered - the whole point of the row is that it is a conversion.
    """
    return _reference_audit("S1_toe_per_tonne", period) * 41.868


def _reference_audit_span_pct():
    """The flat factor's spread as a per cent of its level, which is what the prose prints."""
    return 100.0 * _reference_audit("S2_flat_factor_span", None) / 0.4474


def _supply_bound_kt(which):
    """One side of the FY2023-24 coal supply bound, PARSED FROM THE AUDIT'S OWN VERDICT.

    B1's `value` column is the ratio (119.5 per cent of national supply); the two tonnages it
    compares are stated in the verdict string, "INFEASIBLE: 29531 kt required against 24719 kt
    supplied". Reading them from there rather than recomputing them is deliberate: the
    manuscript's sentence and the audit's verdict must move together, and a second computation
    here could agree with the product while both disagreed with the printed verdict.
    """
    for r in read_rows("outputs/pakemis_power_reference_audit.csv", comments=True):
        if r["test_id"] != "B1_the_bound":
            continue
        head, _, tail = r["verdict"].replace(",", "").partition("against")
        text = head if which == "required" else tail
        return float(text.split("kt")[0].strip().split()[-1])
    raise AssertionError("no B1_the_bound row in the reference audit")


def _station_coal_kt(period="FY2023-24"):
    """The station account's own coal tonnage for a period, summed over the enumerated rows.

    A typed absence is skipped, never read as a zero; the unplaced-generation rows carry no
    mass by construction and so contribute nothing here.
    """
    total = 0.0
    for r in read_rows("outputs/pakemis_power_fuel_reconciliation.csv", comments=True):
        if r["period_id"] != period or r["plant_coverage_class"] != "enumerated station":
            continue
        value = (r.get("mass_kt") or "").strip()
        if value in ("", "NE", "NO", "IE", "C", "NA"):
            continue
        total += float(value)
    return total


def _yearbook_coal_kt(consumer="power", fiscal_year="2023-24"):
    """What the energy yearbook books to one consumer, final revision only.

    revision_status is filtered because a superseded print of this table has shipped before
    (see the vintage-filter defect): two readers of the same file disagreed because one
    filtered and its sibling did not.
    """
    for r in read_rows(os.path.join(paths.DATA, "sectors", "industry", "activity",
                                    "coal_by_consumer.csv")):
        if (r["consumer"] == consumer and r.get("revision_status") == "final"
                and r["fiscal_year"] == fiscal_year):
            return float(r["coal_kt"])
    raise AssertionError("no final %s row for %s in coal_by_consumer" % (consumer, fiscal_year))


def _citation_audit(kind):
    """Counts from the citation-vs-deposit audit.

    The `bare*` kinds exist because cycle 37 found the audit reading one of the two notations
    the manuscripts use for a filename. Section 12 now prints the size of what had been
    invisible and how it split, so those three numbers are getters rather than remembered
    ones - a count that measures a repair is the first thing to go stale.
    """
    rows = [r for r in read_rows("outputs/pakemis_citation_deposit_audit.csv")
            if r["row_kind"] == "citation"]
    if kind == "cited":
        return float(len(rows))
    if kind == "deposited":
        return float(sum(1 for r in rows if r["in_deposit"] == "yes"))
    if kind == "absent":
        return float(sum(1 for r in rows if r["in_deposit"] == "no"))
    if kind.startswith("undeposited_"):
        role = kind[len("undeposited_"):]
        return float(sum(1 for r in rows
                         if r["in_deposit"] == "no" and r["role"] == role))
    bare = [r for r in rows if r["named_as"] == "bare"]
    if kind == "bare":
        return float(len(bare))
    if kind == "bare_deposited":
        return float(sum(1 for r in bare if r["in_deposit"] == "yes"))
    if kind == "bare_undeposited":
        return float(sum(1 for r in bare if r["in_deposit"] == "no"))
    if kind == "path_named":
        return float(sum(1 for r in rows if r["named_as"] in ("path", "both")))
    raise AssertionError(kind)


def _archived_third_party_documents():
    """DISTINCT third-party documents the repository archives.

    What depositing the repository whole would have offered under CC BY: one count per
    document, not per register row, and only documents the project did not itself produce.
    Registered because the number it replaced ("sixty") matched no construction of the
    register at all -- an unregistered quantity that had gone stale without anything noticing.
    """
    rows = read_rows("outputs/pakemis_source_register.csv")
    return len({r["archived_path"] for r in rows
                if r["archival_state"] == "archived"
                and r["outbound_redistribution"] != "own-work"})


def _industry_liquid_mt():
    """The industrial LIQUID fuels, as distinct from the gas half of the same category."""
    from pkinv.sectors.industry import combustion
    labels = tuple(combustion.LIQUID_LABELS.values())
    return sum(float(r["co2e_Mt_AR5"]) for r in _rows("industry_by_stream_2024.csv")
               if r["subitem"].startswith(labels))


def _swap_pct(case):
    """The share of its own total that one documented factor-table swap moves.

    Priced from the engine rather than quoted: see tests/test_factor_table_trap.py for why
    the manuscript's previous 8-9 percent range was wrong for two of the four cases."""
    from pkinv.core import registry
    from pkinv.core.components import enrich_co2e
    GWP = {"CH4": 30, "N2O": 265}

    def totals(name):
        s = registry.get(name)
        comps = s.build_components(s.load_data())
        enrich_co2e(comps)
        by_cat = {}
        for c in comps:
            by_cat[c["category"]] = by_cat.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        return sum(by_cat.values()), by_cat

    if case == "railways":
        from pkinv.sectors.railways import traction
        from pkinv.sectors.railways.data import RailwaysData
        tot, _ = totals("railways")
        tj = traction.fuel_TJ(RailwaysData())["Diesel"]
        return 100 * tj * (28.6 - 3.9) * GWP["N2O"] / 1e9 / tot
    if case == "power":
        from pkinv.sectors.power import combustion as pc
        from pkinv.sectors.power.data import PowerData
        tot, _ = totals("power")
        tj = pc.fuel_TJ(PowerData())["Gas"]
        return 100 * tj * 4 * GWP["CH4"] / 1e9 / tot
    if case == "residential":
        from pkinv.sectors.residential import combustion as rc
        from pkinv.sectors.residential.data import ResidentialData
        tot, _ = totals("residential")
        tj = rc.fuel_TJ(ResidentialData())
        moved = (tj["Natural gas"] * 4 + tj["Kerosene"] * 7) * GWP["CH4"] / 1e9
        return 100 * moved / tot
    raise KeyError(case)


def _res_param(name):
    import csv as _csv
    with open(asset_path(ROOT, "data", "residential_params.csv"),
              newline="", encoding="utf-8") as handle:
        for row in _csv.DictReader(handle):
            if row["param"] == name:
                return float(row["value"])
    raise KeyError(name)


def _generator_petrol_kt():
    """The live household-generator carve-out, read through the relay the paper describes
    rather than from a file - so the claim fails if the relay stops being called."""
    from pkinv.sectors.transport import road
    return road.generator_petrol_kt()


def _fuel_share(stream):
    """One residential fuel's share of household energy input, percent."""
    from pkinv.sectors.residential import combustion
    from pkinv.sectors.residential.data import ResidentialData
    tj = combustion.fuel_TJ(ResidentialData())
    return 100.0 * tj[stream] / sum(tj.values())


def _ocac_rail(col):
    """The YEAR-MATCHED railway cross-source row of the OCAC control diagnostic.

    Selected by the transport sector's own reference period rather than by a literal year,
    because harmonisation moved which row is the matched one - it used to be FY2021-22 and
    is now FY2023-24, and a hardcoded label would have silently started reporting the
    two-year-offset row as if it were the check."""
    from pkinv.core import period, registry
    s = registry.get("transport")
    want = period.label(s.PERIOD_START, s.PERIOD_END)
    for row in _rows("transport_ocac_control_diagnostic.csv"):
        if row["sector_row"] == "RAILWAYS" and row["fiscal_year"] == want:
            return float(row[col])
    raise KeyError(("rail cross-source", col, want))


# --- the cross-sector closure quantities -------------------------------------------------
#
# Read through the sector modules rather than from a CSV, because that is what the closures
# ARE: a quantity one sector computes and another subtracts by calling it. A file copy would
# pass while the relay was dead, which is the failure test_every_described_closure_has_a_live
# _relay exists to catch. These make the same accessors carry the printed magnitudes too.
#
# Every one of these was in the declared-debt list, and three of them - the waste generation,
# disposal and uncollected masses - were stale by about 2.6 percent, left behind when waste's
# population panel was projected to the fiscal midpoint. Nothing failed, because a listed debt
# is compared against nothing.
def _waste_mass(which):
    from pkinv.sectors.waste import open_burning, swds
    from pkinv.sectors.waste.data import WasteData
    data = WasteData()
    generated = swds.waste_generated(data)
    disposed = swds.waste_disposed(data)
    return {"generated": generated / 1e6,
            "disposed": disposed / 1e6,
            "uncollected": (generated - disposed) / 1e6,
            "burnt": open_burning.waste_burnt(data) / 1e6,
            "collection_pct": 100.0 * disposed / generated,
            "burned_share_pct": 100.0 * open_burning.waste_burnt(data)
                                / (generated - disposed),
            # The second stage's remainder: uncollected waste that is not burned either. It is
            # a declared unresolved FATE, not a category, and the abstract used to imply that
            # disposal and burning exhausted the stream.
            "unresolved": (generated - disposed - open_burning.waste_burnt(data)) / 1e6,
            }[which]


def _gas(gas, field):
    """One gas's national magnitude or share, from the generated category x gas ledger.

    The paragraph this serves was typed for three releases and drifted 7 Mt while sitting in
    the coverage test's declared-debt list. It has an output behind it now.
    """
    import csv as _csv
    totals = {}
    with open(os.path.join(OUT, "national_category_gas.csv"),
              newline="", encoding="utf-8") as handle:
        for row in _csv.DictReader(handle):
            ar5, ar6 = totals.get(row["gas"], (0.0, 0.0))
            totals[row["gas"]] = (ar5 + float(row["co2e_Mt_AR5"]),
                                  ar6 + float(row["co2e_Mt_AR6"]))
    national = sum(v[0] for v in totals.values())
    return {"AR5": totals[gas][0], "AR6": totals[gas][1],
            "share": 100.0 * totals[gas][0] / national}[field]


def _power_coal_co2_share():
    """Coal's share of the grid category's CO2, which is why coal leads on emissions while
    gas leads on energy."""
    from pkinv.core import registry
    engine = registry.get("power")
    comps = [c for c in engine.build_components(engine.load_data())
             if c["category"] == "Electricity and heat production" and c["gas"] == "CO2"]
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    coal = sum(c["co2e_Mt_AR5"] for c in comps if c["subitem"].startswith("Coal"))
    return 100.0 * coal / total


def _power_table3_efficiency_hi():
    """The highest implied net efficiency NEPRA Table 3's coal energy produces over the
    panel, in per cent. Asked of the table3 basis explicitly: the engine books the station
    account now, and this quantity is a property of the account that was refuted."""
    from pkinv.core import registry
    from pkinv.sectors.power import heat_rate
    engine = registry.get("power")
    return 100.0 * heat_rate.stability(engine.load_data(), basis="table3")["Coal"]["hi"]


def _power_gas_efficiency_lo():
    """The lowest implied net efficiency on the gas leg, which the coal re-base leaves
    untouched - only the coal row differs between the two bases."""
    from pkinv.core import registry
    from pkinv.sectors.power import heat_rate
    engine = registry.get("power")
    return 100.0 * heat_rate.stability(engine.load_data())["Gas"]["lo"]


def _residential_biomass_share():
    """Biomass streams as a percentage of the residential sector's reported CO2e.

    Reported means what enters the total: the biogenic CO2 of these fuels is a memo item
    outside it, so this share is their CH4 and N2O against the sector total, which is
    exactly the point the sentence makes about the memo convention.
    """
    rows = _rows("residential_by_stream_2024.csv")
    total = sum(float(r["co2e_Mt_AR5"]) for r in rows)
    biomass = ("Dung cake", "Firewood", "Charcoal", "Crop residues")
    share = sum(float(r["co2e_Mt_AR5"]) for r in rows
                if r["subitem"].rsplit(" ", 1)[0] in biomass)
    return 100.0 * share / total


def _rebase_ledger(period, column):
    """One cell of the power coal re-base ledger, which is what publishes the per-year
    consequence of the pin move and its two causes."""
    # comments=True: this product carries a banner, and _rows() is the comment-free reader.
    from pkinv.assets import asset_path
    from pkinv.core.io import read_rows as _read
    from pkinv.paths import OUTPUTS
    for r in _read(asset_path(OUTPUTS, "pakemis_power_coal_rebase_ledger.csv"),
                   comments=True):
        if r["period_id"] == period:
            return abs(float(r[column]))
    raise AssertionError("no re-base ledger row for %s" % period)


def _power_scenario(name):
    """One power structural scenario's deterministic total, Mt CO2e."""
    return float(next(r["deterministic_Mt"] for r in
                      _rows("power_uncertainty_scenarios_fy2023_24.csv")
                      if r["structural_scenario"] == name))


def _dung_configuration_ratio():
    """How far apart the two dung readings are - the L/S factor the limitations quote."""
    from pkinv.sectors.residential import combustion, hies
    from pkinv.sectors.residential.data import ResidentialData
    data = ResidentialData()
    ledger = combustion.dung_air_dry_kg(data, basis="ledger")
    survey = combustion.dung_air_dry_kg(data, basis="survey")
    return ledger / survey


def _air(sector, pollutant, basis=None):
    """One sector's national total for one air pollutant, kt.

    Reads the sector's own air-pollutant output, except for residential under configuration S,
    which no output carries - that one is computed through the module, the same way the
    manuscript's S figures are. Every one of these was declared debt.
    """
    if sector == "residential" and basis == "survey":
        from pkinv.sectors.residential import air_pollutants
        from pkinv.sectors.residential.data import ResidentialData
        rows = air_pollutants.compute(ResidentialData(), dung_basis="survey")
        return sum(r["emissions_kt"] for r in rows if r["pollutant"] == pollutant)
    files = {"residential": "residential_air_pollutants_2024.csv",
             "transport": "transport_air_pollutants_2024.csv",
             "waste": "waste_air_pollutants_2024.csv",
             "agriculture": "air_pollutants_2024.csv"}
    return sum(float(r["emissions_kt"]) for r in _rows(files[sector])
               if r["pollutant"] == pollutant)


def _industry_gas_Mt():
    """The metered-gas half of the industry module, Mt CO2e - the number quoted in three
    sections as what OGRA's sector-wise table contributes to 1.A.2."""
    # " gas " with spaces: "Industrial gasoline CO2" contains the bare substring and is a
    # liquid fuel, which makes the metered-gas figure 5.74 instead of 5.67.
    return sum(float(r["co2e_Mt_AR5"]) for r in _rows("industry_by_stream_2024.csv")
               if " gas " in r["subitem"].lower())


def _methane(field):
    """Fossil methane and its share of all methane, from the ledger's origin column."""
    import csv as _csv
    fossil = biogenic = 0.0
    with open(os.path.join(OUT, "national_category_gas.csv"),
              newline="", encoding="utf-8") as handle:
        for row in _csv.DictReader(handle):
            if row["ch4_origin"] == "fossil":
                fossil += float(row["co2e_Mt_AR5"])
            elif row["ch4_origin"] == "biogenic":
                biogenic += float(row["co2e_Mt_AR5"])
    return {"fossil_Mt": fossil, "biogenic_Mt": biogenic,
            "fossil_share": 100.0 * fossil / (fossil + biogenic)}[field]


def _power_province_share(province):
    """A province's share of the power sector, percent. The manuscript's provincial-proxy
    example quoted 0.02 percent for Khyber Pakhtunkhwa, which is the "Other" row of the same
    table; KP is 0.43."""
    rows = _rows("power_provincial_fy2023_24.csv")
    total = sum(float(r["co2e_Mt_AR5"]) for r in rows)
    value = next(float(r["co2e_Mt_AR5"]) for r in rows if r["province"] == province)
    return 100.0 * value / total


def _diverted_nitrogen_Mt():
    """The nitrogen agriculture removes from its manure balance as dung-cake fuel.

    This is the closure's actual currency - the residential sector receives mass, not an
    estimate - so it is read from the same accessor the transfer runs through.
    """
    from pkinv.sectors.residential import combustion
    return sum(combustion.diverted_n_by_species().values()) / 1e9


def _dung_mass(basis):
    """The dung the residential sector burns, on the basis the closure is asserted in.

    The manuscript calls the volatile-solids figure "dry matter", which is loose but is the
    quantity agriculture's manure balance hands over; air-dry and total-solids masses are
    larger and are the ones a reader might otherwise assume.
    """
    from pkinv.sectors.residential import combustion
    from pkinv.sectors.residential.data import ResidentialData
    data = ResidentialData()
    return {"air_dry": combustion.dung_air_dry_kg(data),
            "total_solids": combustion.dung_ts_kg(data),
            "volatile_solids": combustion.dung_vs_kg(data)}[basis] / 1e9


def _test_function_count():
    """Every test function in tests/. Deterministic and cheap, unlike asking pytest to
    collect itself from inside a test, and it is what "the engine ships N tests" means."""
    total = 0
    # os.walk since rc35: the paper-number tests live in tests/paper_numbers/.
    # The count is invariant under the split (the same `def test_` lines,
    # in test_*.py files one level down), so the published number held.
    for base, dirs, names in os.walk(os.path.join(ROOT, "tests")):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(names):
            if name.startswith("test_") and name.endswith(".py"):
                with open(os.path.join(base, name), encoding="utf-8") as handle:
                    total += len(re.findall(r"^\s+def (test_\w+)", handle.read(), re.M))
    return total


def _factor_ratio(numerator, denominator):
    """A ratio of two emission factors, read from the rows the engine actually uses.

    The rail-vs-road N2O ratio was printed as the WORD "seven times" at four sites across
    three papers. Both factors are registry rows - rail_n2o_diesel 28.6 and tr_n2o_diesel 3.9
    - so the ratio derives from what the inventory computes with, and a factor revision moves
    the prose instead of orphaning it.
    """
    rows = {r["ef_id"]: r for r in _data_rows("emission_factors.csv")}
    return float(rows[numerator]["value"]) / float(rows[denominator]["value"])


def _rail_diesel_change():
    """FY2017-18 diesel over FY2023-24, the "not a year effect" argument at three sites.

    Printed as "eighteen percent" in the national benchmark section and twice in the railways
    paper. It is the one number that rules a year effect out, so it carries the matched-year
    comparison's whole premise.
    """
    return 100.0 * (_rail_year_litres(2018) / _rail_year_litres(2024) - 1)


def _claim_read_role_count(uncited=False):
    """Products a REGISTERED CLAIM reads that the register types `intermediate`.

    A claim getter reads a product by name and the manuscript prints the figure computed from
    it, so a file a claim reads is a file a reader-facing claim rests on - which is the one
    thing `intermediate` promises is not true of it. Counted here so Section 12 can print it
    and so the number cannot drift away from the register. `uncited` narrows to the subset no
    manuscript names, which is the part re-typing cannot fix: `diagnostic` requires being
    named somewhere.
    """
    import re as _re
    reader = _re.compile(
        r"_(?:rows|rows_banner|cell|data_rows|data_rows_nocomment|csv_rows|first_where|"
        r"max_where|min_where|sum_where|sum_prefix)\(\s*[\"']([\w./-]+\.csv)[\"']")
    text = ""
    for name in ("doc_claims.py", "tables.py", "labelled_tables.py", "quantity_policy.py",
                 "_common.py"):
        path = os.path.join(ROOT, "tests", "paper_numbers", name)
        if os.path.exists(path):
            with io.open(path, encoding="utf-8") as handle:
                text += handle.read()
    names = set(reader.findall(text))
    inventory = {r["artifact"]: r
                 for r in read_rows("outputs/pakemis_artifact_inventory.csv")}
    rows = [inventory[n] for n in names if n in inventory
            and inventory[n]["role"] == "intermediate"]
    if uncited:
        rows = [r for r in rows if r["cited_in"] == "none"]
    return float(len(rows))


def _supplement_citations_recovered():
    """Artifacts a sector supplement names that the citation scan used to miss.

    DOC_GLOBS read papers/*/sections/*.tex and not papers/*/*.tex, so anything named only in a
    supplement's own body was recorded as named by nobody. Fixed at rc64; this counts what the
    repair found, so the number Section 12 prints is not a remembered one.

    IT MOVED 17 -> 12 IN CYCLE 36, and the tree is why. This function had its own
    `replace("\\_", "_")` and was blind to \allowbreak, exactly the defect cycle 32 fixed in
    the inventory's scanner and nowhere else. Five of the seventeen have since been named in a
    SECTION too - with break hints, because the names are long - and the blind scan could not
    see those mentions, so it kept counting them as supplement-only. Section 12 now prints both:
    17 as what the rc64 repair found in the tree of the day (a literal claim, since the tree it
    measured no longer exists) and 12 as what this function reports now.
    """
    import glob as _glob
    missed = {}
    for pattern in ("papers/*/supplement.tex", "papers/*/paper.tex"):
        for path in sorted(_glob.glob(os.path.join(ROOT, pattern))):
            label = os.path.relpath(path, ROOT).split(os.sep)[1]
            with io.open(path, encoding="utf-8", errors="replace") as handle:
                missed[label] = missed.get(label, "") + as_a_reader_sees_it(handle.read())
    sections = {}
    for pattern in ("papers/*/sections/*.tex",):
        for path in sorted(_glob.glob(os.path.join(ROOT, pattern))):
            label = os.path.relpath(path, ROOT).split(os.sep)[2 - 1]
            with io.open(path, encoding="utf-8", errors="replace") as handle:
                sections[label] = sections.get(label, "") + as_a_reader_sees_it(handle.read())
    total = 0
    for row in read_rows("outputs/pakemis_artifact_inventory.csv"):
        base = os.path.basename(row["artifact"])
        stem = base.rsplit(".", 1)[0]
        in_supp = any(base in t or stem in t for t in missed.values())
        in_sect = any(base in t or stem in t for t in sections.values())
        if in_supp and not in_sect:
            total += 1
    return float(total)


def _ippu_geocode(kind):
    """The facility registry's geocoding breakdown, by coordinate source.

    ONE getter for BOTH sections. The methods section had a registered `16` for the Global
    Energy Monitor contribution and the study-area section still said "eleven" - five short,
    and its own three components summed to 19 against the 24 it stated in the same sentence.
    doc_claims already carried the lesson, on the methods claim below: "'eleven' cannot be
    repaired, and it was wrong the moment five arrived." Five arrived, the registered site
    tracked it, and the word two sections away did not. Sharing the getter is what stops the
    two sections diverging again - a second lambda computing the same thing would have been
    the same defect waiting.
    """
    rows = _rows("ippu_facility_registry.csv")
    if kind == "total":
        return float(len(rows))
    if kind == "resolved":
        return float(sum(1 for r in rows
                         if r["geocode_status"] == "exact_coordinate_resolved"))
    if kind == "unresolved":
        return float(sum(1 for r in rows
                         if r["geocode_status"] != "exact_coordinate_resolved"))
    prefix = {"gem": "Global Energy Monitor Global Cement",
              "osm": "OpenStreetMap snapshot",
              "nominatim": "OpenStreetMap Nominatim"}[kind]
    return float(sum(1 for r in rows if r["coordinate_source"].startswith(prefix)))


def _fugitives_table_rows(name, distinct=None):
    """A fugitives evidence table's size, for the counts its appendix states.

    The appendix described its outputs by size - "224 factorial configurations", "five
    conditional Monte Carlo intervals", the "nine-year" reconstruction - and named none of the
    files. Naming them without anchoring the counts would have left the same drift one step
    further on, so each stated count now reads the table it describes. `distinct` counts unique
    values of a column instead of rows, for the segment ledger.
    """
    rows = _rows(name)
    if distinct:
        return float(len({r[distinct] for r in rows}))
    return float(len(rows))


def _ufg_threshold(which):
    """The UFG thresholds the compatibility table tests, read from its COLUMN NAMES.

    The appendix says the test reports compatibility with a 10 and a 25 per cent
    unaccounted-for-gas figure. Those are not derived quantities - they are thresholds baked
    into the product's schema as `compatible_with_10pct_ufg` and `compatible_with_25pct_ufg`.
    Reading them off the columns means that changing a threshold renames a column and fails
    this claim, which is the strongest anchor available for a number that is a choice rather
    than a measurement.
    """
    import re as _re
    columns = _rows("fugitives_ufg_network_compatibility_2024.csv")[0].keys()
    found = sorted(int(m.group(1)) for m in
                   (_re.match(r"compatible_with_(\d+)pct_ufg$", c) for c in columns) if m)
    if not found:
        raise KeyError("the UFG compatibility table has no compatible_with_*pct_ufg column")
    return float(found[0] if which == "low" else found[-1])


def _aviation_oecd_complete_years():
    """Years the OCAC-OECD comparison matches in full, NOT the table's row count.

    The appendix says "five complete matched OECD years" and the table has SEVEN rows: FY2018
    and FY2024 match six months each and are marked partial. So the five counts a FILTERED
    subset, which is why every row-count search for it failed - four unrelated five-row
    aviation tables matched the integer and the OECD table did not. A row count is one
    statistic about a table; prose can be counting a subset, a distinct-value count or a
    derived quantity, and only reading the file settles which.
    """
    return float(sum(1 for r in _rows("aviation_ocac_oecd_annual_comparison.csv")
                     if r["period_status"] == "complete"))


def _railways_generated_outputs():
    """How many files the railway runner's own manifest records as generated.

    The appendix said "seventeen railways_* files" - a glob where a filename belongs, and a
    count contradicted by the file named in the same clause: railways_run_manifest_2024.json
    carries a generated_outputs list of 21. Two wrong places were checked first: `ls
    outputs/railways_*` gives 30 (it includes the GIS products, the derivation chain, the
    activity-factor ledger, the ELK crosscheck, the network audit and the route shares, all
    written by other phases) and the run_all Phase for the runner declares only 2, the rest
    being written in-process. The runner's manifest is the one authority, and the appendix
    already cited it.
    """
    import json as _json
    path = asset_path(ROOT, "outputs", "railways_run_manifest_2024.json")
    with io.open(path, encoding="utf-8") as handle:
        return float(len(_json.load(handle)["generated_outputs"]))


def _crt_rail_cell(field):
    """One cell of Pakistan's CRT railway row, from the audit that re-derives it each run.

    Transcribing 56,609 would have been the obvious thing and the wrong one: the audit
    locates the row by label so a workbook revision breaks loudly, and a claim that reads the
    audit inherits that property.
    """
    for row in _rows("railways_unfccc_crt_cell_audit_2024.csv"):
        if row["row_label"].strip().startswith("1.A.3.c") and row["field"] == field:
            return float(row["value"])
    raise KeyError("no CRT railway cell %r" % field)


def _rail_benchmark(benchmark_id, field):
    """A row of the railway official-benchmark comparison, read from the shipped product.

    The five official filings and this inventory's value for each one's own year live in
    outputs/railways_official_comparison_2024.csv, written by the sector runner. Reading it
    rather than retranscribing is the point: four of these numbers were published nowhere in
    the national paper while the product carried them, and the ratio the sector paper prints
    for the CRT rests on a DIFFERENT denominator from the one the product declares - a single
    fiscal year rather than the mean of the two that calendar 2022 straddles.
    """
    for row in _rows("railways_official_comparison_2024.csv"):
        if row["benchmark_id"] == benchmark_id:
            return float(row[field])
    raise KeyError("no railway benchmark %r" % benchmark_id)


def _rail_history_peak_row():
    """The whole peak row, so the tonnages and the period move WITH the peak.

    Section 10 names the peak year's coal and furnace-oil purchases beside the peak itself.
    Transcribing them, or keying them on the string "1965-70", would let the three numbers
    come apart if the reconstruction ever moved - the peak would update and its fuels would
    not, which reads as a fact about a different year.
    """
    return max(_rows("railways_fuel_history.csv"),
               key=lambda r: float(r["co2e_Mt_AR5_indicative"]))


def _rail_history_peak():
    """The highest annual figure in the operator's reconstructed fuel history, 1950 onward.

    The steam-era peak is the ceiling any official railway figure has to clear, and it is a
    stronger bound than the per-train-kilometre diagnostic because it needs no traffic
    statistic - only the operator's own coal, furnace-oil and diesel purchases.
    """
    return float(_rail_history_peak_row()["co2e_Mt_AR5_indicative"])


def _held_product_count(checkable=False, mode=None):
    """Held products, and how many of them are VERIFIED rather than merely re-runnable.

    A held product is one no build phase writes, so `make release-check` does not regenerate
    it and nothing compares it against its producer. The registry pins each by its digest at
    release, which proves the bytes are the published bytes and says nothing about whether
    the producer still agrees - the tautology that let outputs/eval/sensitivity.csv drift.

    `checkable` reads the DECLARED verify_mode, not the command string. It was written as
    `"--check" in verify_command` and that was wrong twice over: it counted MODES where the
    paper means products compared (six commands carried the flag and between them compared
    two of the products registered against them, the rest being written below an early
    return), and a mode cannot be inferred from a spelling - seven rows name their producer
    as the verification, and running one rewrites the file it was meant to verify.
    """
    rows = read_rows(os.path.join(ROOT, "data", "catalog", "held_products.csv"))
    want = mode or ("checks" if checkable else None)
    paths = {r["path"] for r in rows
             if want is None or (r.get("verify_mode") or "").strip() == want}
    return len(paths)


def _contract_invariant_count():
    """How many contract invariants there actually are: the test functions in
    tests/test_sector_contract.py, which is what the manuscript's number means."""
    path = os.path.join(ROOT, "tests", "test_sector_contract.py")
    with open(path, encoding="utf-8") as handle:
        return len(re.findall(r"^\s+def (test_\w+)", handle.read(), re.M))


def _bounded_fold_span():
    """p97.5/p2.5 of the rc11 bounded split-triangular for the effluent factor,
    closed form from the transcribed endpoints - the after side of the S1
    before/after comparison (the before side, 6.6, is a listed constant)."""
    import math as _m
    # The endpoints are read from the parameter row the engine draws from: the upper
    # bound moved from 0.25 (2006 Guidelines) to 0.075 (2019 Refinement) at rc67, and a
    # literal here would have gone on asserting the old span.
    row = next(r for r in _data_rows("waste_params.csv") if r["param"] == "ww_ef_effluent")
    lo, mode, hi = float(row["lower"]), float(row["value"]), float(row["upper"])
    llo, lmo, lhi = _m.log(lo), _m.log(mode), _m.log(hi)
    p025 = _m.exp(llo + (lmo - llo) * _m.sqrt(2 * 0.025))
    p975 = _m.exp(lhi - (lhi - lmo) * _m.sqrt(2 * 0.025))
    return p975 / p025


def _longitudinal_share(col):
    for r in _csv_rows("pakemis_longitudinal_uncertainty.csv"):
        if (r.get("scenario") == "parameter_typed"
                and r.get("fiscal_end_year") == "2024"):
            return float(r[col])
    raise KeyError(col)


def _trend_window(col, from_period="FY2015-16", to_period="FY2023-24",
                  scenario="parameter_typed"):
    for r in _csv_rows("pakemis_trend_uncertainty.csv"):
        if (r["scenario"] == scenario and r["from_period"] == from_period
                and r["to_period"] == to_period):
            return float(r[col])
    raise KeyError((col, from_period, to_period, scenario))


def _divergence_1a2(period):
    """The engine's 1.A.2 in one fiscal year, from the banner-headed divergence product."""
    for r in _rows_banner("pakemis_industry_edgar_divergence.csv"):
        if r["period_id"] == period:
            return float(r["engine_1a2_mt"])
    raise KeyError(period)


def _mc(scenario, name, col="rel_uncert_pct_MC_95"):
    for r in _rows("national_uncertainty_montecarlo.csv"):
        if r["scenario"] == scenario and r["name"] == name:
            return float(r[col])
    raise KeyError((scenario, name))


def _ranking_top(section, col="metric"):
    """The rank-1 row of one priority ranking (parametric / structural / coverage)."""
    for r in _rows("national_priority_rankings.csv"):
        if r["ranking"] == section and r["rank"] == "1":
            return r[col]
    raise KeyError(section)


def _mc_scenario_pairs():
    """Every (scope, name) with a half-width under BOTH covariance scenarios."""
    by_key = {}
    for r in _rows("national_uncertainty_montecarlo.csv"):
        by_key.setdefault((r["scope"], r["name"]), {})[r["scenario"]] = (
            float(r["rel_uncert_pct_MC_95"]), float(r["rel_uncert_se_pp"]))
    return {k: v for k, v in by_key.items()
            if "within_sector" in v and "cross_sector" in v}


def _max_mc_noise_ratio():
    """The largest scenario move as a multiple of three combined batch-means SEs.

    Under 1.0 everywhere, "indistinguishable from sampling noise" is a checked relation
    rather than a manner of speaking."""
    import math
    worst = 0.0
    for v in _mc_scenario_pairs().values():
        (w, se_w), (c, se_c) = v["within_sector"], v["cross_sector"]
        denom = 3.0 * math.sqrt(se_w * se_w + se_c * se_c)
        worst = max(worst, abs(c - w) / denom if denom else float("inf"))
    return worst


def _keycat(category, col):
    """A key-category row, by IPCC category name, IPCC code, or engine source stream.

    Three keys because the screen moved onto IPCC categories and the engine names survive as
    source streams. Accepting all three means a claim can be written in whichever vocabulary
    the surrounding prose uses, and none of them silently resolves to the wrong row: category
    names and codes are unique, and a source stream belongs to exactly one code.
    """
    for r in _rows("national_key_categories.csv"):
        streams = [s.rsplit(" ", 1)[0] for s in r["source_streams"].split("; ") if s]
        if category in (r["category"], r["ipcc_code"]) or category in streams:
            return float(r[col])
    raise KeyError(category)


def _rail_year_litres(year):
    """Diesel in thousand litres for one railway series year, from the sector's own series.

    Both years are read rather than one being read and the other typed: the paragraph this
    replaced quoted FY2017's 144,631 beside a matched-year estimate built on FY2017-18's
    156,396, and nothing could see that they were different years.
    """
    for row in _rows("railways_timeseries_2024.csv"):
        if str(row.get("fiscal_year")) == str(year):
            return float(row["diesel_thousand_litres"])
    raise KeyError(("rail diesel litres", year))


def _rail_density_t_per_kl():
    """Tonnes per thousand litres, derived from the reference year's own pair rather than
    typed: the sector publishes both the litres and the mass for FY2023-24, so the density it
    actually used is the ratio of the two."""
    return (_cell("railways_totals_2024.csv", "category",
                  "Traction diesel, for cross-source comparison", "co2e_Mt_AR5")
            / _rail_year_litres(2024))


def _source_stream(name, col="level_Mt_co2e_AR5"):
    """One engine source stream's magnitude, from the key-category screen's stream column.

    Captive gas self-generation stopped being a row of its own when the screen moved onto IPCC
    categories - it is a stream beneath 1.A.2 now - so the three sections that quote 5.61 Mt
    lost the tier-2 backing they had been riding on. This gives them a first-class one.
    """
    for r in _rows("national_key_categories.csv"):
        for entry in r["source_streams"].split("; "):
            if entry.rsplit(" ", 1)[0] == name:
                return float(entry.rsplit(" ", 1)[1])
    raise KeyError(name)


def _notation(key):
    return float(sum(1 for r in _rows("completeness.csv") if r["notation_key"] == key))


def _bench(source, category, col="ratio_engine_over_benchmark", year=None):
    """year=None keeps the historic first-match behaviour; pass a year where a source
    carries more than one vintage for a category (EDGAR/transport has a year-matched
    2022 row and a release-vintage 2024 row)."""
    for r in _rows("national_benchmark_comparison.csv"):
        if (r["source"] == source and r["engine_category"] == category
                and (year is None or r["year"] == str(year))):
            return float(r[col])
    raise KeyError((source, category, year))


def _attribution(group, col="total_effect_index"):
    """One dependency group's Sobol index, from the covariance-aware attribution."""
    for r in _rows("national_variance_attribution.csv"):
        if r["parameter_group"] == group:
            return float(r[col])
    raise KeyError(group)


def _scenario_axes():
    """The axes of the reference scenario. The paper said "nine" against a registry of ten,
    in a sentence whose whole point was that the letter names less than the scenario."""
    from pkinv.report import national_rollup
    return national_rollup.scenario_registry()


def _district_multi_check(category):
    """One category's entry in the multi-record district validation JSON."""
    blob = json.load(open(os.path.join(OUT, "eval", "validation",
                                       "district_records_multi.json")))
    for check in blob["checks"]:
        if check["category"] == category:
            return check
    raise KeyError(category)


def _validation_catalog_rows(name):
    """The rc33 validation products carry '#' banner lines; strip them (the plain
    _rows helper would read the first banner line as the header)."""
    return read_rows(os.path.join(OUT, name))


def _validation_scorecard_covered():
    return float(sum(1 for r in _validation_catalog_rows(
        "pakemis_validation_scorecard.csv") if r["status"] == "covered"))


def _residual_share():
    """The share of national variance with no named PARAMETER, summed over the module
    residuals it is now split across.

    It used to be one row called "(residual: no named parameter)". Splitting it by module
    means nothing in the attribution belongs to no object -- and it turned an unusable
    headline into an actionable one: agriculture's residual alone is most of it.
    """
    rows = [r for r in _rows("national_variance_attribution.csv")
            if r["parameter_group"].startswith("residual:")]
    if not rows:
        raise AssertionError("no module residuals in the attribution -- the split is gone")
    return sum(max(0.0, float(r["total_effect_index"])) for r in rows)


def _largest_residual():
    rows = [r for r in _rows("national_variance_attribution.csv")
            if r["parameter_group"].startswith("residual:")]
    return max(rows, key=lambda r: float(r["total_effect_index"]))


def _largest_named_group():
    """The named parameter group with the largest total effect.

    A residual is a named OBJECT but not a named PARAMETER, so it does not compete for the
    title. The prefix moved from "(residual" to "residual:" when the bucket was split by
    module, and for one run this function happily reported "residual:agriculture" as the
    largest named driver -- caught by the semantic claim that says it must be a livestock
    count, which is exactly the kind of catch that registry exists for.
    """
    named = [r for r in _rows("national_variance_attribution.csv")
             if not r["parameter_group"].startswith("residual:")]
    return max(named, key=lambda r: float(r["total_effect_index"]))["parameter_group"]




def _temporal_share(cls):
    """A T-class's share of the national inventory, from the generated profile table."""
    return _first_where("temporal_profile.csv", "share_of_scope_pct",
                        scope="NATIONAL", temporal_method=cls)


def _month_total(month):
    """One month of the national monthly layer, Mt CO2e AR5."""
    return _sum_where("national_monthly_2024.csv", "co2e_Mt_AR5", month=month)


def _national_monthly_total():
    return sum(float(r["co2e_Mt_AR5"]) for r in _rows("national_monthly_2024.csv"))


def _power_grid_shaped_mass():
    """The grid coal and gas mass the SIR listings gave observed months (rc21), Mt."""
    return sum(float(r["co2e_Mt_AR5"]) for r in _rows("power_monthly_fy2023_24.csv")
               if r["subitem"].startswith(("Coal ", "Gas ")))






def _annex28_share(fiscal_year, consumption):
    """Feed or fuel share of Annex-28's monthly cells for one fiscal year.

    The reference year's split is OBSERVED here. Round 11 anchored these claims on Table
    40, which is the FOLLOWING year, because the annex had not been read; anchoring the
    reference-year sentence on the reference year is the point of the repair.
    """
    rows = [r for r in _data_rows(os.path.join("nfdc",
                                               "afr2025_fertilizer_gas_monthly.csv"))
            if r["fiscal_year"] == fiscal_year and r["mmcf"].strip()]
    total = sum(float(r["mmcf"]) for r in rows)
    part = sum(float(r["mmcf"]) for r in rows if r["consumption"] == consumption)
    return part / total * 100.0


def _ogra_fertiliser_mmcfd():
    """OGRA's own fertiliser row, read from the cross-source table the engine writes."""
    return float(next(r for r in _rows("ippu_fertilizer_gas_cross_source_2024.csv")
                      if r["record"].startswith("OGRA"))["mmcfd"])


def _gas_agreement_pct():
    """How far apart the two institutions land, as the engine computes it."""
    return abs(float(next(r for r in _rows("ippu_fertilizer_gas_cross_source_2024.csv")
                          if r["record"] == "difference")["agreement_pct"]))


def _annex28_mmcfd(fiscal_year):
    rows = [r for r in _data_rows(os.path.join("nfdc",
                                               "afr2025_fertilizer_gas_monthly.csv"))
            if r["fiscal_year"] == fiscal_year and r["mmcf"].strip()]
    return sum(float(r["mmcf"]) for r in rows) / 365.0




def _ef(ef_id, col="value"):
    for r in _data_rows("emission_factors.csv"):
        if r["ef_id"] == ef_id:
            return float(r[col])
    raise KeyError(ef_id)


def _railpar(name):
    for r in _data_rows("railways_params.csv"):
        if r["param"] == name:
            return float(r["value"])
    raise KeyError(name)


def _transport_edgar_scope(include_offroad=False, calendar=False):
    """The EDGAR-scope-matched construction of the transport paper's validation
    section: the road residual (plus mixed off-road when the outside-transport
    booking is waived) plus the railways and domestic-aviation terms on the SAME
    FY2023-24 reference period - the rc4 edition anchored these two terms to
    FY2021-22 rows beside a live road figure, and this helper mirrored the mix.
    calendar=True rebuilds the road residual on the CY2022 controls exactly as the
    calendar_2022_controls scenario does - petrol scaled net of the generator
    carve-out, diesel scaled, CNG held - keeping rail and aviation at the FY2021-22
    vintage, because that whole construction is ranked superseded history."""
    if calendar:
        streams = [r for r in _rows("transport_by_stream_%d.csv" % _transport_year())
                   if r["category"] == "Road transport"]
        pet = sum(float(r["co2e_Mt_AR5"]) for r in streams if "Petrol" in r["subitem"])
        die = sum(float(r["co2e_Mt_AR5"]) for r in streams if "Diesel" in r["subitem"])
        cng = _sum_prefix("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                          "subitem", "CNG")
        gen = _first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "kt", fuel="Petrol",
                           tier="road", claimant="Household generators")
        pet_ctl = _first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "kt", fuel="Petrol",
                               tier="national", claimant="Road (retail pump sales)")
        die_ctl = _first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "kt", fuel="Diesel",
                               tier="national", claimant="Road (retail pump sales)")
        cy_pet = _cell("transport_calendar_year_controls_%d.csv" % _transport_year(), "item",
                       "CY2022 Road petrol (MS+HOBC)", "value")
        cy_die = _cell("transport_calendar_year_controls_%d.csv" % _transport_year(), "item",
                       "CY2022 Road diesel (HSD)", "value")
        road = (pet * (cy_pet - gen) / (pet_ctl - gen)
                + die * cy_die / die_ctl + cng)
    elif include_offroad:
        road = _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5")
    else:
        road = _cell("transport_totals_%d.csv" % _transport_year(), "category", "Road transport",
                     "co2e_Mt_AR5")
    # rc12: the reference-year rail term is STRICT 1A3c (EDGAR's inferred scope has
    # no non-traction category); the calendar-2022 superseded construction predates
    # the recode and keeps the timeseries module total its history was built on.
    if calendar:
        rail = _cell("railways_timeseries_2024.csv", "fiscal_year", "2022",
                     "mt_co2e_AR5")
        avi_fy = "2022"
    else:
        rail = _cell("railways_totals_2024.csv", "category", "Railways",
                     "co2e_Mt_AR5")
        avi_fy = "2023"
    return (road + rail
            + _cell("aviation_timeseries_2006_fy2023_24.csv", "fiscal_year", avi_fy,
                    "domestic_kt_co2e_AR5") / 1000.0)


def _edgar_blend():
    """EDGAR at this sector's FISCAL year: half of each calendar column.

    FY2023-24 runs July to June, so six of its months fall in EDGAR's 2023 column and
    six in its 2024 one. The paper's primary comparison is against this blend and is
    labelled fiscal-year blended, never year-matched.

    Read from the tracked series extract rather than the benchmark register: the
    register carries one row per published benchmark figure, and the single-year
    columns are inputs to a derived construction rather than benchmarks in their own
    right."""
    return 0.5 * (_edgar_series(2023) + _edgar_series(2024))


def _edgar_series(year):
    """A single EDGAR transport column, from the tracked extract rather than the
    gitignored booklet."""
    for r in _data_rows(os.path.join("activity", "transport",
                                     "edgar_pak_transport_series.csv")):
        if r["year"] == str(year):
            return float(r["total_Mt_co2e_AR5"])
    raise KeyError(year)


def _aviation_noncommercial_Mt(account, factor_param):
    """One bridged non-commercial stream priced at the sector's own factor - the memo
    arithmetic run_aviation performs, recomputed for the claim."""
    tonnes = sum(float(r[account]) for r in _rows("aviation_fuel_bridge_fy2023_24.csv")
                 if r["scenario"] == "literal_customer")
    factor = float(next(r["value"] for r in _data_rows("aviation_params.csv")
                        if r["param"] == factor_param))
    return tonnes * factor / 1e6


def _onroad_diesel_mjkm():
    """The vkt-weighted mean energy intensity of the ON-ROAD diesel classes - the
    comparator the off-road sign argument rests on. NRV is the off-road machinery
    class itself, so it is excluded from its own comparator."""
    # rc41: the within-fuel weights are their own file (one table per csv)
    rows = _rows_banner("transport_class_fuel_weights_%d.csv" % _transport_year())
    num = den = 0.0
    for r in rows:
        if r["fuel"] == "Diesel" and r["ei_class"] != "NRV":
            num += float(r["vkt_vehicle_km"]) * float(r["mjkm_mid"])
            den += float(r["vkt_vehicle_km"])
    return num / den


def _class_weight(ei_class, fuel):
    """One within-fuel weight from the class-parameter output.

    Until rc41 that file held TWO tables under two headers separated by a blank line;
    the weights are their own file now (transport_class_fuel_weights_<year>.csv)."""
    # rc41: the within-fuel weights are their own file (one table per csv)
    rows = _rows_banner("transport_class_fuel_weights_%d.csv" % _transport_year())
    for r in rows:
        if r["ei_class"] == ei_class and r["fuel"] == fuel:
            return float(r["within_fuel_weight"])
    raise KeyError((ei_class, fuel))


def _grid_resolution_deg():
    """The cube's own cell size, from the gridded product's declaration rather
    than the number the prose happens to say."""
    for r in _csv_rows("pakemis_grid_provincial_check.csv"):
        break
    from pkinv.core.gis.grid import RES
    return RES


def _industry_liquid_Mt():
    """The industrial category's LIQUID rows - everything whose subitem is not a gas
    stream. They are metered in tonnes and converted by calorific value, so the
    heating-value scenario leaves them alone."""
    return sum(float(r["co2e_Mt_AR5"])
               for r in _csv_rows("industry_by_stream_2024.csv")
               if " gas " not in r["subitem"])




def _class_distance_weight(ei_class, fuel):
    """The distance-only counterpart of _class_weight: the same second table's
    vehicle-km renormalised within the fuel, which is what the methods prose
    compares the energy weighting against."""
    rows = [r for r in _rows_banner("transport_class_fuel_weights_%d.csv" % _transport_year())
            if r["fuel"] == fuel]
    total = sum(float(r["vkt_vehicle_km"]) for r in rows)
    return next(float(r["vkt_vehicle_km"]) for r in rows
                if r["ei_class"] == ei_class) / total


def _wpar(name):
    for r in _data_rows("waste_params.csv"):
        if r["param"] == name:
            return float(r["value"])
    raise KeyError(name)


def _hies_route(region, route, scope="national"):
    """Design-weighted HIES 2024-25 disposal-route share (as a percentage)."""
    for r in _data_rows(os.path.join("activity", "waste", "hies_disposal_routes.csv")):
        if r["scope"] == scope and r["region"] == region and r["route"] == str(route):
            return 100.0 * float(r["share_of_region"])
    raise KeyError((scope, region, route))


# The seven per-sector air-pollutant outputs at NATIONAL level (the district and
# provincial files re-slice the same totals and would double-count).
_PM_NATIONAL_FILES = ("air_pollutants_2024.csv", "aviation_air_pollutants_fy2023_24.csv",
                      "power_air_pollutants_fy2023_24.csv", "railways_air_pollutants_2024.csv",
                      "residential_air_pollutants_2024.csv",
                      "transport_air_pollutants_%d.csv" % _transport_year(), "waste_air_pollutants_%d.csv" % _waste_year())


def _pm25_national_total():
    return sum(_sum_where(f, "emissions_kt", pollutant="PM2.5")
               for f in _PM_NATIONAL_FILES)


def _waste_river_sector_total():
    """The sector total under the river-discharge MCF: TOTAL - central 4D1 + river 4D1."""
    return (_cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5")
            - _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                    "co2e_Mt_AR5")
            + _cell("waste_totals_%d.csv" % _waste_year(), "category",
                    "Sensitivity: wastewater on the river-discharge MCF (category total)",
                    "co2e_Mt_AR5"))


def _air_kt(pollutant):
    """Total railway air-pollutant mass, all fuel streams."""
    return _sum_where("railways_air_pollutants_2024.csv", "emissions_kt",
                      pollutant=pollutant)


def _rail_fuel(year, fuel="Gas/Diesel Oil"):
    for r in _data_rows(os.path.join("activity", "railways", "fuel_consumption.csv")):
        if r["fiscal_year"] == str(year) and r["fuel"] == fuel:
            return float(r["quantity"])
    raise KeyError((year, fuel))


# ---------------------------------------------------------------------------
# The national manuscript and the eight sector notes.
#
# Same contract as CLAIMS above, with an explicit document key. Anchored on the numbers a
# reader would actually quote: every sector total, both ends of the correlated-uncertainty
# result, the two key-category shares the paper builds an argument on, the completeness
# tally, and each note's headline figure and its distinctive claim.
# (label, doc, section file, regex with ONE capture group, expected value, extra tolerance)
def _located(profile):
    """The share of a grid profile's ledger fuel that sits on a plant with a coordinate."""
    from pkinv.report import grid_cube
    return grid_cube.located_activity_share(profile, grid_cube.period_keys())


def _province_share(proxy, province):
    """One cell of data/province_shares.csv - the committed provincial vector (rc62)."""
    import csv as _csv
    import os as _os
    from pkinv.paths import DATA as _DATA
    with open(asset_path(_DATA, "province_shares.csv"), newline="", encoding="utf-8") as h:
        for row in _csv.DictReader(l for l in h if not l.startswith("#")):
            if row["proxy"] == proxy:
                return float(row[province])
    raise KeyError("no province_shares row %r" % proxy)


def _sulfur_central(evidence_id):
    """The booked sulfur central for one evidence row, straight from the register the engine
    reads. Bound rather than transcribed, because these two values moved three times in one
    round and the supplement must not be able to drift behind them."""
    for row in _data_rows_nocomment("activity/industry/fuel_sulfur_evidence.csv"):
        if row["evidence_id"] == evidence_id:
            return float(row["s_pct_central"])
    raise KeyError(evidence_id)


def _sulfur_hi(evidence_id):
    for row in _data_rows_nocomment("activity/industry/fuel_sulfur_evidence.csv"):
        if row["evidence_id"] == evidence_id:
            return float(row["s_pct_hi"])
    raise KeyError(evidence_id)


def _sulfur_lo(evidence_id):
    for row in _data_rows_nocomment("activity/industry/fuel_sulfur_evidence.csv"):
        if row["evidence_id"] == evidence_id:
            return float(row["s_pct_lo"])
    raise KeyError(evidence_id)


def _brick_retention():
    for row in _data_rows_nocomment("air_source_classes.csv"):
        if row["source_class_id"] == "brick_fcbk_mapped":
            return float(row["sulfur_retention_frac"])
    raise KeyError("brick_fcbk_mapped")


def _min_hsfo_share_pct():
    """The lowest high-sulphur share the held import split shows, in percent - the evidence that
    chose between the two furnace-oil centrals."""
    shares = [float(r["hsfo_share"]) for r in
              _data_rows_nocomment("activity/industry/furnace_oil_grade_mix.csv")
              if r["hsfo_share"]]
    return min(shares) * 100.0


def _lahore_so2(period, sector=None):
    """Lahore District SO2 in Gg for one period under the reference configuration."""
    total = 0.0
    for row in _rows_banner("pakemis_air_lahore_by_year.csv"):
        if (row["pollutant"].upper() == "SO2" and row["row_kind"] == "district"
                and row["configuration_id"] == "REF_2023_24" and row["period_id"] == period
                and (sector is None or row["sector_id"] == sector)):
            total += float(row["emissions_Gg"] or 0.0)
    return total


def _lahore_power_share_pct(period):
    """Power's share of Lahore SO2 in one period - the quantity that carries the round's
    mechanism, and the one a reader would otherwise have to take on trust."""
    return _lahore_so2(period, "power") / _lahore_so2(period) * 100.0



# ---- v3: the products the supplement cites by their headline numbers ---------------------
def _basis_share(period, basis):
    """Mass-weighted share (percent) of one spatial evidence class in one period."""
    for r in read_rows("outputs/pakemis_spatial_basis_shares.csv", comments=True):
        if r["period_id"] == period and r["spatial_time_basis"] == basis:
            return 100.0 * float(r["share_of_period"])
    raise AssertionError("no %s/%s row in the taxonomy shares" % (period, basis))


def _fixed_vector_exposure(which):
    """The largest |movement| the per-year provincial split of grid power made: over every
    fuel, period and province ('max'), or within the reference year ('reference'). Through
    rc65 this was the EXPOSURE of a fixed vector, read from a comparator; it is now the size
    of the correction, read from the before-and-after product."""
    rows = read_rows("outputs/pakemis_power_provincial_basis_by_year.csv", comments=True)
    if which == "reference":
        rows = [r for r in rows if r["period_id"] == "FY2023-24"]
    return max(abs(float(r["difference_Mt_CO2e"])) for r in rows)


def _gas_generation_derived_max():
    """The largest share of a period's gas energy that rests on generation and a station's
    own specific consumption, in percent, over the periods before the fuel ledger."""
    rows = read_rows("outputs/pakemis_power_provincial_basis_by_year.csv", comments=True)
    return 100.0 * max(float(r["generation_derived_share"]) for r in rows
                       if r["stream"] == "power_gas")


def _enteric_bridge(species, field):
    for r in read_rows("outputs/pakemis_enteric_btr_bridge.csv", comments=True):
        if r["species"] == species:
            return float(r[field])
    raise AssertionError("no %s row in the enteric bridge" % species)


def _enteric_bridge_btr_only():
    return sum(float(r["btr_Mt_co2e"]) for r in
               read_rows("outputs/pakemis_enteric_btr_bridge.csv", comments=True)
               if r["pakemis_Mt_co2e_AR5"] == "NE")




def _hies_users_share(survey):
    """Design-weighted share of households using dung cake, by survey round (percent)."""
    from pkinv.assets import asset_path
    for r in read_rows(asset_path(paths.DATA, "activity", "residential", "hies",
                                  "hies_national_totals.csv"), comments=True):
        if r["survey"] == survey and r["fuel"] == "dung_cake":
            return 100.0 * float(r["users_share"])
    raise AssertionError("no %s dung_cake row" % survey)


def _hies_dung_change_pct():
    """The HIES 2024-25 national dung-cake quantity over the 2018-19 one, as a percentage change."""
    from pkinv.assets import asset_path
    q = {}
    for r in read_rows(asset_path(paths.DATA, "activity", "residential", "hies",
                                  "hies_national_totals.csv"), comments=True):
        if r["fuel"] == "dung_cake":
            q[r["survey"]] = float(r["annual_total"])
    return 100.0 * (q["hies2025"] / q["hies2019"] - 1.0)


def _five_class_count(label_start):
    for r in read_rows("outputs/pakemis_validation_five_classes_summary.csv", comments=True):
        if r["five_class"].startswith(label_start):
            return float(r["entries"])
    raise AssertionError("no five-class row starting %r" % label_start)




def _btr_within_band_count():
    return float(sum(1 for r in read_rows("outputs/pakemis_btr_comparison.csv", comments=True)
                     if r["tier"] in ("exact", "aggregate") and r["within_0.5_2.0x"] == "YES"))


def _btr_like_for_like_count():
    return float(sum(1 for r in read_rows("outputs/pakemis_btr_comparison.csv", comments=True)
                     if r["tier"] in ("exact", "aggregate")))


def _btr_like_for_like_total_ratio():
    """PakEmis over the submission, summed over the like-for-like categories and nothing else."""
    rows = [r for r in read_rows("outputs/pakemis_btr_comparison.csv", comments=True)
            if r["tier"] in ("exact", "aggregate")]
    return sum(float(r["pakemis_Mt_co2e"]) for r in rows) / sum(float(r["btr_Mt_co2e"]) for r in rows)


def _btr_qualified_count():
    return float(sum(1 for r in read_rows("outputs/pakemis_btr_comparison.csv", comments=True)
                     if r["tier"] in ("aggregate-restated", "scope-gap", "btr-only", "btr-zero",
                                      "btr-elsewhere", "out-of-scope")))


def _configuration_delta(a, b):
    """national_total_Mt of configuration a minus configuration b (inventory_reference allowed)."""
    rows = {r["configuration_id"]: float(r["national_total_Mt"])
            for r in read_rows("outputs/national_configurations.csv", comments=True)}
    return rows[a] - rows[b]




def _rebase_units(which):
    """(smallest, largest) number of districts whose allocation the curated-district re-base
    moved in a period, from the same product rows as _rebase_gross."""
    units = [int(r["units_moved"]) for r in
             read_rows("outputs/pakemis_spatial_rebase_rc44.csv")
             if r["rebase"] == "rc63 curated station district"
             and r["product"] == "pakemis_adm2_sector_by_year.csv"
             and (r["units_moved"] or "").strip()]
    return float(min(units) if which == "min" else max(units))



DOC_CLAIMS = [
    # ---- national: the nine-year spatial products ----
    # Both counts are read back from the products themselves, so a rebuild that changed the
    # number of rows - a period added, a district frame revised - fails here rather than
    # leaving the manuscript quoting a shape the release no longer has.
    ("adm1 by-year row count", "national", "06_results.tex",
     r"pakemis\\_adm1\\_by\\_year\.csv\} \(\\num\{(\d+)\} rows",
     lambda: len(_rows("pakemis_adm1_by_year.csv")), 0.0),
    ("canonical district frame units", "national", "06_results.tex",
     r"the\s*\n?\s*canonical \\num\{(\d+)\}-unit set",
     lambda: len(read_rows(os.path.join(paths.DATA, "adm2_canonical.csv"))), 0.0),
    ("backcast stream years confirmed by hash", "national", "06_results.tex",
     r"all \\num\{(\d+)\} stream-years\s*\n?\s*labelled a backcast",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "reference_shape_backcast"
                 and r["temporal_operator"] == "reference_pattern_reused"), 0.0),
    ("own year stream years", "national", "06_results.tex",
     r"of the \\num\{(\d+)\} labelled as",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "annual_observed_activity"), 0.0),
    ("annual cube megabytes", "national", "06_results.tex",
     r"lattice,\s*\n?\s*\\SI\{([\d.]+)\}\{\\mega\\byte\}",
     lambda: round(os.path.getsize(os.path.join(
         OUT, "pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc")) / 1e6, 1), 0.0),
    ("adm2 monthly by year row count", "national", "06_results.tex",
     r"grain \(\\num\{(\d+)\} rows\)",
     lambda: len(_rows("pakemis_adm2_monthly_by_year.csv")), 0.0),
    ("stream periods in the weight registry", "national", "06_results.tex",
     r"Of \\num\{(\d+)\} stream-periods",
     lambda: len(_rows("pakemis_spatial_weights_by_year.csv")), 0.0),
    ("stream periods carrying no mass", "national", "06_results.tex",
     r"stream-periods, \\num\{(\d+)\} carry no\s*\n?\s*mass",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "not_present"), 0.0),
    ("stream periods carrying mass", "national", "06_results.tex",
     r"the remaining \\num\{(\d+)\} are typed",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] != "not_present"), 0.0),
    ("stream years unallocated below adm1", "national", "06_results.tex",
     r"and \\num\{(\d+)\} are unallocated below ADM1",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "unallocated"), 0.0),
    ("stream years backcast percent", "national", "06_results.tex",
     r"\\num\{\d+\}\s*\n?\s*\(\\SI\{([\d.]+)\}\{\\percent\}\) carry the reference",
     lambda: round(100.0 * sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                               if r["spatial_time_basis"] == "reference_shape_backcast")
                   / sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                         if r["spatial_time_basis"] != "not_present"), 1), 0.0),
    ("stream years measured in their own year", "national", "06_results.tex",
     r"\\num\{(\d+)\} \(\\SI\{[\d.]+\}\{\\percent\}\) were measured for their own",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "annual_observed_activity"), 0.0),
    ("stream years own-year percent", "national", "06_results.tex",
     r"\\num\{\d+\} \(\\SI\{([\d.]+)\}\{\\percent\}\) were measured for their own",
     lambda: round(100.0 * sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                               if r["spatial_time_basis"] == "annual_observed_activity")
                   / sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                         if r["spatial_time_basis"] != "not_present"), 1), 0.0),
    ("stream years timeless percent", "national", "06_results.tex",
     r"\\num\{\d+\} \(\\SI\{([\d.]+)\}\{\\percent\}\) ride a timeless",
     lambda: round(100.0 * sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                               if r["spatial_time_basis"] == "static_structural")
                   / sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                         if r["spatial_time_basis"] != "not_present"), 1), 0.0),
    # The land-cover vintage is a fact about the raster, and the registry already records it
    # per row in surface_vintage - so the manuscript's "2021" is checked against the surface
    # the build actually used, not against memory.
    ("builtup raster vintage", "national", "06_results.tex",
     r"placed on a \\num\{(\d{4})\} land-cover snapshot",
     lambda: int([r["surface_vintage"] for r in _rows("pakemis_spatial_weights_by_year.csv")
                  if r["surface"] == "builtup" and r["surface_vintage"]][0].split()[-1]), 0.0),
    ("stream years on a substitute surface", "national", "06_results.tex",
     r"\\num\{(\d+)\} rode a substitute",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "substituted_surface"), 0.0),
    ("stream years on a timeless surface", "national", "06_results.tex",
     r"\\num\{(\d+)\} \(\\SI\{[\d.]+\}\{\\percent\}\) ride a timeless",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "static_structural"), 0.0),
    # ---- the 2026-10-05 relabelling: the three quantities the correction's own prose prints.
    # All derived from the shipped registry, none of them a constant, because the point of the
    # passage is that these three are what moved and what did not.
    ("relabelled stream years", "national", "06_results.tex",
     r"\\num\{(\d+)\} stream-years were affected",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "static_structural"
                 and r["period_id"] != "FY2023-24"), 0.0),
    # The claim the passage leans on: the quantity of non-evidence did not change, only its
    # kind. Anchored as the SUM of the two classes, so if either moves alone this fails - which
    # is the whole assertion.
    ("timeless and backcast together", "national", "06_results.tex",
     r"account for \\num\{(\d+)\} stream-periods",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] in ("static_structural",
                                                "reference_shape_backcast")), 0.0),
    # The hash fact that found the defect, read from temporal_operator rather than from the
    # label - which is the entire reason the two columns are kept apart.
    ("stream years reusing the reference pattern by hash", "national", "06_results.tex",
     r"\\num\{(\d+)\} non-reference stream-years\s*\n?\s*carry the reference year's pattern",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["temporal_operator"] == "reference_pattern_reused"), 0.0),
    ("stream years carrying the reference pattern", "national", "06_results.tex",
     r"\\num\{(\d+)\}\s*\n?\s*\(\\SI\{[\d.]+\}\{\\percent\}\) carry the reference",
     lambda: sum(1 for r in _rows("pakemis_spatial_weights_by_year.csv")
                 if r["spatial_time_basis"] == "reference_shape_backcast"), 0.0),
    ("grid fleet substituted mass fy2015_16", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} is placed on\s+that substitute in FY2015--16",
     lambda: round(sum(float(r["affected_Mt_AR5"])
                       for r in _rows("pakemis_grid_fallbacks_by_year.csv")
                       if r["period_id"] == "FY2015-16"
                       and r["declared"] == "grid station points"), 2), 0.0),
    # The three per-fuel unlocated fractions, straight from the ledger and the coordinate
    # tables - the same measure the cube now splits each province's share by.
    ("grid gas unlocated percent", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of grid gas",
     lambda: round(100.0 * (1.0 - _located("power_gas")), 1), 0.0),
    ("grid rfo unlocated percent", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of furnace oil",
     lambda: round(100.0 * (1.0 - _located("power_rfo")), 1), 0.0),
    ("grid hsd unlocated percent", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of diesel",
     lambda: round(100.0 * (1.0 - _located("power_hsd")), 1), 0.0),
    # The reference year's own substituted mass, which rc44 moved from 0.34 to 10.05 Mt by
    # pricing the fuel that has no coordinate instead of pooling it onto located siblings.
    ("grid fleet substituted mass reference year", "national", "06_results.tex",
     r"against \\SI\{([\d.]+)\}\{\\mega\\tonne\} in the reference year",
     lambda: round(sum(float(r["affected_Mt_AR5"])
                       for r in _rows("pakemis_grid_fallbacks_by_year.csv")
                       if r["period_id"] == "FY2023-24"
                       and r["declared"] == "grid station points"), 2), 0.0),
    # rc67: A PRINTED HISTORICAL VALUE, pinned, not a live quantity. The sentence narrates
    # what the rc60 Lal Pir match did to the reference year's substituted mass (1.24 to 0.94
    # Mt); no shipped product carries a superseded release's figure, and the live figure is
    # the claim above (0.62). It scored as covered only because the benchmark table printed
    # an unrelated 0.94 (residential over EDGAR), which moved to 0.77 with the survey
    # reference. Same convention as a superseded edition's printed value elsewhere in this
    # registry; if the sentence is dropped, drop this with it.
    ("grid fleet substituted mass after the rc60 match", "national", "06_results.tex",
     r"moves from \\SI\{[\d.]+\}\{\\mega\\tonne\} to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} "
     r"for the same reason",
     lambda: 0.94, 0.0),
    ("adm2 by-year row count", "national", "06_results.tex",
     r"pakemis\\_adm2\\_by\\_year\.csv\} \(\\num\{(\d+)\} rows",
     lambda: len(_rows("pakemis_adm2_by_year.csv")), 0.0),
    # ---- national: sector table ----
    ("national total", "national", "06_results.tex",
     r"\\textbf\{Total\}\s+& FY\d{4}--\d{2} & \\textbf\{([\d.]+)\}", lambda: _sector("TOTAL"), 0.0),
    ("agriculture", "national", "06_results.tex",
     r"Agriculture\s+&[^&]*&\s*([\d.]+)", lambda: _sector("agriculture"), 0.0),
    ("road transport", "national", "06_results.tex",
     r"Transport module\s+&[^&]*&\s*([\d.]+)", lambda: _sector("transport"), 0.0),
    ("electricity", "national", "06_results.tex",
     r"Power module\s+&[^&]*&\s*([\d.]+)", lambda: _sector("power"), 0.0),
    ("waste", "national", "06_results.tex",
     r"Waste\s+&[^&]*&\s*([\d.]+)", lambda: _sector("waste"), 0.0),
    ("residential", "national", "06_results.tex",
     r"Residential fuel\s+&[^&]*&\s*([\d.]+)", lambda: _sector("residential"), 0.0),
    ("cement", "national", "06_results.tex",
     r"Cement \(IPPU\)\s+&[^&]*&\s*([\d.]+)", lambda: _sector("ippu"), 0.0),
    ("fugitives", "national", "06_results.tex",
     r"Oil and gas fugitives\$\^\{e\}\$\s*&[^&]*&\s*([\d.]+)",
     lambda: _sector("fugitives"), 0.0),
    # Unanchored until the liquid fuels landed and moved it from 5.67 to 9.07 with nothing
    # failing. Every other row of this table had a claim; this one was missed because it was
    # the newest, which is exactly when a row is most likely to move.
    ("industrial fuel", "national", "06_results.tex",
     r"Industrial fuel \(1A2\)\s+&[^&]*&\s*([\d.]+)", lambda: _sector("industry"), 0.0),
    ("railways", "national", "06_results.tex",
     r"Railways\s+&[^&]*&\s*([\d.]+)", lambda: _sector("railways"), 0.0),
    ("aviation", "national", "06_results.tex",
     r"Domestic aviation\s+&[^&]*&\s*([\d.]+)", lambda: _sector("aviation"), 0.0),
    ("results opening total", "national", "06_results.tex",
     r"The inventory reports \\SI\{([\d.]+)\}\{\\mega\\tonne\}", lambda: _sector("TOTAL"), 0.0),
    ("national AR6 total", "national", "06_results.tex",
     r"or \\SI\{([\d.]+)\}\{\\mega\\tonne\} on AR6", lambda: _sector("TOTAL", "co2e_Mt_AR6"), 0.0),

    # ---- national: the correlated-uncertainty result, both ends ----
    ("MC independent national", "national", "07_uncertainty.tex",
     r"\\textbf\{National \$\\pm\$\\%\} & national & \\textbf\{([\d.]+)\}",
     lambda: _mc("within_sector", "TOTAL"), 0.0),
    ("MC correlated national", "national", "07_uncertainty.tex",
     r"\\textbf\{National \$\\pm\$\\%\} & national & \\textbf\{[\d.]+\} & \\textbf\{([\d.]+)\}",
     lambda: _mc("cross_sector", "TOTAL"), 0.0),
    ("MC road category independent", "national", "07_uncertainty.tex",
     r"Road transport \$\\pm\$\\%\s+& category &\s*([\d.]+)",
     lambda: _mc("within_sector", "Road transport"), 0.0),
    ("MC road category correlated", "national", "07_uncertainty.tex",
     r"Road transport \$\\pm\$\\%\s+& category &\s*[\d.]+ &\s*([\d.]+)",
     lambda: _mc("cross_sector", "Road transport"), 0.0),

    # ---- national: the level-versus-variance argument ----
    ("enteric variance share", "national", "08_key_categories.tex",
     r"Enteric fermentation & 3\.A\.1 & agriculture & [\d.]+ & [\d.]+ & ([\d.]+)",
     lambda: _keycat("Enteric fermentation", "variance_share_pct_independent_approx"), 0.05),
    ("fugitives variance share", "national", "08_key_categories.tex",
     r"Fugitive emissions, oil and gas\$\^\{e\}\$ & 1\.B\.2 & fugitives & [\d.]+ & [\d.]+ & ([\d.]+)",
     lambda: _keycat("Fugitive emissions from oil and gas", "variance_share_pct_independent_approx"), 0.05),
    ("transport variance share", "national", "08_key_categories.tex",
     r"Road transportation & 1\.A\.3\.b & transport & [\d.]+ & [\d.]+ & ([\d.]+)",
     lambda: _keycat("Road transport", "variance_share_pct_independent_approx"), 0.05),

    # ---- national: the headline, everywhere it appears ----
    # The abstract, the introduction and the conclusion each quoted a DIFFERENT vintage of
    # the national total while the results table was current, because only the table was
    # anchored. Coverage breadth, not mechanism, was the defect; these close it.
    # rc52: the uncertainty section quotes the deterministic reference three times and the
    # discussion quotes the methane share; each is registered so no printed quantity is
    # checked against nothing
    ("uncertainty deterministic reference (band)", "national", "07_uncertainty.tex",
     r"reference\} \\SI\{([\d.]+)\}\{\\mega\\tonne\} is \$", lambda: _sector("TOTAL"), 0.0),
    ("uncertainty deterministic reference (recommended point)", "national", "07_uncertainty.tex",
     r"reference \\SI\{([\d.]+)\}\{\\mega\\tonne\} for accounting", lambda: _sector("TOTAL"), 0.0),
    ("uncertainty total rests on the axes", "national", "07_uncertainty.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} total rests on \\num\{\d+\} such choices", lambda: _sector("TOTAL"), 0.0),
    ("discussion methane share", "national", "11_discussion.tex",
     r"At \\SI\{([\d.]+)\}\{\\percent\} of the national\s*total on AR5", lambda: _gas("CH4", "share"), 0.0),
    ("national total in abstract", "national", "00_abstract.tex",
     r"reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} \(AR5",
     lambda: _sector("TOTAL"), 0.0),
    ("national AR6 total in abstract", "national", "00_abstract.tex",
     r"\(AR5, \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*\n?on AR6\)",
     lambda: _sector("TOTAL", "co2e_Mt_AR6"), 0.0),
    # rc67: the roles swapped. This sentence now introduces the reference as the survey
    # reading and prices configuration L, the destination assumption, beside it. The label
    # keeps its rc66 wording because data/claim_matrix.csv (abs_total_S) and a national-v3
    # claim resolve through it by name; what it reads is the ALTERNATIVE's total.
    ("survey-configuration total in abstract", "national", "00_abstract.tex",
     r"destination assumption~L gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sector_alt("TOTAL"), 0.0),
    ("national total in introduction", "national", "01_introduction.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} under reference scenario",
     lambda: _sector("TOTAL"), 0.0),
    # Parameter coverage (Section 7, "Parameter coverage, and what the variance is attributed
    # to"). Every one of these is a property of the registry or of the decomposition, so the
    # subsection cannot drift from the machinery it describes.
    ("scenario axis count", "national", "07_uncertainty.tex",
     r"total rests on \\num\{(\d+)\} such choices",
     lambda: float(len(_scenario_axes())), 0.0),
    ("validation scorecard covered cells", "national", "07_uncertainty.tex",
     r"and \\num\{(\d+)\} of its \\num\{36\} cells are covered",
     lambda: _validation_scorecard_covered(), 0.0),
    ("validation scorecard cell space", "national", "07_uncertainty.tex",
     r"of its \\num\{(\d+)\} cells are covered",
     lambda: float(len(_validation_catalog_rows("pakemis_validation_scorecard.csv"))), 0.0),
    ("paramcov component rows", "national", "07_uncertainty.tex",
     r"Of the \\num\{(\d+)\} component rows",
     lambda: _decomposed_component_count(), 0.0),
    ("paramcov rows with a named parameter", "national", "07_uncertainty.tex",
     r"component rows, \\num\{(\d+)\} carry at least one named parameter",
     lambda: _named_parameter_component_count(), 0.0),
    ("paramcov rows with several", "national", "07_uncertainty.tex",
     r"named parameter and \\num\{(\d+)\}\s*carry more than one",
     lambda: _multi_group_component_count(), 0.0),
    ("paramcov registry size", "national", "07_uncertainty.tex",
     r"registry\s*holds \\num\{(\d+)\} parameters",
     lambda: _parameter_registry("parameters"), 0.0),
    ("paramcov drawn groups", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} dependency groups carry variance",
     lambda: _parameter_registry("drawn_groups"), 0.0),
    ("paramcov shared groups", "national", "07_uncertainty.tex",
     r"and\s*(\d+) of those enter more than one row",
     lambda: _parameter_registry("shared_groups"), 0.0),
    ("paramcov over-decomposed rows", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} rows remain derived",
     lambda: _over_decomposed_component_count(), 0.0),
    ("paramcov audited rows", "national", "07_uncertainty.tex",
     r"audit register carries \\num\{(\d+)\} dispositioned rows",
     lambda: float(len(__import__("pkinv.core.parameters", fromlist=["x"])
                       .load_dispositions())), 0.0),
    # The MC surface literals the interval paragraph prints (rc18: they moved
    # when agriculture's parameters were named, and now they are pinned).
    ("MC band low", "national", "07_uncertainty.tex",
     r"\(\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}\) read against",
     lambda: _mc("within_sector", "TOTAL", "P2.5_Mt"), 0.05),
    ("MC band high", "national", "07_uncertainty.tex",
     r"\(\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}\) read against",
     lambda: _mc("within_sector", "TOTAL", "P97.5_Mt"), 0.05),
    ("MC median", "national", "07_uncertainty.tex",
     r"\(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\) and mean",
     lambda: _mc("within_sector", "TOTAL", "P50_Mt"), 0.05),
    ("MC mean", "national", "07_uncertainty.tex",
     r"and mean \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _mc("within_sector", "TOTAL", "mean_Mt"), 0.05),
    # The trajectories product's counts (rc18).
    ("trajectories priced count", "national", "07_uncertainty.tex",
     r"(\d+) axis-years priced on their\s*own years' activity",
     lambda: float(sum(1 for r in
                       _csv_rows("pakemis_structural_trajectories.csv")
                       if r["status"] == "priced")), 0.0),
    ("trajectories refused count", "national", "07_uncertainty.tex",
     r"\((\d+) refusals;",
     lambda: float(sum(1 for r in
                       _csv_rows("pakemis_structural_trajectories.csv")
                       if r["status"] == "not_priceable_for_year")), 0.0),
    # rc67: the six "paramcov" claims on the surrogate Sobol attribution (sample count,
    # residual share, agriculture's residual, the largest residual, the buffalo enteric
    # factor's index and the superseded leader) are DELETED with their sentences: the
    # product they read, national_variance_attribution.csv, is retired. The section now
    # states the released ensemble's own shares, from pakemis_uncertainty_drivers.csv.
    ("drivers enteric variance share", "national", "07_uncertainty.tex",
     r"Enteric fermentation carries \\SI\{([\d.]+)\}\{\\percent\} of the variance",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="category", name="Enteric fermentation"), 0.0),
    ("drivers managed soils variance share", "national", "07_uncertainty.tex",
     r"of the variance,\s*managed soils \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="category", name="Managed soils"), 0.0),
    ("drivers wastewater variance share", "national", "07_uncertainty.tex",
     r"domestic wastewater \\SI\{([\d.]+)\}\{\\percent\}, manure",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="category", name="Domestic wastewater"), 0.0),
    ("drivers manure variance share", "national", "07_uncertainty.tex",
     r"manure\s*management \\SI\{([\d.]+)\}\{\\percent\} and rice",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="category", name="Manure management"), 0.0),
    ("drivers rice variance share", "national", "07_uncertainty.tex",
     r"rice cultivation \\SI\{([\d.]+)\}\{\\percent\}; by module",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="category", name="Rice cultivation"), 0.0),
    ("drivers agriculture module variance share", "national", "07_uncertainty.tex",
     r"agriculture carries \\SI\{([\d.]+)\}\{\\percent\} and waste",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="sector", name="agriculture"), 0.0),
    ("drivers waste module variance share", "national", "07_uncertainty.tex",
     r"and waste \\SI\{([\d.]+)\}\{\\percent\}\. The upper tail",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="sector", name="waste"), 0.0),
    ("drivers enteric upper tail share", "national", "07_uncertainty.tex",
     r"enteric fermentation is\s*\\SI\{([\d.]+)\}\{\\percent\}, managed soils",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv",
                                  "upper_tail_excess_share",
                                  grain="category", name="Enteric fermentation"), 0.0),
    ("drivers managed soils upper tail share", "national", "07_uncertainty.tex",
     r"managed soils \\SI\{([\d.]+)\}\{\\percent\} and domestic wastewater",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv",
                                  "upper_tail_excess_share",
                                  grain="category", name="Managed soils"), 0.0),
    ("drivers wastewater upper tail share", "national", "07_uncertainty.tex",
     r"and domestic wastewater\s*\\SI\{([\d.]+)\}\{\\percent\}\. With enteric",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv",
                                  "upper_tail_excess_share",
                                  grain="category", name="Domestic wastewater"), 0.0),
    ("drivers unconditional interval low", "national", "07_uncertainty.tex",
     r"narrows\s*from \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} to",
     lambda: _first_where("pakemis_ensemble_summary.csv", "P2.5_Mt",
                          name="NATIONAL_TOTAL"), 0.0),
    ("drivers unconditional interval high", "national", "07_uncertainty.tex",
     r"narrows\s*from \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} to",
     lambda: _first_where("pakemis_ensemble_summary.csv", "P97.5_Mt",
                          name="NATIONAL_TOTAL"), 0.0),
    ("drivers enteric-fixed interval low", "national", "07_uncertainty.tex",
     r"\{\\mega\\tonne\} to \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}\.\s*\n\s*\n"
     r"The product carries",
     lambda: _first_where("pakemis_uncertainty_drivers.csv", "national_p2_5_if_fixed",
                          grain="category", name="Enteric fermentation"), 0.0),
    ("drivers enteric-fixed interval high", "national", "07_uncertainty.tex",
     r"\{\\mega\\tonne\} to \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}\.\s*\n\s*\n"
     r"The product carries",
     lambda: _first_where("pakemis_uncertainty_drivers.csv", "national_p97_5_if_fixed",
                          grain="category", name="Enteric fermentation"), 0.0),
    ("drivers effluent factor variance share", "national", "07_uncertainty.tex",
     r"same draws, carries \\SI\{([\d.]+)\}\{\\percent\} of the\s*national variance",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="parameter", sector="waste"), 0.0),
    ("drivers effluent factor upper tail share", "national", "07_uncertainty.tex",
     r"national variance and \\SI\{([\d.]+)\}\{\\percent\} of the upper tail",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv",
                                  "upper_tail_excess_share",
                                  grain="parameter", sector="waste"), 0.0),
    ("dung variants survey activity uncertainty", "national", "07_uncertainty.tex",
     r"dung stream is drawn at \\SI\{(\d+)\}\{\\percent\}\s*activity uncertainty",
     lambda: _res_param("activity_uncert_dung_survey"), 0.0),

    ("national total in conclusion", "national", "13_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} on AR5 under reference scenario",
     lambda: _sector("TOTAL"), 0.0),
    # Both uncertainty endpoints, at every prose site that quotes them.
    ("MC national low in abstract", "national", "00_abstract.tex",
     r"the national interval is\s*\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("within_sector", "TOTAL"), 0.0),
    # The abstract's and discussion's second figures retired at rc16: the two
    # scenarios round to the same value, so one anchor covers each sentence and a
    # second would pin a difference that no longer exists.
    ("MC national in discussion", "national", "11_discussion.tex",
     r"leaves the national uncertainty at \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("within_sector", "TOTAL"), 0.0),
    ("MC national low in conclusion", "national", "13_conclusion.tex",
     r"uncertainty at \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ either way",
     lambda: _mc("within_sector", "TOTAL"), 0.0),

    # ---- sector papers: the totals their PROSE quotes ----
    # Each of these was anchored in its own results TABLE and unanchored three paragraphs
    # away, so the tables re-anchored at the harmonisation round and the sentences did not.
    # The waste paper printed 36.96 Mt in four places beside a table reading 37.91, and its
    # own EDGAR ratio of 143 percent was computed from the table it disagreed with. The
    # sector papers are not yet under the unregistered-quantity sweep - that is a known and
    # separately tracked debt - so the headline each one leads with is registered here.
    ("agriculture share of national, abstract", "agriculture", "00_abstract.tex",
     r"agriculture is \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _sector("agriculture") / float(_sector_row("TOTAL")["co2e_Mt_AR5"]), 0.05),
    ("agriculture national total, abstract", "agriculture", "00_abstract.tex",
     r"\\percent\} of \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: float(_sector_row("TOTAL")["co2e_Mt_AR5"]), 0.005),
    ("agriculture share of national, introduction", "agriculture", "01_introduction.tex",
     r"agriculture is \\SI\{([\d.]+)\}\{\\percent\} of the national total",
     lambda: 100.0 * _sector("agriculture") / float(_sector_row("TOTAL")["co2e_Mt_AR5"]), 0.05),
    ("agriculture share of national, conclusion", "agriculture", "09_conclusion.tex",
     r"Agriculture is \\SI\{([\d.]+)\}\{\\percent\} of that national total",
     lambda: 100.0 * _sector("agriculture") / float(_sector_row("TOTAL")["co2e_Mt_AR5"]), 0.05),
    ("waste sector total, introduction", "waste", "01_introduction.tex",
     r"a sector total of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sector("waste"), 0.005),
    ("waste sector total, results prose", "waste", "06_results.tex",
     r"waste sector emitted \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sector("waste"), 0.005),
    ("waste sector total, validation", "waste", "05_validation.tex",
     r"This inventory reports \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sector("waste"), 0.005),
    ("waste sector total, river comparison", "waste", "07_discussion.tex",
     r"or \\SI\{([\d.]+)\}\{\\mega\\tonne\} against",
     lambda: _sector("waste"), 0.005),
    ("waste river sector total", "waste", "07_discussion.tex",
     r"against\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} for the sector",
     lambda: _waste_river_sector_total(), 0.005),
    ("residential total, results prose", "residential", "06_results.tex",
     r"households emitted \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sector("residential"), 0.005),
    # rc67: the survey is the reference and _sector_alt reads the ledger rollup, which is
    # configuration L. The label below still says "S" because a national-v3 claim resolves
    # through it by name (_as_registered); what it anchors is the residential total under
    # configuration L, printed beside the reference.
    ("residential total S, results prose", "residential", "06_results.tex",
     r"under the reference \(\\SI\{([\d.]+)\}\{\} under configuration~L",
     lambda: _sector_alt("residential"), 0.005),
    ("residential total, validation", "residential", "05_validation.tex",
     r"This inventory reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} under the reference",
     lambda: _sector("residential"), 0.005),
    ("residential total L, validation", "residential", "05_validation.tex",
     r"or \\SI\{([\d.]+)\}\{\} under configuration~L",
     lambda: _sector_alt("residential"), 0.005),

    # ---- the release record: docs/reproducibility.md and docs/qa_qc.md ----
    # These are the numbers that were stale. Registered against the same outputs the
    # manuscripts read, so the release record cannot describe a release again.
    # rc67: the roles swapped, so each row of the page's table is anchored on its own dung
    # basis: the baseline is the survey row (the rollup), configuration L the ledger row
    # (the alternative rollup). The mechanical update had left each value under the other
    # row's label.
    ("release record baseline residential", "release-record", "reproducibility.md",
     r"HIES reported cake \(household demand\) \| ([\d.]+) Mt",
     lambda: _sector_row("residential")["co2e_Mt_AR5"] and
             float(_sector_row("residential")["co2e_Mt_AR5"]), 0.005),
    ("release record baseline national", "release-record", "reproducibility.md",
     r"HIES reported cake \(household demand\) \| [\d.]+ Mt \| \*\*([\d.]+) Mt\*\*",
     lambda: float(_sector_row("TOTAL")["co2e_Mt_AR5"]), 0.005),
    ("release record residential L", "release-record", "reproducibility.md",
     r"nitrogen ledger \(all diverted supply\) \| ([\d.]+) Mt",
     lambda: _sector_alt("residential"), 0.005),
    ("release record national L", "release-record", "reproducibility.md",
     r"nitrogen ledger \(all diverted supply\) \| [\d.]+ Mt \| \*\*([\d.]+) Mt\*\*",
     lambda: _sector_alt("TOTAL"), 0.005),
    ("release record configuration ratio", "release-record", "reproducibility.md",
     # the diverted supply over the 2024-25 HIES round AS MEASURED (11.97 Mt), which is the
     # basis the page states; the reference's interpolated 10.93 Mt would give 5.4
     r"same evidence, a factor of ([\d.]+) apart on the\s*2024-25 survey round",
     lambda: 1e9 * _cell("residential_dung_ledger_2024.csv", "claimant",
                         "Diverted to fuel (agriculture ledger)", "Mt_air_dry")
             / _cell("residential_hies_comparison_2024.csv", "fuel", "dung_cake",
                     "hies2425_annual"), 0.0),
    ("release record flat share", "release-record", "reproducibility.md",
     r"\*\*([\d.]+) percent\*\* of the national total sits on a flat",
     lambda: _temporal_share("T4"), 0.05),
    ("release record flat share, limits", "release-record", "reproducibility.md",
     r"([\d.]+) percent of the inventory\s*carries a flat profile",
     lambda: _temporal_share("T4"), 0.05),
    ("qa note test count", "release-record", "qa_qc.md",
     r"\*\*(\d+) defined test functions across ten sectors\*\*",
     lambda: _test_function_count(), 0.0),

    # ---- national supplement: the sulfur evidence adopted at rc63 ----
    # Every one of these is read from the register or the products, not transcribed. Two of them
    # moved three times in a single round, which is exactly the drift a claim exists to stop.
    ("supplement brick sulfur central", "national-supplement", "supplement.tex",
     r"their mean, \\SI\{([\d.]+)\}\{\\percent\}, replaces",
     lambda: _sulfur_central("coal_punjab_fields"), 0.0),
    ("supplement furnace oil central", "national-supplement", "supplement.tex",
     r"booked at\s*\n?\\SI\{([\d.]+)\}\{\\percent\} and",
     lambda: _sulfur_central("fo_hsfo_grade_mix"), 0.0),
    ("supplement hsfo ceiling", "national-supplement", "supplement.tex",
     r"\\SIrange\{0.5\}\{([\d.]+)\}\{\\percent\} specification span",
     lambda: _sulfur_hi("fo_hsfo_grade_mix"), 0.0),
    ("supplement min hsfo share", "national-supplement", "supplement.tex",
     r"\\SIrange\{([\d.]+)\}\{100\}\{\\percent\} high-sulphur",
     lambda: _min_hsfo_share_pct(), 0.1),
    ("supplement retired power central", "national-supplement", "supplement.tex",
     r"and\s*\n?\\SI\{([\d.]+)\}\{\\percent\}: one national fuel",
     lambda: _sulfur_central("power_rfo_spec_range"), 0.0),
    ("supplement furnace oil ratio", "national-supplement", "supplement.tex",
     r"a factor of\s*\n?\\num\{([\d.]+)\} apart",
     lambda: _sulfur_central("fo_hsfo_grade_mix") / _sulfur_central("power_rfo_spec_range"), 0.01),
    ("supplement max hsfo share", "national-supplement", "supplement.tex",
     r"\\SIrange\{[\d.]+\}\{([\d]+)\}\{\\percent\} high-sulphur",
     lambda: max(float(r["hsfo_share"]) for r in
                 _data_rows_nocomment("activity/industry/furnace_oil_grade_mix.csv")
                 if r["hsfo_share"]) * 100.0, 0.1),
    ("supplement spec span floor", "national-supplement", "supplement.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\} specification span",
     lambda: _sulfur_lo("power_rfo_spec_range"), 0.0),
    ("supplement brick retention", "national-supplement", "supplement.tex",
     r"declared \\SI\{([\d.]+)\}\{\} retention",
     lambda: _brick_retention(), 0.0),
    ("supplement lahore so2 open", "national-supplement", "supplement.tex",
     r"SO\$_2\$ to\s*\n?\\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _lahore_so2("FY2015-16"), 0.01),
    ("supplement lahore power share", "national-supplement", "supplement.tex",
     r"rose to \\SI\{([\d]+)\}\{\\percent\} from\s*\n?roughly",
     lambda: _lahore_power_share_pct("FY2015-16"), 1.0),

    # ---- national: the monthly layer (Section 6, "Monthly resolution") ----
    # Registered in the commit that wrote the section. Every one of these is read from a
    # generated table, including the class shares, which is the whole argument for having
    # written temporal_profile.csv rather than typing four percentages.
    ("monthly T1 share", "national", "06_results.tex",
     r"national inventory is \\SI\{([\d.]+)\}\{\\percent\} TE1",
     lambda: _temporal_share("T1"), 0.05),
    ("monthly T2 share", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} TE2", lambda: _temporal_share("T2"), 0.05),
    ("monthly T3 share", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} TE3", lambda: _temporal_share("T3"), 0.05),
    ("monthly T4 share", "national", "06_results.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} TE4", lambda: _temporal_share("T4"), 0.05),
    ("monthly peak", "national", "06_results.tex",
     r"peaks in August at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _month_total("202308"), 0.005),
    ("monthly trough", "national", "06_results.tex",
     r"troughs in April at\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _month_total("202404"), 0.005),
    ("monthly flat year", "national", "06_results.tex",
     r"against a flat \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _national_monthly_total() / 12.0, 0.005),
    ("monthly peak trough ratio", "national", "06_results.tex",
     r"a ratio of \\num\{([\d.]+)\}",
     lambda: _month_total("202308") / _month_total("202404"), 0.005),
    ("power newly timed mass", "national", "06_results.tex",
     r"newly timed mass\s*\(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     _power_grid_shaped_mass, 0.005),
    ("power newly timed mass, history", "national", "06_results.tex",
     r"new evidence about\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\} that had sat flat",
     _power_grid_shaped_mass, 0.005),
    ("monthly livestock share", "national", "06_results.tex",
     r"categories---\\SI\{([\d.]+)\}\{\\percent\} of the national inventory",
     lambda: 100.0 * sum(_sum_where("national_monthly_2024.csv", "co2e_Mt_AR5",
                                    category=c)
                         for c in ("Enteric fermentation", "Manure management"))
             / _national_monthly_total(), 0.005),
    ("monthly livestock soils flat", "national", "06_results.tex",
     r"an observed monthly basis for \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("national_monthly_2024.csv", "co2e_Mt_AR5",
                        category="Managed soils", temporal_method="T4"), 0.005),
    ("abstract monthly T4 share", "national", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the national total sits on a flat profile",
     lambda: _temporal_share("T4"), 0.05),
    ("limitations monthly T4 share", "national", "12_limitations.tex",
     # Re-anchored when the paragraph was rewritten to lead with the three figures. The
     # reference-year T4 share is still stated - it is true - but it is now explicitly framed
     # as the number that cannot distinguish physics from ignorance, so the anchor moved with
     # the sentence rather than the claim being quietly dropped.
     r"\\SI\{([\d.]+)\}\{\\percent\} of the reference year on a flat\s*\n?profile",
     lambda: _temporal_share("T4"), 0.05),
    ("seasonality caption T4 share", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the inventory sits in the flat TE4 band",
     lambda: _temporal_share("T4"), 0.05),

    # ---- national: the abstract's own completeness and coverage sentence ----
    # Registered because it was wrong. The abstract said 81 combinations and 39 estimated
    # while the generated table beside it said 82 and 40, and 88 percent of EDGAR while the
    # benchmark row said 89 - three superseded numbers in four lines of the most-read
    # paragraph in the paper, none of which any test could see.
    ("abstract completeness rows", "national", "00_abstract.tex",
     r"notation keys over (\d+)\s*category--gas combinations",
     lambda: len(_rows("completeness.csv")), 0.0),

    # ---- national: the introduction's contribution list ----
    ("introduction enteric share", "national", "01_introduction.tex",
     r"enteric fermentation alone is \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _keycat("Enteric fermentation", "level_pct"), 0.0),
    ("introduction residential share", "national", "01_introduction.tex",
     r"residential biomass is \\SI\{([\d.]+)\}\{\\percent\} of national",
     lambda: _keycat("Residential fuel combustion", "level_pct"), 0.0),
    ("introduction completeness rows", "national", "01_introduction.tex",
     r"notation keys are reported\s*over all \\num\{(\d+)\}",
     lambda: len(_rows("completeness.csv")), 0.0),
    # The contract-invariant count drifted from 19 to 23 as invariants were added, in three
    # places at once, and the review did not catch it either. It is now the length of the
    # file that enforces them.
    ("introduction contract invariants", "national", "01_introduction.tex",
     r"architecture\} in which \\num\{(\d+)\} contract invariants",
     lambda: _contract_invariant_count(), 0.0),
    ("architecture contract invariants", "national", "03_architecture.tex",
     r"subject to \\num\{(\d+)\} invariants", lambda: _contract_invariant_count(), 0.0),
    ("architecture invariants in caption", "national", "03_architecture.tex",
     r"caption\{The \\num\{(\d+)\} contract invariants",
     lambda: _contract_invariant_count(), 0.0),
    # The two held-product figures. Registered because the paragraph they sit in is an
    # ADMISSION about what CI does not cover, and an admission that quietly stops being true
    # is worse than no admission: if a producer gains a --check mode the second number must
    # move, and if a hand-run product is added the first must.
    ("architecture held products", "national", "03_architecture.tex",
     r"\\num\{(\d+)\} of the shipped products are \\emph\{held\}",
     lambda: _held_product_count(), 0.0),
    ("architecture held products checkable", "national", "03_architecture.tex",
     r"Only \\num\{(\d+)\} of the \\num\{\d+\} are\s*\n?re-derived and compared",
     lambda: _held_product_count(checkable=True), 0.0),
    ("architecture held products rewriting", "national", "03_architecture.tex",
     r"for\s*\n?\\num\{(\d+)\} the only recorded instruction is the producer",
     lambda: _held_product_count(mode="rewrites"), 0.0),
    ("architecture held products unverified", "national", "03_architecture.tex",
     r"the remaining \\num\{(\d+)\} record no verification",
     lambda: _held_product_count(mode="none"), 0.0),
    # "The engine ships N tests" was 319 while the suite held over a thousand - a claim
    # about the paper's own reproducibility argument, three times out of date.
    ("architecture test count", "national", "03_architecture.tex",
     r"The engine ships \\num\{(\d+)\} defined test functions",
     lambda: _test_function_count(), 0.0),
    ("appendix test count", "national", "14_appendix.tex",
     r"The full test suite---\\num\{(\d+)\} defined test functions",
     lambda: _test_function_count(), 0.0),
    ("appendix contract invariants", "national", "14_appendix.tex",
     r"test functions including the \\num\{(\d+)\} contract invariants",
     lambda: _contract_invariant_count(), 0.0),
    ("architecture invariants in verification", "national", "03_architecture.tex",
     r"test functions\. Beyond the \\num\{(\d+)\} contract invariants",
     lambda: _contract_invariant_count(), 0.0),
    ("appendix agriculture share", "national", "14_appendix.tex",
     r"it is\s*\\SI\{(\d+)\}\{\\percent\} of the national total",
     lambda: float(_sector_row("agriculture")["share_pct"]), 0.0),
    ("conclusion road independent", "national", "13_conclusion.tex",
     r"road transport's\s*at \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("within_sector", "Road transport"), 0.05),
    # The correlated twin retired at rc16 with its movement: the conclusion now
    # states one road figure because both scenarios round to it.
    ("conclusion contract invariants", "national", "13_conclusion.tex",
     r"a common contract enforced by \\num\{(\d+)\} invariants",
     lambda: _contract_invariant_count(), 0.0),

    # ---- national: the closures, the rail cross-check and the firewood limitation ----
    # Written in this round, and registered in the same commit rather than a release later,
    # which is the habit the coverage test exists to enforce.
    ("closure generator carve-out", "national", "04_closures.tex",
     r"FY2023--24---from HIES generator-fuel expenditure|"
     r"the quantity---\\SI\{([\d.]+)\}\{\\kilo\\tonne\} of petrol in",
     lambda: _generator_petrol_kt(), 0.0),
    ("rail cross-source gap", "national", "10_benchmarks.tex",
     r"differ by \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: abs(_ocac_rail("rel_pct")), 0.0),
    ("rail cross-source panel", "national", "10_benchmarks.tex",
     r"\\SI\{(\d+)\}\{\\tonne\} against", lambda: _ocac_rail("panel_value"), 0.0),
    ("rail cross-source printed", "national", "10_benchmarks.tex",
     r"against \\SI\{(\d+)\}\{\\tonne\}", lambda: _ocac_rail("printed_value"), 0.0),
    ("limitations firewood energy share", "national", "12_limitations.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of household input", lambda: _fuel_share("Firewood"), 0.0),
    ("limitations dung energy share", "national", "12_limitations.tex",
     # rc67: firewood is the LARGEST household fuel under the survey reference, so the
     # sentence sets dung cake against it rather than ahead of it
     r"against dung cake's \\SI\{([\d.]+)\}\{\\percent\}", lambda: _fuel_share("Dung cake"), 0.0),
    ("limitations firewood uncertainty", "national", "12_limitations.tex",
     r"reported at\s*\\SI\{([\d.]+)\}\{\\percent\}", lambda: _res_param("activity_uncert_woodfuel"), 0.0),
    ("architecture firewood sensitivity", "national", "03_architecture.tex",
     r"firewood excluded, at \$-\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _res_param("activity_uncert_woodfuel"), 0.0),
    ("limitations firewood faostat case", "national", "12_limitations.tex",
     r"which puts the sector at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("residential_uncertainty_scenarios_2024.csv", "structural_scenario",
                   "firewood_faostat", "deterministic"), 0.0),
    ("limitations firewood excluded", "national", "12_limitations.tex",
     r"Dropping firewood entirely gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("residential_uncertainty_scenarios_2024.csv", "structural_scenario",
                   "firewood_none", "deterministic"), 0.0),

    # Harmonisation-round registrations: values that were tier-2 repeats until the numbers
    # they repeated moved, at which point the coverage test surfaced every one of them.
    ("introduction contract tests", "national", "01_introduction.tex",
     r"the contract is enforced by\s*\\num\{(\d+)\} tests",
     lambda: _contract_invariant_count(), 0.0),
    ("introduction EDGAR coverage", "national", "01_introduction.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the\s*corresponding EDGAR aggregate magnitude",
     lambda: 100 * _bench("EDGAR", "NATIONAL"), 0.0),
    ("architecture contract tests", "national", "03_architecture.tex",
     r"groups the \\num\{(\d+)\} contract tests", lambda: _contract_invariant_count(), 0.0),
    ("results AR6 difference", "national", "06_results.tex",
     r"AR5-to-AR6 difference is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sector("TOTAL") - _sector("TOTAL", "co2e_Mt_AR6"), 0.0),
    ("power parametric band", "national", "07_uncertainty.tex",
     r"parametric band fell to \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("within_sector", "power"), 0.0),
    # The sentence now states ONE number for both scopes, so both scenarios anchor the
    # same printed digit: if they ever diverge past rounding, one of these fails.
    ("national interval high in uncertainty", "national", "07_uncertainty.tex",
     r"symmetric summary\s*\\SI\{([\d.]+)\}\{\\percent\}; \$-\\SI",
     lambda: _mc("cross_sector", "TOTAL"), 0.05),
    ("limitations national total", "national", "12_limitations.tex",
     r"ten sectors totalling\s*\\SI\{(\d+)\}\{\\mega\\tonne\}", lambda: _sector("TOTAL"), 0.0),

    # The source-archival audit, registered in the same commit that wrote it into the paper.
    ("results archival audit total", "national", "06_results.tex",
     r"found\s*\\num\{(\d+)\} of \\num\{\d+\} activity files",
     lambda: _source_register_count("not-archived"), 0.0),
    ("results activity file count", "national", "06_results.tex",
     r"of \\num\{(\d+)\} activity files", lambda: _source_register_count(None), 0.0),
    # The same count appears in three files. Registering only the one in 06_results left the
    # other two unprotected, and they held 138 for a release after the register moved to 139.
    ("conclusion activity file count", "national", "13_conclusion.tex",
     r"of \\num\{(\d+)\} activity files cite", lambda: _source_register_count(None), 0.0),
    # 2026-10-07: the coal-energy booking table is a SEVENTH own-compiled row, so the
    # unchanged remainder is the register less seven, not less six. The sentence says
    # "The other", capitalised, because the clause that precedes it is now its own
    # sentence naming that seventh.
    ("conclusion activity files unchanged", "national", "13_conclusion.tex",
     r"The other \\num\{(\d+)\} rows are\s*unchanged",
     lambda: _source_register_count(None) - 7, 0.0),
    ("appendix activity file count", "national", "14_appendix.tex",
     r"and \\num\{\d+\} of \\num\{(\d+)\} cite", lambda: _source_register_count(None), 0.0),
    ("appendix not-archived count", "national", "14_appendix.tex",
     r"and \\num\{(\d+)\} of \\num\{\d+\} cite",
     lambda: _source_register_count("not-archived"), 0.0),
    ("results industry liquids", "national", "06_results.tex",
     r"customer class \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _industry_liquid_mt(), 0.0),
    ("benchmarks managed soils ratio", "national", "10_benchmarks.tex",
     r"Managed soils at \\num\{([\d.]+)\} of FAOSTAT",
     lambda: _bench("FAOSTAT", "Managed soils"), 0.0),

    # The chemical-industries filing value was a whitelisted constant until the ammonia
    # reconciliation published it as a benchmark row -- at which point a constant that also
    # appears in an engine output is a result somebody exempted, and both prose sites
    # anchor to the row instead.
    # The commercial/institutional floor, pinned to the audit's own arithmetic.
    ("limitations commercial floor", "national", "12_limitations.tex",
     r"screened at\s*roughly \\SI\{([\d.]+)\}\{\\mega\\tonne\} across its two "
     r"quantifiable streams",
     lambda: __import__("pkinv.report.commercial_audit",
                        fromlist=["x"]).quantified_floor_mt(), 0.05),

    # The dung-variants paragraph, each mass and the delta span pinned to the pricing.
    ("dung variants household mass", "national", "07_uncertainty.tex",
     r"observes \\SI\{([\d.]+)\}\{\\mega\\tonne\} of dung cake",
     lambda: float(_rows("national_dung_variants.csv")[0]["household_Mt"]), 0.0),
    ("dung variants unresolved mass", "national", "07_uncertainty.tex",
     r"other \\SI\{([\d.]+)\}\{\\mega\\tonne\} went",
     lambda: float(_rows("national_dung_variants.csv")[0]["diverted_Mt"])
             - float(_rows("national_dung_variants.csv")[0]["household_Mt"]), 0.0),
    ("dung variants delta floor", "national", "07_uncertainty.tex",
     r"worth between \\num\{([\d.]+)\} and",
     lambda: min(float(r["delta_vs_S_Mt_co2e_AR5"])
                 for r in _rows("national_dung_variants.csv")
                 if float(r["delta_vs_S_Mt_co2e_AR5"]) > 0), 0.0),
    ("dung variants delta ceiling", "national", "07_uncertainty.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} depending on where it went",
     lambda: max(float(r["delta_vs_S_Mt_co2e_AR5"])
                 for r in _rows("national_dung_variants.csv")), 0.0),

    # The three priority rankings' top entries, each pinned to the generated ranking so
    # the subsection cannot quietly keep an answer the join has replaced.
    ("priorities structural top", "national", "07_uncertainty.tex",
     r"coal energy basis at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: float(_ranking_top("structural")), 0.05),
    ("priorities coverage top", "national", "07_uncertainty.tex",
     r"EDGAR carries \\SI\{([\d.]+)\}\{\\mega\\tonne\} for 1\.A\.2",
     lambda: float(_ranking_top("coverage")), 0.0),

    ("completeness chemical-industries filing", "national", "09_completeness.tex",
     r"chemical industries near\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} for 2022",
     lambda: _bench("Pakistan 2022 CRT", "Ammonia production", "benchmark_Mt_co2e"), 0.0),
    ("limitations chemical-industries filing", "national", "12_limitations.tex",
     r"chemical industries near \\SI\{([\d.]+)\}\{\\mega\\tonne\}; industrial",
     lambda: _bench("Pakistan 2022 CRT", "Ammonia production", "benchmark_Mt_co2e"), 0.0),

    # The corrected parallel-table magnitudes, derived from the engine.
    ("factor trap railway category", "national", "05_factor_tables.tex",
     r"category by \\SI\{([\d.]+)\}\{\\percent\}\.", lambda: _swap_pct("railways"), 0.2),
    ("factor trap power sector", "national", "05_factor_tables.tex",
     r"move the sector by \\SI\{([\d.]+)\}\{\} and", lambda: _swap_pct("power"), 0.02),
    ("factor trap residential sector", "national", "05_factor_tables.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\percent\} respectively",
     lambda: _swap_pct("residential"), 0.02),

    # ---- national: the uncertainty section's prose, all of it ----
    # Six stale values were found here by the coverage test, none of them by the review:
    # Approach 1 at 10.8 against 10.7, Approach 2 at 10.75 in two places against 10.94, and
    # the fugitives Approach-2 band and median. The section that argues the paper's central
    # correlation finding was the least anchored in the manuscript.
    # The asymmetric national surface (rc12): the -/+ arms about the median.
    ("national up arm in abstract", "national", "00_abstract.tex",
     r"/\+\\SI\{([\d.]+)\}\{\\percent\}\$ about the\s*median",
     lambda: _mc("within_sector", "TOTAL", "rel_up_pct_95"), 0.05),
    ("national down arm in abstract", "national", "00_abstract.tex",
     r"\$-\\SI\{([\d.]+)\}\{\\percent\}/",
     lambda: _mc("within_sector", "TOTAL", "rel_down_pct_95"), 0.05),
    ("national up arm in uncertainty", "national", "07_uncertainty.tex",
     r"/\+\\SI\{([\d.]+)\}\{\\percent\}\$ about the median",
     lambda: _mc("within_sector", "TOTAL", "rel_up_pct_95"), 0.05),
    # rc40 G3b: the interval is RESTATED three times in this section - once beside the
    # published column names, once in the closing paragraph beside the symmetric summary,
    # and once as a bare +-13 - and only the first statement of each arm was registered.
    # The restatements had the right numbers by coincidence until the herd draws widened
    # the interval, when repair moved the registered twins and left these behind. Each
    # restatement is its own claim now, anchored on the words around it.
    ("national down arm beside the column names", "national", "07_uncertainty.tex",
     r"\$-\\SI\{([\d.]+)\}\{\\percent\}/\+\\SI\{[\d.]+\}\{\\percent\}\$ about the median\s*\(\\texttt\{rel",
     lambda: _mc("within_sector", "TOTAL", "rel_down_pct_95"), 0.05),
    ("national down arm in the closing paragraph", "national", "07_uncertainty.tex",
     r"\$-\\SI\{([\d.]+)\}\{\\percent\}/\+\\SI\{[\d.]+\}\{\\percent\}\$ about the median \(symmetric summary",
     lambda: _mc("within_sector", "TOTAL", "rel_down_pct_95"), 0.05),
    ("national up arm in the closing paragraph", "national", "07_uncertainty.tex",
     r"/\+\\SI\{([\d.]+)\}\{\\percent\}\$ about the median \(symmetric summary",
     lambda: _mc("within_sector", "TOTAL", "rel_up_pct_95"), 0.05),
    ("national down arm about reference, closing paragraph", "national", "07_uncertainty.tex",
     r"\$-\\SI\{([\d.]+)\}\{\\percent\}/\+\\SI\{[\d.]+\}\{\\percent\}\$ about the\s*deterministic reference\) under either",
     lambda: (float(_sector_row("TOTAL")["co2e_Mt_AR5"])
              - _mc("within_sector", "TOTAL", "P2.5_Mt"))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    ("national up arm about reference, closing paragraph", "national", "07_uncertainty.tex",
     r"/\+\\SI\{([\d.]+)\}\{\\percent\}\$ about the\s*deterministic reference\) under either",
     lambda: (_mc("within_sector", "TOTAL", "P97.5_Mt")
              - float(_sector_row("TOTAL")["co2e_Mt_AR5"]))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    # rc59 campaign cycle 3: tab:correlation's two percentage rows were WRONG in both
    # columns - 10.3/15.8 against the product's 10.52/16.15 about the median, and 9.3/17.1
    # against 9.65/17.28 about the deterministic reference - while the prose three lines
    # above printed the right det-ref pair and line 57 printed the correlated arms
    # correctly at two decimals. Nothing caught it: a cell reading "10.3/15.8" is not a
    # purely numeric tabular cell, so the quantity sweep never saw it. Eight claims now,
    # one per printed number, so each column is checked against its own scenario.
    ("tab correlation median down, independent", "national", "07_uncertainty.tex",
     r"about median & national & ([\d.]+)/",
     lambda: _mc("within_sector", "TOTAL", "rel_down_pct_95"), 0.05),
    ("tab correlation median up, independent", "national", "07_uncertainty.tex",
     r"about median & national & [\d.]+/([\d.]+)",
     lambda: _mc("within_sector", "TOTAL", "rel_up_pct_95"), 0.05),
    ("tab correlation median down, correlated", "national", "07_uncertainty.tex",
     r"about median & national & [\d.]+/[\d.]+ & ([\d.]+)/",
     lambda: _mc("cross_sector", "TOTAL", "rel_down_pct_95"), 0.05),
    ("tab correlation median up, correlated", "national", "07_uncertainty.tex",
     r"about median & national & [\d.]+/[\d.]+ & [\d.]+/([\d.]+)",
     lambda: _mc("cross_sector", "TOTAL", "rel_up_pct_95"), 0.05),
    ("tab correlation ref down, independent", "national", "07_uncertainty.tex",
     r"about det\.\\ ref\. & national & ([\d.]+)/",
     lambda: (float(_sector_row("TOTAL")["co2e_Mt_AR5"])
              - _mc("within_sector", "TOTAL", "P2.5_Mt"))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    ("tab correlation ref up, independent", "national", "07_uncertainty.tex",
     r"about det\.\\ ref\. & national & [\d.]+/([\d.]+)",
     lambda: (_mc("within_sector", "TOTAL", "P97.5_Mt")
              - float(_sector_row("TOTAL")["co2e_Mt_AR5"]))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    ("tab correlation ref down, correlated", "national", "07_uncertainty.tex",
     r"about det\.\\ ref\. & national & [\d.]+/[\d.]+ & ([\d.]+)/",
     lambda: (float(_sector_row("TOTAL")["co2e_Mt_AR5"])
              - _mc("cross_sector", "TOTAL", "P2.5_Mt"))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    ("tab correlation ref up, correlated", "national", "07_uncertainty.tex",
     r"about det\.\\ ref\. & national & [\d.]+/[\d.]+ & [\d.]+/([\d.]+)",
     lambda: (_mc("cross_sector", "TOTAL", "P97.5_Mt")
              - float(_sector_row("TOTAL")["co2e_Mt_AR5"]))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    # rc59 campaign cycle 5 (Q06): the two figures that carry the argument against reading
    # the 1A2 residual as a completeness floor. Both resolve from the nine-year divergence
    # product, so if the series moves the sentence cannot quietly keep its old numbers.
    ("limitations 1A2 max positive divergence", "national", "12_limitations.tex",
     r"by as much as \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: max(float(r["divergence_1a2_mt"])
                 for r in _rows_banner("pakemis_industry_edgar_divergence.csv")), 0.005),
    ("limitations 1A2 fall below FY2021-22", "national", "12_limitations.tex",
     r"falls\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} below its FY2021--22 level",
     lambda: (_divergence_1a2("FY2021-22") - _divergence_1a2("FY2023-24")), 0.005),
    ("limitations registered sources, restated", "national", "12_limitations.tex",
     r"of those \\num\{(\d+)\} registered sources",
     lambda: _product_fact("source_register_entries"), 0.0),
    ("national symmetric band a reader is given", "national", "07_uncertainty.tex",
     r"reader given only \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ has no way",
     lambda: _mc("within_sector", "TOTAL"), 0.05),
    # rc40 G3b: the twelve manure and soils N2O rows now derived from the graph, and the
    # widths they declared. Printed as integer ranges; each endpoint is its own claim.
    # The ninth review's basis fix: the same percentile band read against the
    # DETERMINISTIC reference, computed here from the published percentiles and
    # the published deterministic total so neither basis can drift alone.
    # The IPPU geocoding split (rc15): the provisional province-proxy statement
    # quotes 8-of-34 from the coverage product itself.
    ("ippu geocoded count", "ippu", "06_results.tex",
     r"\\num\{(\d+)\} of the \\num\{34\} census works carry resolved",
     lambda: float(_first_where("ippu_facility_coverage.csv", "facilities_geocoded",
                                province="TOTAL")), 0.0),
    # The anchor no longer embeds the OTHER number in the sentence. It read
    # `\num{8} of the \num{(\d+)} census works`, so correcting eight to nineteen silently
    # lost the anchor - a guard whose pattern hard-codes a value it does not check is a guard
    # that stops watching the moment that value is right.
    ("ippu census works count", "ippu", "06_results.tex",
     r"of the \\num\{(\d+)\} census works",
     lambda: float(_first_where("ippu_facility_coverage.csv", "facilities_declared",
                                province="TOTAL")), 0.0),
    # The supplement's product-contract table (rc15): the two quantities it prints
    # are the monthly layer's flat share and the grid resolution, both from the
    # products themselves.
    # These four moved into the GENERATED product table when the hand-maintained one was
    # retired. They are still checked, against the fragment that now carries them.
    ("contract flat share", "national-supplement", "sections/generated_products.tex",
     r"against ([\d.]+) per cent in the reference year",
     lambda: _temporal_share("T4"), 0.05),
    # Re-anchored when the catalog began distinguishing the MONTHLY cube from the annual one
    # in caps. The case is scoped-insensitive so the anchor tracks the sentence rather than its
    # emphasis; the word itself stays load-bearing, because "annual" here would be a different
    # claim about a different product.
    ("contract grid resolution", "national-supplement", "sections/generated_products.tex",
     r"The ([\d.]+) degree (?i:monthly) cube",
     lambda: float(_grid_resolution_deg()), 0.0),
    # The conclusion's road-transport figure (rc16): the sentence became an
    # equality when the scenarios converged, so it needs a claim rather than a
    # movement to stay covered.
    ("conclusion road transport band", "national", "13_conclusion.tex",
     r"at \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$\. We report both readings",
     lambda: _mc("within_sector", "Road transport"), 0.05),
    # The emissions RATIO the coverage paragraph contrasts against the scope share
    # (rc16): both are derivable, and printing them together is the whole point.
    # The nine-year series section (rc15): both views' endpoints and the coverage
    # share, read off the series and the annual product rather than typed.
    # The two FY2015-16 controls the results section quotes. They are CLAIM-anchored rather
    # than whitelisted because they come from a generated ledger: the whole point of the
    # sentence is that the evidence exists and is checkable, so the number it prints has to
    # resolve against the file that holds it.
    ("fy2015-16 road control", "national", "06_results.tex",
     r"Road\s*\\num\{(\d+)\} tonnes",
     lambda: _first_where("pakemis_unallocated_activity_controls.csv", "value",
                          claimant_sector="transport", fiscal_year="FY2015-16"), 0.0),
    ("fy2015-16 industry control", "national", "06_results.tex",
     r"Total Industry\s*\\num\{(\d+)\} tonnes",
     lambda: _first_where("pakemis_unallocated_activity_controls.csv", "value",
                          claimant_sector="industry", fiscal_year="FY2015-16"), 0.0),
    ("series covered total first year", "national", "06_results.tex",
     r"total runs from \\SI\{([\d.]+)\}\{\\mega\\tonne\} at FY2015--16",
     lambda: _first_where("pakemis_national_series.csv", "co2e_Mt_AR5",
                          sector="COVERED_TOTAL", period_label="FY2015-16"), 0.005),
    # "series coverage share first year" and "series emissions ratio" are RETIRED
    # (rc20): coverage_share_pct_of_reference is 100.0 in every row since the
    # FY2015-16 recovery, the scope-share formula left the prose with its premise,
    # and the constant is asserted by tests/test_unallocated_controls instead.
    # This claim used to read the covered total's maximum as the REFERENCE year's, because
    # for as long as cement existed in one year only the two were the same number. They are
    # not any more: FY2021-22 carries a larger cement and tops the series at 448.91 while
    # the reference year is 448.00. The claim now resolves the maximum as a maximum.
    ("series covered total maximum", "national", "06_results.tex",
     r"to a maximum of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} at",
     lambda: max(float(r["co2e_Mt_AR5"])
                 for r in _rows("pakemis_national_series.csv")
                 if r["row_kind"] == "covered_total"), 0.005),
    # The conservation split (rc15, the tenth review): the exact/declared/derived
    # counts in the invariance statement read off the provincial check itself.
    ("conservation exact count", "national", "06_results.tex",
     r"\\num\{(\d+)\} stream-province cells exact by construction",
     lambda: float(sum(1 for r in _csv_rows("pakemis_grid_provincial_check.csv")
                       if r["status"] == "exact_by_construction")), 0.0),
    # The fourth status, added with the two-term closure identity: a stream the cube
    # declines to place still declares a provincial share, and that share is checked here
    # rather than dropped along with the placement.
    ("conservation unallocated count", "national", "06_results.tex",
     r"\\num\{(\d+)\}\s*unallocated below ADM1",
     lambda: float(sum(1 for r in _csv_rows("pakemis_grid_provincial_check.csv")
                       if r["status"] == "unallocated_below_adm1")), 0.0),
    ("conservation check row count", "national", "06_results.tex",
     r"all \\num\{(\d+)\} provincial marginals are unchanged",
     lambda: float(len(_csv_rows("pakemis_grid_provincial_check.csv"))), 0.0),
    ("conservation declared count", "national", "06_results.tex",
     r"\\num\{(\d+)\}\s*carrying a declared divergence",
     lambda: float(sum(1 for r in _csv_rows("pakemis_grid_provincial_check.csv")
                       if r["status"] == "declared_divergence")), 0.0),
    ("conservation derived count", "national", "06_results.tex",
     r"and \\num\{(\d+)\} derived from\s*the grid itself",
     lambda: float(sum(1 for r in _csv_rows("pakemis_grid_provincial_check.csv")
                       if r["status"] == "derived_from_grid")), 0.0),
    # The district-map audit (rc14): both caption counts read off the audit
    # product, so a returning name-match failure breaks the prose.
    ("residential map painted count", "residential", "06_results.tex",
     r"\\num\{(\d+)\} of the\s*\\num\{126\} boundary polygons are painted",
     lambda: float(sum(1 for r in
                       _csv_rows("residential_district_map_audit_2024.csv")
                       if r["status"] == "painted")), 0.0),
    ("residential map residual count", "residential", "06_results.tex",
     r"the \\num\{(\d+)\} grey polygons are the GB/AJK/ICT units",
     lambda: float(sum(1 for r in
                       _csv_rows("residential_district_map_audit_2024.csv")
                       if r["status"] == "residual_declared")), 0.0),
    # The gas-closure magnitudes in the national closures section (rc14).
    ("national gas leak kt", "national", "04_closures.tex",
     r"about \\SI\{(\d+)\}\{\\kilo\\tonne\} of methane is",
     lambda: round(float(next(
         r["annual_million_m3"] for r in _csv_rows("national_gas_closure.csv")
         if r["stream"] == "CLOSURE: declared double-claim")) * 6.1 / 1000.0),
     0.5),
    # rc67: rewritten with its sentence. The ledger carries fertiliser gas as feedstock
    # (outside the base) and process fuel (inside), so the share printed is feedstock over
    # the base AS IT STOOD through rc66 - today's base plus the feedstock withheld from it.
    ("national gas fertilizer share", "national", "04_closures.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} of the leak base as it\s*stood",
     lambda: (lambda feed, base: 100.0 * feed / (feed + base))(
         float(_cell("national_gas_closure.csv", "stream", "Fertilizer: feedstock",
                     "annual_million_m3")),
         float(_cell("national_gas_closure.csv", "stream",
                     "CLOSURE: declared double-claim", "annual_million_m3"))), 0.0),
    ("national gas feedstock share of the fertiliser class", "national", "04_closures.tex",
     r"Feedstock---\\SI\{([\d.]+)\}\{\\percent\} of the class",
     lambda: _annex28_share("2023-24", "Feed"), 0.05),
    ("national gas feedstock membership delta", "national", "04_closures.tex",
     r"which adds \\SI\{([\d.]+)\}\{\\mega\\tonne\}; the",
     lambda: _configuration("fugitives_including_feedstock", "national_delta_Mt"), 0.0),
    ("national gas fertiliser carbon potential low", "national", "04_closures.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} \\COtwo\{\} at the utility",
     lambda: _first_where("pakemis_gas_flow_crosswalk.csv",
                          "gas_carbon_potential_Mt_CO2_low", period_id="FY2023-24",
                          stream="MEMO: fertiliser class (feed + process fuel)"), 0.0),
    ("national gas fertiliser carbon potential high", "national", "04_closures.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\} at the utility",
     lambda: _first_where("pakemis_gas_flow_crosswalk.csv",
                          "gas_carbon_potential_Mt_CO2_high", period_id="FY2023-24",
                          stream="MEMO: fertiliser class (feed + process fuel)"), 0.0),
    ("national gas fertiliser carbon booked", "national", "04_closures.tex",
     r"stands against \\SI\{([\d.]+)\}\{\\mega\\tonne\} gross booked by 2\.B\.1",
     lambda: _first_where("pakemis_gas_flow_crosswalk.csv", "carbon_booked_Mt_CO2",
                          period_id="FY2023-24",
                          stream="MEMO: fertiliser class (feed + process fuel)"), 0.0),
    # And the same three in the fugitives limitations paragraph.
    ("fugitives double-claim share", "fugitives", "08_limitations.tex",
     r"double-claim at about \\SI\{([\d.]+)\}\{\\percent\}",
     # whole-gas share: the CH4 leak factor over the declared CH4 mass fraction,
     # over gas mass - the rc17 correction (0.897% divided CH4 by whole gas)
     lambda: 100.0 * (6.1 / 0.90) / (0.68 * 1000.0), 0.05),
    # rc67: the ledger carries fertiliser gas as two rows and the feedstock row is out
    # of the leak base, so "31 per cent of the leak base leaks" is no longer a sentence
    # the paper can print. What it prints is the CLASS's share of the six classes the
    # base is drawn from: both fertiliser rows over the registered six-class activity.
    ("fugitives fertilizer leak share", "fugitives", "08_limitations.tex",
     r"\\SI\{(\d+)\}\{\\percent\} of the six classes the leak base is drawn from",
     lambda: 100.0 * sum(
         float(r["annual_million_m3"]) for r in _csv_rows("national_gas_closure.csv")
         if r["stream"] in ("Fertilizer: feedstock", "Fertilizer: process fuel"))
         / _first_where("fugitives_post_meter_end_use_2024.csv",
                        "registered_activity_million_m3",
                        include_in_ipcc_post_meter="yes"), 0.5),
    ("fugitives feedstock share of the fertilizer class, limitations", "fugitives",
     "08_limitations.tex",
     r"The chemical feedstock, \\SI\{([\d.]+)\}\{\\percent\} of the class",
     lambda: _annex28_share("2023-24", "Feed"), 0.0),
    ("fugitives including-feedstock scenario, limitations", "fugitives",
     "08_limitations.tex",
     r"post\\_meter\\_including\\_feedstock\}\s*\(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv", "mt_co2e_ar5",
                          scenario="post_meter_including_feedstock"), 0.0),
    ("fugitives official field count", "fugitives", "08_limitations.tex",
     r"of the \\num\{(\d+)\} official fields",
     lambda: float(len({r["canonical_field"] for r in _data_rows(
         os.path.join("activity", "fugitives", "field_gas_supply_2023_24.csv"))})),
     0.0),
    # The MARS censoring wording (rc14): the 71.1% twin in 06_results was
    # hand-maintained (only the abstract was claim-covered), and the
    # eight-matched-fields count had no claim at all.
    ("fugitives matched-supply share in results", "fugitives", "06_results.tex",
     r"fields accounting for \\SI\{([\d.]+)\}\{\\percent\} of reported supply",
     lambda: _first_where("fugitives_observation_field_statistics_2024.csv",
                          "supply_coverage_by_any_named_observation_pct",
                          comparison="VIIRS named-field flare volume"), 0.05),
    ("fugitives matched MARS field count", "fugitives", "08_limitations.tex",
     r"only \\num\{(\d+)\} of the \\num\{73\} official fields",
     lambda: float(next(
         r["n_fields_with_nonzero_observation"] for r in
         _csv_rows("fugitives_observation_field_statistics_2024.csv")
         if "MARS" in r["comparison"])), 0.0),
    # The gas double-claim paragraphs (rc14): both papers quote the variant's
    # deduction and the ledger's leak base from the products themselves.
    ("national gas leak base", "national", "04_closures.tex",
     r"\\num\{(\d+)\} million m\$\^3\$ leak base",
     lambda: round(float(next(
         r["annual_million_m3"] for r in _csv_rows("national_gas_closure.csv")
         if r["stream"] == "CLOSURE: declared double-claim"))), 0.5),
    ("fugitives gas restoration", "fugitives", "08_limitations.tex",
     r"gross\\_delivered\\_gas\\_accounting\}\s*\(\\SI\{\+([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("national_gas_closure_variant.csv", "adjustment_Mt_co2e",
                          configuration="gross_delivered_gas_accounting"),
     0.0005),
    # The waste series product facts (rc17): the per-year FOD claim's numbers,
    # asserted from the shipped annual product - the hidden-108-month lesson.
    # The rc17 solid-fuel screenings: the completeness section's numbers pinned
    # to the industry ledger and totals rows they come from.
    # rc46 Wave 2: the screening CENTRAL is no longer printed (the measured stream
    # superseded the model) and the "kiln screening magnitude" 7.35 print left with it -
    # both claims retired WITH their sentences. What is printed now: the superseded
    # bracket as a comparator, the measured streams, and the activation's activity.
    ("cement kiln fuel superseded bracket low", "national", "09_completeness.tex",
     r"transfer\s*\n?\s*model's \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} bracket",
     lambda: __import__("importlib").import_module(
         "pkinv.sectors.industry.solid_screenings").cement_screening()[0]["low"],
     0.005),
    ("cement kiln fuel superseded bracket high", "national", "09_completeness.tex",
     r"transfer\s*\n?\s*model's \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} bracket",
     lambda: __import__("importlib").import_module(
         "pkinv.sectors.industry.solid_screenings").cement_screening()[0]["high"],
     0.005),
    ("bagasse ceiling", "national", "09_completeness.tex",
     r"bagasse reaches only\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\} of countable "
     r"CH\$_4\$ and N\$_2\$O",
     lambda: _first_where("industry_fuel_ledger_2024.csv", "Mt_co2e",
                          claimant="Sugar-mill process bagasse"), 0.005),
    ("completeness brick coal stream", "national", "09_completeness.tex",
     r"gate---\\SI\{([\d.]+)\}\{\\mega\\tonne\} of brick-kiln",
     lambda: _first_where("industry_fuel_ledger_2024.csv", "Mt_co2e",
                          claimant="Brick-kiln coal"), 0.005),
    ("completeness cement coal stream", "national", "09_completeness.tex",
     r"and\s*\n?\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of cement-sector coal",
     lambda: _first_where("industry_fuel_ledger_2024.csv", "Mt_co2e",
                          claimant="Cement-sector coal"), 0.005),
    ("completeness cement coal measured mass", "national", "09_completeness.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} on \\num\{4391\}~kt",
     lambda: _first_where("industry_fuel_ledger_2024.csv", "Mt_co2e",
                          claimant="Cement-sector coal"), 0.005),
    ("completeness cement coal activity kt", "national", "09_completeness.tex",
     r"on \\num\{(\d+)\}~kt",
     lambda: float(next(r["coal_kt"] for r in
                        _data_rows_nocomment("activity/industry/coal_by_consumer.csv")
                        if r["fiscal_year"] == "2023-24" and r["consumer"] == "cement"
                        and r["revision_status"] == "final")), 0.5),
    ("limitations brick coal stream", "national", "12_limitations.tex",
     r"estimates\s*\n?\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of brick-kiln",
     lambda: _first_where("industry_fuel_ledger_2024.csv", "Mt_co2e",
                          claimant="Brick-kiln coal"), 0.005),
    ("limitations cement coal stream", "national", "12_limitations.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} of cement-sector coal",
     lambda: _first_where("industry_fuel_ledger_2024.csv", "Mt_co2e",
                          claimant="Cement-sector coal"), 0.005),
    # The Table 3 hypothesis register's quoted evidence (rc17): the numbers the
    # power validation passage prints beside the enumeration.
    ("power imported-band CV", "power", "05_validation.tex",
     r"imported-only band whose mass-weighted value\s+is \\SI\{([\d.]+)\}",
     lambda: _first_where("power_implied_coal_cv_fy2023_24.csv",
                          "implied_cv_TJ_per_Gg", fiscal_year="2023",
                          plant="imported only"), 0.005),
    ("power gross TOE priced in hypotheses", "power", "05_validation.tex",
     r"a gross-basis TOE column, priced at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("power_uncertainty_scenarios_fy2023_24.csv",
                          "deterministic_Mt",
                          structural_scenario="toe_gross_basis"), 0.0005),
    ("power circularity comparison count", "power", "05_validation.tex",
     r"circularity screen covers\s+\\num\{(\d+)\} plant-fuel comparisons",
     lambda: float(len(_csv_rows("power_hr_circularity_fy2023_24.csv"))), 0.0),
    # The rc17 envelope members: the geometric-mean central reading and the
    # post-meter feedstock scope, each pinned to the sector's own products.
    ("fugitives central deterministic", "fugitives", "06_results.tex",
     r"midpoint mechanism carried into the segment engine---prices "
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "deterministic_mt_co2e_ar5", configuration="central"),
     0.0005),
    ("fugitives central interval low", "fugitives", "06_results.tex",
     r"with its own conditional interval of \\SIrange\{([\d.]+)\}\{[\d.]+\}",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p025_mt_co2e_ar5", configuration="central"), 0.0005),
    ("fugitives central interval high", "fugitives", "06_results.tex",
     r"with its own conditional interval of \\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p975_mt_co2e_ar5", configuration="central"), 0.0005),
    ("fugitives feedstock scenario", "fugitives", "06_results.tex",
     r"prices\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\}\s+\(the post-meter feedstock scope",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv",
                          "mt_co2e_ar5",
                          scenario="post_meter_including_feedstock"), 0.0005),
    ("fugitives feedstock delta", "fugitives", "06_results.tex",
     r"post-meter feedstock scope axis, \\SI\{\+([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: (_first_where("fugitives_structural_scenarios_2024.csv",
                           "mt_co2e_ar5",
                           scenario="post_meter_including_feedstock")
              - _first_where("fugitives_structural_scenarios_2024.csv",
                             "mt_co2e_ar5", scenario="reference")), 0.0005),
    # rc67: the axis turned over. What post_meter_excluding_feedstock priced is the
    # reference now (process fuel kept in), so the sentence above states the feedstock
    # put back (the membership through rc66, +) and this one the whole class out (-).
    ("fugitives whole-class scenario", "fugitives", "06_results.tex",
     r"whole fertilizer class out prices \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv", "mt_co2e_ar5",
                          scenario="post_meter_excluding_fertilizer"), 0.0005),
    ("fugitives whole-class delta", "fugitives", "06_results.tex",
     r"whole fertilizer class out prices \\SI\{[\d.]+\}\{\\mega\\tonne\}\s*"
     r"\(\\SI\{(-[\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: (_first_where("fugitives_structural_scenarios_2024.csv", "mt_co2e_ar5",
                           scenario="post_meter_excluding_fertilizer")
              - _first_where("fugitives_structural_scenarios_2024.csv",
                             "mt_co2e_ar5", scenario="reference")), 0.0005),
    # The envelope's top and the reference's place in it, wherever the paper states
    # them. Through rc66 the two were one number and tab:segments' total covered both.
    ("fugitives abstract reference", "fugitives", "00_abstract.tex",
     r"configuration\} of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}---not an empirically",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv",
                          "mt_co2e_ar5", scenario="reference"), 0.0),
    ("fugitives abstract envelope floor", "fugitives", "00_abstract.tex",
     r"span \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}; the reference sits high",
     lambda: _min_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5"), 0.0),
    ("fugitives abstract envelope top", "fugitives", "00_abstract.tex",
     r"span \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}; the reference sits high",
     lambda: _max_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5"), 0.0),
    ("fugitives results reference", "fugitives", "06_results.tex",
     r"the full public-data ledger gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}---high",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv",
                          "mt_co2e_ar5", scenario="reference"), 0.0),
    ("fugitives results envelope top", "fugitives", "06_results.tex",
     r"high in the sector's \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _max_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5"), 0.0),
    ("fugitives complete structural maximum", "fugitives", "06_results.tex",
     r"retaining all public-data segments span\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: _max_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5",
                        coverage_complete_under_configuration="True"), 0.0),
    ("fugitives widest structural maximum", "fugitives", "06_results.tex",
     r"excluded expands the envelope to\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: _max_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5"), 0.0),
    ("fugitives conclusion reference", "fugitives", "09_conclusion.tex",
     r"configuration to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}---high in its own",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv",
                          "mt_co2e_ar5", scenario="reference"), 0.0),
    ("fugitives conclusion envelope floor", "fugitives", "09_conclusion.tex",
     r"Joint structural choices span \\SIrange\{([\d.]+)\}\{[\d.]+\}",
     lambda: _min_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5"), 0.0),
    ("fugitives conclusion envelope top", "fugitives", "09_conclusion.tex",
     r"Joint structural choices span \\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: _max_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5"), 0.0),
    # Sentences that restated a tab:segments cell or a product value and were covered
    # only as repeats of it; each now reads its own product in place.
    ("fugitives reference CH4", "fugitives", "06_results.tex",
     r"reference inventory contains \\SI\{([\d.]+)\}\{\\giga\\gram\} CH",
     lambda: _sum_where("fugitives_segment_native_gases_2024.csv", "ch4_Gg"), 0.0),
    ("fugitives reference CO2", "fugitives", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\giga\\gram\} CO\$_2\$ and",
     lambda: _sum_where("fugitives_segment_native_gases_2024.csv", "co2_Gg"), 0.0),
    ("fugitives post-meter industrial segment", "fugitives", "06_results.tex",
     r"post-meter industrial and power use \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _first_where("fugitives_segment_native_gases_2024.csv", "co2e_Mt_AR5",
                          segment="Post-meter industrial and power"), 0.0),
    ("fugitives post-meter exclusion effect", "fugitives", "06_results.tex",
     r"reduces the total by \\SI\{[\d.]+\}\{\} or\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}, "
     r"respectively",
     lambda: (_first_where("fugitives_structural_scenarios_2024.csv",
                           "mt_co2e_ar5", scenario="reference")
              - _first_where("fugitives_structural_scenarios_2024.csv",
                             "mt_co2e_ar5", scenario="no_post_meter_industrial")), 0.0),
    ("fugitives sector run median, draw-count remark", "fugitives", "06_results.tex",
     r"residual difference against\s*\\num\{([\d.]+)\} is draw count",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p50_mt_co2e_ar5", configuration="reference"), 0.0),
    ("fugitives timeseries reference year", "fugitives", "06_results.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} in FY2023--24 \(each",
     lambda: _first_where("fugitives_infrastructure_timeseries_2016_2024.csv",
                          "co2e_Mt_AR5", fiscal_year="2024"), 0.0),
    ("fugitives CRT waterfall close", "fugitives", "06_results.tex",
     r"then closes at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_unfccc_crt_waterfall_2022.csv",
                          "cumulative_common_mt_co2e", step="Numerical closure"), 0.0),
    ("fugitives polythene network share, data", "fugitives", "03_study_area_and_data.tex",
     r"This is only \\SI\{([\d.]+)\}\{\\percent\} of the reported national distribution",
     lambda: _first_where("fugitives_distribution_practice_evidence_2024.csv",
                          "coverage_pct", evidence_id="ssgcl_polythene_pipe"), 0.0),
    ("fugitives polythene network share, results", "fugitives", "06_results.tex",
     r"covers only\s*\\SI\{([\d.]+)\}\{\\percent\} of the national network",
     lambda: _first_where("fugitives_distribution_practice_evidence_2024.csv",
                          "coverage_pct", evidence_id="ssgcl_polythene_pipe"), 0.0),
    ("fugitives post-meter activity after feedstock", "fugitives",
     "03_study_area_and_data.tex",
     r"is withheld and \\num\{([\d.]+)\} after",
     lambda: _first_where("fugitives_uncertainty_inputs_2024.csv", "central_value",
                          input_id="activity:post_meter_nonresidential"), 0.0),
    ("fugitives feedstock share of the fertilizer class, data", "fugitives",
     "03_study_area_and_data.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} of the fertilizer class is\s*chemical feedstock",
     lambda: _annex28_share("2023-24", "Feed"), 0.0),
    ("fugitives feedstock volume", "fugitives", "03_study_area_and_data.tex",
     r"that feedstock, \\num\{([\d.]+)\} million m\$\^3\$",
     lambda: float(_cell("national_gas_closure.csv", "stream", "Fertilizer: feedstock",
                         "annual_million_m3")), 0.0),
    ("fugitives screen threshold", "fugitives", "../supplement.tex",
     r"reference configuration\s*\(\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\}\)",
     lambda: _first_where("fugitives_completeness_2024.csv", "screen_threshold_mt_co2e",
                          ipcc_code="1.B.1"), 0.0),
    ("national central in sector caption", "national", "06_results.tex",
     r"geometric-mean central reading of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "deterministic_mt_co2e_ar5", configuration="central"),
     0.005),
    # The fugitives envelope in the national limitations (rc14): both ends and
    # the reference pinned to the sector's own conditional-intervals product.
    ("national fugitives envelope floor", "national", "12_limitations.tex",
     r"structural envelope of \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "deterministic_mt_co2e_ar5",
                          configuration="minimum_coverage_combined"), 0.0005),
    # rc67: the reference is no longer the envelope's top. THIS claim keeps its label and
    # its getter (the reference), because data/claim_matrix.csv (lim_fugitives_top) resolves
    # the reference through it by name; it is re-anchored on the sentence's reference
    # figure. The envelope's upper end is the claim after it, read from the feedstock-inside
    # scenario that now defines it.
    ("national fugitives envelope top", "national", "12_limitations.tex",
     r"and the reference \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\) sits one membership step",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "deterministic_mt_co2e_ar5",
                          configuration="reference"), 0.0005),
    ("national fugitives envelope upper end", "national", "12_limitations.tex",
     r"structural envelope of \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv", "mt_co2e_ar5",
                          scenario="post_meter_including_feedstock"), 0.0005),
    ("national fugitives lower member", "national", "12_limitations.tex",
     r"the lower-practice member at\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "deterministic_mt_co2e_ar5",
                          configuration="lower_practices"), 0.0005),
    ("national down arm about reference", "national", "07_uncertainty.tex",
     r"reference\} \\SI\{[\d.]+\}\{\\mega\\tonne\} is \$-\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: (float(_sector_row("TOTAL")["co2e_Mt_AR5"])
              - _mc("within_sector", "TOTAL", "P2.5_Mt"))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    ("national up arm about reference", "national", "07_uncertainty.tex",
     r"is \$-\\SI\{[\d.]+\}\{\\percent\}/\+\\SI\{([\d.]+)\}\{\\percent\}\$,\s*because the deterministic",
     lambda: (_mc("within_sector", "TOTAL", "P97.5_Mt")
              - float(_sector_row("TOTAL")["co2e_Mt_AR5"]))
             / float(_sector_row("TOTAL")["co2e_Mt_AR5"]) * 100.0, 0.05),
    ("A1 national in uncertainty", "national", "07_uncertainty.tex",
     r"the gap is the finding: \\SI\{([\d.]+)\}\{\\percent\} from\s*Approach~1",
     lambda: _sector("TOTAL", "uncert_pct_95"), 0.0),
    ("A2 national in uncertainty", "national", "07_uncertainty.tex",
     r"Approach~1 against \\SI\{([\d.]+)\}\{\\percent\} from",
     lambda: _mc("within_sector", "TOTAL"), 0.0),
    ("fugitives A1 in uncertainty", "national", "07_uncertainty.tex",
     r"ledger gives\s*\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ under Approach~1",
     lambda: _sector("fugitives", "uncert_pct_95"), 0.0),
    ("fugitives A2 in uncertainty", "national", "07_uncertainty.tex",
     r"and \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ under the injected",
     lambda: _mc("within_sector", "fugitives"), 0.0),
    ("fugitives MC median", "national", "07_uncertainty.tex",
     r"Monte-Carlo median is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _mc("within_sector", "fugitives", "P50_Mt"), 0.0),
    ("fugitives MC mean", "national", "07_uncertainty.tex",
     r"its mean\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}---the sector engine",
     lambda: _mc("within_sector", "fugitives", "mean_Mt"), 0.0),
    ("national band independent", "national", "07_uncertainty.tex",
     r"below the reporting precision:\s*\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ either way",
     lambda: _mc("within_sector", "TOTAL"), 0.0),
    # The correlated twin retired at rc16: one figure now, both scenarios.
    # rc41 Wave 4: the transport module reads the same printed half-width under both
    # correlation structures, so the sentence stopped being a movement; the one printed
    # number is anchored to BOTH engine readings (its twin sits with the movements).
    ("transport module correlated low", "national", "07_uncertainty.tex",
     r"transport module reads \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ under both",
     lambda: _mc("within_sector", "transport"), 0.0),
    ("road category correlated low", "national", "07_uncertainty.tex",
     r"road-transport category from \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("within_sector", "Road transport"), 0.0),
    ("road category correlated high", "national", "07_uncertainty.tex",
     r"road-transport category from \$\\pm\\SI\{[\d.]+\}\{\\percent\}\$ to\s*\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("cross_sector", "Road transport"), 0.0),
    # The sentence now brackets the two Monte-Carlo correlation cases, not Approach 1
    # against a correlated bound: with the factor grouping corrected they are 0.15 points
    # apart rather than a point.
    ("national interval low in uncertainty", "national", "07_uncertainty.tex",
     r"symmetric summary\s*\\SI\{([\d.]+)\}\{\\percent\}; \$-\\SI",
     lambda: _mc("within_sector", "TOTAL"), 0.05),
    ("national band against waste", "national", "07_uncertainty.tex",
     r"sectors'---\\SI\{([\d.]+)\}\{\\percent\} against",
     lambda: _sector("TOTAL", "uncert_pct_95"), 0.0),
    ("waste A1 in uncertainty", "national", "07_uncertainty.tex",
     r"waste's \\SI\{([\d.]+)\}\{\\percent\}", lambda: _sector("waste", "uncert_pct_95"), 0.0),
    ("fugitives A1 against waste", "national", "07_uncertainty.tex",
     r"and fugitives' \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _sector("fugitives", "uncert_pct_95"), 0.0),
    ("fugitives level in uncertainty", "national", "07_uncertainty.tex",
     r"Fugitives now contribute\s*\\SI\{([\d.]+)\}\{\\percent\} of emissions",
     lambda: _keycat("Fugitive emissions from oil and gas", "level_pct"), 0.0),
    ("fugitives variance in uncertainty", "national", "07_uncertainty.tex",
     r"of emissions and \\SI\{([\d.]+)\}\{\\percent\} of Approach-1 variance\. Its discrete",
     lambda: _keycat("Fugitive emissions from oil and gas", "variance_share_pct_independent_approx"), 0.0),

    # ---- national: the key-category section's prose ----
    # The wastewater variance share was printed as 10.0 against an engine value of 10.62,
    # and survived because 10.0 happens to be the power sector's uncertainty elsewhere in
    # the document. A repeat-of-a-checked-value tier cannot catch that; only an in-place
    # claim can, which is why these are registered rather than left to tier 2.
    ("keycat road level", "national", "08_key_categories.tex",
     r"\\textbf\{Road transport\} contributes \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _keycat("Road transport", "level_pct"), 0.0),
    ("keycat road variance", "national", "08_key_categories.tex",
     r"of emissions but\s*\\SI\{([\d.]+)\}\{\\percent\} of variance",
     lambda: _keycat("Road transport", "variance_share_pct_independent_approx"), 0.0),
    ("keycat wastewater level", "national", "08_key_categories.tex",
     r"\\textbf\{Domestic wastewater\} contributes \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _keycat("Domestic wastewater", "level_pct"), 0.0),
    ("keycat wastewater variance", "national", "08_key_categories.tex",
     r"of emissions and\s*\\SI\{([\d.]+)\}\{\\percent\} of variance",
     lambda: _keycat("Domestic wastewater", "variance_share_pct_independent_approx"), 0.0),
    ("keycat fugitives level", "national", "08_key_categories.tex",
     r"segment account is\s*\\SI\{([\d.]+)\}\{\\percent\} of emissions",
     lambda: _keycat("Fugitive emissions from oil and gas", "level_pct"), 0.0),
    ("keycat fugitives variance", "national", "08_key_categories.tex",
     r"of emissions and \\SI\{([\d.]+)\}\{\\percent\} of Approach-1 variance\. This replaces",
     lambda: _keycat("Fugitive emissions from oil and gas", "variance_share_pct_independent_approx"), 0.0),
    ("keycat enteric level", "national", "08_key_categories.tex",
     r"rankings, at\s*\\SI\{([\d.]+)\}\{\\percent\} of emissions",
     lambda: _keycat("Enteric fermentation", "level_pct"), 0.0),
    ("keycat enteric variance", "national", "08_key_categories.tex",
     r"of emissions and \\SI\{([\d.]+)\}\{\\percent\} of variance\. The variance ranking",
     lambda: _keycat("Enteric fermentation", "variance_share_pct_independent_approx"), 0.0),

    # ---- national: the discussion's and completeness's repeats of the headline ----
    ("discussion fugitives level", "national", "11_discussion.tex",
     r"making fugitives\s*\\SI\{([\d.]+)\}\{\\percent\} of national emissions",
     lambda: _keycat("Fugitive emissions from oil and gas", "level_pct"), 0.0),
    ("discussion fugitives variance", "national", "11_discussion.tex",
     r"national emissions and \\SI\{([\d.]+)\}\{\\percent\} of variance",
     lambda: _keycat("Fugitive emissions from oil and gas", "variance_share_pct_independent_approx"), 0.0),
    ("discussion road level", "national", "11_discussion.tex",
     r"Road transport\s*is \\SI\{([\d.]+)\}\{\\percent\} and",
     lambda: _keycat("Road transport", "level_pct"), 0.0),
    ("discussion road variance", "national", "11_discussion.tex",
     r"is \\SI\{[\d.]+\}\{\\percent\} and \\SI\{([\d.]+)\}\{\\percent\}\. The binding",
     lambda: _keycat("Road transport", "variance_share_pct_independent_approx"), 0.0),
    ("waste district base contrast", "waste", "03_study_area_and_data.tex",
     r"uses \\num\{(\d+)\} four-province districts",
     lambda: len({r["district"] for r in _rows("district_totals_2024.csv")
                  if "residual" not in r["district"]}), 0.0),
    ("power discussion 1A2 remaining", "power", "07_discussion.tex",
     r"The remaining \\SI\{(\d+)\}\{\\mega\\tonne\} is specifically solid",
     lambda: round(_bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
                   - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e")), 0.0),
    ("power limitations 1A2 remaining", "power", "08_limitations.tex",
     r"roughly\s*\\SI\{(\d+)\}\{\\mega\\tonne\} of EDGAR's",
     lambda: round(_bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
                   - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e")), 0.0),
    ("power conclusion 1A2 remaining", "power", "09_conclusion.tex",
     r"roughly\s*\\SI\{(\d+)\}\{\\mega\\tonne\} still missing",
     lambda: round(_bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
                   - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e")), 0.0),
    ("waste unresolved shallow bound", "waste", "08_limitations.tex",
     r"shallow\s*disposal \(sector total \\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _cell("waste_uncertainty_scenarios_2024.csv", "structural_scenario",
                   "unresolved_shallow_dumps", "deterministic"), 0.0),
    ("waste unresolved deep bound", "waste", "08_limitations.tex",
     r"unmanaged deep disposal\s*\(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _cell("waste_uncertainty_scenarios_2024.csv", "structural_scenario",
                   "unresolved_deep_dumps", "deterministic"), 0.0),
    ("waste unresolved reference bound", "waste", "08_limitations.tex",
     r"reference reading \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _cell("waste_uncertainty_scenarios_2024.csv", "structural_scenario",
                   "unresolved_inert", "deterministic"), 0.0),
    ("aviation military memo Gg", "aviation", "06_results.tex",
     r"military and government jet fuel \(\\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: 1000 * _aviation_noncommercial_Mt("military_1a5b", "co2_per_t_fuel"), 0.0),
    ("aviation ga memo Gg", "aviation", "06_results.tex",
     r"100LL general aviation \(\\SI\{([\d.]+)\}\{\\giga\\gram\}\)",
     lambda: 1000 * _aviation_noncommercial_Mt("general_aviation", "co2_per_t_avgas"),
     0.0),
    ("aviation residual memo Gg", "aviation", "06_results.tex",
     r"unresolved government JP-1\s*\(\\SI\{([\d.]+)\}\{\\giga\\gram\}\)",
     lambda: 1000 * _aviation_noncommercial_Mt("residual", "co2_per_t_fuel"), 0.0),
    ("aviation noncommercial total", "aviation", "06_results.tex",
     r"together about\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (_aviation_noncommercial_Mt("military_1a5b", "co2_per_t_fuel")
              + _aviation_noncommercial_Mt("general_aviation", "co2_per_t_avgas")
              + _aviation_noncommercial_Mt("residual", "co2_per_t_fuel")), 0.0),
    ("aviation military scope configuration total", "aviation", "06_results.tex",
     r"military\\_government\\_in\\_scope\}\s*\(\\num\{([\d.]+)\}~Mt\)",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "military_government_in_scope", "national_total_Mt"), 0.0),
    ("aviation GA scope configuration total", "aviation", "06_results.tex",
     r"general\\_aviation\\_in\\_scope\}\s*\(\\num\{([\d.]+)\}~Mt\)",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "general_aviation_in_scope", "national_total_Mt"), 0.0),
    ("aviation JP-1 scope configuration total", "aviation", "06_results.tex",
     r"unresolved\\_jp1\\_in\\_scope\}\s*\(\\num\{([\d.]+)\}~Mt\)",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "unresolved_jp1_in_scope", "national_total_Mt"), 0.0),
    ("aviation scope reference total", "aviation", "06_results.tex",
     r"against the\s*\\num\{([\d.]+)\} reference",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "inventory_reference", "national_total_Mt"), 0.0),
    ("railways non-traction recode quantity", "railways", "08_limitations.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} at its own non-traction category",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("railways_fuel_claimants_2024.csv")
                 if r["status"] == "RESOLVED-RECODED"), 0.0),
    ("railways recode national total", "railways", "08_limitations.tex",
     r"conserves the national\s*total at \\num\{([\d.]+)\} exactly",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "rail_ie_summary", "national_total_Mt"), 0.0),
    ("national adm2 bracket captive", "national", "06_results.tex",
     r"moves up to \\num\{([\d.]+)\} percentage points of a\s*district share",
     lambda: max(abs(float(r["spread_pp"]))
                 for r in _rows("pakemis_spatial_brackets_adm2.csv")
                 if r["alternative_id"] == "power_captive_points_builtup_adm2"
                 and r["province"] == "MAX_ABS"), 0.0),
    ("national spatial bracket registration", "national", "06_results.tex",
     r"disagrees with the fuel-sales allocation by up to\s*\\num\{([\d.]+)\} percentage",
     lambda: max(abs(float(r["spread_pp"]))
                 for r in _rows("pakemis_spatial_brackets.csv")
                 if r["alternative_id"] == "transport_diesel_registration"
                 and r["province"] != "MAX_ABS"), 0.0),
    ("national spatial bracket shape year", "national", "06_results.tex",
     r"by at most \\num\{([\d.]+)\}\npoints",
     lambda: max(abs(float(r["spread_pp"]))
                 for r in _rows("pakemis_spatial_brackets.csv")
                 if r["alternative_id"] == "transport_shape_year"
                 and r["province"] != "MAX_ABS"), 0.0),
    ("national config physical coal", "national", "07_uncertainty.tex",
     r"divided by---the total is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "power_plant_physical_coal", "national_total_Mt"), 0.0),
    # The non-circular member of the same family (2026-10-07). Registered beside its
    # neighbour rather than leaning on it: the two are a megatonne and a half apart and a
    # tier-2 repeat would check neither against the other.
    # The legacy control's own delta, printed in the abstract. Registered because a number
    # whose only live source is a configuration row must resolve against that row: the
    # retired 19.4 Mt it replaced appears elsewhere in this document as the EDGAR 1.A.2 gap,
    # so quoting it here would have passed the coverage sweep as a tier-2 repeat of an
    # unrelated quantity - a number checked against the wrong thing is worse than unchecked.
    ("abstract legacy control delta", "national", "00_abstract.tex",
     r"legacy configuration worth\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: abs(float(_cell("national_configurations.csv", "configuration_id",
                             "power_table3_legacy_control", "national_delta_Mt"))), 0.005),
    # THE LEGACY CONTROL'S GRID LEVEL, which the national and power documents both quote
    # several times. Registered once per document so the repeats are covered by a value that
    # resolves against the scenario table rather than by a coincidence: 57.82 was the grid
    # reference for every release until the coal re-base, and after it the string survives in
    # prose with a different meaning, which is the condition under which a stale number looks
    # current.
    # THE RE-BASE'S OWN NUMBERS, each resolving against the ledger that publishes it rather
    # than against a remembered total.
    ("rebase start year move", "national", "07_uncertainty.tex",
     r"start year by only\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _rebase_ledger("FY2015-16", "national_move_Mt"), 0.005),
    ("rebase matched year move", "national", "10_benchmarks.tex",
     r"re-base raised by \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _rebase_ledger("FY2020-21", "national_move_Mt"), 0.005),
    # Table 3's flat conversion, the quantity the whole refutation turns on.
    ("table3 flat conversion", "national", "07_uncertainty.tex",
     r"constant is \\SI\{([\d.]+)\}\{\\tera\\joule\\per\\giga\\gram\}",
     lambda: float(_cell("pakemis_power_coal_configurations.csv", "configuration_id",
                         "C0_table3", "cv_TJ_per_Gg")), 0.01),
    # The leading unresolved structural axis. This number used to ride a tier-2 match on an
    # UNRELATED quantity in the same document (19.4 Mt, which is also the EDGAR 1.A.2
    # diagnostic gap), so the abstract's structural headline was checked against nothing it
    # had anything to do with for several releases.
    ("abstract structural max", "national", "00_abstract.tex",
     r"still open move the total by up to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: float(next(r["metric"] for r in _rows("national_priority_rankings.csv")
                        if r["ranking"] == "structural" and r["rank"] == "1")), 0.005),
    ("road transport mc band", "national", "07_uncertainty.tex",
     r"published\}---\\SI\{([\d.]+)\}\{\}",
     lambda: _mc("within_sector", "Road transport"), 0.05),
    # The uncontrolled PM2.5 bound, which moved with the coal energy the AP-42 factors ride
    # on. Registered rather than left as a tier-2 repeat: it is printed in two sections and
    # one of them is the discussion's summary of the other.
    ("power uncontrolled pm25", "power", "06b_air_pollutants.tex",
     r"The result is \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of\s*uncontrolled",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.05),
    # THE POWER PAPER'S OWN COPIES of the re-base quantities. Registered per document
    # because tier 2 is scoped to a document: the national sections' claims do not cover the
    # power paper's repeats, and 57.82 in particular now means the LEGACY control there.
    ("power legacy control level", "power", "00_abstract.tex",
     r"grid\\_nepra\\_reference\\_legacy\} \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _power_scenario("coal_at_table3_legacy"), 0.005),
    ("power rebase distance", "power", "06_results.tex",
     r"legacy control sits \\SI\{([\d.]+)\}\{\\mega\\tonne\} above the reference",
     lambda: (_power_scenario("coal_at_table3_legacy")
              - _power_scenario("reference")), 0.005),
    ("power rebase over blend span", "power", "06_results.tex",
     r"which is \\num\{([\d.]+)\} times the blend span",
     lambda: ((_power_scenario("coal_at_table3_legacy") - _power_scenario("reference"))
              / (_power_scenario("coal_all_lignite")
                 - _power_scenario("coal_all_bituminous"))), 0.5),
    ("power coal co2 share", "power", "03_study_area_and_data.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} of the\s*category's \\COtwo\{\}",
     lambda: _power_coal_co2_share(), 0.05),
    # Table 3's coal implied efficiency at its highest, the single most implausible cell the
    # refutation rests on. It is a property of the REFUTED account, so the getter asks for
    # that account by name rather than taking whatever the engine books.
    ("power table3 efficiency peak", "power", "05_validation.tex",
     r"implied efficiency runs \\SI\{([\d.]+)\}\{\\percent\} in FY2020",
     lambda: _power_table3_efficiency_hi(), 0.05),
    ("power gas efficiency floor", "power", "05_validation.tex",
     r"efficiency steps from \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\}",
     lambda: _power_gas_efficiency_lo(), 0.5),
    # THE BIOMASS MEMO CONVENTION'S OWN NUMBER. It was covered only as a tier-2 repeat of
    # 36.66 - the crop-residue CH4 row in the same document, an unrelated quantity that
    # happened to round nearby. The same accident covered the national abstract's structural
    # headline against the EDGAR 1.A.2 gap. Both are now computed where they are printed.
    ("residential biomass emission share", "residential", "01_introduction.tex",
     r"of household energy produces \\SI\{([\d.]+)\}\{\\percent\} of reported emissions",
     lambda: _residential_biomass_share(), 0.5),
    ("national legacy control grid level", "national", "07_uncertainty.tex",
     r"retained as \\texttt\{power\\_table3\\_legacy\\_control\} at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _power_scenario("coal_at_table3_legacy"), 0.005),
    ("national config table3 legacy control", "national", "07_uncertainty.tex",
     r"seven of nine years---it is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "power_table3_legacy_control", "national_total_Mt"), 0.05),
    ("uncertainty section transport module cross", "national", "07_uncertainty.tex",
     r"transport module reads \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ under both",
     lambda: _mc("cross_sector", "transport"), 0.0),
    ("residential MC counterpart", "residential", "06_results.tex",
     r"national Monte Carlo counterpart is \$\\pm\$\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _mc("within_sector", "residential"), 0.0),
    ("national config tier1 cement model", "national", "07_uncertainty.tex",
     r"in place of the producer census, it is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "cement_tier1_model_low", "national_total_Mt"), 0.0),
    # rc41 M-2: the reference is the census (21.816); 17.389 is the named diagnostic.
    ("national reference cement census", "national", "10_benchmarks.tex",
     r"observed clinker,\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}, above both",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "process_co2_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu abstract reference co2", "ippu", "00_abstract.tex",
     r"gives the reference \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "process_co2_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu abstract reference interval low", "ippu", "00_abstract.tex",
     r"conditional 95\\%\s*interval ([\d.]+)--[\d.]+ Mt",
     lambda: _first_where("ippu_cement_conditional_intervals_2024.csv", "p025_mt_co2",
                          configuration="reference (producer census)"), 0.0),
    ("ippu abstract reference interval high", "ippu", "00_abstract.tex",
     r"conditional 95\\%\s*interval [\d.]+--([\d.]+) Mt",
     lambda: _first_where("ippu_cement_conditional_intervals_2024.csv", "p975_mt_co2",
                          configuration="reference (producer census)"), 0.0),
    ("ippu results diagnostic co2", "ippu", "06_results.tex",
     r"inferred route are \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "process_co2_mt",
                          method="Diagnostic model f=0.75"), 0.0),
    ("ippu results reference clinker", "ippu", "06_results.tex",
     r"takes the\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of clinker the sixteen producers",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "clinker_activity_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu results reference co2", "ippu", "06_results.tex",
     r"producers report and gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "process_co2_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu conclusion reference co2", "ippu", "09_conclusion.tex",
     r"own disclosed clinker, \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "process_co2_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu conclusion reference interval low", "ippu", "09_conclusion.tex",
     r"conditional 95\\% interval ([\d.]+)--[\d.]+ Mt\), 1\.4",
     lambda: _first_where("ippu_cement_conditional_intervals_2024.csv", "p025_mt_co2",
                          configuration="reference (producer census)"), 0.0),
    ("ippu conclusion reference interval high", "ippu", "09_conclusion.tex",
     r"conditional 95\\% interval [\d.]+--([\d.]+) Mt\), 1\.4",
     lambda: _first_where("ippu_cement_conditional_intervals_2024.csv", "p975_mt_co2",
                          configuration="reference (producer census)"), 0.0),
    # rc41 T-1: the historical monthly product's explicit below-A- grade.
    ("temporal grade nine-year", "national", "12_limitations.tex",
     r"it: \\SI\{([\d.]+)\}\{\\percent\} of its mass varies within the year",
     lambda: _temporal_grade("nine_year_pct"), 0.0),
    ("temporal grade reference year", "national", "12_limitations.tex",
     r"alone carries \\SI\{([\d.]+)\}\{\\percent\}, inside the gate",
     lambda: _temporal_grade("reference_pct"), 0.0),
    ("temporal grade target", "national", "12_limitations.tex",
     r"no more than \\SI\{([\d.]+)\}\{\\percent\} of nine-year monthly mass",
     lambda: _temporal_grade("target_pct"), 0.0),
    ("temporal grade ocac mass", "national", "12_limitations.tex",
     r"carry \\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s*nine-year mass",
     lambda: _temporal_grade("ocac_Mt"), 0.0),
    ("temporal grade after ocac", "national", "12_limitations.tex",
     r"the figure would be \\SI\{([\d.]+)\}\{\\percent\}, inside the gate",
     lambda: _temporal_grade("after_ocac_pct"), 0.0),
    ("transport temporal grade ocac mass", "transport", "06_results.tex",
     r"flat mass---\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _temporal_grade("ocac_Mt"), 0.0),
    ("transport temporal grade nine-year", "transport", "06_results.tex",
     r"below A\$-\$ \(\\SI\{([\d.]+)\}\{\\percent\} of nine-year monthly mass",
     lambda: _temporal_grade("nine_year_pct"), 0.0),
    ("transport temporal grade target", "transport", "06_results.tex",
     r"against a \\SI\{([\d.]+)\}\{\\percent\} gate",
     lambda: _temporal_grade("target_pct"), 0.0),
    ("transport temporal grade after ocac", "transport", "06_results.tex",
     r"gate; \\SI\{([\d.]+)\}\{\\percent\} with the\s*pre-July-2021",
     lambda: _temporal_grade("after_ocac_pct"), 0.0),
    ("longitudinal prefix length", "national", "07_uncertainty.tex",
     r"the first \\num\{(\d+)\} draws of every stream ship as",
     lambda: float(__import__("pkinv.report.longitudinal_uncertainty",
                              fromlist=["PREFIX_N_ITER"]).PREFIX_N_ITER), 0.0),
    ("national closures ledger count", "national", "04_closures.tex",
     r"publishes \\num\{(\d+)\} ledgers in one schema",
     lambda: float(len({r["ledger_id"]
                        for r in _data_rows_nocomment("cross_sector_ledger_map.csv")})),
     0.0),
    ("national config kelectric", "national", "07_uncertainty.tex",
     r"power boundary it is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("national_configurations.csv", "configuration_id",
                   "power_with_kelectric", "national_total_Mt"), 0.0),
    ("discussion 1A2 remaining", "national", "11_discussion.tex",
     r"At roughly\s*\\SI\{(\d+)\}\{\\mega\\tonne\} still missing",
     lambda: round(_bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
                   - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e")), 0.0),
    # rc67: the same remainder at two decimals, in the three sections that print it. It was
    # never anchored in place: it scored as a repeat of the river-discharge wastewater
    # figure, which happened to print 15.85 too, and became visible when that figure moved
    # to 15.39 with the 2019 Refinement.
    ("completeness 1A2 remaining", "national", "09_completeness.tex",
     r"\(1A2\), roughly \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*remaining",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
             - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e"), 0.005),
    ("benchmarks 1A2 remaining", "national", "10_benchmarks.tex",
     r"industrial combustion \(\\SI\{([\d.]+)\}\{\\mega\\tonne\} of its",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
             - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e"), 0.005),
    ("limitations 1A2 remaining", "national", "12_limitations.tex",
     r"leaving about \\SI\{([\d.]+)\}\{\\mega\\tonne\} outstanding",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
             - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e"), 0.005),
    ("discussion EDGAR coverage", "national", "11_discussion.tex",
     r"this inventory reports \\SI\{([\d.]+)\}\{\\percent\} of EDGAR's aggregate magnitude",
     lambda: 100 * _bench("EDGAR", "NATIONAL"), 0.0),
    ("completeness national total", "national", "09_completeness.tex",
     r"an inventory reporting\s*\\SI\{(\d+)\}\{\\mega\\tonne\}", lambda: _sector("TOTAL"), 0.0),
    # ---- the ammonia reconciliation, registered in the round that wrote it --------------
    ("completeness fertiliser gas feed share", "national", "09_completeness.tex",
     r"split at \\SI\{([\d.]+)\}\{\\percent\} feedstock",
     lambda: _annex28_share("2023-24", "Feed"), 0.05),
    ("completeness fertiliser gas fuel share", "national", "09_completeness.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\percent\} process fuel",
     lambda: _annex28_share("2023-24", "Fuel"), 0.05),
    # rc67: the sentence names which configuration each end is, because the two are
    # different KINDS of alternative and are no longer called one range. Each getter reads
    # the named row and raises (KeyError) if that row is not the extreme the sentence says.
    ("results configuration span low", "national", "06_results.tex",
     r"joint floor at \\SI\{([\d.]+)\}\{\} to the",
     lambda: (lambda t: {True: t["fugitives_joint_minimum"]}[
         t["fugitives_joint_minimum"] == min(t.values())])(
             {r["configuration_id"]: float(r["national_total_Mt"])
              for r in _rows("national_configurations.csv")}), 0.01),
    ("results configuration span high", "national", "06_results.tex",
     r"retained legacy power account at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (lambda t: {True: t["power_table3_legacy_control"]}[
         t["power_table3_legacy_control"] == max(t.values())])(
             {r["configuration_id"]: float(r["national_total_Mt"])
              for r in _rows("national_configurations.csv")}), 0.01),
    ("completeness fertiliser gas nfdc mmcfd", "national", "09_completeness.tex",
     r"sector at \\SI\{([\d.]+)\}\{\} MMCFD",
     lambda: _annex28_mmcfd("2023-24"), 0.05),
    ("completeness fertiliser gas agreement", "national", "09_completeness.tex",
     r"fiscal year \\SI\{([\d.]+)\}\{\\percent\} apart",
     lambda: _gas_agreement_pct(), 0.1),
    ("completeness soda ash QIM", "national", "09_completeness.tex",
     r"\\SI\{(\d+)\}\{\\kilo\\tonne\} of soda ash",
     lambda: float(next(r for r in _rows("ippu_activity_controls_2024.csv")
                        if r["product"] == "Soda ash")["quantity"]) / 1000.0, 0.5),
    ("completeness CRT ammonia activity", "national", "09_completeness.tex",
     r"filing's\s*\\SI\{(\d+)\}\{\\kilo\\tonne\} of ammonia",
     lambda: float(next(r for r in _rows("ippu_ammonia_activity_reconciliation.csv")
                        if r["pathway"] == "official CRT")["nh3_kt_central"]), 0.5),
    ("completeness embodied ammonia", "national", "09_completeness.tex",
     r"sits near\s*\\SI\{(\d+)\}\{\\kilo\\tonne\}",
     lambda: float(next(r for r in _rows("ippu_ammonia_activity_reconciliation.csv")
                        if r["pathway"] == "product stoichiometry"
                        and r["period"] == "2024-25")["nh3_kt_central"]), 100.0),
    # "near 44 Mt" is EDGAR's 1A2 figure spoken loosely, in four sections. It rode on the
    # abstract printing 44 exactly - tier 2, a repeat of a checked value - until the abstract
    # started printing 43.98, at which point four claims lost their backing at once and
    # nothing about them had changed. Each is anchored to the benchmark now, with the
    # tolerance the rounding actually needs.
    ("completeness EDGAR 1A2 approx", "national", "09_completeness.tex",
     r"industrial fuel combustion near \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e"), 0.05),
    ("completeness EDGAR 1A2 hole", "national", "09_completeness.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} 1A2 hole",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e"), 0.05),
    ("limitations EDGAR 1A2 approx", "national", "12_limitations.tex",
     r"EDGAR\s*\n?\s*puts the category near \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e"), 0.05),
    ("conclusion EDGAR 1A2 approx", "national", "13_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} EDGAR reports for 1A2",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e"), 0.05),
    ("benchmarks waste over EDGAR", "national", "10_benchmarks.tex",
     r"waste sits at \\SI\{([\d.]+)\}\{\\percent\} of EDGAR",
     lambda: 100 * _bench("EDGAR", "waste", year=2023), 0.0),
    ("benchmarks agriculture over EDGAR", "national", "10_benchmarks.tex",
     r"agriculture at\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * _bench("EDGAR", "TOTAL", year=2024), 0.0),
    # ---- the closure quantities, registered against the relays that compute them --------
    # Every one of these was declared debt. Three were stale: waste generation, disposal and
    # the uncollected remainder had not moved when waste's population panel was projected to
    # the fiscal midpoint, and mixed off-road still printed 2.77 Mt against a live 1.73.
    ("closures waste generated", "national", "04_closures.tex",
     r"single national quantity---\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _waste_mass("generated"), 0.0),
    ("closures waste collection", "national", "04_closures.tex",
     r"Collection is \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _waste_mass("collection_pct"), 0.0),
    ("closures waste disposed", "national", "04_closures.tex",
     r"so \\SI\{([\d.]+)\}\{\\mega\\tonne\} enters",
     lambda: _waste_mass("disposed"), 0.0),
    ("closures waste uncollected", "national", "04_closures.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} remains uncollected",
     lambda: _waste_mass("uncollected"), 0.0),
    ("closures unresolved fate", "national", "04_closures.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} dumped to",
     lambda: _waste_mass("unresolved"), 0.0),
    ("closures waste burned share", "national", "04_closures.tex",
     r"of which \\SI\{([\d.]+)\}\{\\percent\} is openly burned",
     lambda: _waste_mass("burned_share_pct"), 0.0),
    # ---- the availability statement, in the manuscript's own .tex ------------------------
    # Scanning paper_national.tex at all is new: the coverage survey walked sections/ and the
    # front matter was never in it, so the availability statement - which is where a reader
    # looks first for what this release IS - was the least-checked page in the document.
    ("availability activity files", "national-supplement", "paper_national.tex",
     r"classifies all \\num\{(\d+)\} activity files",
     lambda: sum(_source_register_count(s)
                 for s in ("archived", "derived", "not-archived")), 0.0),
    # The spatial-class prose (rc11 rail re-base): the appendix quotes the national S3
    # share and railways' S1 share in running text, beside the table the shares come from.
    # The same national S3 share is quoted in the results section, where the sentence also
    # carries the share it ROSE FROM. That older figure is deliberately a manuscript
    # constant: it is what the previous release published, and a number describing a
    # superseded release must not be recomputed from this one.
    ("results national S3 share", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the inventory reaches the grid",
     lambda: next(float(r["share_of_scope_pct"])
                  for r in _csv_rows("spatial_profile.csv")
                  if r["scope"] == "NATIONAL" and r["spatial_method"] == "S3"), 0.05),
    # "results power raster share" was deleted at Wave 5: its subject - the share
    # of power the cube placed on a raster - no longer exists, because the grid
    # fleet's points are consumed. The 91.2 the sentence still quotes is the
    # HAND-WRITTEN letter's historical claim (a manuscript constant), and the
    # previous release's 96.59 administrative share is one beside it.
    ("results national S2 share", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} now reaches it through",
     lambda: next(float(r["share_of_scope_pct"])
                  for r in _csv_rows("spatial_profile.csv")
                  if r["scope"] == "NATIONAL" and r["spatial_method"] == "S2"), 0.05),
    ("appendix national S3 share", "national", "14_appendix.tex",
     r"S3, \\SI\{([\d.]+)\}\{\\percent\} of the inventory",
     lambda: next(float(r["share_of_scope_pct"])
                  for r in _csv_rows("spatial_profile.csv")
                  if r["scope"] == "NATIONAL" and r["spatial_method"] == "S3"), 0.05),
    # Railways' S1 share was quoted here until the class became derived and the module's
    # traction streams moved to S2 - the corridor service tiers are declared judgement, and
    # a network proxy without per-object activity is what S2 means. The claim that replaces
    # it is the grid fleet's move, which is the largest thing the derivation found.
    # The spatial VIEW axis: whether a placement is where the emission happens. Four claims
    # because each share is a separate row of the profile and the total is what a reader
    # acts on - a sentence that quoted only the total could drift from its own parts.
    # The joint uncertainty statement: the national bound at the coarsest and finest
    # resolutions, so the sentence that says the interval widens cannot stop being true.
    ("uncertainty joint annual low", "national", "07_uncertainty.tex",
     r"\$-\\SI\{([\d.]+)\}\{\\percent\}/\+\\SI\{[\d.]+\}\{\\percent\}\$ annually",
     lambda: _joint_national("annual_national", "low"), 0.02),
    ("uncertainty joint annual high", "national", "07_uncertainty.tex",
     r"/\+\\SI\{([\d.]+)\}\{\\percent\}\$ annually",
     lambda: _joint_national("annual_national", "high"), 0.02),
    ("uncertainty joint monthly adm2 low", "national", "07_uncertainty.tex",
     r"annually to\n\$-\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _joint_national("monthly_adm2", "low"), 0.02),
    ("uncertainty joint monthly adm2 high", "national", "07_uncertainty.tex",
     r"annually to\n\$-\\SI\{[\d.]+\}\{\\percent\}/\+\\SI\{([\d.]+)\}\{\\percent\}\$ for a district",
     lambda: _joint_national("monthly_adm2", "high"), 0.02),
    # The validation register, cited in a manuscript for the first time. Five claims because
    # each is a separate count a reader would act on, and the register grows.
    # THE PRODUCT-FACTS REGISTRY, read by every count a manuscript makes about the release's
    # shape. Each of these was in conflict across documents when an external review found it.
    # "abstract common scope sectors" RETIRED (rc20): the abstract's two-views
    # sentence left with the recovery; the ten-sector count is asserted by the
    # panel-complete CLAIMS trio against the facts registry.
    ("supplement months published", "national-supplement", "sections/generated_products.tex",
     r"(\d+) months, July 2015 to",
     lambda: _product_fact("monthly_months_published"), 0.0),
    ("supplement monthly flat share", "national-supplement",
     "sections/generated_products.tex",
     r"([\d.]+) per cent of the published monthly mass sits on a flat",
     lambda: _product_fact("monthly_flat_share_pct"), 0.05),
    ("results gridded streams", "national", "06_results.tex",
     # rc39 A4: the TOTAL was hard-coded here as 190. When the withdrawn liming stream took
     # it to 189 the pattern stopped matching, so the claim silently unbound and
     # repair_claims reported "nothing to repair" - a claim that matches nothing cannot fail.
     # A regex that embeds a second quantity is a second unchecked claim; this one now
     # captures the numerator and lets the denominator be whatever the sentence says.
     r"\\num\{(\d+)\} of the \\num\{\d+\} source streams, spread over",
     lambda: _product_fact("grid_streams_allocated"), 0.0),
    ("results unallocated streams", "national", "06_results.tex",
     r"the remaining \\num\{(\d+)\} are held at ADM1",
     lambda: _product_fact("grid_streams_unallocated"), 0.0),
    ("ippu fiscal years reported", "ippu", "03_study_area_and_data.tex",
     r"reports all \\num\{(\d+)\} of the national series",
     lambda: _product_fact("ippu_years_estimated"), 0.0),
    # AGRICULTURE'S BASIS. Half the inventory, and the four figures a reader would act on.
    # Anchored to the facts registry rather than to the products directly, so the manuscript
    # and the register cannot disagree in EITHER direction - the failure mode that let a
    # supplement sentence deny a shipped product for four releases.
    ("results agriculture misaligned crops", "national", "06_results.tex",
     r"misalignment of a full calendar year in\s*\\num\{(\d+)\} of the four crops",
     lambda: _product_fact("agriculture_crops_misaligned_by_one_year"), 0.0),
    ("results agriculture calendar share", "national", "06_results.tex",
     r"management, \\SI\{([\d.]+)\}\{\\percent\} of the sector",
     lambda: _product_fact("agriculture_calendar_basis_share_pct"), 0.005),
    ("results agriculture basis change", "national", "06_results.tex",
     r"worth \\SI\{(-[\d.]+)\}\{\\mega\\tonne\} of basis",
     lambda: _product_fact("agriculture_basis_change_Mt"), 0.0005),
    ("results agriculture cotton scope", "national", "06_results.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of cotton",
     lambda: _product_fact("agriculture_cotton_scope_Mt"), 0.0005),
    # THE NINE-YEAR ENSEMBLE, and specifically its NEGATIVE result. A finding that says the
    # panel cannot resolve a year-on-year change is the kind a manuscript drifts away from
    # under revision, so each number is anchored to the register rather than retyped.
    ("uncertainty consecutive changes tested", "national", "07_uncertainty.tex",
     r"of the \\num\{(\d+)\}\s+consecutive year-on-year changes",
     lambda: _product_fact("trend_consecutive_changes_tested"), 0.0),
    ("uncertainty consecutive changes resolved", "national", "07_uncertainty.tex",
     r"typed\) scenario, \\num\{(\d+)\} of the \\num\{8\}",
     lambda: _product_fact("trend_consecutive_changes_resolved"), 0.0),
    ("uncertainty window change", "national", "07_uncertainty.tex",
     r"full-panel change is \\SI\{([\d.]+)\}\{\\mega\\tonne\} over all ten",
     lambda: _product_fact("trend_window_change_Mt"), 0.005),
    ("uncertainty persisting variance share", "national", "07_uncertainty.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the reference year's\s*variance now sits in\s*"
     r"parameters that persist",
     lambda: _product_fact("uncertainty_variance_share_persists_pct"), 0.05),
    ("uncertainty resampling variance share", "national", "07_uncertainty.tex",
     r"persist across years, \\SI\{([\d.]+)\}\{\\percent\} in",
     lambda: _longitudinal_share("variance_share_resamples_pct"), 0.05),
    ("uncertainty residual variance share", "national", "07_uncertainty.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} in residual",
     lambda: _product_fact("uncertainty_variance_share_residual_pct"), 0.05),
    # ONE window since rc20 (the common-scope span merged into the full panel), and
    # the resolution sentence quotes all three scenarios; each end of each range is
    # anchored to its own trend row.
    ("longitudinal typed window low", "national", "07_uncertainty.tex",
     r"resolves at\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} under the typed",
     lambda: _trend_window("P2.5_Mt"), 0.05),
    ("longitudinal typed window high", "national", "07_uncertainty.tex",
     r"resolves at\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} under the typed",
     lambda: _trend_window("P97.5_Mt"), 0.05),
    ("longitudinal correlated window low", "national", "07_uncertainty.tex",
     r"at\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} under time correlation",
     lambda: _trend_window("P2.5_Mt", scenario="time_correlated"), 0.05),
    ("longitudinal correlated window high", "national", "07_uncertainty.tex",
     r"at\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} under time correlation",
     lambda: _trend_window("P97.5_Mt", scenario="time_correlated"), 0.05),
    # Re-anchored 2026-10-07: the sentence now says this reading does NOT resolve, and the
    # low end is negative, which the old [\d.]+ class could not match at all - so the claim
    # would have stopped guarding exactly when the number started mattering.
    ("longitudinal independent window low", "national", "07_uncertainty.tex",
     r"time independence\s*\(\\SIrange\{(-?[\d.]+)\}\{-?[\d.]+\}\{\\mega\\tonne\}\)",
     lambda: _trend_window("P2.5_Mt", scenario="time_independent"), 0.05),
    ("longitudinal independent window high", "national", "07_uncertainty.tex",
     r"time independence\s*\(\\SIrange\{-?[\d.]+\}\{(-?[\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _trend_window("P97.5_Mt", scenario="time_independent"), 0.05),
    # THE DEPOSIT. What a reader receives and what they do not, anchored so the manuscript
    # cannot drift from the manifest in either direction - and the more important direction
    # here is UNDERSTATING what is missing, which is the failure mode that cost a grade band.
    ("limitations registered sources", "national", "12_limitations.tex",
     r"reads\s*\\num\{(\d+)\} registered sources",
     lambda: _product_fact("source_register_entries"), 0.0),
    # rc67: the conclusion's restatement of the same count was covered only as a repeat of
    # the limitations value; when three sources were registered it stayed at 214.
    ("conclusion registered sources", "national", "13_conclusion.tex",
     r"Six of the\s*\\num\{(\d+)\} are this project's own compiled fact tables",
     lambda: _product_fact("source_register_entries"), 0.0),
    ("limitations sources without terms", "national", "12_limitations.tex",
     r"For \\num\{(\d+)\} of those",
     lambda: _product_fact("source_documents_not_redistributable"), 0.0),
    # THE MONTHLY PRODUCT'S THREE FIGURES. The single flat-share number is true and, alone,
    # misleading - it cannot tell a physically-correct flat month from an unread record - so
    # the manuscript now states X, Y and Z, and each is bound to the register that computes
    # it from the released rows.
    ("limitations monthly observed share", "national", "12_limitations.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of monthly mass has",
     lambda: _product_fact("monthly_observed_share_pct"), 0.05),
    ("limitations monthly physical share", "national", "12_limitations.tex",
     r"series; \\SI\{([\d.]+)\}\{\\percent\} is\s*\n?continuous or stock-driven",
     lambda: _product_fact("monthly_physical_share_pct"), 0.05),
    ("limitations monthly weakly timed share", "national", "12_limitations.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} genuinely",
     lambda: _product_fact("monthly_weakly_timed_share_pct"), 0.05),
    ("limitations archived documents", "national", "12_limitations.tex",
     r"of which \\num\{(\d+)\} are third-party publications",
     lambda: _product_fact("source_documents_archived"), 0.0),
    ("limitations archived third-party documents", "national", "12_limitations.tex",
     r"offered the \\num\{(\d+)\} distinct third-party documents",
     _archived_third_party_documents, 0.0),
    ("limitations deposit files", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} files under\s*\n?licences the project can actually grant",
     lambda: _product_fact("deposit_files"), 0.0),
    # The OCAC direct-edition cross-check. Every number in the paragraph is read back from
    # the parse's own summary row, including the POSITIVE CONTROL: a paper that printed
    # "0 disagreements" without also printing how many a known defect would cause is making
    # the weaker claim look like the stronger one.
    ("ocac crosscheck comparisons", "national", "06_results.tex",
     r"\\num\{(\d+)\} months were compared",
     lambda: _ocac_parse_fact("comparisons"), 0.0),
    ("ocac crosscheck exact", "national", "06_results.tex",
     r"\\num\{(\d+)\} agree to the tonne",
     lambda: _ocac_parse_fact("comparisons_exact"), 0.0),
    ("ocac crosscheck max deviation", "national", "06_results.tex",
     r"none disagrees by more than\n\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _ocac_parse_fact("max_relative_delta_pct"), 0.005),
    ("ocac crosscheck mutation caught", "national", "06_results.tex",
     r"is caught by \\num\{(\d+)\} of the \\num\{\d+\} comparisons",
     lambda: _ocac_parse_fact("shift_mutation_caught"), 0.0),
    ("ocac parse product cells", "national", "06_results.tex",
     r"two rows out of \\num\{(\d+)\}",
     lambda: _ocac_parse_fact("product_cells"), 0.0),
    # The PBS QIM parse, read back from its own summary row for the same reason.
    ("qim item years closed", "national", "06_results.tex",
     r"\\num\{(\d+)\} item-years close on the annual total",
     lambda: _qim_parse_fact("item_years_closed"), 0.0),
    ("qim closure rate", "national", "06_results.tex",
     r"a rate of \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _qim_parse_fact("closure_rate_pct"), 0.005),
    ("qim quarantined", "national", "06_results.tex",
     r"and the \\num\{(\d+)\} that do not are kept",
     lambda: _qim_parse_fact("item_years_quarantined"), 0.0),
    ("qim rotation detectable", "national", "06_results.tex",
     r"control published beside it: \\num\{(\d+)\} of the",
     lambda: _qim_parse_fact("rotation_detectable_series"), 0.0),
    ("qim rotation denominator", "national", "06_results.tex",
     r"of the \\num\{(\d+)\} series are distinguishable",
     lambda: _qim_parse_fact("item_years_closed"), 0.0),
    ("qim borrowed shape ratio", "national", "06_results.tex",
     r"peaking at \\num\{([\d.]+)\} times its trough",
     lambda: _cement_shape_ratio("borrowed"), 0.005),
    ("limitations managed soils moved", "national", "12_limitations.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} moved from",
     _managed_soils_observed, 0.15),
    ("limitations agriculture cells", "national", "12_limitations.tex",
     r"across all\s+\\num\{(\d+)\} year-category-gas cells",
     _agriculture_series_cells, 0.0),
    # The corrected trend. Each figure read back from the product, so the section cannot
    # describe a result the rerun no longer gives.
    ("trend common window", "national", "07_uncertainty.tex",
     r"change of \\SI\{([\d.]+)\}\{\\mega\\tonne\} resolves",
     lambda: _product_fact("trend_common_window_change_Mt"), 0.01),
    ("trend first step corrected", "national", "07_uncertainty.tex",
     r"first step is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} and still not resolved",
     lambda: _trend_pair("consecutive"), 0.01),
    ("uncertainty limestone mean", "national", "07_uncertainty.tex",
     r"cement shape to a mean \\num\{([\d.]+)\} percentage points",
     lambda: _limestone_fact("mean"), 0.005),
    ("uncertainty limestone anomaly", "national", "07_uncertainty.tex",
     r"November 2016 carries \\SI\{([\d.]+)\}\{\\percent\} of its year's limestone",
     lambda: _limestone_fact("anomaly"), 0.05),
    ("limitations fugitives moved", "national", "12_limitations.tex",
     r"moved \\SI\{([\d.]+)\}\{\\mega\\tonne\} of cumulative",
     _fugitives_moved, 0.1),
    ("limitations fugitives t2 share", "national", "12_limitations.tex",
     r"observed timing, \\SI\{([\d.]+)\}\{\\percent\} of the sector",
     _fugitives_t2_share, 0.05),
    # The three deferred cross-checks, each read back from its own output.
    ("era5 correlation low", "national", "07_uncertainty.tex",
     r"correlation\n\\num\{([\d.]+)\} to", lambda: _era5_correlation("min"), 0.0005),
    ("era5 correlation high", "national", "07_uncertainty.tex",
     r"to \\num\{([\d.]+)\} across five cities",
     lambda: _era5_correlation("high"), 0.0005),
    ("apcma defect printed", "national", "07_uncertainty.tex",
     r"printed as \\num\{(\d+)\} where", lambda: _apcma_defect("printed"), 0.0),
    ("apcma defect months", "national", "07_uncertainty.tex",
     r"twelve months sum to \\num\{(\d+)\}", lambda: _apcma_defect("months"), 0.0),
    ("era5 offset low", "national", "07_uncertainty.tex",
     r"level by\na systematic \\SIrange\{([\d.]+)\}", lambda: _era5_offset("min"), 0.05),
    ("era5 offset high", "national", "07_uncertainty.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\celsius\}", lambda: _era5_offset("max"), 0.05),
    ("era5 months", "national", "07_uncertainty.tex",
     r"five cities and \\num\{(\d+)\} months", _era5_months, 0.0),
    ("apcma shape difference", "national", "07_uncertainty.tex",
     r"a mean\n\\SI\{([\d.]+)\}\{\} percentage points",
     lambda: _apcma_fact("mean"), 0.005),
    ("apcma months", "national", "07_uncertainty.tex",
     r"of the year over \\num\{(\d+)\} months", lambda: _apcma_fact("months"), 0.0),
    # The 108-month coverage report and the evidence axis beside it.
    ("coverage summary rows", "national", "06_results.tex",
     r"carries exactly \\num\{(\d+)\} rows, one", lambda: float(len(_coverage_summary())), 0.0),
    ("coverage observed share", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the\nnine-year mass is observed",
     lambda: _coverage_share("observed"), 0.05),
    ("coverage flat share", "national", "06_results.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} sits on a declared-flat",
     lambda: _coverage_share("flat"), 0.05),
    ("coverage before panel", "national", "06_results.tex",
     r"average \\SI\{([\d.]+)\}\{\\percent\} observed",
     lambda: _coverage_share_before_or_after_the_panel("before"), 0.05),
    ("coverage after panel", "national", "06_results.tex",
     r"three after it \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _coverage_share_before_or_after_the_panel("after"), 0.05),
    # "coverage missing rows" RETIRED (rc20): the count is structurally zero
    # since the FY2015-16 recovery and asserted by test_monthly_coverage's
    # empty EXPECTED_ABSENT; the prose states the zero in words.
    ("evidence share e1", "national", "06_results.tex",
     r"split is \\SI\{([\d.]+)\}\{\\percent\} E1", lambda: _evidence_share("E1"), 0.05),
    ("evidence share e2", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} E2", lambda: _evidence_share("E2"), 0.05),
    ("evidence share e3", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} E3", lambda: _evidence_share("E3"), 0.05),
    ("evidence share e4", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} E4", lambda: _evidence_share("E4"), 0.05),
    ("qim own shape ratio", "national", "06_results.tex",
     r"where FY2023--24 peaks at\n\\num\{([\d.]+)\} times its own",
     lambda: _cement_shape_ratio("own"), 0.005),
    ("validation entries", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} entries across the three properties",
     lambda: float(len(_csv_rows("pakemis_validation_catalog.csv"))), 0.0),
    ("validation magnitude", "national", "07_uncertainty.tex",
     r"---\\num\{(\d+)\} magnitude",
     lambda: float(sum(1 for r in _csv_rows("pakemis_validation_catalog.csv")
                       if r["property_tested"] == "magnitude")), 0.0),
    ("validation timing", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} timing, ",
     lambda: float(sum(1 for r in _csv_rows("pakemis_validation_catalog.csv")
                       if r["property_tested"] == "timing")), 0.0),
    ("validation geography", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} geography---because",
     lambda: float(sum(1 for r in _csv_rows("pakemis_validation_catalog.csv")
                       if r["property_tested"] == "geography")), 0.0),
    ("validation large independence", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} carry \\emph\{large\} independence",
     lambda: float(sum(1 for r in _csv_rows("pakemis_validation_catalog.csv")
                       if r["independence_class"] == "large")), 0.0),
    ("validation partial independence", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} only \\emph\{partial\}",
     lambda: float(sum(1 for r in _csv_rows("pakemis_validation_catalog.csv")
                       if r["independence_class"] == "partial")), 0.0),
    ("validation no independence", "national", "07_uncertainty.tex",
     r"and \\num\{(\d+)\} \\emph\{none\} at all",
     lambda: float(sum(1 for r in _csv_rows("pakemis_validation_catalog.csv")
                       if r["independence_class"] == "none")), 0.0),
    ("validation declared absences", "national", "07_uncertainty.tex",
     r"\\num\{(\d+)\} rows are declared absences",
     lambda: float(sum(1 for r in _csv_rows("pakemis_validation_catalog.csv")
                       if r["calibration_or_validation"] == "declared-absence")), 0.0),
    ("appendix view physical share", "national", "14_appendix.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the inventory\nis \\texttt\{physical\}",
     lambda: _view_share("physical"), 0.02),
    ("appendix view origin share", "national", "14_appendix.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} is \\texttt\{origin\}",
     lambda: _view_share("origin"), 0.02),
    ("appendix view accounting share", "national", "14_appendix.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} is \\texttt\{accounting\}",
     lambda: _view_share("accounting"), 0.02),
    ("appendix view not physical mass", "national", "14_appendix.tex",
     r"So \\SI\{([\d.]+)\}\{\\mega\\tonne\},",
     lambda: sum(float(r["co2e_Mt_AR5"]) for r in _csv_rows("spatial_view_profile.csv")
                 if r["scope"] == "NATIONAL" and r["spatial_view"] != "physical"), 0.02),
    ("appendix view not physical share", "national", "14_appendix.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the national total, is placed somewhere",
     lambda: 100.0 - _view_share("physical"), 0.02),
    # "appendix grid fleet S3 share" deleted at Wave 5 with its sentence: power
    # carries no S3 row once the fleet's points are consumed, and the appendix
    # narrates the move rather than quoting the vanished share.
    ("appendix captive geocoded", "national", "14_appendix.tex",
     r"\\num\{(\d+)\} of \\num\{\d+\}\s+registered plants are",
     lambda: float(_captive_registry_count("geocoded")), 0.0),
    ("appendix captive members", "national", "14_appendix.tex",
     r"\\num\{\d+\} of \\num\{(\d+)\}\s+registered plants are",
     lambda: float(_captive_registry_count("members")), 0.0),
    ("appendix captive weighted", "national", "14_appendix.tex",
     r"\\num\{(\d+)\} carry a gas allocation",
     lambda: float(_captive_registry_count("weighted")), 0.0),
    # The ODbL carve-out (rc11): the availability statement counts the facility rows
    # whose geometry travels under ODbL, and the registry's licence column is the record.
    ("availability odbl facility rows", "national-supplement", "paper_national.tex",
     r"and \\num\{(\d+)\} rows of the\s*facility registry",
     lambda: sum(1 for r in _csv_rows("pakemis_facility_registry.csv")
                 if r["licence"].startswith("odbl")), 0.0),
    ("availability archived", "national-supplement", "paper_national.tex",
     r"\(\\num\{(\d+)\}\), derived from an archived source",
     lambda: _source_register_count("archived"), 0.0),
    ("availability derived", "national-supplement", "paper_national.tex",
     r"derived from an archived source \(\\num\{(\d+)\}\)",
     lambda: _source_register_count("derived"), 0.0),
    ("availability not archived", "national-supplement", "paper_national.tex",
     r"not kept \(\\num\{(\d+)\}\)",
     lambda: _source_register_count("not-archived"), 0.0),
    # ---- PakEmis-Air beta, in the national supplement ------------------------------------
    # Ten of these were the last of the declared-debt list. They are read from each sector's
    # own air-pollutant output, except residential under configuration S, which no output
    # carries and which is therefore computed through the module.
    # rc67: relabelled and re-pointed with the sentence. The first pair is the reference
    # (the sector's own output, household dung on the survey); the second is configuration
    # L, read from the configurations product, which carries both readings' particulate.
    ("air residential PM2.5 reference", "national-supplement", "supplement.tex",
     r"emits \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of primary",
     lambda: _air("residential", "PM2.5"), 0.0),
    ("air residential BC reference", "national-supplement", "supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\kilo\\tonne\} of black carbon under the reference",
     lambda: _air("residential", "BC"), 0.0),
    ("air residential PM2.5 configuration L", "national-supplement", "supplement.tex",
     r"REF\\_2023\\_24\}\s*\(\\num\{([\d.]+)\} and",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "pm25_kt"), 0.0),
    ("air residential BC configuration L", "national-supplement", "supplement.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\kilo\\tonne\} under configuration~L\)",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "bc_kt"), 0.0),
    ("air residential share beside road", "national-supplement", "supplement.tex",
     r"against residential's \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _keycat("Residential fuel combustion", "level_pct"), 0.0),
    ("air residential GHG share", "national-supplement", "supplement.tex",
     r"Residential solid fuel is \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _keycat("Residential fuel combustion", "level_pct"), 0.0),
    ("air road GHG share", "national-supplement", "supplement.tex",
     r"at \\SI\{([\d.]+)\}\{\\percent\} of\s*the national total against residential",
     lambda: _keycat("Road transport", "level_pct"), 0.0),
    ("air road over residential", "national-supplement", "supplement.tex",
     r"Road transport is \\num\{([\d.]+)\} times its size",
     lambda: _keycat("Road transport", "level_Mt_co2e_AR5")
             / _keycat("Residential fuel combustion", "level_Mt_co2e_AR5"), 0.0),
    ("air transport PM2.5", "national-supplement", "supplement.tex",
     r"emits \\SI\{([\d.]+)\}\{\\kilo\\tonne\}\s*of primary \\PM\{\}: a",
     lambda: _air("transport", "PM2.5"), 0.0),
    ("air waste PM2.5", "national-supplement", "supplement.tex",
     r"Open waste burning\s*contributes \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _air("waste", "PM2.5"), 0.0),
    ("air agriculture PM2.5", "national-supplement", "supplement.tex",
     r"crop-residue burning \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _air("agriculture", "PM2.5"), 0.0),
    ("air residential CO", "national-supplement", "supplement.tex",
     r"carbon\s*monoxide, at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _air("residential", "CO"), 0.0),
    ("air transport CO", "national-supplement", "supplement.tex",
     r"against transport's \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _air("transport", "CO"), 0.0),
    ("air PM ratio reference", "national-supplement", "supplement.tex",
     r"roughly \\num\{([\d.]+)\} times road transport",
     lambda: _air("residential", "PM2.5") / _air("transport", "PM2.5"), 0.0),
    ("air PM ratio configuration L", "national-supplement", "supplement.tex",
     r"REF\\_2023\\_24\} and \\num\{([\d.]+)\} times under configuration~L",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L", "pm25_kt")
     / _air("transport", "PM2.5"), 0.0),
    ("air open burning share", "national-supplement", "supplement.tex",
     r"together \\SI\{([\d.]+)\}\{\\percent\} of the national",
     lambda: _keycat("Open burning of waste", "level_pct")
             + _keycat("Field burning of residues", "level_pct"), 0.0),
    # rc64: the numerator here has always been the WHOLE IPPU module, but until this round the
    # sentence called it "cement" -- true when cement was the only activated category and false
    # from rc52, when ammonia, iron and steel, and lubricant use entered the reference. The
    # getters are unchanged; the prose they anchor now says what they compute, and cement alone
    # is registered separately beside them.
    ("benchmarks IPPU module over whole processes", "national", "10_benchmarks.tex",
     r"IPPU at \\num\{([\d.]+)\} of EDGAR",
     lambda: _sector("ippu") / _bench("EDGAR", "Cement production",
                                      "benchmark_Mt_co2e"), 0.005),
    ("benchmarks cement alone over whole processes", "national", "10_benchmarks.tex",
     r"Cement alone is \\num\{([\d.]+)\} of the whole-processes row",
     lambda: _cell("ippu_totals_2024.csv", "category", "Cement production", "co2e_Mt_AR5")
             / _bench("EDGAR", "Cement production", "benchmark_Mt_co2e"), 0.005),
    ("benchmarks IPPU cement term", "national", "10_benchmarks.tex",
     r"cement at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("ippu_totals_2024.csv", "category", "Cement production", "co2e_Mt_AR5"), 0.005),
    ("benchmarks IPPU ammonia term", "national", "10_benchmarks.tex",
     r"ammonia at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("ippu_totals_2024.csv", "category", "Ammonia production", "co2e_Mt_AR5"), 0.005),
    ("benchmarks IPPU iron and steel term", "national", "10_benchmarks.tex",
     r"iron and steel\s*at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("ippu_totals_2024.csv", "category", "Iron and steel production",
                   "co2e_Mt_AR5"), 0.005),
    ("benchmarks IPPU lubricant term", "national", "10_benchmarks.tex",
     r"adds lubricant use, \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("ippu_totals_2024.csv", "category", "Lubricant use", "co2e_Mt_AR5"), 0.005),
    ("benchmarks IPPU unmatched residual", "national", "10_benchmarks.tex",
     r"The \\SI\{([\d.]+)\}\{\\mega\\tonne\} by which EDGAR's row exceeds",
     lambda: _bench("EDGAR", "Cement production", "benchmark_Mt_co2e") - _sector("ippu"), 0.005),
    # ---- the provincial SO2 external comparison (Section 10) ----------------------------
    # Registered cell by cell because the WHOLE POINT of the passage is that the national
    # ratio and the provincial ratios disagree: a stale national number beside live
    # provincial ones would make the section argue the opposite of what the product says.
    ("provincial so2 national ratio", "national", "10_benchmarks.tex",
     r"the national ratio is \\num\{([\d.]+)\}",
     lambda: _prov_so2("FY2021-22", "comparison", "pakistan", "ratio_engine_over_edgar"), 0.005),
    ("provincial so2 punjab", "national", "10_benchmarks.tex",
     r"Underneath it Punjab is \\num\{([\d.]+)\}",
     lambda: _prov_so2("FY2021-22", "comparison", "Punjab", "ratio_engine_over_edgar"), 0.005),
    ("provincial so2 kp", "national", "10_benchmarks.tex",
     r"Khyber Pakhtunkhwa \\num\{([\d.]+)\}",
     lambda: _prov_so2("FY2021-22", "comparison", "Khyber Pakhtunkhwa",
                       "ratio_engine_over_edgar"), 0.005),
    ("provincial so2 balochistan", "national", "10_benchmarks.tex",
     r"Balochistan \\num\{([\d.]+)\} and Sindh",
     lambda: _prov_so2("FY2021-22", "comparison", "Balochistan",
                       "ratio_engine_over_edgar"), 0.005),
    ("provincial so2 sindh", "national", "10_benchmarks.tex",
     r"and Sindh \\num\{([\d.]+)\}",
     lambda: _prov_so2("FY2021-22", "comparison", "Sindh", "ratio_engine_over_edgar"), 0.005),
    ("provincial so2 power engine", "national", "10_benchmarks.tex",
     r"this inventory books \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _prov_so2("FY2021-22", "power_decomposition", "pakistan", "engine_Gg"), 0.05),
    ("provincial so2 power edgar", "national", "10_benchmarks.tex",
     r"against EDGAR's\s*\\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _prov_so2("FY2021-22", "power_decomposition", "pakistan", "edgar_Gg"), 0.05),
    ("provincial so2 power sindh engine", "national", "10_benchmarks.tex",
     r"in Sindh, where it books \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _prov_so2("FY2021-22", "power_decomposition", "Sindh", "engine_Gg"), 0.05),
    ("provincial so2 power sindh edgar", "national", "10_benchmarks.tex",
     r"against\s*\\SI\{([\d.]+)\}\{\\giga\\gram\}\.",
     lambda: _prov_so2("FY2021-22", "power_decomposition", "Sindh", "edgar_Gg"), 0.05),
    ("provincial so2 bracket high", "national", "10_benchmarks.tex",
     r"gives \\SI\{([\d.]+)\}\{\\giga\\gram\};",
     lambda: (_prov_so2("FY2021-22", "power_decomposition", "pakistan", "engine_Gg")
              + _power_so2_screen("FY2021-22", "uncontrolled")), 0.05),
    ("provincial so2 bracket low", "national", "10_benchmarks.tex",
     r"controlled case gives \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: (_prov_so2("FY2021-22", "power_decomposition", "pakistan", "engine_Gg")
              + _power_so2_screen("FY2021-22", "controlled_case")), 0.05),
    ("provincial so2 bracket position", "national", "10_benchmarks.tex",
     r"at \\SI\{(\d+)\}\{\\percent\} of its width",
     lambda: round(100.0 * (_prov_so2("FY2021-22", "power_decomposition", "pakistan", "edgar_Gg")
                            - (_prov_so2("FY2021-22", "power_decomposition", "pakistan",
                                         "engine_Gg")
                               + _power_so2_screen("FY2021-22", "controlled_case")))
                   / (_power_so2_screen("FY2021-22", "uncontrolled")
                      - _power_so2_screen("FY2021-22", "controlled_case"))), 0.5),
    ("provincial so2 hub coal share", "national", "10_benchmarks.tex",
     r"burned\s*\\SI\{([\d.]+)\}\{\\percent\} of the coal generated",
     lambda: _hub_coal("2021", "generation_share_pct"), 0.05),
    ("provincial so2 hub co2 midperiod", "national", "10_benchmarks.tex",
     r"some \\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s*CO\\textsubscript\{2\}",
     lambda: _hub_coal("2021", "co2_Mt"), 0.05),
    # ---- the power province boundary audit (Section 10) ---------------------------------
    ("boundary audit stations tested", "national", "10_benchmarks.tex",
     r"tests all \\num\{(\d+)\} located",
     lambda: _boundary_audit("stations"), 0.0),
    ("boundary audit misplaced", "national", "10_benchmarks.tex",
     r"fields:\s*\\num\{(\d+)\} are misplaced",
     lambda: _boundary_audit("misplaced"), 0.0),
    ("boundary audit max distance", "national", "10_benchmarks.tex",
     r"within \\SI\{([\d.]+)\}\{\\kilo\\metre\} of a district line",
     lambda: _boundary_audit("max_km"), 0.05),
    ("boundary audit exposure low", "national", "10_benchmarks.tex",
     r"between\s*\\SI\{([\d.]+)\}\{\\percent\} and \\SI\{[\d.]+\}\{\\percent\} of plant-ledger",
     lambda: _boundary_audit("exposure_min"), 0.05),
    ("boundary audit exposure high", "national", "10_benchmarks.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} of plant-ledger generation",
     lambda: _boundary_audit("exposure_max"), 0.05),
    # ---- the citation-vs-deposit audit (Section 12) --------------------------------------
    # The anchor moved in cycle 37 with the wording: the audit no longer reads only the
    # files named BY PATH, so the sentence no longer says so.
    ("limitations cited paths", "national", "12_limitations.tex",
     r"manuscripts name---\\num\{(\d+)\} of them",
     lambda: _citation_audit("cited"), 0.0),
    # These four moved to the PRESENT TENSE in cycle 38. As past-tense claims about what the
    # old scan "could not see" they were historical, but they were wired to live getters, so
    # naming thirteen more files in the bare notation drifted them (194 -> 207, 76 -> 89)
    # inside one cycle. A sentence about a repair either states the measurement the repair
    # took, as a literal, or states the standing fact and lets the getter follow it. This
    # passage now states the standing fact: a prefix-matching scan reaches 111 of 318.
    # The anchor no longer says "two rounds ago": a countdown in prose is stale one cycle later
    # and this one already was. The sentence names the event instead, which cannot age.
    # A LITERAL, and the distinction is the whole point of the paragraph it sits in: this is
    # the audit's denominator as it stood BEFORE the notation repair, a fact about the past.
    # It was briefly wired to the path-notation getter, which was right only while the two
    # numbers coincided; cycle 39 named four files WITH the prefix and the getter moved to
    # 115 while the historical fact stayed 111.
    ("limitations denominator before the repair", "national", "12_limitations.tex",
     r"That denominator was \\num\{(\d+)\} before the notation repair",
     lambda: 111.0, 0.0),
    # The SECOND printed copy of the cited-path count, which no claim reached: the reconciler
    # updated the anchored one and left this at a stale value, and only the quantity scan saw
    # it. Two printed copies of one number need two claims.
    ("limitations cited paths, restated", "national", "12_limitations.tex",
     r"of the \\num\{(\d+)\} files the manuscripts name",
     lambda: _citation_audit("cited"), 0.0),
    ("limitations cited seen before the notation repair", "national", "12_limitations.tex",
     r"matched the first notation alone, which reaches \\num\{(\d+)\}",
     lambda: _citation_audit("path_named"), 0.0),
    ("limitations citations invisible to the old scan", "national", "12_limitations.tex",
     r"the other \\num\{(\d+)\} are named only as a bare",
     lambda: _citation_audit("bare"), 0.0),
    ("limitations invisible and deposited", "national", "12_limitations.tex",
     r"of those \\num\{(\d+)\} are in the archive",
     lambda: _citation_audit("bare_deposited"), 0.0),
    # The three counts of what the notation repair exposed. LITERALS, deliberately: each is a
    # measurement of a one-time repair (22 cited-and-undeposited at the headline tier in cycle
    # 37, 13 described-but-unnamed in cycle 38), and wiring a historical measurement to a live
    # getter is what drifted the four figures above inside a single cycle. The live check that
    # they were really closed is test_citation_deposit's headline-tier assertion, which holds
    # that set at zero - a guard, not a printed number.
    ("limitations undeposited diagnostic", "national", "12_limitations.tex",
     r"What remains undeposited is \\num\{(\d+)\} files typed",
     lambda: _citation_audit("undeposited_diagnostic"), 0.0),
    ("limitations headline tier exposed", "national", "12_limitations.tex",
     r"it exposed \\num\{(\d+)\} \\emph\{sector headline\}",
     lambda: 22.0, 0.0),
    ("limitations headline tier described only", "national", "12_limitations.tex",
     r"A further \\num\{(\d+)\} were the same gap",
     lambda: 22.0, 0.0),
    ("limitations headline tier total", "national", "12_limitations.tex",
     r"All \\num\{(\d+)\} are\s*\n?named and deposited",
     lambda: 44.0, 0.0),
    ("limitations invisible and undeposited", "national", "12_limitations.tex",
     r"are in the archive and \\num\{(\d+)\} are not",
     lambda: _citation_audit("bare_undeposited"), 0.0),
    ("limitations cited deposited", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} are deposited and",
     lambda: _citation_audit("deposited"), 0.0),
    ("limitations cited not deposited", "national", "12_limitations.tex",
     r"are deposited and \\num\{(\d+)\} are not",
     lambda: _citation_audit("absent"), 0.0),
    ("limitations cited intermediates", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} files are now typed as working files",
     lambda: _cited_intermediate(), 0.0),
    ("limitations cited intermediates national", "national", "12_limitations.tex",
     r"while being named in a manuscript, \\num\{(\d+)\} of\s*\n?them in this one",
     lambda: _cited_intermediate("national"), 0.0),
    # A WORD-NUMBER I WROTE MYSELF, one cycle after making the rule. "Seventeen artifacts"
    # slipped past tests/test_word_number_policy.py because that sweep looks for a number word
    # before a UNIT (times, percent, Mt) and "artifacts" is an ordinary noun - a real limit of
    # the sweep, and the reason the claims registry is the second line rather than the only one.
    # It failed here instead, on the rule that every registered pattern must capture exactly
    # one group, which is what a claim with no capture group cannot do.
    # A LITERAL, not the getter: this is what the rc64 repair measured in the tree of that
    # day, and the tree has changed since (five of the seventeen gained break hints in a
    # section). The live reconstruction is registered on its own sentence below.
    ("limitations supplement citations recovered", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} artifacts were recorded as named by nobody",
     lambda: 17.0, 0.0),
    ("limitations supplement citations reconstructed", "national", "12_limitations.tex",
     r"same reconstruction finds \\num\{(\d+)\} rather than",
     lambda: _supplement_citations_recovered(), 0.0),
    ("limitations cited intermediates before repair", "national", "12_limitations.tex",
     r"from \\num\{(\d+)\} to \\num\{\d+\}, without a single citation",
     lambda: 77.0, 0.0),
    ("limitations cited intermediates after repair", "national", "12_limitations.tex",
     r"from \\num\{\d+\} to \\num\{(\d+)\}, without a single citation",
     lambda: 84.0, 0.0),
    # Cycle 36 closed both of these at zero and REWORDED the passage, so both anchors moved
    # with it. A claim whose regex stops matching stops guarding silently - the c31 lesson -
    # so the rule is that the anchor is re-checked in the same edit as the prose.
    ("limitations claim read intermediates", "national", "12_limitations.tex",
     r"types them a working file is now \\num\{(\d+)\}",
     lambda: _claim_read_role_count(), 0.0),
    ("limitations claim read uncited", "national", "12_limitations.tex",
     r"named in no\s+manuscript at all is \\num\{(\d+)\}",
     lambda: _claim_read_role_count(uncited=True), 0.0),
    ("limitations claim read at first measurement", "national", "12_limitations.tex",
     r"contradiction stood at\s*\n?\\num\{(\d+)\} products when it was first measured",
     lambda: 83.0, 0.0),
    ("limitations pattern cover size", "national", "12_limitations.tex",
     r"needed \\num\{(\d+)\} patterns for \\num\{\d+\} files",
     lambda: 61.0, 0.0),
    ("limitations pattern cover target", "national", "12_limitations.tex",
     r"needed \\num\{\d+\} patterns for \\num\{(\d+)\} files",
     lambda: 74.0, 0.0),
    ("limitations catch-all moved", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} files moved on that one change",
     lambda: 74.0, 0.0),
    ("limitations deposit gap", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} hashed products sat in that gap",
     lambda: 13.0, 0.0),
    # ---- the Table 3 coal energy adjudication (Section 7) --------------------------------
    ("uncertainty t3 efficiency high", "national", "07_uncertainty.tex",
     r"efficiency of \\SI\{([\d.]+)\}\{\\percent\} in FY2020--21",
     lambda: _coal_adjudication("FY2020-21", "table3_implied_efficiency_pct"), 0.05),
    ("uncertainty t3 efficiency low", "national", "07_uncertainty.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} in FY2023--24",
     lambda: _coal_adjudication("FY2023-24", "table3_implied_efficiency_pct"), 0.05),
    ("uncertainty plant efficiency low", "national", "07_uncertainty.tex",
     r"implies\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\}, which is a fleet",
     lambda: _coal_adjudication_range("plant_implied_efficiency_pct", "min"), 0.05),
    ("uncertainty plant efficiency high", "national", "07_uncertainty.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\}, which is a fleet",
     lambda: _coal_adjudication_range("plant_implied_efficiency_pct", "max"), 0.05),
    ("uncertainty t3 hdip toe 2019", "national", "07_uncertainty.tex",
     r"works\s+out at \\num\{([\d.]+)\} tonnes of oil equivalent",
     lambda: _coal_adjudication("FY2019-20", "table3_toe_per_hdip_tonne"), 0.005),
    ("uncertainty t3 hdip toe 2020", "national", "07_uncertainty.tex",
     r"at \\num\{([\d.]+)\} tonnes of oil equivalent\s+per tonne in every year"
     r" from FY2015--16 to\s+FY2020--21",
     lambda: _coal_adjudication("FY2020-21", "table3_toe_per_hdip_tonne"), 0.005),
    ("uncertainty hdip ratio first", "national", "07_uncertainty.tex",
     r"quantities runs \\num\{([\d.]+)\}",
     lambda: _coal_adjudication("FY2019-20", "hdip_over_table21"), 0.005),
    ("uncertainty hdip ratio last", "national", "07_uncertainty.tex",
     r"\\num\{[\d.]+\}, \\num\{[\d.]+\}, \\num\{[\d.]+\}, \\num\{[\d.]+\}, \\num\{([\d.]+)\}, crossing unity",
     lambda: _coal_adjudication("FY2023-24", "hdip_over_table21"), 0.005),
    ("uncertainty t21 eff low", "national", "07_uncertainty.tex",
     r"account gives\s+\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\} in every one",
     lambda: _coal_adjudication_range("table21_mass_implied_efficiency_pct", "min"), 0.05),
    ("uncertainty t21 eff high", "national", "07_uncertainty.tex",
     r"account gives\s+\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\} in every one",
     lambda: _coal_adjudication_range("table21_mass_implied_efficiency_pct", "max"), 0.05),
    ("uncertainty hdip eff high", "national", "07_uncertainty.tex",
     r"national series gives \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _coal_adjudication("FY2020-21", "hdip_mass_implied_efficiency_pct"), 0.05),
    ("uncertainty hdip eff low", "national", "07_uncertainty.tex",
     r"falling to \\SI\{([\d.]+)\}\{\\percent\},\s+outside at both ends",
     lambda: _coal_adjudication("FY2023-24", "hdip_mass_implied_efficiency_pct"), 0.05),
    ("uncertainty lignite before", "national", "07_uncertainty.tex",
     r"lignite share by mass goes\s*\nfrom \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _coal_adjudication("FY2020-21", "lignite_share_of_mass_pct"), 0.05),
    ("uncertainty lignite after", "national", "07_uncertainty.tex",
     r"in FY2020--21 to \\SI\{([\d.]+)\}\{\\percent\} in FY2021--22",
     lambda: _coal_adjudication("FY2021-22", "lignite_share_of_mass_pct"), 0.05),
    ("uncertainty lignite end", "national", "07_uncertainty.tex",
     r"and reaches\s*\n\\SI\{([\d.]+)\}\{\\percent\} by the reference year",
     lambda: _coal_adjudication("FY2023-24", "lignite_share_of_mass_pct"), 0.05),
    ("uncertainty t3 toe rise pct", "national", "07_uncertainty.tex",
     r"figure rises \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * (_coal_adjudication("FY2021-22", "table3_coal_toe")
                    / _coal_adjudication("FY2020-21", "table3_coal_toe") - 1), 0.05),
    ("uncertainty t3 toe before abs", "national", "07_uncertainty.tex",
     r"from \\num\{(\d+)\} to\s*\\num\{\d+\}~TOE",
     lambda: _coal_adjudication("FY2020-21", "table3_coal_toe"), 0.5),
    ("uncertainty t3 toe after abs", "national", "07_uncertainty.tex",
     r"to\s*\\num\{(\d+)\}~TOE",
     lambda: _coal_adjudication("FY2021-22", "table3_coal_toe"), 0.5),
    ("uncertainty mass fall pct", "national", "07_uncertainty.tex",
     r"coal mass falling\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * (1 - _coal_adjudication("FY2021-22", "table21_mass_kt")
                    / _coal_adjudication("FY2020-21", "table21_mass_kt")), 0.05),
    ("uncertainty generation fall pct", "national", "07_uncertainty.tex",
     r"coal generation falling \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * (1 - _coal_adjudication("FY2021-22", "coal_generation_GWh")
                    / _coal_adjudication("FY2020-21", "coal_generation_GWh")), 0.05),
    # THE REALLOCATION THE POWER RE-BASE WOULD FORCE ON THE INDUSTRIAL LANE. Both the tonnage
    # and its CO2e are bound, because the paragraph's point is that they offset the power lane
    # and an unguarded offset is how a partial correction reads as a whole one.
    ("completeness reallocation tonnage", "national", "09_completeness.tex",
     r"the other way---at the reference year by\s*\\SI\{(\d+)\}\{\\kilo\\tonne\}",
     lambda: _coal_reallocation("FY2023-24", "industrial_delta_kt"), 0.5),
    ("completeness reallocation co2e", "national", "09_completeness.tex",
     r"worth \\SI\{([\d.]+)\}\{\\mega\\tonne\}~\\COe\{\} against",
     lambda: _coal_reallocation("FY2023-24", "industrial_offset_Mt"), 0.005),
    # THE NON-CIRCULAR ROUTE'S RATIO TO THE PUBLISHED ENERGY. Both endpoints are bound,
    # because the claim is that the ratio CROSSES unity: one endpoint alone would let the
    # sentence survive a change that removed the crossing.
    ("uncertainty coal ratio low", "national", "07_uncertainty.tex",
     r"runs from\s+\\num\{([\d.]+)\} to", lambda: _coal_config_ratio("min"), 0.005),
    ("uncertainty coal ratio high", "national", "07_uncertainty.tex",
     r"to\s+\\num\{([\d.]+)\} across the panel and crosses unity",
     lambda: _coal_config_ratio("max"), 0.005),
    # THE SIX-YEAR FLAT FACTOR AND WHERE IT BREAKS (2026-10-06). Section 7 used to say
    # Table 3's energy was "not a conversion" on the strength of two identical years; the
    # reference audit shows one constant across six, and the correction is the stronger
    # claim, so every number in it is bound to that product rather than remembered.
    ("uncertainty flat factor span", "national", "07_uncertainty.tex",
     r"spanning\s*\\num\{([\d.]+)\}~TOE per tonne",
     lambda: _reference_audit("S2_flat_factor_span", None), 1e-6),
    ("uncertainty flat factor span pct", "national", "07_uncertainty.tex",
     r"or\s+\\SI\{([\d.]+)\}\{\\percent\}---and",
     _reference_audit_span_pct, 0.001),
    ("uncertainty broken factor 2021", "national", "07_uncertainty.tex",
     r"upward\}---to\s+\\SI\{([\d.]+)\}\{\}",
     lambda: _reference_audit_tjgg("FY2021-22"), 0.005),
    ("uncertainty broken factor 2022", "national", "07_uncertainty.tex",
     r"then \\SI\{([\d.]+)\}\{\} and",
     lambda: _reference_audit_tjgg("FY2022-23"), 0.005),
    ("uncertainty broken factor 2023", "national", "07_uncertainty.tex",
     r"and \\SI\{([\d.]+)\}\{\}---over exactly",
     lambda: _reference_audit_tjgg("FY2023-24"), 0.005),
    ("uncertainty physical ncv 2021", "national", "07_uncertainty.tex",
     r"falls from \\SI\{([\d.]+)\}\{\} to",
     lambda: _coal_adjudication("FY2021-22", "composition_only_ncv_TJ_per_Gg"), 0.005),
    ("uncertainty physical ncv 2023", "national", "07_uncertainty.tex",
     r"to \\SI\{([\d.]+)\}\{\\tera\\joule\\per\\giga\\gram\} as",
     lambda: _coal_adjudication("FY2023-24", "composition_only_ncv_TJ_per_Gg"), 0.005),
    # the interior of the two series Section 7 prints in full - the endpoints are anchored
    # above, and a series quoted in full needs every member bound or the middle can drift
    ("uncertainty t3 hdip toe 2021", "national", "07_uncertainty.tex",
     r"\\percent\}---and \\num\{([\d.]+)\}",
     lambda: _coal_adjudication("FY2021-22", "table3_toe_per_hdip_tonne"), 0.005),
    ("uncertainty t3 hdip toe 2023", "national", "07_uncertainty.tex",
     r"\\num\{[\d.]+\},\s*\\num\{[\d.]+\}, \\num\{([\d.]+)\} thereafter",
     lambda: _coal_adjudication("FY2023-24", "table3_toe_per_hdip_tonne"), 0.005),
    ("uncertainty hdip ratio 2020", "national", "07_uncertainty.tex",
     r"quantities runs \\num\{[\d.]+\}, \\num\{([\d.]+)\}",
     lambda: _coal_adjudication("FY2020-21", "hdip_over_table21"), 0.005),
    ("uncertainty hdip ratio 2021", "national", "07_uncertainty.tex",
     r"quantities runs \\num\{[\d.]+\}, \\num\{[\d.]+\}, \\num\{([\d.]+)\}",
     lambda: _coal_adjudication("FY2021-22", "hdip_over_table21"), 0.005),
    ("uncertainty hdip ratio 2022", "national", "07_uncertainty.tex",
     r"quantities runs \\num\{[\d.]+\}, \\num\{[\d.]+\}, \\num\{[\d.]+\}, \\num\{([\d.]+)\}",
     lambda: _coal_adjudication("FY2022-23", "hdip_over_table21"), 0.005),
    # ---- the HDIP coal allocation identity (Section 9) -----------------------------------
    ("completeness identity years", "national", "09_completeness.tex",
     r"over the \\num\{(\d+)\} years both tables",
     lambda: _coal_alloc_years(), 0.0),
    ("completeness identity closes", "national", "09_completeness.tex",
     r"within \\SI\{1\}\{\\kilo\\tonne\} in \\num\{(\d+)\}",
     lambda: _coal_alloc_closes(1.0), 0.0),
    ("completeness window total", "national", "09_completeness.tex",
     r"the total moves\s*\\SI\{(\d+)\}\{\\kilo\\tonne\}",
     lambda: abs(_coal_alloc("redistribution", "FY2019-20..FY2023-24", "total", "value_kt")), 0.5),
    ("completeness window power", "national", "09_completeness.tex",
     r"power column gains\s*\\SI\{(\d+)\}\{\\kilo\\tonne\}",
     lambda: _coal_alloc("redistribution", "FY2019-20..FY2023-24", "power", "value_kt"), 0.5),
    ("completeness window brick cement", "national", "09_completeness.tex",
     r"lose \\SI\{(\d+)\}\{\\kilo\\tonne\}",
     lambda: abs(_coal_alloc("redistribution", "FY2019-20..FY2023-24", "brick_kilns", "value_kt")
                 + _coal_alloc("redistribution", "FY2019-20..FY2023-24", "cement", "value_kt")), 0.5),
    ("completeness brick fall pct", "national", "09_completeness.tex",
     r"series' \\SI\{([\d.]+)\}\{\\percent\} fall",
     lambda: abs(_coal_alloc("redistribution", "FY2019-20..FY2023-24", "brick_kilns",
                             "share_of_total_pct")), 0.05),
    ("completeness brick booked", "national", "09_completeness.tex",
     r"At \\SI\{(\d+)\}\{\\kilo\\tonne\} the booked column",
     lambda: _coal_alloc("brick_bound", "FY2023-24", "bkoap", "value_kt"), 0.5),
    ("completeness fleet kilns bkoap", "national", "09_completeness.tex",
     r"late 2020 at \\num\{(\d+)\} kilns",
     lambda: _coal_alloc("brick_bound", "FY2023-24", "bkoap", "fleet_kilns"), 0.5),
    ("completeness fleet kilns hamdani", "national", "09_completeness.tex",
     r"one reading and \\num\{(\d+)\} on the",
     lambda: _coal_alloc("brick_bound", "FY2023-24", "hamdani", "fleet_kilns"), 0.5),
    ("completeness fleet low bkoap", "national", "09_completeness.tex",
     r"bounds its coal at \\SI\{(\d+)\}\{\\kilo\\tonne\}",
     lambda: _coal_alloc("brick_bound", "FY2023-24", "bkoap", "fleet_low_kt"), 0.5),
    ("completeness fleet low hamdani", "national", "09_completeness.tex",
     r"\\SI\{\d+\}\{\\kilo\\tonne\} and \\SI\{(\d+)\}\{\\kilo\\tonne\} even on the",
     lambda: _coal_alloc("brick_bound", "FY2023-24", "hamdani", "fleet_low_kt"), 0.5),
    ("completeness implied kilns ref", "national", "09_completeness.tex",
     r"supports \\num\{(\d+)\} firing kiln-years",
     lambda: _coal_alloc("brick_bound", "FY2023-24", "bkoap",
                         "implied_firing_kiln_years"), 0.5),
    ("completeness implied kilns 2019", "national", "09_completeness.tex",
     r"against \\num\{(\d+)\} in FY2019--20",
     lambda: _coal_alloc("brick_bound", "FY2019-20", "bkoap",
                         "implied_firing_kiln_years"), 0.5),
    ("completeness full span growth", "national", "09_completeness.tex",
     r"same total grew by \\SI\{(\d+)\}\{\\kilo\\tonne\}",
     lambda: _coal_alloc("redistribution", "FY2010-11..FY2023-24", "total",
                         "value_kt"), 0.5),
    # the band's ends and the factors it falls short by - all derived from the booked column
    # and the fleet bounds, so none of them is a free-standing number
    ("completeness band low", "national", "09_completeness.tex",
     r"spans\s*\\SIrange\{(\d+)\}\{\d+\}\{\\kilo\\tonne\}",
     lambda: 0.70 * _coal_alloc("brick_bound", "FY2023-24", "bkoap", "value_kt"), 0.5),
    ("completeness band high", "national", "09_completeness.tex",
     r"\\SIrange\{\d+\}\{(\d+)\}\{\\kilo\\tonne\} under its",
     lambda: 1.30 * _coal_alloc("brick_bound", "FY2023-24", "bkoap", "value_kt"), 0.5),
    ("completeness shortfall bkoap", "national", "09_completeness.tex",
     r"a factor of\s*\\num\{([\d.]+)\}",
     lambda: (_coal_alloc("brick_bound", "FY2023-24", "bkoap", "fleet_low_kt")
              / (1.30 * _coal_alloc("brick_bound", "FY2023-24", "bkoap", "value_kt"))),
     0.005),
    ("completeness shortfall hamdani", "national", "09_completeness.tex",
     r"\\num\{[\d.]+\} and \\num\{([\d.]+)\} short of those",
     lambda: (_coal_alloc("brick_bound", "FY2023-24", "hamdani", "fleet_low_kt")
              / (1.30 * _coal_alloc("brick_bound", "FY2023-24", "bkoap", "value_kt"))),
     0.005),
    ("completeness kiln coal rate", "national", "09_completeness.tex",
     r"\\SI\{([\d.]+)\}\{\\tonne\} per kiln-year",
     lambda: (_coal_alloc("brick_bound", "FY2023-24", "bkoap", "value_kt") * 1000.0
              / _coal_alloc("brick_bound", "FY2023-24", "bkoap",
                            "implied_firing_kiln_years")), 0.05),
    # ---- the FAOSTAT nitrogen-flow comparison (Section 10) -------------------------------
    ("benchmarks fao fert agreement", "national", "10_benchmarks.tex",
     r"fertiliser nitrogen agrees to \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: abs(100 * (_nflow("synthetic fertiliser nitrogen", "pakemis")
                        / _nflow("synthetic fertiliser nitrogen", "faostat") - 1)), 0.05),
    ("benchmarks fao fert pakemis", "national", "10_benchmarks.tex",
     r"\\num\{(\d+)\} against\s*\\num\{\d+\}~t~N",
     lambda: _nflow("synthetic fertiliser nitrogen", "pakemis"), 0.5),
    ("benchmarks fao fert faostat", "national", "10_benchmarks.tex",
     r"against\s*\\num\{(\d+)\}~t~N",
     lambda: _nflow("synthetic fertiliser nitrogen", "faostat"), 0.5),
    ("benchmarks fao head agreement", "national", "10_benchmarks.tex",
     r"carry agree to\s*\\SI\{([\d.]+)\}\{\\percent\} in total",
     lambda: abs(100 * (_nflow("livestock head: all six species", "pakemis")
                        / _nflow("livestock head: all six species", "faostat") - 1)), 0.05),
    ("benchmarks fao sheep ratio", "national", "10_benchmarks.tex",
     r"counts \\num\{([\d.]+)\} times FAOSTAT's sheep",
     lambda: _nflow("livestock head: sheep", "pakemis_over_faostat"), 0.005),
    ("benchmarks fao camel ratio", "national", "10_benchmarks.tex",
     r"and \\num\{([\d.]+)\} times its camels",
     lambda: _nflow("livestock head: camels", "pakemis_over_faostat"), 0.005),
    ("benchmarks fao soils main", "national", "10_benchmarks.tex",
     r"soils from \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _nflow("managed soils, as reported", "pakemis"), 0.005),
    ("benchmarks fao soils ef2006", "national", "10_benchmarks.tex",
     r"to \\SI\{([\d.]+)\}\{\\mega\\tonne\}, closing",
     lambda: _nflow("managed soils, at FAOSTAT's EF1 vintage", "pakemis"), 0.005),
    ("benchmarks fao gap closed", "national", "10_benchmarks.tex",
     r"closing\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of a",
     lambda: (_nflow("managed soils, at FAOSTAT's EF1 vintage", "pakemis")
              - _nflow("managed soils, as reported", "pakemis")), 0.005),
    ("benchmarks fao gap total", "national", "10_benchmarks.tex",
     r"of a \\SI\{([\d.]+)\}\{\\mega\\tonne\} gap",
     lambda: (_nflow("managed soils, as reported", "faostat")
              - _nflow("managed soils, as reported", "pakemis")), 0.005),
    ("benchmarks fao gap remaining", "national", "10_benchmarks.tex",
     r"The remaining\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} is neither",
     lambda: _nflow("unexplained after activity and EF1 vintage", "pakemis"), 0.005),
    ("benchmarks fao ef1 2006", "national", "10_benchmarks.tex",
     r"aggregate EF1 of \\num\{([\d.]+)\}",
     lambda: _faostat_ef1(), 0.0),
    ("benchmarks fao excreted n", "national", "10_benchmarks.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of excreted nitrogen",
     lambda: _n_excreted_Mt(), 0.0005),
    ("benchmarks fao grazing share", "national", "10_benchmarks.tex",
     r"applied to the \\SI\{([\d.]+)\}\{\\percent\} of this",
     lambda: _n_grazing_pct(), 0.05),
    ("benchmarks fao pasture pakemis", "national", "10_benchmarks.tex",
     r"pasture deposition is \\SI\{([\d.]+)\}\{\\mega\\tonne\} here",
     lambda: _npool("manure on pasture", "pakemis"), 0.005),
    ("benchmarks fao pasture faostat", "national", "10_benchmarks.tex",
     r"here against\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}, a difference",
     lambda: _npool("manure on pasture", "faostat"), 0.005),
    ("benchmarks fao pasture gap", "national", "10_benchmarks.tex",
     r"a difference of \\SI\{([\d.]+)\}\{\\mega\\tonne\} and",
     lambda: (_npool("manure on pasture", "faostat")
              - _npool("manure on pasture", "pakemis")), 0.005),
    ("benchmarks fao pasture share", "national", "10_benchmarks.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\}\s*\n?of the total",
     lambda: _npool_gap_share("manure on pasture"), 0.05),
    ("benchmarks fao synth gap", "national", "10_benchmarks.tex",
     r"Synthetic fertiliser contributes \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (_npool("synthetic fertiliser", "faostat")
              - _npool("synthetic fertiliser", "pakemis")), 0.005),
    ("benchmarks fao synth share", "national", "10_benchmarks.tex",
     r"\(\\SI\{([\d.]+)\}\{\\percent\}\) and crop residues",
     lambda: _npool_gap_share("synthetic fertiliser"), 0.05),
    ("benchmarks fao residue gap", "national", "10_benchmarks.tex",
     r"crop residues \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (_npool("crop residues", "faostat")
              - _npool("crop residues", "pakemis")), 0.005),
    ("benchmarks fao applied ratio", "national", "10_benchmarks.tex",
     r"is \\num\{([\d.]+)\} times FAOSTAT's despite",
     lambda: _npool("manure applied to soils", "pakemis_over_faostat"), 0.005),
    ("benchmarks fao both soils", "national", "10_benchmarks.tex",
     r"moves managed soils to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sens_soils("Both 2006 direct factors (EF1 0.010 + EF3PRP aggregate)"), 0.005),
    ("benchmarks fao both closed", "national", "10_benchmarks.tex",
     r"closing \\SI\{([\d.]+)\}\{\\mega\\tonne\} or",
     lambda: _sens_soils("Both 2006 direct factors (EF1 0.010 + EF3PRP aggregate)") - _sens_soils("Main case (EF1=0.005 dry; rice continuously flooded)"), 0.005),
    ("benchmarks fao both pct", "national", "10_benchmarks.tex",
     r"or \\SI\{(\d+)\}\{\\percent\} of the gap",
     lambda: round(100 * (_sens_soils("Both 2006 direct factors (EF1 0.010 + EF3PRP aggregate)") - _sens_soils("Main case (EF1=0.005 dry; rice continuously flooded)"))
                   / (_nflow("managed soils, as reported", "faostat")
                      - _sens_soils("Main case (EF1=0.005 dry; rice continuously flooded)"))), 0.5),
    ("benchmarks fao both remaining", "national", "10_benchmarks.tex",
     r"What remains is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (_nflow("managed soils, as reported", "faostat")
              - _sens_soils("Both 2006 direct factors (EF1 0.010 + EF3PRP aggregate)")), 0.005),
    # ---- the railway benchmark, year-matched ---------------------------------------------
    # The national paper used to compare BUR-1's FY2017-18 filing against this inventory's
    # FY2023-24 figure while the railways report led with the matched-year reconstruction;
    # two documents describing the same comparison two different ways.
    # The matched two-year table. Each cell is anchored, because the defect it replaced was
    # three different years quoted in one paragraph as though they were one comparison.
    ("railmatched diesel FY2018", "national", "10_benchmarks.tex",
     r"thousand litres & \\num\{(\d+)\}",
     lambda: _rail_year_litres(2018), 0.0),
    ("railmatched diesel FY2024", "national", "10_benchmarks.tex",
     r"thousand litres & \\num\{\d+\} & \\num\{(\d+)\}",
     lambda: _rail_year_litres(2024), 0.0),
    ("railmatched estimate FY2018", "national", "10_benchmarks.tex",
     r"\\COe\{\} & \\num\{([\d.]+)\} & \\num\{[\d.]+\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.0),
    ("railmatched estimate FY2024", "national", "10_benchmarks.tex",
     r"\\COe\{\} & \\num\{[\d.]+\} & \\num\{([\d.]+)\}",
     lambda: _sector("railways"), 0.0),
    ("railmatched ratio", "national", "10_benchmarks.tex",
     r"Submission over this inventory & \\num\{([\d.]+)\}",
     lambda: 4.06 / _cell("railways_totals_2024.csv", "category",
                          "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.05),
    ("railmatched mass FY2018", "national", "10_benchmarks.tex",
     r"\\kilo\\tonne\} & \\num\{(\d+)\}",
     lambda: _rail_year_litres(2018) * _rail_density_t_per_kl(), 1.0),
    ("railmatched mass FY2024", "national", "10_benchmarks.tex",
     r"\\kilo\\tonne\} & \\num\{\d+\} & \\num\{(\d+)\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Traction diesel, for cross-source comparison", "co2e_Mt_AR5"), 0.5),
    ("benchmarks railway matched year", "national", "10_benchmarks.tex",
     r"identical method, this inventory reconstructs \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.0),
    ("benchmarks railway matched ratio", "national", "10_benchmarks.tex",
     r"BUR-1 is \\num\{([\d.]+)\} times it",
     lambda: 4.06 / _cell("railways_totals_2024.csv", "category",
                          "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.05),
    # ---- the railway divergence, PLACED (cycle 24) -----------------------------------------
    # Every one read from railways_official_comparison_2024.csv or the fuel history, never
    # transcribed. The national paper had carried only the BUR-1 row while the product held
    # five, and Section 1 claimed the INC was "not used as a comparator anywhere in this
    # paper" while the register used it.
    ("benchmarks railway crt ratio", "national", "10_benchmarks.tex",
     r"the filing is\s*\n?\\num\{([\d.]+)\} times it",
     lambda: _rail_benchmark("crt2022", "ratio_official_over_own"), 0.05),
    ("benchmarks railway crt activity", "national", "10_benchmarks.tex",
     r"book \\SI\{(\d+)\}\{\\tera\\joule\}",
     lambda: _crt_rail_cell("activity_TJ"), 0.5),
    ("benchmarks railway inc official", "national", "10_benchmarks.tex",
     r"implies \\SI\{([\d.]+)\}\{\\mega\\tonne\} for FY1993",
     lambda: _rail_benchmark("inc1994", "official_Mt_co2e"), 0.0),
    ("benchmarks railway inc shortfall", "national", "10_benchmarks.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} \\emph\{below\} this",
     lambda: 100.0 * (1 - _rail_benchmark("inc1994", "ratio_official_over_own")), 0.05),
    ("benchmarks railway official rise", "national", "10_benchmarks.tex",
     r"rose by a factor of \\num\{([\d.]+)\}",
     lambda: 4.06 / _rail_benchmark("inc1994", "official_Mt_co2e"), 0.05),
    ("benchmarks railway own fall", "national", "10_benchmarks.tex",
     r"\\emph\{fell\} by \\SI\{(\d+)\}\{\\percent\}",
     lambda: 100.0 * (1 - _rail_benchmark("bur1", "own_Mt_co2e")
                      / _rail_benchmark("inc1994", "own_Mt_co2e")), 0.5),
    ("benchmarks railway history peak", "national", "10_benchmarks.tex",
     r"peaks at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _rail_history_peak(), 0.0),
    ("benchmarks railway peak coal", "national", "10_benchmarks.tex",
     r"burned \\num\{(\d+)\} tonnes of coal",
     lambda: float(_rail_history_peak_row()["coal_t"]), 0.0),
    ("benchmarks railway peak furnace oil", "national", "10_benchmarks.tex",
     r"\\num\{(\d+)\} tonnes\s*\n?of furnace oil",
     lambda: float(_rail_history_peak_row()["furnace_oil_t"]), 0.0),
    ("benchmarks railway over peak", "national", "10_benchmarks.tex",
     r"is\s*\n?\\num\{([\d.]+)\} times that peak",
     lambda: 4.06 / _rail_history_peak(), 0.05),
    # The CRT activity ratio, at all four sites that print it. It read "eleven" as a spelled-out
    # WORD in the abstract, introduction, discussion and conclusion - invisible to
    # quantity_policy, which sweeps siunitx arguments and numeric tabular cells - and rested on
    # a different denominator from the product beside it: the implied 1316.5 kt over FY2021-22's
    # metered mass alone (120.1 kt, 11.0x) rather than over the mean of the two fiscal years
    # calendar 2022 straddles, which is the basis the product's own match_basis declares
    # (104.4 kt, 12.6x). The word understated the divergence.
    ("railways crt over metered, abstract", "railways", "00_abstract.tex",
     r"TJ for railways, \\num\{([\d.]+)\} times the metered fuel",
     lambda: _rail_benchmark("crt2022", "implied_over_metered"), 0.05),
    ("railways crt over metered, intro", "railways", "01_introduction.tex",
     r"railway activity, \\num\{([\d.]+)\} times the metered fuel",
     lambda: _rail_benchmark("crt2022", "implied_over_metered"), 0.05),
    ("railways crt over metered, discussion", "railways", "07_discussion.tex",
     r"the activity cell is \\num\{([\d.]+)\} times the",
     lambda: _rail_benchmark("crt2022", "implied_over_metered"), 0.05),
    ("railways crt over metered, conclusion", "railways", "09_conclusion.tex",
     r"CRT books \\num\{([\d.]+)\} times the metered activity",
     lambda: _rail_benchmark("crt2022", "implied_over_metered"), 0.05),
    # ---- word-numbers promoted to registered numerals (cycle 25, Q29) ----------------------
    # Each of these was a spelled-out word, invisible to quantity_policy, with a product
    # behind it that could move. doc_claims already carried the lesson on one IPPU claim -
    # "'eleven' cannot be repaired, and it was wrong the moment five arrived" - and it stayed
    # a comment on that claim while the same defect recurred four more times.
    ("factor trap rail over road, national", "national", "05_factor_tables.tex",
     r"vs \\num\{3\.9\}---\\num\{([\d.]+)\} times higher",
     lambda: _factor_ratio("rail_n2o_diesel", "tr_n2o_diesel"), 0.05),
    ("factor trap rail over road, railways", "railways", "04b_emission_factors.tex",
     r"is \\num\{([\d.]+)\} times road\}",
     lambda: _factor_ratio("rail_n2o_diesel", "tr_n2o_diesel"), 0.05),
    ("factor trap rail over road, transport", "transport", "S3_completeness.tex",
     r"factor is ([\d.]+) times the road value\. Railway",
     lambda: _factor_ratio("rail_n2o_diesel", "tr_n2o_diesel"), 0.05),
    ("factor trap offroad over road, transport", "transport", "S3_completeness.tex",
     r"N2O is ([\d.]+) times the road value \(and identical",
     lambda: _factor_ratio("offroad_n2o_diesel", "tr_n2o_diesel"), 0.05),
    ("rail diesel year change, national", "national", "10_benchmarks.tex",
     r"diesel is \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _rail_diesel_change(), 0.05),
    ("rail diesel year change, railways intro", "railways", "01_introduction.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\}\. And it is not history",
     lambda: _rail_diesel_change(), 0.05),
    ("rail diesel year change, railways validation", "railways", "05_validation.tex",
     r"diesel is \\SI\{([\d.]+)\}\{\\percent\} above FY2023",
     lambda: _rail_diesel_change(), 0.05),
    ("rail inc agreement, railways", "railways", "05_validation.tex",
     r"sits within \\SI\{([\d.]+)\}\{\\percent\} of this",
     lambda: 100.0 * (1 - _rail_benchmark("inc1994", "ratio_official_over_own")), 0.05),
    ("rail peak over today, railways intro", "railways", "01_introduction.tex",
     r"emitted \\num\{([\d.]+)\} times its present total",
     lambda: _rail_history_peak() / _cell("railways_totals_2024.csv", "category",
                                          "Module total (both categories)",
                                          "co2e_Mt_AR5"), 0.05),
    ("rail peak over today, railways conclusion", "railways", "09_conclusion.tex",
     r"peak \\num\{([\d.]+)\} times today's total",
     lambda: _rail_history_peak() / _cell("railways_totals_2024.csv", "category",
                                          "Module total (both categories)",
                                          "co2e_Mt_AR5"), 0.05),
    # ---- structural scenarios and configuration ranges quoted in prose --------------------
    # The structural bridge, read from the bridge output rather than from three sector tables.
    ("QA table categories reported", "national", "11_discussion.tex",
     r"categories screened against \\num\{(\d+)\} reported",
     lambda: float(len(_rows("national_key_categories.csv"))), 0.0),
    # rc67: the defect row quotes the fugitives figure of the release it happened in, which
    # is the envelope's top and no longer the reference (feedstock inside the leak base).
    ("QA table fugitives then-current", "national", "11_discussion.tex",
     r"beside the then-current \\SI\{([\d.]+)\}\{\} \(the envelope's top\)",
     lambda: _first_where("fugitives_structural_scenarios_2024.csv", "mt_co2e_ar5",
                          scenario="post_meter_including_feedstock"), 0.0),
    # rc67: re-pointed. The surrogate Sobol attribution this read is retired; the sentence
    # now states the parameter graph's own row-private residual share, the product fact the
    # claim matrix (intro_residual_variance) already resolves it against.
    ("introduction residual share", "national", "01_introduction.tex",
     r"now\s*finds is that \\SI\{([\d.]+)\}\{\\percent\} of the national variance",
     lambda: _product_fact("uncertainty_variance_share_residual_pct"), 0.05),
    ("introduction enteric variance share", "national", "01_introduction.tex",
     r"enteric fermentation carries \\SI\{([\d.]+)\}\{\\percent\} of it",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="category", name="Enteric fermentation"), 0.0),
    ("bridge interval in megatonnes", "national", "07_uncertainty.tex",
     r"interval, which is about \\SI\{(\d+)\}\{\\mega\\tonne\}",
     lambda: _mc("within_sector", "TOTAL") / 100.0 * _sector("TOTAL"), 0.5),
    ("uncertainty coal calorific scenario", "national", "07_uncertainty.tex",
     r"coal calorific conversion \(worth \\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _power_scenario("reference") - _power_scenario("coal_at_implied_cv"), 0.0),
    ("completeness industry gas at 900", "national", "09_completeness.tex",
     r"moves the gas rows from \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _industry_gas_Mt() * 0.9, 0.005),
    ("completeness industry at 900", "national", "09_completeness.tex",
     r"as a whole from \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("industry_totals_2024.csv", "category",
                   "Sensitivity: gas at 900 Btu/scf", "co2e_Mt_AR5"), 0.0),
    ("completeness industry at 1000", "national", "09_completeness.tex",
     r"as a whole from \\SI\{[\d.]+\}\{\\mega\\tonne\} to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sector("industry"), 0.0),
    ("benchmarks cement high clinker", "national", "10_benchmarks.tex",
     r"0.95-fraction trade-corrected configuration gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("ippu_cement_conditional_intervals_2024.csv", "configuration",
                   "diagnostic model f=0.95 (all-Portland)", "deterministic_mt_co2"), 0.0),
    ("benchmarks railway metered fuel", "national", "10_benchmarks.tex",
     r"reports buying \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Traction diesel, for cross-source comparison", "co2e_Mt_AR5"), 0.5),
    ("limitations configuration ratio", "national", "12_limitations.tex",
     # rc67: the ratio is stated against the 2024-25 HIES round AS MEASURED (11.97 Mt), the
     # basis pakemis_dung_balance.csv's falsifiable row uses; _dung_configuration_ratio()
     # divides by the reference's interpolated 10.93 Mt and gives 5.4, a different quantity
     r"which diverts \\num\{([\d.]+)\} times what the 2024--25 survey round measured",
     lambda: 1e9 * _cell("residential_dung_ledger_2024.csv", "claimant",
                         "Diverted to fuel (agriculture ledger)", "Mt_air_dry")
             / _cell("residential_hies_comparison_2024.csv", "fuel", "dung_cake",
                     "hies2425_annual"), 0.0),
    # ---- sector-output quantities the flagship quotes ------------------------------------
    # These were declared debt on the grounds that registering them meant teaching this file
    # to read nine more sector outputs. That was true and it was not a reason: two of them
    # (the river-discharge wastewater sensitivity, quoted in two sections) were stale by
    # 0.4 Mt when the list was finally worked through.
    ("benchmarks wastewater river MCF", "national", "10_benchmarks.tex",
     r"At \\num\{0.1\} it is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_2024.csv", "category",
                   "Sensitivity: wastewater on the river-discharge MCF (category total)",
                   "co2e_Mt_AR5"), 0.0),
    ("discussion wastewater river MCF", "national", "11_discussion.tex",
     r"domestic wastewater from \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_2024.csv", "category",
                   "Sensitivity: wastewater on the river-discharge MCF (category total)",
                   "co2e_Mt_AR5"), 0.0),
    ("discussion wastewater factor", "national", "11_discussion.tex",
     r"\\mega\\tonne\}---a factor of \\num\{([\d.]+)\}",
     lambda: _keycat("Domestic wastewater", "level_Mt_co2e_AR5")
             / _cell("waste_totals_2024.csv", "category",
                     "Sensitivity: wastewater on the river-discharge MCF (category total)",
                     "co2e_Mt_AR5"), 0.0),
    ("conclusion wastewater factor", "national", "13_conclusion.tex",
     r"wastewater by a factor of\s*\\num\{([\d.]+)\}",
     lambda: _keycat("Domestic wastewater", "level_Mt_co2e_AR5")
             / _cell("waste_totals_2024.csv", "category",
                     "Sensitivity: wastewater on the river-discharge MCF (category total)",
                     "co2e_Mt_AR5"), 0.0),
    # rc67: the roles swapped. The rollup carries the survey reading; configuration L is
    # the sensitivity row, and it RAISES the total.
    ("limitations configuration difference", "national", "12_limitations.tex",
     r"would raise the \\texttt\{REF\\_2023\\_24\} total by\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: dung configuration L (all diverted dung)", "co2e_Mt_AR5")
             - _sector("residential"),
     0.0),
    ("limitations unresolved dung mass", "national", "12_limitations.tex",
     r"burn in households, \\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s*air-dry cake",
     lambda: _cell("residential_dung_ledger_2024.csv", "claimant",
                   "UNRESOLVED - diverted air-dry cake with no observed destination",
                   "Mt_air_dry"), 0.0),
    ("limitations firewood case reported total", "national", "12_limitations.tex",
     r"against the\s*reported \\SI\{([\d.]+)\}\{\\mega\\tonne\}\. Dropping firewood",
     lambda: _sector("residential"), 0.0),
    ("completeness industrial gas", "national", "09_completeness.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of industrial\s*process gas",
     lambda: _industry_gas_Mt(), 0.0),
    ("limitations industrial gas", "national", "12_limitations.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of industrial process gas",
     lambda: _industry_gas_Mt(), 0.0),
    ("results industrial gas", "national", "06_results.tex",
     r"industrial-fuel row is metered gas \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _industry_gas_Mt(), 0.0),
    # ---- the remaining results-section quantities ---------------------------------------
    # All were declared debt, and three had gone stale: the fossil-methane share, the energy
    # sectors' combined share, and the Khyber Pakhtunkhwa provincial correction, which still
    # quoted a KP share of 0.02 percent that is in fact the "Other" row of the same table.
    ("results fossil methane", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}---\\SI\{[\d.]+\}\{\\percent\} of the inventory's methane",
     lambda: _methane("fossil_Mt"), 0.0),
    ("results fossil methane share", "national", "06_results.tex",
     r"---\\SI\{([\d.]+)\}\{\\percent\} of the inventory's methane",
     lambda: _methane("fossil_share"), 0.0),
    ("results energy sectors share", "national", "06_results.tex",
     r"residential fuel---together are \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: sum(_keycat(c, "level_pct") for c in
                 ("Road transport", "Electricity and heat production",
                  "Residential fuel combustion")), 0.0),
    ("results AR5-AR6 percent", "national", "06_results.tex",
     r"difference is \\SI\{[\d.]+\}\{\\mega\\tonne\}, or \\SI\{([\d.]+)\}\{\\percent\} lower",
     lambda: 100.0 * (_sector("TOTAL") - _sector("TOTAL", "co2e_Mt_AR6")) / _sector("TOTAL"),
     0.0),
    ("results KP provincial share", "national", "06_results.tex",
     r"Khyber Pakhtunkhwa carries \\SI\{([\d.]+)\}\{\\percent\} of the sector",
     lambda: _power_province_share("Khyber Pakhtunkhwa"), 0.0),
    # ---- the gas decomposition, from the ledger built for it ----------------------------
    ("results methane share", "national", "06_results.tex",
     r"Methane is\s*\\SI\{([\d.]+)\}\{\\percent\} of the national total",
     lambda: _gas("CH4", "share"), 0.0),
    ("results methane AR5-AR6", "national", "06_results.tex",
     r"methane falls by \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _gas("CH4", "AR5") - _gas("CH4", "AR6"), 0.0),
    ("results N2O AR5-AR6", "national", "06_results.tex",
     r"nitrous oxide\s*rises by \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _gas("N2O", "AR6") - _gas("N2O", "AR5"), 0.0),
    ("closures diverted nitrogen", "national", "04_closures.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of excreted nitrogen a year",
     lambda: _diverted_nitrogen_Mt(), 0.0),
    # rc67: the transfer's air-dry mass is the DIVERTED mass (the dung ledger's control
    # row), which is what the volatile solids beside it describe. _dung_mass("air_dry")
    # follows the reference basis, which is now the household survey, so it is read for the
    # household sentence below and the ledger product for the diversion.
    ("closures dung air dry", "national", "04_closures.tex",
     r"corresponds to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry dung cake",
     lambda: _cell("residential_dung_ledger_2024.csv", "claimant",
                   "Diverted to fuel (agriculture ledger)", "Mt_air_dry"), 0.0),
    ("closures dung basis ratio", "national", "04_closures.tex",
     r"is \\num\{([\d.]+)\} times smaller than it",
     lambda: _cell("residential_dung_ledger_2024.csv", "claimant",
                   "Diverted to fuel (agriculture ledger)", "Mt_air_dry")
     / _dung_mass("volatile_solids"), 0.05),
    ("closures dung household mass", "national", "04_closures.tex",
     r"household survey observes, \\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry cake",
     lambda: _dung_mass("air_dry"), 0.0),
    ("closures dung unresolved mass", "national", "04_closures.tex",
     r"the other \\SI\{([\d.]+)\}\{\\mega\\tonne\} of the diversion",
     lambda: _cell("residential_dung_ledger_2024.csv", "claimant",
                   "UNRESOLVED - diverted air-dry cake with no observed destination",
                   "Mt_air_dry"), 0.0),
    ("closures dung volatile solids", "national", "04_closures.tex",
     r"The result is \\SI\{([\d.]+)\}\{\\mega\\tonne\} of \\emph\{volatile solids\}",
     lambda: _dung_mass("volatile_solids"), 0.0),
    ("closures off-road category", "national", "04_closures.tex",
     r"reported category of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _keycat("Mixed off-road (1A4c/1A2)", "level_Mt_co2e_AR5"), 0.0),
    ("results agriculture share", "national", "06_results.tex",
     r"Agriculture is \\SI\{([\d.]+)\}\{\\percent\} of",
     lambda: float(_sector_row("agriculture")["share_pct"]), 0.0),
    ("benchmarks rice over climate trace", "national", "10_benchmarks.tex",
     r"rice at \\num\{([\d.]+)\} of Climate",
     lambda: _bench("Climate TRACE", "Rice cultivation"), 0.0),
    ("benchmarks magnitude ratio", "national", "10_benchmarks.tex",
     r"this work is \\SI\{([\d.]+)\}\{\\percent\} of EDGAR's Pakistani sectors",
     lambda: 100 * _bench("EDGAR", "NATIONAL"), 0.0),
    ("benchmarks magnitude ratio restated", "national", "10_benchmarks.tex",
     r"Magnitude ratio, \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * _bench("EDGAR", "NATIONAL"), 0.0),
    ("benchmarks engine total", "national", "10_benchmarks.tex",
     r"\\SI\{([\d.]+)\}\{\} against\s*\\SI\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _sector("TOTAL"), 0.0),
    ("completeness EDGAR coverage", "national", "09_completeness.tex",
     r"this inventory is \\SI\{([\d.]+)\}\{\\percent\}\s*of EDGAR's",
     lambda: 100 * _bench("EDGAR", "NATIONAL"), 0.0),
    ("completeness EDGAR shortfall", "national", "09_completeness.tex",
     r"makes that\s*\\SI\{([\d.]+)\}\{\\percent\} attributable",
     lambda: 100 * (1 - _bench("EDGAR", "NATIONAL")), 0.0),

    ("results 1A2 estimated total", "national", "06_results.tex",
     r"Together they are \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e"), 0.0),
    ("results captive gas stream", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}\); the transport module",
     lambda: _source_stream("Captive gas self-generation (1A2)"), 0.0),
    ("keycat superseded row count", "national", "08_key_categories.tex",
     r"table \\num\{(\d+)\} rows against the category table",
     lambda: len(_rows("national_key_categories.csv")) + 1, 0.0),
    ("keycat category count", "national", "08_key_categories.tex",
     r"variance share for all \\num\{(\d+)\} IPCC categories",
     lambda: len(_rows("national_key_categories.csv")), 0.0),

    # ---- national: completeness tally and the whole-inventory benchmark ----
    # v1.0.0: the four counts are value macros written by the stored query
    # tab_completeness (scripts/make_paper_artefacts.py, get_completeness per key). The
    # anchors follow them into the generated file so the engine's own tally still
    # cross-checks the query layer's - two independent readers of completeness.csv.
    ("estimated count", "national", "gen_tab_completeness.tex",
     r"\\genCompletenessCountE\}\{(\d+)\}", lambda: _notation("E"), 0.0),
    ("not-estimated count", "national", "gen_tab_completeness.tex",
     r"\\genCompletenessCountNE\}\{(\d+)\}", lambda: _notation("NE"), 0.0),
    ("included-elsewhere count", "national", "gen_tab_completeness.tex",
     r"\\genCompletenessCountIE\}\{(\d+)\}", lambda: _notation("IE"), 0.0),
    ("not-occurring count", "national", "gen_tab_completeness.tex",
     r"\\genCompletenessCountNO\}\{(\d+)\}", lambda: _notation("NO"), 0.0),
    # The related-work section repeats the completeness row total; it was the one printed
    # copy of this number that no claim reached, which only became visible when the IPCC 2006
    # migration moved every other copy from 136 to 138 and left it behind.
    ("related work completeness rows", "national", "02_related_work.tex",
     r"of the \\num\{(\d+)\} detailed categories tracked here",
     lambda: len(_rows("completeness.csv")), 0.0),
    ("completeness row total", "national", "09_completeness.tex",
     r"notation keys over \\num\{(\d+)\} category--gas combinations",
     lambda: len(_rows("completeness.csv")), 0.0),
    ("completeness row total in caption", "national", "09_completeness.tex",
     r"Completeness across \\num\{(\d+)\} category--gas combinations",
     lambda: len(_rows("completeness.csv")), 0.0),
    # The row count and the CODE count are different facts about the same table, and the
    # section prints both in one sentence: 136 category-gas combinations spanning 66 IPCC
    # codes. Only the row count was anchored, so the code count could drift alone - which it
    # would have on 2026-10-05, when closing the table's universe moved it 38 -> 66. Three of
    # the 69 distinct values in `code` are not IPCC codes at all - "(air)", "(x-sector)" and
    # "LU" - which is why the getter counts codes that begin with a digit rather than every
    # distinct value. Counting all 69 was a defect I raised against the printed 38 and had to
    # withdraw; the getter now records the distinction instead of leaving it to a reader.
    ("completeness IPCC code total", "national", "09_completeness.tex",
     r"combinations spanning \\num\{(\d+)\} IPCC codes",
     lambda: len({r["code"] for r in _rows("completeness.csv")
                  if r["code"][:1].isdigit()}), 0.0),
    ("completeness IPCC code total in caption", "national", "09_completeness.tex",
     r"combinations and \\num\{(\d+)\} IPCC codes",
     lambda: len({r["code"] for r in _rows("completeness.csv")
                  if r["code"][:1].isdigit()}), 0.0),
    # The benchmarks section repeats the count under a THIRD phrasing, which is how a
    # stale 87 shipped for a release while the two anchors above stayed green - the
    # sixteenth review caught it in a document-level audit. Same getter, third regex.
    ("completeness row total in benchmarks", "national", "10_benchmarks.tex",
     r"notation-key matrix over all \\num\{(\d+)\}\s+category--gas combinations",
     lambda: len(_rows("completeness.csv")), 0.0),
    # The transport fuel series grew a tenth year (FY2015-16, the rc20 recovery) and
    # the sector paper went on saying nine for two releases - the sixteenth review's
    # window audit caught it, along with a caption whose lower bound predated the file
    # it cites. The caption's first year is anchored to the file's own minimum.
    ("transport fuel series first year", "transport", "06_results.tex",
     r"Road-class petroleum emissions, FY(\d{4})--\d{2} to FY2024--25",
     lambda: min(int(r["fy_label"][2:6])
                 for r in _rows("transport_fuel_series.csv")), 0.0),
    ("EDGAR whole-inventory ratio", "national", "10_benchmarks.tex",
     r"All sectors & EDGAR & CY2024 & 514\.33 & [\d.]+ & ([\d.]+)",
     lambda: _bench("EDGAR", "NATIONAL"), 0.0),

    # ---- sector papers: claims are added here as each paper is written ----
    # ---- fugitives ----
    ("fugitives total", "fugitives", "06_results.tex",
     r"\\textbf\{Total\} & \\textbf\{[\d.]+\} & \\textbf\{[\d.]+\} & \\textbf\{[\d.]+\} &\s*\\textbf\{([\d.]+)\}",
     lambda: _cell("fugitives_totals_2024.csv", "category",
                   "Fugitive emissions from oil and gas", "co2e_Mt_AR5"), 0.0),
    ("fugitives lower-practice scenario", "fugitives", "06_results.tex",
     r"lower-practice configuration has a deterministic value of\s+\\SI\{([\d.]+)\}",
     lambda: _cell("fugitives_structural_scenarios_2024.csv", "scenario",
                   "lower_practices", "mt_co2e_ar5"), 0.0),
    ("fugitives MC lower", "fugitives", "06_results.tex",
     r"reference Monte Carlo has median\s*\\SI\{[\d.]+\}\{\\mega\\tonne\} and a 95\\% interval of\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}",
     lambda: _cell("fugitives_totals_2024.csv", "category",
                   "Fugitive emissions from oil and gas", "mc_p025"), 0.0),
    ("fugitives MC upper", "fugitives", "06_results.tex",
     r"reference Monte Carlo has median\s*\\SI\{[\d.]+\}\{\\mega\\tonne\} and a 95\\% interval of\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: _cell("fugitives_totals_2024.csv", "category",
                   "Fugitive emissions from oil and gas", "mc_p975"), 0.0),
    ("fugitives complete structural minimum", "fugitives", "06_results.tex",
     r"retaining all public-data segments span\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}",
     lambda: _min_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5",
                        coverage_complete_under_configuration="True"), 0.0),
    ("fugitives widest structural minimum", "fugitives", "06_results.tex",
     r"excluded expands the envelope to\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}",
     lambda: _min_where("fugitives_structural_factorial_2024.csv", "mt_co2e_ar5"), 0.0),
    ("fugitives common-GWP CRT", "fugitives", "06_results.tex",
     r"or\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} on the common GWP basis",
     lambda: _first_where("fugitives_unfccc_crt_common_metric.csv",
                          "common_ar5_fossil_ch4_mt_co2e", inventory_year="2022"), 0.0),
    ("fugitives gas distribution", "fugitives", "06_results.tex",
     r"Gas distribution & [\d.]+ & [\d.]+ & [\d.]+ & ([\d.]+)",
     lambda: _sum_prefix("fugitives_by_stream_2024.csv", "co2e_Mt_AR5",
                         "subitem", "Gas distribution "), 0.0),
    ("fugitives CRT total", "fugitives", "06_results.tex",
     r"Pakistan's 2022 CRT reports\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("fugitives_benchmark_crosswalk.csv", "benchmark_id",
                   "pakistan_crt_1b2_2022", "value_mt_co2e"), 0.0),
    ("fugitives historical upstream start", "fugitives", "06_results.tex",
     r"Upstream and processing emissions fall from\s*\\SI\{([\d.]+)\}",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2016",
                        reporting_group="upstream/processing"), 0.0),
    ("fugitives historical network end", "fugitives", "06_results.tex",
     r"network and LNG emissions rise\s*from \\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2024",
                        reporting_group="network/import"), 0.0),
    ("fugitives VIIRS national permutation", "fugitives", "../supplement.tex",
     r"VIIRS flare volume & national & 25 & 0\.230 & ([\d.]+)",
     lambda: _first_where("fugitives_observation_permutation_2024.csv",
                          "spearman_two_sided_empirical_p",
                          comparison="VIIRS named-field flare volume", null_model="national"),
     0.0001),
    # ---- residential ----
    ("residential total", "residential", "06_results.tex",
     r"\\textbf\{Total\} & & & \\textbf\{([\d.]+)\}",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential gas CO2", "residential", "06_results.tex",
     r"Natural gas & \\COtwo\{\}  & 15\\,963\.42 & ([\d.]+)",
     lambda: _sum_where("residential_by_stream_2024.csv", "co2e_Mt_AR5",
                        subitem="Natural gas CO2"), 0.0),
    ("residential firewood excluded", "residential", "06_results.tex",
     r"Firewood excluded entirely & ([\d.]+)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood excluded", "co2e_Mt_AR5"), 0.0),
    ("residential firewood high", "residential", "06_results.tex",
     r"Firewood quantity \$\+35\\%\$  & ([\d.]+)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood high", "co2e_Mt_AR5"), 0.0),
    ("residential PM2.5", "residential", "06b_air_pollutants.tex",
     r"\\PM\{\}                &  ([\d.]+) &",
     lambda: _sum_where("residential_air_pollutants_2024.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.05),
    ("residential nox", "residential", "06b_air_pollutants.tex",
     r"\\NOx\{\} \(as NO\$_2\$\)   &  ([\d.]+) &",
     lambda: _sum_where("residential_air_pollutants_2024.csv", "emissions_kt",
                        pollutant="NOx"), 0.05),
    ("residential black carbon", "residential", "06b_air_pollutants.tex",
     r"Black carbon         &   ([\d.]+) &",
     lambda: _sum_where("residential_air_pollutants_2024.csv", "emissions_kt",
                        pollutant="BC"), 0.05),
    ("residential variance", "residential", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of national Approach-1 variance",
     lambda: _keycat("Residential fuel combustion", "variance_share_pct_independent_approx"), 0.02),
    ("residential r_dung", "residential", "06_results.tex",
     r"r_\{\\text\{dung\}\} = ([\d.]+)",
     lambda: 1.0 / _cell("residential_hies_comparison_2024.csv", "fuel",
                         "dung_cake", "ratio_hies_over_engine"), 0.01),
    # BOTH columns captured. The rc3 versions matched the L column with a non-capturing
    # [\d.]+ and compared it to nothing, so tab:configs shipped a stale 29.228 / 617.3
    # beside a guarded S column -- a registration that looked like coverage and was not.
    ("residential config L co2e", "residential", "06_results.tex",
     r"Sector \\COe\{\}, AR5 \(Mt\)        & ([\d.]+) &",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "co2e_Mt_AR5"), 0.0),
    ("residential config S co2e", "residential", "06_results.tex",
     r"Sector \\COe\{\}, AR5 \(Mt\)        & [\d.]+ & ([\d.]+)",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "S",
                   "co2e_Mt_AR5"), 0.0),
    ("residential config L pm25", "residential", "06_results.tex",
     r"Primary \\PM\{\} \(kt\)             & ([\d.]+) &",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "pm25_kt"), 0.0),
    ("residential config S pm25", "residential", "06_results.tex",
     r"Primary \\PM\{\} \(kt\)             & [\d.]+ & ([\d.]+)",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "S",
                   "pm25_kt"), 0.0),
    ("residential config L pm ratio", "residential", "06_results.tex",
     r"Ratio vs road exhaust \\PM\{\}    & ([\d.]+)",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "pm_ratio_vs_road_exhaust"), 0.0),
    # The rc3 pattern hard-coded the stale upper end (29.2) as its own anchor, so
    # repairing the prose would have silently unhooked the claim -- the single worst
    # guard in the file. Both ends are captured now and neither appears in the pattern.
    ("residential abstract pm ratio S end", "residential", "00_abstract.tex",
     r"\\numrange\{([\d]+)\}\{[\d]+\} times road transport's",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "S",
                   "pm_ratio_vs_road_exhaust"), 0.0),
    ("residential abstract pm ratio L end", "residential", "00_abstract.tex",
     r"\\numrange\{[\d]+\}\{([\d]+)\} times road transport's",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "pm_ratio_vs_road_exhaust"), 0.0),
    ("residential results ratio swing L", "residential", "06_results.tex",
     r"road-transport ratio from \\num\{([\d]+)\} to \\num",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "pm_ratio_vs_road_exhaust"), 0.0),
    ("residential results ratio swing S", "residential", "06_results.tex",
     r"road-transport ratio from \\num\{[\d]+\} to \\num\{([\d]+)\}\. The configurations",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "S",
                   "pm_ratio_vs_road_exhaust"), 0.0),
    ("residential abstract S co2e", "residential", "00_abstract.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "S",
                   "co2e_Mt_AR5"), 0.01),
    ("residential abstract L co2e", "residential", "00_abstract.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L",
                   "co2e_Mt_AR5"), 0.01),
    ("residential january pm", "residential", "06_results.tex",
     r"January at \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of \\PM\{\} per month",
     lambda: _sum_where("residential_monthly_2024.csv", "pm25_kt",
                        month="202401"), 0.02),
    ("residential matched crt own", "residential", "05_validation.tex",
     r"the\nfiling reports \\SI\{17.73\}\{\\mega\\tonne\} against this inventory's "
     r"\\SI\{([\d.]+)\}\{\}",
     lambda: _cell("residential_official_comparison_2024.csv", "benchmark_id",
                   "crt2022", "own_Mt_co2e"), 0.01),
    # ---- power ----
    ("power grid", "power", "06_results.tex",
     r"Electricity and heat production & 1A1a & ([\d.]+)",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Electricity and heat production", "co2e_Mt_AR5"), 0.0),
    ("power captive", "power", "06_results.tex",
     r"Captive gas self-generation     & 1A2  &  ([\d.]+)",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Captive gas self-generation (1A2)", "co2e_Mt_AR5"), 0.0),
    ("power sector total", "power", "06_results.tex",
     r"\\textbf\{Total\}                  &      & \\textbf\{([\d.]+)\}",
     lambda: _cell("power_totals_fy2023_24.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("power lignite bound", "power", "06_results.tex",
     r"All coal lignite    & ([\d.]+)",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: all coal lignite", "co2e_Mt_AR5"), 0.0),
    ("power captive 900btu", "power", "06_results.tex",
     r"Captive at 900 Btu/scf & ([\d.]+)",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: captive gas at 900 Btu/scf", "co2e_Mt_AR5"), 0.0),
    ("power coal CO2", "power", "06_results.tex",
     r"Coal is \\SI\{([\d.]+)\}\{\\mega\\tonne\} of \\COtwo\{\}",
     lambda: _sum_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                        subitem="Coal CO2"), 0.0),
    ("power SO2 bound", "power", "06b_air_pollutants.tex",
     r"\\SOtwo\{\}        & ([\d.]+) ",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="SO2"), 0.05),
    # Level AND variance captured; the rc3 version skipped the level with [\d.]+ and the
    # printed 12.74 rode a pre-harmonisation denominator for two releases.
    ("power grid keycat level", "power", "06_results.tex",
     r"Electricity and heat production & ([\d.]+) &",
     lambda: _keycat("Electricity and heat production", "level_pct"), 0.02),
    ("power grid variance", "power", "06_results.tex",
     r"Electricity and heat production & [\d.]+ & ([\d.]+) ",
     lambda: _keycat("Electricity and heat production", "variance_share_pct_independent_approx"), 0.02),
    # Anchored to the power ledger over the national total, NOT to _keycat: the key
    # category screen is IPCC-category-based, so "Captive gas self-generation (1A2)"
    # resolves to the whole 1.A.2 row (3.27) via its source streams -- the wrong row,
    # silently. The paper's cell is the engine category's own share.
    ("power captive keycat level", "power", "06_results.tex",
     r"Captive gas self-generation \(1A2\)        &  ([\d.]+) &",
     lambda: 100.0 * _cell("power_totals_fy2023_24.csv", "category",
                           "Captive gas self-generation (1A2)", "co2e_Mt_AR5")
             / _sector("TOTAL"), 0.02),
    ("power captive share discussion", "power", "07_discussion.tex",
     r"Captive gas self-generation contributes \\SI\{([\d.]+)\}\{\\percent\} of national emissions",
     lambda: 100.0 * _cell("power_totals_fy2023_24.csv", "category",
                           "Captive gas self-generation (1A2)", "co2e_Mt_AR5")
             / _sector("TOTAL"), 0.02),
    # ---- ippu (registered at sweep inclusion; every claim reads a cement-audit or
    #      CRT-reproduction output, so the paper cannot restate the audit it describes) ----
    ("ippu misdated cement value", "ippu", "00_abstract.tex",
     r"audit shows that \\SI\{([\d.]+)\}\{\\mega\\tonne\} of cement previously attributed",
     lambda: _first_where("ippu_cement_activity_reconciliation.csv", "reported_value_kt",
                          correct_period="FY2021-22") / 1000.0, 0.0),
    ("ippu reference cement", "ippu", "00_abstract.tex",
     r"both report\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} for FY2023--24",
     lambda: _first_where("ippu_cement_activity_reconciliation.csv", "reported_value_kt",
                          correct_period="FY2023-24") / 1000.0, 0.0),
    ("ippu clinker exports", "ippu", "00_abstract.tex",
     r"Accounting for \\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s*clinker exports",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="exports") / 1000.0, 0.0),
    ("ippu clinker imports", "ippu", "00_abstract.tex",
     r"exports and \\SI\{([\d.]+)\}\{\\mega\\tonne\} of imports",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="imports for consumption") / 1000.0, 0.0),
    ("ippu inferred clinker", "ippu", "00_abstract.tex",
     r"gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of inferred domestic clinker",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="inferred domestic production")
             / 1000.0, 0.0),
    ("ippu producer clinker", "ippu", "00_abstract.tex",
     r"filings independently report \\SI\{([\d.]+)\}\{\\mega\\tonne\} of clinker",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "clinker_activity_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu bounded bank central", "ippu", "03_study_area_and_data.tex",
     r"whose 2024 reading of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: next(float(r["value_Mt_co2e"]) for r in csv.DictReader(
                      line for line in open(os.path.join(OUT,
                          "ippu_fgas_screening_2024.csv"), encoding="utf-8")
                      if not line.startswith("#"))
                  if r["configuration"] == "scope_plus_fgas_bounded_bank"), 0.0),
    ("ippu customs net imports", "ippu", "03_study_area_and_data.tex",
     r"net imports of \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of substance",
     lambda: (sum(float(r["net_kg"]) for r in
                  _data_rows("activity/ippu/hfc_trade_screening.csv")
                  if r["calendar_year"] == "2024" and r["flow"] == "import")
              - sum(float(r["net_kg"]) for r in
                    _data_rows("activity/ippu/hfc_trade_screening.csv")
                    if r["calendar_year"] == "2024" and r["flow"] == "export")) / 1e6,
     0.05),
    ("ippu fecto exact production", "ippu", "09_conclusion.tex",
     r"Fecto's\s*\\SI\{(\d+)\}\{\\tonne\}",
     lambda: _first_where("ippu_cement_producer_census_2024.csv",
                          "clinker_production_t",
                          company="Fecto Cement Limited"), 0.0),
    ("national diagnostic cement model", "national", "10_benchmarks.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}, while the 0.95-fraction",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "process_co2_mt",
                          method="Diagnostic model f=0.75"), 0.0),
    ("ippu official cement CO2", "ippu", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} in Pakistan's official cement inventory",
     lambda: _first_where("ippu_official_comparison.csv", "official_mt_co2e",
                          comparison="Cement process CO2"), 0.0),
    ("ippu study-area exports precise", "ippu", "03_study_area_and_data.tex",
     r"Exports total \\SI\{([\d.]+)\}\{\\mega\\tonne\} and imports",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="exports") / 1000.0, 0.0),
    ("ippu study-area imports precise", "ippu", "03_study_area_and_data.tex",
     r"and imports\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}, with all twelve months",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="imports for consumption") / 1000.0, 0.0),
    ("ippu calendar 2022 cement", "ippu", "03_study_area_and_data.tex",
     r"sum to \\SI\{([\d.]+)\}\{\\mega\\tonne\}\. Calendar-2022",
     lambda: _first_where("ippu_cement_matched_calendar_2022.csv", "cement_activity_kt",
                          calendar_year="2022", clinker_fraction="0.75") / 1000.0, 0.0),
    ("ippu calendar 2022 exports", "ippu", "03_study_area_and_data.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of exports and",
     lambda: _first_where("ippu_cement_matched_calendar_2022.csv", "clinker_exports_kt",
                          calendar_year="2022", clinker_fraction="0.75") / 1000.0, 0.0),
    ("ippu calendar 2022 imports", "ippu", "03_study_area_and_data.tex",
     r"exports and \\SI\{([\d.]+)\}\{\\mega\\tonne\} of imports",
     lambda: _first_where("ippu_cement_matched_calendar_2022.csv", "clinker_imports_kt",
                          calendar_year="2022", clinker_fraction="0.75") / 1000.0, 0.0),
    ("ippu producer clinker precise", "ippu", "03_study_area_and_data.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of clinker production",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "clinker_activity_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu soda ash QIM", "ippu", "03_study_area_and_data.tex",
     r"soda ash \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _first_where("ippu_activity_controls_2024.csv", "quantity",
                          product="Soda ash") / 1e6, 0.0),
    ("ippu billets QIM", "ippu", "03_study_area_and_data.tex",
     r"ingots \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _first_where("ippu_activity_controls_2024.csv", "quantity",
                          product="Billets and ingots") / 1e6, 0.0),
    ("ippu flying clinker", "ippu", "03_study_area_and_data.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} and \\SI\{[\d.]+\}\{\\mega\\tonne\}, respectively",
     lambda: _first_where("ippu_company_clinker_2024.csv", "clinker_production_t",
                          company="Flying Cement Company Limited") / 1e6, 0.0),
    ("ippu flying cement", "ippu", "03_study_area_and_data.tex",
     r"\\SI\{[\d.]+\}\{\\mega\\tonne\} and \\SI\{([\d.]+)\}\{\\mega\\tonne\}, respectively",
     lambda: _first_where("ippu_company_clinker_2024.csv", "cement_production_t",
                          company="Flying Cement Company Limited") / 1e6, 0.0),
    ("ippu results clinker content", "ippu", "06_results.tex",
     r"contains \\SI\{([\d.]+)\}\{\\mega\\tonne\} of clinker at a 0.75 fraction",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="clinker in cement") / 1000.0, 0.0),
    ("ippu results inferred precise", "ippu", "06_results.tex",
     r"gives \\SI\{([\d.]+)\}\{\\mega\\tonne\} of inferred domestic",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="inferred domestic production")
             / 1000.0, 0.0),
    ("ippu clinker EF", "ippu", "06_results.tex",
     r"At \\SI\{([\d.]+)\}\{\\tonne\\per\\tonne\}, process",
     lambda: _first_where("ippu_cement_crt_bridge_2022.csv", "factor_t_co2_per_t",
                          step="Independent trade-corrected f=0.75"), 0.0),
    ("ippu stock increase row", "ippu", "06_results.tex",
     r"Stock increase              &  ([\d.]+) &",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="stock increase") / 1000.0, 0.0),
    ("ippu producer co2", "ippu", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\} at the common factor",
     lambda: _first_where("ippu_cement_tier_comparison_2024.csv", "process_co2_mt",
                          method="Reference: producer census (rc30)"), 0.0),
    ("ippu MC median", "ippu", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} and a 95\\% interval",
     lambda: _first_where("ippu_cement_conditional_intervals_2024.csv", "p50_mt_co2",
                          configuration="reference (producer census)"), 0.0),
    ("ippu 2022 matched clinker", "ippu", "06_results.tex",
     r"gives \\SI\{([\d.]+)\}\{\\mega\\tonne\} of inferred clinker",
     lambda: _first_where("ippu_cement_matched_calendar_2022.csv",
                          "inferred_clinker_production_kt",
                          calendar_year="2022", clinker_fraction="0.75") / 1000.0, 0.0),
    ("ippu 2022 reference co2", "ippu", "06_results.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\} at the 0.75 fraction",
     lambda: _first_where("ippu_cement_matched_calendar_2022.csv", "co2_mt",
                          calendar_year="2022", clinker_fraction="0.75"), 0.0),
    ("ippu 2022 all-portland co2", "ippu", "06_results.tex",
     r"The 0.95 configuration gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("ippu_cement_matched_calendar_2022.csv", "co2_mt",
                          calendar_year="2022", clinker_fraction="0.95"), 0.0),
    ("ippu CRT activity", "ippu", "06_results.tex",
     r"CRT cement row reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} of activity",
     lambda: _first_where("ippu_cement_crt_bridge_2022.csv", "activity_mt",
                          step="CRT reported activity with default clinker EF"), 0.0),
    ("ippu CRT cement co2", "ippu", "06_results.tex",
     r"yielding \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\}",
     lambda: _first_where("ippu_official_comparison.csv", "official_mt_co2e",
                          comparison="Cement process CO2"), 0.0),
    ("ippu CRT whole total", "ippu", "06_results.tex",
     r"CRT reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} for all IPPU",
     lambda: _first_where("ippu_official_comparison.csv", "official_mt_co2e",
                          comparison="Pakistan CRT total IPPU"), 0.0),
    ("ippu CRT ammonia activity", "ippu", "06_results.tex",
     r"filing's \\SI\{([\d]+)\}\{\\kilo\\tonne\} of ammonia",
     lambda: float(next(r for r in _rows("ippu_ammonia_activity_reconciliation.csv")
                        if r["pathway"] == "official CRT")["nh3_kt_central"]), 0.5),
    ("ippu conclusion CRT total", "ippu", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\}, including",
     lambda: _first_where("ippu_official_comparison.csv", "official_mt_co2e",
                          comparison="Pakistan CRT total IPPU"), 0.0),
    ("ippu conclusion chemicals", "ippu", "09_conclusion.tex",
     r"including \\SI\{([\d.]+)\}\{\\mega\\tonne\} from chemicals",
     lambda: _first_where("ippu_unfccc_crt_background_2022.csv", "co2_kt",
                          category="2.B. Chemical industry") / 1000.0, 0.001),

    ("ippu fatima ammonia study-area", "ippu", "03_study_area_and_data.tex",
     r"reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} of calendar-2024 ammonia",
     lambda: _first_where("ippu_chemical_plant_activity.csv", "production_t",
                          operator="Fatima Fertilizer Company Limited",
                          product="Ammonia") / 1e6, 0.0),
    ("ippu fatima ammonia results", "ippu", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of output in 2024",
     lambda: _first_where("ippu_chemical_plant_activity.csv", "production_t",
                          operator="Fatima Fertilizer Company Limited",
                          product="Ammonia") / 1e6, 0.0),
    ("ippu feedstock share", "ippu", "03_study_area_and_data.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\}/\\SI\{[\d.]+\}\{\\percent\} in 2023--24",
     lambda: _annex28_share("2023-24", "Feed"), 0.05),
    ("ippu fuel share", "ippu", "03_study_area_and_data.tex",
     r"/\\SI\{([\d.]+)\}\{\\percent\} in 2023--24",
     lambda: _annex28_share("2023-24", "Fuel"), 0.05),
    # The later year is now quoted beside the reference year, so it needs its own pair of
    # anchors rather than riding the reference year's.
    ("ippu feedstock share 2024-25", "ippu", "03_study_area_and_data.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\}/\\SI\{[\d.]+\}\{\\percent\} in 2024--25",
     lambda: _annex28_share("2024-25", "Feed"), 0.05),
    ("ippu fuel share 2024-25", "ippu", "03_study_area_and_data.tex",
     r"/\\SI\{([\d.]+)\}\{\\percent\} in 2024--25",
     lambda: _annex28_share("2024-25", "Fuel"), 0.05),
    ("ippu fertiliser gas mmcfd", "ippu", "03_study_area_and_data.tex",
     r"reference year's total, \\SI\{([\d.]+)\}\{\} MMCFD",
     lambda: _annex28_mmcfd("2023-24"), 0.05),
    ("ippu fertiliser gas ogra", "ippu", "03_study_area_and_data.tex",
     r"independently published \\SI\{(\d+)\}\{\} to",
     lambda: _ogra_fertiliser_mmcfd(), 0.0),
    ("ippu fertiliser gas agreement", "ippu", "03_study_area_and_data.tex",
     r"to \\SI\{([\d.]+)\}\{\\percent\}\.", lambda: _gas_agreement_pct(), 0.1),
    ("ippu balance clinker row", "ippu", "06_results.tex",
     r"Clinker contained in cement & ([\d.]+) &",
     lambda: _first_where("ippu_cement_material_balance_2024.csv", "amount_kt",
                          material="clinker", flow="clinker in cement") / 1000.0, 0.0),
    ("ippu NFDC stoichiometry", "ippu", "06_results.tex",
     r"sits near \\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: float(next(r for r in _rows("ippu_ammonia_activity_reconciliation.csv")
                        if r["pathway"] == "product stoichiometry"
                        and r["period"] == "2024-25")["nh3_kt_central"]), 100.0),
    ("ippu plant census floor", "ippu", "06_results.tex",
     r"floor is \\SI\{([\d]+)\}\{\\kilo\\tonne\} from two of eight census plants",
     lambda: float(next(r for r in _rows("ippu_ammonia_activity_reconciliation.csv")
                        if r["pathway"] == "plant census")["nh3_kt_central"]), 0.5),

    ("aviation national figure abstract", "aviation", "00_abstract.tex",
     r"aggregate movement model's\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\}",
     lambda: _sector("aviation"), 0.0),
    ("aviation national figure conclusion", "aviation", "09_conclusion.tex",
     r"aggregate movement model's \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*\\COe\{\}",
     lambda: _sector("aviation"), 0.0),

    ("aviation abstract calibrated bridge", "aviation", "00_abstract.tex",
     r"partition gives \\SI\{([\d.]+)\}\{\\mega\\tonne\} of domestic \\COtwo\{\}",
     lambda: float(next(x for x in _rows("aviation_reconciliation_fy2023_24.csv")
                        if x["fiscal_year"] == "2023"
                        and x["scenario"] == "flight_fuel_weighted")
                   ["domestic_co2_Gg"]) / 1000.0, 0.0),
    ("aviation abstract gross commercial", "aviation", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\}, 0.8\\% below OECD",
     lambda: float(next(x for x in _rows("aviation_annual_component_comparison.csv")
                        if x["fiscal_year"] == "2023" and x["component"] == "combined")
                   ["ocac_co2_t"]) / 1e6, 0.0),
    ("aviation introduction sector figure", "aviation", "01_introduction.tex",
     r"aviation near \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} in FY2023--24",
     lambda: _sector("aviation"), 0.0),
    ("aviation appendix JP1 total FY23", "aviation", "10_appendix.tex",
     r"JP-1 totals of \\SI\{([\d]+)\}\{\\tonne\}",
     lambda: float(next(x for x in _rows("aviation_ocac_annual_summary.csv")
                        if x["fiscal_year"] == "2022")["tracked_aviation_jp1_t"]), 0.0),
    ("aviation appendix JP1 total FY24", "aviation", "10_appendix.tex",
     r"and\s*\\SI\{([\d]+)\}\{\\tonne\} in the two fiscal years",
     lambda: float(next(x for x in _rows("aviation_ocac_annual_summary.csv")
                        if x["fiscal_year"] == "2023")["tracked_aviation_jp1_t"]), 0.0),

    ("aviation appendix detour", "aviation", "10_appendix.tex",
     r"Route detour & ([\d.]+) &",
     lambda: _first_where("aviation_uncertainty_inputs_complete.csv", "central_value",
                          variable="Synthetic-route detour multiplier"), 0.0),
    ("fugitives bracket low", "fugitives", "00_abstract.tex",
     r"bracket calendar 2022 at\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_unfccc_crt_fiscal_bracket_2022.csv",
                          "reconstructed_common_mt_co2e",
                          adjacent_fiscal_period="FY2022-23"), 0.0),
    ("fugitives bracket high", "fugitives", "00_abstract.tex",
     r"bracket calendar 2022 at\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_unfccc_crt_fiscal_bracket_2022.csv",
                          "reconstructed_common_mt_co2e",
                          adjacent_fiscal_period="FY2021-22"), 0.0),

    ("fugitives ladder legacy common", "fugitives", "00_abstract.tex",
     r"give\s*\\SI\{([\d.]+)\}\{\} and \\SI\{[\d.]+\}\{\\mega\\tonne\} \\COe\{\}, respectively",
     lambda: _first_where("fugitives_method_ladder_2024.csv", "mt_co2e_ar5",
                          method="Legacy 2006 on common anchor activity"), 0.0),
    ("fugitives ladder refined common", "fugitives", "00_abstract.tex",
     r"give\s*\\SI\{[\d.]+\}\{\} and \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\}, respectively",
     lambda: _first_where("fugitives_method_ladder_2024.csv", "mt_co2e_ar5",
                          method="2019 Refinement on common production support"), 0.0),
    ("fugitives observation supply coverage", "fugitives", "00_abstract.tex",
     r"near fields with \\SI\{([\d.]+)\}\{\\percent\} of reported supply",
     lambda: _first_where("fugitives_observation_field_statistics_2024.csv",
                          "supply_coverage_by_any_named_observation_pct",
                          comparison="VIIRS named-field flare volume"), 0.0),
    ("fugitives 2019 production factor high", "fugitives", "02_related_work.tex",
     r"\\num\{([\d.]+)\} tonnes CH\$_4\$ per million m",
     lambda: float(next(r for r in _data_rows("fugitives_ipcc2019_factors.csv")
                        if r["factor_id"] == "gas_prod_high_ch4")["value"]), 0.0),
    ("fugitives 2019 production factor low", "fugitives", "02_related_work.tex",
     r"\\SI\{([\d.]+)\}\{\} for lower-emitting practices",
     lambda: float(next(r for r in _data_rows("fugitives_ipcc2019_factors.csv")
                        if r["factor_id"] == "gas_prod_low_ch4")["value"]), 0.0),
    ("fugitives oil activity", "fugitives", "03_study_area_and_data.tex",
     r"\\num\{([\d.]+)\} thousand m\$\^3\$ of oil",
     lambda: _first_where("fugitives_uncertainty_inputs_2024.csv", "central_value",
                          input_id="activity:oil_onshore_production"), 0.0),
    ("fugitives gas activity", "fugitives", "03_study_area_and_data.tex",
     r"\\num\{([\d.]+)\} million m\$\^3\$ of gas",
     lambda: _first_where("fugitives_uncertainty_inputs_2024.csv", "central_value",
                          input_id="activity:gas_onshore_production"), 0.0),
    ("fugitives domestic customers", "fugitives", "03_study_area_and_data.tex",
     r"serve \\num\{([\d]+)\} domestic",
     lambda: _first_where("fugitives_uncertainty_inputs_2024.csv", "central_value",
                          input_id="activity:post_meter_appliances"), 0.0),
    ("fugitives sales control", "fugitives", "03_study_area_and_data.tex",
     r"\\num\{([\d.]+)\} MMCF d\$\^\{-1\}\$ of utility and independent-system sales",
     lambda: _first_where("fugitives_gas_flow_balance_2022_2024.csv",
                          "categorized_consumption_mmcfd", fiscal_year="2024"), 0.0),
    ("fugitives transmission length start", "fugitives", "03_study_area_and_data.tex",
     r"transmission length rises from\s*\\SI\{([\d.]+)\}\{\\kilo\\metre\}",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "fugitives",
                        "infrastructure_history_2015_21.csv"))
                        if r["fiscal_year"] == "2016")["transmission_length_km"]), 0.0),
    ("fugitives transmission length end", "fugitives", "03_study_area_and_data.tex",
     r"transmission length rises from\s*\\SI\{[\d.]+\}\{\\kilo\\metre\} to "
     r"\\SI\{([\d.]+)\}\{\\kilo\\metre\}",
     lambda: _first_where("fugitives_uncertainty_inputs_2024.csv", "central_value",
                          input_id="activity:gas_transmission_pipeline"), 0.0),
    ("fugitives distribution length start", "fugitives", "03_study_area_and_data.tex",
     r"distribution length from\s*\\SI\{([\d]+)\}\{\\kilo\\metre\}",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "fugitives",
                        "infrastructure_history_2015_21.csv"))
                        if r["fiscal_year"] == "2016")["distribution_length_km"]), 0.0),
    ("fugitives distribution length end", "fugitives", "03_study_area_and_data.tex",
     r"distribution length from\s*\\SI\{[\d]+\}\{\\kilo\\metre\} to\s*"
     r"\\SI\{([\d]+)\}\{\\kilo\\metre\}",
     lambda: _first_where("fugitives_uncertainty_inputs_2024.csv", "central_value",
                          input_id="activity:gas_distribution_pipeline"), 0.0),
    ("fugitives customers start", "fugitives", "03_study_area_and_data.tex",
     r"domestic customers from \\num\{([\d]+)\} to",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "fugitives",
                        "infrastructure_history_2015_21.csv"))
                        if r["fiscal_year"] == "2016")["domestic_customers"]), 0.0),
    ("fugitives polythene evidence", "fugitives", "03_study_area_and_data.tex",
     r"identifies \\SI\{([\d]+)\}\{\\kilo\\metre\} of polythene",
     lambda: _first_where("fugitives_distribution_practice_evidence_2024.csv",
                          "evidence_value", evidence_id="ssgcl_polythene_pipe"), 0.0),
    ("fugitives leak survey evidence", "fugitives", "03_study_area_and_data.tex",
     r"surveyed \\SI\{([\d]+)\}\{\\kilo\\metre\} of underground network",
     lambda: _first_where("fugitives_distribution_practice_evidence_2024.csv",
                          "evidence_value",
                          evidence_id="sngpl_underground_leak_survey"), 0.0),
    ("fugitives refinery product output", "fugitives", "03_study_area_and_data.tex",
     r"OGRA reports \\num\{([\d.]+)\} million tonnes of refinery product",
     lambda: 0.85 * _first_where("fugitives_uncertainty_inputs_2024.csv",
                                 "central_value",
                                 input_id="activity:oil_refining") / 1000.0, 0.0),
    ("fugitives post-meter throughput", "fugitives", "03_study_area_and_data.tex",
     r"together\s*\\num\{([\d.]+)\} MMCF d",
     lambda: _sum_where("fugitives_post_meter_end_use_2024.csv", "throughput_mmcfd",
                        fiscal_year="2024", include_in_ipcc_post_meter="yes"), 0.0),
    # rc12: the data-section sentence used to equate these two quantities ("or"),
    # then quote their 0.042 difference two lines later. They are named apart now
    # and anchored to DIFFERENT audit columns - the defect was precisely that the
    # old single sentence carried two anchors resolving to two different numbers.
    ("fugitives post-meter class-sum conversion", "fugitives",
     "03_study_area_and_data.tex",
     r"converts to \\num\{([\d.]+)\} million m\$\^3\$ yr",
     lambda: _first_where("fugitives_post_meter_end_use_2024.csv",
                          "included_activity_control_million_m3", include_in_ipcc_post_meter="yes"), 0.0),
    ("fugitives post-meter registered activity", "fugitives",
     "03_study_area_and_data.tex",
     # rc67: the sentence states the registered six-class base first ("before the
     # fertilizer feedstock is withheld") and the activity the factor is charged on
     # second; this row is the first, from the end-use audit's own column, and
     # "fugitives post-meter activity after feedstock" is the second.
     r"leak factor rides is \\num\{([\d.]+)\} million m\$\^3\$ yr",
     lambda: _first_where("fugitives_post_meter_end_use_2024.csv",
                          "registered_activity_million_m3",
                          include_in_ipcc_post_meter="yes"), 0.0),
    ("fugitives flare sites count", "fugitives", "03_study_area_and_data.tex",
     r"\\num\{([\d]+)\} sites labelled Pakistan",
     lambda: float(len(_rows("fugitives_viirs_flare_sites.csv"))), 0.0),
    ("fugitives MARS sources", "fugitives", "03_study_area_and_data.tex",
     r"contains\s*\\num\{([\d]+)\} oil-and-gas sources",
     lambda: float(_rows("fugitives_mars_summary.csv")[0]["oil_gas_sources"]), 0.0),
    ("fugitives MARS plumes", "fugitives", "03_study_area_and_data.tex",
     r"and \\num\{([\d]+)\} plume detections",
     lambda: float(_rows("fugitives_mars_summary.csv")[0]["oil_gas_plumes"]), 0.0),
    ("fugitives field reconciliation", "fugitives", "03_study_area_and_data.tex",
     r"reconcile to \\num\{([\d.]+)\} MMCF d",
     lambda: _first_where("fugitives_qa_2024.csv", "actual",
                          check="field supply reconciliation"), 0.0),
    ("fugitives field reconciliation gap", "fugitives", "03_study_area_and_data.tex",
     r"within\s*\\num\{([\d.]+)\} MMCF d",
     lambda: abs(_first_where("fugitives_gas_flow_balance_2022_2024.csv",
                              "indigenous_marketable_supply_mmcfd", fiscal_year="2024")
                 - _first_where("fugitives_qa_2024.csv", "actual",
                                check="field supply reconciliation")), 0.0),
    ("fugitives sour share", "fugitives", "04_methods.tex",
     r"2019 default\s*\\SI\{([\d]+)\}\{\\percent\} share",
     lambda: 100.0 * _first_where("fugitives_conditional_intervals_2024.csv",
                                  "sour_fraction", configuration="reference"), 0.0),
    ("fugitives post-meter factor", "fugitives", "04_methods.tex",
     r"factor is \\SI\{([\d.]+)\}\{\\tonne\} CH",
     lambda: _first_where("fugitives_post_meter_factor_lineage_2024.csv",
                          "registered_t_CH4_per_million_m3",
                          factor_id="post_meter_industrial_ch4"), 0.0),
    ("fugitives lineage source value", "fugitives", "04_methods.tex",
     r"Revised 1996 value of \\SI\{([\d]+)\}\{\\kilogram\\per\\peta\\joule\}",
     lambda: _first_where("fugitives_post_meter_factor_lineage_2024.csv",
                          "source_value_kg_per_PJ",
                          factor_id="post_meter_industrial_ch4"), 0.0),
    ("fugitives lineage conversion", "fugitives", "04_methods.tex",
     r"\\SI\{([\d]+)\}\{\\mega\\joule\\per\\cubic\\metre\} gas conversion",
     lambda: _first_where("fugitives_post_meter_factor_lineage_2024.csv",
                          "energy_conversion_MJ_per_m3",
                          factor_id="post_meter_industrial_ch4"), 0.0),
    ("fugitives ladder benchmark", "fugitives", "06_results.tex",
     r"legacy 2006 calculation is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_method_ladder_2024.csv", "mt_co2e_ar5",
                          method="Legacy 2006 published benchmark"), 0.0),
    ("fugitives ladder upstream completion", "fugitives", "06_results.tex",
     r"gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}; the full public-data",
     lambda: _first_where("fugitives_method_ladder_2024.csv", "mt_co2e_ar5",
                          method="2019 upstream completion"), 0.0),
    ("fugitives distribution structural effect", "fugitives", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}\. Its selection requires",
     lambda: _first_where("fugitives_data_priorities_2024.csv",
                          "absolute_effect_mt_co2e",
                          scenario="lower_distribution_only"), 0.0),
    ("fugitives post-meter half effect", "fugitives", "06_results.tex",
     r"reduces the total by \\SI\{([\d.]+)\}\{\} or",
     lambda: _first_where("fugitives_data_priorities_2024.csv",
                          "absolute_effect_mt_co2e",
                          scenario="post_meter_half_factor"), 0.0),
    ("fugitives MC median", "fugitives", "06_results.tex",
     r"reference Monte Carlo has median\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p50_mt_co2e_ar5", configuration="reference"), 0.0),
    ("fugitives lower practices p025", "fugitives", "06_results.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\} for lower practices",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p025_mt_co2e_ar5", configuration="lower_practices"), 0.0),
    ("fugitives lower practices p975", "fugitives", "06_results.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\} for lower practices",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p975_mt_co2e_ar5", configuration="lower_practices"), 0.0),
    ("fugitives no post-meter p025", "fugitives", "06_results.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\} without industrial",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p025_mt_co2e_ar5",
                          configuration="no_post_meter_industrial"), 0.0),
    ("fugitives no post-meter p975", "fugitives", "06_results.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\} without industrial",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p975_mt_co2e_ar5",
                          configuration="no_post_meter_industrial"), 0.0),
    ("fugitives minimum coverage p025", "fugitives", "06_results.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} for the minimum-coverage",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p025_mt_co2e_ar5",
                          configuration="minimum_coverage_combined"), 0.0),
    ("fugitives minimum coverage p975", "fugitives", "06_results.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} for the minimum-coverage",
     lambda: _first_where("fugitives_conditional_intervals_2024.csv",
                          "mc_p975_mt_co2e_ar5",
                          configuration="minimum_coverage_combined"), 0.0),
    ("fugitives sensitivity top", "fugitives", "06_results.tex",
     r"contribute \\SI\{([\d.]+)\}\{\\percent\} and",
     lambda: _first_where("fugitives_uncertainty_attribution_2024.csv",
                          "normalized_squared_spearman_pct",
                          input_group="factor:gas_distribution_high_km"), 0.0),
    ("fugitives sensitivity second", "fugitives", "06_results.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\percent\} of normalized squared rank",
     lambda: _first_where("fugitives_uncertainty_attribution_2024.csv",
                          "normalized_squared_spearman_pct",
                          input_group="factor:post_meter_industrial"), 0.0),
    ("fugitives sensitivity third bound", "fugitives", "06_results.tex",
     r"individually contribute less than \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: sorted(float(r["normalized_squared_spearman_pct"])
                    for r in _rows("fugitives_uncertainty_attribution_2024.csv"))[-3],
     0.0),
    ("fugitives timeseries start", "fugitives", "06_results.tex",
     r"ranges from \\SI\{([\d.]+)\}\{\\mega\\tonne\} in FY2015--16",
     lambda: _first_where("fugitives_infrastructure_timeseries_2016_2024.csv",
                          "co2e_Mt_AR5", fiscal_year="2016",
                          configuration="reference"), 0.0),
    ("fugitives timeseries peak", "fugitives", "06_results.tex",
     r"peak of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} in FY2018--19",
     lambda: _first_where("fugitives_infrastructure_timeseries_2016_2024.csv",
                          "co2e_Mt_AR5", fiscal_year="2019",
                          configuration="reference"), 0.0),
    ("fugitives upstream group start", "fugitives", "06_results.tex",
     r"fall from\s*\\SI\{([\d.]+)\}\{\} to",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2016",
                        reporting_group="upstream/processing",
                        configuration="reference"), 0.0),
    ("fugitives upstream group end", "fugitives", "06_results.tex",
     r"fall from\s*\\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2024",
                        reporting_group="upstream/processing",
                        configuration="reference"), 0.0),
    ("fugitives network group start", "fugitives", "06_results.tex",
     r"network and LNG emissions rise\s*from \\SI\{([\d.]+)\}\{\} to",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2016",
                        reporting_group="network/import",
                        configuration="reference"), 0.0),
    ("fugitives network group end", "fugitives", "06_results.tex",
     r"rise\s*from \\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2024",
                        reporting_group="network/import",
                        configuration="reference"), 0.0),
    ("fugitives post-meter group start", "fugitives", "06_results.tex",
     r"nearly\s*constant at \\SI\{([\d.]+)\}\{\} and",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2016",
                        reporting_group="post-meter",
                        configuration="reference"), 0.0),
    ("fugitives post-meter group end", "fugitives", "06_results.tex",
     r"nearly\s*constant at \\SI\{[\d.]+\}\{\} and \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                        "co2e_Mt_AR5", fiscal_year="2024",
                        reporting_group="post-meter",
                        configuration="reference"), 0.0),
    ("fugitives upstream balance min", "fugitives", "06_results.tex",
     r"supply by \\SI\{([\d.]+)\}\{\\percent\}--",
     lambda: _min_where("fugitives_gas_flow_balance_2022_2024.csv",
                        "upstream_difference_pct_gross"), 0.0),
    ("fugitives upstream balance max", "fugitives", "06_results.tex",
     r"--\s*\\SI\{([\d.]+)\}\{\\percent\} across FY2021--22",
     lambda: _max_where("fugitives_gas_flow_balance_2022_2024.csv",
                        "upstream_difference_pct_gross"), 0.0),
    ("fugitives downstream residual low", "fugitives", "06_results.tex",
     r"from \$-\\SI\{([\d.]+)\}\{\\percent\}\$ to",
     lambda: abs(_min_where("fugitives_gas_flow_balance_2022_2024.csv",
                            "downstream_statistical_discrepancy_pct_supply")), 0.0),
    ("fugitives downstream residual high", "fugitives", "06_results.tex",
     r"to\s*\$\+\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _max_where("fugitives_gas_flow_balance_2022_2024.csv",
                        "downstream_statistical_discrepancy_pct_supply"), 0.0),
    ("fugitives network methane", "fugitives", "06_results.tex",
     r"emissions are \\SI\{([\d.]+)\}\{\\giga\\gram\} CH",
     lambda: _first_where("fugitives_ufg_network_compatibility_2024.csv",
                          "network_ch4_Gg", scenario="reference"), 0.0),
    ("fugitives UFG share reference", "fugitives", "06_results.tex",
     r"equivalent to \\SI\{([\d.]+)\}\{\\percent\} of reported UFG methane",
     lambda: _first_where("fugitives_ufg_network_compatibility_2024.csv",
                          "ufg_physical_fraction_required_pct",
                          scenario="reference"), 0.0),
    ("fugitives UFG share lower", "fugitives", "06_results.tex",
     r"estimates require\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _first_where("fugitives_ufg_network_compatibility_2024.csv",
                          "ufg_physical_fraction_required_pct",
                          scenario="lower_practices"), 0.0),
    ("fugitives UFG share throughput", "fugitives", "06_results.tex",
     r"cases require \\SI\{([\d.]+)\}\{\\percent\} and",
     lambda: _first_where("fugitives_ufg_network_compatibility_2024.csv",
                          "ufg_physical_fraction_required_pct",
                          scenario="throughput"), 0.0),
    ("fugitives UFG share lower throughput", "fugitives", "06_results.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\percent\}\. Both practice classes",
     lambda: _first_where("fugitives_ufg_network_compatibility_2024.csv",
                          "ufg_physical_fraction_required_pct",
                          scenario="lower_throughput"), 0.0),
    ("fugitives CRT ratio high", "fugitives", "06_results.tex",
     r"reconstructions are \\num\{([\d.]+)\} and",
     lambda: _first_where("fugitives_unfccc_crt_fiscal_bracket_2022.csv",
                          "ratio_to_official_common_metric",
                          adjacent_fiscal_period="FY2021-22"), 0.0),
    ("fugitives CRT ratio low", "fugitives", "06_results.tex",
     r"and \\num\{([\d.]+)\} times this value",
     lambda: _first_where("fugitives_unfccc_crt_fiscal_bracket_2022.csv",
                          "ratio_to_official_common_metric",
                          adjacent_fiscal_period="FY2022-23"), 0.0),
    ("fugitives fiscal choice sensitivity", "fugitives", "06_results.tex",
     r"changes the\s*reconstruction by about \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * (1.0 - _first_where(
         "fugitives_unfccc_crt_fiscal_bracket_2022.csv",
         "reconstructed_common_mt_co2e", adjacent_fiscal_period="FY2022-23")
         / _first_where("fugitives_unfccc_crt_fiscal_bracket_2022.csv",
                        "reconstructed_common_mt_co2e",
                        adjacent_fiscal_period="FY2021-22")), 0.0),
    ("fugitives flare volume 2012", "fugitives", "06_results.tex",
     r"declines from \\num\{([\d.]+)\} billion m\$\^3\$ in 2012",
     lambda: _first_where("fugitives_viirs_flaring_2012_2025.csv",
                          "flare_volume_bcm", year="2012"), 0.0),
    ("fugitives flare volume 2024", "fugitives", "06_results.tex",
     r"to\s*\\SI\{([\d.]+)\}\{\} in 2024",
     lambda: _first_where("fugitives_viirs_flaring_2012_2025.csv",
                          "flare_volume_bcm", year="2024"), 0.0),
    ("fugitives VIIRS rho", "fugitives", "06_results.tex",
     r"Spearman \$\\rho=\\num\{([\d.]+)\}\$ with VIIRS",
     lambda: _first_where("fugitives_observation_field_statistics_2024.csv",
                          "spearman_rho_with_ties",
                          comparison="VIIRS named-field flare volume"), 0.0),
    ("fugitives MARS rho", "fugitives", "06_results.tex",
     r"\$\\rho=\\num\{([\d.]+)\}\$ with MARS",
     lambda: _first_where("fugitives_observation_field_statistics_2024.csv",
                          "spearman_rho_with_ties",
                          comparison="MARS sources assigned by nearest flare"), 0.001),
    ("fugitives MARS rank p bound", "fugitives", "06_results.tex",
     r"statistics at\s*\$p\\leq\\num\{([\d.]+)\}\$",
     lambda: max(float(r["spearman_two_sided_empirical_p"])
                 for r in _rows("fugitives_observation_permutation_2024.csv")
                 if r["comparison"].startswith("MARS")), 0.0),
    ("fugitives overlap p low", "fugitives", "06_results.tex",
     r"overlaps at\s*\$p=\\num\{([\d.]+)\}\$",
     lambda: min(float(r["top10_overlap_upper_tail_empirical_p"])
                 for r in _rows("fugitives_observation_permutation_2024.csv")
                 if r["comparison"].startswith("MARS")), 0.0),
    ("fugitives overlap p high", "fugitives", "06_results.tex",
     r"\$p=\\num\{[\d.]+\}\$--\$\\num\{([\d.]+)\}\$",
     lambda: max(float(r["top10_overlap_upper_tail_empirical_p"])
                 for r in _rows("fugitives_observation_permutation_2024.csv")
                 if r["comparison"].startswith("MARS")), 0.0),
    ("fugitives provincial Sindh", "fugitives", "06_results.tex",
     r"provincial inventory is \\SI\{([\d.]+)\}\{\\mega\\tonne\} in Sindh",
     lambda: _first_where("fugitives_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Sindh"), 0.0),
    ("fugitives provincial Punjab", "fugitives", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\} in Punjab",
     lambda: _first_where("fugitives_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Punjab"), 0.0),
    ("fugitives provincial KP", "fugitives", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\} in Khyber",
     lambda: _first_where("fugitives_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Khyber Pakhtunkhwa"), 0.0),
    ("fugitives provincial Balochistan", "fugitives", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\} in Balochistan",
     lambda: _first_where("fugitives_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Balochistan"), 0.0),
    ("fugitives provincial Other", "fugitives", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\} in Other",
     lambda: _first_where("fugitives_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Other"), 0.0),
    ("fugitives top-two sensitivity", "fugitives", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the reference-configuration rank sensitivity",
     lambda: sum(sorted(float(r["normalized_squared_spearman_pct"])
                        for r in _rows(
                            "fugitives_uncertainty_attribution_2024.csv"))[-2:]),
     0.0),

    ("waste panel districts", "waste", "03_study_area_and_data.tex",
     r"panel covers \\num\{([\d]+)\} district units",
     lambda: float(len({(r["province"], r["district"])
                        for r in _data_rows(os.path.join("activity", "waste",
                                            "population_district.csv"))
                        if r["year"] == "2024"})), 0.0),
    ("waste panel urban", "waste", "03_study_area_and_data.tex",
     r"\\SI\{([\d]+)\}\{\} million urban",
     lambda: sum(float(r["pop_urban"])
                 for r in _data_rows(os.path.join("activity", "waste",
                                     "population_district.csv"))
                 if r["year"] == "2024") / 1e6, 0.0),
    ("waste panel rural", "waste", "03_study_area_and_data.tex",
     r"\\SI\{([\d]+)\}\{\} million rural",
     lambda: sum(float(r["pop_rural"])
                 for r in _data_rows(os.path.join("activity", "waste",
                                     "population_district.csv"))
                 if r["year"] == "2024") / 1e6, 0.0),
    ("waste panel total", "waste", "03_study_area_and_data.tex",
     r"\\SI\{([\d]+)\}\{\} million in total",
     lambda: sum(float(r["pop_total"])
                 for r in _data_rows(os.path.join("activity", "waste",
                                     "population_district.csv"))
                 if r["year"] == "2024") / 1e6, 0.0),
    ("waste pre-2000 share", "waste", "04_methods.tex",
     r"contribute \\SI\{([\d]+)\}\{\\percent\} of today's landfill methane",
     lambda: 100.0 * (1.0 - _cell("waste_totals_2024.csv", "category",
                                  "Sensitivity: disposal without spin-up",
                                  "co2e_Mt_AR5")
                      / _cell("waste_totals_2024.csv", "category",
                              "Solid waste disposal", "co2e_Mt_AR5")), 0.1),
    ("waste biogenic memo", "waste", "04_methods.tex",
     r"memo item at \\SI\{([\d]+)\}\{\\giga\\gram\} \\COtwo\{\}",
     lambda: float(re.search(
         r"([\d.]+) Gg CO2",
         next(r for r in _rows("waste_totals_2024.csv")
              if r["category"].startswith("Biogenic CO2"))["note"]).group(1)), 0.0),
    ("waste wastewater national share", "waste", "08_limitations.tex",
     r"alone is \\SI\{([\d.]+)\}\{\\percent\} of the national inventory",
     lambda: 100.0 * _cell("waste_totals_2024.csv", "category",
                           "Domestic wastewater", "co2e_Mt_AR5")
             / _sector("TOTAL"), 0.0),
    ("waste stream band low", "waste", "06_results.tex",
     r"between \\SI\{([\d]+)\}\{\\percent\} and \\SI\{[\d]+\}\{\\percent\}",
     lambda: _min_where("waste_by_stream_2024.csv", "uncert_pct"), 0.0),
    ("waste stream band high", "waste", "06_results.tex",
     r"the\s*sixth, wastewater N\$_2\$O, declares \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _max_where("waste_by_stream_2024.csv", "uncert_pct"), 0.0),
    ("waste methane-only river row", "waste", "10_appendix.tex",
     r"river-discharge row's \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_2024.csv", "category",
                   "Sensitivity: wastewater on the river-discharge MCF "
                   "(category total)", "co2e_Mt_AR5")
             - _first_where("waste_by_stream_2024.csv", "co2e_Mt_AR5",
                            subitem="Domestic wastewater N2O"), 0.0),
    ("waste wrong lever", "waste", "10_appendix.tex",
     r"computed a lever of \\num\{([\d.]+)\} where",
     lambda: _cell("waste_totals_2024.csv", "category", "Domestic wastewater",
                   "co2e_Mt_AR5")
             / (_cell("waste_totals_2024.csv", "category",
                      "Sensitivity: wastewater on the river-discharge MCF "
                      "(category total)", "co2e_Mt_AR5")
                - _first_where("waste_by_stream_2024.csv", "co2e_Mt_AR5",
                               subitem="Domestic wastewater N2O")), 0.0),
    ("waste symmetric lower bound", "waste", "S1_uncertainty.tex",
     r"infer a lower bound near\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_2024.csv", "category", "Solid waste disposal",
                   "co2e_Mt_AR5")
             * (1.0 - _first_where("waste_uncertainty_2024.csv",
                                   "approach1_pct_independent",
                                   category="Solid waste disposal") / 100.0), 0.0),

    ("railways sulfur ladder low ppm", "railways", "00_abstract.tex",
     r"ladder spanning \\SIrange\{([\d]+)\}\{[\d]+\}\{ppm\}",
     lambda: _first_where("railways_air_sulfur_cases_2024.csv", "diesel_sulfur_ppm",
                          sulfur_case="euro5_import_spec"), 0.0),
    ("railways sulfur ladder high ppm", "railways", "00_abstract.tex",
     r"ladder spanning \\SIrange\{[\d]+\}\{([\d]+)\}\{ppm\}",
     lambda: _first_where("railways_air_sulfur_cases_2024.csv", "diesel_sulfur_ppm",
                          sulfur_case="historical_1.0pct"), 0.0),
    ("railways network coverage pct", "railways", "00_abstract.tex",
     r"rail network---\\SI\{([\d]+)\}\{\\percent\}",
     lambda: 100.0 * _cell("railways_network_audit_2024.csv", "item", "active_total",
                           "km")
             / _cell("railways_network_audit_2024.csv", "item", "route_km_yearbook",
                     "km"), 0.0),
    # rc62: furnace oil's own Punjab share, READ from the committed vector rather than pinned -
    # it is the live number the product split produced and must move if the area pages do.
    ("industrial furnace oil Punjab share", "national", "06_results.tex",
     r"own \\num\{([\d.]+)\}---while industrial diesel",
     lambda: round(_province_share("industry_furnace_oil", "Punjab"), 3), 0.0),
    ("railways route Punjab share", "railways", "00_abstract.tex",
     r"Punjab\s*\\SI\{([\d]+)\}\{\\percent\}, where a freight-loadings proxy",
     lambda: 100.0 * _first_where("railways_route_province_shares_2024.csv", "share",
                                  province="Punjab"), 0.0),
    ("railways BUR figure", "railways", "00_abstract.tex",
     r"Report's \\SI\{([\d.]+)\}\{\\mega\\tonne\} for FY2017--18",
     lambda: _first_where("railways_official_comparison_2024.csv", "official_Mt_co2e",
                          benchmark_id="bur1"), 0.0),
    ("railways EDGAR fugitives aside", "railways", "02_related_work.tex",
     r"factor of \\num\{([\d.]+)\} against EDGAR",
     lambda: _first_where("national_benchmark_comparison.csv",
                          "ratio_engine_over_benchmark", source="EDGAR",
                          engine_category="Fugitive emissions from oil and gas"), 0.0),
    ("railways electric peak quinquennium", "railways", "03_study_area_and_data.tex",
     r"quinquennium \(\\SI\{([\d.]+)\}\{\\giga\\watt\\hour\} per year",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "railways",
                        "fuel_history_quinquennial.csv"))
                        if r["period"] == "1985-90")["electric_kwh_thousand"]) / 1000.0,
     0.0),
    ("railways electric last quinquennium", "railways", "03_study_area_and_data.tex",
     r"declines through 2005--2010\s*\(\\SI\{([\d.]+)\}\{\\giga\\watt\\hour\}\)",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "railways",
                        "fuel_history_quinquennial.csv"))
                        if r["period"] == "2005-10")["electric_kwh_thousand"]) / 1000.0,
     0.0),
    ("railways coaching train-km", "railways", "03_study_area_and_data.tex",
     r"reports \\num\{([\d]+)\} thousand passenger, mixed and other coaching",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "railways",
                        "service_statistics.csv"))
                        if r["fiscal_year"] == "2024"
                        and r["service"] == "line_haul_passenger")["value"]), 0.0),
    ("railways freight train-km", "railways", "03_study_area_and_data.tex",
     r"train-kilometres and \\num\{([\d]+)\} thousand freight",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "railways",
                        "service_statistics.csv"))
                        if r["fiscal_year"] == "2024"
                        and r["service"] == "line_haul_freight")["value"]), 0.0),
    ("railways total train-km", "railways", "03_study_area_and_data.tex",
     r"\\num\{([\d]+)\} thousand in total",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "railways",
                        "traffic.csv"))
                        if r["fiscal_year"] == "2024"
                        and r["metric"] == "total_train_km")["value"]), 0.0),
    ("railways HSD density", "railways", "04_methods.tex",
     r"midpoint \\SI\{([\d.]+)\}\{\\kilo\\gram\\per\\litre\}",
     lambda: float(next(r for r in _data_rows("railways_params.csv")
                        if r["param"] == "hsd_density_kg_per_l")["value"]), 0.0),
    ("railways yearbook route km", "railways", "04_methods.tex",
     r"Year Book's \\num\{([\d]+)\} route-kilometres",
     lambda: _cell("railways_network_audit_2024.csv", "item", "route_km_yearbook",
                   "km"), 0.0),
    ("railways road N2O understatement", "railways", "04b_emission_factors.tex",
     r"understate railway \\NtwoO\{\} by \\SI\{([\d]+)\}\{\\percent\}",
     lambda: 100.0 * (1.0 - 3.9 / 28.6), 0.0),
    ("railways road-table sector gap pct", "railways", "04b_emission_factors.tex",
     r"sector total by about \\SI\{([\d]+)\}\{\\percent\}",
     lambda: 100.0 * (1.0 - _cell("railways_totals_2024.csv", "category",
                                  "Diagnostic: N2O on the road factor", "co2e_Mt_AR5")
                      / _cell("railways_totals_2024.csv", "category",
                              "Module total (both categories)",
                              "co2e_Mt_AR5")), 0.0),
    ("railways road-table diagnostic", "railways", "04b_emission_factors.tex",
     r"from \\SI\{0.394\}\{\} to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Diagnostic: N2O on the road factor", "co2e_Mt_AR5"), 0.0),
    ("railways CRT implied CO2 factor", "railways", "04b_emission_factors.tex",
     r"\\COtwo\{\} at \\num\{([\d.]+)\} t/TJ",
     lambda: _first_where("railways_unfccc_crt_cell_audit_2024.csv", "value",
                          row_label="Liquid fuels", field="ief_co2_t_per_TJ"), 0.0),
    ("railways CRT implied CH4 factor", "railways", "04b_emission_factors.tex",
     r"\\CHfour\{\} at \\num\{([\d.]+)\} and",
     lambda: _first_where("railways_unfccc_crt_cell_audit_2024.csv", "value",
                          row_label="Liquid fuels", field="ief_ch4_kg_per_TJ"), 0.0),
    ("railways CO2 share of category", "railways", "04b_emission_factors.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} of the category---is byte-identical",
     lambda: 100.0 * _first_where("railways_by_stream_2024.csv", "co2e_Mt_AR5",
                                  subitem="Diesel CO2")
             / _cell("railways_totals_2024.csv", "category", "Railways",
                     "co2e_Mt_AR5"), 0.6),
    ("railways FY2018 fuel kt", "railways", "05_validation.tex",
     r"consuming\s*\\SI\{([\d]+)\}\{\\kilo\\tonne\} in FY2017--18",
     lambda: _first_where("railways_official_comparison_2024.csv",
                          "metered_diesel_kt", benchmark_id="bur1"), 0.0),
    ("railways reference fuel kt", "railways", "05_validation.tex",
     r"and \\SI\{([\d]+)\}\{\\kilo\\tonne\} in the reference year",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Traction diesel, for cross-source comparison", "co2e_Mt_AR5"),
     0.0),
    ("railways traffic million", "railways", "05_validation.tex",
     r"ran \\num\{([\d.]+)\} million\s*train-kilometres",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "railways",
                        "traffic.csv"))
                        if r["fiscal_year"] == "2024"
                        and r["metric"] == "total_train_km")["value"]) / 1000.0, 0.0),
    ("railways ELK total", "railways", "05_validation.tex",
     r"rail signal: \\SI\{([\d]+)\}\{\\kilo\\tonne\} of \\COtwo\{\} for 2019",
     lambda: _first_where("railways_elk_crosscheck_2024.csv", "elk_pak_kt_2019",
                          species="CO2-rep", subsector="rail-total"), 0.0),
    ("railways own CY2019", "railways", "05_validation.tex",
     r"inventory's \\SI\{([\d]+)\}\{\\kilo\\tonne\} for the same calendar",
     lambda: _first_where("railways_elk_crosscheck_2024.csv", "own_kt_cy2019",
                          species="CO2-rep", subsector="rail-total"), 0.0),
    ("railways ELK freight", "railways", "05_validation.tex",
     r"\\SI\{([\d]+)\}\{\\kilo\\tonne\} on freight across a thousand grid cells",
     lambda: _first_where("railways_elk_crosscheck_2024.csv", "elk_pak_kt_2019",
                          species="CO2-rep", subsector="rail-freight"), 0.0),
    ("railways ELK passenger", "railways", "05_validation.tex",
     r"\\SI\{([\d]+)\}\{\\kilo\\tonne\} of passenger rail on five cells",
     lambda: _first_where("railways_elk_crosscheck_2024.csv", "elk_pak_kt_2019",
                          species="CO2-rep", subsector="rail-passenger"), 0.0),
    ("railways freight intensity", "railways", "05_validation.tex",
     r"roughly \\SI\{([\d.]+)\}\{\\gram\} \\COtwo\{\} per\s*tonne-kilometre",
     lambda: _first_where("railways_efficiency_2024.csv", "gCO2_per_tonne_km",
                          fiscal_year="2024"), 0.0),
    ("railways OCAC customer row", "railways", "05_validation.tex",
     r"customer-class row at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _first_where("transport_fuel_ledger_2024.csv", "kt",
                          claimant="Railways"), 0.0),
    ("railways two-source gap", "railways", "05_validation.tex",
     r"two unrelated reporting chains\s*\\SI\{([\d.]+)\}\{\\percent\} apart",
     lambda: 100.0 * (_cell("railways_totals_2024.csv", "category",
                            "Traction diesel, for cross-source comparison",
                            "co2e_Mt_AR5")
                      - _first_where("transport_fuel_ledger_2024.csv", "kt",
                                     claimant="Railways"))
             / _first_where("transport_fuel_ledger_2024.csv", "kt",
                            claimant="Railways"), 0.0),
    ("railways BC fraction", "railways", "04_methods.tex",
     r"declared fraction \(\\num\{([\d.]+)\}\) of PM",
     # summed over the traction split: both categories share the declared f-BC,
     # so the ratio of sums is the fraction itself
     lambda: _sum_where("railways_air_pollutants_2024.csv", "emissions_kt",
                        fuel="Diesel", pollutant="BC")
             / _sum_where("railways_air_pollutants_2024.csv", "emissions_kt",
                          fuel="Diesel", pollutant="PM2.5"), 0.001),
    ("railways N2O interval low", "railways", "04b_emission_factors.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\kilo\\gram\\per\\tera\\joule\}",
     lambda: 0.5 * float(next(r for r in _rows(
         "railways_uncertainty_inputs_2024.csv")
         if r["variable"] == "Diesel N2O factor (rail)")["central_value"]), 0.0),
    ("railways N2O interval high", "railways", "04b_emission_factors.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\kilo\\gram\\per\\tera\\joule\}",
     lambda: 3.0 * float(next(r for r in _rows(
         "railways_uncertainty_inputs_2024.csv")
         if r["variable"] == "Diesel N2O factor (rail)")["central_value"]), 0.0),
    ("railways reference sulfur ppm", "railways", "04_methods.tex",
     r"against the \\SI\{([\d]+)\}\{ppm\} pre-Euro-V specification",
     lambda: _first_where("railways_air_sulfur_cases_2024.csv", "diesel_sulfur_ppm",
                          sulfur_case="reference_pre_euro5_spec"), 0.0),
    ("railways wagons-proxy Sindh share", "railways", "00_abstract.tex",
     r"freight-loadings proxy had said Sindh \\SI\{([\d]+)\}\{\\percent\}",
     lambda: 100.0 * _first_where("railways_uncertainty_scenarios_2024.csv",
                                  "deterministic",
                                  structural_scenario="provincial_wagons_proxy",
                                  scope="provincial: Sindh share"), 0.0),
    ("railways road-table caption gap", "railways", "06_results.tex",
     r"The gap is\s*\\SI\{([\d.]+)\}\{\\percent\} of the category",
     lambda: 100.0 * (1.0 - _cell("railways_totals_2024.csv", "category",
                                  "Diagnostic: N2O on the road factor", "co2e_Mt_AR5")
                      / _cell("railways_totals_2024.csv", "category",
                              "Module total (both categories)",
                              "co2e_Mt_AR5")), 0.0),
    ("railways AR6 total", "railways", "06_results.tex",
     r"or \\SI\{([\d.]+)\}\{\\mega\\tonne\} on AR6",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Module total (both categories)",
                   "co2e_Mt_AR6"), 0.0),
    ("railways N2O band", "railways", "06_results.tex",
     r"\\NtwoO\{\} at \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ is among the worst",
     lambda: _first_where("railways_by_stream_2024.csv", "uncert_pct",
                          subitem="Diesel N2O"), 0.0),
    ("railways NOx", "railways", "06_results.tex",
     r"NO\\textsubscript\{x\} at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     # the SECTOR total: the traction split (air spatial Wave A) put two rows per
     # pollutant in this file, and a first-row read silently became traction-only
     lambda: _air_kt("NOx"), 0.0),
    ("railways SO2 euro5", "railways", "06_results.tex",
     r"Euro-V fuel throughout it would be \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _first_where("railways_air_sulfur_cases_2024.csv", "so2_kt",
                          sulfur_case="euro5_import_spec"), 0.0),
    ("railways SO2 one percent", "railways", "06_results.tex",
     r"specification \\SI\{([\d.]+)\}\{\\kilo\\tonne\}---a",
     lambda: _first_where("railways_air_sulfur_cases_2024.csv", "so2_kt",
                          sulfur_case="historical_1.0pct"), 0.0),
    ("railways sulfur fold", "railways", "06_results.tex",
     r"a \\num\{([\d]+)\}-fold",
     lambda: _first_where("railways_air_sulfur_cases_2024.csv", "so2_kt",
                          sulfur_case="historical_1.0pct")
             / _first_where("railways_air_sulfur_cases_2024.csv", "so2_kt",
                            sulfur_case="euro5_import_spec"), 0.0),
    ("railways series start litres", "railways", "06_results.tex",
     r"rises from \\num\{([\d]+)\} to",
     lambda: _first_where("railways_timeseries_2024.csv", "diesel_thousand_litres",
                          fiscal_year="2014"), 0.0),
    ("railways series end litres", "railways", "06_results.tex",
     r"rises from \\num\{[\d]+\} to \\num\{([\d]+)\} thousand",
     lambda: _first_where("railways_timeseries_2024.csv", "diesel_thousand_litres",
                          fiscal_year="2025"), 0.0),
    ("railways series peak", "railways", "06_results.tex",
     r"it peaks in FY2019 at\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("railways_timeseries_2024.csv", "mt_co2e_AR5",
                          fiscal_year="2019"), 0.0),
    ("railways peak over reference", "railways", "06_results.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} above the reference year",
     lambda: 100.0 * (_first_where("railways_timeseries_2024.csv", "mt_co2e_AR5",
                                   fiscal_year="2019")
                      / _cell("railways_totals_2024.csv", "category", "Railways",
                              "co2e_Mt_AR5") - 1.0), 0.0),
    ("railways route Punjab in results", "railways", "06_results.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} of emissions land in Punjab",
     lambda: 100.0 * _first_where("railways_route_province_shares_2024.csv", "share",
                                  province="Punjab"), 0.0),
    ("railways route Sindh scenario pair", "railways", "06_results.tex",
     r"Sindh \\SI\{[\d]+\}\{\\percent\} against \\SI\{([\d]+)\}\{\\percent\}",
     lambda: 100.0 * _first_where("railways_route_province_shares_2024.csv", "share",
                                  province="Sindh"), 0.0),
    ("railways national share", "railways", "06_results.tex",
     r"At \\SI\{([\d.]+)\}\{\\percent\} of the national total",
     lambda: 100.0 * _cell("railways_totals_2024.csv", "category", "Railways",
                           "co2e_Mt_AR5") / _sector("TOTAL"), 0.0),
    ("railways independent band", "railways", "06b_uncertainty.tex",
     r"against \\SI\{([\d.]+)\}\{\\percent\} if the rows were independent",
     lambda: _first_where("railways_uncertainty_2024.csv",
                          "approach1_pct_independent", category="Railways"), 0.0),
    ("railways N2O input band", "railways", "06b_uncertainty.tex",
     r"\\NtwoO\{\} carries\s*\$\\pm\$\\SI\{([\d]+)\}\{\\percent\}",
     lambda: float(next(r for r in _rows("railways_uncertainty_inputs_2024.csv")
                        if r["variable"] == "Diesel N2O factor (rail)")
                   ["uncert_pct_95"]), 0.0),
    ("railways detail-sum gap", "railways", "08_limitations.tex",
     r"a\s*\\SI\{([\d.]+)\}\{\\percent\} gap",
     lambda: 100.0 * (138587.0 - _first_where("railways_fuel_reconciliation_2024.csv",
                                              "summary_k_litres", fiscal_year="2024"))
             / _first_where("railways_fuel_reconciliation_2024.csv",
                            "summary_k_litres", fiscal_year="2024"), 0.0),
    ("railways wear PM10", "railways", "08_limitations.tex",
     r"\\SI\{([\d]+)\}\{\\tonne\} of PM\\textsubscript\{10\} a year",
     lambda: 1000.0 * _first_where("railways_wear_pm_2024.csv", "emissions_kt",
                                   pollutant="PM10"), 0.0),
    ("railways PM25", "railways", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\kilo\\tonne\} PM\\textsubscript\{2.5\}",
     # sector total across the traction split, not the largest single row
     lambda: _air_kt("PM2.5"), 0.0),

    ("power sector total", "power", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} for FY2023--24",
     lambda: _cell("power_totals_fy2023_24.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("power grid total", "power", "00_abstract.tex",
     r"FY2023--24: \\SI\{([\d.]+)\}\{\\mega\\tonne\} from grid",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Electricity and heat production", "co2e_Mt_AR5"), 0.0),
    ("power captive total", "power", "00_abstract.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} from industrial captive",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Captive gas self-generation (1A2)", "co2e_Mt_AR5"), 0.0),
    ("power national share", "power", "00_abstract.tex",
     r"together\s*\\SI\{([\d.]+)\}\{\\percent\} of a ten-sector",
     lambda: 100.0 * _cell("power_totals_fy2023_24.csv", "category", "TOTAL",
                           "co2e_Mt_AR5") / _sector("TOTAL"), 0.0),
    ("power thar share of coal generation", "power", "00_abstract.tex",
     r"plants are \\SI\{([\d.]+)\}\{\\percent\} of coal generation",
     lambda: _cell("power_coal_blend_fy2023_24.csv", "item",
                   "Thar-named plants, share of coal generation", "value"), 0.0),
    ("power lignite share midpoint", "power", "00_abstract.tex",
     r"lignite share is \\num\{([\d.]+)\} with",
     lambda: 0.5 * (_cell("power_coal_blend_fy2023_24.csv", "item",
                          "Lignite share, Lucky as imported", "value")
                    + _cell("power_coal_blend_fy2023_24.csv", "item",
                            "Lignite share, Lucky as Thar", "value")), 0.0),
    ("power MMBTU implied efficiency", "power", "00_abstract.tex",
     r"imply \\SI\{([\d.]+)\}\{\\percent\} net efficiency",
     lambda: _cell("power_energy_closure_fy2023_24.csv", "item",
                   "Implied net efficiency, MMBTU plants", "value"), 0.0),
    ("power table3 implied NCV", "power", "00_abstract.tex",
     r"implies \\SI\{([\d.]+)\}\{\} TJ/Gg over",
     lambda: _cell("power_coal_blend_fy2023_24.csv", "item",
                   "Implied fleet NCV from Table 3", "value"), 0.0),
    ("power lignite mass share", "power", "00_abstract.tex",
     r"fleet that is \\SI\{([\d]+)\}\{\\percent\} lignite by mass",
     lambda: (lambda rows: 100.0
              * sum(float(r["mass_kt"]) for r in rows
                    if r["fuel_origin"] in ("Thar lignite", "unknown"))
              / sum(float(r["mass_kt"]) for r in rows))(
         [r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
          if r["fiscal_year"] == "2023" and r["mass_kt"]
          and r["fuel_origin"] in ("Thar lignite", "imported", "unknown")]), 0.0),
    ("power captive metered sum", "power", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\} MMCFD against the regulator's published",
     lambda: sum(float(r["gas_mmcfd"])
                 for r in _data_rows(os.path.join("activity", "power",
                                     "captive_register.csv"))
                 if r["gas_mmcfd"]), 0.0),
    ("power OGRA captive total", "power", "00_abstract.tex",
     r"against the regulator's published \\SI\{([\d]+)\}\{\}",
     lambda: float(next(r for r in _data_rows(os.path.join("activity", "power",
                        "captive_gas.csv"))
                        if r["fiscal_year"] == "2024")["total_mmcfd"]), 0.0),
    ("power NOx total", "power", "00_abstract.tex",
     r"\\SI\{([\d]+)\}\{\\kilo\\tonne\}\s*\\NOx\{\}",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="NOx"), 0.0),
    ("power filterable PM total", "power", "00_abstract.tex",
     r"\\SI\{([\d]+)\}\{\\kilo\\tonne\} filterable particulate",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM"), 0.0),
    ("power PM25 total", "power", "00_abstract.tex",
     r"of which \\SI\{([\d]+)\}\{\\kilo\\tonne\} is",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.0),
    ("power ledger-vs-default ratio", "power", "01_introduction.tex",
     r"implies a calorific value \\num\{([\d.]+)\} times",
     lambda: (lambda rows, cv: cv / (
         (lambda s: s * 11.9 + (1.0 - s) * 25.8)(
             sum(float(r["mass_kt"]) for r in rows
                 if r["fuel_origin"] in ("Thar lignite", "unknown"))
             / sum(float(r["mass_kt"]) for r in rows))))(
         [r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
          if r["fiscal_year"] == "2023" and r["mass_kt"]
          and r["fuel_origin"] in ("Thar lignite", "imported", "unknown")],
         _cell("power_coal_blend_fy2023_24.csv", "item",
               "Implied fleet NCV from Table 3", "value")), 0.01),
    ("power fleet implied CV", "power", "05_validation.tex",
     r"implies \\SI\{([\d.]+)\}\{\} TJ/Gg against",
     lambda: float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                        if r["fiscal_year"] == "2023"
                        and r["plant"] == "FLEET (mass-weighted)")
                   ["implied_cv_TJ_per_Gg"]), 0.0),
    ("power CV factor 2023", "power", "05_validation.tex",
     r"a factor of \\num\{([\d.]+)\}, and \\num\{[\d.]+\} in FY2022--23",
     lambda: _cell("power_coal_blend_fy2023_24.csv", "item",
                   "Implied fleet NCV from Table 3", "value")
             / float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                          if r["fiscal_year"] == "2023"
                          and r["plant"] == "FLEET (mass-weighted)")
                     ["implied_cv_TJ_per_Gg"]), 0.0),
    ("power thar mass-weighted CV", "power", "05_validation.tex",
     r"mass-weighted \\SI\{([\d.]+)\}\{\} in\s*FY2023--24",
     lambda: float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                        if r["fiscal_year"] == "2023"
                        and r["plant"] == "Thar lignite only")
                   ["implied_cv_TJ_per_Gg"]), 0.05),
    ("power gas unmatched in CRT", "power", "05_validation.tex",
     r"\\SI\{([\d]+)\}\{\} TJ in this inventory's matched year",
     lambda: float(_cell("power_crt_comparison.csv", "item",
                         "Engine gas energy unmatched in CRT (TJ)", "value")), 10.0),
    ("power series values", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: \\SI\{([\d.]+)\}\{\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2013"), 0.0),
    ("power series y2014", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){1}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2014"), 0.0),
    ("power series y2015", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){2}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2015"), 0.0),
    ("power series y2016", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){3}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2016"), 0.0),
    ("power series y2017", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){4}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2017"), 0.0),
    ("power series y2018", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){5}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2018"), 0.0),
    ("power series y2019", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){6}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2019"), 0.0),
    ("power series y2020", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){7}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2020"), 0.0),
    ("power series y2021", "power", "05_validation.tex",
     r"FY2013--14 to FY2023--24: (?:\\SI\{[\d.]+\}\{\},\s*){8}\\SI\{([\d.]+)\}",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2021"), 0.0),
    ("power series end", "power", "05_validation.tex",
     r"\\SI\{([\d.]+)\}\{\} and \\SI\{[\d.]+\}\{\\mega\\tonne\} \([^)]*\)---extended backward",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2022"), 0.0),
    ("power series reference year", "power", "05_validation.tex",
     r"\\SI\{[\d.]+\}\{\} and \\SI\{([\d.]+)\}\{\\mega\\tonne\} \([^)]*\)---extended backward",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2023"), 0.0),
    ("power one-year fall", "power", "05_validation.tex",
     r"a \\SI\{([\d.]+)\}\{\\mega\\tonne\} fall in one year",
     lambda: _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                          fiscal_year="2017")
             - _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                            fiscal_year="2018"), 0.05),
    ("power EDGAR power", "power", "05_validation.tex",
     r"emissions at \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} for 2024",
     lambda: _first_where("national_benchmark_comparison.csv", "benchmark_Mt_co2e",
                          source="EDGAR",
                          engine_category="Electricity and heat production"), 0.0),
    ("power EDGAR ratio", "power", "05_validation.tex",
     r"or\s*\\SI\{([\d]+)\}\{\\percent\} of it",
     lambda: 100.0 * _first_where("national_benchmark_comparison.csv",
                                  "ratio_engine_over_benchmark", source="EDGAR",
                                  engine_category="Electricity and heat production"),
     0.5),
    ("power EDGAR industry", "power", "05_validation.tex",
     r"industrial combustion at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("national_benchmark_comparison.csv", "benchmark_Mt_co2e",
                          source="EDGAR",
                          engine_category="1A2 (all estimated)"), 0.0),
    ("power EDGAR industry ratio", "power", "05_validation.tex",
     r"a ratio of \\num\{([\d.]+)\}",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Captive gas self-generation (1A2)", "co2e_Mt_AR5")
             / _first_where("national_benchmark_comparison.csv",
                            "benchmark_Mt_co2e", source="EDGAR",
                            engine_category="1A2 (all estimated)"), 0.0),
    ("power KE RFO discriminator low", "power", "05_validation.tex",
     # rc67: the sentence had the ratio the wrong way round. The audit divides the
     # station sum by the national row (plant_ledger.ke_boundary_audit), so it is the
     # plant sum that sits at 0.890 and 1.256 times the row, not the row times the sum.
     r"without-K-E plant sum sits at \\num\{([\d.]+)\} times the national RFO row",
     lambda: _first_where("power_boundary_audit_fy2023_24.csv", "rfo_without_KE",
                          fiscal_year="2023"), 0.0),
    ("power KE RFO discriminator high", "power", "05_validation.tex",
     r"the with-K-E sum at \\num\{([\d.]+)\} times it",
     lambda: _first_where("power_boundary_audit_fy2023_24.csv", "rfo_with_KE",
                          fiscal_year="2023"), 0.0),
    ("power KE first year", "power", "05_validation.tex",
     r"rows imply \\SI\{([\d.]+)\}\{\}, \\SI\{[\d.]+\}\{\},",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "co2_Mt",
                          fiscal_year="2019"), 0.0),
    ("power KE last year", "power", "05_validation.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*\\COtwo\{\} across FY2019--24",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "co2_Mt",
                          fiscal_year="2023"), 0.0),
    ("power KE decline", "power", "05_validation.tex",
     r"a \\SI\{([\d]+)\}\{\\percent\} decline in five years",
     lambda: 100.0 * (1.0 - _first_where("power_ke_leg_fy2023_24.csv", "co2_Mt",
                                         fiscal_year="2023")
                      / max(float(r["co2_Mt"])
                            for r in _rows("power_ke_leg_fy2023_24.csv"))), 0.5),
    ("power KE ledger scenario", "power", "05_validation.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} against the \\SI\{40.04\}\{\} headline",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: grid + K-Electric ledger fuel", "co2e_Mt_AR5"), 0.0),
    ("power KE 2020", "power", "05_validation.tex",
     r"rows imply \\SI\{[\d.]+\}\{\}, \\SI\{([\d.]+)\}\{\},",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "co2_Mt",
                          fiscal_year="2020"), 0.0),
    ("power KE 2021", "power", "05_validation.tex",
     r"rows imply \\SI\{[\d.]+\}\{\}, \\SI\{[\d.]+\}\{\}, \\SI\{([\d.]+)\}\{\},",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "co2_Mt",
                          fiscal_year="2021"), 0.0),
    ("power KE 2022", "power", "05_validation.tex",
     r"rows imply (?:\\SI\{[\d.]+\}\{\}, ){3}\\SI\{([\d.]+)\}\{\} and",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "co2_Mt",
                          fiscal_year="2022"), 0.0),

    ("power ledger generation coverage", "power", "00_abstract.tex",
     r"covering \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * sum(float(r["net_generation_GWh"])
                         for r in _data_rows(os.path.join("activity", "power",
                                             "plant_fuel_ledger.csv"))
                         if r["fiscal_year"] == "2023" and r["net_generation_GWh"])
             / sum(float(r["gwh_net"])
                   for r in _data_rows(os.path.join("activity", "power",
                                       "generation_by_fuel.csv"))
                   if r["fiscal_year"] == "2023" and r["gwh_net"]), 0.0),
    ("power register agreement", "power", "03_study_area_and_data.tex",
     r"agreeing to \\SI\{([\d.]+)\}\{\} MMCFD",
     lambda: abs(sum(float(r["gas_mmcfd"])
                     for r in _data_rows(os.path.join("activity", "power",
                                         "captive_register.csv"))
                     if r["gas_mmcfd"])
                 - float(next(r for r in _data_rows(os.path.join(
                     "activity", "power", "captive_gas.csv"))
                     if r["fiscal_year"] == "2024")["total_mmcfd"])), 0.0),
    ("ippu geocoded count", "ippu", "08_limitations.tex",
     r"only \\num\{(\d+)\} carry\s*resolved coordinates",
     lambda: sum(1 for r in _rows("ippu_facility_registry.csv")
                 if r["geocode_status"] == "exact_coordinate_resolved"), 0.0),
    # The registry now anchored to a register proved consistent with the master and with the
    # override file it reads (tests/test_ippu.py). These three claims passed for four
    # releases against a stale sector registry saying eight.
    ("ippu geocoded study area", "ippu", "03_study_area_and_data.tex",
     r"\\num\{(\d+)\} facilities now carry resolved coordinates",
     lambda: sum(1 for r in _rows("ippu_facility_registry.csv")
                 if r["geocode_status"] == "exact_coordinate_resolved"), 0.0),
    ("ippu geocoded methods", "ippu", "04_methods.tex",
     r"identified; \\num\{(\d+)\} carry resolved coordinates",
     lambda: sum(1 for r in _rows("ippu_facility_registry.csv")
                 if r["geocode_status"] == "exact_coordinate_resolved"), 0.0),
    # THE OTHER SIDE OF THE SAME SENTENCE (rc44). The resolved count was registered and the
    # unresolved count beside it was not, so locating five cement works repaired one number and
    # left the other reading 15 against a true 10 - in the same clause. A count and its
    # complement have to be registered together or the repair makes the sentence worse.
    # The basis test, both sides of it. A comparison quoted with only the favourable number
    # is not a comparison, so the control's distance from BOTH candidates is registered.
    ("power rfo basis generation", "power", "05_validation.tex",
     r"own-year generation lands at \\num\{([\d.]+)\}",
     lambda: float(next(r["tvd_generation_vs_fuel"] for r in
                        _rows_banner("pakemis_power_grid_basis_change.csv")
                        if r["stream"] == "power_rfo")), 0.0005),
    ("power rfo basis borrowed", "power", "05_validation.tex",
     r"against\s*\\num\{([\d.]+)\} for the borrowed vector",
     lambda: float(next(r["tvd_borrowed_vs_fuel"] for r in
                        _rows_banner("pakemis_power_grid_basis_change.csv")
                        if r["stream"] == "power_rfo")), 0.0005),
    # The historical unallocated series, both ends of it: a range quoted with one end
    # registered and the other not is the half-repaired sentence this release already found
    # once, in the IPPU facility counts below.
    ("national unallocated fy2017_18", "national", "06_results.tex",
     r"falls from \\SI\{([\d.]+)\}\{\\mega\\tonne\} in FY2017--18",
     lambda: sum(float(r["co2e_Mt_AR5"] or 0) for r in
                 _rows_banner("pakemis_spatial_unallocated_by_year.csv")
                 if r["period_id"] == "FY2017-18"), 0.005),
    ("national unallocated fy2023_24", "national", "06_results.tex",
     r"to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} in FY2023--24",
     lambda: sum(float(r["co2e_Mt_AR5"] or 0) for r in
                 _rows_banner("pakemis_spatial_unallocated_by_year.csv")
                 if r["period_id"] == "FY2023-24"), 0.005),
    ("railways appendix generated outputs", "railways", "10_appendix.tex",
     r"writes the \\num\{(\d+)\} files its run manifest",
     lambda: _railways_generated_outputs(), 0.0),
    # ---- the aviation appendix, now naming its outputs (cycle 32) --------------------------
    ("aviation appendix source rows", "aviation", "10_appendix.tex",
     r"\\num\{(\d+)\} monthly source rows",
     lambda: float(len(_rows("aviation_ocac_monthly.csv"))), 0.0),
    ("aviation appendix annual summaries", "aviation", "10_appendix.tex",
     r"\\num\{(\d+)\} annual OCAC summaries",
     lambda: float(len(_rows("aviation_ocac_annual_summary.csv"))), 0.0),
    ("aviation appendix comparison rows", "aviation", "10_appendix.tex",
     r"\\num\{(\d+)\} monthly comparison rows",
     lambda: float(len(_rows("aviation_monthly_reconciliation.csv"))), 0.0),
    ("aviation appendix complete oecd years", "aviation", "10_appendix.tex",
     r"of which \\num\{(\d+)\} years are complete",
     lambda: _aviation_oecd_complete_years(), 0.0),
    # ---- the fugitives appendix, now naming its outputs (cycle 31) -------------------------
    ("fugitives appendix ufg low", "fugitives", "10_appendix.tex",
     r"\\SI\{(\d+)\}\{\\percent\} and a \\SI\{\d+\}\{\\percent\} unaccounted",
     lambda: _ufg_threshold("low"), 0.0),
    ("fugitives appendix ufg high", "fugitives", "10_appendix.tex",
     r"and a \\SI\{(\d+)\}\{\\percent\} unaccounted",
     lambda: _ufg_threshold("high"), 0.0),
    ("fugitives appendix segments", "fugitives", "10_appendix.tex",
     r"for each of \\num\{(\d+)\} segments",
     lambda: _fugitives_table_rows("fugitives_segment_native_gases_2024.csv",
                                   distinct="segment"), 0.0),
    ("fugitives appendix factorial", "fugitives", "10_appendix.tex",
     r"all \\num\{(\d+)\} factorial",
     lambda: _fugitives_table_rows("fugitives_structural_factorial_2024.csv"), 0.0),
    ("fugitives appendix intervals", "fugitives", "10_appendix.tex",
     r"\\num\{(\d+)\} conditional Monte",
     lambda: _fugitives_table_rows("fugitives_conditional_intervals_2024.csv"), 0.0),
    ("fugitives appendix reconstruction years", "fugitives", "10_appendix.tex",
     r"the \\num\{(\d+)\}-year\s*\n?\s*infrastructure reconstruction",
     lambda: _fugitives_table_rows("fugitives_infrastructure_timeseries_2016_2024.csv"), 0.0),
    # ---- the IPPU registry breakdown, BOTH sections on one getter (cycle 29) ---------------
    # The study-area passage stated 24 resolved coordinates and then listed one, seven and
    # eleven - which sums to 19. The methods passage, two sections later, listed one, seven and
    # a registered 16, which sums to 24 and is right. Every component of both is now anchored
    # to _ippu_geocode, and tests/test_passage_arithmetic.py asserts the parts sum to the
    # total, which is the check that was missing: nothing compared a passage against itself.
    ("ippu census companies", "ippu", "03_study_area_and_data.tex",
     r"All \\num\{(\d+)\} census companies",
     lambda: float(len(_rows("ippu_cement_producer_census_2024.csv"))), 0.0),
    ("ippu registry total, study area", "ippu", "03_study_area_and_data.tex",
     r"identifies \\num\{(\d+)\} cement",
     lambda: _ippu_geocode("total"), 0.0),
    ("ippu resolved, study area", "ippu", "03_study_area_and_data.tex",
     r"\\num\{(\d+)\} facilities now carry resolved",
     lambda: _ippu_geocode("resolved"), 0.0),
    ("ippu nominatim, study area", "ippu", "03_study_area_and_data.tex",
     r"resolved coordinates---\\num\{(\d+)\} from an",
     lambda: _ippu_geocode("nominatim"), 0.0),
    ("ippu osm, study area", "ippu", "03_study_area_and_data.tex",
     r"\\num\{(\d+)\} from named OSM industrial polygons",
     lambda: _ippu_geocode("osm"), 0.0),
    ("ippu gem, study area", "ippu", "03_study_area_and_data.tex",
     r"\\num\{(\d+)\} from the Global Energy Monitor cement tracker",
     lambda: _ippu_geocode("gem"), 0.0),
    ("ippu unresolved, study area", "ippu", "03_study_area_and_data.tex",
     r"the remaining \\num\{(\d+)\} are retained at locality",
     lambda: _ippu_geocode("unresolved"), 0.0),
    # The appendix now NAMES the evidence tables it describes, and states the census size twice
    # (the census itself and the company-flow table covering the same entities). Both read the
    # census, so a change in the producer universe moves both or fails.
    ("ippu appendix census size", "ippu", "10_appendix.tex",
     r"the \\num\{(\d+)\}-company producer",
     lambda: float(len(_rows("ippu_cement_producer_census_2024.csv"))), 0.0),
    ("ippu appendix company entities", "ippu", "10_appendix.tex",
     r"for the same\s*\n?\\num\{(\d+)\} entities",
     lambda: float(len(_rows("ippu_company_clinker_2024.csv"))), 0.0),
    ("ippu unresolved methods", "ippu", "04_methods.tex",
     r"remaining \\num\{(\d+)\} are located only",
     lambda: sum(1 for r in _rows("ippu_facility_registry.csv")
                 if r["geocode_status"] != "exact_coordinate_resolved"), 0.0),
    # The tracker's own contribution, promoted from a spelled word to a registered number for
    # the same reason: "eleven" cannot be repaired, and it was wrong the moment five arrived.
    ("ippu gem geocoded methods", "ippu", "04_methods.tex",
     r"and \\num\{(\d+)\} from the Global Energy",
     lambda: sum(1 for r in _rows("ippu_facility_registry.csv")
                 if r["coordinate_source"].startswith("Global Energy Monitor Global Cement")),
     0.0),
    # The two-register agreement, and its bounds. The narrowest and widest separations are
    # both claims because a sentence quoting a range can go stale at either end.
    ("ippu census works limitations", "ippu", "08_limitations.tex",
     r"Although \\num\{(\d+)\} facilities are identified",
     lambda: float(_first_where("ippu_facility_coverage.csv", "facilities_declared",
                                province="TOTAL")), 0.0),
    ("ippu locality count", "ippu", "03_study_area_and_data.tex",
     r"remaining \\num\{(\d+)\} are retained at locality",
     lambda: sum(1 for r in _rows("ippu_facility_registry.csv")
                 if r["geocode_status"] != "exact_coordinate_resolved"), 0.0),
    ("power family cv restated", "power", "00_abstract.tex",
     r"grid\\_plant\\_cv\\_restated\} \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("power_uncertainty_scenarios_fy2023_24.csv", "deterministic_Mt",
                          family_id="grid_plant_cv_restated"), 0.0),
    ("power family plus ke", "power", "00_abstract.tex",
     r"grid\\_plus\\_ke\} \\SI\{([\d.]+)\}\{\\mega\\tonne\} beside them---competing",
     lambda: _first_where("power_uncertainty_scenarios_fy2023_24.csv", "deterministic_Mt",
                          family_id="grid_plus_ke"), 0.0),
    ("power family intro ke", "power", "01_introduction.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} are the\s*plant-implied",
     lambda: _first_where("power_uncertainty_scenarios_fy2023_24.csv", "deterministic_Mt",
                          family_id="grid_plus_ke"), 0.0),
    ("power captive ICT", "power", "03_study_area_and_data.tex",
     r"with \\SI\{([\d.]+)\}\{\} in the Islamabad",
     lambda: sum(float(r["gas_mmcfd"])
                 for r in _data_rows(os.path.join("activity", "power",
                                     "captive_register.csv"))
                 if r["gas_mmcfd"] and "Islamabad" in r["province_region"]), 0.0),
    ("power captive unassigned count", "power", "03_study_area_and_data.tex",
     r"register: (\d+) plants\s*holding",
     lambda: float(len([r for r in _data_rows(os.path.join("activity", "power",
                                              "captive_register.csv"))
                        if r["gas_mmcfd"] and not r["province_region"].strip()])), 0.0),
    ("power captive unassigned residual", "power", "03_study_area_and_data.tex",
     r"holding \\SI\{([\d.]+)\}\{\} MMCFD carry no province",
     lambda: sum(float(r["gas_mmcfd"])
                 for r in _data_rows(os.path.join("activity", "power",
                                     "captive_register.csv"))
                 if r["gas_mmcfd"] and not r["province_region"].strip()), 0.0),
    ("power captive Sindh", "power", "03_study_area_and_data.tex",
     r"Sindh \\SI\{([\d.]+)\}\{\}, Punjab",
     lambda: sum(float(r["gas_mmcfd"])
                 for r in _data_rows(os.path.join("activity", "power",
                                     "captive_register.csv"))
                 if r["gas_mmcfd"] and r["province_region"] == "Sindh"), 0.0),
    ("power captive Punjab", "power", "03_study_area_and_data.tex",
     r"Punjab \\SI\{([\d.]+)\}\{\}, Khyber",
     lambda: sum(float(r["gas_mmcfd"])
                 for r in _data_rows(os.path.join("activity", "power",
                                     "captive_register.csv"))
                 if r["gas_mmcfd"] and r["province_region"] == "Punjab"), 0.0),
    ("power captive KP", "power", "03_study_area_and_data.tex",
     r"Pakhtunkhwa \\SI\{([\d.]+)\}\{\}, Balochistan",
     lambda: sum(float(r["gas_mmcfd"])
                 for r in _data_rows(os.path.join("activity", "power",
                                     "captive_register.csv"))
                 if r["gas_mmcfd"]
                 and r["province_region"] == "Khyber Pakhtunkhwa"), 0.0),
    ("power captive Balochistan", "power", "03_study_area_and_data.tex",
     r"Balochistan \\SI\{([\d.]+)\}\{\} MMCFD",
     lambda: sum(float(r["gas_mmcfd"])
                 for r in _data_rows(os.path.join("activity", "power",
                                     "captive_register.csv"))
                 if r["gas_mmcfd"] and r["province_region"] == "Balochistan"), 0.0),
    ("power blend span", "power", "04_methods.tex",
     r"a span of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} around a central",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: all coal lignite", "co2e_Mt_AR5")
             - _cell("power_totals_fy2023_24.csv", "category",
                     "Sensitivity: all coal bituminous", "co2e_Mt_AR5"), 0.0),
    ("power lignite share pct", "power", "04_methods.tex",
     r"computed at a\s*\\SI\{([\d]+)\}\{\\percent\} lignite share",
     lambda: 100.0 * 0.5 * (_cell("power_coal_blend_fy2023_24.csv", "item",
                                  "Lignite share, Lucky as imported", "value")
                            + _cell("power_coal_blend_fy2023_24.csv", "item",
                                    "Lignite share, Lucky as Thar", "value")), 0.0),
    ("power captive at 900", "power", "04_methods.tex",
     r"at \\SI\{900\}\{\} it is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: captive gas at 900 Btu/scf", "co2e_Mt_AR5"), 0.0),
    ("power imported share", "power", "04b_emission_factors.tex",
     r"imported-coal plants \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 - _cell("power_coal_blend_fy2023_24.csv", "item",
                           "Thar-named plants, share of coal generation", "value")
             - _cell("power_coal_blend_fy2023_24.csv", "item",
                     "Lucky Electric, share of coal generation", "value"), 0.0),
    ("power lucky share", "power", "04b_emission_factors.tex",
     r"Lucky Electric, at\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _cell("power_coal_blend_fy2023_24.csv", "item",
                   "Lucky Electric, share of coal generation", "value"), 0.0),
    ("power lignite lower bound", "power", "04b_emission_factors.tex",
     r"assigned: \\num\{([\d.]+)\} with Lucky as imported",
     lambda: _cell("power_coal_blend_fy2023_24.csv", "item",
                   "Lignite share, Lucky as imported", "value"), 0.0),
    ("power lignite upper bound", "power", "04b_emission_factors.tex",
     r"\\num\{([\d.]+)\} with Lucky as Thar",
     lambda: _cell("power_coal_blend_fy2023_24.csv", "item",
                   "Lignite share, Lucky as Thar", "value"), 0.0),
    ("power lucky CV low", "power", "04b_emission_factors.tex",
     r"calorific value sits at \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\} TJ/Gg",
     lambda: min(float(r["implied_cv_TJ_per_Gg"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["plant"] == "Lucky Electric"
                 and r["implied_cv_TJ_per_Gg"]), 0.05),
    ("power lucky CV high", "power", "04b_emission_factors.tex",
     r"calorific value sits at \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\} TJ/Gg",
     lambda: max(float(r["implied_cv_TJ_per_Gg"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["plant"] == "Lucky Electric"
                 and r["implied_cv_TJ_per_Gg"]), 0.05),
    ("power gas thermal share", "power", "05_validation.tex",
     r"gas and RLNG as \\SI\{([\d]+)\}\{\\percent\} of thermal",
     lambda: _first_where("power_fuel_fy2023_24.csv", "share_pct", fuel="Gas"), 0.0),
    ("power CRT lignite share", "power", "05_validation.tex",
     r"sits at a \\SI\{([\d]+)\}\{\\percent\} lignite share",
     lambda: 100.0 * float(_cell("power_crt_comparison.csv", "item",
                                 "CRT implied lignite share of solid-fuel factor",
                                 "value")), 0.0),
    ("power EDGAR agreement", "power", "05_validation.tex",
     r"Agreement\s*at \\SI\{([\d]+)\}\{\\percent\} between two independently",
     lambda: 100.0 * _first_where("national_benchmark_comparison.csv",
                                  "benchmark_Mt_co2e", source="EDGAR",
                                  engine_category="Electricity and heat production")
             / _cell("power_totals_fy2023_24.csv", "category",
                     "Electricity and heat production", "co2e_Mt_AR5"), 0.5),
    ("power FO efficiency low", "power", "05_validation.tex",
     r"Furnace oil\s+& \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\}",
     lambda: 100.0 * _first_where("power_heat_rate_stability_fy2023_24.csv",
                                  "efficiency_lo", fuel="Furnace Oil"), 0.05),
    ("power FO efficiency high", "power", "05_validation.tex",
     r"Furnace oil\s+& \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _first_where("power_heat_rate_stability_fy2023_24.csv",
                                  "efficiency_hi", fuel="Furnace Oil"), 0.05),
    ("power diesel efficiency low", "power", "05_validation.tex",
     r"Diesel oil\s+& \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\}",
     lambda: 100.0 * _first_where("power_heat_rate_stability_fy2023_24.csv",
                                  "efficiency_lo", fuel="Diesel Oil"), 0.05),
    ("power diesel efficiency high", "power", "05_validation.tex",
     r"Diesel oil\s+& \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _first_where("power_heat_rate_stability_fy2023_24.csv",
                                  "efficiency_hi", fuel="Diesel Oil"), 0.05),
    ("power imported CV band low", "power", "05_validation.tex",
     r"imported-coal plants\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\}",
     lambda: min(float(r["implied_cv_TJ_per_Gg"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["fuel_origin"] == "imported" and r["implied_cv_TJ_per_Gg"]
                 and r["fiscal_year"] != "2021"), 0.5),
    ("power imported CV band high", "power", "05_validation.tex",
     r"imported-coal plants\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\}",
     lambda: max(float(r["implied_cv_TJ_per_Gg"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["fuel_origin"] == "imported" and r["implied_cv_TJ_per_Gg"]
                 and r["fiscal_year"] != "2021"
                 and float(r["implied_cv_TJ_per_Gg"]) < 30.0), 0.5),
    ("power thar CV band low", "power", "05_validation.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\} TJ/Gg across their plant-years",
     lambda: min(float(r["implied_cv_TJ_per_Gg"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["fuel_origin"] == "Thar lignite"
                 and r["implied_cv_TJ_per_Gg"]), 0.05),
    ("power thar CV band high", "power", "05_validation.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\} TJ/Gg across their plant-years",
     lambda: max(float(r["implied_cv_TJ_per_Gg"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["fuel_origin"] == "Thar lignite"
                 and r["implied_cv_TJ_per_Gg"]), 0.05),
    ("power CV factor 2022", "power", "05_validation.tex",
     r"and \\num\{([\d.]+)\} in FY2022--23",
     lambda: (lambda rows: float(next(r for r in rows
                                      if r["fiscal_year"] == "2022"
                                      and r["plant"] == "Table 3 implied NCV")
                                 ["implied_cv_TJ_per_Gg"])
              / float(next(r for r in rows if r["fiscal_year"] == "2022"
                           and r["plant"] == "FLEET (mass-weighted)")
                      ["implied_cv_TJ_per_Gg"]))(
         list(_rows("power_implied_coal_cv_fy2023_24.csv"))), 0.05),
    ("power restated energy", "power", "05_validation.tex",
     r"\\SI\{([\d]+)\}\{\} against \\SI\{[\d]+\}\{\} TJ",
     lambda: (lambda rows: sum(float(r["mass_kt"])
                               * float(r["implied_cv_TJ_per_Gg"])
                               for r in rows))(
         [r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
          if r["fiscal_year"] == "2023" and r["mass_kt"]
          and r["implied_cv_TJ_per_Gg"]
          and r["fuel_origin"] in ("Thar lignite", "imported", "unknown")]), 3000.0),
    ("power coal TJ", "power", "05_validation.tex",
     r"against \\SI\{([\d]+)\}\{\} TJ",
     lambda: _first_where("power_fuel_fy2023_24.csv", "TJ", fuel="Coal"), 0.0),
    ("power trace missing coal", "power", "05_validation.tex",
     r"missing \\SI\{([\d]+)\}\{\\mega\\tonne\} of",
     lambda: sum(float(r["trace_co2e_t"])
                 for r in _rows_banner("power_climatetrace_plants_fy2023_24.csv")
                 if r["asset_type"] == "coal" and r["trace_co2e_t"]) / 1e6
             - _first_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                            subitem="Coal CO2"), 0.7),
    ("power own coal", "power", "05_validation.tex",
     r"inventory's coal is\s*near \\SI\{([\d]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                          subitem="Coal CO2"), 0.7),
    ("power trace gas low", "power", "05_validation.tex",
     r"ratios of \\num\{([\d.]+)\} to",
     lambda: _first_where("power_climatetrace_plants_fy2023_24.csv", "trace_over_engine",
                          trace_name="Trimmu power station"), 0.0),
    ("power trace gas high", "power", "05_validation.tex",
     r"to \\num\{([\d.]+)\}---the benchmark works",
     lambda: _first_where("power_climatetrace_plants_fy2023_24.csv", "trace_over_engine",
                          trace_name="Uch power station"), 0.0),
    ("power thar mass start", "power", "05_validation.tex",
     r"plant to four and \\SI\{([\d.]+)\}\{\} to",
     lambda: sum(float(r["mass_kt"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["fiscal_year"] == "2019" and r["mass_kt"]
                 and r["fuel_origin"] == "Thar lignite") / 1000.0, 0.3),
    ("power thar mass end", "power", "05_validation.tex",
     r"to \\SI\{([\d.]+)\}\{\\mega\\tonne\} of coal, its NO",
     lambda: sum(float(r["mass_kt"])
                 for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                 if r["fiscal_year"] == "2023" and r["mass_kt"]
                 and r["fuel_origin"] == "Thar lignite") / 1000.0, 0.1),
    ("power CPH mass start", "power", "05_validation.tex",
     r"China Power Hub's imported coal \\SI\{([\d]+)\}\{\} to",
     lambda: float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                        if r["fiscal_year"] == "2019"
                        and r["plant"] == "China Power Hub")["mass_kt"]), 0.0),
    ("power CPH mass end", "power", "05_validation.tex",
     r"coal \\SI\{[\d]+\}\{\} to\s*\\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                        if r["fiscal_year"] == "2023"
                        and r["plant"] == "China Power Hub")["mass_kt"]), 0.0),
    ("power sahiwal suspect mass", "power", "05_validation.tex",
     r"suspect \(\\SI\{([\d]+)\}\{\\kilo\\tonne\} against",
     lambda: float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                        if r["fiscal_year"] == "2021"
                        and "Huaneng" in r["plant"])["mass_kt"]), 0.0),
    ("power sahiwal generation", "power", "05_validation.tex",
     r"against\s*\\SI\{([\d]+)\}\{GWh\}",
     lambda: float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                        if r["fiscal_year"] == "2021"
                        and "Huaneng" in r["plant"])["net_generation_GWh"]), 0.0),
    ("power sahiwal implied CV", "power", "05_validation.tex",
     r"implied CV \\SI\{([\d]+)\}\{\} TJ/Gg",
     lambda: float(next(r for r in _rows("power_implied_coal_cv_fy2023_24.csv")
                        if r["fiscal_year"] == "2021"
                        and "Huaneng" in r["plant"])["implied_cv_TJ_per_Gg"]), 0.0),
    ("power sahiwal generation ratio", "power", "05_validation.tex",
     r"the year ran at \\num\{([\d.]+)\}",
     lambda: _first_where("power_tropomi_crosscheck.csv", "no2_enh_mol_m2",
                          source="VERDICT: h3_generation_ratio"), 0.0),
    ("power uch CV flat", "power", "05_validation.tex",
     r"holds flat \(CV \\num\{([\d.]+)\}\)",
     lambda: _first_where("power_tropomi_crosscheck.csv", "no2_enh_mol_m2",
                          source="VERDICT: h4_uch_cv"), 0.0),
    ("power KE RFO retirement start", "power", "05_validation.tex",
     r"furnace-oil retirement \(\\SI\{([\d]+)\}\{\} down to",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "rfo_TJ", fiscal_year="2019")
             / 40.4, 1.0),
    ("power KE RFO retirement end", "power", "05_validation.tex",
     r"down to \\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "rfo_TJ", fiscal_year="2023")
             / 40.4, 1.0),
    ("power KE efficiency start", "power", "05_validation.tex",
     r"\\SI\{([\d.]+)\}\{\} to \\SI\{[\d.]+\}\{\\percent\} across the window",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "implied_net_efficiency_pct",
                          fiscal_year="2019"), 0.0),
    ("power KE efficiency end", "power", "05_validation.tex",
     r"\\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\\percent\} across the window",
     lambda: _first_where("power_ke_leg_fy2023_24.csv", "implied_net_efficiency_pct",
                          fiscal_year="2023"), 0.0),
    ("power coal emission share", "power", "06_results.tex",
     r"and \\SI\{([\d]+)\}\{\\percent\} of the grid emissions",
     lambda: 100.0 * _first_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                                  subitem="Coal CO2")
             / _cell("power_totals_fy2023_24.csv", "category",
                     "Electricity and heat production", "co2e_Mt_AR5"), 0.0),
    ("power CO2 share", "power", "06_results.tex",
     r"sector is \\SI\{([\d.]+)\}\{\\percent\} \\COtwo\{\}",
     lambda: 100.0 * _sum_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                                gas="CO2")
             / _cell("power_totals_fy2023_24.csv", "category", "TOTAL",
                     "co2e_Mt_AR5"), 0.3),
    ("power bagasse noncO2", "power", "06_results.tex",
     r"that is \\SI\{([\d.]+)\}\{\\mega\\tonne\} of \\CHfour\{\} and",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("power_by_stream_fy2023_24.csv")
                 if r["subitem"].startswith("Bagasse")), 0.005),
    ("power blend span share", "power", "06_results.tex",
     r"spans\s*\\SI\{([\d.]+)\}\{\\percent\} of the grid category",
     lambda: 100.0 * (_cell("power_totals_fy2023_24.csv", "category",
                            "Sensitivity: all coal lignite", "co2e_Mt_AR5")
                      - _cell("power_totals_fy2023_24.csv", "category",
                              "Sensitivity: all coal bituminous", "co2e_Mt_AR5"))
             / _cell("power_totals_fy2023_24.csv", "category",
                     "Electricity and heat production", "co2e_Mt_AR5"), 0.05),
    ("power gas span", "power", "06_results.tex",
     r"heating value spans \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Captive gas self-generation (1A2)", "co2e_Mt_AR5")
             - _cell("power_totals_fy2023_24.csv", "category",
                     "Sensitivity: captive gas at 900 Btu/scf", "co2e_Mt_AR5"), 0.0),
    ("power provincial Balochistan", "power", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}, Khyber Pakhtunkhwa",
     lambda: _first_where("power_provincial_fy2023_24.csv", "co2e_Mt_AR5",
                          province="Balochistan"), 0.0),
    ("power provincial KP", "power", "06_results.tex",
     r"Khyber Pakhtunkhwa \\SI\{([\d.]+)\}\{\\mega\\tonne\}\. Unlike",
     lambda: _first_where("power_provincial_fy2023_24.csv", "co2e_Mt_AR5",
                          province="Khyber Pakhtunkhwa"), 0.0),
    # rc66: the sentence says "on the stations' booked energy" and the claim reads the
    # committed coal row, which is that basis. It used to read the point-source product's
    # implied-calorific-value energy, the weighting the provincial split no longer uses.
    ("power sindh coal energy share", "power", "06_results.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} Sindh on the stations' booked energy",
     lambda: 100.0 * _province_share("power_coal", "Sindh"), 0.7),
    ("power captive band", "power", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} band is small",
     lambda: _first_where("power_uncertainty_fy2023_24.csv", "approach1_pct_grouped",
                          category="Captive gas self-generation (1A2)"), 0.0),
    ("power captive variance share", "power", "06_results.tex",
     r"contributes \\SI\{([\d.]+)\}\{\\percent\} of national variance",
     lambda: _power_keycat_rows()[1][1], 0.005),
    # The rank split dissolved the old within-3.2% agreement (a shared all-bituminous
    # assumption); the claim now anchors the DIVERGENCE the paper reports instead.
    # Re-anchored 2026-10-07: the screening moved BELOW the workbook with the coal re-base,
    # so the sentence says "below" and the magnitude is the absolute divergence. The old
    # regex took [\d.]+ against a signed getter, which could only ever match while the sign
    # was positive - a claim that stops guarding the moment the quantity it guards changes
    # direction.
    ("power SO2 workbook divergence", "power", "06b_air_pollutants.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} below the workbook",
     lambda: abs(100.0 * (_sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                                     pollutant="SO2") / 253.2 - 1.0)), 0.05),
    ("power SO2 screening level", "power", "06b_air_pollutants.tex",
     r"value the figure is \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="SO2"), 0.05),
    ("power residential biomass PM25", "power", "06b_air_pollutants.tex",
     r"residential biomass at \\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: sum(float(r["emissions_kt"])
                 for r in _rows("residential_air_pollutants_2024.csv")
                 if r["pollutant"] == "PM2.5"
                 and any(k in r["subitem"] for k in
                         ("Dung", "Firewood", "Crop", "Charcoal"))), 0.0),
    ("power coal PM25", "power", "06b_air_pollutants.tex",
     r"\\SI\{([\d.]+)\}\{\} of it from coal",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM2.5", fuel="Coal"), 0.05),
    ("power gas turbine share", "power", "06b_air_pollutants.tex",
     r"classifies as \\SI\{([\d.]+)\}\{\\percent\} turbine",
     lambda: 100.0 * _first_where("power_gas_technology_fy2023_24.csv", "share",
                                  bucket="turbine"), 0.0),
    ("power gas boiler share", "power", "06b_air_pollutants.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} boiler",
     lambda: 100.0 * _first_where("power_gas_technology_fy2023_24.csv", "share",
                                  bucket="boiler"), 0.05),
    ("power gas unresolved share", "power", "06b_air_pollutants.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} unresolved",
     lambda: 100.0 * _first_where("power_gas_technology_fy2023_24.csv", "share",
                                  bucket="unresolved"), 0.05),
    ("power bagasse generation", "power", "06_results.tex",
     r"sold \\SI\{([\d.]+)\}\{GWh\}",
     lambda: float(_cell("power_bagasse_fy2023_24.csv", "item", "Generation (GWh)",
                         "value")), 0.0),
    ("power blend consequence", "power", "08_limitations.tex",
     r"blend's consequence to \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * (_cell("power_totals_fy2023_24.csv", "category",
                            "Sensitivity: all coal lignite", "co2e_Mt_AR5")
                      - _cell("power_totals_fy2023_24.csv", "category",
                              "Sensitivity: all coal bituminous", "co2e_Mt_AR5"))
             / _cell("power_totals_fy2023_24.csv", "category",
                     "Electricity and heat production", "co2e_Mt_AR5"), 0.05),
    ("power blend lower endpoint prose", "power", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} and all-lignite",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: all coal bituminous", "co2e_Mt_AR5"), 0.0),
    ("power blend upper endpoint prose", "power", "04_methods.tex",
     r"all-lignite \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: all coal lignite", "co2e_Mt_AR5"), 0.0),
    ("power gas efficiency step low", "power", "05_validation.tex",
     r"to \\SIrange\{([\d]+)\}\{[\d]+\}\{\\percent\}\s*from FY2018 onward",
     lambda: 100.0 * min(float(r["efficiency"])
                         for r in _rows("power_heat_rate_fy2023_24.csv")
                         if r["fuel"] == "Gas"
                         and int(r["fiscal_year"]) >= 2018), 0.05),
    ("power gas efficiency step high", "power", "05_validation.tex",
     r"to \\SIrange\{[\d]+\}\{([\d]+)\}\{\\percent\}\s*from FY2018 onward",
     lambda: 100.0 * max(float(r["efficiency"])
                         for r in _rows("power_heat_rate_fy2023_24.csv")
                         if r["fuel"] == "Gas"
                         and int(r["fiscal_year"]) >= 2018), 0.05),
    ("power stable gas net", "power", "05_validation.tex",
     r"Gas at a stable \\SI\{([\d]+)\}\{\\percent\} net",
     lambda: 100.0 * sorted(float(r["efficiency"])
                            for r in _rows("power_heat_rate_fy2023_24.csv")
                            if r["fuel"] == "Gas"
                            and int(r["fiscal_year"]) >= 2018)[2], 0.05),
    ("power gross reading", "power", "05_validation.tex",
     r"imply about\s*\\SI\{([\d]+)\}\{\\percent\}, which is at the very top",
     lambda: 100.0 * sorted(float(r["efficiency"])
                            for r in _rows("power_heat_rate_fy2023_24.csv")
                            if r["fuel"] == "Gas"
                            and int(r["fiscal_year"]) >= 2018)[2] / 0.9, 0.3),
    ("power grid variance share prose", "power", "06_results.tex",
     r"national variance: \\SI\{([\d.]+)\}\{\\percent\}, down",
     lambda: _first_where("national_key_categories.csv",
                          "variance_share_pct_independent_approx",
                          ipcc_code="1.A.1.a"), 0.0),
    ("power annulus inner", "power", "05_validation.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\degree\} annulus",
     lambda: float(json.load(open(os.path.join(
         OUT, "power_tropomi_extraction_manifest.json")))
         ["method"]["annulus_deg"][0]), 0.0),
    ("power annulus outer", "power", "05_validation.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\degree\} annulus",
     lambda: float(json.load(open(os.path.join(
         OUT, "power_tropomi_extraction_manifest.json")))
         ["method"]["annulus_deg"][1]), 0.0),
    ("power proxy KP error", "power", "06_results.tex",
     r"generation moved \\SI\{([\d.]+)\}\{\\mega\\tonne\} out",
     lambda: (14.24 - 0.02) / 100.0
             * _first_where("power_timeseries_fy2023_24.csv", "mt_co2e_AR5",
                            fiscal_year="2022"), 0.05),
    ("power EDGAR near-44 aside", "power", "02_related_work.tex",
     r"industrial combustion near \\SI\{([\d]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("national_benchmark_comparison.csv", "benchmark_Mt_co2e",
                          source="EDGAR",
                          engine_category="1A2 (all estimated)"), 0.0),

    ("residential gas CRT agreement", "residential", "00_abstract.tex",
     r"sits within \\SI\{([\d.]+)\}\{\\percent\} of the regulator-derived",
     lambda: 100.0 * (288493.0 / _first_where("residential_fuel_2024.csv", "TJ",
                                              stream="Natural gas") - 1.0), 0.05),
    ("residential CRT own-scope agreement", "residential", "00_abstract.tex",
     r"within \\SI\{([\d]+)\}\{\\percent\} on its own scope",
     lambda: 100.0 * (_first_where("residential_official_comparison_2024.csv",
                                   "own_Mt_co2e", benchmark_id="crt2022")
                      / _first_where("residential_official_comparison_2024.csv",
                                     "official_Mt_co2e", benchmark_id="crt2022")
                      - 1.0), 0.4),
    ("residential dung factor", "residential", "00_abstract.tex",
     r"a factor of \\num\{([\d.]+)\} that mass conservation",
     lambda: _first_where("residential_dung_ledger_2024.csv", "Mt_air_dry",
                          configuration="both",
                          claimant="Diverted to fuel (agriculture ledger)")
             / _first_where("residential_dung_ledger_2024.csv", "Mt_air_dry",
                            configuration="S",
                            claimant="Household combustion (1.A.4.b)"), 0.0),
    ("residential share range low", "residential", "00_abstract.tex",
     r"\(\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\}",
     lambda: float(next(r for r in _rows("residential_configurations_2024.csv")
                        if r["configuration"] == "S")["national_share_pct"]), 0.05),
    ("residential share range high", "residential", "00_abstract.tex",
     r"\(\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\}",
     lambda: float(next(r for r in _rows("residential_configurations_2024.csv")
                        if r["configuration"] == "L")["national_share_pct"]), 0.05),
    ("residential PM range low", "residential", "00_abstract.tex",
     r"\\SIrange\{([\d]+)\}\{[\d]+\}\{\\kilo\\tonne\} of gross primary",
     lambda: float(next(r for r in _rows("residential_configurations_2024.csv")
                        if r["configuration"] == "S")["pm25_kt"]), 0.7),
    ("residential PM range high", "residential", "00_abstract.tex",
     r"\\SIrange\{[\d]+\}\{([\d]+)\}\{\\kilo\\tonne\} of gross primary",
     lambda: float(next(r for r in _rows("residential_configurations_2024.csv")
                        if r["configuration"] == "L")["pm25_kt"]), 0.7),
    # rc67: the bridge starts from the reference (survey dung) and has no configuration
    # wedge, so the reference at the matched year is endpoint A less the year wedge, and
    # configuration L at the matched year is the bridge's memo row.
    ("residential CCAC reference gap", "residential", "00_abstract.tex",
     r"falls within \\SI\{([\d]+)\}\{\\percent\} of the independent CCAC",
     lambda: 100.0 * ((_cell("residential_ccac_bridge_2024.csv", "item",
                             "ENDPOINT A: this inventory, FY2023-24 (reference)",
                             "pm25_kt")
                       - _cell("residential_ccac_bridge_2024.csv", "item",
                               "WEDGE: inventory year", "pm25_kt"))
                      / _cell("residential_ccac_bridge_2024.csv", "item",
                              "ENDPOINT B: CCAC/SEI implied residential, 2021",
                              "pm25_kt") - 1.0), 0.6),
    ("residential CCAC L multiple", "residential", "00_abstract.tex",
     r"configuration~L is \\num\{([\d.]+)\} times",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "MEMO: configuration L at the matched year", "pm25_kt")
             / _cell("residential_ccac_bridge_2024.csv", "item",
                     "ENDPOINT B: CCAC/SEI implied residential, 2021",
                     "pm25_kt"), 0.05),
    ("residential nitrogen", "residential", "01_introduction.tex",
     r"nowhere was elsewhere: \\SI\{([\d.]+)\}\{\\mega\\tonne\} of",
     lambda: _residential_dung_chain()[0], 0.005),
    ("residential unobserved cake", "residential", "01_introduction.tex",
     r"leaving \\SI\{([\d.]+)\}\{\\mega\\tonne\} with no observed",
     lambda: _first_where("residential_dung_ledger_2024.csv", "Mt_air_dry",
                          configuration="both",
                          claimant="Diverted to fuel (agriculture ledger)")
             - _first_where("residential_dung_ledger_2024.csv", "Mt_air_dry",
                            configuration="S",
                            claimant="Household combustion (1.A.4.b)"), 0.0),
    ("residential biomass energy share", "residential", "02_related_work.tex",
     r"biomass is \\SI\{([\d.]+)\}\{\\percent\} of household energy",
     lambda: sum(_first_where("residential_fuel_2024.csv", "share_pct", stream=s)
                 for s in ("Dung cake", "Firewood", "Crop residues", "Charcoal")),
     0.05),
    ("residential gas CO2", "residential", "03_study_area_and_data.tex",
     r"Natural gas alone is \\SI\{([\d.]+)\}\{\\mega\\tonne\} of \\COtwo\{\}",
     lambda: _first_where("residential_by_stream_2024.csv", "co2e_Mt_AR5",
                          subitem="Natural gas CO2"), 0.0),
    ("residential gas emission share", "residential", "03_study_area_and_data.tex",
     r"---\\SI\{([\d]+)\}\{\\percent\} of the sector's",
     lambda: 100.0 * sum(float(r["co2e_Mt_AR5"])
                         for r in _rows("residential_by_stream_2024.csv")
                         if r["subitem"].startswith("Natural gas"))
             / _cell("residential_totals_2024.csv", "category",
                     "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential VS", "residential", "03_study_area_and_data.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of ash-free volatile solids",
     lambda: _residential_dung_chain()[1], 0.005),
    # rc67: the sentence states the LEDGER chain (volatile solids to total dry solids to
    # air-dry cake), which is the diverted supply and configuration L. The engine's own
    # dry-solids accessor now returns the reference stream's survey quantity, so this
    # reads the diverted dry solids from the residual ledger instead.
    ("residential TS", "residential", "03_study_area_and_data.tex",
     r"\\SI\{[\d.]+\}\{\\mega\\tonne\} of ash-free volatile solids "
     r"\$\\rightarrow\$ \\SI\{([\d.]+)\}\{\}",
     lambda: _first_where("pakemis_dung_residual_ledger.csv", "diverted_dry_solids_kt",
                          species="ALL") / 1000.0, 0.005),
    ("residential firewood quantity", "residential", "03_study_area_and_data.tex",
     r"---\\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry wood",
     lambda: float(next(r for r in _rows("residential_hies_comparison_2024.csv")
                        if r["fuel"] == "firewood")["hies2425_annual"]) / 1e9, 0.0),
    ("residential top1 share now", "residential", "03_study_area_and_data.tex",
     r"carrying \\SI\{([\d]+)\}\{\\percent\} of the weighted",
     lambda: 100.0 * float(next(
         r for r in _data_rows(os.path.join("activity", "residential", "hies",
                                            "hies_diagnostics.csv"))
         if r["fuel"] == "firewood" and r["survey"] == "hies2025")
         ["top1pct_hh_share_of_total"]), 0.1),
    ("residential top1 share then", "residential", "03_study_area_and_data.tex",
     r"against \\SI\{([\d]+)\}\{\} in 2018--19",
     lambda: 100.0 * float(next(
         r for r in _data_rows(os.path.join("activity", "residential", "hies",
                                            "hies_diagnostics.csv"))
         if r["fuel"] == "firewood" and r["survey"] == "hies2019")
         ["top1pct_hh_share_of_total"]), 0.3),
    ("residential per-user low", "residential", "03_study_area_and_data.tex",
     r"in the \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\kilo\\gram\} band",
     lambda: min(float(r["per_user_hh_day"])
                 for r in _data_rows(os.path.join("activity", "residential", "hies",
                                                  "hies_diagnostics.csv"))
                 if r["fuel"] == "firewood"), 0.05),
    ("residential per-user high", "residential", "03_study_area_and_data.tex",
     r"in the \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\kilo\\gram\} band",
     lambda: max(float(r["per_user_hh_day"])
                 for r in _data_rows(os.path.join("activity", "residential", "hies",
                                                  "hies_diagnostics.csv"))
                 if r["fuel"] == "firewood"), 0.05),
    ("residential 1819 firewood", "residential", "03_study_area_and_data.tex",
     r"earlier, gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}---within",
     lambda: float(next(r for r in _rows("residential_hies_comparison_2024.csv")
                        if r["fuel"] == "firewood")["hies1819_annual"]) / 1e9, 0.0),
    ("residential rounds agreement", "residential", "03_study_area_and_data.tex",
     r"---within \\SI\{([\d]+)\}\{\\percent\}\. FAOSTAT",
     lambda: 100.0 * (float(next(
         r for r in _rows("residential_hies_comparison_2024.csv")
         if r["fuel"] == "firewood")["hies2425_annual"])
         / float(next(r for r in _rows("residential_hies_comparison_2024.csv")
                      if r["fuel"] == "firewood")["hies1819_annual"]) - 1.0), 1.0),
    ("residential FAOSTAT above", "residential", "03_study_area_and_data.tex",
     r"sits \\SI\{([\d]+)\}\{\\percent\} above the",
     lambda: 100.0 * (1.0 / float(next(
         r for r in _rows("residential_hies_comparison_2024.csv")
         if r["fuel"] == "firewood")["ratio_hies_over_engine"]) - 1.0), 1.0),
    ("residential SE 2425", "residential", "03_study_area_and_data.tex",
     r"design SE is \\SI\{([\d.]+)\}\{\\percent\} for the 2024--25",
     lambda: float(next(r for r in _data_rows(os.path.join(
         "activity", "residential", "hies", "hies_diagnostics.csv"))
         if r["fuel"] == "firewood" and r["survey"] == "hies2025")
         ["design_se_pct_of_total"]), 0.05),
    ("residential SE 1819", "residential", "03_study_area_and_data.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\} for 2018--19",
     lambda: float(next(r for r in _data_rows(os.path.join(
         "activity", "residential", "hies", "hies_diagnostics.csv"))
         if r["fuel"] == "firewood" and r["survey"] == "hies2019")
         ["design_se_pct_of_total"]), 0.06),
    ("residential biogenic dung", "residential", "04_methods.tex",
     r"\\SI\{([\d]+)\}\{\\giga\\gram\} from dung cake",
     lambda: float(re.search(r"([\d.]+) Gg CO2", next(
         r for r in _rows("residential_totals_2024.csv")
         if r["category"].startswith("Biogenic CO2 from dung"))["note"]).group(1)),
     0.5),
    ("residential biogenic firewood", "residential", "04_methods.tex",
     r"\\SI\{([\d]+)\}\{\\giga\\gram\} from firewood",
     lambda: float(re.search(r"([\d.]+) Gg CO2", next(
         r for r in _rows("residential_totals_2024.csv")
         if r["category"].startswith("Biogenic CO2 from firewood"))["note"]).group(1)),
     0.5),
    ("residential biogenic residues", "residential", "04_methods.tex",
     r"\\SI\{([\d]+)\}\{\\giga\\gram\} from crop residues and charcoal",
     lambda: float(re.search(r"([\d.]+) Gg CO2", next(
         r for r in _rows("residential_totals_2024.csv")
         if r["category"].startswith("Biogenic CO2 from crop"))["note"]).group(1))
     + float(re.search(r"([\d.]+) Gg CO2", next(
         r for r in _rows("residential_totals_2024.csv")
         if r["category"].startswith("Biogenic CO2 from charcoal"))["note"]).group(1)),
     0.5),
    ("residential memo L", "residential", "04_methods.tex",
     r"together \(\\SI\{([\d]+)\}\{\} under configuration~L\)",
     lambda: float(next(r for r in _rows("residential_configurations_2024.csv")
                        if r["configuration"] == "L")["memo_biogenic_Gg"]), 0.5),
    ("residential biomass emissions", "residential", "04_methods.tex",
     r"contributes \\SI\{([\d.]+)\}\{\\mega\\tonne\} of the sector's",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("residential_by_stream_2024.csv")
                 if r["gas"] in ("CH4", "N2O")
                 and any(r["subitem"].startswith(b)
                         for b in ("Dung", "Firew", "Crop", "Charc"))), 0.3),
    # rc67: total and memo from the SAME configuration. This added configuration L's
    # memo to the sector total, which was one configuration while L was the reference
    # and became a mixture (the survey total plus the ledger memo) when it stopped being.
    ("residential with-biomass-co2 counterfactual", "residential", "04_methods.tex",
     r"roughly \\SI\{([\d]+)\}\{\\mega\\tonne\} and would be wrong",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR5")
             + float(next(r for r in _rows("residential_configurations_2024.csv")
                          if r["configuration"] == "S")["memo_biogenic_Gg"]) / 1000.0,
     0.5),
    ("residential no-biomass counterfactual", "residential", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} and would miss",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR5")
             - sum(float(r["co2e_Mt_AR5"])
                   for r in _rows("residential_by_stream_2024.csv")
                   if r["gas"] in ("CH4", "N2O")
                   and any(r["subitem"].startswith(b)
                           for b in ("Dung", "Firew", "Crop", "Charc"))), 0.01),
    ("residential residue fuel dry", "residential", "04_methods.tex",
     r"R_\{\\text\{fuel\}\}\$ \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*dry",
     lambda: _first_where("residential_fuel_2024.csv", "TJ",
                          stream="Crop residues") / 13.17 / 1000.0, 0.05),
    ("residential residue air-dry", "residential", "04_methods.tex",
     r"the ledger's \\SI\{([\d.]+)\}\{\}",
     lambda: _first_where("residential_fuel_2024.csv", "TJ",
                          stream="Crop residues") / 13.17 / 1000.0 / 0.88, 0.06),
    ("residential generator petrol", "residential", "04_methods.tex",
     r"gives \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of petrol",
     lambda: _first_where("residential_fuel_2024.csv", "TJ", stream="Generators")
             / 44.3, 0.1),
    ("residential CO2 share", "residential", "04b_emission_factors.tex",
     r"\\COtwo\{\} is \\SI\{([\d]+)\}\{\\percent\} of the sector's reported",
     lambda: 100.0 * sum(float(r["co2e_Mt_AR5"])
                         for r in _rows("residential_by_stream_2024.csv")
                         if r["gas"] == "CO2")
             / _cell("residential_totals_2024.csv", "category",
                     "Residential fuel combustion", "co2e_Mt_AR5"), 0.1),
    ("residential methane total", "residential", "04b_emission_factors.tex",
     r"methane totals \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} of which",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("residential_by_stream_2024.csv")
                 if r["gas"] == "CH4"), 0.01),
    ("residential fossil methane", "residential", "04b_emission_factors.tex",
     r"of which\s*\\SI\{([\d.]+)\}\{\} is fossil",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("residential_by_stream_2024.csv")
                 if r["gas"] == "CH4" and r["fossil"] == "True"), 0.005),
    ("residential EDGAR benchmark", "residential", "05_validation.tex",
     r"at \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} for 2024",
     lambda: _first_where("national_benchmark_comparison.csv", "benchmark_Mt_co2e",
                          source="EDGAR",
                          engine_category="Residential fuel combustion"), 0.0),
    ("residential EDGAR ratio reference", "residential", "05_validation.tex",
     r"\(\\SI\{([\d]+)\}\{\\percent\} of EDGAR\)",
     lambda: 100.0 * _cell("residential_totals_2024.csv", "category",
                           "Residential fuel combustion", "co2e_Mt_AR5")
             / _first_where("national_benchmark_comparison.csv",
                            "benchmark_Mt_co2e", source="EDGAR",
                            engine_category="Residential fuel combustion"), 0.3),
    ("residential EDGAR ratio L", "residential", "05_validation.tex",
     r"under configuration~L \(\\SI\{([\d]+)\}\{\\percent\}\)",
     lambda: 100.0 * _cell("residential_totals_2024.csv", "category",
                           "Sensitivity: dung configuration L (all diverted dung)",
                           "co2e_Mt_AR5")
             / _first_where("national_benchmark_comparison.csv",
                            "benchmark_Mt_co2e", source="EDGAR",
                            engine_category="Residential fuel combustion"), 0.5),
    ("residential EDGAR gap", "residential", "05_validation.tex",
     r"remaining \\SI\{([\d.]+)\}\{\\mega\\tonne\} difference",
     lambda: _first_where("national_benchmark_comparison.csv", "benchmark_Mt_co2e",
                          source="EDGAR",
                          engine_category="Residential fuel combustion")
             - _cell("residential_totals_2024.csv", "category",
                     "Residential fuel combustion", "co2e_Mt_AR5"), 0.01),
    ("residential low hypothetical", "residential", "05_validation.tex",
     r"the ratio would read\s*\\SI\{([\d]+)\}\{\\percent\} and would read as",
     lambda: 100.0 * _cell("residential_totals_2024.csv", "category",
                           "Residential fuel combustion", "co2e_Mt_AR5")
             / 1.2 / _first_where("national_benchmark_comparison.csv",
                                  "benchmark_Mt_co2e", source="EDGAR",
                                  engine_category="Residential fuel combustion"),
     0.4),
    ("residential BUR component", "residential", "05_validation.tex",
     r"residential component of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("residential_official_comparison_2024.csv",
                          "official_Mt_co2e", benchmark_id="bur1res"), 0.0),
    ("residential matched FY2018", "residential", "05_validation.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}, putting the BUR at",
     lambda: _first_where("residential_official_comparison_2024.csv",
                          "own_Mt_co2e", benchmark_id="bur1res"), 0.0),
    ("residential BUR ratio", "residential", "05_validation.tex",
     r"putting the BUR at \\num\{([\d.]+)\} of it",
     lambda: _first_where("residential_official_comparison_2024.csv",
                          "ratio_official_over_own", benchmark_id="bur1res"), 0.0),
    ("residential two-fuel energy", "residential", "05_validation.tex",
     r"fuels---\\SI\{([\d]+)\}\{\\tera\\joule\} in this inventory",
     lambda: _first_where("residential_fuel_2024.csv", "TJ", stream="Dung cake")
             + _first_where("residential_fuel_2024.csv", "TJ",
                            stream="Firewood"), 0.0),
    ("residential OGRA gas TJ", "residential", "05_validation.tex",
     r"against this inventory's \\SI\{([\d]+)\}\{\} from OGRA",
     lambda: _first_where("residential_fuel_2024.csv", "TJ",
                          stream="Natural gas"), 0.0),
    ("residential gas derivations apart", "residential", "05_validation.tex",
     r"table---\\SI\{([\d.]+)\}\{\\percent\} apart",
     lambda: 100.0 * (288493.0 / _first_where("residential_fuel_2024.csv", "TJ",
                                              stream="Natural gas") - 1.0), 0.05),
    ("residential CRT figure", "residential", "05_validation.tex",
     r"filing reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} against this",
     lambda: _first_where("residential_official_comparison_2024.csv",
                          "official_Mt_co2e", benchmark_id="crt2022"), 0.0),
    ("residential CRT own", "residential", "05_validation.tex",
     r"against this inventory's \\SI\{([\d.]+)\}\{\}---within",
     lambda: _first_where("residential_official_comparison_2024.csv",
                          "own_Mt_co2e", benchmark_id="crt2022"), 0.0),
    ("residential CCAC implied", "residential", "05_validation.tex",
     r"implies about \\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "ENDPOINT B: CCAC/SEI implied residential, 2021", "pm25_kt"), 0.0),
    ("residential bridge start", "residential", "05_validation.tex",
     r"bridge steps from this inventory's \\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "ENDPOINT A: this inventory, FY2023-24 (reference)",
                   "pm25_kt"), 0.0),
    ("residential year wedge", "residential", "05_validation.tex",
     r"inventory year \(\\SI\{([\d]+)\}\{\\kilo\\tonne\}, from the time series\)",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "WEDGE: inventory year", "pm25_kt"), 0.0),
    # rc67: the configuration wedge is gone from the bridge and from the sentence (it was
    # 314 kt, the step needed to leave configuration L). What the product carries in its
    # place is a memo row, configuration L at the matched year, which the paragraph now
    # prints as a row beside the bridge and not a step of it.
    ("residential bridge L memo", "residential", "05_validation.tex",
     r"configuration~L at the matched year, \\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "MEMO: configuration L at the matched year", "pm25_kt"), 0.0),
    ("residential residue wedge", "residential", "05_validation.tex",
     r"residue fuel set \(\\SI\{([\d]+)\}\{\}\)",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "WEDGE: fuel set (crop residues)", "pm25_kt"), 0.0),
    ("residential bridge residual", "residential", "05_validation.tex",
     r"residual of\s*\\SI\{(-[\d]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "UNEXPLAINED RESIDUAL", "pm25_kt"), 0.0),
    ("residential L multiple validation", "residential", "05_validation.tex",
     r"stands \\num\{([\d.]+)\} times above the assessment",
     lambda: _cell("residential_ccac_bridge_2024.csv", "item",
                   "MEMO: configuration L at the matched year", "pm25_kt")
             / _cell("residential_ccac_bridge_2024.csv", "item",
                     "ENDPOINT B: CCAC/SEI implied residential, 2021",
                     "pm25_kt"), 0.05),
    ("residential AR6", "residential", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} on AR6",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR6"), 0.0),
    ("residential exclusion pct", "residential", "06_results.tex",
     r"moves the sector by \\SI\{([\d]+)\}\{\\percent\}---from",
     lambda: 100.0 * (1.0 - _cell("residential_totals_2024.csv", "category",
                                  "Sensitivity: firewood excluded", "co2e_Mt_AR5")
                      / _cell("residential_totals_2024.csv", "category",
                              "Residential fuel combustion", "co2e_Mt_AR5")), 0.5),
    ("residential firewood energy share", "residential", "06_results.tex",
     r"fuel supplying\s*\\SI\{([\d]+)\}\{\\percent\} of household energy",
     lambda: _first_where("residential_fuel_2024.csv", "share_pct",
                          stream="Firewood"), 0.7),
    ("residential config gap", "residential", "06_results.tex",
     r"total by \\SI\{([\d.]+)\}\{\\mega\\tonne\}, the particulate",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: dung configuration L (all diverted dung)",
                   "co2e_Mt_AR5")
             - _cell("residential_totals_2024.csv", "category",
                     "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential series start", "residential", "06_results.tex",
     r"FY2015--16 through FY2024--25: \\SI\{([\d.]+)\}\{\} to",
     lambda: _first_where("residential_timeseries.csv", "co2e_Mt_AR5",
                          fiscal_year="2016"), 0.0),
    ("residential series end", "residential", "06_results.tex",
     r"FY2015--16 through FY2024--25: \\SI\{[\d.]+\}\{\} to\s*"
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("residential_timeseries.csv", "co2e_Mt_AR5",
                          fiscal_year="2025"), 0.0),
    ("residential January PM", "residential", "06_results.tex",
     r"January at \\SI\{([\d]+)\}\{\\kilo\\tonne\} of \\PM\{\} per month",
     lambda: max((lambda m: sum(float(r["pm25_kt"])
                                for r in _rows("residential_monthly_2024.csv")
                                if r["month"] == m))(mm)
                 for mm in {r["month"]
                            for r in _rows("residential_monthly_2024.csv")}), 0.5),
    ("residential trough month PM", "residential", "06_results.tex",
     r"against July's \\SI\{([\d]+)\}\{\}",
     lambda: min((lambda m: sum(float(r["pm25_kt"])
                                for r in _rows("residential_monthly_2024.csv")
                                if r["month"] == m))(mm)
                 for mm in {r["month"]
                            for r in _rows("residential_monthly_2024.csv")}), 0.5),
    ("residential provincial Punjab", "residential", "06_results.tex",
     r"\\caption\{Punjab \\SI\{([\d.]+)\}\{\\mega\\tonne\}, Sindh",
     lambda: _first_where("residential_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Punjab"), 0.0),
    ("residential provincial Sindh", "residential", "06_results.tex",
     r"Sindh \\SI\{([\d.]+)\}\{\\mega\\tonne\}, Khyber",
     lambda: _first_where("residential_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Sindh"), 0.0),
    ("residential provincial KP", "residential", "06_results.tex",
     r"Pakhtunkhwa\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}, Balochistan",
     lambda: _first_where("residential_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Khyber Pakhtunkhwa"), 0.0),
    ("residential provincial Balochistan", "residential", "06_results.tex",
     r"Balochistan \\SI\{([\d.]+)\}\{\\mega\\tonne\}\. Each stream",
     lambda: _first_where("residential_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Balochistan"), 0.0),
    ("residential Lahore", "residential", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} because gas is urban",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("residential_district_2024.csv")
                 if "Lahore" in r["district"]), 0.0),
    ("residential Faisalabad", "residential", "06_results.tex",
     r"with Faisalabad \(\\SI\{([\d.]+)\}\{\}\)",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("residential_district_2024.csv")
                 if "Faisalabad" in r["district"]), 0.0),
    ("residential Rawalpindi", "residential", "06_results.tex",
     r"Rawalpindi \(\\SI\{([\d.]+)\}\{\}\) behind it",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("residential_district_2024.csv")
                 if "Rawalpindi" in r["district"]), 0.0),
    ("residential MC within", "residential", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\}\$ with parameters shared within",
     lambda: float(next(r for r in _rows("national_uncertainty_montecarlo.csv")
                        if r["scenario"] == "within_sector"
                        and r["name"] == "Residential fuel combustion")
                   ["rel_uncert_pct_MC_95"]), 0.05),
    ("residential MC cross", "residential", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\}\$ with factors correlated across",
     lambda: float(next(r for r in _rows("national_uncertainty_montecarlo.csv")
                        if r["scenario"] == "cross_sector"
                        and r["name"] == "Residential fuel combustion")
                   ["rel_uncert_pct_MC_95"]), 0.05),
    ("residential grouped band prose", "residential", "06_results.tex",
     r"analytic \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ grouped figure",
     lambda: _first_where("residential_uncertainty_2024.csv",
                          "approach1_pct_grouped",
                          category="Residential fuel combustion"), 0.05),
    ("residential variance share", "residential", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of national Approach-1 variance",
     lambda: _first_where("national_key_categories.csv",
                          "variance_share_pct_independent_approx",
                          ipcc_code="1.A.4.b"), 0.0),
    ("residential road PM", "residential", "06b_air_pollutants.tex",
     r"transport's exhaust \\PM\{\} of \\SI\{([\d.]+)\}\{\\kilo\\tonne\} under the reference",
     lambda: _sum_where("transport_air_pollutants_2024.csv", "emissions_kt",
                        pollutant="PM2.5", process="exhaust"), 0.05),
    ("residential waste PM aside", "residential", "06b_air_pollutants.tex",
     r"open waste burning at\s*\\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _first_where("waste_air_pollutants_2024.csv", "emissions_kt",
                          pollutant="PM2.5"), 0.0),
    ("residential field burning PM aside", "residential", "06b_air_pollutants.tex",
     r"field burning at \\SI\{([\d.]+)\}\{\}",
     lambda: sum(float(r["emissions_kt"]) for r in _rows("air_pollutants_2024.csv")
                 if r["subitem"].startswith("Residue burning PM2.5")), 0.0),
    ("residential fossil NOx", "residential", "06b_air_pollutants.tex",
     r"contributing \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of \\NOx\{\}",
     lambda: sum(float(r["emissions_kt"])
                 for r in _rows("residential_air_pollutants_2024.csv")
                 if r["pollutant"] == "NOx"
                 and any(r["subitem"].startswith(f)
                         for f in ("Natural", "LPG", "Kerosene", "Coal"))), 0.2),
    ("residential fossil support", "residential", "07_discussion.tex",
     r"by themselves support about \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("residential_by_stream_2024.csv")
                 if any(r["subitem"].startswith(f)
                        for f in ("Natural", "LPG", "Kerosene", "Coal",
                                  "Generators"))), 0.05),
    # rc67: the configuration axis runs from the reference (the survey) to configuration
    # L, and the firewood cases are priced on the reference, so the sentence no longer
    # prints configuration L with firewood at its upper bound - no product carries it.
    ("residential axis low", "residential", "07_discussion.tex",
     r"the wider one: \\SI\{([\d.]+)\}\{\} \(the reference\)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential axis high", "residential", "07_discussion.tex",
     r"to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} \(configuration~L\)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: dung configuration L (all diverted dung)",
                   "co2e_Mt_AR5"), 0.0),
    ("residential firewood axis low", "residential", "07_discussion.tex",
     r"firewood axis spans \\SI\{([\d.]+)\}\{\} to",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood excluded", "co2e_Mt_AR5"), 0.0),
    ("residential firewood axis high", "residential", "07_discussion.tex",
     r"firewood axis spans \\SI\{[\d.]+\}\{\} to\s*\\SI\{([\d.]+)\}\{\}",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood high", "co2e_Mt_AR5"), 0.0),

    ("residential memo scale intro", "residential", "01_introduction.tex",
     r"of the \\SI\{([\d]+)\}\{\\mega\\tonne\}-scale biogenic",
     lambda: float(next(r for r in _rows("residential_configurations_2024.csv")
                        if r["configuration"] == "S")["memo_biogenic_Gg"]) / 1000.0,
     0.3),
    ("residential MTF clean share", "residential", "02_related_work.tex",
     r"clean-fuel main-stove share of \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: float(next(r for r in _data_rows(os.path.join(
         "activity", "residential", "stove_mix_mtf.csv"))
         if r["stove_class"] == "clean_fuel_main_stove")["share_pct"]), 0.0),
    ("residential MTF rural traditional", "residential", "02_related_work.tex",
     r"three-stone/open-fire stoves \(\\SI\{([\d.]+)\}\{\\percent\}\)",
     lambda: float(next(r for r in _data_rows(os.path.join(
         "activity", "residential", "stove_mix_mtf.csv"))
         if r["stove_class"] == "traditional_or_three_stone_open_fire")
         ["share_pct"]), 0.0),
    ("residential MTF stacking", "residential", "02_related_work.tex",
     r"stove stacking at\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 - float(next(r for r in _data_rows(os.path.join(
         "activity", "residential", "stove_mix_mtf.csv"))
         if r["stove_class"] == "single_stove_households")["share_pct"]), 0.0),
    ("residential coal quantity", "residential", "03_study_area_and_data.tex",
     r"measured them in passing, at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: (lambda r: float(r["weighted_users"]) * float(r["per_user_hh_day"])
              * 365.0 / 1e6)(next(
         x for x in _data_rows(os.path.join("activity", "residential", "hies",
                                            "hies_diagnostics.csv"))
         if x["fuel"] == "coal" and x["survey"] == "hies2025")), 0.05),
    ("residential coal SE", "residential", "03_study_area_and_data.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} on the 2024--25 coal total",
     lambda: float(next(x for x in _data_rows(os.path.join(
         "activity", "residential", "hies", "hies_diagnostics.csv"))
         if x["fuel"] == "coal" and x["survey"] == "hies2025")
         ["design_se_pct_of_total"]), 0.2),
    ("residential coal top1", "residential", "03_study_area_and_data.tex",
     r"one percent of them carrying \\SI\{([\d]+)\}\{\\percent\} of it",
     lambda: 100.0 * float(next(x for x in _data_rows(os.path.join(
         "activity", "residential", "hies", "hies_diagnostics.csv"))
         if x["fuel"] == "coal" and x["survey"] == "hies2025")
         ["top1pct_hh_share_of_total"]), 0.3),
    ("residential charcoal SE", "residential", "03_study_area_and_data.tex",
     r"and \\SI\{([\d]+)\}\{\} on charcoal",
     lambda: float(next(x for x in _data_rows(os.path.join(
         "activity", "residential", "hies", "hies_diagnostics.csv"))
         if x["fuel"] == "charcoal" and x["survey"] == "hies2025")
         ["design_se_pct_of_total"]), 0.2),
    ("residential sensitivity caption excluded", "residential", "06_results.tex",
     r"firewood excluded entirely \(\\SI\{([\d.]+)\}\{\}\)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood excluded", "co2e_Mt_AR5"), 0.0),
    ("residential sensitivity caption legacy", "residential", "06_results.tex",
     r"legacy VS dung basis\s*\(\\SI\{([\d.]+)\}\{\}\)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: dung legacy VS basis", "co2e_Mt_AR5"), 0.0),
    ("residential sensitivity caption low", "residential", "06_results.tex",
     r"quantity \$-35\\%\$ \(\\SI\{([\d.]+)\}\{\}\)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood low", "co2e_Mt_AR5"), 0.0),
    ("residential sensitivity caption high", "residential", "06_results.tex",
     r"and \$\+35\\%\$\s*\(\\SI\{([\d.]+)\}\{\}\)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood high", "co2e_Mt_AR5"), 0.0),
    ("residential ledger cake", "residential", "06_results.tex",
     r"implies\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry cake",
     lambda: _first_where("residential_dung_ledger_2024.csv", "Mt_air_dry",
                          configuration="both",
                          claimant="Diverted to fuel (agriculture ledger)"), 0.0),
    ("residential survey cake", "residential", "06_results.tex",
     r"the survey series puts \\SI\{([\d.]+)\}\{\} in\s*households",
     lambda: _first_where("residential_dung_ledger_2024.csv", "Mt_air_dry",
                          configuration="S",
                          claimant="Household combustion (1.A.4.b)"), 0.0),
    ("residential stove-mix scenario", "residential", "06b_air_pollutants.tex",
     r"would lower \\PM\{\} to\s*\\SI\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: _first_where("residential_uncertainty_scenarios_2024.csv",
                          "deterministic",
                          structural_scenario="stove_mix_mtf"), 0.0),
    ("residential residue-family scenario", "residential", "06b_air_pollutants.tex",
     r"domestic-biofuel family would give \\SI\{([\d]+)\}\{\}",
     lambda: _first_where("residential_uncertainty_scenarios_2024.csv",
                          "deterministic",
                          structural_scenario="residue_factor_family"), 0.0),

    # ---- residential, rc67: the survey is the reference for household dung ----
    # The sentences below were rewritten when the roles of the two dung configurations
    # swapped (S, the household survey, became the reference; L, all diverted dung burned
    # in households, became the alternative). Each claim reads the product row that now
    # carries the quantity its sentence states, at zero tolerance beyond the printed
    # precision. The four helpers they share are beside _residential_dung_chain.
    # -- abstract
    ("residential abstract diverted cake", "residential", "00_abstract.tex",
     r"implies\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry cake where",
     lambda: _residential_dung_survey("diverted"), 0.0),
    ("residential abstract survey cake", "residential", "00_abstract.tex",
     r"puts \\SI\{([\d.]+)\}\{\} in households",
     lambda: _residential_dung_survey("household"), 0.0),
    ("residential abstract round ratio", "residential", "00_abstract.tex",
     r"disagree by a factor of \\num\{([\d.]+)\} per household",
     lambda: _residential_dung_survey("round_ratio"), 0.0),
    # -- introduction
    ("residential intro share reference", "residential", "01_introduction.tex",
     r"\\SI\{([\d.]+)\}\{\} or \\SI\{[\d.]+\}\{\\percent\} of Pakistan's emissions",
     lambda: _residential_config("S", "national_share_pct"), 0.0),
    ("residential intro share L", "residential", "01_introduction.tex",
     r"\\SI\{[\d.]+\}\{\} or \\SI\{([\d.]+)\}\{\\percent\} of Pakistan's emissions",
     lambda: _residential_config("L", "national_share_pct"), 0.0),
    ("residential intro biomass energy share", "residential", "01_introduction.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} of household energy produces",
     lambda: sum(_first_where("residential_fuel_2024.csv", "share_pct", stream=s)
                 for s in ("Dung cake", "Firewood", "Crop residues", "Charcoal")), 0.0),
    # -- related work
    ("residential related-work biomass emission share", "residential",
     "02_related_work.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} of its reported emissions",
     lambda: _residential_biomass_share(), 0.0),
    # -- data
    ("residential activity caption biomass share", "residential",
     "03_study_area_and_data.tex",
     r"together---is \\SI\{([\d.]+)\}\{\\percent\} of\s*household energy",
     lambda: sum(_first_where("residential_fuel_2024.csv", "share_pct", stream=s)
                 for s in ("Dung cake", "Firewood", "Crop residues", "Charcoal")), 0.0),
    ("residential gas energy share", "residential", "03_study_area_and_data.tex",
     r"reported emissions from \\SI\{([\d]+)\}\{\\percent\} of its energy",
     lambda: _first_where("residential_fuel_2024.csv", "share_pct",
                          stream="Natural gas"), 0.0),
    ("residential chain air-dry", "residential", "03_study_area_and_data.tex",
     r"\\rightarrow\$ \\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry cake",
     lambda: _residential_dung_survey("diverted"), 0.0),
    ("residential dung round 2018-19", "residential", "03_study_area_and_data.tex",
     r"\(\\SI\{([\d.]+)\}\{\\mega\\tonne\} in 2018--19, \\SI\{[\d.]+\}\{\} in 2024--25\)",
     lambda: _first_where("residential_hies_comparison_2024.csv", "hies1819_annual",
                          fuel="dung_cake") / 1e9, 0.0),
    ("residential dung round 2024-25", "residential", "03_study_area_and_data.tex",
     r"\(\\SI\{[\d.]+\}\{\\mega\\tonne\} in 2018--19, \\SI\{([\d.]+)\}\{\} in 2024--25\)",
     lambda: _first_where("residential_hies_comparison_2024.csv", "hies2425_annual",
                          fuel="dung_cake") / 1e9, 0.0),
    ("residential reference dung", "residential", "03_study_area_and_data.tex",
     r"takes \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*\(\\SI\{[\d.]+\}\{\} of total dry solids\)",
     lambda: _residential_dung_survey("household"), 0.0),
    ("residential reference dung dry solids", "residential",
     "03_study_area_and_data.tex",
     r"\(\\SI\{([\d.]+)\}\{\} of total dry solids\)",
     lambda: _residential_dung_chain()[2], 0.0),
    ("residential L books all", "residential", "03_study_area_and_data.tex",
     r"books all \\SI\{([\d.]+)\}\{\\mega\\tonne\} to household",
     lambda: _residential_dung_survey("diverted"), 0.0),
    ("residential round ratio, data", "residential", "03_study_area_and_data.tex",
     r"rounds disagree by a factor of\s*\\num\{([\d.]+)\} per household",
     lambda: _residential_dung_survey("round_ratio"), 0.0),
    ("residential dung SE 2425", "residential", "03_study_area_and_data.tex",
     r"design SE of the dung total is \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _residential_dung_diag("hies2025", "design_se_pct_of_total"), 0.0),
    ("residential dung SE 1819", "residential", "03_study_area_and_data.tex",
     r"2024--25 and \\SI\{([\d.]+)\}\{\} in 2018--19",
     lambda: _residential_dung_diag("hies2019", "design_se_pct_of_total"), 0.0),
    ("residential dung top5 share 2425", "residential", "03_study_area_and_data.tex",
     r"hold \\SI\{([\d.]+)\}\{\\percent\} of the reported dung",
     lambda: 100.0 * _residential_dung_diag("hies2025", "top5pct_hh_share_of_total"),
     0.0),
    ("residential dung top5 share 1819", "residential", "03_study_area_and_data.tex",
     r"against \\SI\{([\d.]+)\}\{\} in\s*the earlier round",
     lambda: 100.0 * _residential_dung_diag("hies2019", "top5pct_hh_share_of_total"),
     0.0),
    ("residential dung survey activity width", "residential",
     "03_study_area_and_data.tex",
     r"activity term therefore carries \\SI\{([\d]+)\}\{\\percent\}",
     lambda: _first_where("residential_uncertainty_inputs_2024.csv", "uncert_pct_95",
                          variable="Household dung cake (survey series)"), 0.0),
    # -- methods
    ("residential memo reference", "residential", "04_methods.tex",
     r"\\SI\{([\d]+)\}\{\\giga\\gram\} together",
     lambda: _residential_config("S", "memo_biogenic_Gg"), 0.0),
    ("residential methods biomass energy share", "residential", "04_methods.tex",
     r"Biomass is \\SI\{([\d.]+)\}\{\\percent\} of household energy",
     lambda: sum(_first_where("residential_fuel_2024.csv", "share_pct", stream=s)
                 for s in ("Dung cake", "Firewood", "Crop residues", "Charcoal")), 0.0),
    ("residential methods total", "residential", "04_methods.tex",
     r"of the sector's\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}---",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential methods biomass emission share", "residential", "04_methods.tex",
     r"---\\SI\{([\d]+)\}\{\\percent\}---entirely as methane",
     lambda: _residential_biomass_share(), 0.0),
    ("residential methods gas energy share", "residential", "04_methods.tex",
     r"Natural gas is \\SI\{([\d.]+)\}\{\\percent\} of the energy",
     lambda: _first_where("residential_fuel_2024.csv", "share_pct",
                          stream="Natural gas"), 0.0),
    ("residential methods gas emission share", "residential", "04_methods.tex",
     r"of the energy and \\SI\{([\d]+)\}\{\\percent\} of the\s*emissions, because",
     lambda: 100.0 * sum(float(r["co2e_Mt_AR5"])
                         for r in _rows("residential_by_stream_2024.csv")
                         if r["subitem"].startswith("Natural gas"))
             / _cell("residential_totals_2024.csv", "category",
                     "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential residue bracket low scenario", "residential", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} for the sector at the low end",
     lambda: _first_where("residential_uncertainty_scenarios_2024.csv", "deterministic",
                          structural_scenario="residue_fuel_survey_bracket_low"), 0.0),
    ("residential residue bracket high scenario", "residential", "04_methods.tex",
     r"at the low end and \\SI\{([\d.]+)\}\{\} at the high end",
     lambda: _first_where("residential_uncertainty_scenarios_2024.csv", "deterministic",
                          structural_scenario="residue_fuel_survey_bracket_high"), 0.0),
    ("residential dung activity width, methods", "residential", "04_methods.tex",
     r"dung activity term carries\s*\\SI\{([\d]+)\}\{\\percent\} under the reference",
     lambda: _first_where("residential_uncertainty_inputs_2024.csv", "uncert_pct_95",
                          variable="Household dung cake (survey series)"), 0.0),
    ("residential ledger chain activity width", "residential", "04_methods.tex",
     r"chain's \\SI\{([\d]+)\}\{\\percent\} applies to configuration~L only",
     lambda: float(next(r for r in _data_rows("residential_params.csv")
                        if r["param"] == "activity_uncert_dung")["value"]), 0.0),
    ("residential survey-rate scenario", "residential", "04_methods.tex",
     r"held to the reference year, \\SI\{([\d.]+)\}\{\\mega\\tonne\} for the sector",
     lambda: _first_where("residential_uncertainty_scenarios_2024.csv", "deterministic",
                          structural_scenario="dung_survey_rate_2018_19"), 0.0),
    ("residential round-as-measured scenario", "residential", "04_methods.tex",
     r"round taken as measured, \\SI\{([\d.]+)\}\{\}",
     lambda: _first_where("residential_uncertainty_scenarios_2024.csv", "deterministic",
                          structural_scenario="dung_survey_round_2024_25_as_measured"),
     0.0),
    # -- emission factors
    ("residential grouped band, factors", "residential", "04b_emission_factors.tex",
     r"figure of \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ \(Section",
     lambda: _first_where("residential_uncertainty_2024.csv", "approach1_pct_grouped",
                          category="Residential fuel combustion"), 0.0),
    # -- validation
    ("residential memo reference, validation", "residential", "05_validation.tex",
     r"decision to hold \\SI\{([\d]+)\}\{\\giga\\gram\}",
     lambda: _residential_config("S", "memo_biogenic_Gg"), 0.0),
    ("residential biomass over CRT activity", "residential", "05_validation.tex",
     r"\\num\{([\d.]+)\} times the filing's whole residential activity",
     lambda: (_first_where("residential_fuel_2024.csv", "TJ", stream="Dung cake")
              + _first_where("residential_fuel_2024.csv", "TJ", stream="Firewood"))
             / _first_where("residential_unfccc_crt_cell_audit_2024.csv", "value",
                            block="category", field="activity_TJ"), 0.0),
    ("residential reference gap validation", "residential", "05_validation.tex",
     r"the reference lands within\s*\\SI\{([\d]+)\}\{\\percent\} of it",
     lambda: 100.0 * ((_residential_ccac("ENDPOINT A")
                       - _residential_ccac("WEDGE: inventory year"))
                      / _residential_ccac("ENDPOINT B") - 1.0), 0.0),
    # -- results
    ("residential memo reference, results", "residential", "06_results.tex",
     r"plus \\SI\{([\d]+)\}\{\\giga\\gram\} of biogenic",
     lambda: _residential_config("S", "memo_biogenic_Gg"), 0.0),
    ("residential results biomass energy share", "residential", "06_results.tex",
     r"Biomass supplies\s*\\SI\{([\d.]+)\}\{\\percent\} of household energy",
     lambda: sum(_first_where("residential_fuel_2024.csv", "share_pct", stream=s)
                 for s in ("Dung cake", "Firewood", "Crop residues", "Charcoal")), 0.0),
    ("residential results biomass emission share", "residential", "06_results.tex",
     r"household energy and \\SI\{([\d]+)\}\{\\percent\} of reported emissions",
     lambda: _residential_biomass_share(), 0.0),
    ("residential results gas energy share", "residential", "06_results.tex",
     r"gas supplies \\SI\{([\d.]+)\}\{\\percent\} of the energy",
     lambda: _first_where("residential_fuel_2024.csv", "share_pct",
                          stream="Natural gas"), 0.0),
    ("residential results gas emission share", "residential", "06_results.tex",
     r"of the energy and \\SI\{([\d]+)\}\{\\percent\} of the emissions",
     lambda: 100.0 * sum(float(r["co2e_Mt_AR5"])
                         for r in _rows("residential_by_stream_2024.csv")
                         if r["subitem"].startswith("Natural gas"))
             / _cell("residential_totals_2024.csv", "category",
                     "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential sensitivity caption L", "residential", "06_results.tex",
     r"configuration~L itself\s*\(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: dung configuration L (all diverted dung)",
                   "co2e_Mt_AR5"), 0.0),
    ("residential sensitivity caption reference", "residential", "06_results.tex",
     r"marks the reference at\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential exclusion from", "residential", "06_results.tex",
     r"---from \\SI\{([\d.]+)\}\{\} to\s*\\SI\{[\d.]+\}\{\\mega\\tonne\}---which",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Residential fuel combustion", "co2e_Mt_AR5"), 0.0),
    ("residential exclusion to", "residential", "06_results.tex",
     r"---from \\SI\{[\d.]+\}\{\} to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}---which",
     lambda: _cell("residential_totals_2024.csv", "category",
                   "Sensitivity: firewood excluded", "co2e_Mt_AR5"), 0.0),
    ("residential 2024-25 round as measured", "residential", "06_results.tex",
     r"round as\s*measured is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("residential_hies_comparison_2024.csv", "hies2425_annual",
                          fuel="dung_cake") / 1e9, 0.0),
    ("residential diverted over survey series", "residential", "06_results.tex",
     r"and \\num\{([\d.]+)\} times the survey series at the reference year",
     lambda: _residential_dung_survey("diverted")
             / _residential_dung_survey("household"), 0.0),
    ("residential round ratio, results", "residential", "06_results.tex",
     r"rounds disagree by a factor of\s*\\num\{([\d.]+)\} per household",
     lambda: _residential_dung_survey("round_ratio"), 0.0),
    ("residential dung top5 share, results", "residential", "06_results.tex",
     r"hold\s*\\SI\{([\d.]+)\}\{\\percent\} of the reported dung",
     lambda: 100.0 * _residential_dung_diag("hies2025", "top5pct_hh_share_of_total"),
     0.0),
    ("residential unresolved cake, configs caption", "residential", "06_results.tex",
     r"under S, \\SI\{([\d.]+)\}\{\\mega\\tonne\} of diverted air-dry cake",
     lambda: _residential_dung_survey("unresolved"), 0.0),
    ("residential CCAC reference gap, results", "residential", "06_results.tex",
     r"configuration S sits within\s*\\SI\{([\d]+)\}\{\\percent\}",
     lambda: 100.0 * ((_residential_ccac("ENDPOINT A")
                       - _residential_ccac("WEDGE: inventory year"))
                      / _residential_ccac("ENDPOINT B") - 1.0), 0.0),
    ("residential CCAC L multiple, results", "residential", "06_results.tex",
     r"while L\s*is \\num\{([\d.]+)\} times above it",
     lambda: _residential_ccac("MEMO: configuration L at the matched year")
             / _residential_ccac("ENDPOINT B"), 0.0),
    ("residential unresolved cake, results", "residential", "06_results.tex",
     r"The \\SI\{([\d.]+)\}\{\\mega\\tonne\} left unresolved",
     lambda: _residential_dung_survey("unresolved"), 0.0),
    ("residential unresolved nitrogen", "residential", "06_results.tex",
     r"holds\s*\\SI\{([\d.]+)\}\{\\kilo\\tonne\} of nitrogen",
     lambda: _first_where("pakemis_dung_residual_ledger.csv", "unresolved_N_kt",
                          species="ALL"), 0.0),
    ("residential fate: non-household burning", "residential", "06_results.tex",
     r"non-household users,\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} more",
     lambda: _first_where("national_dung_variants.csv", "delta_vs_S_Mt_co2e_AR5",
                          variant_id="S_residual_nonhousehold_combustion"), 0.0),
    ("residential fate: return to manure", "residential", "06_results.tex",
     r"returned to manure\s*management, \\SI\{([\d.]+)\}\{\} more",
     lambda: _first_where("national_dung_variants.csv", "delta_vs_S_Mt_co2e_AR5",
                          variant_id="S_residual_return_to_manure"), 0.0),
    ("residential fate: field application", "residential", "06_results.tex",
     r"applied to fields, \\SI\{([\d.]+)\}\{\} more",
     lambda: _first_where("national_dung_variants.csv", "delta_vs_S_Mt_co2e_AR5",
                          variant_id="S_residual_field_application"), 0.0),
    ("residential national share", "residential", "06_results.tex",
     r"combustion is \\SI\{([\d.]+)\}\{\\percent\} of Pakistan's national emissions",
     lambda: _residential_config("S", "national_share_pct"), 0.0),
    # -- air pollutants
    ("residential PM2.5, air prose", "residential", "06b_air_pollutants.tex",
     r"burning emits \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of primary",
     lambda: _residential_config("S", "pm25_kt"), 0.0),
    ("residential PM2.5 under L, air prose", "residential", "06b_air_pollutants.tex",
     r"---and \\SI\{([\d.]+)\}\{\\kilo\\tonne\}, \\num\{\d+\} times",
     lambda: _residential_config("L", "pm25_kt"), 0.0),
    ("residential PM ratio under L, air prose", "residential", "06b_air_pollutants.tex",
     r"\\kilo\\tonne\}, \\num\{(\d+)\} times\s*\(31--445\)",
     lambda: _residential_config("L", "pm_ratio_vs_road_exhaust"), 0.0),
    ("residential black carbon, prose", "residential", "06b_air_pollutants.tex",
     r"At \\SI\{([\d.]+)\}\{\\kilo\\tonne\} \(\\SI",
     lambda: _residential_config("S", "bc_kt"), 0.0),
    ("residential black carbon under L, prose", "residential", "06b_air_pollutants.tex",
     r"\(\\SI\{([\d.]+)\}\{\} under configuration~L\), household biomass",
     lambda: _residential_config("L", "bc_kt"), 0.0),
    # -- discussion
    ("residential discussion share reference", "residential", "07_discussion.tex",
     r"sector is \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\}",
     lambda: _residential_config("S", "national_share_pct"), 0.0),
    ("residential discussion share L", "residential", "07_discussion.tex",
     r"sector is \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\}",
     lambda: _residential_config("L", "national_share_pct"), 0.0),
    ("residential discussion diverted over survey", "residential", "07_discussion.tex",
     r"a factor of \\num\{([\d.]+)\} lower",
     lambda: _residential_dung_survey("diverted")
             / _residential_dung_survey("household"), 0.0),
    # -- limitations
    ("residential reference dung, limitations", "residential", "08_limitations.tex",
     r"rounds: \\SI\{([\d.]+)\}\{\\mega\\tonne\} for FY2023--24",
     lambda: _residential_dung_survey("household"), 0.0),
    ("residential round ratio, limitations", "residential", "08_limitations.tex",
     r"disagree by a\s*factor of \\num\{([\d.]+)\} per household",
     lambda: _residential_dung_survey("round_ratio"), 0.0),
    ("residential dung top5 share, limitations", "residential", "08_limitations.tex",
     r"hold \\SI\{([\d.]+)\}\{\\percent\} of the reported dung",
     lambda: 100.0 * _residential_dung_diag("hies2025", "top5pct_hh_share_of_total"),
     0.0),
    ("residential dung activity width, limitations", "residential",
     "08_limitations.tex",
     r"the stream carries \\SI\{([\d]+)\}\{\\percent\} for\s*that",
     lambda: _first_where("residential_uncertainty_inputs_2024.csv", "uncert_pct_95",
                          variable="Household dung cake (survey series)"), 0.0),
    ("residential unresolved cake, limitations", "residential", "08_limitations.tex",
     r"The \\SI\{([\d.]+)\}\{\\mega\\tonne\} of diverted cake",
     lambda: _residential_dung_survey("unresolved"), 0.0),
    # -- conclusion
    ("residential conclusion reference co2e", "residential", "09_conclusion.tex",
     r"emitted \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _residential_config("S", "co2e_Mt_AR5"), 0.0),
    ("residential conclusion L co2e", "residential", "09_conclusion.tex",
     r"emitted \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _residential_config("L", "co2e_Mt_AR5"), 0.0),
    ("residential conclusion reference PM", "residential", "09_conclusion.tex",
     r"emitted \\SIrange\{([\d]+)\}\{[\d]+\}\{\\kilo\\tonne\}",
     lambda: _residential_config("S", "pm25_kt"), 0.0),
    ("residential conclusion L PM", "residential", "09_conclusion.tex",
     r"emitted \\SIrange\{[\d]+\}\{([\d]+)\}\{\\kilo\\tonne\}",
     lambda: _residential_config("L", "pm25_kt"), 0.0),
    # -- the dung note
    ("residential 2024-25 round, dung note", "residential", "S1_dung_closure.tex",
     r"observes \\SI\{([\d.]+)\}\{\\mega\\tonne\} of cake",
     lambda: _first_where("residential_hies_comparison_2024.csv", "hies2425_annual",
                          fuel="dung_cake") / 1e9, 0.0),
    ("residential diverted over 2024-25 round", "residential", "S1_dung_closure.tex",
     r"a factor of \\num\{([\d.]+)\} below the diverted total",
     lambda: _residential_dung_survey("diverted")
             / (_first_where("residential_hies_comparison_2024.csv", "hies2425_annual",
                             fuel="dung_cake") / 1e9), 0.0),
    ("residential reference dung, dung note", "residential", "S1_dung_closure.tex",
     r"rounds puts \\SI\{([\d.]+)\}\{\} there in FY2023--24",
     lambda: _residential_dung_survey("household"), 0.0),
    ("residential ledger dry solids, dung note", "residential", "S1_dung_closure.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}\) and are the basis",
     lambda: _first_where("pakemis_dung_residual_ledger.csv", "diverted_dry_solids_kt",
                          species="ALL") / 1000.0, 0.0),
    ("residential ledger air-dry, dung note", "residential", "S1_dung_closure.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}\) and\s*pairs with",
     lambda: _residential_dung_survey("diverted"), 0.0),

    ("transport reported interval", "transport", "00_abstract.tex",
     r"reported interval is \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _first_where("transport_uncertainty_2024.csv",
                          "approach1_pct_independent", scope="sector"), 0.0),
    ("transport 2W reference Mt", "transport", "01_introduction.tex",
     r"they receive \\SI\{([\d.]+)\}\{\\mega\\tonne\}, \\SI\{[\d.]+\}\{\\percent\}",
     lambda: _sum_where("transport_by_stream_2024.csv", "co2e_Mt_AR5",
                        subitem="2W Petrol CO2"), 0.0),
    ("transport 2W reference share", "transport", "01_introduction.tex",
     r"they receive \\SI\{[\d.]+\}\{\\mega\\tonne\}, \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _sum_where("transport_by_stream_2024.csv", "co2e_Mt_AR5",
                                subitem="2W Petrol CO2")
             / sum(float(r["co2e_Mt_AR5"])
                   for r in _rows("transport_by_stream_2024.csv")
                   if r["gas"] == "CO2" and "Off-road" not in r["subitem"]), 0.05),
    ("transport petrol NCV", "transport", "04_methods.tex",
     r"by \\SI\{([\d.]+)\}\{\\tera\\joule\\per\\giga\\gram\} gets",
     lambda: float(next(r for r in _rows("transport_fuel_bridge_2024.csv")
                        if r["fuel"] == "Petrol" and r["kind"] == "opening")
                   ["ncv_TJ_per_Gg"]), 0.0),
    ("transport navigation kt", "transport", "04_methods.tex",
     r"Domestic Bunkers row \(\\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _first_where("transport_fuel_ledger_2024.csv", "kt",
                          claimant="Domestic bunkers"), 0.0),
    ("transport navigation Mt", "transport", "04_methods.tex",
     r"implying about \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\}",
     lambda: _first_where("transport_fuel_ledger_2024.csv", "kt",
                          claimant="Domestic bunkers") * 3.2 / 1000.0, 0.005),
    ("transport offroad energy share", "transport", "04_methods.tex",
     r"the energy weighting the share is \\num\{([\d.]+)\}, against",
     lambda: -float(next(r for r in _rows("transport_fuel_bridge_2024.csv")
                         if r["fuel"] == "Diesel" and r["kind"] == "partition")
                    ["kt"])
             / float(next(r for r in _rows("transport_fuel_bridge_2024.csv")
                          if r["fuel"] == "Diesel" and r["kind"] == "opening")
                     ["kt"]), 0.0),
    ("transport offroad reclassification", "transport", "04_methods.tex",
     r"a\s*\\SI\{([\d]+)\}\{\\kilo\\tonne\} reclassification",
     lambda: (0.0999 + float(next(r for r in _rows("transport_fuel_bridge_2024.csv")
                                  if r["fuel"] == "Diesel"
                                  and r["kind"] == "partition")["kt"])
              / float(next(r for r in _rows("transport_fuel_bridge_2024.csv")
                           if r["fuel"] == "Diesel" and r["kind"] == "opening")
                      ["kt"]))
             * float(next(r for r in _rows("transport_fuel_bridge_2024.csv")
                          if r["fuel"] == "Diesel" and r["kind"] == "opening")
                     ["kt"]), 1.0),
    ("transport rail matched kt", "transport", "04_methods.tex",
     r"= \\SI\{([\d.]+)\}\{\\kilo\\tonne\} at\s*0.845 kg/l",
     lambda: _first_where("railways_fuel_reconciliation_2024.csv",
                          "summary_k_litres", fiscal_year="2024")
             * 0.845 / 1000.0, 0.05),
    ("transport rail historical kt", "transport", "04_methods.tex",
     r"= \\SI\{([\d.]+)\}\{\\kilo\\tonne\}; Year Book 2022--23",
     lambda: _first_where("railways_fuel_reconciliation_2024.csv",
                          "summary_k_litres", fiscal_year="2022")
             * 0.845 / 1000.0, 0.05),
    ("transport CNG MMCFD", "transport", "04_methods.tex",
     r"---\\SI\{([\d]+)\}\{\} MMCFD as an annual average",
     lambda: _first_where("transport_cng_2024.csv", "mmcfd",
                          fiscal_year="2024"), 0.0),
    ("transport off-road N2O diagnostic", "transport", "04b_emission_factors.tex",
     r"\\NtwoO\{\} would be \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*instead",
     lambda: _cell("transport_totals_2024.csv", "category",
                   "Diagnostic: off-road N2O on the road factor", "co2e_Mt_AR5"), 0.0),
    ("transport off-road on road table", "transport", "04b_emission_factors.tex",
     r"category total \\SI\{([\d.]+)\}\{\\mega\\tonne\} instead of",
     lambda: _cell("transport_totals_2024.csv", "category",
                   "Mixed off-road (1A4c/1A2)", "co2e_Mt_AR5")
             - _sum_where("transport_by_stream_2024.csv", "co2e_Mt_AR5",
                          subitem="Off-road machinery diesel N2O")
             + _cell("transport_totals_2024.csv", "category",
                     "Diagnostic: off-road N2O on the road factor",
                     "co2e_Mt_AR5"), 0.005),
    ("transport onroad diesel intensity", "transport", "04_methods.tex",
     r"against roughly \\SI\{([\d.]+)\}\{\}, because buses",
     _onroad_diesel_mjkm, 0.0),
    ("transport EDGAR headline construction", "transport", "05_validation.tex",
     r"road residual \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\) plus railways",
     # rail term is STRICT 1A3c since rc12 - EDGAR's inferred scope has no
     # non-traction category, so like-for-like takes the traction row alone
     lambda: _first_where("national_edgar_transport_comparison.csv", "engine_Mt",
                          rank="PRIMARY")
             - _cell("railways_totals_2024.csv", "category", "Railways",
                     "co2e_Mt_AR5")
             - _cell("aviation_timeseries_2006_fy2023_24.csv", "fiscal_year", "2023",
                     "domestic_kt_co2e_AR5") / 1000.0, 0.0),
    ("transport EDGAR blend ratio", "transport", "05_validation.tex",
     r"or \\num\{([\d.]+)\} of EDGAR's fiscal-year",
     lambda: _first_where("national_edgar_transport_comparison.csv",
                          "ratio_engine_over_edgar", rank="PRIMARY"), 0.0),
    ("transport EDGAR blend Mt", "transport", "05_validation.tex",
     r"blend of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("national_edgar_transport_comparison.csv", "edgar_Mt",
                          rank="PRIMARY"), 0.0),
    ("transport EDGAR cy2024", "transport", "05_validation.tex",
     r"Against the 2024 column alone it is \\num\{([\d.]+)\}",
     lambda: _first_where("national_edgar_transport_comparison.csv",
                          "ratio_engine_over_edgar",
                          construction="EDGAR-scope match against calendar 2024"),
     0.0),
    ("transport EDGAR cy2023", "transport", "05_validation.tex",
     r"against 2023 alone \\num\{([\d.]+)\}",
     lambda: _first_where("national_edgar_transport_comparison.csv",
                          "ratio_engine_over_edgar",
                          construction="EDGAR-scope match against calendar 2023"),
     0.0),
    ("transport EDGAR superseded ratio", "transport", "05_validation.tex",
     r"led with a \\num\{([\d.]+)\} ratio whose engine side",
     lambda: _first_where("national_edgar_transport_comparison.csv",
                          "ratio_engine_over_edgar",
                          construction="rc4's mixed-vintage construction"),
     0.0),
    ("transport provincial shape bracket", "transport", "06_results.tex",
     r"against either neighbour is \\num\{([\d.]+)\} points",
     lambda: max(abs(float(r["spread_pp"])) for r in
                 _rows("transport_provincial_shape_brackets.csv")), 0.005),
    ("transport borrowing error", "transport", "06_results.tex",
     r"off by at most \\num\{([\d.]+)\} points",
     lambda: (__import__("importlib").import_module(
         "pkinv.sectors.transport.province_shape").borrowing_error_pp()), 0.005),
    ("waste second widest", "waste", "00_abstract.tex",
     r"at \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$\), carries its second-widest",
     lambda: _sector_uncertainty("aviation"), 0.05),
    ("waste second widest results", "waste", "06_results.tex",
     r"carries a wider band \(\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$\)",
     lambda: _sector_uncertainty("aviation"), 0.05),
    ("transport CNG net TJ", "transport", "05_validation.tex",
     r"The metered gas is \\SI\{([\d]+)\}\{\} net terajoules",
     lambda: float(_cell("transport_cng_crosscheck_2024.csv", "item",
                         "Metered gas (OGRA)", "value")), 0.0),
    ("transport CNG vkm share", "transport", "05_validation.tex",
     r"puts \\SI\{([\d.]+)\}\{\\percent\} of road vehicle-kilometres on CNG",
     lambda: float(re.search(r"([\d.]+)% of all road vehicle-km",
                             next(r for r in _rows(
                                 "transport_cng_crosscheck_2024.csv")
                                 if r["item"] == "Modelled CNG travel (fleet)")
                             ["note"]).group(1)), 0.0),
    ("transport CNG intensity", "transport", "05_validation.tex",
     r"implying \\SI\{([\d.]+)\}\{\\mega\\joule\\per\\kilo\\metre\}",
     lambda: float(_cell("transport_cng_crosscheck_2024.csv", "item",
                         "Implied energy intensity", "value")), 0.0),
    ("transport CNG 3W distance share", "transport", "05_validation.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} of this modelled travel is three-wheelers",
     lambda: float(re.search(r"([\d.]+)% of CNG vehicle-km",
                             next(r for r in _rows(
                                 "transport_cng_crosscheck_2024.csv")
                                 if r["item"] == "CNG travel 3W")["note"])
                   .group(1)), 0.2),
    ("transport CNG Mt", "transport", "06_results.tex",
     r"Its \\SI\{([\d.]+)\}\{\\mega\\tonne\} rests on",
     lambda: _first_where("transport_cng_2024.csv", "mt_co2e_AR5",
                          fiscal_year="2024"), 0.0),
    ("transport CNG span", "transport", "06_results.tex",
     r"The sector moves by \\SI\{([\d.]+)\}\{\\mega\\tonne\} across the",
     lambda: _first_where("transport_uncertainty_scenarios_2024.csv",
                          "deterministic", structural_scenario="reference")
             - _first_where("transport_uncertainty_scenarios_2024.csv",
                            "deterministic",
                            structural_scenario="cng_hhv_900"), 0.005),
    ("transport grouped band low", "transport", "06_results.tex",
     r"gives \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\} depending",
     lambda: _first_where("transport_uncertainty_2024.csv",
                          "approach1_pct_grouped", scope="sector"), 0.05),
    ("transport grouped band high", "transport", "06_results.tex",
     r"gives \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\} depending",
     lambda: _first_where("transport_uncertainty_2024.csv",
                          "approach1_pct_grouped_crossfuel", scope="sector"), 0.05),
    ("transport MC within", "transport", "06_results.tex",
     r"reports \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ under module-shared",
     lambda: float(next(r for r in _rows("national_uncertainty_montecarlo.csv")
                        if r["scenario"] == "within_sector"
                        and r["name"] == "transport")["rel_uncert_pct_MC_95"]),
     0.05),
    ("transport MC cross", "transport", "06_results.tex",
     r"\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ with the shared fuel-carbon factors",
     lambda: float(next(r for r in _rows("national_uncertainty_montecarlo.csv")
                        if r["scenario"] == "cross_sector"
                        and r["name"] == "transport")["rel_uncert_pct_MC_95"]),
     0.05),
    ("transport heavy plus bus", "transport", "06_results.tex",
     r"together \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _sum_where("transport_by_stream_2024.csv", "co2e_Mt_AR5",
                        subitem="HDV Diesel CO2")
             + _sum_where("transport_by_stream_2024.csv", "co2e_Mt_AR5",
                          subitem="BUS Diesel CO2"), 0.05),

    ("transport share now", "transport", "06_results.tex",
     r"it is \\SI\{([\d.]+)\}\{\\percent\}, and road transport remains",
     lambda: 100.0 * _cell("transport_totals_2024.csv", "category", "TOTAL",
                           "co2e_Mt_AR5") / _sector("TOTAL"), 0.4),

    ("transport territories", "transport", "06_results.tex",
     r"territories \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("transport_provincial_2024.csv", "co2e_Mt_AR5",
                          province="Other"), 0.01),
    ("transport CNG intensity limitation", "transport", "08_limitations.tex",
     r"gets \\SI\{([\d.]+)\}\{\\mega\\joule\\per\\kilo\\metre\}, below",
     lambda: float(_cell("transport_cng_crosscheck_2024.csv", "item",
                         "Implied energy intensity", "value")), 0.005),
    # rc40 G1. The appendix CRT table's ACTIVITY column was hand-written and A11 never
    # opened it - it verified the supplement's livestock table and declared Table 26 done.
    # 245.3 M head, 3.50 Mha, "3.78 Mt N applied" and 5.89 Mt urea all predated the round.
    # Each cell now reads the product that computes it.
    ("agri crt enteric head", "agriculture", "10_appendix.tex",
     r"\\CHfour\{\} & ([\d.]+) M ruminant head & 54\.5",
     lambda: sum(float(r["national_control_head"]) for r in
                 _rows_banner("agriculture_livestock_reconciliation_2024.csv")) / 1e6, 0.005),
    ("agri crt manure head", "agriculture", "10_appendix.tex",
     r"([\d.]+) M ruminant head\$\^\{a\}\$",
     lambda: sum(float(r["national_control_head"]) for r in
                 _rows_banner("agriculture_livestock_reconciliation_2024.csv")) / 1e6, 0.005),
    ("agri crt n excreted", "agriculture", "10_appendix.tex",
     r"([\d.]+) M t N excreted\$\^\{a\}\$",
     lambda: next(float(r["Mt_N"]) for r in _rows_banner("n_ledger_2024.csv")
                  if r["flow"] == "Total N excreted"), 0.005),
    ("agri crt rice area", "agriculture", "10_appendix.tex",
     r"([\d.]+) M ha paddy",
     lambda: __import__("pkinv.sectors.agriculture.ef_library", fromlist=["x"])
             .InventoryData().crops["rice"]["area_ha"] / 1e6, 0.005),
    ("agri crt FSN", "agriculture", "10_appendix.tex",
     r"F\$_\{SN\}\$ ([\d.]+),",
     lambda: __import__("pkinv.sectors.agriculture.ef_library", fromlist=["x"])
             .InventoryData().fertilizer["nitrogen_N_offtake"]["value_t"] / 1e6, 0.005),
    ("agri crt FON", "agriculture", "10_appendix.tex",
     r"F\$_\{ON\}\$ ([\d.]+),",
     lambda: next(float(r["Mt_N"]) for r in _rows_banner("n_ledger_2024.csv")
                  if r["flow"].startswith("Manure N applied to soils (gross FON)")), 0.005),
    ("agri crt FPRP", "agriculture", "10_appendix.tex",
     r"F\$_\{PRP\}\$ ([\d.]+),",
     lambda: next(float(r["Mt_N"]) for r in _rows_banner("n_ledger_2024.csv")
                  if r["flow"].startswith("to grazing")), 0.005),
    ("agri crt FCR", "agriculture", "10_appendix.tex",
     r"F\$_\{CR\}\$ ([\d.]+) M t N",
     lambda: __import__("pkinv.sectors.agriculture.soils", fromlist=["x"]).residue_N(
         __import__("pkinv.sectors.agriculture.ef_library", fromlist=["x"]).InventoryData())
             / 1e9, 0.005),
    ("agri crt combusted", "agriculture", "10_appendix.tex",
     r"([\d.]+) M t d\.m\.\\ combusted\$\^\{c\}\$",
     lambda: next(float(r["combusted_Mt"]) for r in
                  _rows_banner("agriculture_crop_residue_ledger_2024.csv")
                  if r["crop"] == "TOTAL"), 0.005),
    ("agri crt urea", "agriculture", "10_appendix.tex",
     r"([\d.]+) M t urea\$\^\{b\}\$",
     lambda: next(float(r["urea_mass_t"]) for r in _rows_banner("agriculture_urea_basis.csv")
                  if r["fiscal_year"] == "FY2023-24") / 1e6, 0.005),
    # Table 7's factor cell: the one copy of FracGASF the A2 repair could not see because it
    # was never registered; it kept 0.1605 while the prose moved to 0.1608.
    ("agri table7 fracgasf", "agriculture", "04c_shared_ledger.tex",
     r"kg \\NHthree\{\}-N per kg N & ([\d.]+)\$\^\{b\}\$",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["x"]).fracgasf()[0], 0.00005),
    # The two remaining "114 districts" sites, generated like the methods one.
    ("agri conclusion district count", "agriculture", "09_conclusion.tex",
     r"grid and (\d+) districts under",
     lambda: float(len({r["district"] for r in _rows("district_totals_2024.csv")}) - 1), 0.0),
    ("agri air district count", "agriculture", "06b_air_pollutants.tex",
     r"grid and (\d+) districts using",
     lambda: float(len({r["district"] for r in _rows("district_totals_2024.csv")}) - 1), 0.0),
    # rc39 A11. The district count, generated rather than stated. It appears in four
    # sections and the number is CORRECT - 115 rows in the product, 114 districts plus one
    # residual reporting unit - so this pass does not change it. What it changes is that
    # nothing was checking it, in a repository where the district frame differs by sector
    # (114 on agriculture's four-province base, 134 on the census frame the residential and
    # waste sectors allocate over). A count that is right and unchecked is one boundary
    # revision away from being wrong and unnoticed.
    ("agri district count", "agriculture", "04_methods.tex",
     r"The main output contains (\d+) districts across the four provinces",
     lambda: float(len({r["district"] for r in _rows("district_totals_2024.csv")}) - 1), 0.0),
    # rc39 A9. The district layer's two published limits and the nesting gap, each read
    # from the product that measures it. Written as prose they would be three numbers no
    # test could see going stale - which is how the fire masses got two passes behind.
    # rc41: priced per stream, and the province is the event's own - Larkana is Sindh's
    # residential and waste panels; the territories outside the four provinces are a
    # second unit of the same kind that this claim used to fold into "Larkana".
    ("agri larkana unplaced mass", "agriculture", "06_results.tex",
     r"sub-provincial placement of \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: sum(float(r["affected_mass_Mt_AR5"])
                 for r in _rows_banner("pakemis_spatial_exceptions.csv")
                 if r["exception_kind"] == "shape_missing" and r["province"] == "Sindh"), 0.005),
    ("agri other-territory unplaced mass", "agriculture", "06_results.tex",
     r"has no shapes: \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: sum(float(r["affected_mass_Mt_AR5"])
                 for r in _rows_banner("pakemis_spatial_exceptions.csv")
                 if r["exception_kind"] == "shape_missing" and r["province"] == "Other"), 0.005),
    ("agri rice uniform fallback mass", "agriculture", "06_results.tex",
     r"affecting\n\\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: sum(float(r["affected_mass_Mt_AR5"])
                 for r in _rows_banner("pakemis_spatial_exceptions.csv")
                 if r["exception_kind"] == "proxy_empty" and r["module"] == "agriculture"),
     0.005),
    # The earlier nine-year timing percentages are no longer manuscript claims.
    # The typed timing diagnostic remains available as a separate data product.
    ("agri nfdc residual tonnes", "agriculture", "04c_shared_ledger.tex",
     r"\\SI\{(\d+)\}\{\\tonne\} of product",
     lambda: next(float(r["residual_tonnes"]) for r in
                  _rows_banner("agriculture_nfdc_province_residual.csv")
                  if r["month"] == "TOTAL"), 1.0),
    ("agri nfdc residual pct", "agriculture", "04c_shared_ledger.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the national total and mostly",
     lambda: next(float(r["residual_pct_of_national"]) for r in
                  _rows_banner("agriculture_nfdc_province_residual.csv")
                  if r["month"] == "TOTAL"), 0.00001),
    # rc39 A6. The appendix's two fire masses, read from the residue ledger that now
    # publishes them. They were prose two passes behind the engine - 7.7 and 6.6 against the
    # engine's 8.4 and 7.1 - which is what happens to a number with no output behind it.
    ("agri residue to fire", "agriculture", "10_appendix.tex",
     r"\\SI\{([\d.]+)\}\{\}~Mt of dry matter reaching the fire",
     lambda: next(float(r["to_fire_Mt"]) for r in
                  _rows_banner("agriculture_crop_residue_ledger_2024.csv")
                  if r["crop"] == "TOTAL"), 0.05),
    ("agri residue combusted", "agriculture", "10_appendix.tex",
     r"leaves \\SI\{([\d.]+)\}\{\}~Mt burnt",
     lambda: next(float(r["combusted_Mt"]) for r in
                  _rows_banner("agriculture_crop_residue_ledger_2024.csv")
                  if r["crop"] == "TOTAL"), 0.05),
    # rc39 A3. The methods text states how far the old reconstruction fell short of the
    # printed offtake. Registered rather than written as a literal: it is the whole reason
    # 3.H changed basis, and a stale version of it would understate or overstate the case
    # for the change itself.
    ("agri urea reconstruction shortfall", "agriculture", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\}; a measurement is preferred",
     lambda: next(float(r["shortfall_of_reconstruction_pct"])
                  for r in _rows_banner("agriculture_urea_basis.csv")
                  if r["fiscal_year"] == "FY2023-24"), 0.001),
    # rc39 A2 promoted this whole paragraph from tier 2 to tier 1. Every number in it was a
    # REPEAT of a value registered elsewhere in the document, so the coverage test was
    # satisfied while five of the six were stale - the five-category estimate, the aggregate
    # ratio, and the enteric, field-burning and manure ratios, all predating a scope change.
    # A repeat only proves the digits appear somewhere else in the paper; it cannot notice
    # that a sentence has attached a current-looking number to the wrong comparison. These
    # now read the benchmark file in the place they are printed.
    # rc42 (M-3): Fecto's exact FY2023-24 quantities, read from the census table
    ("ippu fecto clinker", "ippu", "03_study_area_and_data.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s*clinker and \\SI\{[\d.]+\}\{\\mega\\tonne\} of cement",
     lambda: float(_first_where_data(os.path.join("activity", "ippu", "company_clinker_2023_24.csv"),
                                     "clinker_production_t", company="Fecto Cement Limited")) / 1e6, 0.0),
    ("ippu fecto cement", "ippu", "03_study_area_and_data.tex",
     r"of\s*clinker and \\SI\{([\d.]+)\}\{\\mega\\tonne\} of cement",
     lambda: float(_first_where_data(os.path.join("activity", "ippu", "company_clinker_2023_24.csv"),
                                     "cement_production_t", company="Fecto Cement Limited")) / 1e6, 0.0),
    # rc42 (M-1): the structural-NH3 prose reads the regenerated eval product it describes
    ("agri apstruct benchmark NH3", "agriculture", "06b_air_pollutants.tex",
     r"grazing\. It\s*produces \\SI\{([\d.]+)\}\{\}~Mt \\NHthree\{\} and a greenhouse-gas total of \\SI\{[\d.]+\}",
     lambda: _msu("benchmark-like (high grazing)", "NH3_total_kt") / 1000.0, 0.005),
    ("agri apstruct benchmark total", "agriculture", "06b_air_pollutants.tex",
     r"grazing\. It\s*produces \\SI\{[\d.]+\}\{\}~Mt \\NHthree\{\} and a greenhouse-gas total of \\SI\{([\d.]+)\}",
     lambda: _msu("benchmark-like (high grazing)", "national_total_Mt"), 0.05),
    ("agri apstruct gleam NH3", "agriculture", "06b_air_pollutants.tex",
     r"to\s*grazing\. It produces \\SI\{([\d.]+)\}\{\}~Mt \\NHthree\{\} and a greenhouse-gas total of\s*\\SI\{[\d.]+\}",
     lambda: _msu("GLEAM 3.0 South Asia", "NH3_total_kt") / 1000.0, 0.005),
    ("agri apstruct gleam total", "agriculture", "06b_air_pollutants.tex",
     r"to\s*grazing\. It produces \\SI\{[\d.]+\}\{\}~Mt \\NHthree\{\} and a greenhouse-gas total of\s*\\SI\{([\d.]+)\}",
     lambda: _msu("GLEAM 3.0 South Asia", "national_total_Mt"), 0.05),
    ("agri apstruct midpoint NH3", "agriculture", "06b_air_pollutants.tex",
     r"A midpoint diagnostic gives \\SI\{([\d.]+)\}\{\}~Mt \\NHthree\{\}",
     lambda: _msu("evidence-weighted mean", "NH3_total_kt") / 1000.0, 0.005),
    ("agri apstruct midpoint total", "agriculture", "06b_air_pollutants.tex",
     r"A midpoint diagnostic gives \\SI\{[\d.]+\}\{\}~Mt \\NHthree\{\} and \\SI\{([\d.]+)\}\{\}~Mt~\\COe",
     lambda: _msu("evidence-weighted mean", "national_total_Mt"), 0.05),
    ("agri apstruct range low", "agriculture", "06b_air_pollutants.tex",
     r"national \\NHthree\{\} ranges from \\SI\{([\d.]+)\}\{\} to",
     lambda: _msu("benchmark-like (high grazing)", "NH3_total_kt") / 1000.0, 0.005),
    ("agri apstruct range high", "agriculture", "06b_air_pollutants.tex",
     r"ranges from \\SI\{[\d.]+\}\{\} to\s*\\SI\{([\d.]+)\}\{\}~Mt, and the agricultural",
     lambda: _msu("GLEAM 3.0 South Asia", "NH3_total_kt") / 1000.0, 0.005),
    # rc42 (M-1): the discussion's EF1 = 0.010 total is the live sensitivity scenario
    ("agri discussion ef1 aggregate total", "agriculture", "07_discussion.tex",
     r"and the national total to\s*\\SI\{([\d.]+)\}\{\} \(Table~\\ref\{tab:sensitivity\}\)",
     lambda: _sensitivity_total("Soil EF1 = 0.010 (2006 aggregate)"), 0.05),
    ("agri discussion ef1 aggregate soils", "agriculture", "07_discussion.tex",
     r"managed soils rises to \\SI\{([\d.]+)\}\{\} Mt~\\COe\{\} and the national total",
     lambda: _sensitivity_soils("Soil EF1 = 0.010 (2006 aggregate)"), 0.05),
    # rc42 (M-5): the crop-residue fuel transfer, anchored to the residue ledger wherever
    # the agriculture paper states it beside the dung-cake one
    ("agri residue fuel dry (abstract)", "agriculture", "00_abstract.tex",
     r"\(\\SI\{([\d.]+)\}\{\}~Mt dry matter, \\SI\{\d+\}\{\}~TJ\)",
     lambda: _residue_total("fuel_dry_Mt"), 0.005),
    ("agri residue fuel TJ (abstract)", "agriculture", "00_abstract.tex",
     r"~Mt dry matter, \\SI\{(\d+)\}\{\}~TJ\)",
     lambda: _residue_total("energy_TJ"), 0.5),
    ("agri residue fuel dry (conclusion)", "agriculture", "09_conclusion.tex",
     r"fuel \(\\SI\{([\d.]+)\}\{\}~Mt dry, \\SI\{\d+\}\{\}~TJ\)",
     lambda: _residue_total("fuel_dry_Mt"), 0.005),
    ("agri residue fuel TJ (conclusion)", "agriculture", "09_conclusion.tex",
     r"~Mt dry, \\SI\{(\d+)\}\{\}~TJ\)",
     lambda: _residue_total("energy_TJ"), 0.5),
    ("agri residue dry total (limitations)", "agriculture", "08_limitations.tex",
     r"Of \\SI\{([\d.]+)\}\{\}~Mt of dry residue",
     lambda: _residue_total("dry_residue_Mt"), 0.005),
    ("agri residue fuel dry (limitations)", "agriculture", "08_limitations.tex",
     r"dry residue, \\SI\{([\d.]+)\}\{\}~Mt \(\\SI\{\d+\}\{\}~TJ\)",
     lambda: _residue_total("fuel_dry_Mt"), 0.005),
    ("agri residue fuel TJ (limitations)", "agriculture", "08_limitations.tex",
     r"dry residue, \\SI\{[\d.]+\}\{\}~Mt \(\\SI\{(\d+)\}\{\}~TJ\)",
     lambda: _residue_total("energy_TJ"), 0.5),
    ("agri residue returned (limitations)", "agriculture", "08_limitations.tex",
     r"dung cake; \\SI\{([\d.]+)\}\{\}~Mt is returned to soil",
     lambda: _residue_total("returned_to_soil_Mt"), 0.005),
    ("agri residue burned (limitations)", "agriculture", "08_limitations.tex",
     r"returned to soil and\s*\\SI\{([\d.]+)\}\{\}~Mt burned in the field",
     lambda: _residue_total("to_fire_Mt"), 0.005),
    ("agri residue unresolved (limitations)", "agriculture", "08_limitations.tex",
     r"The \\SI\{([\d.]+)\}\{\}~Mt the ledger cannot place",
     lambda: _residue_total("other_unresolved_Mt"), 0.005),
    ("agri residue unresolved pct (limitations)", "agriculture", "08_limitations.tex",
     r"cannot place\s*\(\\SI\{([\d.]+)\}\{\\percent\} of dry residue",
     lambda: _residue_total("other_pct_of_dry"), 0.05),
    # rc42 (the twentieth review's M-2): the prose compares on the CALENDAR-2023 basis
    # tab:benchmark prints - the engine's calendar reconstruction of the fiscal series
    # (districts/district_totals_by_year.csv, year 2023) against FAOSTAT 2023 - and not the
    # FY2023-24 engine values national_benchmark_comparison.csv carries, which put a
    # fiscal-year 218.6 and 0.94 beside a table reading 207.8 and 0.89.
    ("agri faostat five-category estimate", "agriculture", "06_results.tex",
     r"our estimate is\s*\\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: sum(_agri_cy2023()[c]
                 for c in ("Enteric fermentation", "Manure management", "Rice cultivation",
                           "Managed soils", "Field burning of residues")), 0.05),
    ("agri faostat five-category ratio", "agriculture", "06_results.tex",
     r"The resulting\s*ratio is \\num\{([\d.]+)\}",
     lambda: (sum(_agri_cy2023()[c]
                  for c in ("Enteric fermentation", "Manure management", "Rice cultivation",
                            "Managed soils", "Field burning of residues"))
              / _first_where("national_benchmark_comparison.csv", "benchmark_Mt_co2e",
                             source="FAOSTAT", engine_category="TOTAL")), 0.005),
    ("agri faostat enteric ratio", "agriculture", "06_results.tex",
     r"agrees to within five per cent, with a\nratio of \\num\{([\d.]+)\}",
     lambda: _agri_cy2023_ratio("Enteric fermentation"), 0.005),
    ("agri faostat rice ratio", "agriculture", "06_results.tex",
     r"have ratios of \\num\{([\d.]+)\} and",
     lambda: _agri_cy2023_ratio("Rice cultivation"), 0.005),
    ("agri faostat burning ratio", "agriculture", "06_results.tex",
     r"have ratios of \\num\{[\d.]+\} and\n\\num\{([\d.]+)\}",
     lambda: _agri_cy2023_ratio("Field burning of residues"), 0.005),
    ("agri faostat manure ratio", "agriculture", "06_results.tex",
     r"Manure-management emissions are \\num\{([\d.]+)\} times",
     lambda: _agri_cy2023_ratio("Manure management"), 0.005),
    ("agri abstract total", "agriculture", "00_abstract.tex",
     r"greenhouse-gas emissions of \\SI\{([\d]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _cell("national_totals_2024.csv", "category", "TOTAL",
                   "co2e_Mt_AR5"), 0.0),
    ("agri abstract MC low", "agriculture", "00_abstract.tex",
     r"interval of \\SI\{([\d]+)\}\{\}--\\SI\{[\d]+\}\{\}~Mt~\\COe\{\}",
     lambda: _cell("uncertainty_montecarlo.csv", "category", "TOTAL",
                   "P2.5_Mt"), 0.0),
    ("agri abstract MC high", "agriculture", "00_abstract.tex",
     r"interval of \\SI\{[\d]+\}\{\}--\\SI\{([\d]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _cell("uncertainty_montecarlo.csv", "category", "TOTAL",
                   "P97.5_Mt"), 0.0),
    ("agri abstract NH3", "agriculture", "00_abstract.tex",
     r"We also estimate \\SI\{([\d.]+)\}\{\}~Mt of \\NHthree\{\}",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="NH3") / 1000.0, 0.0),
    ("agri abstract CO", "agriculture", "00_abstract.tex",
     r"crop-residue burning, \\SI\{([\d.]+)\}\{\}~Mt of CO",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="CO") / 1000.0, 0.005),
    ("agri abstract PM", "agriculture", "00_abstract.tex",
     r"and \\SI\{([\d]+)\}\{\}~kt of PM",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.05),
    ("agri abstract pearson", "agriculture", "00_abstract.tex",
     r"Pearson correlation of\s*\\num\{([\d.]+)\}",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["all_sectors"]["pearson"], 0.005),
    ("agri abstract hotspot", "agriculture", "00_abstract.tex",
     r"and \\SI\{([\d]+)\}\{\\percent\} overlap among top-decile",
     lambda: 100.0 * json.load(open(os.path.join(OUT, "eval",
                               "spatial_nh3_validation.json")))
             ["all_sectors"]["hotspot_overlap_top10pct"], 0.3),
    ("agri abstract ratio", "agriculture", "00_abstract.tex",
     r"estimate is approximately \\num\{([\d.]+)\} times higher",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["all_sectors"]["ratio"], 0.05),
    ("agri config span low", "agriculture", "00_abstract.tex",
     r"emissions range from \\SI\{([\d.]+)\}\{\} to",
     lambda: min(float(r["NH3_total_kt"])
                 for r in _rows(os.path.join("eval",
                                "mms_structural_uncertainty.csv"))) / 1000.0, 0.05),
    ("agri config span high", "agriculture", "00_abstract.tex",
     r"range from \\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: max(float(r["NH3_total_kt"])
                 for r in _rows(os.path.join("eval",
                                "mms_structural_uncertainty.csv"))) / 1000.0, 0.05),
    ("agri enteric share", "agriculture", "06_results.tex",
     r"or\s*\\SI\{([\d]+)\}\{\\percent\} of the national agricultural total",
     lambda: _cell("key_categories.csv", "category", "Enteric fermentation",
                   "level_pct"), 0.2),
    ("agri livestock share", "agriculture", "06_results.tex",
     r"together account for approximately \\SI\{([\d]+)\}\{\\percent\} of the total",
     lambda: _cell("key_categories.csv", "category", "Enteric fermentation",
                   "level_pct")
             + _cell("key_categories.csv", "category", "Manure management",
                     "level_pct"), 0.7),
    ("agri proxy shift out", "agriculture", "06_results.tex",
     r"shifts \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\} out of Punjab",
     lambda: abs(_first_where(os.path.join("eval", "proxy_attribution.csv"),
                              "1 split indirect by stream",
                              province="Punjab")), 0.0),
    ("agri proxy shift back", "agriculture", "06_results.tex",
     r"shifts \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\} back to",
     lambda: _first_where(os.path.join("eval", "proxy_attribution.csv"),
                          "2 manure -> manure_applied", province="Punjab"), 0.0),
    ("agri provincial Punjab prose", "agriculture", "06_results.tex",
     r"Punjab contributes \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}, or",
     lambda: _first_where("provincial_totals_2024.csv", "TOTAL",
                          province="Punjab"), 0.05),
    ("agri provincial Sindh prose", "agriculture", "06_results.tex",
     r"contributes \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}, or \\SI\{23\}",
     lambda: _first_where("provincial_totals_2024.csv", "TOTAL",
                          province="Sindh"), 0.05),
    ("agri provincial KP prose", "agriculture", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}, or \\SI\{14\}",
     lambda: _first_where("provincial_totals_2024.csv", "TOTAL",
                          province="Khyber Pakhtunkhwa"), 0.05),
    ("agri provincial Balochistan prose", "agriculture", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}, or \\SI\{8\}",
     lambda: _first_where("provincial_totals_2024.csv", "TOTAL",
                          province="Balochistan"), 0.05),
    ("agri top district prose", "agriculture", "06_results.tex",
     r"Karachi has the largest estimated total at\s*\\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _agri_districttop_named("Karachi"), 0.0),
    # rc42: the census crosswalk (Wave 2) re-ranked the table - Karachi, Jhang, Sheikhupura,
    # Faisalabad, Muzaffargarh - and these anchors name the district beside each number, so
    # a re-ranking that the ordinal repair would paper over fails here by name.
    ("agri second district prose", "agriculture", "06_results.tex",
     r"Jhang follows\s*at \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _agri_districttop_named("Jhang"), 0.0),
    ("agri third district prose", "agriculture", "06_results.tex",
     r"and Sheikhupura at \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}\. Faisalabad",
     lambda: _agri_districttop_named("Sheikhpura"), 0.0),
    ("agri fourth fifth prose", "agriculture", "06_results.tex",
     r"Faisalabad and\s*Muzaffargarh contribute \\SI\{([\d.]+)\}\{\} and",
     lambda: _agri_districttop_named("Faisalabad"), 0.05),
    ("agri fifth prose", "agriculture", "06_results.tex",
     r"Muzaffargarh contribute \\SI\{[\d.]+\}\{\} and \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: _agri_districttop_named("Muzaffargarh"), 0.05),
    ("agri matiari prose", "agriculture", "06_results.tex",
     r"Its estimated total\s*is \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _agri_districttop_named("Matiari"), 0.0),
    ("agri karachi former placement", "agriculture", "06_results.tex",
     r"placed the shape on the GLW\s*surface \(\\SI\{([\d.]+)\}\{\}~Mt\)",
     lambda: 0.10, 0.0),   # the rc41 value, a historical statement (git show 063b43d1)
    ("agri karachi census cattle", "agriculture", "06_results.tex",
     r"separately---\\SI\{([\d.]+)\}\{\} million cattle",
     lambda: _karachi_census("cattle") / 1e6, 0.05),
    ("agri karachi census buffalo", "agriculture", "06_results.tex",
     r"million cattle and \\SI\{([\d.]+)\}\{\} million buffalo",
     lambda: _karachi_census("buffalo") / 1e6, 0.05),
    ("agri 1990 total", "agriculture", "06_results.tex",
     r"from approximately \\SI\{([\d]+)\}\{\}~Mt~\\COe\{\} in 1990",
     lambda: float(next(r for r in _rows("crt_AFOLU_table.csv")
                        if r["year"] == "1990" and r["code"] == "3")
                   ["CO2e_kt_AR5"]) / 1000.0, 0.3),
    ("agri CAGR", "agriculture", "06_results.tex",
     r"compound annual growth rate of\s*approximately \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * ((_cell("national_totals_2024.csv", "category", "TOTAL",
                             "co2e_Mt_AR5")
                       / (float(next(r for r in _rows("crt_AFOLU_table.csv")
                                     if r["year"] == "1990" and r["code"] == "3")
                          ["CO2e_kt_AR5"]) / 1000.0)) ** (1.0 / 34.0) - 1.0), 0.05),
    # rc41 M-3: the headline printed 223.3 (the evaluation harness's own re-implementation,
    # outputs/eval/sensitivity.csv) in four places and 223.4 (a second rounding of the
    # 2-dp totals file) in four more, against an engine total of 223.454. Every headline
    # site reads the sector's published total; the harness figure stays in its own tables.
    ("agri headline AR5", "agriculture", "06_results.tex",
     r"estimated at \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\} using AR5",
     lambda: _cell("national_totals_2024.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("agri trajectory 2024", "agriculture", "06_results.tex",
     r"to \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\} in 2024\. This corresponds",
     lambda: _cell("national_totals_2024.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("agri MC deterministic", "agriculture", "06_results.tex",
     r"deterministic estimate of \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _cell("national_totals_2024.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("agri S5 published total", "agriculture", "06_results.tex",
     r"carried the published\s*total to \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _cell("national_totals_2024.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("agri harness MMS total", "agriculture", "06b_air_pollutants.tex",
     r"own re-implementation is \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: float(next(r for r in _rows(os.path.join("eval", "mms_structural_uncertainty.csv"))
                        if r["configuration"].startswith("current"))["national_total_Mt"]),
     0.0),
    ("agri harness reference total", "agriculture", "06b_air_pollutants.tex",
     r"the inventory's reference total is \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: _cell("national_totals_2024.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("agri panel rows", "agriculture", "06_results.tex",
     r"The panel contains \\num\{([\d]+)\}",
     lambda: float(len(_rows(os.path.join("districts",
                                          "district_totals_by_year.csv")))), 0.0),
    ("agri district panel anchor rows", "agriculture", "06_results.tex",
     r"only the \\num\{(\d+)\} reference-year records",
     lambda: float(sum(1 for r in _rows(os.path.join("districts",
                                                     "district_totals_by_year.csv"))
                       if r["spatial_basis"] == "reference_year_pattern")), 0.0),
    ("agri sheikhupura 1990", "agriculture", "06_results.tex",
     r"Sheikhupura increases from approximately \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\} in",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows(os.path.join("districts",
                                             "district_totals_by_year.csv"))
                 if r["district"] == "Sheikhpura" and r["year"] == "1990"), 0.05),
    ("agri sheikhupura 2024", "agriculture", "06_results.tex",
     r"increases from approximately \\SI\{[\d.]+\}\{\}~Mt~\\COe\{\} in 1990 to\s*"
     r"\\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\} in 2024",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows(os.path.join("districts",
                                             "district_totals_by_year.csv"))
                 if r["district"] == "Sheikhpura" and r["year"] == "2024"), 0.05),
    ("agri MC width prose", "agriculture", "06_results.tex",
     r"half-width of approximately \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: float(_cell("uncertainty_montecarlo.csv", "category", "TOTAL",
                         "rel_uncert_pct_MC_95")), 0.05),
    ("agri rice growth factor", "agriculture", "06_results.tex",
     r"increased by a factor of approximately \\num\{([\d.]+)\} between 1990",
     lambda: float(next(r for r in _rows("crt_AFOLU_table.csv")
                        if r["year"] == "2024" and r["code"] == "3.C")
                   ["CO2e_kt_AR5"])
             / float(next(r for r in _rows("crt_AFOLU_table.csv")
                          if r["year"] == "1990" and r["code"] == "3.C")
                     ["CO2e_kt_AR5"]), 0.05),
    ("agri other growth low", "agriculture", "06_results.tex",
     r"factors of \\num\{([\d.]+)\}--\\num\{[\d.]+\} for the other",
     lambda: min(float(next(r for r in _rows("crt_AFOLU_table.csv")
                            if r["year"] == "2024" and r["code"] == c)
                       ["CO2e_kt_AR5"])
                 / float(next(r for r in _rows("crt_AFOLU_table.csv")
                              if r["year"] == "1990" and r["code"] == c)
                         ["CO2e_kt_AR5"])
                 for c in ("3.A", "3.B", "3.D")), 0.1),
    ("agri other growth high", "agriculture", "06_results.tex",
     r"factors of \\num\{[\d.]+\}--\\num\{([\d.]+)\} for the other",
     lambda: max(float(next(r for r in _rows("crt_AFOLU_table.csv")
                            if r["year"] == "2024" and r["code"] == c)
                       ["CO2e_kt_AR5"])
                 / float(next(r for r in _rows("crt_AFOLU_table.csv")
                              if r["year"] == "1990" and r["code"] == c)
                         ["CO2e_kt_AR5"])
                 for c in ("3.A", "3.B", "3.D")), 0.1),
    ("agri housing NH3", "agriculture", "06b_air_pollutants.tex",
     r"storage contribute approximately \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: _agri_air_nh3_split()["NH3 - housing and storage"] / 1000.0, 0.005),
    ("agri applied NH3", "agriculture", "06b_air_pollutants.tex",
     r"soils contributes a further \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: _agri_air_nh3_split()["NH3 - manure applied to soils"] / 1000.0, 0.005),
    ("agri synthetic NH3", "agriculture", "06b_air_pollutants.tex",
     r"Synthetic fertiliser contributes\s*\\SI\{([\d.]+)\}\{\}~Mt",
     lambda: _agri_air_nh3_split()["NH3 - synthetic fertiliser"] / 1000.0, 0.005),
    ("agri grazing NH3", "agriculture", "06b_air_pollutants.tex",
     r"grazing deposition contributes approximately \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: (_agri_air_nh3_split()["NH3 - pasture deposition (cattle-type)"]
              + _agri_air_nh3_split()
              ["NH3 - pasture deposition (sheep/goat/other)"]) / 1000.0, 0.005),
    ("agri NH3 Punjab", "agriculture", "06b_air_pollutants.tex",
     r"Punjab contributes \\SI\{([\d.]+)\}\{\}~Mt of \\NHthree\{\}",
     lambda: sum(float(r["emissions_kt"])
                 for r in _rows("air_pollutants_provincial_2024.csv")
                 if r["pollutant"] == "NH3" and r["province"] == "Punjab") / 1000.0,
     0.005),
    ("agri NH3 Sindh", "agriculture", "06b_air_pollutants.tex",
     r"followed by Sindh at \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: sum(float(r["emissions_kt"])
                 for r in _rows("air_pollutants_provincial_2024.csv")
                 if r["pollutant"] == "NH3" and r["province"] == "Sindh") / 1000.0,
     0.005),
    ("agri NH3 KP", "agriculture", "06b_air_pollutants.tex",
     r"Pakhtunkhwa at \\SI\{([\d.]+)\}\{\}~Mt and Balochistan",
     lambda: sum(float(r["emissions_kt"])
                 for r in _rows("air_pollutants_provincial_2024.csv")
                 if r["pollutant"] == "NH3"
                 and r["province"] == "Khyber Pakhtunkhwa") / 1000.0, 0.005),
    ("agri NH3 Balochistan", "agriculture", "06b_air_pollutants.tex",
     r"Balochistan at \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: sum(float(r["emissions_kt"])
                 for r in _rows("air_pollutants_provincial_2024.csv")
                 if r["pollutant"] == "NH3"
                 and r["province"] == "Balochistan") / 1000.0, 0.005),
    # rc42 (Wave 3): the held air-district product was regenerated after the census crosswalk
    # (Wave 2) and the ranking moved; each anchor names its district, so a re-ranking cannot
    # pass as a repaired number beside the old name.
    ("agri NH3 district 1", "agriculture", "06b_air_pollutants.tex",
     r"Jhang has the highest district estimate at approximately \\SI\{([\d]+)\}\{\}~kt",
     lambda: _nh3_district("Jhang"), 0.5),
    ("agri NH3 district 2", "agriculture", "06b_air_pollutants.tex",
     r"followed by\s*Muzaffargarh at \\SI\{([\d]+)\}\{\}~kt",
     lambda: _nh3_district("Muzaffargarh"), 0.5),
    ("agri NH3 district 3", "agriculture", "06b_air_pollutants.tex",
     r"Sheikhupura at \\SI\{([\d]+)\}\{\}~kt",
     lambda: _nh3_district("Sheikhpura"), 0.5),
    ("agri NH3 district 4", "agriculture", "06b_air_pollutants.tex",
     r"Sargodha at \\SI\{([\d]+)\}\{\}~kt",
     lambda: _nh3_district("Sargodha"), 0.5),
    ("agri NH3 district 5", "agriculture", "06b_air_pollutants.tex",
     r"Rahim Yar Khan at \\SI\{([\d]+)\}\{\}~kt",
     lambda: _nh3_district("Rahim Yar Khan"), 0.5),
    ("agri NH3 2024 timeseries", "agriculture", "06b_air_pollutants.tex",
     r"to\s*\\SI\{([\d]+)\}\{\}~kt in 2024, a factor of",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="NH3"), 0.5),
    ("agri NH3 growth factor", "agriculture", "06b_air_pollutants.tex",
     r"kt in 2024, a factor of \\num\{([\d.]+)\}",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="NH3") / 784.0, 0.05),
    ("agri CO 2024 timeseries", "agriculture", "06b_air_pollutants.tex",
     r"approximately \\SI\{250\}\{\}~kt to \\SI\{([\d]+)\}\{\}~kt, a",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="CO"), 0.5),
    ("agri CO growth factor", "agriculture", "06b_air_pollutants.tex",
     r"~kt to \\SI\{[\d]+\}\{\}~kt, a\s*factor of \\num\{([\d.]+)\}",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="CO") / 250.0, 0.05),
    ("agri MC NH3 mean", "agriculture", "06b_air_pollutants.tex",
     r"mean \\NHthree\{\} estimate of \\SI\{([\d]+)\}\{\}~kt",
     lambda: _cell("air_uncertainty_montecarlo.csv", "pollutant", "NH3",
                   "mean_kt"), 0.0),
    ("agri MC NH3 low", "agriculture", "06b_air_pollutants.tex",
     r"interval of \\SI\{([\d]+)\}\{\}--\\SI\{[\d]+\}\{\}~kt",
     lambda: _cell("air_uncertainty_montecarlo.csv", "pollutant", "NH3",
                   "P2.5_kt"), 0.0),
    ("agri MC NH3 high", "agriculture", "06b_air_pollutants.tex",
     r"interval of \\SI\{[\d]+\}\{\}--\\SI\{([\d]+)\}\{\}~kt",
     lambda: _cell("air_uncertainty_montecarlo.csv", "pollutant", "NH3",
                   "P97.5_kt"), 0.0),
    ("agri MMS current grazing", "agriculture", "06b_air_pollutants.tex",
     r"It assigns \\SI\{([\d]+)\}\{\\percent\} of excreted",
     lambda: 100.0 * _first_where(os.path.join("eval",
                                  "mms_structural_uncertainty.csv"),
                                  "grazing_share_of_excreted",
                                  configuration="current (FAOSTAT-consistent)"),
     0.3),
    ("agri MMS bench grazing", "agriculture", "06b_air_pollutants.tex",
     r"configuration assigns \\SI\{([\d]+)\}\{\\percent\} of excreted nitrogen "
     r"to grazing",
     lambda: 100.0 * _first_where(os.path.join("eval",
                                  "mms_structural_uncertainty.csv"),
                                  "grazing_share_of_excreted",
                                  configuration="benchmark-like (high grazing)"),
     0.3),
    ("agri MMS gleam grazing", "agriculture", "06b_air_pollutants.tex",
     r"\\citep\{gleam2022\} assigns \\SI\{([\d]+)\}\{\\percent\} to",
     lambda: 100.0 * _first_where(os.path.join("eval",
                                  "mms_structural_uncertainty.csv"),
                                  "grazing_share_of_excreted",
                                  configuration="GLEAM 3.0 South Asia"), 0.8),
    ("agri MMS GHG span", "agriculture", "06b_air_pollutants.tex",
     r"total varies by approximately\s*\\SI\{([\d]+)\}\{\}~Mt~\\COe\{\}",
     lambda: max(float(r["national_total_Mt"]) for r in _rows(os.path.join(
         "eval", "mms_structural_uncertainty.csv")))
             - min(float(r["national_total_Mt"]) for r in _rows(os.path.join(
                 "eval", "mms_structural_uncertainty.csv"))), 0.4),
    ("agri spatial cells", "agriculture", "06b_air_pollutants.tex",
     r"\\num\{([\d]+)\} grid cells within Pakistan",
     lambda: float(json.load(open(os.path.join(OUT, "eval",
                             "spatial_nh3_validation.json")))
                   ["all_sectors"]["cells"]), 0.0),
    ("agri spatial regridded benchmark", "agriculture", "06b_air_pollutants.tex",
     r"The resulting total is \\SI\{([\d]+)\}\{\}~kt",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["all_sectors"]["benchmark_kt"], 0.5),
    ("agri spatial rho", "agriculture", "06b_air_pollutants.tex",
     r"\$\\rho=([\d.]+)\$, log-space",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["all_sectors"]["spearman"], 0.005),
    ("agri spatial log pearson", "agriculture", "06b_air_pollutants.tex",
     r"log-space Pearson \$r=([\d.]+)\$",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["all_sectors"]["pearson_log10"], 0.005),
    ("agri spatial hotspot", "agriculture", "06b_air_pollutants.tex",
     r"and \\SI\{([\d]+)\}\{\\percent\} overlap among top-decile",
     lambda: 100.0 * json.load(open(os.path.join(OUT, "eval",
                               "spatial_nh3_validation.json")))
             ["all_sectors"]["hotspot_overlap_top10pct"], 0.3),
    ("agri provincial ratio low", "agriculture", "06b_air_pollutants.tex",
     r"approximately \\num\{([\d.]+)\}--\\num\{[\d.]+\}\. This indicates",
     lambda: min(v["ratio"] for k, v in json.load(open(os.path.join(
         OUT, "eval", "spatial_nh3_validation.json")))["provincial"].items()
                 if k in ("Punjab", "Sindh", "Khyber Pakhtunkhwa")), 0.005),
    ("agri provincial ratio high", "agriculture", "06b_air_pollutants.tex",
     r"approximately \\num\{[\d.]+\}--\\num\{([\d.]+)\}\. This indicates",
     lambda: max(v["ratio"] for k, v in json.load(open(os.path.join(
         OUT, "eval", "spatial_nh3_validation.json")))["provincial"].items()
                 if k in ("Punjab", "Sindh", "Khyber Pakhtunkhwa")), 0.005),
    ("agri balochistan ratio", "agriculture", "06b_air_pollutants.tex",
     r"exception, with a ratio of \\num\{([\d.]+)\}",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["provincial"]["Balochistan"]["ratio"], 0.005),
    ("agri synthetic stream r", "agriculture", "06b_air_pollutants.tex",
     r"with \$r=([\d.]+)\$, \\SI\{[\d]+\}\{\\percent\} top-decile",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["by_stream"]["synthetic"]["pearson"], 0.005),
    ("agri synthetic stream hotspot", "agriculture", "06b_air_pollutants.tex",
     r"\$r=[\d.]+\$, \\SI\{([\d]+)\}\{\\percent\} top-decile",
     lambda: 100.0 * json.load(open(os.path.join(OUT, "eval",
                               "spatial_nh3_validation.json")))
             ["by_stream"]["synthetic"]["hotspot_overlap_top10pct"], 0.5),
    ("agri synthetic stream ratio", "agriculture", "06b_air_pollutants.tex",
     r"overlap and a level ratio of \\num\{([\d.]+)\}",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["by_stream"]["synthetic"]["ratio"], 0.005),
    ("agri burning stream hotspot", "agriculture", "06b_air_pollutants.tex",
     r"\\SI\{([\d]+)\}\{\\percent\} top-decile overlap and a level ratio of "
     r"\\num\{0\.21\}",
     lambda: 100.0 * json.load(open(os.path.join(OUT, "eval",
                               "spatial_nh3_validation.json")))
             ["by_stream"]["burning"]["hotspot_overlap_top10pct"], 0.5),
    ("agri burning stream ratio", "agriculture", "06b_air_pollutants.tex",
     r"top-decile overlap and a level ratio of \\num\{([\d.]+)\}\.",
     lambda: json.load(open(os.path.join(OUT, "eval",
                            "spatial_nh3_validation.json")))
             ["by_stream"]["burning"]["ratio"], 0.005),
    ("agri SANH growth", "agriculture", "06b_air_pollutants.tex",
     r"increases by a factor of \\num\{([\d.]+)\} between 2015 and 2024",
     lambda: _first_where("benchmark_air_comparison.csv", "activity_growth",
                          source="SANH 2026 (ESSD)", scope="TOTAL"), 0.0),
    ("agri SANH 2015 engine", "agriculture", "06b_air_pollutants.tex",
     r"this inventory estimates \\SI\{([\d]+)\}\{\}~kt \\NHthree\{\}",
     lambda: _first_where("benchmark_air_comparison.csv", "engine_kt",
                          source="SANH 2026 (ESSD)", scope="TOTAL"), 0.0),
    ("agri SANH ratio", "agriculture", "06b_air_pollutants.tex",
     r"benchmark \\citep\{sanh2026\}\. The ratio is \\num\{([\d.]+)\}",
     lambda: _first_where("benchmark_air_comparison.csv", "ratio",
                          source="SANH 2026 (ESSD)", scope="TOTAL"), 0.0),
    ("agri SANH anchor ratio", "agriculture", "06b_air_pollutants.tex",
     r"2024 estimate would produce a ratio of \\num\{([\d.]+)\}",
     lambda: _first_where("benchmark_air_comparison.csv", "ratio_anchor",
                          source="SANH 2026 (ESSD)", scope="TOTAL"), 0.0),
    ("agri EDGAR v8 ratio", "agriculture", "06b_air_pollutants.tex",
     r"\\num\{([\d.]+)\} times the corresponding EDGAR v8",
     lambda: _first_where("benchmark_air_comparison.csv", "ratio",
                          source="EDGAR v8", scope="TOTAL"), 0.0),
    ("agri HTAP ratio", "agriculture", "06b_air_pollutants.tex",
     r"and \\num\{([\d.]+)\} times the HTAP v3",
     lambda: _first_where("benchmark_air_comparison.csv", "ratio",
                          source="HTAP v3", scope="TOTAL"), 0.0),
    ("agri fert bench ratio", "agriculture", "06b_air_pollutants.tex",
     r"Synthetic-fertiliser \\NHthree\{\} is \\num\{([\d.]+)\} times the",
     lambda: _first_where("benchmark_air_comparison.csv", "ratio",
                          source="SANH 2026 (ESSD)",
                          scope="Managed soils - synthetic"), 0.0),
    ("agri livestock bench ratio", "agriculture", "06b_air_pollutants.tex",
     r"Livestock \\NHthree\{\} is approximately \\num\{([\d.]+)\} times",
     lambda: _first_where("benchmark_air_comparison.csv", "ratio",
                          source="SANH 2026 (ESSD)",
                          scope="Livestock (grazing+manure+management)"), 0.0),
    ("agri residue bench ratio", "agriculture", "06b_air_pollutants.tex",
     r"Residue-burning \\NHthree\{\} is \\num\{([\d.]+)\} times",
     lambda: _first_where("benchmark_air_comparison.csv", "ratio",
                          source="SANH 2026 (ESSD)",
                          scope="Field burning of residues"), 0.0),
    ("agri fracgasf", "agriculture", "04c_shared_ledger.tex",
     r"kg \\NHthree\{\}-N per kg N & ([\d.]+)\$\^\{b\}\$ & 30",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0], 0.001),
    # The eighth review's NH3 item: the display equation, the prose restatement, the
    # FracGASF sum and BOTH supplements each carried their own copy of this scalar,
    # and the equation drifted to 0.1615 - a value no engine path reproduces - while
    # only the tables were anchored. Every copy is now pinned to the ONE generator,
    # fertiliser_mix.fracgasf(), and the Eq. 11.9 sum to fracgasf()+0.007.
    ("agri fracgasf equation", "agriculture", "04c_shared_ledger.tex",
     r"EF\^\{\\NHthree\{\}\\text\{-\}N\}_j \\;=\\; ([\d.]+)",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0], 0.0001),
    ("agri fracgasf prose restatement", "agriculture", "04c_shared_ledger.tex",
     r"The value ([\d.]+) is already expressed",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0], 0.0001),
    # rc36: the buffalo TAN fraction was covered only by coincidence - the nitrogen
    # ledger's stale "0.50" cell matched it - and the ledger's first live run since the
    # census re-base moved that cell to 0.49. It is a Guidebook parameter
    # (emission_factors.csv emep_tan_buffalo), so it is pinned to the parameter store.
    ("agri buffalo TAN fraction", "agriculture", "04c_shared_ledger.tex",
     r"Buffalo manure is assigned a TAN fraction of \\num\{([\d.]+)\}",
     lambda: _ef("emep_tan_buffalo"), 0.0),
    ("agri fracgasf eq119 sum", "agriculture", "04c_shared_ledger.tex",
     r"f_\{NO,SF\} \\;=\\; ([\d.]+)",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0] + 0.007, 0.0001),
    ("agri fracgasf S5 factor", "agriculture", "S5_qaqc.tex",
     r"f_\{\\NHthree\{\},SF\}=([\d.]+)\$ drives",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0], 0.0001),
    ("agri fracgasf S5 sum", "agriculture", "S5_qaqc.tex",
     r"Frac_\{GASF\}\}=([\d.]+)\$",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0] + 0.007, 0.0001),
    ("agri fracgasf S2 factor", "agriculture", "S2_provenance.tex",
     r"\$f_\{\\NHthree\{\},SF\}\$ ([\d.]+)",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0], 0.0001),
    ("agri fracgasf S2 sum", "agriculture", "S2_provenance.tex",
     r"of Eq\.~11\.9, is ([\d.]+)\)",
     lambda: __import__("pkinv.sectors.agriculture.fertiliser_mix",
                        fromlist=["fertiliser_mix"]).fracgasf()[0] + 0.007, 0.0001),
    ("agri audited N total", "agriculture", "04c_shared_ledger.tex",
     r"audited national nitrogen total \(\\SI\{([\d.]+)\}\{\}~Mt~N\)",
     lambda: float(next(r for r in _data_rows(os.path.join(
         "activity", "fertilizer_2024.csv"))
         if r["item"] == "nitrogen_N_offtake")["value_t"]) / 1e6, 0.0),
    ("agri FON prior IPCC correction", "agriculture", "S5_qaqc.tex",
     r"falls from \\SI\{[\d.]+\}\{\} to\s*\\SI\{([\d.]+)\}\{\}~Mt~N",
     lambda: float(next(r for r in read_rows(os.path.join(paths.DATA, "baselines", "rc67_integrated_campaign", "outputs", "n_ledger_2024.csv"))
                        if r["flow"].startswith("= N available"))["Mt_N"]), 0.0),

    ("agri AWD delta", "agriculture", "04b_emission_factors.tex",
     r"reduces\s*the national total by \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: -float(next(r for r in _rows(os.path.join("eval", "sensitivity.csv"))
                         if "intermittent" in r["scenario"])["delta"]), 0.0),
    ("agri rainfed delta", "agriculture", "04b_emission_factors.tex",
     r"rainfed assumption reduces it by\s*\\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: -float(next(r for r in _rows(os.path.join("eval", "sensitivity.csv"))
                         if "rainfed" in r["scenario"])["delta"]), 0.0),
    ("agri EF1 aggregate delta", "agriculture", "04b_emission_factors.tex",
     r"\$0\.010\$ raises the national total by \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: float(next(r for r in _rows(os.path.join("eval", "sensitivity.csv"))
                        if "0.010" in r["scenario"])["delta"]), 0.0),
    ("agri Cui soils", "agriculture", "04b_emission_factors.tex",
     r"managed-soils estimate of \\SI\{([\d.]+)\}\{\}~Mt, close",
     lambda: float(next(r for r in _rows(os.path.join("eval", "sensitivity.csv"))
                        if "0.0055" in r["scenario"])["soils"]), 0.0),
    ("agri GLEAM delta", "agriculture", "04b_emission_factors.tex",
     r"\\citep\{gleam2022\} raises the\s*national total by \\SI\{([\d.]+)\}\{\}~Mt",
     lambda: float(next(r for r in _rows(os.path.join("eval", "sensitivity.csv"))
                        if "GLEAM" in r["scenario"])["delta"]), 0.0),
    ("agri GLEAM manure", "agriculture", "04b_emission_factors.tex",
     r"management \(\\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\}~Mt\)",
     lambda: float(next(r for r in _rows(os.path.join("eval", "sensitivity.csv"))
                        if "GLEAM" in r["scenario"])["manure"]), 0.05),
    ("agri GLEAM soils", "agriculture", "04b_emission_factors.tex",
     r"moves managed soils \(\\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\}~Mt\)",
     lambda: float(next(r for r in _rows(os.path.join("eval", "sensitivity.csv"))
                        if "GLEAM" in r["scenario"])["soils"]), 0.05),
    ("agri urea N share", "agriculture", "04c_shared_ledger.tex",
     r"Urea supplies approximately \\SI\{([\d]+)\}\{\\percent\} of the nitrogen",
     lambda: 100.0 * __import__("pkinv.sectors.agriculture.fertiliser_mix",
                                fromlist=["fertiliser_mix"]).national_shares()[0]
             ["Urea"], 0.4),
    ("agri punjab share prose", "agriculture", "06_results.tex",
     r"or \\SI\{([\d]+)\}\{\\percent\} of the national total\. Sindh",
     lambda: 100.0 * _first_where("provincial_totals_2024.csv", "TOTAL",
                                  province="Punjab")
             / _cell("national_totals_2024.csv", "category", "TOTAL",
                     "co2e_Mt_AR5"), 0.3),
    ("agri muzaffargarh 2024", "agriculture", "06_results.tex",
     r"and Muzaffargarh from \\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\}~Mt~\\COe\{\}",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows(os.path.join("districts",
                                             "district_totals_by_year.csv"))
                 if r["district"] == "Muzaffargarh" and r["year"] == "2024"), 0.05),
    ("agri rice rank rho", "agriculture", "01_introduction.tex",
     r"Spearman rank correlation of \\num\{([\d.]+)\} with official district rice",
     lambda: json.load(open(os.path.join(OUT, "eval", "validation",
                            "district_rice_vs_records.json")))["spearman_rho"],
     0.005),
    ("agri rice rank rho table", "agriculture", "05_validation.tex",
     r"& 66 & ([\d.]+) \\\\",
     lambda: json.load(open(os.path.join(OUT, "eval", "validation",
                            "district_rice_vs_records.json")))["spearman_rho"],
     0.005),
    ("agri rice rank n", "agriculture", "05_validation.tex",
     r"& (66) & [\d.]+ \\\\",
     lambda: float(json.load(open(os.path.join(OUT, "eval", "validation",
                             "district_rice_vs_records.json")))["n_matched"]), 0.0),
    ("agri wheat rank rho", "agriculture", "01_introduction.tex",
     r"reaches \\num\{([\d.]+)\} against district wheat area",
     lambda: _district_multi_check("Managed soils")["spearman_rho"], 0.005),
    ("agri wheat rank rho prose", "agriculture", "05_validation.tex",
     r"The resulting rank correlation is \$\\rho=([\d.]+)\$",
     lambda: _district_multi_check("Managed soils")["spearman_rho"], 0.005),
    ("agri wheat rank rho table", "agriculture", "05_validation.tex",
     r"& 85 & ([\d.]+) \\\\",
     lambda: _district_multi_check("Managed soils")["spearman_rho"], 0.005),
    ("agri wheat rank n", "agriculture", "05_validation.tex",
     r"& (85) & [\d.]+ \\\\",
     lambda: float(_district_multi_check("Managed soils")["n_matched"]), 0.0),
    ("agri wheat rank n prose", "agriculture", "05_validation.tex",
     r"district wheat area across (\d+) matched districts",
     lambda: float(_district_multi_check("Managed soils")["n_matched"]), 0.0),
    ("agri rice rank n prose", "agriculture", "05_validation.tex",
     r"Across (\d+) matched\ndistricts the correlation",
     lambda: float(json.load(open(os.path.join(OUT, "eval", "validation",
                             "district_rice_vs_records.json")))["n_matched"]), 0.0),
    # rc42 (M-7): tab:proxyattr is joined by label in labelled_tables.py; the nine claims
    # that used to anchor it had every printed value baked into their regexes, so a cell
    # that moved made the anchor "lost" and a column no claim named (manure) drifted
    # unchecked (+2.13 printed against 2.08 in the regenerated eval product).

    ("agri residue SO2 factor", "agriculture", "04c_shared_ledger.tex",
     r"SO\$_2\$[^&]*&[^&]*& ([\d.]+) & [\d]+ \\\\",
     lambda: float(next(r for r in _data_rows("emission_factors.csv")
                        if r["ef_id"] == "burning_gef_so2")["value"]), 0.0),
    ("national S4 stream count", "national", "06_results.tex",
     r"unallocated is the \\num\{([\d]+)\} cruise-aviation streams",
     lambda: float(sum(1 for r in _rows("pakemis_source_streams.csv")
                       if r["geometry_id"] == "S4:no-native-geometry")), 0.0),
    ("national S4 share", "national", "06_results.tex",
     r"streams\s+\(\\SI\{([\d.]+)\}\{\\percent\} of the national total\): fuel burned",
     lambda: 100.0 * sum(float(r["emissions_ar5"])
                         for r in _rows("pakemis_source_streams.csv")
                         if r["geometry_id"] == "S4:no-native-geometry")
             / sum(float(r["emissions_ar5"])
                   for r in _rows("pakemis_source_streams.csv")), 0.005),
    ("national S4 count brackets sentence", "national", "06_results.tex",
     r"price them\. The \\num\{([\d]+)\}\s+no-native-geometry cruise streams",
     lambda: float(sum(1 for r in _rows("pakemis_source_streams.csv")
                       if r["geometry_id"] == "S4:no-native-geometry")), 0.0),
    # rc47 Wave 4 retired the industry-share sentence with the industry S4 era;
    # the appendix now narrates the placement, and the S4 share claims above cover
    # what is left (the cruise streams).
    ("national S4 count appendix", "national", "14_appendix.tex",
     r"at all: \\num\{([\d]+)\} cruise-aviation streams",
     lambda: float(sum(1 for r in _rows("pakemis_source_streams.csv")
                       if r["geometry_id"] == "S4:no-native-geometry")), 0.0),
    ("national S4 share appendix", "national", "14_appendix.tex",
     r"cruise-aviation streams \(\\SI\{([\d.]+)\}\{\\percent\} of the national total\)",
     lambda: 100.0 * sum(float(r["emissions_ar5"])
                         for r in _rows("pakemis_source_streams.csv")
                         if r["geometry_id"] == "S4:no-native-geometry")
             / sum(float(r["emissions_ar5"])
                   for r in _rows("pakemis_source_streams.csv")), 0.005),
    # ---- claims below are pre-existing transport anchors ----
    ("transport total", "transport", "06_results.tex",
     r"\\textbf\{Total\}            & \\textbf\{([\d.]+)\}",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("transport road", "transport", "06_results.tex",
     r"Road transport \(1A3b\)     & ([\d.]+)",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category", "Road transport", "co2e_Mt_AR5"), 0.0),
    ("transport offroad", "transport", "06_results.tex",
     r"Mixed off-road \(1A4c/1A2\) &  ([\d.]+)",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category",
                   "Mixed off-road (1A4c/1A2)", "co2e_Mt_AR5"), 0.0),
    ("transport two-wheeler", "transport", "06_results.tex",
     r"Two-wheeler petrol          & ([\d.]+)",
     lambda: _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                        subitem="2W Petrol CO2"), 0.0),
    ("transport offroad road-factor N2O", "transport", "04b_emission_factors.tex",
     r"instead of \\SI\{([\d.]+)\}\{\\mega\\tonne\}, and the category total",
     lambda: _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                        category="Mixed off-road (1A4c/1A2)", gas="N2O"), 0.001),
    ("transport PM2.5", "transport", "06b_air_pollutants.tex",
     r"\\PM\{\}                &    ([\d.]+) &",
     lambda: _sum_where("transport_air_pollutants_%d.csv" % _transport_year(), "emissions_kt",
                        pollutant="PM2.5"), 0.02),
    ("transport road variance", "transport", "06_results.tex",
     r"Road transport\s+&\s*[\d.]+ &\s*([\d.]+) ",
     lambda: _keycat("Road transport", "variance_share_pct_independent_approx"), 0.02),
    # ---- waste ----
    ("waste sector total", "waste", "06_results.tex",
     r"\\textbf\{Total\}            &                   &         & \\textbf\{([\d.]+)\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("waste wastewater CH4", "waste", "06_results.tex",
     r"Domestic wastewater \(4D1\) & \\CHfour\{\}\s+&\s*[\d.]+ & ([\d.]+)",
     lambda: _sum_where("waste_by_stream_%d.csv" % _waste_year(), "co2e_Mt_AR5",
                        category="Domestic wastewater", gas="CH4"), 0.0),
    ("waste river MCF", "waste", "06_results.tex",
     r"Sewer MCF \\num\{0.1\} \(river reading\) & ([\d.]+)",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category",
                   "Sensitivity: wastewater on the river-discharge MCF (category total)",
                   "co2e_Mt_AR5"), 0.0),
    ("waste no spin-up", "waste", "06_results.tex",
     r"Disposal without spin-up            &  ([\d.]+)",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category",
                   "Sensitivity: disposal without spin-up", "co2e_Mt_AR5"), 0.0),
    ("waste PM2.5", "waste", "06b_air_pollutants.tex",
     r"\\PM\{\}               &  ([\d.]+) ",
     lambda: _sum_where("waste_air_pollutants_%d.csv" % _waste_year(), "emissions_kt",
                        pollutant="PM2.5"), 0.02),
    ("waste wastewater variance", "waste", "06_results.tex",
     r"Domestic wastewater  & [\d.]+ & ([\d.]+) ",
     lambda: _keycat("Domestic wastewater", "variance_share_pct_independent_approx"), 0.02),
    # ---- waste: abstract (August 2026 repair round - every headline number anchored) ----
    ("waste abstract total", "waste", "00_abstract.tex",
     r"sector for\s*FY2023--24 at\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("waste abstract AR6", "waste", "00_abstract.tex",
     r"AR5, \\SI\{([\d.]+)\}\{\\mega\\tonne\} on AR6",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR6"), 0.0),
    ("waste abstract wastewater", "waste", "00_abstract.tex",
     r"wastewater \(4D1\) at \\SI\{([\d.]+)\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5"), 0.0),
    ("waste abstract disposal", "waste", "00_abstract.tex",
     r"disposal \(4A\)\s*at \\SI\{([\d.]+)\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Solid waste disposal",
                   "co2e_Mt_AR5"), 0.0),
    ("waste abstract burning", "waste", "00_abstract.tex",
     r"open burning \(4C2\) at \\SI\{([\d.]+)\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Open burning of waste",
                   "co2e_Mt_AR5"), 0.0),
    ("waste abstract national share", "waste", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of a ten-sector national inventory",
     lambda: _sector("waste", "share_pct"), 0.0),
    # The rc11 parameter-rerun interval, wherever it is quoted as a range.
    # rc67: re-anchored. The caption names each member's KIND (national_configurations.csv
    # family_kind) instead of listing three numbers as one set of "alternatives".
    ("results family low member", "national", "06_results.tex",
     r"fuel-property\s*alternative at \\SI\{([\d.]+)\}\{\},",
     lambda: _first_where("power_uncertainty_scenarios_fy2023_24.csv", "deterministic_Mt",
                          family_id="grid_plant_cv_restated"), 0.05),
    ("results family high member", "national", "06_results.tex",
     r"a coverage alternative at \\SI\{([\d.]+)\}\{\} \(the K-Electric",
     lambda: _first_where("power_uncertainty_scenarios_fy2023_24.csv", "deterministic_Mt",
                          family_id="grid_plus_ke"), 0.05),
    ("results family legacy member", "national", "06_results.tex",
     r"retained legacy control at \\SI\{([\d.]+)\}\{\\mega\\tonne\}, three kinds",
     lambda: _configuration("power_table3_legacy_control", "alternative_value_Mt"), 0.0),
    ("benchmarks agriculture below EDGAR", "national", "10_benchmarks.tex",
     r"agriculture is \\SI\{([\d]+)\}\{\\mega\\tonne\} below\s*EDGAR",
     lambda: _bench("EDGAR", "TOTAL", "benchmark_Mt_co2e", 2024)
             - _bench("EDGAR", "TOTAL", "engine_Mt_co2e", 2024), 0.5),
    ("waste abstract rerun low", "waste", "00_abstract.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} \(2\.5th",
     lambda: _first_where("waste_parameter_mc_%d.csv" % _waste_year(), "P2.5",
                          scope="SECTOR"), 0.05),
    ("waste abstract rerun high", "waste", "00_abstract.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} \(2\.5th",
     lambda: _first_where("waste_parameter_mc_%d.csv" % _waste_year(), "P97.5",
                          scope="SECTOR"), 0.05),
    ("waste results rerun low", "waste", "06_results.tex",
     r"interval at\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_parameter_mc_%d.csv" % _waste_year(), "P2.5",
                          scope="SECTOR"), 0.05),
    ("waste results rerun high", "waste", "06_results.tex",
     r"interval at\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_parameter_mc_%d.csv" % _waste_year(), "P97.5",
                          scope="SECTOR"), 0.05),
    ("waste limitations rerun low", "waste", "08_limitations.tex",
     r"interval of \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_parameter_mc_%d.csv" % _waste_year(), "P2.5",
                          scope="SECTOR"), 0.05),
    ("waste limitations rerun high", "waste", "08_limitations.tex",
     r"interval of \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_parameter_mc_%d.csv" % _waste_year(), "P97.5",
                          scope="SECTOR"), 0.05),
    # the five non-effluent stream bands, quoted as a range in results and limitations
    ("waste stream band floor", "waste", "06_results.tex",
     r"bands between \\SI\{([\d]+)\}\{\\percent\}",
     lambda: min(float(r["uncert_pct"]) for r in
                 _rows("waste_by_stream_%d.csv" % _waste_year())), 0.5),
    ("waste stream band five-stream high", "waste", "06_results.tex",
     r"and \\SI\{([\d]+)\}\{\\percent\}; the",
     lambda: max(float(r["uncert_pct"]) for r in
                 _rows("waste_by_stream_%d.csv" % _waste_year())
                 if r["subitem"] != "Domestic wastewater N2O"), 0.5),
    ("waste limitations band floor", "waste", "08_limitations.tex",
     r"carry between\s*\\SI\{([\d]+)\}\{\\percent\}",
     lambda: min(float(r["uncert_pct"]) for r in
                 _rows("waste_by_stream_%d.csv" % _waste_year())), 0.5),
    ("waste limitations band high", "waste", "08_limitations.tex",
     r"and \\SI\{([\d]+)\}\{\\percent\}; wastewater",
     lambda: max(float(r["uncert_pct"]) for r in
                 _rows("waste_by_stream_%d.csv" % _waste_year())
                 if r["subitem"] != "Domestic wastewater N2O"), 0.5),
    ("waste limitations A1", "waste", "08_limitations.tex",
     r"sector reads \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ by quadrature",
     lambda: _mc("within_sector", "waste", "approach1_pct_95"), 0.05),
    # the log-variance-matched equivalent declaration and the endpoint arithmetic
    ("waste S1 effluent equivalent", "waste", "S1_uncertainty.tex",
     r"symmetric equivalent \(about \\SI\{([\d.]+)\}\{\\percent\}\), the",
     # rc67: the FACTOR's own equivalent, from the inputs product. This read the N2O
     # stream's band (the factor combined with population and the nitrogen chain),
     # which the sentence does not describe: 268.0 for the stream, 266.8 for the factor.
     lambda: _first_where("waste_uncertainty_inputs_%d.csv" % _waste_year(),
                          "uncert_pct_95", variable="ww_ef_effluent"), 0.5),
    # rc67: the endpoint SCENARIO's own nitrous oxide. The old getter scaled the
    # reference by 0.25/0.005; the ceiling is 0.075 now, and under the 2019 method the
    # plant term does not scale with the effluent factor, so the scenario is read.
    ("waste S1 effluent ceiling arithmetic", "waste", "S1_uncertainty.tex",
     r"alone\s*reaches about \\SI\{([\d]+)\}\{\\mega\\tonne\}",
     lambda: (_first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                           "deterministic", structural_scenario="effluent_ef_high")
              - _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                             "deterministic", structural_scenario="reference")
              + _first_where("waste_by_stream_%d.csv" % _waste_year(), "co2e_Mt_AR5",
                             subitem="Domestic wastewater N2O")), 0.5),
    # The 2006 equation is linear in the effluent factor, so its ceiling is its own
    # nitrous oxide (the 2006 scenario less the reference, plus the reference's N2O)
    # scaled to the 2006 bound.
    ("waste S1 effluent ceiling arithmetic, 2006 range", "waste", "S1_uncertainty.tex",
     r"it reached\s*about \\SI\{([\d]+)\}\{\\mega\\tonne\}",
     lambda: (_first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                           "deterministic", structural_scenario="n2o_method_ipcc2006")
              - _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                             "deterministic", structural_scenario="reference")
              + _first_where("waste_by_stream_%d.csv" % _waste_year(), "co2e_Mt_AR5",
                             subitem="Domestic wastewater N2O"))
             * _wpar("ww_ef_effluent_2006_high") / _wpar("ww_ef_effluent"), 0.5),
    # RETIRED at rc67: "waste S1 rerun engine arm" anchored the rerun engine's upper
    # arm beside the retired surrogate's 63.5. That comparison was against the arm on
    # the 2006 range (98.9); the sentence now says so in words and prints no current
    # number there. The arm itself stays anchored in the abstract, results and
    # limitations claims and in tab:rerunmc.
    ("waste S1 bounded fold span", "waste", "S1_uncertainty.tex",
     r"a \\num\{([\d]+)\}-fold span",
     lambda: _bounded_fold_span(), 1.0),
    # The upper end of that interval as a multiple of the default: the same closed form
    # on the same parameter row. It was the word "twenty-one" on the 2006 range.
    ("waste S1 bounded upper multiple", "waste", "S1_uncertainty.tex",
     r"to \\num\{([\d.]+)\} times it---a",
     lambda: (lambda row: (float(row["upper"]) / float(row["value"]))
              ** (1.0 - (2 * 0.025) ** 0.5))(
         next(r for r in _data_rows("waste_params.csv")
              if r["param"] == "ww_ef_effluent")), 0.0),
    ("waste abstract A1 band", "waste", "00_abstract.tex",
     r"uncertainty band: \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ by Approach-1",
     lambda: _mc("within_sector", "waste", "approach1_pct_95"), 0.0),
    ("waste abstract EDGAR ratio", "waste", "00_abstract.tex",
     r"sits at\s*\\SI\{([\d.]+)\}\{\\percent\} of EDGAR",
     lambda: 100.0 * _bench("EDGAR", "waste", year=2023), 0.0),
    ("waste abstract river wastewater", "waste", "00_abstract.tex",
     r"at \\num\{0.1\} it is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category",
                   "Sensitivity: wastewater on the river-discharge MCF (category total)",
                   "co2e_Mt_AR5"), 0.0),
    ("waste abstract variance share", "waste", "00_abstract.tex",
     r"carries\s*\\SI\{([\d.]+)\}\{\\percent\} of national inventory variance",
     lambda: _keycat("Domestic wastewater", "variance_share_pct_independent_approx"), 0.0),
    ("waste abstract level share", "waste", "00_abstract.tex",
     r"contributing \\SI\{([\d.]+)\}\{\\percent\} of\s*national emissions",
     lambda: _keycat("Domestic wastewater", "level_pct"), 0.0),
    # ---- waste: the year-matched EDGAR comparison ----
    ("waste EDGAR 2023 value", "waste", "05_validation.tex",
     r"at\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} for 2023",
     lambda: _bench("EDGAR", "waste", "benchmark_Mt_co2e", year=2023), 0.0),
    ("waste EDGAR ratio", "waste", "05_validation.tex",
     r"or\s*\\SI\{([\d.]+)\}\{\\percent\} of it",
     lambda: 100.0 * _bench("EDGAR", "waste", year=2023), 0.0),
    ("waste EDGAR 2024 context value", "waste", "05_validation.tex",
     r"2024 value, \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _bench("EDGAR", "waste", "benchmark_Mt_co2e", year=2024), 0.0),
    ("waste EDGAR pre-4D reading", "waste", "05_validation.tex",
     r"read\s*\\SI\{([\d.]+)\}\{\\percent\} of EDGAR",
     lambda: 100.0 * (_cell("waste_totals_%d.csv" % _waste_year(), "category", "Solid waste disposal",
                            "co2e_Mt_AR5")
                      + _cell("waste_totals_%d.csv" % _waste_year(), "category", "Open burning of waste",
                              "co2e_Mt_AR5"))
             / _bench("EDGAR", "waste", "benchmark_Mt_co2e", year=2023), 0.0),
    ("waste river-case sector", "waste", "05_validation.tex",
     r"the sector is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     _waste_river_sector_total, 0.001),
    # ---- waste: the HIES 2024-25 household-survey comparison ----
    ("waste HIES urban uncollected", "waste", "05_validation.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of urban households report no collection",
     lambda: _hies_route("urban", "uncollected"), 0.0),
    ("waste HIES urban assumption", "waste", "05_validation.tex",
     r"against\s*the \\SI\{([\d.]+)\}\{\\percent\} assumed",
     lambda: 100.0 * _wpar("uncollected_urban"), 0.0),
    ("waste HIES rural uncollected", "waste", "05_validation.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} of rural households against",
     lambda: _hies_route("rural", "uncollected"), 0.0),
    ("waste HIES rural assumption", "waste", "05_validation.tex",
     r"of rural households against\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _wpar("uncollected_rural"), 0.0),
    ("waste HIES rural open space", "waste", "05_validation.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of rural households report disposal to open space",
     lambda: _hies_route("rural", 6), 0.0),
    ("waste river-case EDGAR ratio", "waste", "05_validation.tex",
     r"lands at \\num\{([\d.]+)\} times EDGAR",
     lambda: _waste_river_sector_total()
             / _bench("EDGAR", "waste", "benchmark_Mt_co2e", year=2023), 0.0),
    # ---- waste: results prose and captions ----
    ("waste MC band results", "waste", "06_results.tex",
     r"printing \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ as this\s*module's symmetric summary",
     lambda: _mc("within_sector", "waste"), 0.0),
    ("waste wastewater share of sector", "waste", "06_results.tex",
     r"Domestic wastewater is \\SI\{([\d.]+)\}\{\\percent\} of it",
     lambda: 100.0 * _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                           "co2e_Mt_AR5")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("waste methane share", "waste", "06_results.tex",
     r"Methane is \\SI\{([\d.]+)\}\{\\percent\} of the sector",
     lambda: 100.0 * _sum_where("waste_by_stream_%d.csv" % _waste_year(), "co2e_Mt_AR5", gas="CH4")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("waste AR5-AR6 gap", "waste", "06_results.tex",
     r"AR5-to-AR6 difference of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5")
             - _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR6"), 0.0),
    ("waste streams caption wastewater CH4", "waste", "06_results.tex",
     r"wastewater methane alone, at\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("waste_by_stream_%d.csv" % _waste_year(), "co2e_Mt_AR5",
                        category="Domestic wastewater", gas="CH4"), 0.0),
    ("waste spin-up share", "waste", "06_results.tex",
     r"pre-2000 deposits contribute \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * (_cell("waste_totals_%d.csv" % _waste_year(), "category", "Solid waste disposal",
                            "co2e_Mt_AR5")
                      - _cell("waste_totals_%d.csv" % _waste_year(), "category",
                              "Sensitivity: disposal without spin-up", "co2e_Mt_AR5"))
             / _cell("waste_totals_%d.csv" % _waste_year(), "category", "Solid waste disposal",
                     "co2e_Mt_AR5"), 0.0),
    ("waste provincial Punjab", "waste", "06_results.tex",
     r"Punjab \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_provincial_%d.csv" % _waste_year(), "province", "Punjab", "co2e_Mt_AR5"), 0.0),
    ("waste provincial Sindh", "waste", "06_results.tex",
     r"Sindh \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_provincial_%d.csv" % _waste_year(), "province", "Sindh", "co2e_Mt_AR5"), 0.0),
    ("waste provincial KP", "waste", "06_results.tex",
     r"Khyber Pakhtunkhwa\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_provincial_%d.csv" % _waste_year(), "province", "Khyber Pakhtunkhwa",
                   "co2e_Mt_AR5"), 0.0),
    ("waste provincial Balochistan", "waste", "06_results.tex",
     r"Balochistan \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_provincial_%d.csv" % _waste_year(), "province", "Balochistan",
                   "co2e_Mt_AR5"), 0.0),
    ("waste provincial territories", "waste", "06_results.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} in the\s*territories",
     lambda: _cell("waste_provincial_%d.csv" % _waste_year(), "province", "Other", "co2e_Mt_AR5"), 0.0),
    # ---- waste: study area parameters (the partition's load-bearing inputs) ----
    ("waste urban generation rate", "waste", "03_study_area_and_data.tex",
     r"generation is \\SI\{([\d.]+)\}\{\\kilo\\gram\} per person per day urban",
     lambda: _wpar("gen_rate_urban"), 0.0),
    ("waste rural generation rate", "waste", "03_study_area_and_data.tex",
     r"and\s*\\SI\{([\d.]+)\}\{\\kilo\\gram\} rural",
     lambda: _wpar("gen_rate_rural"), 0.0),
    ("waste urban uncollected", "waste", "03_study_area_and_data.tex",
     r"uncollected fraction: \\SI\{([\d.]+)\}\{\\percent\} urban",
     lambda: 100.0 * _wpar("uncollected_urban"), 0.0),
    ("waste rural uncollected", "waste", "03_study_area_and_data.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} rural",
     lambda: 100.0 * _wpar("uncollected_rural"), 0.0),
    ("waste burned fraction", "waste", "03_study_area_and_data.tex",
     r"remainder, \\SI\{([\d.]+)\}\{\\percent\} is openly burned",
     lambda: 100.0 * _wpar("burned_fraction"), 0.0),
    # ---- waste: the partition, anchored on the fate ledger ----
    ("waste abstract generated", "waste", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*generated",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Generated", "Mt_wet"), 0.0),
    ("waste abstract collected share", "waste", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} collected to disposal",
     lambda: 100.0 * _cell("waste_ledger_%d.csv" % _waste_year(), "claimant",
                           "Collected to disposal sites", "share_of_generated"), 0.0),
    ("waste study generated", "waste", "03_study_area_and_data.tex",
     r"that is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of municipal solid waste",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Generated", "Mt_wet"), 0.0),
    ("waste study collected share", "waste", "03_study_area_and_data.tex",
     r"resolves to \\SI\{([\d.]+)\}\{\\percent\} of national generation",
     lambda: 100.0 * _cell("waste_ledger_%d.csv" % _waste_year(), "claimant",
                           "Collected to disposal sites", "share_of_generated"), 0.0),
    ("waste methods generated", "waste", "04_methods.tex",
     r"this gives \\SI\{([\d.]+)\}\{\\mega\\tonne\} generated",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Generated", "Mt_wet"), 0.0),
    ("waste methods collected", "waste", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} collected to\s*disposal",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Collected to disposal sites",
                   "Mt_wet"), 0.0),
    ("waste methods uncollected", "waste", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} uncollected",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Uncollected", "Mt_wet"), 0.0),
    ("waste methods burned", "waste", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} openly burned",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Openly burned", "Mt_wet"), 0.0),
    ("waste methods unresolved", "waste", "04_methods.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of uncollected waste that does not\s*burn",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant",
                   "UNRESOLVED - dumped to land and waterways, unburned", "Mt_wet"), 0.0),
    ("waste partition caption generated", "waste", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of municipal solid waste is generated",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Generated", "Mt_wet"), 0.0),
    ("waste partition caption collected", "waste", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} is collected and enters the decay model",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Collected to disposal sites",
                   "Mt_wet"), 0.0),
    ("waste partition caption uncollected", "waste", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} is uncollected",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Uncollected", "Mt_wet"), 0.0),
    ("waste partition caption burned", "waste", "06_results.tex",
     r"of which \\SI\{([\d.]+)\}\{\\mega\\tonne\} burns",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Openly burned", "Mt_wet"), 0.0),
    ("waste air burned tonnage", "waste", "06b_air_pollutants.tex",
     r"the same\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of burned waste",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant", "Openly burned", "Mt_wet"), 0.0),
    ("waste limitations collected share", "waste", "08_limitations.tex",
     r"but \\SI\{([\d.]+)\}\{\\percent\} is an assumption",
     lambda: 100.0 * _cell("waste_ledger_%d.csv" % _waste_year(), "claimant",
                           "Collected to disposal sites", "share_of_generated"), 0.0),
    ("waste limitations unresolved", "waste", "08_limitations.tex",
     r"unresolved row:\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} of uncollected, unburned",
     lambda: _cell("waste_ledger_%d.csv" % _waste_year(), "claimant",
                   "UNRESOLVED - dumped to land and waterways, unburned", "Mt_wet"), 0.0),
    # ---- waste: discussion ----
    ("waste keycat level discussion", "waste", "07_discussion.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of Pakistan's national emissions",
     lambda: _keycat("Domestic wastewater", "level_pct"), 0.0),
    ("waste keycat variance discussion", "waste", "07_discussion.tex",
     r"emissions and \\SI\{([\d.]+)\}\{\\percent\} of national\s*inventory variance",
     lambda: _keycat("Domestic wastewater", "variance_share_pct_independent_approx"), 0.0),
    ("waste burning level discussion", "waste", "07_discussion.tex",
     r"At \\SI\{([\d.]+)\}\{\\percent\} of\s*national \\COe",
     lambda: _keycat("Open burning of waste", "level_pct"), 0.0),
    ("waste burning PM share discussion", "waste", "07_discussion.tex",
     r"roughly \\SI\{([\d.]+)\}\{\\percent\} of national primary \\PM",
     lambda: 100.0 * _sum_where("waste_air_pollutants_%d.csv" % _waste_year(), "emissions_kt",
                                pollutant="PM2.5") / _pm25_national_total(), 0.0),
    # ---- waste: conclusion ----
    ("waste conclusion total", "waste", "09_conclusion.tex",
     r"emitted \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} in FY2023--24",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("waste conclusion wastewater", "waste", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} from domestic wastewater",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5"), 0.0),
    ("waste conclusion disposal", "waste", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} from solid-waste\s*disposal",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Solid waste disposal",
                   "co2e_Mt_AR5"), 0.0),
    ("waste conclusion burning", "waste", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} from open burning",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Open burning of waste",
                   "co2e_Mt_AR5"), 0.0),
    ("waste conclusion national share", "waste", "09_conclusion.tex",
     r"The sector is \\SI\{([\d.]+)\}\{\\percent\} of a",
     lambda: _sector("waste", "share_pct"), 0.0),
    ("waste conclusion lever from", "waste", "09_conclusion.tex",
     r"moves this sector\s*from \\SI\{([\d.]+)\}\{\\mega\\tonne\} to",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("waste conclusion lever to", "waste", "09_conclusion.tex",
     r"from \\SI\{[\d.]+\}\{\\mega\\tonne\} to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     _waste_river_sector_total, 0.001),
    ("waste keycat level conclusion", "waste", "09_conclusion.tex",
     r"is \\SI\{([\d.]+)\}\{\\percent\} of national emissions",
     lambda: _keycat("Domestic wastewater", "level_pct"), 0.0),
    ("waste keycat variance conclusion", "waste", "09_conclusion.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} of national inventory\s*variance",
     lambda: _keycat("Domestic wastewater", "variance_share_pct_independent_approx"), 0.0),
    # ---- waste: S1 prose (the table body is covered by the tab:mc registration) ----
    ("waste S1 A2 band", "waste", "S1_uncertainty.tex",
     r"so its \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ symmetric summary",
     lambda: _mc("within_sector", "waste"), 0.0),
    ("waste S1 national down arm", "waste", "S1_uncertainty.tex",
     r"really\s*\$-\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _mc("within_sector", "waste", "rel_down_pct_95"), 0.05),
    ("waste S1 national up arm", "waste", "S1_uncertainty.tex",
     r"/\+\\SI\{([\d.]+)\}\{\\percent\}\$ about the median\) stands apart",
     lambda: _mc("within_sector", "waste", "rel_up_pct_95"), 0.05),
    ("waste S1 wastewater national up arm", "waste", "S1_uncertainty.tex",
     r"\$\+\\SI\{([\d.]+)\}\{\\percent\}\$ upper arm on the wastewater",
     lambda: _mc("within_sector", "Domestic wastewater", "rel_up_pct_95"), 0.05),
    ("waste S1 disposal MC band", "waste", "S1_uncertainty.tex",
     r"analytically and \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$ in the injected\s*simulation",
     lambda: _mc("within_sector", "Solid waste disposal"), 0.0),
    ("waste S1 disposal median", "waste", "S1_uncertainty.tex",
     r"simulated median of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _mc("within_sector", "Solid waste disposal", "P50_Mt"), 0.0),
    ("waste S1 disposal mean", "waste", "S1_uncertainty.tex",
     r"below its mean of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _mc("within_sector", "Solid waste disposal", "mean_Mt"), 0.0),
    ("waste S1 disposal P2.5", "waste", "S1_uncertainty.tex",
     r"2\.5th percentile at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _mc("within_sector", "Solid waste disposal", "P2.5_Mt"), 0.0),
    ("waste S1 disposal P97.5", "waste", "S1_uncertainty.tex",
     r"97\.5th at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _mc("within_sector", "Solid waste disposal", "P97.5_Mt"), 0.0),
    ("waste S1 correlated band", "waste", "S1_uncertainty.tex",
     r"independent against \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$\s*correlated",
     lambda: _mc("cross_sector", "waste"), 0.0),
    ("waste S1 fossil CO2 share", "waste", "S1_uncertainty.tex",
     r"it is \\SI\{([\d.]+)\}\{\\percent\} of the sector",
     lambda: 100.0 * _cell("waste_by_stream_%d.csv" % _waste_year(), "subitem",
                           "Open waste burning CO2 (fossil)", "co2e_Mt_AR5")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("waste S1 variance wastewater", "waste", "S1_uncertainty.tex",
     r"domestic wastewater\s*\\SI\{([\d.]+)\}\{\\percent\} of \\emph\{national\}",
     lambda: _keycat("Domestic wastewater", "variance_share_pct_independent_approx"), 0.0),
    ("waste S1 variance disposal", "waste", "S1_uncertainty.tex",
     r"solid-waste disposal\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _keycat("Solid waste disposal", "variance_share_pct_independent_approx"), 0.0),
    ("waste S1 variance burning", "waste", "S1_uncertainty.tex",
     r"open burning \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _keycat("Open burning of waste", "variance_share_pct_independent_approx"), 0.0),
    ("waste S1 MCF lever", "waste", "S1_uncertainty.tex",
     r"a factor of \\num\{([\d.]+)\} on\s*the CH",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category",
                     "Sensitivity: wastewater on the river-discharge MCF (category total)",
                     "co2e_Mt_AR5"), 0.0),
    ("waste S1 grouped band", "waste", "S1_uncertainty.tex",
     r"quadrature---gives \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _cell("waste_uncertainty_%d.csv" % _waste_year(), "category", "SECTOR",
                   "approach1_pct_grouped"), 0.0),
    ("waste S1 grouped-vs-independent", "waste", "S1_uncertainty.tex",
     r"against the independent\s*\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _cell("waste_uncertainty_%d.csv" % _waste_year(), "category", "SECTOR",
                   "approach1_pct_independent"), 0.0),
    ("waste S1 effective mixture MCF", "waste", "S1_uncertainty.tex",
     r"effective correction factor of \\num\{([\d.]+)\}",
     lambda: ((1.0 - _wpar("ww_treated_share")) / 2.0
              * (_wpar("ww_mcf_sewer") + _wpar("ww_mcf_sewer_river"))
              + _wpar("ww_treated_share") * _wpar("ww_mcf_treated")), 0.0),
    ("waste S1 treated sliver", "waste", "S1_uncertainty.tex",
     r"treated sliver of \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _wpar("ww_treated_share"), 0.0),
    ("waste S1 equal-mix total", "waste", "S1_uncertainty.tex",
     r"sector of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(), "deterministic",
                          structural_scenario="sewer_equal_mix"), 0.0),
    ("waste S1 HIES scenario total", "waste", "S1_uncertainty.tex",
     r"\\emph\{lowers\} the sector to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(), "deterministic",
                          structural_scenario="hies_route_shares"), 0.0),
    # ---- waste: air-pollutant comparatives (06b) ----
    ("waste air PM headline", "waste", "06b_air_pollutants.tex",
     r"At \\SI\{([\d.]+)\}\{\\kilo\\tonne\} of primary \\PM",
     lambda: _sum_where("waste_air_pollutants_%d.csv" % _waste_year(), "emissions_kt",
                        pollutant="PM2.5"), 0.0),
    ("waste air residential solid fuel", "waste", "06b_air_pollutants.tex",
     r"residential solid fuel at\s*\\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: sum(_sum_where("residential_air_pollutants_2024.csv", "emissions_kt",
                            subitem=s)
                 for s in ("Dung cake PM2.5", "Firewood PM2.5", "Crop residues PM2.5",
                           "Charcoal PM2.5", "Coal PM2.5")), 0.0),
    ("waste air crop burning", "waste", "06b_air_pollutants.tex",
     r"crop-residue burning at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _sum_where("air_pollutants_2024.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.0),
    ("waste air road transport", "waste", "06b_air_pollutants.tex",
     r"road\s*transport at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _sum_where("transport_air_pollutants_%d.csv" % _transport_year(), "emissions_kt",
                        pollutant="PM2.5"), 0.0),
    ("waste air burning ghg share", "waste", "06b_air_pollutants.tex",
     r"burning is \\SI\{([\d.]+)\}\{\\percent\} of national \\COe",
     lambda: _keycat("Open burning of waste", "level_pct"), 0.0),
    ("waste air national PM share", "waste", "06b_air_pollutants.tex",
     r"roughly \\SI\{([\d.]+)\}\{\\percent\} of national\s*primary \\PM",
     lambda: 100.0 * _sum_where("waste_air_pollutants_%d.csv" % _waste_year(), "emissions_kt",
                                pollutant="PM2.5") / _pm25_national_total(), 0.0),
    ("waste air road level", "waste", "06b_air_pollutants.tex",
     r"the other way, at \\SI\{([\d.]+)\}\{\\percent\} of emissions",
     lambda: _keycat("Road transport", "level_pct"), 0.05),
    ("waste air BC", "waste", "06b_air_pollutants.tex",
     r"Black carbon at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("waste_air_pollutants_%d.csv" % _waste_year(), "pollutant", "BC",
                   "emissions_kt"), 0.0),
    ("waste air HCl", "waste", "06b_air_pollutants.tex",
     r"Hydrogen chloride at \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("waste_air_pollutants_%d.csv" % _waste_year(), "pollutant", "HCl",
                   "emissions_kt"), 0.0),
    # ---- waste: wastewater nitrous oxide on the 2019 Refinement (rc67) ----
    # The methods paragraph states the chain; every factor it prints is the parameter
    # row the engine reads, and both methods' gas is the product's own.
    ("waste methods protein consumed", "waste", "04_methods.tex",
     r"protein consumed \(a factor of \\num\{([\d.]+)\}\)",
     lambda: _wpar("ww_f_pc"), 0.0),
    ("waste methods nitrogen in protein", "waste", "04_methods.tex",
     r"and its nitrogen \(\\num\{([\d.]+)\}\)",
     lambda: _wpar("ww_f_npr"), 0.0),
    ("waste methods household products", "waste", "04_methods.tex",
     r"with factors of \\num\{([\d.]+)\} for\s*household products",
     lambda: _wpar("ww_n_hh"), 0.0),
    ("waste methods non-consumed protein", "waste", "04_methods.tex",
     r"\\num\{([\d.]+)\} for non-consumed protein",
     lambda: _wpar("ww_f_non_con"), 0.0),
    ("waste methods industrial-commercial, sewered", "waste", "04_methods.tex",
     r"co-discharge, \\num\{([\d.]+)\} on the sewered population only",
     lambda: _wpar("ww_f_ind_com"), 0.0),
    ("waste methods septic removal", "waste", "04_methods.tex",
     r"discharge---\\num\{([\d.]+)\} in septic\s*tanks",
     lambda: _wpar("ww_nrem_septic"), 0.0),
    ("waste methods latrine removal", "waste", "04_methods.tex",
     r"\\num\{([\d.]+)\} in latrines",
     lambda: _wpar("ww_nrem_latrine"), 0.0),
    ("waste methods secondary removal", "waste", "04_methods.tex",
     r"and \\num\{([\d.]+)\} in the treated share",
     lambda: _wpar("ww_nrem_secondary"), 0.0),
    ("waste methods treated share", "waste", "04_methods.tex",
     r"declared at \\SI\{([\d.]+)\}\{\\percent\} and not measured",
     lambda: 100.0 * _wpar("ww_treated_share"), 0.0),
    ("waste methods plant factor", "waste", "04_methods.tex",
     r"emits there at \\num\{([\d.]+)\}",
     lambda: _wpar("ww_ef_plant_aerobic"), 0.0),
    ("waste methods effluent factor", "waste", "04_methods.tex",
     r"effluent factor of \\num\{([\d.]+)\}",
     lambda: _wpar("ww_ef_effluent"), 0.0),
    ("waste methods N2O, 2019 method", "waste", "04_methods.tex",
     r"The result is\s*\\SI\{([\d.]+)\}\{\\giga\\gram\} of \\NtwoO",
     lambda: _first_where("waste_by_stream_%d.csv" % _waste_year(), "emissions_Gg",
                          subitem="Domestic wastewater N2O"), 0.0),
    ("waste methods N2O, 2006 method", "waste", "04_methods.tex",
     r"alternative and gives \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "deterministic",
                          scope="wastewater_n2o", period_id="FY2023-24",
                          method="ipcc2006"), 0.0),
    # The sewer lever where it is restated, each in place and not as a repeat.
    ("waste abstract central wastewater", "waste", "00_abstract.tex",
     r"At \\num\{0.5\} domestic wastewater is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5"), 0.0),
    ("waste related-work EDGAR ratio", "waste", "02_related_work.tex",
     r"sits at \\SI\{([\d.]+)\}\{\\percent\} of EDGAR's year-matched",
     lambda: 100.0 * _bench("EDGAR", "waste", year=2023), 0.0),
    ("waste validation central wastewater", "waste", "05_validation.tex",
     r"the wastewater category is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5"), 0.0),
    ("waste validation river wastewater", "waste", "05_validation.tex",
     r"river-discharge \\num\{0.1\} it is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category",
                   "Sensitivity: wastewater on the river-discharge MCF (category total)",
                   "co2e_Mt_AR5"), 0.0),
    ("waste results AR6", "waste", "06_results.tex",
     r"or\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} on AR6",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL",
                   "co2e_Mt_AR6"), 0.0),
    ("waste discussion MCF lever", "waste", "07_discussion.tex",
     r"a factor of \\num\{([\d.]+)\} on the sector's largest category",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category",
                     "Sensitivity: wastewater on the river-discharge MCF (category total)",
                     "co2e_Mt_AR5"), 0.0),
    ("waste discussion central wastewater", "waste", "07_discussion.tex",
     r"largest category:\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} against",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5"), 0.0),
    ("waste discussion river wastewater", "waste", "07_discussion.tex",
     r"against \\SI\{([\d.]+)\}\{\\mega\\tonne\}, or",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category",
                   "Sensitivity: wastewater on the river-discharge MCF (category total)",
                   "co2e_Mt_AR5"), 0.0),
    ("waste limitations MCF lever", "waste", "08_limitations.tex",
     r"A factor of\s*\\num\{([\d.]+)\} on two-thirds",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category",
                     "Sensitivity: wastewater on the river-discharge MCF (category total)",
                     "co2e_Mt_AR5"), 0.0),
    ("waste conclusion methane share", "waste", "09_conclusion.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} methane",
     lambda: 100.0 * _sum_where("waste_by_stream_%d.csv" % _waste_year(), "co2e_Mt_AR5",
                                gas="CH4")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL",
                     "co2e_Mt_AR5"), 0.0),
    ("waste appendix reported category", "waste", "10_appendix.tex",
     r"comparing the reported\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5"), 0.0),
    ("waste appendix real lever", "waste", "10_appendix.tex",
     r"where the real one is \\num\{([\d.]+)\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "Domestic wastewater",
                   "co2e_Mt_AR5")
             / _cell("waste_totals_%d.csv" % _waste_year(), "category",
                     "Sensitivity: wastewater on the river-discharge MCF (category total)",
                     "co2e_Mt_AR5"), 0.0),
    # S1: the method change as a revision, the driver statement from the released
    # ensemble (the retired surrogate ranking carried this before), the declared
    # assumptions' scenarios and the two methods on the same draws.
    ("waste S1 N2O before the method change", "waste", "S1_uncertainty.tex",
     r"fell from \\SI\{([\d.]+)\}\{\} to \\SI\{[\d.]+\}\{\\giga\\gram\}",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "deterministic",
                          scope="wastewater_n2o", period_id="FY2023-24",
                          method="ipcc2006"), 0.0),
    ("waste S1 N2O after the method change", "waste", "S1_uncertainty.tex",
     r"fell from \\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "deterministic",
                          scope="wastewater_n2o", period_id="FY2023-24",
                          method="ipcc2019"), 0.0),
    ("waste S1 sector before the method change", "waste", "S1_uncertainty.tex",
     r"the sector from\s*\\SI\{([\d.]+)\}\{\} to \\SI\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                          "deterministic", structural_scenario="n2o_method_ipcc2006"), 0.0),
    ("waste S1 sector after the method change", "waste", "S1_uncertainty.tex",
     r"the sector from\s*\\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL",
                   "co2e_Mt_AR5"), 0.0),
    ("waste S1 effluent factor variance share", "waste", "S1_uncertainty.tex",
     r"it accounts for \\SI\{([\d.]+)\}\{\\percent\} of national variance",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="parameter", sector="waste"), 0.0),
    ("waste S1 effluent factor upper-tail share", "waste", "S1_uncertainty.tex",
     r"national variance and \\SI\{([\d.]+)\}\{\\percent\} of the\s*excess in the upper tail",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv",
                                  "upper_tail_excess_share",
                                  grain="parameter", sector="waste"), 0.0),
    ("waste S1 wastewater variance share, ensemble", "waste", "S1_uncertainty.tex",
     r"as a whole accounts for\s*\\SI\{([\d.]+)\}\{\\percent\} and",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv", "variance_share",
                                  grain="category", name="Domestic wastewater"), 0.0),
    ("waste S1 wastewater upper-tail share, ensemble", "waste", "S1_uncertainty.tex",
     r"as a whole accounts for\s*\\SI\{[\d.]+\}\{\\percent\} and \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _first_where("pakemis_uncertainty_drivers.csv",
                                  "upper_tail_excess_share",
                                  grain="category", name="Domestic wastewater"), 0.0),
    ("waste S1 effluent ceiling, table label", "waste", "S1_uncertainty.tex",
     r"Effluent EF at its ceiling \(\\num\{([\d.]+)\}\)",
     lambda: float(_first_where_data("waste_params.csv", "upper",
                                     param="ww_ef_effluent")), 0.0),
    ("waste S1 2006 method scenario", "waste", "S1_uncertainty.tex",
     r"gives a sector of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                          "deterministic", structural_scenario="n2o_method_ipcc2006"), 0.0),
    ("waste S1 decentralised effluent to soil", "waste", "S1_uncertainty.tex",
     r"effluent---gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                          "deterministic",
                          structural_scenario="decentralised_effluent_to_soil"), 0.0),
    ("waste S1 nutrient-impacted factor", "waste", "S1_uncertainty.tex",
     r"receiving waters \(\\num\{([\d.]+)\}\)",
     lambda: _wpar("ww_ef_effluent_nutrient"), 0.0),
    ("waste S1 nutrient-impacted scenario", "waste", "S1_uncertainty.tex",
     r"on every discharge gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                          "deterministic",
                          structural_scenario="effluent_nutrient_impacted"), 0.0),
    ("waste S1 septic dispersal field scenario", "waste", "S1_uncertainty.tex",
     r"land dispersal field give\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                          "deterministic",
                          structural_scenario="septic_with_dispersal_field"), 0.0),
    ("waste S1 treated share high scenario", "waste", "S1_uncertainty.tex",
     r"sewered flow gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_uncertainty_scenarios_%d.csv" % _waste_year(),
                          "deterministic", structural_scenario="treated_share_high"), 0.0),
    ("waste S1 category interval low, 2019 method", "waste", "S1_uncertainty.tex",
     r"interval is \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} under the 2019 method",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p2_5",
                          scope="wastewater_category", method="ipcc2019"), 0.0),
    ("waste S1 category interval high, 2019 method", "waste", "S1_uncertainty.tex",
     r"interval is \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} under the 2019 method",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p97_5",
                          scope="wastewater_category", method="ipcc2019"), 0.0),
    ("waste S1 category interval low, 2006 method", "waste", "S1_uncertainty.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} under the 2006 method",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p2_5",
                          scope="wastewater_category", method="ipcc2006"), 0.0),
    ("waste S1 category interval high, 2006 method", "waste", "S1_uncertainty.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} under the 2006 method",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p97_5",
                          scope="wastewater_category", method="ipcc2006"), 0.0),
    ("waste S1 national interval low, 2019 method", "waste", "S1_uncertainty.tex",
     r"national interval is \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} against",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p2_5",
                          scope="national_total", method="ipcc2019"), 0.0),
    ("waste S1 national interval high, 2019 method", "waste", "S1_uncertainty.tex",
     r"national interval is \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} against",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p97_5",
                          scope="national_total", method="ipcc2019"), 0.0),
    ("waste S1 national interval low, 2006 method", "waste", "S1_uncertainty.tex",
     r"against\s*\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}\.",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p2_5",
                          scope="national_total", method="ipcc2006"), 0.0),
    ("waste S1 national interval high, 2006 method", "waste", "S1_uncertainty.tex",
     r"against\s*\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}\.",
     lambda: _first_where("pakemis_wastewater_method_comparison.csv", "p97_5",
                          scope="national_total", method="ipcc2006"), 0.0),
    # ---- aviation fuel bridge ----
    ("aviation movement CO2", "aviation", "06_results.tex",
     r"Aggregate movement \(M0\) & 94,576 & ([\d.]+)",
     lambda: _cell("aviation_reconciliation_fy2023_24.csv", "scenario",
                   "flight_fuel_weighted", "bottom_up_domestic_co2_Gg"), 0.1),
    ("aviation bridged CO2", "aviation", "06_results.tex",
     r"Calibrated fuel bridge & 92,409 & ([\d.]+)",
     lambda: _cell("aviation_reconciliation_fy2023_24.csv", "scenario",
                   "flight_fuel_weighted", "domestic_co2_Gg"), 0.1),
    ("aviation literal scenario", "aviation", "06_results.tex",
     r"Literal customer labels & 359,932 & ([\d.]+)",
     lambda: _cell("aviation_reconciliation_fy2023_24.csv", "scenario",
                   "literal_customer", "domestic_co2_Gg"), 0.1),
    ("aviation completed M2 CO2", "aviation", "06_results.tex",
     r"Completed route--aircraft model \(M2\) & 78,139 & ([\d.]+)",
     lambda: _first_where("aviation_common_support_ladder.csv", "fuel_t",
                          experiment="coverage_completion", step="completed_total") * 3.16 / 1000,
     0.1),
    ("aviation fuel constrained total", "aviation", "06_results.tex",
     r"gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe",
     lambda: sum(float(r["co2e_Mt_AR5"])
                 for r in _rows("aviation_fuel_constrained_by_stream_fy2023_24.csv")), 0.001),
    ("aviation full international bunker", "aviation", "06_results.tex",
     r"or \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo",
     lambda: _cell("aviation_reconciliation_fy2023_24.csv", "scenario",
                   "flight_fuel_weighted", "international_co2_Gg") / 1000.0, 0.001),
    ("aviation explicit residual", "aviation", "06_results.tex",
     r"explicit \\SI\{([\d.]+)\}\{\\tonne\} residual",
     lambda: _cell("aviation_reconciliation_fy2023_24.csv", "scenario",
                   "flight_fuel_weighted", "residual_fuel_t"), 0.0),
    ("aviation M2 probabilistic mean", "aviation", "06_results.tex",
     r"Monte Carlo gives mean domestic emissions of\s+([\d.]+) Mt \\COtwo",
     lambda: _first_where("aviation_m2_uncertainty_intervals.csv", "mean_Mt",
                          route_graph="central_ipf",
                          completion_method="current_icao_route_m1_endpoint_m0",
                          interval_type="primary", metric="CO2"), 0.001),
    ("aviation M2 probabilistic lower", "aviation", "06_results.tex",
     r"95\\% interval ([\d.]+)--[\d.]+ Mt",
     lambda: _first_where("aviation_m2_uncertainty_intervals.csv", "P2.5_Mt",
                          route_graph="central_ipf",
                          completion_method="current_icao_route_m1_endpoint_m0",
                          interval_type="primary", metric="CO2"), 0.001),
    ("aviation M2 probabilistic upper", "aviation", "06_results.tex",
     r"95\\% interval [\d.]+--([\d.]+) Mt",
     lambda: _first_where("aviation_m2_uncertainty_intervals.csv", "P97.5_Mt",
                          route_graph="central_ipf",
                          completion_method="current_icao_route_m1_endpoint_m0",
                          interval_type="primary", metric="CO2"), 0.001),
    ("aviation M2 aircraft contribution", "aviation", "06_results.tex",
     r"Aircraft assignment reduces simulated\s+variance by\s+([\d.]+)\\%",
     lambda: _first_where("aviation_m2_uncertainty_contributions.csv",
                          "variance_reduction_pct", uncertainty_group="aircraft"), 0.05),
    # ---- railways ----
    ("railways total", "railways", "06_results.tex",
     r"\\textbf\{Module total\} & & & \\textbf\{([\d.]+)\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Module total (both categories)", "co2e_Mt_AR5"), 0.0),
    ("railways traction row", "railways", "06_results.tex",
     r"1A3c locomotive traction & & & ([\d.]+) &",
     lambda: _cell("railways_totals_2024.csv", "category", "Railways",
                   "co2e_Mt_AR5"), 0.0),
    ("railways non-traction row", "railways", "06_results.tex",
     r"Non-traction \(1A2/1A4c\) & & & ([\d.]+) &",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Railway non-traction energy (1A2/1A4c unresolved)",
                   "co2e_Mt_AR5"), 0.0),
    ("railways diesel CO2 Gg", "railways", "06_results.tex",
     r"Diesel \(traction\) & \\COtwo\{\}  & ([\d.]+) ",
     lambda: _cell("railways_by_stream_2024.csv", "subitem", "Diesel CO2",
                   "emissions_Gg"), 0.0),
    ("railways diesel CO2 uncertainty", "railways", "06_results.tex",
     r"Diesel \(traction\) & \\COtwo\{\}  & [\d.]+ & [\d.]+ &   ([\d.]+)",
     lambda: _cell("railways_by_stream_2024.csv", "subitem", "Diesel CO2",
                   "uncert_pct"), 0.0),
    ("railways diesel N2O", "railways", "06_results.tex",
     r"& \\NtwoO\{\}  &   [\d.]+ & ([\d.]+) ",
     lambda: _cell("railways_by_stream_2024.csv", "subitem", "Diesel N2O",
                   "co2e_Mt_AR5"), 0.0),
    # The counterfactual the sector publishes so the factor-table choice is visible in the
    # output rather than asserted in prose. If the rail table were ever swapped for the road
    # one, the reported total would move to this number and this claim would fail.
    ("railways road-factor diagnostic", "railways", "06_results.tex",
     r"Road table \(3\.2\.2\) substituted   & ([\d.]+)",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Diagnostic: N2O on the road factor", "co2e_Mt_AR5"), 0.0),
    ("railways metered diesel", "railways", "04_methods.tex",
     r"metered diesel is \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Traction diesel, for cross-source comparison", "co2e_Mt_AR5"), 0.0),
    ("railways diesel TJ", "railways", "03_study_area_and_data.tex",
     r"Diesel      & ([\d.]+) & 99",
     lambda: _cell("railways_fuel_2024.csv", "stream", "Diesel", "TJ"), 0.0),
    ("railways diesel share", "railways", "03_study_area_and_data.tex",
     r"Diesel      & [\d.]+ & ([\d.]+)",
     lambda: _cell("railways_fuel_2024.csv", "stream", "Diesel", "share_pct"), 0.0),
    ("railways Sindh", "railways", "06_results.tex",
     r"\\mega\\tonne\}, Sindh \\SI\{([\d.]+)\}",
     lambda: _cell("railways_provincial_2024.csv", "province", "Sindh", "co2e_Mt_AR5"), 0.0),
    ("railways network audit km", "railways", "04_methods.tex",
     r"network---\\num\{(\d+)\} active\s+line-kilometres",
     lambda: _cell("railways_network_audit_2024.csv", "item", "active_total", "km"), 1.0),
    # The primary benchmark is matched-year: the BUR-1 inventory year FY2017-18 recomputed
    # by the identical method. The reference-year figure is a different year, not a
    # different method, and the paper must quote the engine's number for the matched year.
    ("railways matched-year estimate", "railways", "05_validation.tex",
     r"applied to the \\num\{156396\} thousand\s+litres the operator reports for "
     r"FY2017--18, gives \\SI\{([\d.]+)\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.0005),
    ("railways abstract reference year", "railways", "00_abstract.tex",
     r"reference year, \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Module total (both categories)", "co2e_Mt_AR5"),
     0.0005),
    # The rc12 canonical statement: everywhere the module total is quoted, the
    # 0.38939/0.00498 split is quoted beside it, and every copy anchors to the
    # totals ledger's two category rows.
    ("railways abstract traction split", "railways", "00_abstract.tex",
     r"of which\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} is strict locomotive traction",
     lambda: _cell("railways_totals_2024.csv", "category", "Railways",
                   "co2e_Mt_AR5"), 0.0),
    ("railways abstract non-traction split", "railways", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} is the measured non-traction claimant",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Railway non-traction energy (1A2/1A4c unresolved)",
                   "co2e_Mt_AR5"), 0.0),
    ("railways intro traction share", "railways", "01_introduction.tex",
     r"module total; \\SI\{([\d.]+)\}\{\\mega\\tonne\} of it strict 1A3c",
     lambda: _cell("railways_totals_2024.csv", "category", "Railways",
                   "co2e_Mt_AR5"), 0.0),
    ("railways validation strict 1A3c", "railways", "05_validation.tex",
     r"\(\\SI\{([\d.]+)\}\{\\mega\\tonne\} strict 1A3c\)",
     lambda: _cell("railways_totals_2024.csv", "category", "Railways",
                   "co2e_Mt_AR5"), 0.0),
    ("railways conclusion traction split", "railways", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of it strict locomotive traction",
     lambda: _cell("railways_totals_2024.csv", "category", "Railways",
                   "co2e_Mt_AR5"), 0.0),
    ("railways conclusion non-traction split", "railways", "09_conclusion.tex",
     r"1A3c, \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s*the measured non-traction",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Railway non-traction energy (1A2/1A4c unresolved)",
                   "co2e_Mt_AR5"), 0.0),
    ("transport EDGAR non-traction exclusion", "transport", "05_validation.tex",
     r"the non-traction\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} is excluded",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Railway non-traction energy (1A2/1A4c unresolved)",
                   "co2e_Mt_AR5"), 0.0),
    ("national table4 rail traction", "national", "06_results.tex",
     r"strict locomotive traction \(1A3c,\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _cell("railways_totals_2024.csv", "category", "Railways",
                   "co2e_Mt_AR5"), 0.0),
    ("national table4 rail non-traction", "national", "06_results.tex",
     r"\(1A2/1A4c unresolved, \\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Railway non-traction energy (1A2/1A4c unresolved)",
                   "co2e_Mt_AR5"), 0.0),
    # The waste landfill-seed acknowledgement (rc12, resolving the holds-nothing
    # contradiction) and the published seeds.
    # The release-assignment product (rc13): the unassigned share and district
    # count, anchored to the assignment product's own rows.
    ("waste release unassigned share", "waste", "06_results.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} of the\s*disposal category stays unassigned",
     lambda: 100.0 * sum(float(r["unassigned_co2e_Mt"]) for r in
                         _csv_rows("waste_release_assignment_2024.csv"))
             / sum(float(r["origin_co2e_Mt"]) for r in
                   _csv_rows("waste_release_assignment_2024.csv")), 0.5),
    ("waste release unassigned districts", "waste", "06_results.tex",
     r"unassigned across \\num\{(\d+)\} districts",
     lambda: float(sum(1 for r in _csv_rows("waste_release_assignment_2024.csv")
                       if r["assignment_status"] == "UNASSIGNED")), 0.0),
    # The period-matched fire layer (rc13, nine-year record since Wave 3): the
    # fetched total in the data section is the committed extraction's own row
    # count, so a re-fetch that changes the layer breaks the prose.
    ("agriculture fire detections", "agriculture", "03_study_area_and_data.tex",
     r"\\num\{(\d+)\} unique\s+detections",
     lambda: float(len(_data_rows(os.path.join("gis", "manual", "firms_fire.csv")))),
     0.0),
    # The in-grid count beside the fetched count (rc14): the two were published
    # conflated until the ninth review; both now carry labels and both are pinned.
    # Since the Wave-3 proxy period-filter the in-grid count is the reporting
    # period's own, and the gis report's parenthetical says so.
    ("agriculture fire in-grid detections", "agriculture", "03_study_area_and_data.tex",
     r"\\num\{(\d+)\} in-grid detections inside\s+FY2023--24",
     lambda: float(re.search(r"\((\d+) in-grid FY2023-24 detections",
                             open(os.path.join(OUT, "gis", "gis_report.md"),
                                  encoding="utf-8").read()).group(1)), 0.0),
    # The attribution ladder's rungs (Wave 3): each count the data section prints
    # is the burning crosscheck's own published row, so the ladder cannot move
    # without breaking the prose that narrates it.
    # The conclusion's flat-share verdict rides the shipped monthly layer's own
    # evidence declaration (same source as claims-registry
    # agriculture_monthly_flat_share, integer-rounded as printed).
    ("agriculture conclusion flat share", "agriculture", "09_conclusion.tex",
     r"declaration---\\SI\{(\d+)\}\{\\percent\} of the sector's emissions ride a",
     lambda: float(round(next(
         float(r["share_of_scope_pct"]) for r in _csv_rows("temporal_profile.csv")
         if r.get("scope") == "agriculture" and r.get("temporal_method") == "T4"))),
     0.0),
    # The built-form bracket (rc13): the limitations paragraph's rival count is
    # the number of residential proof rows the ADM2 bracket product actually
    # carries, so a member added or dropped there breaks the prose.
    ("residential built-form rivals", "residential", "08_limitations.tex",
     r"prices that choice against\s*\\num\{(\d+)\} admissible rivals",
     lambda: float(sum(1 for r in _csv_rows("pakemis_spatial_brackets_adm2.csv")
                       if r["module"] == "residential"
                       and r["status"] == "structurally_invariant")), 0.0),
    ("waste landfill polygon count", "waste", "06_results.tex",
     r"\\num\{(\d+)\} OpenStreetMap",
     lambda: float(len(_data_rows(os.path.join("gis", "landfills", "pak_landfill_assets.csv")))), 0.0),
    ("waste landfill named count", "waste", "06_results.tex",
     r"\\num\{(\d+)\} of them named",
     lambda: float(sum(1 for r in
                       _data_rows(os.path.join("gis", "landfills", "pak_landfill_assets.csv"))
                       if r["name"].strip())), 0.0),
    ("waste scenario seed", "waste", "S1_uncertainty.tex",
     r"\\num\{10000\} draws on seed\s*\\num\{(\d+)\}",
     lambda: _first_where("waste_uncertainty_scenarios_2024.csv", "seed",
                          structural_scenario="reference"), 0.0),
    ("railways abstract NOx", "railways", "00_abstract.tex",
     r"Tier~1:\s+\\SI\{([\d.]+)\}\{\\kilo\\tonne\} NO",
     lambda: _air_kt("NOx"), 0.005),
    ("railways abstract PM2.5", "railways", "00_abstract.tex",
     r"NO\\textsubscript\{x\}, \\SI\{([\d.]+)\}\{\\kilo\\tonne\}\s+PM",
     lambda: _air_kt("PM2.5"), 0.0005),
    ("railways abstract network km", "railways", "00_abstract.tex",
     r"over\s+\\num\{(\d+)\} audited line-kilometres",
     lambda: _cell("railways_network_audit_2024.csv", "item", "active_total", "km"), 1.0),
    ("railways abstract matched year", "railways", "00_abstract.tex",
     r"times the \\SI\{([\d.]+)\}\{\\mega\\tonne\} the identical method",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.0005),
    ("railways abstract CRT TJ", "railways", "00_abstract.tex",
     r"book \\num\{(\d+)\} TJ for railways",
     lambda: _first_where("railways_unfccc_crt_cell_audit_2024.csv", "value",
                          field="activity_TJ"), 1.0),
    ("railways intro matched year", "railways", "01_introduction.tex",
     r"run on the operator's metered fuel for that same fiscal year,\s+gets "
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.0005),
    ("railways conclusion matched year", "railways", "09_conclusion.tex",
     r"times the \\SI\{([\d.]+)\}\{\\mega\\tonne\} the identical method gives",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Matched year: own FY2017-18 estimate", "co2e_Mt_AR5"), 0.0005),
    ("railways uncertainty grouped", "railways", "06b_uncertainty.tex",
     r"lands at \$\\pm\$\\SI\{([\d.]+)\}\{\\percent\} on the sector\s+total",
     lambda: _cell("railways_uncertainty_2024.csv", "category", "Railways",
                   "approach1_pct_grouped"), 0.05),
    ("railways ELK ratio", "railways", "05_validation.tex",
     r"same calendar\s+year---\\num\{([\d.]+)\} times",
     lambda: _first_where("railways_elk_crosscheck_2024.csv",
                          "ratio_elk_over_own", subsector="rail-total",
                          species="CO2-rep"), 0.005),
    # The BUR-side arithmetic is derived, not transcribed: implied diesel from the CO2
    # factor chain, implied intensity over the operator's own train-km. Recomputed here so
    # 'roughly' cannot drift into 'wrong'.
    ("railways implied diesel", "railways", "05_validation.tex",
     r"requires the combustion of\s+roughly \\SI\{(\d+)\}\{\\kilo\\tonne\} of diesel",
     lambda: 4.06e3 / (_ef("rail_co2_diesel") * _ef("rail_ncv_diesel") / 1e6), 10.0),
    ("railways actual intensity", "railways", "05_validation.tex",
     r"consumption works out at\s+\\SI\{([\d.]+)\}\{\\litre\} per train-kilometre",
     lambda: _rail_fuel(2024) / _railpar("train_km_thousand"), 0.05),
    ("railways implied intensity", "railways", "05_validation.tex",
     r"would be \\SI\{(\d+)\}\{\\litre\} per train-kilometre",
     lambda: (4.06e3 / (_ef("rail_co2_diesel") * _ef("rail_ncv_diesel") / 1e6)) * 1e6
             / _railpar("hsd_density_kg_per_l") / 1e3 / _railpar("train_km_thousand"), 1.0),
    # Figure captions carry numbers too, and nothing else checks them.
    ("railways caption gas split CO2", "railways", "06_results.tex",
     r"\\COtwo\{\} is \\SI\{([\d.]+)\}\{\\percent\} of the category",
     lambda: 100 * _sum_where("railways_by_stream_2024.csv", "co2e_Mt_AR5", gas="CO2")
             / _cell("railways_totals_2024.csv", "category",
                     "Module total (both categories)", "co2e_Mt_AR5"),
     0.0),
    ("railways caption gas split N2O", "railways", "06_results.tex",
     r"\\NtwoO\{\} is\s+\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * _sum_where("railways_by_stream_2024.csv", "co2e_Mt_AR5", gas="N2O")
             / _cell("railways_totals_2024.csv", "category",
                     "Module total (both categories)", "co2e_Mt_AR5"),
     0.0),
    ("railways series first year", "railways", "06_results.tex",
     r"Emissions rise from \\SI\{([\d.]+)\}\{\} to",
     lambda: _cell("railways_timeseries_2024.csv", "fiscal_year", "2014", "mt_co2e_AR5"),
     0.0),
    ("railways series peak", "railways", "06_results.tex",
     r"peaking at \\SI\{([\d.]+)\}\{\\mega\\tonne\} in FY2019",
     lambda: _cell("railways_timeseries_2024.csv", "fiscal_year", "2019", "mt_co2e_AR5"),
     0.0),
    ("railways series FY2022", "railways", "06_results.tex",
     r"dropping from \\SI\{([\d.]+)\}\{\} in FY2022",
     lambda: _cell("railways_timeseries_2024.csv", "fiscal_year", "2022", "mt_co2e_AR5"),
     0.0),
    ("railways series FY2023", "railways", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} in FY2023",
     lambda: _cell("railways_timeseries_2024.csv", "fiscal_year", "2023", "mt_co2e_AR5"),
     0.0),
    ("railways caption Punjab", "railways", "06_results.tex",
     r"Punjab \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("railways_provincial_2024.csv", "province", "Punjab", "co2e_Mt_AR5"),
     0.0),
    ("railways caption KP", "railways", "06_results.tex",
     r"Khyber Pakhtunkhwa\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("railways_provincial_2024.csv", "province", "Khyber Pakhtunkhwa",
                   "co2e_Mt_AR5"), 0.0),
    ("railways caption Balochistan", "railways", "06_results.tex",
     r"Balochistan\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("railways_provincial_2024.csv", "province", "Balochistan",
                   "co2e_Mt_AR5"), 0.0005),
    # ---- ippu ----
    ("cement total", "ippu", "06_results.tex",
     r"producers report and gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo",
     lambda: _cell("ippu_totals_2024.csv", "category", "Cement production",
                   "co2e_Mt_AR5"), 0.0),
    ("cement current no-trade benchmark", "ippu", "06_results.tex",
     r"correct FY2023--24 activity but omitting observed trade gives\s*\\SI\{([\d.]+)\}",
     lambda: _first_where("ippu_cement_method_benchmarks_2024.csv", "co2e_Mt_AR5",
                          benchmark_id="cement_no_trade_method_benchmark"), 0.0),
    # rc41 M-2: the printed range is the TIER 1 bracket (the two IPCC clinker fractions);
    # the census reference sits above it and is anchored separately. The old getters took
    # the min/max over every valid scenario, which put the census at the "0.95" end.
    ("cement structural minimum", "ippu", "06_results.tex",
     r"structural range is\s*([\d.]+)--[\d.]+ Mt",
     lambda: _first_where("ippu_cement_valid_structural_2024.csv", "co2e_Mt_AR5",
                          scenario_id="pbs_qim_fy2023_24_f0.75_trade"), 0.0),
    ("cement structural maximum", "ippu", "06_results.tex",
     r"structural range is\s*[\d.]+--([\d.]+) Mt",
     lambda: _first_where("ippu_cement_valid_structural_2024.csv", "co2e_Mt_AR5",
                          scenario_id="pbs_qim_fy2023_24_f0.95_trade"), 0.0),
    ("cement census above the bracket", "ippu", "06_results.tex",
     r"observed census \(([\d.]+) Mt\) sits",
     lambda: _first_where("ippu_cement_valid_structural_2024.csv", "co2e_Mt_AR5",
                          scenario_id="producer_census_observed"), 0.0),
    ("cement census margin over the high case", "ippu", "06_results.tex",
     r"sits\s*([\d.]+)\\% above the high end",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_vs_high_inference_pct") - 100.0, 0.0),
    ("ippu conclusion census margin", "ippu", "09_conclusion.tex",
     r"Mt\), ([\d.]+)\\% above the high case",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_vs_high_inference_pct") - 100.0, 0.0),
    # rc59 campaign cycle 1: the limitations section had said the module "covers only cement
    # calcination", so these four category values and the cement share were unregistered the
    # moment they were printed. Each resolves from outputs/ippu_totals_2024.csv, the module's
    # own product, which names itself "sum of the four activated categories".
    ("ippu limitations ammonia co2", "ippu", "08_limitations.tex",
     r"ammonia production \(2\.B\.1,\s*\\SI\{([\d.]+)\}",
     lambda: round(_first_where("ippu_totals_2024.csv", "co2e_Mt_AR5",
                                category="Ammonia production"), 4), 0.0),
    ("ippu limitations iron steel co2", "ippu", "08_limitations.tex",
     r"iron and steel \(2\.C\.1,\s*\\SI\{([\d.]+)\}",
     lambda: round(_first_where("ippu_totals_2024.csv", "co2e_Mt_AR5",
                                category="Iron and steel production"), 4), 0.0),
    ("ippu limitations lubricant co2", "ippu", "08_limitations.tex",
     r"lubricant use \(2\.D\.1,\s*\\SI\{([\d.]+)\}",
     lambda: round(_first_where("ippu_totals_2024.csv", "co2e_Mt_AR5",
                                category="Lubricant use"), 4), 0.0),
    ("ippu limitations module total", "ippu", "08_limitations.tex",
     r"module total of\s*\\SI\{([\d.]+)\}",
     lambda: round(_first_where("ippu_totals_2024.csv", "co2e_Mt_AR5",
                                category="IPPU reference total"), 4), 0.0),
    ("ippu limitations cement share", "ippu", "08_limitations.tex",
     r"Cement is therefore\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: round(100.0 * _first_where("ippu_totals_2024.csv", "co2e_Mt_AR5",
                                        category="Cement production")
                   / _first_where("ippu_totals_2024.csv", "co2e_Mt_AR5",
                                  category="IPPU reference total"), 1), 0.0),
    ("ippu limitations census margin", "ippu", "08_limitations.tex",
     r"the high case by\s*([\d.]+)\\%",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_vs_high_inference_pct") - 100.0, 0.0),
    ("ippu abstract low coverage", "ippu", "00_abstract.tex",
     r"of clinker,\s*([\d.]+)\\% of the low-clinker",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_vs_low_inference_pct"), 0.0),
    ("ippu abstract high coverage", "ippu", "00_abstract.tex",
     r"and ([\d.]+)\\% of the high case, which",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_vs_high_inference_pct"), 0.0),
    ("cement reference P025", "ippu", "06_results.tex",
     r"95\\% interval of ([\d.]+)--[\d.]+ Mt",
     lambda: _first_where("ippu_cement_conditional_intervals_2024.csv", "p025_mt_co2",
                          configuration="reference (producer census)"), 0.0),
    ("cement reference P975", "ippu", "06_results.tex",
     r"95\\% interval of [\d.]+--([\d.]+) Mt",
     lambda: _first_where("ippu_cement_conditional_intervals_2024.csv", "p975_mt_co2",
                          configuration="reference (producer census)"), 0.0),
    ("cement clinker exports", "ippu", "06_results.tex",
     r"Adding\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\} of exports",
     lambda: _cell("ippu_cement_material_balance_2024.csv", "flow", "exports",
                   "amount_kt") / 1000.0, 0.0),
    ("company clinker subset", "ippu", "06_results.tex",
     r"company filings sum to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_clinker_mt"), 0.0),
    ("company clinker coverage", "ippu", "06_results.tex",
     r"observed census is ([\d.]+)\\%",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_vs_low_inference_pct"), 0.0),
    ("company clinker high-case coverage", "ippu", "06_results.tex",
     r"and ([\d.]+)\\% of the 0.95\s*inference",
     lambda: _first_where("ippu_company_clinker_coverage_2024.csv",
                          "reported_vs_high_inference_pct"), 0.0),
    ("official IPPU total", "ippu", "06_results.tex",
     r"reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe",
     lambda: _first_where("ippu_unfccc_crt_summary_2022.csv", "total_co2e_kt",
                          category="2. Total industrial processes") / 1000.0, 0.0),
    ("cement matched 2022", "ippu", "06_results.tex",
     r"and\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\} at the 0.75 fraction",
     lambda: _first_where("ippu_cement_matched_calendar_2022.csv", "co2_mt",
                          clinker_fraction="0.75"), 0.0),
    # ---- power: the CRT filing ----
    ("crt activity", "power", "05_validation.tex",
     r"reports 1\.A\.1\.a at \\SI\{([\d]+)\}\{\} TJ",
     lambda: _cell("power_crt_comparison.csv", "item",
                   "CRT 1.A.1.a activity (TJ, CY2022)", "value"), 0.5),
    ("crt co2", "power", "05_validation.tex",
     r"TJ and \\SI\{([\d]+)\}\{\\kilo\\tonne\} \\COtwo\{\}",
     lambda: _cell("power_crt_comparison.csv", "item", "CRT 1.A.1.a CO2 (kt)", "value"), 0.5),
    # ---- power: conclusion and captions ----
    # These drifted through three review rounds precisely because they were unpinned: the
    # conclusion still said 60.31 Mt three commits after the sector moved to 63.58, and the
    # provincial caption lagged the coal-blend change. Prose is where staleness hides.
    ("conclusion sector total", "power", "09_conclusion.tex",
     r"emitted \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} in FY2023--24",
     lambda: _cell("power_totals_fy2023_24.csv", "category", "TOTAL", "co2e_Mt_AR5"), 0.0),
    ("conclusion SO2 bound", "power", "09_conclusion.tex",
     r"uncontrolled---\\SI\{([\d.]+)\}\{\\kilo\\tonne\} \\SOtwo\{\}",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="SO2"), 0.5),
    ("conclusion NOx bound", "power", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\kilo\\tonne\} \\NOx\{\}, \\SI",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="NOx"), 0.5),
    ("power SO2 abstract", "power", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\kilo\\tonne\} \\SOtwo\{\}",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="SO2"), 0.5),
    ("conclusion PM2.5 bound", "power", "09_conclusion.tex",
     r"\\SI\{([\d.]+)\}\{\\kilo\\tonne\} PM\\textsubscript\{2.5\} from each coal rank",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.5),
    ("abstract NOx bound", "power", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\kilo\\tonne\}\s+\\NOx\{\}, \\SI",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="NOx"), 0.5),
    ("abstract PM2.5 bound", "power", "00_abstract.tex",
     r"of which \\SI\{([\d.]+)\}\{\\kilo\\tonne\} is\s+PM\\textsubscript\{2.5\}",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.5),
    ("abstract gas turbine share", "power", "00_abstract.tex",
     r"classification of the fleet, \\SI\{([\d.]+)\}\{\\percent\} combined-cycle",
     lambda: 100 * float(_cell("power_gas_technology_fy2023_24.csv", "bucket", "turbine",
                               "share")), 0.5),
    # ---- power: the air table and the combustor split (06b) ----
    ("air table NOx", "power", "06b_air_pollutants.tex",
     r"\\NOx\{\}          & ([\d.]+) ",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="NOx"), 0.05),
    ("air table PM", "power", "06b_air_pollutants.tex",
     r"PM \(filterable\) & ([\d.]+) ",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM"), 0.05),
    ("air table PM10", "power", "06b_air_pollutants.tex",
     r"PM\\textsubscript\{10\} & ([\d.]+) ",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM10"), 0.05),
    ("air table PM2.5", "power", "06b_air_pollutants.tex",
     r"PM\\textsubscript\{2.5\} & ([\d.]+) ",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.05),
    ("air gas turbine share", "power", "06b_air_pollutants.tex",
     r"classifies as \\SI\{([\d.]+)\}\{\\percent\} turbine",
     lambda: 100 * float(_cell("power_gas_technology_fy2023_24.csv", "bucket", "turbine",
                               "share")), 0.05),
    ("air gas boiler share", "power", "06b_air_pollutants.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} boiler",
     lambda: 100 * float(_cell("power_gas_technology_fy2023_24.csv", "bucket", "boiler",
                               "share")), 0.05),
    ("air gas unresolved share", "power", "06b_air_pollutants.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} unresolved",
     lambda: 100 * float(_cell("power_gas_technology_fy2023_24.csv", "bucket", "unresolved",
                               "share")), 0.05),
    ("air coal PM2.5", "power", "06b_air_pollutants.tex",
     r"uncontrolled PM\\textsubscript\{2.5\}, \\SI\{([\d.]+)\}\{\} of it from coal",
     lambda: _sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        fuel="Coal", pollutant="PM2.5"), 0.05),
    # ---- power: the per-fuel CO2 paragraph and the bagasse stream ----
    # Gas, furnace oil and diesel drifted a full anchor-year behind (5.06 Mt of furnace
    # oil was FY2022) because only the coal figure was pinned. Now all four are.
    ("power gas CO2", "power", "06_results.tex",
     r"gas \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                        subitem="Gas CO2"), 0.005),
    ("power FO CO2", "power", "06_results.tex",
     r"furnace oil\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                        subitem="Furnace Oil CO2"), 0.005),
    ("power diesel CO2", "power", "06_results.tex",
     r"diesel \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _sum_where("power_by_stream_fy2023_24.csv", "co2e_Mt_AR5",
                        subitem="Diesel Oil CO2"), 0.005),
    ("power coal energy share", "power", "06_results.tex",
     r"Coal is \\SI\{([\d.]+)\}\{\\percent\} of the\s+energy",
     lambda: _cell("power_fuel_fy2023_24.csv", "fuel", "Coal", "share_pct"), 0.05),
    ("power bagasse GWh", "power", "06_results.tex",
     r"sold \\SI\{([\d.]+)\}\{GWh\} of bagasse-fired",
     lambda: _cell("power_bagasse_fy2023_24.csv", "item", "Generation (GWh)", "value"), 0.005),
    ("power bagasse memo", "power", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of biogenic",
     lambda: _cell("power_bagasse_fy2023_24.csv", "item", "Biogenic CO2 memo (Gg)",
                   "value") / 1000.0, 0.01),
    # ---- power: the rebuilt uncertainty statement ----
    # The +/-% cells were never pinned, which is how 15.3 would have survived the rebuild.
    ("power grid A1", "power", "06_results.tex",
     r"Electricity and heat production & 1A1a & [\d.]+ & ([\d.]+) ",
     lambda: _cell("power_uncertainty_fy2023_24.csv", "category",
                   "Electricity and heat production", "approach1_pct_grouped"), 0.0),
    ("power sector A1", "power", "06_results.tex",
     r"\\textbf\{Total\}                  &      & \\textbf\{[\d.]+\} & \\textbf\{([\d.]+)\}",
     lambda: _cell("power_uncertainty_fy2023_24.csv", "category", "TOTAL",
                   "approach1_pct_grouped"), 0.0),
    ("power grid A1 independent", "power", "06_results.tex",
     r"give \\SI\{([\d.]+)\}\{\\percent\}\); the one-sided",
     lambda: _cell("power_uncertainty_fy2023_24.csv", "category",
                   "Electricity and heat production", "approach1_pct_independent"), 0.0),
    ("power scenario gross basis", "power", "06_results.tex",
     r"TOE on a gross basis          & ([\d.]+) ",
     lambda: _cell("power_uncertainty_scenarios_fy2023_24.csv", "structural_scenario",
                   "toe_gross_basis", "deterministic_Mt"), 0.0),
    ("power scenario KE", "power", "06_results.tex",
     r"Grid \+ K-Electric ledger fuel & ([\d.]+) ",
     lambda: _cell("power_uncertainty_scenarios_fy2023_24.csv", "structural_scenario",
                   "grid_plus_ke_ledger_fuel", "deterministic_Mt"), 0.0),
    ("04b gross basis scenario", "power", "04b_emission_factors.tex",
     r"computes to\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\} against",
     lambda: _cell("power_uncertainty_scenarios_fy2023_24.csv", "structural_scenario",
                   "toe_gross_basis", "deterministic_Mt"), 0.005),
    ("national power A1", "national", "06_results.tex",
     r"Power module\s+&[^&]*&\s*[\d.]+ &\s*[\d.]+ &\s*([\d.]+) \\\\",
     lambda: _sector("power", "uncert_pct_95"), 0.0),
    # ---- power: the LMDI decomposition and the plant-level TRACE benchmark ----
    ("lmdi total rise", "power", "05_validation.tex",
     r"attributes the \\SI\{(-?[\d.]+)\}\{\\mega\\tonne\} change",
     lambda: _first_where("power_lmdi_fy2023_24.csv", "delta_Mt", y0="2013", y1="2023"), 0.05),
    ("lmdi activity term", "power", "05_validation.tex",
     r"as\s+\\SI\{(-?[\d.]+)\}\{\\mega\\tonne\} of activity",
     lambda: _first_where("power_lmdi_fy2023_24.csv", "activity_Mt", y0="2013", y1="2023"),
     0.05),
    ("lmdi mix term", "power", "05_validation.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s+mix",
     lambda: _first_where("power_lmdi_fy2023_24.csv", "mix_Mt", y0="2013", y1="2023"), 0.05),
    ("lmdi coal mix", "power", "05_validation.tex",
     r"coal contributes\s+\\SI\{\+([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("power_lmdi_fy2023_24.csv", "coal_mix_Mt", y0="2013", y1="2023"),
     0.05),
    ("lmdi fo mix", "power", "05_validation.tex",
     r"furnace oil \\SI\{-([\d.]+)\}\{\}",
     lambda: -_first_where("power_lmdi_fy2023_24.csv", "fo_mix_Mt", y0="2013", y1="2023"),
     0.05),
    ("lmdi factor term", "power", "05_validation.tex",
     r"the prediction held at \\SI\{\+([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("power_lmdi_fy2023_24.csv", "factor_Mt",
                          y0="2013", y1="2023"), 0.05),
    ("lmdi fy2021 spike", "power", "05_validation.tex",
     r"whose \\SI\{(-?[\d.]+)\}\{\\mega\\tonne\} step",
     lambda: _first_where("power_lmdi_fy2023_24.csv", "delta_Mt", y0="2020", y1="2021"), 0.05),
    ("trace coal label total", "power", "05_validation.tex",
     r"Climate TRACE reports \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\}",
     lambda: sum(float(r["trace_co2e_t"])
                 for r in _rows_banner("power_climatetrace_plants_fy2023_24.csv")
                 if r["asset_type"] == "coal") / 1e6, 0.05),
    ("trace label intensity", "power", "05_validation.tex",
     r"carries exactly\s+\\SI\{([\d.]+)\}\{\\gram\\per\\kilo\\watt\\hour\}",
     lambda: _first_where("power_climatetrace_plants_fy2023_24.csv", "trace_g_per_kwh",
                          trace_name="Thar Block I power station"), 0.5),
    # ---- power: the TROPOMI channel ----
    ("tropomi thar no2 ratio", "power", "05_validation.tex",
     r"enhancement rose \\num\{([\d.]+)\}-fold",
     lambda: _cell("power_tropomi_crosscheck.csv", "source",
                   "VERDICT: h2_thar_no2_ratio", "no2_enh_mol_m2"), 0.0),
    ("tropomi thar so2 ratio", "power", "05_validation.tex",
     r"the lignite sulfur signature---\\num\{([\d.]+)\}-fold",
     lambda: _cell("power_tropomi_crosscheck.csv", "source",
                   "VERDICT: h2_thar_so2_ratio", "no2_enh_mol_m2"), 0.0),
    ("tropomi hub ratio", "power", "05_validation.tex",
     r"\(ratio \\num\{([\d.]+)\} against",
     lambda: _cell("power_tropomi_crosscheck.csv", "source",
                   "VERDICT: h1_hub_ratio_fy2023_over_fy2020", "no2_enh_mol_m2"), 0.0),
    ("tropomi sahiwal arbitration", "power", "05_validation.tex",
     r"NEPRA's tables---says \\num\{([\d.]+)\}",
     lambda: _cell("power_tropomi_crosscheck.csv", "source",
                   "VERDICT: h3_sahiwal_enh_ratio_fy2021_over_fy2020",
                   "no2_enh_mol_m2"), 0.0),
    ("tropomi within rho", "power", "05_validation.tex",
     r"Spearman \$\\rho = ([\d.]+)\$",
     lambda: _cell("power_tropomi_crosscheck.csv", "source",
                   "SPEARMAN within-source", "no2_enh_mol_m2"), 0.0),
    ("tropomi thar so2 fy2023", "power", "05_validation.tex",
     r"to\s+\\SI\{([\d.e-]+)\}\{\\mole\\per\\metre\\squared\}: the strongest",
     lambda: _first_where("power_tropomi_crosscheck.csv", "so2_enh_mol_m2",
                          source="thar_cluster", fiscal_year="2023"), 3e-7),
    # ---- power: the K-Electric leg ----
    ("validation KE sensitivity", "power", "05_validation.tex",
     r"K-Electric ledger fuel'':\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: grid + K-Electric ledger fuel", "co2e_Mt_AR5"), 0.005),
    ("validation KE series start", "power", "05_validation.tex",
     r"rows imply \\SI\{([\d.]+)\}\{\}, \\SI",
     lambda: _cell("power_ke_leg_fy2023_24.csv", "fiscal_year", "2019", "co2_Mt"), 0.05),
    ("validation KE series end", "power", "05_validation.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\}\s+\\COtwo\{\} across FY2019--24",
     lambda: _cell("power_ke_leg_fy2023_24.csv", "fiscal_year", "2023", "co2_Mt"), 0.05),
    ("conclusion KE range start", "power", "09_conclusion.tex",
     r"a trending \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _cell("power_ke_leg_fy2023_24.csv", "fiscal_year", "2019", "co2_Mt"), 0.05),
    # ---- power: the implied coal CV channel (Tables 20/23/28) ----
    # The arbitration numbers appear in four sections; every one is pinned to the CSV the
    # runner writes, because these are exactly the claims a future data refresh would move.
    ("validation Thar CV", "power", "05_validation.tex",
     r"mass-weighted \\SI\{([\d.]+)\}\{\} in\s+FY2023--24",
     lambda: _first_where("power_implied_coal_cv_fy2023_24.csv", "implied_cv_TJ_per_Gg",
                          fiscal_year="2023", plant="Thar lignite only"), 0.05),
    ("validation fleet CV", "power", "05_validation.tex",
     r"implies \\SI\{([\d.]+)\}\{\} TJ/Gg against the \\SI\{24.2\}",
     lambda: _first_where("power_implied_coal_cv_fy2023_24.csv", "implied_cv_TJ_per_Gg",
                          fiscal_year="2023", plant="FLEET (mass-weighted)"), 0.05),
    ("validation CV factor", "power", "05_validation.tex",
     r"a factor of \\num\{([\d.]+)\}, and \\num\{1.62\}",
     lambda: (_first_where("power_implied_coal_cv_fy2023_24.csv", "implied_cv_TJ_per_Gg",
                           fiscal_year="2023", plant="Table 3 implied NCV")
              / _first_where("power_implied_coal_cv_fy2023_24.csv", "implied_cv_TJ_per_Gg",
                             fiscal_year="2023", plant="FLEET (mass-weighted)")), 0.01),
    ("validation restated sensitivity", "power", "05_validation.tex",
     r"labelled sensitivity of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: coal at ledger mass x implied CV", "co2e_Mt_AR5"), 0.005),
    ("abstract Thar CV", "power", "00_abstract.tex",
     r"put the Thar plants at\s+\\SI\{([\d.]+)\}\{\} TJ/Gg",
     lambda: _first_where("power_implied_coal_cv_fy2023_24.csv", "implied_cv_TJ_per_Gg",
                          fiscal_year="2023", plant="Thar lignite only"), 0.05),
    ("abstract CV at stake", "power", "00_abstract.tex",
     r"worth \\SI\{([\d.]+)\}\{\\mega\\tonne\}; and the plant sums",
     lambda: (_cell("power_totals_fy2023_24.csv", "category",
                    "Electricity and heat production", "co2e_Mt_AR5")
              - _cell("power_totals_fy2023_24.csv", "category",
                      "Sensitivity: coal at ledger mass x implied CV",
                      "co2e_Mt_AR5")), 0.05),
    ("abstract restated sensitivity", "power", "00_abstract.tex",
     r"grid\\_plant\\_cv\\_restated\} \\SI\{([\d.]+)\}\{\\mega\\tonne\} and",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: coal at ledger mass x implied CV", "co2e_Mt_AR5"), 0.005),
    ("conclusion Thar CV", "power", "09_conclusion.tex",
     r"put the Thar plants at \\SI\{([\d.]+)\}\{\} TJ/Gg",
     lambda: _first_where("power_implied_coal_cv_fy2023_24.csv", "implied_cv_TJ_per_Gg",
                          fiscal_year="2023", plant="Thar lignite only"), 0.05),
    ("conclusion restated sensitivity", "power", "09_conclusion.tex",
     r"grid\\_plant\\_cv\\_restated\} \\SI\{([\d.]+)\}\{\\mega\\tonne\}, the same mass at",
     lambda: _cell("power_totals_fy2023_24.csv", "category",
                   "Sensitivity: coal at ledger mass x implied CV", "co2e_Mt_AR5"), 0.005),
    ("provincial caption Punjab", "power", "06_results.tex",
     r"\\caption\{Punjab \\SI\{([\d.]+)\}\{\\mega\\tonne\}, Sindh",
     lambda: _cell("power_provincial_fy2023_24.csv", "province", "Punjab", "co2e_Mt_AR5"), 0.0),
    ("provincial caption Sindh", "power", "06_results.tex",
     r"Sindh \\SI\{([\d.]+)\}\{\\mega\\tonne\}, Balochistan",
     lambda: _cell("power_provincial_fy2023_24.csv", "province", "Sindh", "co2e_Mt_AR5"), 0.0),
    ("provincial caption Balochistan", "power", "06_results.tex",
     r"Balochistan\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\}, Khyber",
     lambda: _cell("power_provincial_fy2023_24.csv", "province", "Balochistan",
                   "co2e_Mt_AR5"), 0.0),
    ("validation coal efficiency low", "power", "05_validation.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} in FY2023--24, a three-fold",
     lambda: 100 * _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Coal",
                         "efficiency_lo"), 0.05),
    # ---- power: the implied-heat-rate diagnostic ----
    # Percentages in the paper against fractions in the CSV, so each getter scales by 100.
    ("heat rate gas lo", "power", "05_validation.tex",
     r"Gas \(incl\.\\ RLNG\) & \\SIrange\{([\d.]+)\}",
     lambda: 100 * _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Gas",
                         "efficiency_lo"), 0.0),
    ("heat rate gas hi", "power", "05_validation.tex",
     r"Gas \(incl\.\\ RLNG\) & \\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: 100 * _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Gas",
                         "efficiency_hi"), 0.0),
    ("heat rate gas spread", "power", "05_validation.tex",
     r"Gas \(incl\.\\ RLNG\) & \\SIrange\{[\d.]+\}\{[\d.]+\}\{\\percent\} & \$\\times\$([\d.]+)",
     lambda: _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Gas", "spread"), 0.0),
    ("heat rate coal lo", "power", "05_validation.tex",
     r"Coal              & \\SIrange\{([\d.]+)\}",
     lambda: 100 * _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Coal",
                         "efficiency_lo"), 0.0),
    ("heat rate coal hi", "power", "05_validation.tex",
     r"Coal              & \\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: 100 * _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Coal",
                         "efficiency_hi"), 0.0),
    ("heat rate coal spread", "power", "05_validation.tex",
     r"Coal              & \\SIrange\{[\d.]+\}\{[\d.]+\}\{\\percent\} & \$\\times\$([\d.]+)",
     lambda: _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Coal", "spread"), 0.0),
    # ---- railways: the Year Book against itself (the FY2024 detail dispute was resolved
    # by the 2024-25 edition's restatement; the retired sensitivity's anchors went with it,
    # and tab:yearbook is reconciled row-by-row by TestTablesMatchTheEngine) ----
    ("railways non-traction share", "railways", "08_limitations.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the total \(since the 2024--25",
     lambda: _cell("railways_totals_2024.csv", "category",
                   "Non-traction share of diesel", "co2e_Mt_AR5"), 0.0),
    ("railways series last year", "railways", "06_results.tex",
     r"Emissions rise from \\SI\{[\d.]+\}\{\} to\s+\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("railways_timeseries_2024.csv", "fiscal_year", "2025", "mt_co2e_AR5"),
     0.0005),
    # ---- transport: CNG, now estimated from metered gas ----
    ("cng total", "transport", "06_results.tex",
     r"CNG                       &  ([\d.]+)",
     lambda: _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                        subitem="CNG CO2") +
             _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5", subitem="CNG CH4") +
             _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5", subitem="CNG N2O"),
     0.0),
    ("cng 900 sensitivity", "transport", "06_results.tex",
     r"CNG at \\SI\{900\}\{\} Btu/scf     & ([\d.]+)",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category",
                   "Sensitivity: CNG at 900 Btu/scf", "co2e_Mt_AR5"), 0.0),
    ("cng implied intensity", "transport", "05_validation.tex",
     r"implying \\SI\{([\d.]+)\}\{\\mega\\joule\\per\\kilo\\metre\}",
     lambda: _cell("transport_cng_crosscheck_%d.csv" % _transport_year(), "item",
                   "Implied energy intensity", "value"), 0.0),
    ("heat rate furnace oil hi", "power", "05_validation.tex",
     r"Furnace oil       & \\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: 100 * _cell("power_heat_rate_stability_fy2023_24.csv", "fuel", "Furnace Oil",
                         "efficiency_hi"), 0.0),

    # ---- transport: the August 2026 hardening round. Every prose number the earlier
    # ---- edition got wrong (AR6 total, key-category shares, EDGAR arithmetic, the
    # ---- provincial caption, the cross-paper comparators) is now anchored, because
    # ---- each of these drifted with nothing failing.
    ("transport AR5 prose", "transport", "06_results.tex",
     r"together \\SI\{([\d.]+)\}\{\\mega\\tonne\} on AR5",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"),
     0.0),
    ("transport AR6 prose", "transport", "06_results.tex",
     r"The AR6 total is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR6"),
     0.0),
    ("transport CO2 share of sector", "transport", "06_results.tex",
     r"the sector is\s*\\SI\{([\d.]+)\}\{\\percent\} \\COtwo\{\}",
     lambda: 100 * _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5", gas="CO2")
             / _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"),
     0.0),
    ("transport abstract road", "transport", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}~\\COe\{\} as the\s*\\emph\{conditional",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category", "Road transport",
                   "co2e_Mt_AR5"), 0.0),
    ("transport abstract off-road", "transport", "00_abstract.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} for mixed\s*off-road machinery",
     lambda: _cell("transport_totals_%d.csv" % _transport_year(), "category",
                   "Mixed off-road (1A4c/1A2)", "co2e_Mt_AR5"), 0.0),
    ("transport abstract rail agreement", "transport", "00_abstract.tex",
     r"agrees to \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * _first_where("transport_uncertainty_inputs_%d.csv" % _transport_year(),
                                "central_value",
                                variable="Rail figure cross-check "
                                         "(year-matched FY2021-22)"), 0.0),
    ("transport abstract EDGAR ratio", "transport", "00_abstract.tex",
     r"estimate is \\num\{([\d.]+)\} of\s*it",
     lambda: _transport_edgar_scope() / _edgar_blend(), 0.0),
    ("transport conclusion share", "transport", "09_conclusion.tex",
     r"together \\SI\{([\d.]+)\}\{\\percent\} of a ten-sector",
     lambda: _sector("transport", "share_pct"), 0.0),
    ("transport abstract petrol control", "transport", "00_abstract.tex",
     r"\\SI\{([\d]+)\}\{\\kilo\\tonne\} petrol",
     lambda: _first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "kt", fuel="Petrol",
                          tier="national", claimant="Road (retail pump sales)"),
     0.0),
    ("transport abstract diesel control", "transport", "00_abstract.tex",
     r"petrol, \\SI\{([\d]+)\}\{\\kilo\\tonne\} diesel",
     lambda: _first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "kt", fuel="Diesel",
                          tier="national", claimant="Road (retail pump sales)"),
     0.0),
    ("transport rail crosscheck gap", "transport", "04_methods.tex",
     r"agree to \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * _first_where("transport_uncertainty_inputs_%d.csv" % _transport_year(),
                                "central_value",
                                variable="Rail figure cross-check (year-matched FY2021-22)"),
     0.0),
    ("transport rail crosscheck cross-year", "transport", "04_methods.tex",
     r"cross-year comparison at\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * _first_where("transport_uncertainty_inputs_%d.csv" % _transport_year(),
                                "central_value",
                                variable="Rail figure cross-check "
                                         "(FY2023-24 relay)"), 0.0),
    ("transport rail crosscheck ocac", "transport", "04_methods.tex",
     r"OCAC's sold\s*\\SI\{([\d.]+)\}\{\\kilo\\tonne\} agree",
     lambda: _first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "kt", fuel="Diesel",
                          tier="national", claimant="Railways"), 0.0),

    ("transport methods generator kt", "transport", "04_methods.tex",
     r"Rs 249--293: \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _cell("transport_fuel_ledger_%d.csv" % _transport_year(), "claimant",
                   "Household generators", "kt"), 0.0),
    ("transport keycat level results", "transport", "06_results.tex",
     r"Road transport is \\SI\{([\d.]+)\}\{\\percent\} of Pakistan's emissions",
     lambda: _keycat("Road transport", "level_pct"), 0.0),
    ("transport keycat variance results", "transport", "06_results.tex",
     r"of Pakistan's emissions and\s*\\SI\{([\d.]+)\}\{\\percent\} of its inventory "
     r"variance",
     lambda: _keycat("Road transport", "variance_share_pct_independent_approx"), 0.0),
    ("transport keycat level discussion", "transport", "07_discussion.tex",
     r"Road transport is\s*\\SI\{([\d.]+)\}\{\\percent\} of national emissions",
     lambda: _keycat("Road transport", "level_pct"), 0.0),
    ("transport keycat variance discussion", "transport", "07_discussion.tex",
     r"national emissions and \\SI\{([\d.]+)\}\{\\percent\} of national inventory\s*"
     r"variance",
     lambda: _keycat("Road transport", "variance_share_pct_independent_approx"), 0.0),
    ("transport keycat level conclusion", "transport", "09_conclusion.tex",
     r"road transport is \\SI\{([\d.]+)\}\{\\percent\} of national emissions",
     lambda: _keycat("Road transport", "level_pct"), 0.0),
    ("transport keycat variance conclusion", "transport", "09_conclusion.tex",
     r"national emissions and\s*\\SI\{([\d.]+)\}\{\\percent\} of national inventory "
     r"variance",
     lambda: _keycat("Road transport", "variance_share_pct_independent_approx"), 0.0),
    # EDGAR, year-matched: the value, the sector ratio, and the scope-matched sum.
    ("transport EDGAR blend value intro", "transport", "01_introduction.tex",
     r"fiscal-year blend of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     _edgar_blend, 0.0),
    ("transport EDGAR 2023 column", "transport", "05_validation.tex",
     r"\$0\.5 \\times \\SI\{([\d.]+)\}\{\}",
     lambda: _edgar_series(2023), 0.0),
    ("transport EDGAR 2024 column", "transport", "05_validation.tex",
     r"\+ 0\.5 \\times \\SI\{([\d.]+)\}\{\}",
     lambda: _edgar_series(2024), 0.0),
    ("transport EDGAR blend value validation", "transport", "05_validation.tex",
     r"= \\SI\{([\d.]+)\}\{\\mega\\tonne\}\$, and that",
     _edgar_blend, 0.0),
    ("transport EDGAR ratio intro", "transport", "01_introduction.tex",
     r"corresponding construction is \\num\{([\d.]+)\} of EDGAR's",
     lambda: _transport_edgar_scope() / _edgar_blend(), 0.0),
    ("transport EDGAR rail term", "transport", "05_validation.tex",
     r"plus railways\s*\(\\SI\{([\d.]+)\}\{\\mega\\tonne\} strict 1A3c traction",
     lambda: _cell("railways_totals_2024.csv", "category", "Railways",
                   "co2e_Mt_AR5"), 0.0),
    ("transport EDGAR aviation term", "transport", "05_validation.tex",
     r"domestic aviation \(\\SI\{([\d.]+)\}\{\\mega\\tonne\},\s*FY2023--24\)",
     lambda: _cell("aviation_timeseries_2006_fy2023_24.csv", "fiscal_year", "2023",
                   "domestic_kt_co2e_AR5") / 1000.0, 0.0),
    ("transport EDGAR headline sum", "transport", "05_validation.tex",
     r"FY2023--24\) gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}, or \\num",
     _transport_edgar_scope, 0.0),
    ("transport EDGAR headline ratio", "transport", "05_validation.tex",
     r"or \\num\{([\d.]+)\} of EDGAR's fiscal-year",
     lambda: _transport_edgar_scope() / _edgar_blend(), 0.0),
    ("transport EDGAR secondary sum", "transport", "05_validation.tex",
     r"aggregate---gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}, \\num",
     lambda: _transport_edgar_scope(include_offroad=True), 0.0),
    ("transport EDGAR secondary ratio", "transport", "05_validation.tex",
     r"\\mega\\tonne\}, \\num\{([\d.]+)\}\. Every construction",
     lambda: _transport_edgar_scope(include_offroad=True) / _edgar_blend(), 0.0),
    ("transport EDGAR calendar ratio", "transport", "05_validation.tex",
     r"the\s*construction is about \\num\{([\d.]+)\} of EDGAR",
     lambda: _transport_edgar_scope(calendar=True)
             / _bench("EDGAR", "transport", "benchmark_Mt_co2e", year=2022), 0.0),
    # The provincial figure caption - the cells that shipped stale from a superseded run.
    ("transport provincial Punjab", "transport", "06_results.tex",
     r"caption\{Punjab \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("transport_provincial_%d.csv" % _transport_year(), "province", "Punjab",
                   "co2e_Mt_AR5"), 0.0),
    ("transport provincial KP", "transport", "06_results.tex",
     r"Khyber\s*Pakhtunkhwa \\SI\{([\d.]+)\}\{\\mega\\tonne\}, Balochistan",
     lambda: _cell("transport_provincial_%d.csv" % _transport_year(), "province", "Khyber Pakhtunkhwa",
                   "co2e_Mt_AR5"), 0.0),
    ("transport provincial Sindh", "transport", "06_results.tex",
     r"Sindh \\SI\{([\d.]+)\}\{\\mega\\tonne\}, Khyber",
     lambda: _cell("transport_provincial_%d.csv" % _transport_year(), "province", "Sindh",
                   "co2e_Mt_AR5"), 0.0),
    ("transport provincial Balochistan", "transport", "06_results.tex",
     r"Balochistan\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("transport_provincial_%d.csv" % _transport_year(), "province", "Balochistan",
                   "co2e_Mt_AR5"), 0.0),
    ("transport Sindh limitation", "transport", "08_limitations.tex",
     r"Sindh's \\SI\{([\d.]+)\}\{\\percent\} of road\s*diesel",
     lambda: 100 * _first_where(
         "transport_provincial_proxy_comparison_%d.csv" % _transport_year(),
         "diesel_share_fuel", province="Sindh"), 0.0),
    ("transport Sindh diesel share results", "transport", "06_results.tex",
     r"fuel sales give it \\SI\{([\d.]+)\}\{\\percent\} of road\s*diesel",
     lambda: 100 * _first_where(
         "transport_provincial_proxy_comparison_%d.csv" % _transport_year(),
         "diesel_share_fuel", province="Sindh"), 0.0),
    # Cross-paper comparators: read from the RESIDENTIAL engine's outputs, so the two
    # manuscripts cannot disagree about the same number again.
    ("transport residential PM2.5 air", "transport", "06b_air_pollutants.tex",
     r"residential solid fuel's \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _sum_where("residential_air_pollutants_2024.csv", "emissions_kt",
                        pollutant="PM2.5"), 0.05),
    ("transport residential CO", "transport", "06b_air_pollutants.tex",
     r"residential biomass's\s*\\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _sum_where("residential_air_pollutants_2024.csv", "emissions_kt",
                        pollutant="CO"), 0.5),
    ("transport CO", "transport", "06b_air_pollutants.tex",
     r"carbon monoxide of \\SI\{([\d.]+)\}\{\\kilo\\tonne\}",
     lambda: _sum_where("transport_air_pollutants_%d.csv" % _transport_year(), "emissions_kt",
                        pollutant="CO"), 0.5),
    ("transport two-wheeler share caption", "transport", "06_results.tex",
     r"Two-wheelers receive\s*\\SI\{([\d.]+)\}\{\\percent\} of on-road",
     lambda: 100 * _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                              subitem="2W Petrol CO2")
             / _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                          category="Road transport", gas="CO2"), 0.0),
    ("transport methane prose", "transport", "04b_emission_factors.tex",
     r"methane is \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COe\{\} across",
     lambda: _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5", gas="CH4"),
     0.0),
    ("transport by-gas CO2", "transport", "06_results.tex",
     r"By gas the sector is \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\}",
     lambda: _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5", gas="CO2"),
     0.0),
    ("transport by-gas N2O", "transport", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} \\NtwoO\{\} and",
     lambda: _sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5", gas="N2O"),
     0.0),
    # S1: the prose ends of the correlated-factor interval, from the same pooled MC
    # output the table cells are registered against.
    ("transport S1 independent", "transport", "S1_uncertainty.tex",
     r"uncertainty is \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$\s*under either "
     r"correlation treatment",
     lambda: _mc("within_sector", "transport"), 0.0),
    ("transport S1 correlated", "transport", "S1_uncertainty.tex",
     r"treatments print the same width \(\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$\)",
     lambda: _mc("cross_sector", "transport"), 0.0),
    ("transport S1 road independent", "transport", "S1_uncertainty.tex",
     r"Road transport goes from \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("within_sector", "Road transport"), 0.0),
    ("transport S1 road correlated", "transport", "S1_uncertainty.tex",
     r"Road transport goes from \$\\pm\\SI\{[\d.]+\}\{\\percent\}\$ to "
     r"\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("cross_sector", "Road transport"), 0.0),
    # S5: the known-flaw number made concrete - the two-wheeler petrol weight,
    # quoted in the caption, against the class-parameter CSV the table is built from.
    ("transport S5 two-wheeler petrol weight", "transport", "S5_classes.tex",
     r"weight is [\d.]+: ([\d.]+)\\% of the petrol control",
     lambda: 100 * _class_weight("2W", "Petrol"), 0.0),
    # The ninth review's find, closed at both ends: the methods prose quoted a
    # weight pair ("0.786 to 0.563") of which the second had NO source and the
    # first was a prior anchoring's value. Both endpoints now recompute from the
    # published class-parameter table - the energy weight directly, the
    # distance-only weight by renormalising the same rows' vehicle-km.
    ("transport methods distance-only endpoint", "transport", "04_methods.tex",
     r"petrol control falls from ([\d.]+) on distance alone",
     lambda: _class_distance_weight("2W", "Petrol"), 0.0),
    ("transport methods energy endpoint", "transport", "04_methods.tex",
     r"on distance alone to ([\d.]+) and the class",
     lambda: _class_weight("2W", "Petrol"), 0.0),
    ("transport S5 distance-only counterpart", "transport", "S5_classes.tex",
     r"On distance alone it\s*would be ([\d.]+),",
     lambda: _class_distance_weight("2W", "Petrol"), 0.0),
    # v1.0.0 Wave 4: tab:categorygas became a stored query printing three-decimal display
    # values, so the two-decimal prose repeats of its cells lost their tier-2 anchor; each
    # is anchored here to the ledger it restates.
    ("gas composition CO2", "national", "06_results.tex",
     r"On AR5 the inventory is \\SI\{([\d.]+)\}\{\\mega\\tonne\} \\COtwo\{\}",
     lambda: _sum_where("national_category_gas.csv", "co2e_Mt_AR5", gas="CO2"), 0.0),
    ("gas composition CH4", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s+methane",
     lambda: _sum_where("national_category_gas.csv", "co2e_Mt_AR5", gas="CH4"), 0.0),
    ("gas composition N2O", "national", "06_results.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of nitrous oxide",
     lambda: _sum_where("national_category_gas.csv", "co2e_Mt_AR5", gas="N2O"), 0.0),
    ("crop calendar wheat fiscal-end agreement", "national", "06_results.tex",
     r"record to within \\SI\{([\d.]+)\}\{\\percent\} one year back",
     lambda: float(next(r for r in _rows_banner("pakemis_agriculture_crop_calendar.csv")
                        if r["crop"] == "wheat" and r["field"] == "production_t")
                   ["mean_abs_pct_at_fiscal_end_year"]), 0.0),
    # rc60: the kharif disagreement RANGE's two ends. Cotton's two rows are empty -
    # it has no fiscal comparison - so the range is over the crops that do carry one.
    # rc60: the kharif disagreement RANGE's two ends. They were covered only by accident - other
    # claims elsewhere in the document happened to print the same integers - and a coincidence is
    # not a check. Both are the floor and ceiling of the kharif crops' own fiscal-end column,
    # rounded to the integer the sentence prints, so a tolerance of half a unit is the right one.
    ("crop calendar kharif disagreement low", "national", "06_results.tex",
     r"disagree by \\SIrange\{(\d+)\}\{\d+\}\{\\percent\}",
     lambda: min(float(r["mean_abs_pct_at_fiscal_end_year"])
                 for r in _rows_banner("pakemis_agriculture_crop_calendar.csv")
                 if r["season"] == "kharif" and r["mean_abs_pct_at_fiscal_end_year"]), 0.5),
    ("crop calendar kharif disagreement high", "national", "06_results.tex",
     r"disagree by \\SIrange\{\d+\}\{(\d+)\}\{\\percent\}",
     lambda: max(float(r["mean_abs_pct_at_fiscal_end_year"])
                 for r in _rows_banner("pakemis_agriculture_crop_calendar.csv")
                 if r["season"] == "kharif" and r["mean_abs_pct_at_fiscal_end_year"]), 0.5),
    # =========================================================================================
    # THE OCTOBER 2026 COMPACT MANUSCRIPT. 134 sites across 30 paragraphs, every one resolved
    # through a product. Where the sectioned corpus already anchors the quantity the claim
    # borrows that claim's getter by label (_as_registered) rather than re-deriving it, so a
    # re-anchoring moves both sites and neither can drift.
    #
    # Four values here LOOK like a value match and are not, and each was adjudicated against
    # the sentence rather than the number:
    #   77     - enteric+manure as a share of agriculture (= the calendar-basis share, since
    #            livestock stocks are the calendar-basis half) AND, in the boundary paragraph,
    #            77 located power stations. Two quantities, one printed value.
    #   0.005  - the managed-soils dry-climate EF1 AND the wastewater effluent N2O factor.
    #   15.85  - the river-MCF wastewater alternative AND the 1A2-vs-EDGAR difference.
    #   17.1   - the full-period growth, NOT the appendix's "share not placed where emitted",
    #            which is the only registered getter that rounds to it.
    # The 95 of "conditional 95 % interval" is NOT registered here: it is the confidence level
    # the interval is taken at, a property of the method, and it lives in MANUSCRIPT_CONSTANTS.
    # =========================================================================================
    ("rewrite abstract grid resolution", "national-v3", "paper.tex",
     r"monthly profiles and a \\SI\{([\d.]+)\}\{\\degree\} grid",
     lambda: _as_registered("contract grid resolution"), 0.0),
    ("rewrite abstract national total", "national-v3", "paper.tex",
     r"estimated categories total \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("national total"), 0.005),
    ("rewrite abstract MC low", "national-v3", "paper.tex",
     r"Monte Carlo interval of \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}\\,CO\$_2\$e, and",
     lambda: _as_registered("MC band low"), 0.005),
    ("rewrite abstract MC high", "national-v3", "paper.tex",
     r"Monte Carlo interval of \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}\\,CO\$_2\$e, and",
     lambda: _as_registered("MC band high"), 0.005),
    # rc67: the roles swapped. The abstract now states the REFERENCE as the survey reading
    # and gives configuration L (all diverted dung) as the alternative; the power
    # alternatives are stated one kind at a time and never as a range.
    ("rewrite abstract ledger total", "national-v3", "paper.tex",
     r"from manure management gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("all_diverted_dung_household_fuel", "national_total_Mt"), 0.005),
    ("rewrite abstract window change", "national-v3", "paper.tex",
     r"the estimate rises by \\SI\{([\d.]+)\}\{\\mega\\tonne\} over the period",
     lambda: _as_registered("uncertainty window change"), 0.005),
    ("rewrite abstract fuel-property total", "national-v3", "paper.tex",
     r"same stations' coal gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("power_plant_physical_coal", "national_total_Mt"), 0.005),
    ("rewrite abstract coverage total", "national-v3", "paper.tex",
     r"is not established, gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("power_with_kelectric", "national_total_Mt"), 0.005),
    ("rewrite abstract legacy total", "national-v3", "paper.tex",
     r"used in earlier releases gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("power_table3_legacy_control", "national_total_Mt"), 0.005),
    ("rewrite abstract flat share", "national-v3", "paper.tex",
     r"records: \\SI\{([\d.]+)\}\{\\percent\} of reference-year emissions use flat",
     lambda: _as_registered("monthly T4 share"), 0.005),
    ("rewrite intro grid resolution", "national-v3", "paper.tex",
     r"administrative areas and a \\SI\{([\d.]+)\}\{\\degree\} grid",
     lambda: _as_registered("contract grid resolution"), 0.0),
    ("rewrite livestock share of agriculture", "national-v3", "paper.tex",
     r"Approximately \\SI\{([\d.]+)\}\{\\percent\} of the reference agricultural",
     lambda: _as_registered("results agriculture calendar share"), 0.5),
    ("rewrite reference EF1", "national-v3", "paper.tex",
     r"dry-climate value of \\num\{([\d.]+)\}~kg N\$_2\$O--N",
     lambda: _reference_ef1(), 0.0),
    # rc67: read from the dung fate product, whose `diverted_Mt` is agriculture's diversion
    # whatever the residential reference is. The claim this used to borrow resolves the
    # engine's DEFAULT dung quantity, which became the survey's when the roles swapped.
    ("rewrite dung ledger mass", "national-v3", "paper.tex",
     r"diversion implies \\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry dung",
     lambda: _dung_fate("FY2023-24", "S_household_only_unallocated", "diverted_Mt"), 0.005),
    ("rewrite dung survey mass", "national-v3", "paper.tex",
     r"household demand is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("dung variants household mass"), 0.005),
    ("rewrite dung unresolved mass", "national-v3", "paper.tex",
     r"approximately\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} with other or unresolved",
     lambda: _as_registered("dung variants unresolved mass"), 0.05),
    ("rewrite spatial grid resolution", "national-v3", "paper.tex",
     r"products use a fixed \\SI\{([\d.]+)\}\{\\degree\} grid",
     lambda: _as_registered("contract grid resolution"), 0.0),
    ("rewrite district frame units", "national-v3", "paper.tex",
     r"a \\num\{(\d+)\}-unit district frame",
     lambda: _as_registered("canonical district frame units"), 0.0),
    ("rewrite MC realizations", "national-v3", "paper.tex",
     r"A \\num\{(\d+)\}-realization Monte Carlo",
     lambda: _mc("within_sector", "TOTAL", "n_iter"), 0.0),
    ("rewrite results national total", "national-v3", "paper.tex",
     r"emissions total \\SI\{([\d.]+)\}\{\\mega\\tonne\}~CO\$_2\$e in 2023--24 under",
     lambda: _as_registered("national total"), 0.005),
    ("rewrite results agriculture", "national-v3", "paper.tex",
     r"agriculture contributes \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("agriculture"), 0.005),
    ("rewrite results power", "national-v3", "paper.tex",
     r"the power module \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("electricity"), 0.005),
    ("rewrite results transport", "national-v3", "paper.tex",
     r", transport \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("road transport"), 0.005),
    ("rewrite results waste", "national-v3", "paper.tex",
     r"and waste \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("waste"), 0.005),
    ("rewrite gas CH4", "national-v3", "paper.tex",
     r"Methane contributes \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("gas composition CH4"), 0.005),
    ("rewrite gas CH4 share", "national-v3", "paper.tex",
     r"CO\$_2\$e, \\SI\{([\d.]+)\}\{\\percent\} of the total;",
     lambda: _as_registered("results methane share"), 0.05),
    ("rewrite gas CO2", "national-v3", "paper.tex",
     r"contribute \\SI\{([\d.]+)\}\{\} and",
     lambda: _as_registered("gas composition CO2"), 0.005),
    ("rewrite gas N2O", "national-v3", "paper.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\}~CO\$_2\$e\. Enteric",
     lambda: _as_registered("gas composition N2O"), 0.005),
    ("rewrite enteric level", "national-v3", "paper.tex",
     r"largest category at \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _keycat("Enteric fermentation", "level_Mt_co2e_AR5"), 0.005),
    ("rewrite enteric share", "national-v3", "paper.tex",
     r", \\SI\{([\d.]+)\}\{\\percent\} of the inventory",
     lambda: _as_registered("keycat enteric level"), 0.05),
    ("rewrite AR6 total", "national-v3", "paper.tex",
     r"AR6 GWPs gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("national AR6 total"), 0.005),
    ("rewrite AR6 difference", "national-v3", "paper.tex",
     r"the \\SI\{([\d.]+)\}\{\\mega\\tonne\} difference is a change of metric",
     lambda: _as_registered("results AR6 difference"), 0.005),
    ("rewrite series first year", "national-v3", "paper.tex",
     r"rises from \\SI\{([\d.]+)\}\{\\mega\\tonne\} in 2015--16",
     lambda: _as_registered("series covered total first year"), 0.005),
    ("rewrite series last year", "national-v3", "paper.tex",
     r"to \\SI\{([\d.]+)\}\{\\mega\\tonne\} in 2023--24 \(Fig",
     lambda: _as_registered("national total"), 0.005),
    ("rewrite series change", "national-v3", "paper.tex",
     r"increase by \\SI\{([\d.]+)\}\{\\mega\\tonne\}~CO\$_2\$e \(",
     lambda: _as_registered("uncertainty window change"), 0.005),
    ("rewrite series change percent", "national-v3", "paper.tex",
     r"~CO\$_2\$e \(\\SI\{([\d.]+)\}\{\\percent\}\) over the study period",
     lambda: _window_change_pct(), 0.05),
    # Re-anchored 2026-10-07: the coal re-base moved the peak from FY2021-22 to FY2020-21
    # by 0.095 Mt, so the sentence names a different year and says the position is not
    # robust. The claim follows the series' own maximum rather than a year literal, which
    # is what it should have done from the start.
    ("rewrite series peak", "national-v3", "paper.tex",
     r"reaches \\SI\{([\d.]+)\}\{\\mega\\tonne\} in 2020--21",
     lambda: _as_registered("series covered total maximum"), 0.005),
    ("rewrite series after peak", "national-v3", "paper.tex",
     r"falls to \\SI\{([\d.]+)\}\{\\mega\\tonne\} in 2022--23",
     lambda: _series_year_min_after_peak(), 0.005),
    # The runner-up, printed because the peak's position turns on it.
    ("rewrite series second peak", "national-v3", "paper.tex",
     r"2021--22 is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _series_year("FY2021-22"), 0.005),
    ("rewrite trend typed low", "national-v3", "paper.tex",
     r"reference setting gives \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _as_registered("longitudinal typed window low"), 0.005),
    ("rewrite trend typed high", "national-v3", "paper.tex",
     r"reference setting gives \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("longitudinal typed window high"), 0.005),
    # Re-anchored 2026-10-07. The two alternatives no longer share one "respectively"
    # sentence, because the time-independent interval now spans zero and saying so needs its
    # own clause. Each regex names its own setting, which is stronger than positional.
    ("rewrite trend correlated low", "national-v3", "paper.tex",
     r"time-correlated setting \\SIrange\{([\d.-]+)\}\{[\d.-]+\}\{\\mega\\tonne\}",
     lambda: _as_registered("longitudinal correlated window low"), 0.005),
    ("rewrite trend correlated high", "national-v3", "paper.tex",
     r"time-correlated setting \\SIrange\{[\d.-]+\}\{([\d.-]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("longitudinal correlated window high"), 0.005),
    ("rewrite trend independent low", "national-v3", "paper.tex",
     r"time-independent setting \\SIrange\{(-?[\d.]+)\}\{[\d.-]+\}\{\\mega\\tonne\}",
     lambda: _as_registered("longitudinal independent window low"), 0.005),
    ("rewrite trend independent high", "national-v3", "paper.tex",
     r"time-independent setting \\SIrange\{-?[\d.]+\}\{([\d.-]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("longitudinal independent window high"), 0.005),
    ("rewrite MC median", "national-v3", "paper.tex",
     r"Monte Carlo median is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("MC median"), 0.005),
    ("rewrite MC low", "national-v3", "paper.tex",
     r"interval of \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} \(Fig",
     lambda: _as_registered("MC band low"), 0.005),
    ("rewrite MC high", "national-v3", "paper.tex",
     r"interval of \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} \(Fig",
     lambda: _as_registered("MC band high"), 0.005),
    ("rewrite MC cross low", "national-v3", "paper.tex",
     r"only slightly, to \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _mc("cross_sector", "TOTAL", "P2.5_Mt"), 0.005),
    ("rewrite MC cross high", "national-v3", "paper.tex",
     r"only slightly, to \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _mc("cross_sector", "TOTAL", "P97.5_Mt"), 0.005),
    ("rewrite monthly T1", "national-v3", "paper.tex",
     r"activity supports\s*\\SI\{([\d.]+)\}\{\\percent\} of reference-year",
     lambda: _as_registered("monthly T1 share"), 0.005),
    ("rewrite monthly T2", "national-v3", "paper.tex",
     r"reconstructed administrative activity \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _as_registered("monthly T2 share"), 0.005),
    ("rewrite monthly T3", "national-v3", "paper.tex",
     r"process profiles \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _as_registered("monthly T3 share"), 0.005),
    ("rewrite monthly T4", "national-v3", "paper.tex",
     r"while \\SI\{([\d.]+)\}\{\\percent\} is flat or",
     lambda: _as_registered("monthly T4 share"), 0.005),
    ("rewrite panel observed share", "national-v3", "paper.tex",
     r"together support\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _as_registered("coverage observed share"), 0.005),
    ("rewrite panel flat share", "national-v3", "paper.tex",
     r"flat share is \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _as_registered("coverage flat share"), 0.005),
    ("rewrite streams placed", "national-v3", "paper.tex",
     r"places \\num\{(\d+)\} of \\num\{\d+\} streams",
     lambda: _as_registered("results gridded streams"), 0.0),
    ("rewrite streams total", "national-v3", "paper.tex",
     r"places \\num\{\d+\} of \\num\{(\d+)\} streams",
     lambda: _streams_total(), 0.0),
    ("rewrite unallocated share", "national-v3", "paper.tex",
     r"approximately \\SI\{([\d.]+)\}\{\\percent\} of the total, remain unallocated",
     lambda: _unallocated_share_pct(), 0.005),
    ("rewrite placed share", "national-v3", "paper.tex",
     r"\(\\SI\{([\d.]+)\}\{\\percent\} of the mass is placed\)",
     lambda: 100.0 - _unallocated_share_pct(), 0.005),
    ("rewrite residential L", "national-v3", "paper.tex",
     r"residential emissions from \\SI\{([\d.]+)\}\{\\mega\\tonne\} to",
     lambda: _as_registered("residential"), 0.005),
    ("rewrite residential S", "national-v3", "paper.tex",
     r"residential emissions from \\SI\{[\d.]+\}\{\\mega\\tonne\} to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("residential total S, results prose"), 0.005),
    ("rewrite config L national", "national-v3", "paper.tex",
     r"the national total from \\SI\{([\d.]+)\}\{\} to",
     lambda: _as_registered("national total"), 0.005),
    ("rewrite config S national", "national-v3", "paper.tex",
     r"the national total from \\SI\{[\d.]+\}\{\} to \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("survey-configuration total in abstract"), 0.005),
    ("rewrite power plant-coal member", "national-v3", "paper.tex",
     r"heat rate and generation gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("power family cv restated"), 0.005),
    # SUPERSEDED 2026-10-07 and removed, not re-anchored. This read "... for the reference
    # control", and the sentence was rewritten because it paired the re-based reference
    # reading with the LEGACY control's national total. Its quantity is now carried by
    # "v2 power reference grid", which derives the reference's booked grid figure from the
    # legacy control's own value less its own delta - the same derivation the configurations
    # product's family_role uses - rather than borrowing a label from the power paper. The
    # claim is not lost; it moved to a getter that cannot disagree with the product.
    ("rewrite power KE member", "national-v3", "paper.tex",
     r"K-Electric gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("power KE ledger scenario"), 0.005),
    # SUPERSEDED 2026-10-07, same rewrite. These anchored on "approximately" and on the
    # sentence's old ending; the rewritten sentence gives four readings each against its own
    # total and says which one is retained-and-not-preferred, so there are now six claims
    # over it ("v2 power ...") resolving through national_configurations.csv by
    # configuration_id. Three loose anchors are removed because their quantities are
    # covered more tightly, which is the only reason a claim may be deleted.
    ("rewrite fugitives envelope floor", "national-v3", "paper.tex",
     r"span \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _as_registered("national fugitives envelope floor"), 0.005),
    # rc67: the envelope's top is the feedstock-inside membership; the reference sits below it
    ("rewrite fugitives envelope top", "national-v3", "paper.tex",
     r"span \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("fugitives_including_feedstock", "alternative_value_Mt"), 0.0005),
    ("rewrite fugitives reference in envelope", "national-v3", "paper.tex",
     r"The reference, \\SI\{([\d.]+)\}\{\\mega\\tonne\}, keeps the higher published",
     lambda: (_configuration("fugitives_including_feedstock", "alternative_value_Mt")
              - _configuration("fugitives_including_feedstock", "national_delta_Mt")), 0.0005),
    ("rewrite ocac exact", "national-v3", "paper.tex",
     r"\\num\{(\d+)\} of \\num\{\d+\} reconstructed monthly values",
     lambda: _as_registered("ocac crosscheck exact"), 0.0),
    ("rewrite ocac comparisons", "national-v3", "paper.tex",
     r"\\num\{\d+\} of \\num\{(\d+)\} reconstructed monthly values",
     lambda: _as_registered("ocac crosscheck comparisons"), 0.0),
    ("rewrite ocac max deviation", "national-v3", "paper.tex",
     r"maximum difference being \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _as_registered("ocac crosscheck max deviation"), 0.005),
    ("rewrite ocac mutation caught", "national-v3", "paper.tex",
     r"displacement is detected in \\num\{(\d+)\} cases",
     lambda: _as_registered("ocac crosscheck mutation caught"), 0.0),
    ("rewrite apcma shape difference", "national-v3", "paper.tex",
     r"mean of \\num\{([\d.]+)\} percentage",
     lambda: _as_registered("apcma shape difference"), 0.005),
    ("rewrite apcma months", "national-v3", "paper.tex",
     r"points of annual activity across \\num\{(\d+)\} months",
     lambda: _apcma_fact("months"), 0.0),
    ("rewrite edgar electricity ratio", "national-v3", "paper.tex",
     r"are \\num\{([\d.]+)\} and \\num\{[\d.]+\} of EDGAR",
     lambda: _bench("EDGAR", "Electricity and heat production"), 0.005),
    ("rewrite edgar residential ratio", "national-v3", "paper.tex",
     r"and \\num\{([\d.]+)\} of EDGAR's calendar-2024",
     lambda: _bench("EDGAR", "Residential fuel combustion"), 0.005),
    ("rewrite 1A2 estimated", "national-v3", "paper.tex",
     r"Industrial combustion is\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("results 1A2 estimated total"), 0.005),
    ("rewrite 1A2 edgar", "national-v3", "paper.tex",
     r"against \\SI\{([\d.]+)\}\{\\mega\\tonne\} in EDGAR",
     lambda: _as_registered("completeness EDGAR 1A2 approx"), 0.005),
    ("rewrite 1A2 difference", "national-v3", "paper.tex",
     r"so the \\SI\{([\d.]+)\}\{\\mega\\tonne\} difference cannot",
     lambda: _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e") - _bench("EDGAR", "1A2 (all estimated)", "engine_Mt_co2e"), 0.005),
    ("rewrite fgas external", "national-v3", "paper.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} EDGAR estimate for fluorinated",
     lambda: _fgas_benchmark(), 0.005),
    ("rewrite rail BUR", "national-v3", "paper.tex",
     r"gives\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}~CO\$_2\$e for FY2017--18",
     lambda: _as_registered("railways BUR figure"), 0.005),
    ("rewrite rail diesel FY2018", "national-v3", "paper.tex",
     r"operator's \\num\{(\d+)\}~thousand litres",
     lambda: _as_registered("railmatched diesel FY2018"), 0.0),
    ("rewrite rail estimate FY2018", "national-v3", "paper.tex",
     r"that year gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("railmatched estimate FY2018"), 0.0005),
    ("rewrite rail ratio", "national-v3", "paper.tex",
     r"a factor\s*of \\num\{([\d.]+)\} lower",
     lambda: _as_registered("railmatched ratio"), 0.05),
    ("rewrite rail diesel FY2024", "national-v3", "paper.tex",
     r"consumption of \\num\{(\d+)\}~thousand litres",
     lambda: _as_registered("railmatched diesel FY2024"), 0.0),
    ("rewrite rail estimate FY2024", "national-v3", "paper.tex",
     r"litres gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}\.",
     lambda: _as_registered("railways"), 0.0005),
    ("rewrite rail diesel year change", "national-v3", "paper.tex",
     r"The\s*\\SI\{(\d+)\}\{\\percent\} change in reported consumption",
     lambda: _as_registered("rail diesel year change, national"), 0.5),
    ("rewrite rail CRT activity", "national-v3", "paper.tex",
     r"\\SI\{(\d+)\}\{\\tera\\joule\} of railway",
     lambda: _as_registered("benchmarks railway crt activity"), 0.5),
    ("rewrite fleet efficiency FY2021", "national-v3", "paper.tex",
     r"efficiencies of \\SI\{([\d.]+)\}\{\\percent\} in 2020--21",
     lambda: _as_registered("uncertainty t3 efficiency high"), 0.05),
    ("rewrite fleet efficiency FY2024", "national-v3", "paper.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} in 2023--24, against",
     lambda: _as_registered("uncertainty t3 efficiency low"), 0.05),
    ("rewrite plant efficiency low", "national-v3", "paper.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\} under the generation-implied",
     lambda: _as_registered("uncertainty plant efficiency low"), 0.05),
    ("rewrite plant efficiency high", "national-v3", "paper.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\} under the generation-implied",
     lambda: _as_registered("uncertainty plant efficiency high"), 0.05),
    # ---- v2: the FY2023-24 coal supply bound, the article's matched-boundary arithmetic ----
    # Every one of these reads the product that owns it. The paragraph they protect was added
    # because the detailed methods forward-referenced "the physical audit reported in the main
    # article" and the article reported only the efficiency half of it.
    ("v2 coal bound required", "national-v3", "paper.tex",
     r"requires \\SI\{([\d.]+)\}\{\\mega\\tonne\} of coal against",
     lambda: _supply_bound_kt("required") / 1000.0, 0.01),
    ("v2 coal bound supplied", "national-v3", "paper.tex",
     r"against the \\SI\{([\d.]+)\}\{\\mega\\tonne\} the national accounts report",
     lambda: _supply_bound_kt("supplied") / 1000.0, 0.01),
    ("v2 coal bound ratio", "national-v3", "paper.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the supply before",
     lambda: _reference_audit("B1_the_bound", "FY2023-24"), 0.05),
    ("v2 coal station account", "national-v3", "paper.tex",
     r"reference requires \\SI\{([\d.]+)\}\{\\mega\\tonne\} in the same year",
     lambda: _station_coal_kt() / 1000.0, 0.01),
    ("v2 coal station share of supply", "national-v3", "paper.tex",
     r"\\SI\{(\d+)\}\{\\percent\} of the supply and below",
     lambda: 100.0 * _station_coal_kt() / _supply_bound_kt("supplied"), 0.5),
    ("v2 coal yearbook power booking", "national-v3", "paper.tex",
     r"below the \\SI\{([\d.]+)\}\{\\mega\\tonne\} the energy yearbook assigns",
     lambda: _yearbook_coal_kt() / 1000.0, 0.01),
    ("rewrite soils pakemis", "national-v3", "paper.tex",
     r"Managed soils contribute \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("benchmarks fao soils main"), 0.005),
    ("rewrite soils faostat", "national-v3", "paper.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} in FAOSTAT",
     lambda: _bench("FAOSTAT", "Managed soils", "benchmark_Mt_co2e"), 0.005),
    ("rewrite fert agreement", "national-v3", "paper.tex",
     r"agree within \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _as_registered("benchmarks fao fert agreement"), 0.05),
    ("rewrite pasture pakemis", "national-v3", "paper.tex",
     r"Pasture deposition contributes \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("benchmarks fao pasture pakemis"), 0.005),
    ("rewrite pasture faostat", "national-v3", "paper.tex",
     r"here against \\SI\{([\d.]+)\}\{\\mega\\tonne\} in FAOSTAT",
     lambda: _as_registered("benchmarks fao pasture faostat"), 0.005),
    ("rewrite pasture share", "national-v3", "paper.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of the overall difference",
     lambda: _as_registered("benchmarks fao pasture share"), 0.05),
    ("rewrite substitution reference EF1", "national-v3", "paper.tex",
     r"reference dry-climate EF\$_1\$ of \\num\{([\d.]+)\}",
     lambda: _reference_ef1(), 0.0),
    ("rewrite substitution 2006 EF1", "national-v3", "paper.tex",
     r"2006 aggregate value of \\num\{([\d.]+)\}",
     lambda: _as_registered("benchmarks fao ef1 2006"), 0.0),
    ("rewrite soils ef2006", "national-v3", "paper.tex",
     r"raises managed soils to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("benchmarks fao soils ef2006"), 0.005),
    ("rewrite soils both", "national-v3", "paper.tex",
     r"raises it to\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("benchmarks fao both soils"), 0.005),
    ("rewrite soils both closed", "national-v3", "paper.tex",
     r"substitutions account for \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("benchmarks fao both closed"), 0.005),
    ("rewrite soils both pct", "national-v3", "paper.tex",
     r"approximately\s*\\SI\{(\d+)\}\{\\percent\} of the \\SI",
     lambda: _as_registered("benchmarks fao both pct"), 0.5),
    ("rewrite soils gap total", "national-v3", "paper.tex",
     r"of the \\SI\{([\d.]+)\}\{\\mega\\tonne\} difference, and the remaining",
     lambda: _as_registered("benchmarks fao gap total"), 0.005),
    ("rewrite soils both remaining", "national-v3", "paper.tex",
     r"the remaining \\SI\{([\d.]+)\}\{\\mega\\tonne\} lies",
     lambda: _as_registered("benchmarks fao both remaining"), 0.005),
    ("rewrite so2 national ratio", "national-v3", "paper.tex",
     r"PakEmis-to-EDGAR ratio is \\num\{([\d.]+)\}",
     lambda: _as_registered("provincial so2 national ratio"), 0.005),
    ("rewrite so2 punjab", "national-v3", "paper.tex",
     r"provincial ratios are \\num\{([\d.]+)\} in Punjab",
     lambda: _as_registered("provincial so2 punjab"), 0.005),
    ("rewrite so2 kp", "national-v3", "paper.tex",
     r"\\num\{([\d.]+)\} in Khyber Pakhtunkhwa",
     lambda: _as_registered("provincial so2 kp"), 0.005),
    ("rewrite so2 balochistan", "national-v3", "paper.tex",
     r"\\num\{([\d.]+)\} in Balochistan",
     lambda: _as_registered("provincial so2 balochistan"), 0.005),
    ("rewrite so2 sindh", "national-v3", "paper.tex",
     r"\\num\{([\d.]+)\} in Sindh \(\\texttt",
     lambda: _as_registered("provincial so2 sindh"), 0.005),
    ("rewrite so2 power engine", "national-v3", "paper.tex",
     r"power layer gives\s*\\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _as_registered("provincial so2 power engine"), 0.05),
    ("rewrite so2 power edgar", "national-v3", "paper.tex",
     r"against EDGAR's \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _as_registered("provincial so2 power edgar"), 0.05),
    ("rewrite so2 power sindh engine", "national-v3", "paper.tex",
     r"including \\SI\{([\d.]+)\}\{\} against",
     lambda: _as_registered("provincial so2 power sindh engine"), 0.05),
    ("rewrite so2 power sindh edgar", "national-v3", "paper.tex",
     r"against\s*\\SI\{([\d.]+)\}\{\\giga\\gram\} in Sindh",
     lambda: _as_registered("provincial so2 power sindh edgar"), 0.05),
    ("rewrite so2 bracket low", "national-v3", "paper.tex",
     r"gives \\SI\{([\d.]+)\}\{\\giga\\gram\} under the controlled case",
     lambda: _as_registered("provincial so2 bracket low"), 0.05),
    ("rewrite so2 bracket high", "national-v3", "paper.tex",
     r"and \\SI\{([\d.]+)\}\{\\giga\\gram\} under the uncontrolled case",
     lambda: _prov_so2("FY2021-22", "power_decomposition", "pakistan", "engine_Gg") + _power_so2_screen("FY2021-22", "uncontrolled"), 0.05),
    # The corrected direction of the EDGAR comparison. The previous text said EDGAR "lies near
    # the upper endpoint" of the screening range; it lies ABOVE it, and both the margin and the
    # percentage are derived here from the same two quantities the sentence prints, so the
    # three numbers cannot drift apart.
    ("v2 so2 edgar exceeds endpoint", "national-v3", "paper.tex",
     r"exceeding its uncontrolled endpoint by \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _prov_so2("FY2021-22", "power_decomposition", "pakistan", "edgar_Gg")
             - (_prov_so2("FY2021-22", "power_decomposition", "pakistan", "engine_Gg")
                + _power_so2_screen("FY2021-22", "uncontrolled")), 0.1),
    ("v2 so2 edgar exceeds endpoint pct", "national-v3", "paper.tex",
     r"uncontrolled endpoint by \\SI\{[\d.]+\}\{\\giga\\gram\} \(\\SI\{(\d+)\}\{\\percent\}\)",
     lambda: 100.0 * (_prov_so2("FY2021-22", "power_decomposition", "pakistan", "edgar_Gg")
                      - (_prov_so2("FY2021-22", "power_decomposition", "pakistan", "engine_Gg")
                         + _power_so2_screen("FY2021-22", "uncontrolled")))
             / (_prov_so2("FY2021-22", "power_decomposition", "pakistan", "engine_Gg")
                + _power_so2_screen("FY2021-22", "uncontrolled")), 0.5),
    # The benchmark paragraph's illustrative ratio, registered IN PLACE rather than left as
    # a repeat of the main article's copy: the sentence's whole point is that this particular
    # number means less than it looks like, so it had better be this number.
    ("v2 benchmark illustrative ratio", "national-v3", "technical_supplement.tex",
     r"a number like a \\num\{([\d.]+)\} national ratio",
     lambda: _as_registered("provincial so2 national ratio"), 0.005),
    # ---- v2: the four deferred source questions, ranked by what they would move --------
    # Every ratio resolves through the BTR comparison by SUBJECT, so the paragraph that ranks
    # the open items cannot drift from the comparison it ranks them by. The managed-soils
    # scenario values beside them are already registered against the figure's own data.
    ("v2 open item enteric ratio", "national-v3", "paper.tex",
     r"it is \\num\{([\d.]+)\} times the submitted value",
     lambda: _btr("Enteric fermentation"), 0.005),
    ("v2 open item manure ratio", "national-v3", "paper.tex",
     r"from the same herd is \\num\{([\d.]+)\} times",
     lambda: _btr("Manure management (CH4 and direct N2O)"), 0.005),
    ("v2 open item residue ratio", "national-v3", "paper.tex",
     r"Crop residues are \\num\{([\d.]+)\} of the submission",
     lambda: _btr("Residue burning, against the submission's cropland non-CO2"), 0.005),
    ("v2 open item waste disposal ratio", "national-v3", "paper.tex",
     r"disposal is \\num\{([\d.]+)\} of the submitted figure",
     lambda: _btr("Solid waste disposal"), 0.005),
    ("v2 open item waste fate ratio", "national-v3", "paper.tex",
     r"the broader fate account\s*\n?\s*\\num\{([\d.]+)\}",
     lambda: _btr("Solid-waste fate (disposal + burning)"), 0.005),
    # ---- v2: the dung balance as an assignment question (item 6) ------------------------
    ("v2 dung implied household share", "national-v3", "technical_supplement.tex",
     r"about \\SI\{([\d.]+)\}\{\\percent\} of weighted households would have to burn",
     lambda: _dung_falsifiable("implied_share"), 0.05),
    ("v2 dung observed household share", "national-v3", "technical_supplement.tex",
     r"against the \\SI\{([\d.]+)\}\{\\percent\} the survey records",
     lambda: _dung_falsifiable("observed_share"), 0.005),
    ("v2 dung intensity factor", "national-v3", "technical_supplement.tex",
     r"have to burn \\num\{([\d.]+)\} times the observed daily",
     lambda: _dung_falsifiable("intensity_factor"), 0.05),
    ("v2 dung survey round move", "national-v3", "technical_supplement.tex",
     r"an\s*\n?\s*\\SI\{(\d+)\}\{\\percent\} change larger than the parameter",
     lambda: float(_dung_balance("Survey round stability").split("(+")[1].split(" pct")[0]),
     0.5),
    # ---- v2: the gas deduction's boundary and the base's membership (item 6) ------------
    ("v2 gas delivered streams", "national-v3", "technical_supplement.tex",
     r"Of \\num\{(\d+)\} delivered streams",
     lambda: _gas_closure("streams"), 0.0),
    ("v2 gas delivered volume", "national-v3", "technical_supplement.tex",
     r"delivered streams totalling\s*\n?\s*\\SI\{(\d+)\}\{\} million",
     lambda: _gas_closure("total_volume"), 1.0),
    ("v2 gas base streams", "national-v3", "technical_supplement.tex",
     r"million~m\$\^3\$, \\num\{(\d+)\} carrying",
     lambda: _gas_closure("inside_streams"), 0.0),
    ("v2 gas base volume", "national-v3", "technical_supplement.tex",
     r"\\num\{\d+\} carrying \\SI\{(\d+)\}\{\} million",
     lambda: _gas_closure("inside_volume"), 1.0),
    ("v2 gas base pct", "national-v3", "technical_supplement.tex",
     r"\(\\SI\{([\d.]+)\}\{\\percent\}\) are inside the post-meter base",
     lambda: _gas_closure("inside_pct"), 0.05),
    ("v2 gas outside streams", "national-v3", "technical_supplement.tex",
     r"and \\num\{(\d+)\} carrying",
     lambda: _gas_closure("outside_streams"), 0.0),
    ("v2 gas outside volume", "national-v3", "technical_supplement.tex",
     r"\\num\{\d+\} carrying\s*\n?\s*\\SI\{(\d+)\}\{\} million~m\$\^3\$ are outside",
     lambda: _gas_closure("outside_volume"), 1.0),
    # ---- v2: the paddy crosscheck's RESULT (item 5) -------------------------------------
    ("v2 rice crosscheck agree", "national-v3", "technical_supplement.tex",
     r"provincial rice mass, the two surfaces agree in \\num\{(\d+)\}",
     lambda: _rice_crosscheck(verdict="agree"), 0.0),
    ("v2 rice crosscheck disagree", "national-v3", "technical_supplement.tex",
     r"and disagree in \\num\{(\d+)\}",
     lambda: _rice_crosscheck(verdict="disagree"), 0.0),
    ("v2 rice crosscheck punjab", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} in Punjab,",
     lambda: _rice_crosscheck(province="Punjab"), 0.05),
    ("v2 rice crosscheck sindh", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} in Sindh, \\SI",
     lambda: _rice_crosscheck(province="Sindh"), 0.05),
    ("v2 rice crosscheck kp", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} in Khyber Pakhtunkhwa,",
     lambda: _rice_crosscheck(province="Khyber Pakhtunkhwa"), 0.05),
    ("v2 rice crosscheck balochistan", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} in Balochistan and",
     lambda: _rice_crosscheck(province="Balochistan"), 0.05),
    ("v2 rice crosscheck other", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} in the residual",
     lambda: _rice_crosscheck(province="Other"), 0.05),
    ("v2 rice crosscheck units", "national-v3", "technical_supplement.tex",
     r"Coverage is \\num\{(\d+)\} of the canonical",
     lambda: _rice_crosscheck(verdict="agree") + _rice_crosscheck(verdict="disagree"), 0.0),
    ("v2 rice crosscheck canonical", "national-v3", "technical_supplement.tex",
     r"of the canonical \\num\{(\d+)\} ADM2",
     lambda: float(len(read_rows(os.path.join(paths.DATA, "adm2_canonical.csv")))), 0.0),
    # The two GWP values the caption prints come from the engine's own table, not from a
    # whitelist. They look like constants and are not: if core/gwp.py were ever re-based, a
    # caption stating 30 beside an engine applying something else is precisely the class of
    # defect this round exists to remove.
    ("v2 ch4 fossil gwp", "national-v3", "paper.tex",
     r"fossil CH\$_4\$ at AR5's \\num\{(\d+)\}",
     lambda: _gwp_ar5("CH4_fossil"), 0.0),
    ("v2 ch4 biogenic gwp", "national-v3", "paper.tex",
     r"biogenic CH\$_4\$ at \\num\{(\d+)\}",
     lambda: _gwp_ar5("CH4"), 0.0),
    ("v2 ch4 uniform gwp", "national-v3", "paper.tex",
     r"at a uniform \\num\{(\d+)\}, under which",
     lambda: _gwp_ar5("CH4"), 0.0),
    # ---- v2: the CH4 convention the comparison does NOT match (item 3) ------------------
    # The caption used to say the comparison "needs no harmonisation". It needs no calendar
    # blend and no GWP-FAMILY conversion, but this inventory weights fossil CH4 at 30 and the
    # BTR's own weighting is not recoverable from its published table. All four numbers below
    # come from the two columns the product now carries, so the caption cannot drift from the
    # comparison it describes.
    ("v2 btr fugitives ratio published", "national-v3", "paper.tex",
     r"oil and gas fugitives \(\\num\{([\d.]+)\}\)",
     lambda: _btr("Oil and natural gas fugitives"), 0.005),
    ("v2 btr fugitives ratio harmonised", "national-v3", "paper.tex",
     r"fugitives ratio becomes \\num\{([\d.]+)\}",
     lambda: _btr("Oil and natural gas fugitives", "ratio_ch4_uniform_28"), 0.005),
    ("v2 btr national ratio published", "national-v3", "paper.tex",
     r"excluding LULUCF is \\num\{([\d.]+)\}",
     lambda: _btr("TOTAL (excluding LULUCF)"), 0.0005),
    ("v2 btr national ratio harmonised", "national-v3", "paper.tex",
     r"the national ratio \\num\{([\d.]+)\}\.",
     lambda: _btr("TOTAL (excluding LULUCF)", "ratio_ch4_uniform_28"), 0.0005),
    ("rewrite boundary stations", "national-v3", "paper.tex",
     r"audit of \\num\{(\d+)\} located power stations",
     lambda: _boundary_audit("stations"), 0.0),
    ("rewrite boundary max km", "national-v3", "paper.tex",
     r"within\s*\\SI\{([\d.]+)\}\{\\kilo\\metre\} of a district boundary",
     lambda: _boundary_audit("max_km"), 0.05),
    ("rewrite boundary exposure low", "national-v3", "paper.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\} of plant-ledger",
     lambda: _as_registered("boundary audit exposure low"), 0.05),
    ("rewrite boundary exposure high", "national-v3", "paper.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\} of plant-ledger",
     lambda: _as_registered("boundary audit exposure high"), 0.05),
    ("rewrite table annual grid resolution", "national-v3", "paper.tex",
     r"Nine fiscal years, \\SI\{([\d.]+)\}\{\\degree\}",
     lambda: _as_registered("contract grid resolution"), 0.0),
    ("rewrite table monthly grid resolution", "national-v3", "paper.tex",
     r"Monthly grid & 2023--24, \\SI\{([\d.]+)\}\{\\degree\}",
     lambda: _as_registered("contract grid resolution"), 0.0),
    ("rewrite enteric variance", "national-v3", "paper.tex",
     r"accounts for \\SI\{([\d.]+)\}\{\\percent\} of variance",
     lambda: _as_registered("keycat enteric variance"), 0.05),
    ("rewrite wastewater variance", "national-v3", "paper.tex",
     r"domestic wastewater for \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _as_registered("keycat wastewater variance"), 0.05),
    ("rewrite conclusion total", "national-v3", "paper.tex",
     r"reference-year total is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("national total"), 0.005),
    ("rewrite conclusion MC low", "national-v3", "paper.tex",
     r"parameter interval of \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _as_registered("MC band low"), 0.005),
    ("rewrite conclusion MC high", "national-v3", "paper.tex",
     r"parameter interval of \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _as_registered("MC band high"), 0.005),
    ("rewrite conclusion change", "national-v3", "paper.tex",
     r"estimated increase of\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} over the study period excludes",
     lambda: _as_registered("uncertainty window change"), 0.005),
    # The exceedance probability stated as the ESTIMATE it is (item 4). Both bounds come
    # from the diagnostic's own Clopper-Pearson rows, so the interval in the prose cannot
    # drift from the one the product computes.
    # THE TWO BREAKDOWNS THAT MUST PARTITION THEIR REGISTER (v2, 2026-10-08, the 23rd
    # review's item 1). The reviewer summed both and found them short - the spatial classes
    # by 29, the validation classes by 2 - and both shortfalls were real. The spatial prose
    # named five of six `spatial_time_basis` values; the validation prose switched COLUMNS
    # mid-paragraph, mixing independence_class with calibration_or_validation, which
    # double-counted the 3 calibrations already inside partial and large while omitting the
    # classes it never named. Every term is now registered against the column it comes from,
    # so a class added to either register fails the suite instead of a reviewer's addition.
    ("v2 spatial class not present", "national-v3", "technical_supplement.tex",
     r"and \\num\{(\d+)\} carry no mass at all in their period",
     lambda: float(_weights_basis("not_present")), 0.0),
    ("v2 spatial classes total", "national-v3", "technical_supplement.tex",
     r"account for all \\num\{(\d+)\} rows",
     lambda: float(_weights_basis()), 0.0),
    ("v2 register not applicable", "national-v3", "technical_supplement.tex",
     r"\\num\{(\d+)\} have no applicable comparator",
     lambda: _catalog_count("independence_class", "not-applicable"), 0.0),
    ("v2 register none", "national-v3", "technical_supplement.tex",
     r"comparator, and \\num\{(\d+)\} have none",
     lambda: _catalog_count("independence_class", "none"), 0.0),
    ("v2 register validations", "national-v3", "technical_supplement.tex",
     r"partitions the same \\num\{\d+\}: \\num\{(\d+)\} validations",
     lambda: _catalog_count("calibration_or_validation", "validation"), 0.0),
    ("v2 register corroborations", "national-v3", "technical_supplement.tex",
     r"validations, \\num\{(\d+)\} corroborations",
     lambda: _catalog_count("calibration_or_validation", "corroboration"), 0.0),
    ("v2 register overlap calibrations", "national-v3", "technical_supplement.tex",
     r"double-count the \\num\{(\d+)\} calibrations that sit inside",
     lambda: float(_calibrations_inside_partial_or_large()), 0.0),
    # THE FIGURE CAPTIONS' OWN QUANTITIES (v2, 2026-10-07). Rewriting Figures 1, 3 and 4
    # for the review put numbers into captions and into the boundary paragraph, and a
    # caption is prose the sweep reads like any other. Each resolves against the product
    # the figure itself is drawn from, so a caption cannot drift from its own panel.
    ("v2 interval width", "national-v3", "paper.tex",
     r"at the upper, on a width of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _mc_interval_width(), 0.5),
    # rc67: the caption's four endpoints, its two movements and the Approach 1 share were
    # protected only as repeats of body values. When the body moved they stayed, and the
    # caption printed the previous release's interval beside a rebuilt figure.
    ("v3 caption interval low, within module", "national-v3", "paper.tex",
     r"moves the interval from \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} to",
     lambda: _mc("within_sector", "TOTAL", "P2.5_Mt"), 0.005),
    ("v3 caption interval high, within module", "national-v3", "paper.tex",
     r"moves the interval from \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} to",
     lambda: _mc("within_sector", "TOTAL", "P97.5_Mt"), 0.005),
    ("v3 caption interval low, across modules", "national-v3", "paper.tex",
     r"\\mega\\tonne\} to \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}: ",
     lambda: _mc("cross_sector", "TOTAL", "P2.5_Mt"), 0.005),
    ("v3 caption interval high, across modules", "national-v3", "paper.tex",
     r"\\mega\\tonne\} to \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}: ",
     lambda: _mc("cross_sector", "TOTAL", "P97.5_Mt"), 0.005),
    ("v3 caption lower endpoint movement", "national-v3", "paper.tex",
     r"\\SI\{(-[\d.]+)\}\{\\mega\\tonne\} at the lower endpoint",
     lambda: (_mc("cross_sector", "TOTAL", "P2.5_Mt")
              - _mc("within_sector", "TOTAL", "P2.5_Mt")), 0.005),
    ("v3 caption upper endpoint movement", "national-v3", "paper.tex",
     r"\\SI\{\+([\d.]+)\}\{\\mega\\tonne\} at the upper",
     lambda: (_mc("cross_sector", "TOTAL", "P97.5_Mt")
              - _mc("within_sector", "TOTAL", "P97.5_Mt")), 0.005),
    ("v3 enteric share of the Approach 1 screen", "national-v3", "paper.tex",
     r"enteric fermentation is \\SI\{([\d.]+)\}\{\\percent\} of the Approach~1 variance screen",
     lambda: _keycat("Enteric fermentation", "variance_share_pct_independent_approx"), 0.05),
    ("v2 district rebase gross low", "national-v3", "paper.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\s*\{\\mega\\tonne\} of gross mass",
     lambda: _rebase_gross()[0], 0.05),
    ("v2 district rebase gross high", "national-v3", "paper.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\s*\{\\mega\\tonne\} of gross mass",
     lambda: _rebase_gross()[1], 0.05),
    # THE POWER CONTROL FAMILY'S FOUR READINGS (v2, 2026-10-07). This sentence had the
    # reference's power figure beside the LEGACY control's national total - 40.04 against
    # 469.64 - while printing the correct 451.86 two sentences earlier. Every figure now
    # resolves through outputs/national_configurations.csv, so the family cannot be
    # re-based again with one of its members left behind.
    ("v2 power plant physical", "national-v3", "paper.tex",
     r"heat rate and generation gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("power_plant_physical_coal", "alternative_value_Mt"), 0.005),
    ("v2 power reference grid", "national-v3", "paper.tex",
     r"gives \\SI\{([\d.]+)\}\{\\mega\\tonne\} for public power",
     lambda: _reference_grid(), 0.005),
    ("v2 power legacy grid", "national-v3", "paper.tex",
     r"earlier releases used, gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("power_table3_legacy_control", "alternative_value_Mt"), 0.005),
    # rc67: each total is named for its KIND (fuel property, coverage, previously published
    # account) and the reference is printed beside them; they are not a range.
    ("v2 power total plant physical", "national-v3", "paper.tex",
     r"national totals are\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} for the fuel-property",
     lambda: _configuration("power_plant_physical_coal", "national_total_Mt"), 0.005),
    ("v2 power total kelectric", "national-v3", "paper.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} with K-Electric and",
     lambda: _configuration("power_with_kelectric", "national_total_Mt"), 0.005),
    ("v2 power total legacy", "national-v3", "paper.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\} for the previously published account, against",
     lambda: _configuration("power_table3_legacy_control", "national_total_Mt"), 0.005),
    ("v3 power total reference", "national-v3", "paper.tex",
     r"account, against \\SI\{([\d.]+)\}\{\\mega\\tonne\} for the reference",
     lambda: _configuration("inventory_reference", "national_total_Mt"), 0.005),
    # ---- rc67: the supplement's rewritten gas, dung, wastewater and driver paragraphs -------
    ("v3 supp feedstock share of the fertiliser class", "national-v3", "technical_supplement.tex",
     r"puts \\SI\{([\d.]+)\}\{\\percent\} of that class in feedstock",
     lambda: 100.0 * (_gas_crosswalk("Fertiliser: feedstock", "million_m3")
                      / _gas_crosswalk("MEMO: fertiliser class (feed + process fuel)",
                                       "million_m3")), 0.05),
    ("v3 supp feedstock volume", "national-v3", "technical_supplement.tex",
     r"The feedstock, \\SI\{(\d+)\}\{\} million",
     lambda: _gas_crosswalk("Fertiliser: feedstock", "million_m3"), 1.0),
    ("v3 supp feedstock share of the former base", "national-v3", "technical_supplement.tex",
     r"was \\SI\{([\d.]+)\}\{\\percent\} of the base as it stood before",
     lambda: 100.0 * _gas_crosswalk("Fertiliser: feedstock", "million_m3")
     / (_gas_closure("inside_volume")
        + _gas_crosswalk("Fertiliser: feedstock", "million_m3")), 0.05),
    ("v3 supp feedstock correction", "national-v3", "technical_supplement.tex",
     r"lowers the fugitive estimate by \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("fugitives_including_feedstock", "national_delta_Mt"), 0.0005),
    ("v3 supp fertiliser gas carbon low", "national-v3", "technical_supplement.tex",
     r"delivered gas is \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _gas_crosswalk("MEMO: fertiliser class (feed + process fuel)",
                            "gas_carbon_potential_Mt_CO2_low"), 0.05),
    ("v3 supp fertiliser gas carbon high", "national-v3", "technical_supplement.tex",
     r"delivered gas is \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _gas_crosswalk("MEMO: fertiliser class (feed + process fuel)",
                            "gas_carbon_potential_Mt_CO2_high"), 0.05),
    ("v3 supp fertiliser carbon booked", "national-v3", "technical_supplement.tex",
     r"against \\SI\{([\d.]+)\}\{\\mega\\tonne\} booked on ammonia production",
     lambda: _gas_crosswalk("MEMO: fertiliser class (feed + process fuel)",
                            "carbon_booked_Mt_CO2"), 0.005),
    ("v3 supp household dung, reference", "national-v3", "technical_supplement.tex",
     r"takes \\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry cake",
     lambda: _dung_fate("FY2023-24", "S_household_only_unallocated", "household_Mt"), 0.005),
    ("v3 supp dung per household ratio between rounds", "national-v3", "technical_supplement.tex",
     r"differs by a factor of \\num\{([\d.]+)\}",
     lambda: _hies_dung_rate_ratio(), 0.005),
    ("v3 supp dung top five per cent, later round", "national-v3", "technical_supplement.tex",
     r"hold \\SI\{([\d.]+)\}\{\\percent\} of the reported total",
     lambda: _hies_concentration("hies2025"), 0.05),
    ("v3 supp dung top five per cent, earlier round", "national-v3", "technical_supplement.tex",
     r"against \\SI\{([\d.]+)\}\{\\percent\} in 2018--19",
     lambda: _hies_concentration("hies2019"), 0.05),
    ("v3 supp dung survey activity uncertainty", "national-v3", "technical_supplement.tex",
     r"uncertainty of \\SI\{(\d+)\}\{\\percent\} under the reference",
     lambda: _data_param("residential_params.csv", "activity_uncert_dung_survey", "value"),
     0.0),
    ("v3 supp residential at the earlier round's rate", "national-v3", "technical_supplement.tex",
     r"residential total of \\SI\{([\d.]+)\}\{\\mega\\tonne\} and the later round",
     lambda: _residential_scenario("dung_survey_rate_2018_19"), 0.005),
    ("v3 supp residential at the later round as measured", "national-v3", "technical_supplement.tex",
     r"later round as measured gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _residential_scenario("dung_survey_round_2024_25_as_measured"), 0.005),
    ("v3 supp residential reference", "national-v3", "technical_supplement.tex",
     r"against \\SI\{([\d.]+)\}\{\\mega\\tonne\} for the reference\. Both",
     lambda: _residential_scenario("reference"), 0.005),
    ("v3 supp unresolved dung mass", "national-v3", "technical_supplement.tex",
     r"unresolved term is \\SI\{([\d.]+)\}\{\\mega\\tonne\} of air-dry cake",
     lambda: _dung_fate("FY2023-24", "S_household_only_unallocated", "unresolved_Mt"), 0.005),
    ("v3 supp unresolved dung nitrogen", "national-v3", "technical_supplement.tex",
     r"holding \\SI\{(\d+)\}\{\\kilo\\tonne\} of nitrogen",
     lambda: _dung_fate("FY2023-24", "S_household_only_unallocated", "unresolved_N_kt"),
     0.5),
    ("v3 supp dung burned elsewhere", "national-v3", "technical_supplement.tex",
     r"configuration L \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\\,CO\$_2\$e above the reference",
     lambda: _dung_fate("FY2023-24", "S_residual_nonhousehold_combustion",
                        "delta_Mt_co2e_AR5"), 0.005),
    ("v3 supp dung returned to manure", "national-v3", "technical_supplement.tex",
     r"never having left manure management \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _dung_fate("FY2023-24", "S_residual_return_to_manure",
                        "delta_Mt_co2e_AR5"), 0.005),
    ("v3 supp dung applied to fields", "national-v3", "technical_supplement.tex",
     r"applied to fields \(\\SI\{([\d.]+)\}\{\\mega\\tonne\}\)",
     lambda: _dung_fate("FY2023-24", "S_residual_field_application",
                        "delta_Mt_co2e_AR5"), 0.005),
    ("v3 supp wastewater N2O refinement", "national-v3", "technical_supplement.tex",
     r"this gives \\SI\{([\d.]+)\}\{\\giga\\gram\}~N\$_2\$O",
     lambda: _wastewater_method("wastewater_n2o", "ipcc2019", "deterministic"), 0.005),
    ("v3 supp wastewater N2O 2006 equation", "national-v3", "technical_supplement.tex",
     r"it gives \\SI\{([\d.]+)\}\{\\giga\\gram\}, and the difference",
     lambda: _wastewater_method("wastewater_n2o", "ipcc2006", "deterministic"), 0.005),
    ("v3 supp wastewater method difference", "national-v3", "technical_supplement.tex",
     r"and the difference is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (_wastewater_method("wastewater_category", "ipcc2006", "deterministic")
              - _wastewater_method("wastewater_category", "ipcc2019", "deterministic")),
     0.005),
    ("v3 supp waste total, reference", "national-v3", "technical_supplement.tex",
     r"against a waste total of \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _waste_scenario("reference"), 0.005),
    ("v3 supp treated share of sewered flow", "national-v3", "technical_supplement.tex",
     r"sewered wastewater is set at \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100.0 * _data_param("waste_params.csv", "ww_treated_share", "value"), 0.0),
    ("v3 supp waste total, treated share doubled", "national-v3", "technical_supplement.tex",
     r"doubling it gives \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _waste_scenario("treated_share_high"), 0.005),
    ("v3 supp waste total, decentralised effluent to soil", "national-v3", "technical_supplement.tex",
     r"counted as effluent the total is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _waste_scenario("decentralised_effluent_to_soil"), 0.005),
    ("v3 supp nutrient-impacted factor", "national-v3", "technical_supplement.tex",
     r"nutrient-impacted waters \(\\num\{([\d.]+)\}\)",
     lambda: _data_param("waste_params.csv", "ww_ef_effluent_nutrient", "value"), 0.0),
    ("v3 supp waste total, nutrient-impacted", "national-v3", "technical_supplement.tex",
     r"\(\\num\{[\d.]+\}\) the total is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _waste_scenario("effluent_nutrient_impacted"), 0.005),
    ("v3 supp driver enteric", "national-v3", "technical_supplement.tex",
     r"Enteric fermentation carries \\SI\{([\d.]+)\}\{\\percent\} of the variance",
     lambda: 100.0 * _uncertainty_driver("category", "Enteric fermentation",
                                         "variance_share"), 0.05),
    ("v3 supp driver managed soils", "national-v3", "technical_supplement.tex",
     r"managed soils \\SI\{([\d.]+)\}\{\\percent\}, domestic",
     lambda: 100.0 * _uncertainty_driver("category", "Managed soils",
                                         "variance_share"), 0.05),
    ("v3 supp driver wastewater", "national-v3", "technical_supplement.tex",
     r"domestic wastewater \\SI\{([\d.]+)\}\{\\percent\}, manure",
     lambda: 100.0 * _uncertainty_driver("category", "Domestic wastewater",
                                         "variance_share"), 0.05),
    ("v3 supp driver manure", "national-v3", "technical_supplement.tex",
     r"manure management \\SI\{([\d.]+)\}\{\\percent\} and rice",
     lambda: 100.0 * _uncertainty_driver("category", "Manure management",
                                         "variance_share"), 0.05),
    ("v3 supp driver rice", "national-v3", "technical_supplement.tex",
     r"rice cultivation \\SI\{([\d.]+)\}\{\\percent\}\. By sector",
     lambda: 100.0 * _uncertainty_driver("category", "Rice cultivation",
                                         "variance_share"), 0.05),
    ("v3 supp driver agriculture", "national-v3", "technical_supplement.tex",
     r"agriculture carries \\SI\{([\d.]+)\}\{\\percent\} and waste",
     lambda: 100.0 * _uncertainty_driver("sector", "agriculture", "variance_share"), 0.05),
    ("v3 supp driver waste", "national-v3", "technical_supplement.tex",
     r"and waste \\SI\{([\d.]+)\}\{\\percent\}\. The same table",
     lambda: 100.0 * _uncertainty_driver("sector", "waste", "variance_share"), 0.05),
    ("v3 supp upper tail enteric", "national-v3", "technical_supplement.tex",
     r"which is \\SI\{([\d.]+)\}\{\\percent\} for enteric fermentation",
     lambda: 100.0 * _uncertainty_driver("category", "Enteric fermentation",
                                         "upper_tail_excess_share"), 0.05),
    ("v3 supp upper tail wastewater", "national-v3", "technical_supplement.tex",
     r"and \\SI\{([\d.]+)\}\{\\percent\} for domestic wastewater, and the national",
     lambda: 100.0 * _uncertainty_driver("category", "Domestic wastewater",
                                         "upper_tail_excess_share"), 0.05),
    ("v3 supp ensemble interval low", "national-v3", "technical_supplement.tex",
     r"ensemble from \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _wastewater_method("national_total", "ipcc2019", "p2_5"), 0.005),
    ("v3 supp ensemble interval high", "national-v3", "technical_supplement.tex",
     r"ensemble from \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _wastewater_method("national_total", "ipcc2019", "p97_5"), 0.005),
    ("v3 supp interval low, enteric fixed", "national-v3", "technical_supplement.tex",
     r"\\mega\\tonne\} to \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}\.",
     lambda: _uncertainty_driver("category", "Enteric fermentation",
                                 "national_p2_5_if_fixed"), 0.005),
    ("v3 supp interval high, enteric fixed", "national-v3", "technical_supplement.tex",
     r"\\mega\\tonne\} to \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}\.",
     lambda: _uncertainty_driver("category", "Enteric fermentation",
                                 "national_p97_5_if_fixed"), 0.005),
    ("v3 supp effluent factor variance share", "national-v3", "technical_supplement.tex",
     r"accounts for \\SI\{([\d.]+)\}\{\\percent\} of the national variance",
     lambda: 100.0 * _uncertainty_driver(
         "parameter", "wastewater effluent N2O factor (ww_ef_effluent)",
         "variance_share"), 0.05),
    ("v3 supp effluent factor upper tail share", "national-v3", "technical_supplement.tex",
     r"national variance and \\SI\{([\d.]+)\}\{\\percent\} of the upper-tail excess",
     lambda: 100.0 * _uncertainty_driver(
         "parameter", "wastewater effluent N2O factor (ww_ef_effluent)",
         "upper_tail_excess_share"), 0.05),
    ("v3 supp wastewater upper tail, 2006 method", "national-v3", "technical_supplement.tex",
     r"domestic wastewater was \\SI\{([\d.]+)\}\{\\percent\} of the upper-tail excess",
     lambda: 100.0 * _wastewater_method("wastewater_category", "ipcc2006",
                                        "upper_tail_excess_share"), 0.05),
    ("v3 supp national interval low, 2006 method", "national-v3", "technical_supplement.tex",
     r"national interval was \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _wastewater_method("national_total", "ipcc2006", "p2_5"), 0.005),
    ("v3 supp national interval high, 2006 method", "national-v3", "technical_supplement.tex",
     r"national interval was \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _wastewater_method("national_total", "ipcc2006", "p97_5"), 0.005),
    ("v3 supp effluent factor ceiling", "national-v3", "technical_supplement.tex",
     r"ceiling of the Refinement's range \(\\num\{([\d.]+)\}\)",
     lambda: _data_param("waste_params.csv", "ww_ef_effluent", "upper"), 0.0),
    ("v3 supp effluent ceiling delta", "national-v3", "technical_supplement.tex",
     r"adds \\SI\{([\d.]+)\}\{\\mega\\tonne\}\\,CO\$_2\$e to the national total",
     lambda: _waste_scenario("effluent_ef_high") - _waste_scenario("reference"), 0.05),
    # ---- rc67: the quantities the rewritten v3 paragraphs introduce ------------------------
    ("v3 uncertainty deterministic reference", "national-v3", "paper.tex",
     r"deterministic reference estimate is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _configuration("inventory_reference", "national_total_Mt"), 0.005),
    ("v3 ensemble enteric variance share", "national-v3", "paper.tex",
     r"national total is \\SI\{([\d.]+)\}\{\\percent\} for enteric fermentation",
     lambda: 100.0 * _uncertainty_driver("category", "Enteric fermentation",
                                         "variance_share"), 0.05),
    ("v3 ensemble managed soils variance share", "national-v3", "paper.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} for managed soils and",
     lambda: 100.0 * _uncertainty_driver("category", "Managed soils",
                                         "variance_share"), 0.05),
    ("v3 ensemble wastewater variance share", "national-v3", "paper.tex",
     r"managed soils and \\SI\{([\d.]+)\}\{\\percent\} for domestic wastewater",
     lambda: 100.0 * _uncertainty_driver("category", "Domestic wastewater",
                                         "variance_share"), 0.05),
    ("v3 dung returned to manure total", "national-v3", "paper.tex",
     r"revised and the national total is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _dung_fate("FY2023-24", "S_residual_return_to_manure",
                        "national_total_Mt_co2e_AR5"), 0.005),
    ("v3 dung applied to fields total", "national-v3", "paper.tex",
     r"applied to fields, giving \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _dung_fate("FY2023-24", "S_residual_field_application",
                        "national_total_Mt_co2e_AR5"), 0.005),
    ("v3 dung survey round rate ratio", "national-v3", "paper.tex",
     r"round reports \\num\{([\d.]+)\} times the 2018--19 rate",
     lambda: _hies_dung_rate_ratio(), 0.05),
    ("v3 residential at the earlier round's rate", "national-v3", "paper.tex",
     r"residential emissions of \\SI\{([\d.]+)\}\{\} or",
     lambda: _residential_scenario("dung_survey_rate_2018_19"), 0.005),
    ("v3 residential at the later round as measured", "national-v3", "paper.tex",
     r"residential emissions of \\SI\{[\d.]+\}\{\} or \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _residential_scenario("dung_survey_round_2024_25_as_measured"), 0.005),
    ("v3 wastewater N2O refinement", "national-v3", "paper.tex",
     r"the Refinement gives \\SI\{([\d.]+)\}\{\} and the 2006 equation",
     lambda: _wastewater_method("wastewater_n2o", "ipcc2019", "deterministic"), 0.005),
    ("v3 wastewater N2O 2006 equation", "national-v3", "paper.tex",
     r"and the 2006 equation \\SI\{([\d.]+)\}\{\\giga\\gram\}",
     lambda: _wastewater_method("wastewater_n2o", "ipcc2006", "deterministic"), 0.005),
    ("v3 wastewater method difference", "national-v3", "paper.tex",
     r"a difference of \\SI\{([\d.]+)\}\{\\mega\\tonne\}~CO\$_2\$e\. On the same draws",
     lambda: (_wastewater_method("wastewater_category", "ipcc2006", "deterministic")
              - _wastewater_method("wastewater_category", "ipcc2019", "deterministic")),
     0.005),
    ("v3 national interval low, refinement", "national-v3", "paper.tex",
     r"national total is \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} under the Refinement",
     lambda: _wastewater_method("national_total", "ipcc2019", "p2_5"), 0.005),
    ("v3 national interval high, refinement", "national-v3", "paper.tex",
     r"national total is \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} under the Refinement",
     lambda: _wastewater_method("national_total", "ipcc2019", "p97_5"), 0.005),
    ("v3 national interval low, 2006 equation", "national-v3", "paper.tex",
     r"and \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} under the 2006 equation",
     lambda: _wastewater_method("national_total", "ipcc2006", "p2_5"), 0.005),
    ("v3 national interval high, 2006 equation", "national-v3", "paper.tex",
     r"and \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} under the 2006 equation",
     lambda: _wastewater_method("national_total", "ipcc2006", "p97_5"), 0.005),
    ("v3 effluent factor ceiling, refinement", "national-v3", "paper.tex",
     r"effluent factor ends at \\num\{([\d.]+)\} in the Refinement",
     lambda: _data_param("waste_params.csv", "ww_ef_effluent", "upper"), 0.0),
    ("v3 effluent factor ceiling, 2006 guidelines", "national-v3", "paper.tex",
     r"in the Refinement and at \\num\{([\d.]+)\} in the 2006 Guidelines",
     lambda: _data_param("waste_params.csv", "ww_ef_effluent_2006_high", "value"), 0.0),
    ("v3 treated share of sewered flow", "national-v3", "paper.tex",
     r"that \\SI\{([\d.]+)\}\{\\percent\} of sewered flow is treated",
     lambda: 100.0 * _data_param("waste_params.csv", "ww_treated_share", "value"), 0.0),
    ("v3 decentralised effluent to soil", "national-v3", "paper.tex",
     r"goes to soil the waste estimate falls by \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (_waste_scenario("reference")
              - _waste_scenario("decentralised_effluent_to_soil")), 0.005),
    ("v3 nutrient-impacted discharge", "national-v3", "paper.tex",
     r"nutrient-impacted water it rises by \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: (_waste_scenario("effluent_nutrient_impacted")
              - _waste_scenario("reference")), 0.005),
    ("v3 coal drawdown, power alone", "national-v3", "paper.tex",
     r"would have to be \\SI\{(\d+)\}\{\\percent\} of the year's supply for public power alone",
     lambda: _coal_bound("B1_the_bound", r"drawdown of (\d+) percent"), 0.5),
    ("v3 coal drawdown, with other consumers", "national-v3", "paper.tex",
     r"alone and \\SI\{(\d+)\}\{\\percent\} with the other consumers",
     lambda: _coal_bound("B3_stock_change", r"drawdown of (\d+) percent"), 0.5),
    ("v3 conclusion time-independent low", "national-v3", "paper.tex",
     r"under time independence \(\\SIrange\{(-?[\d.]+)\}\{[\d.-]+\}\{\\mega\\tonne\}\)",
     lambda: _as_registered("longitudinal independent window low"), 0.005),
    ("v3 conclusion time-independent high", "national-v3", "paper.tex",
     r"under time independence \(\\SIrange\{-?[\d.]+\}\{([\d.-]+)\}\{\\mega\\tonne\}\)",
     lambda: _as_registered("longitudinal independent window high"), 0.005),
    # THE VALIDATION REGISTER'S OWN COUNTS. These were prose until 2026-10-07, and adding
    # one catalog row moved four of them at once - the register size twice, the internal
    # group and the declared-absence count. A number that changes whenever the register
    # grows is exactly the kind that must resolve against the register.
    ("v2 register size", "national-v3", "technical_supplement.tex",
     r"The register holds \\num\{(\d+)\} entries",
     lambda: float(_catalog_count()), 0.0),
    ("v2 register limits", "national-v3", "technical_supplement.tex",
     r"for all \\num\{(\d+)\} --- an explicit interpretation limit",
     lambda: float(_catalog_count(field="interpretation_limit")), 0.0),
    ("v2 register independent", "national-v3", "technical_supplement.tex",
     r"entries, \\num\{(\d+)\} compare against an independent compilation",
     lambda: float(_catalog_count("independence_class", "independent-compilation")), 0.0),
    ("v2 register partial", "national-v3", "technical_supplement.tex",
     r"compilation, \\num\{(\d+)\} are partial",
     lambda: float(_catalog_count("independence_class", "partial")), 0.0),
    ("v2 register large", "national-v3", "technical_supplement.tex",
     r"are partial, \\num\{(\d+)\} share a large part",
     lambda: float(_catalog_count("independence_class", "large")), 0.0),
    ("v2 register shared upstream", "national-v3", "technical_supplement.tex",
     r"their inputs, \\num\{(\d+)\} share an upstream statistic",
     lambda: float(_catalog_count("independence_class", "shared-upstream")), 0.0),
    ("v2 register absences", "national-v3", "technical_supplement.tex",
     r"calibrations and \\num\{(\d+)\} declared absences",
     lambda: _catalog_count("calibration_or_validation", "declared-absence"), 0.0),
    ("v2 register calibrations", "national-v3", "technical_supplement.tex",
     r"corroborations, \\num\{(\d+)\} calibrations",
     lambda: _catalog_count("calibration_or_validation", "calibration"), 0.0),
    ("v2 register internal", "national-v3", "technical_supplement.tex",
     r"outright, \\num\{(\d+)\} are internal identities or consistency checks",
     lambda: float(_catalog_count("independence_class", "internal-identity")
                   + _catalog_count("independence_class", "internal-consistency")), 0.0),
    # =========================================================================================
    # THE YEAR-MATCHED COMPARISON AGAINST PAKISTAN'S OWN SUBMISSION (Section 10, 2026-10-05).
    # Every quantity resolves through outputs/pakemis_btr_comparison.csv by SUBJECT, never by
    # IPCC code: the two accounts swap rice cultivation and managed soils, so a code-keyed
    # getter would anchor each of those two sentences to the other's row.
    # =========================================================================================
    ("btr lulucf block", "national", "10_benchmarks.tex",
     r"land-use block---\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _btr("Land (LULUCF)", "btr_Mt_co2e"), 0.005),
    ("btr national pakemis", "national", "10_benchmarks.tex",
     r"two national totals are \\SI\{([\d.]+)\}\{\}",
     lambda: _btr("TOTAL (excluding LULUCF)", "pakemis_Mt_co2e"), 0.005),
    ("btr national submission", "national", "10_benchmarks.tex",
     r"and \\SI\{([\d.]+)\}\{\\mega\\tonne\}, a\s*\n?\s*ratio",
     lambda: _btr("TOTAL (excluding LULUCF)", "btr_Mt_co2e"), 0.005),
    ("btr national ratio", "national", "10_benchmarks.tex",
     r"ratio of \\num\{([\d.]+)\}\. That agreement",
     lambda: _btr("TOTAL (excluding LULUCF)"), 0.0005),
    ("btr fugitives ratio", "national", "10_benchmarks.tex",
     r"\\num\{([\d.]+)\} on oil and gas fugitives",
     lambda: _btr("Oil and natural gas fugitives"), 0.005),
    ("btr soils ratio", "national", "10_benchmarks.tex",
     r"\\num\{([\d.]+)\} on managed soils",
     lambda: _btr("Managed soils"), 0.005),
    ("btr enteric ratio", "national", "10_benchmarks.tex",
     r"\\num\{([\d.]+)\} on enteric fermentation",
     lambda: _btr("Enteric fermentation"), 0.005),
    ("btr lubricants ratio", "national", "10_benchmarks.tex",
     r"\\num\{([\d.]+)\} on lubricants",
     lambda: _btr("Lubricant use"), 0.005),
    ("btr like-for-like pakemis", "national", "10_benchmarks.tex",
     r"the totals are \\SI\{([\d.]+)\}\{\}",
     lambda: _btr("TOTAL on categories both accounts estimate", "pakemis_Mt_co2e"), 0.005),
    ("btr like-for-like submission", "national", "10_benchmarks.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}---a ratio",
     lambda: _btr("TOTAL on categories both accounts estimate", "btr_Mt_co2e"), 0.005),
    ("btr like-for-like ratio", "national", "10_benchmarks.tex",
     r"---a ratio of \\num\{([\d.]+)\}",
     lambda: _btr("TOTAL on categories both accounts estimate"), 0.0005),
    # Re-anchored 2026-10-07: the difference changed SIGN with the coal re-base, so the
    # sentence states its magnitude and names the direction in words. The old regex took
    # [\d.]+ against a signed subtraction and would simply have stopped matching.
    ("btr national gap", "national", "10_benchmarks.tex",
     r"The \\SI\{([\d.]+)\}\{\\mega\\tonne\} national",
     lambda: abs(_btr("TOTAL (excluding LULUCF)", "btr_Mt_co2e")
                 - _btr("TOTAL (excluding LULUCF)", "pakemis_Mt_co2e")), 0.011),
    ("btr shared category gap", "national", "10_benchmarks.tex",
     r"inventory is \\SI\{([\d.]+)\}\{\\mega\\tonne\} above the submission",
     lambda: (_btr("TOTAL on categories both accounts estimate", "pakemis_Mt_co2e")
              - _btr("TOTAL on categories both accounts estimate", "btr_Mt_co2e")), 0.011),
    ("btr only mass", "national", "10_benchmarks.tex",
     r"directions\. \\SI\{([\d.]+)\}\{\\mega\\tonne\} is seven categories",
     lambda: _btr_tier_mass("btr-only", "btr_Mt_co2e"), 0.005),
    ("btr pakemis only mass", "national", "10_benchmarks.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} this inventory estimates where",
     lambda: _btr_tier_mass(("pakemis-only", "btr-zero"), "pakemis_Mt_co2e"), 0.005),
    ("btr net completeness gap", "national", "10_benchmarks.tex",
     r"a net \\SI\{([\d.]+)\}\{\\mega\\tonne\} of pure completeness",
     lambda: (_btr_tier_mass("btr-only", "btr_Mt_co2e")
              - _btr_tier_mass(("pakemis-only", "btr-zero"), "pakemis_Mt_co2e")), 0.011),
    ("btr landfill ratio", "national", "10_benchmarks.tex",
     r"this inventory is \\num\{([\d.]+)\} of the submission",
     lambda: _btr("Solid waste disposal"), 0.005),
    ("btr open burning ratio", "national", "10_benchmarks.tex",
     r"waste it is \\num\{([\d.]+)\}\s*\n?\s*times it",
     lambda: _btr("Open burning of waste"), 0.005),
    ("btr solid stream ratio", "national", "10_benchmarks.tex",
     r"solid stream the ratio is \\num\{([\d.]+)\}",
     lambda: _btr("Solid-waste fate (disposal + burning)"), 0.005),
    ("btr soils submission", "national", "10_benchmarks.tex",
     r"managed-soil nitrous oxide at\s*\n?\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _btr("Managed soils", "btr_Mt_co2e"), 0.005),
    ("btr soils pakemis", "national", "10_benchmarks.tex",
     r"against this inventory's\s*\n?\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _btr("Managed soils", "pakemis_Mt_co2e"), 0.005),
    # The related-work section's own repeat of the completeness shortfall.
    ("related work btr shortfall", "national", "02_related_work.tex",
     r"shortfall is\s*\n?\s*\\SI\{([\d.]+)\}\{\\mega\\tonne\} across seven categories",
     lambda: _btr_tier_mass("btr-only", "btr_Mt_co2e"), 0.005),
    # rc67: the nine national "sobol ..." claims on the withdrawn first-order index (Section
    # 7, 2026-10-05) are DELETED with their paragraph. data/sobol_convergence.csv, the
    # estimator sweep and the surrogate attribution are retired, and the section states the
    # released ensemble's own variance shares instead (the "drivers ..." claims).
    # ---- the submission folds residue burning into its land block (Section 10, corrected
    # 2026-10-05 against the land lane's finding; an earlier reading called this inventory the
    # more complete account here, which was the opposite of true).
    ("btr cropland non-co2", "national", "10_benchmarks.tex",
     r"non-CO\\textsubscript\{2\} half is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _btr_gas("3.B.2", "non_co2"), 0.005),
    ("btr cropland co2", "national", "10_benchmarks.tex",
     r"beside \\SI\{([\d.]+)\}\{\\mega\\tonne\} of\s*\n?\s*land-use",
     lambda: _btr_gas("3.B.2", "co2"), 0.005),
    ("btr residue burning ratio", "national", "10_benchmarks.tex",
     r"field burning is \\num\{([\d.]+)\}, not a surplus",
     lambda: _btr("Residue burning, against the submission's cropland non-CO2"), 0.005),
    ("btr land block non-co2", "national", "10_benchmarks.tex",
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\} of its \\SI\{[\d.]+\}\{\\mega\\tonne\} is CH",
     lambda: _btr_gas("3.B", "non_co2"), 0.005),
    # ---- which KIND of boundary conflict each station has (Section 10, 2026-10-05). These four
    # counts move the moment an eighth station appears or a boundary file is re-simplified,
    # which is exactly why they are anchored to the audit rather than left as prose.
    ("boundary frame-inconsistent count", "national", "10_benchmarks.tex",
     r"For\s*\n?\\num\{(\d+)\} the frame disagrees with itself",
     lambda: _boundary_adjudication("frame-inconsistent"), 0.0),
    ("boundary frame-gap count", "national", "10_benchmarks.tex",
     r"\\num\{(\d+)\} sits in a hole",
     lambda: _boundary_adjudication("frame-gap"), 0.0),
    ("boundary frame-dissent count", "national", "10_benchmarks.tex",
     r"the remaining \\num\{(\d+)\}\s*\n?\s*the curated and source records agree",
     lambda: _boundary_adjudication("records-agree-frame-dissents"), 0.0),
    ("boundary record-error count", "national", "10_benchmarks.tex",
     r"\\num\{(\d+)\} of the seven is a\s*\n?\s*station-record error",
     lambda: _boundary_adjudication("records-disagree"), 0.0),
    # ---- the forest-land sign disagreement (Section 12, T-LAND-2, 2026-10-05). Every figure
    # resolves through outputs/pakemis_forest_flux_adjudication.csv, including the CRT gross
    # pair, whose own check is that it nets to the submission's independently printed total.
    ("lulucf crt gross losses", "national", "12_limitations.tex",
     r"gross losses at \\SI\{([\d.]+)\}\{\}",
     lambda: _forest_screen("CRT forest gross losses"), 0.0005),
    ("lulucf crt gross gains", "national", "12_limitations.tex",
     r"gross gains of \\SI\{([\d.]+)\}\{\} kilotonnes",
     lambda: _forest_screen("CRT forest gross gains"), 0.0005),
    ("lulucf crt loss ratio", "national", "12_limitations.tex",
     r"a ratio of \\num\{([\d.]+)\} that nets",
     lambda: _forest_screen("CRT gross loss over gross gain"), 0.005),
    ("lulucf crt net from gross", "national", "12_limitations.tex",
     r"nets to\s*\n?\\SI\{([\d.]+)\}\{\\mega\\tonne\} of CO",
     lambda: _forest_screen("CRT forest net from the gross pair"), 0.0005),
    ("lulucf faostat area step", "national", "12_limitations.tex",
     r"rises at exactly \\SI\{([\d.]+)\}\{\} kha",
     lambda: _forest_step(), 0.0005),
    ("lulucf faostat conversion 2015", "national", "12_limitations.tex",
     r"against\s*\n?\\num\{([\d.]+)\}~kha in 2015",
     lambda: _forest_conversion(2015), 0.0005),
    ("lulucf sign gap", "national", "12_limitations.tex",
     r"FAOSTAT is\s*\n?\\SI\{([\d.]+)\}\{\\mega\\tonne\} of CO",
     lambda: _forest_screen("sign disagreement, matched year"), 0.005),
    # ---- the F-gas leak-rate adjudication (IPPU discussion, T-MISS-2, 2026-10-05).
    # The rates and the spans resolve through outputs/pakemis_fgas_leak_rate_adjudication.csv;
    # the CRT figures resolve through the shipped extraction of the held workbook, at the
    # 2.F.1.a row rather than an aggregate, because the placement is the claim.
    ("fgas crt single entry t", "ippu", "07_discussion.tex",
     r"entered at \\SI\{([\d.]+)\}\{\\tonne\} as exactly",
     lambda: _fgas_rate("CRT 2022, 2.F.1.a commercial refrigeration", "crt_emitted_t"),
     0.0000005),
    ("fgas crt product life factor", "ippu", "07_discussion.tex",
     r"as exactly \\SI\{([\d.]+)\}\{\\percent\} of a declared",
     lambda: _fgas_rate("CRT 2022, 2.F.1.a commercial refrigeration"), 0.0),
    ("fgas crt stock t", "ippu", "07_discussion.tex",
     r"\\SI\{([\d.]+)\}\{\\tonne\} operating stock",
     lambda: _fgas_rate("CRT 2022, 2.F.1.a commercial refrigeration",
                        "crt_declared_stock_t"), 0.000005),
    ("fgas refrigeration domestic low ratio", "ippu", "07_discussion.tex",
     r"outside two of them, from \\num\{(\d+)\} to \\num\{\d+\} times above",
     lambda: _fgas_rate("refrigeration") / 0.5, 0.0),
    ("fgas refrigeration domestic high ratio", "ippu", "07_discussion.tex",
     r"outside two of them, from \\num\{\d+\} to \\num\{(\d+)\} times above",
     lambda: _fgas_rate("refrigeration") / 0.1, 0.0),
    ("fgas refrigeration rate", "ippu", "07_discussion.tex",
     r"refrigeration\s*\n?\\SI\{([\d.]+)\}\{\\percent\} per year",
     lambda: _fgas_rate("refrigeration"), 0.0),
    ("fgas stationary ac rate", "ippu", "07_discussion.tex",
     r"stationary air-conditioning \\SI\{([\d.]+)\}\{\\percent\}",
     lambda: _fgas_rate("stationary AC"), 0.0),
    ("fgas mobile ac rate", "ippu", "07_discussion.tex",
     r"air-conditioning \\SI\{([\d.]+)\}\{\\percent\}---while IPCC",
     lambda: _fgas_rate("mobile AC"), 0.0),
    ("fgas refrigeration band low", "ippu", "07_discussion.tex",
     r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\percent\} per year with no common value",
     lambda: _fgas_range("refrigeration", "band_envelope_pct_yr", "lo"), 0.0),
    ("fgas refrigeration band high", "ippu", "07_discussion.tex",
     r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\percent\} per year with no common value",
     lambda: _fgas_range("refrigeration", "band_envelope_pct_yr", "hi"), 0.0),
    ("fgas refrigeration operating low", "ippu", "07_discussion.tex",
     r"operating channel from\s*\n?\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _fgas_range("refrigeration", "operating_channel_low_to_high_Mt", "lo"), 0.000005),
    ("fgas refrigeration operating high", "ippu", "07_discussion.tex",
     r"to \\SI\{([\d.]+)\}\{\\mega\\tonne\} of \\COtwo e, a factor",
     lambda: _fgas_range("refrigeration", "operating_channel_low_to_high_Mt", "hi"), 0.000005),
    ("fgas refrigeration total low", "ippu", "07_discussion.tex",
     r"moves only\s*\n?\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _fgas_rate("refrigeration", "stratum_at_envelope_low_Mt"), 0.000005),
    ("fgas refrigeration total high", "ippu", "07_discussion.tex",
     r"moves only\s*\n?\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _fgas_rate("refrigeration", "stratum_at_envelope_high_Mt"), 0.000005),
    ("fgas refrigeration bank low", "ippu", "07_discussion.tex",
     r"closing bank of \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
     lambda: _fgas_range("refrigeration", "closing_bank_low_to_high_Mt", "lo"), 0.0005),
    ("fgas refrigeration bank high", "ippu", "07_discussion.tex",
     r"closing bank of \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _fgas_range("refrigeration", "closing_bank_low_to_high_Mt", "hi"), 0.0005),
    # ---- the release-axis measurement (Section 12, T-VINTAGE-AXES, 2026-10-05)
    ("release axis tables fingerprinted", "national", "12_limitations.tex",
     r"Of the \\num\{(\d+)\} disaggregated tables",
     lambda: _axis_fine_only(total=True), 0.0),
    ("release axis fine only tables", "national", "12_limitations.tex",
     r"fingerprinted, \\num\{(\d+)\} currently\s*\n?\s*show a moved fine",
     lambda: _axis_fine_only(), 0.0),
    # ---- the per-row licence repair (Section 12, 2026-10-05)
    ("facility registry rows", "national", "12_limitations.tex",
     r"qualifying each of its\s*\n?\s*\\num\{(\d+)\} rows",
     lambda: _facility_licence("total"), 0.0),
    ("facility registry odbl rows", "national", "12_limitations.tex",
     r"and \\num\{(\d+)\} of them are OpenStreetMap",
     lambda: _facility_licence("odbl"), 0.0),
    # ---- the citation pointer audit (Section 12, 2026-10-05)
    ("pointer audit scored sources", "national", "12_limitations.tex",
     r"Of the \\num\{(\d+)\} sources",
     lambda: _pointer_audit("scored"), 0.0),
    ("pointer audit pointed", "national", "12_limitations.tex",
     r"is the right notion, \\num\{(\d+)\} have one",
     lambda: _pointer_audit("pointed"), 0.0),
    ("pointer audit unpointed", "national", "12_limitations.tex",
     r"rather than \\num\{(\d+)\}\.",
     lambda: _pointer_audit("unpointed"), 0.0),
    ("pointer audit checkable here", "national", "12_limitations.tex",
     r"\\emph\{checkable\}: \\num\{(\d+)\} of the",
     lambda: _pointer_audit("checkable:yes"), 0.0),
    ("pointer audit not held", "national", "12_limitations.tex",
     r"while \\num\{(\d+)\} point into",
     lambda: _pointer_audit("checkable:document-not-held"), 0.0),
    ("pointer audit derived files", "national", "12_limitations.tex",
     r"hold and \\num\{(\d+)\} into files derived",
     lambda: _pointer_audit("checkable:derived-file"), 0.0),
    ("pointer audit unpointed remaining", "national", "12_limitations.tex",
     r"The \\num\{(\d+)\} that remain",
     lambda: _pointer_audit("unpointed"), 0.0),
    # ---- the minerals panel screening (Section 12, 2026-10-05)
    ("minerals screening mineral years", "national", "12_limitations.tex",
     r"of \\num\{(\d+)\} mineral-years",
     lambda: _minerals_screening("mineral_years"), 0.0),
    ("minerals screening incomplete covered", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} are served as\s*\n?\s*covered",
     lambda: _minerals_screening("incomplete_but_covered"), 0.0),
    ("minerals screening worst served share", "national", "12_limitations.tex",
     r"puts \\SI\{([\d.]+)\}\{\\percent\} of the year in a single month",
     lambda: _minerals_screening("worst_served_share"), 0.005),
    ("minerals screening gas oil duplication", "national", "12_limitations.tex",
     r"carries \\num\{(\d+)\} rows in",
     lambda: _minerals_screening("gas_oil_rows_per_month"), 0.0),
    ("minerals screening coal panel share", "national", "12_limitations.tex",
     r"carries \\SI\{([\d.]+)\}\{\\percent\} of that year's coal",
     lambda: _minerals_screening("share:coal:2021"), 0.05),
    ("minerals screening control disagreements", "national", "12_limitations.tex",
     r"\\num\{(\d+)\} canonical mineral-years",
     lambda: _minerals_screening("control_disagreements"), 0.0),
    ("minerals screening limestone panel share", "national", "12_limitations.tex",
     r"FY2016--17 ships \\SI\{([\d.]+)\}\{\\percent\} of what its control",
     lambda: _minerals_screening("share:limestone:2016"), 0.05),
    ("minerals screening gas panel share", "national", "12_limitations.tex",
     r"FY2020--21 ships \\SI\{([\d.]+)\}\{\\percent\} of it",
     lambda: _minerals_screening("share:natural_gas:2020"), 0.05),
    ("minerals screening gas duplication ratio", "national", "12_limitations.tex",
     r"quantity is \\num\{([\d.]+)\} times the last year",
     lambda: _minerals_screening("gas_duplication_ratio"), 0.005),
    ("minerals screening worst duplication", "national", "12_limitations.tex",
     r"and \\num\{(\d+)\} for coal and limestone",
     lambda: _minerals_screening("max_rows_per_month"), 0.0),
    # ---- v3: products the supplement cites by their headline numbers -------------------
    ("v3 taxonomy static share", "national-v3", "technical_supplement.tex",
     r"FY2023--24: \\SI\{([\d.]+)\}\{\\percent\} on a timeless structural surface",
     lambda: _basis_share("FY2023-24", "static_structural"), 0.05),
    ("v3 taxonomy observed share", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} on that year's observed activity",
     lambda: _basis_share("FY2023-24", "annual_observed_activity"), 0.05),
    ("v3 taxonomy substituted share", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} on a declared stand-in surface",
     lambda: _basis_share("FY2023-24", "substituted_surface"), 0.05),
    ("v3 taxonomy unallocated share", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} retained at province level",
     lambda: _basis_share("FY2023-24", "unallocated"), 0.005),
    ("v3 fixed vector exposure max", "national-v3", "technical_supplement.tex",
     r"by up to \\SI\{([\d.]+)\}\{\\mega\\tonne\}\\,CO\$_2\$e in one province-year",
     lambda: _fixed_vector_exposure("max"), 0.05),
    ("v3 fixed vector exposure reference", "national-v3", "technical_supplement.tex",
     r"by at most \\SI\{([\d.]+)\}\{\\mega\\tonne\}\\,CO\$_2\$e in the reference year",
     lambda: _fixed_vector_exposure("reference"), 0.005),
    ("v3 enteric bridge total gap", "national-v3", "technical_supplement.tex",
     r"the whole \\SI\{([\d.]+)\}\{\\mega\\tonne\} difference sitting in buffalo",
     lambda: _enteric_bridge("TOTAL", "difference_Mt"), 0.05),
    ("v3 enteric bridge buffalo ours", "national-v3", "technical_supplement.tex",
     r"buffalo \(\\num\{([\d.]+)\} against \\num\{[\d.]+\}\)",
     lambda: _enteric_bridge("buffalo", "pakemis_Mt_co2e_AR5"), 0.005),
    ("v3 enteric bridge buffalo btr", "national-v3", "technical_supplement.tex",
     r"buffalo \(\\num\{[\d.]+\} against \\num\{([\d.]+)\}\)",
     lambda: _enteric_bridge("buffalo", "btr_Mt_co2e"), 0.005),
    ("v3 enteric bridge other cattle ours", "national-v3", "technical_supplement.tex",
     r"other cattle \(\\num\{([\d.]+)\} against \\num\{[\d.]+\}\)",
     lambda: _enteric_bridge("other_cattle", "pakemis_Mt_co2e_AR5"), 0.005),
    ("v3 enteric bridge other cattle btr", "national-v3", "technical_supplement.tex",
     r"other cattle \(\\num\{[\d.]+\} against \\num\{([\d.]+)\}\)",
     lambda: _enteric_bridge("other_cattle", "btr_Mt_co2e"), 0.005),
    ("v3 enteric bridge btr-only species", "national-v3", "technical_supplement.tex",
     r"mules and asses, horses; \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _enteric_bridge_btr_only(), 0.005),
    ("v3 hies dung users share 2019", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of 33\.2~million weighted households",
     lambda: _hies_users_share("hies2019"), 0.05),
    ("v3 hies dung users share 2025", "national-v3", "technical_supplement.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} of 39\.9~million",
     lambda: _hies_users_share("hies2025"), 0.05),
    ("v3 hies dung change", "national-v3", "technical_supplement.tex",
     r"11\.97~Mt, an \\SI\{([\d.]+)\}\{\\percent\} change larger",
     lambda: _hies_dung_change_pct(), 0.5),
    ("v3 five classes benchmark", "national-v3", "generated/tab_five_classes.tex",
     r"Partially independent benchmark & (\d+)", lambda: _five_class_count("partially"), 0.0),
    ("v3 five classes compilation", "national-v3", "generated/tab_five_classes.tex",
     r"Independent compilation \(another inventory, not an observation\) & (\d+)",
     lambda: _five_class_count("independent compilation"), 0.0),
    ("v3 five classes calibration", "national-v3", "generated/tab_five_classes.tex",
     r"Calibration \(fitted to the comparator; cannot validate it\) & (\d+)",
     lambda: _five_class_count("calibration"), 0.0),
    ("v3 five classes shares", "national-v3", "generated/tab_five_classes.tex",
     r"Shares activity or factors with the estimate & (\d+)", lambda: _five_class_count("shares"), 0.0),
    ("v3 five classes internal", "national-v3", "generated/tab_five_classes.tex",
     r"Internal consistency or accounting identity & (\d+)", lambda: _five_class_count("internal"), 0.0),
    ("v3 five classes absence", "national-v3", "generated/tab_five_classes.tex",
     r"Declared absence \(no check performed\) & (\d+)", lambda: _five_class_count("declared"), 0.0),
    ("v3 five classes not a comparison", "national-v3", "generated/tab_five_classes.tex",
     r"Not a comparison & (\d+)", lambda: _five_class_count("not a comparison"), 0.0),
    ("v3 five classes total", "national-v3", "generated/tab_five_classes.tex",
     r"All catalogue entries & (\d+)", lambda: _five_class_count("TOTAL"), 0.0),
    # ---- v3 editorial rewrite: the BTR paragraph and the conclusions -----------------------
    ("v3 btr like-for-like count", "national-v3", "paper.tex",
     r"On the \\num\{(\d+)\} categories both inventories estimate", lambda: _btr_like_for_like_count(), 0.0),
    # rc63: THE SENTENCE SAID THE SIXTEEN CATEGORIES TOTAL TO 1.02. They total to 1.04. The
    # product's "TOTAL on categories both accounts estimate" also contains "Other sectors", a
    # scope-gap subject that is not one of the sixteen; the figure drew that total under the
    # sixteen points and the text named it as theirs. Each number is now said of its own set.
    ("rc63 btr like-for-like total ratio", "national-v3", "paper.tex",
     r"the totals agree to \\num\{([\d.]+)\};", lambda: _btr_like_for_like_total_ratio(), 0.005),
    ("v3 btr shared-category total ratio", "national-v3", "paper.tex",
     r"they agree to \\num\{([\d.]+)\}, and the ratio of the two totals", lambda: _btr("TOTAL on categories both accounts estimate"), 0.005),
    ("v3 btr within-band count", "national-v3", "paper.tex",
     r"\\num\{(\d+)\} categories lie within a factor of two", lambda: _btr_within_band_count(), 0.0),
    ("v3 btr open burning ratio", "national-v3", "paper.tex",
     r"open burning of waste \(\\num\{([\d.]+)\}\)", lambda: _btr("Open burning of waste"), 0.005),
    ("v3 btr managed soils ratio", "national-v3", "paper.tex",
     r"managed soils \(\\num\{([\d.]+)\}\)", lambda: _btr("Managed soils"), 0.005),
    ("v3 btr solid waste ratio", "national-v3", "paper.tex",
     r"solid-waste disposal \(\\num\{([\d.]+)\}\)", lambda: _btr("Solid waste disposal"), 0.005),
    ("v3 btr lubricant ratio", "national-v3", "paper.tex",
     r"lubricant use \(\\num\{([\d.]+)\}\)", lambda: _btr("Lubricant use"), 0.005),
    ("v3 btr indirect manure ratio", "national-v3", "paper.tex",
     r"indirect manure N\$_2\$O \(\\num\{([\d.]+)\}\)", lambda: _btr("Indirect N2O from manure management"), 0.005),
    ("v3 btr enteric ratio", "national-v3", "paper.tex",
     r"Enteric fermentation is \\num\{([\d.]+)\} times the submitted value", lambda: _btr("Enteric fermentation"), 0.005),
    ("v3 btr manure ratio", "national-v3", "paper.tex",
     r"manure management from the same herd is \\num\{([\d.]+)\}; by species", lambda: _btr("Manure management (CH4 and direct N2O)"), 0.005),
    ("v3 btr qualified count", "national-v3", "paper.tex",
     r"\\num\{(\d+)\} further subjects cannot be expressed as ratios", lambda: _btr_qualified_count(), 0.0),
    ("v3 conclusion calorific choice", "national-v3", "paper.tex",
     r"an open choice worth \\SI\{([\d.]+)\}\{\\mega\\tonne\}", lambda: _configuration_delta("inventory_reference", "power_plant_physical_coal"), 0.05),
    ("v3 conclusion dung difference", "national-v3", "paper.tex",
     r"households raises the national total by \\SI\{([\d.]+)\}\{\\mega\\tonne\}", lambda: _configuration("all_diverted_dung_household_fuel", "national_delta_Mt"), 0.05),
    ("v3 district rebase units low", "national-v3", "paper.tex",
     r"between \\num\{(\d+)\} and \\num\{\d+\} districts", lambda: _rebase_units("min"), 0.0),
    ("v3 district rebase units high", "national-v3", "paper.tex",
     r"between \\num\{\d+\} and \\num\{(\d+)\} districts", lambda: _rebase_units("max"), 0.0),
    ("v3 paper taxonomy static share", "national-v3", "paper.tex",
     r"by mass \\SI\{([\d.]+)\}\{\\percent\} of the reference year sits on a timeless structural surface",
     lambda: _basis_share("FY2023-24", "static_structural"), 0.05),
    ("v3 paper taxonomy observed share", "national-v3", "paper.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} on that year's observed activity and",
     lambda: _basis_share("FY2023-24", "annual_observed_activity"), 0.05),
    ("v3 paper taxonomy substituted share", "national-v3", "paper.tex",
     r"\\SI\{([\d.]+)\}\{\\percent\} on a declared substitute",
     lambda: _basis_share("FY2023-24", "substituted_surface"), 0.05),
    ("v3 paper fixed vector exposure max", "national-v3", "paper.tex",
     r"largest correction is \\SI\{([\d.]+)\}\{\\mega\\tonne\}\\,CO\$_2\$e of coal emissions",
     lambda: _fixed_vector_exposure("max"), 0.05),
    ("v3 paper fixed vector exposure reference", "national-v3", "paper.tex",
     r"reference year moved by at most \\SI\{([\d.]+)\}\{\\mega\\tonne\}\\,CO\$_2\$e",
     lambda: _fixed_vector_exposure("reference"), 0.005),
    ("v3 paper gas energy resting on generation", "national-v3", "paper.tex",
     r"for at most \\SI\{(\d+)\}\{\\percent\} of a period's gas energy",
     lambda: _gas_generation_derived_max(), 0.5),
    # rc65, the retention sweep: the reproducibility paragraph states what is held.
    ("v3 paper files citing only held documents", "national-v3", "paper.tex",
     r"\\num\{(\d+)\} of the \\num\{\d+\} registered data files cite only documents",
     lambda: _source_register_count("archived"), 0.0),
    ("v3 paper registered data files", "national-v3", "paper.tex",
     r"of the \\num\{(\d+)\} registered data files cite only documents",
     lambda: _source_register_count(None), 0.0),
    ("v3 paper derived data files", "national-v3", "paper.tex",
     r"\\num\{(\d+)\} are derived inside the repository",
     lambda: _source_register_count("derived"), 0.0),
    ("v3 paper files citing an unheld document", "national-v3", "paper.tex",
     r"\\num\{(\d+)\} cite at least one document that is not held as cited",
     lambda: _source_register_count("not-archived"), 0.0),
    ("v3 paper hand-run validations with a check", "national-v3", "paper.tex",
     r"\\num\{(\d+)\} can be re-derived and compared without being overwritten",
     lambda: _hand_run_validations_checked(), 0.0),
]


def _hand_run_validations_checked():
    """Hand-run validation products whose producer has a declared compare-only check."""
    rows = read_rows(asset_path(ROOT, "data", "held_products.csv"))
    hand = [r for r in rows if (r["reason_held"] or "").startswith("hand-run validation")]
    assert len(hand) == 8, "the manuscript says eight hand-run validation products; %d" % len(hand)
    return sum(1 for r in hand if r["verify_mode"] == "checks")


# =============================================================================================
# THE SEMANTIC CLAIMS REGISTRY
#
# DOC_CLAIMS and TABLES check that a printed NUMBER matches an output. They cannot check what
# the sentence around it says, and that is where the last three rounds of defects have lived:
#
#   "the road-transport category widens by half, and transport doubles"
#       - both numbers in that sentence were current; neither ratio was a doubling. The module
#         moved 11.54 -> 18.28 (+58%) and the category 11.96 -> 18.46 (+54%).
#   "four cross-sector closures"
#       - four closures exist; two of them are between categories INSIDE a module.
#   "more than twice its size", "a thirtieth as much", "roughly twenty-six times"
#       - all three were comparative statements that outlived the numbers they described.
#
# A claim here binds a PHRASE to a computed RELATION. The phrase must be present in the named
# section, and the relation must hold, or the test fails. It is the same discipline as an
# anchored number, applied to the word rather than the digit.
#
# Operators:
#   ratio_at_least   the phrase asserts a floor      ("doubles" needs >= 1.95)
#   ratio_within     the phrase asserts a value      ("half again" is 1.5 +/- tol)
#   count_equals     the phrase asserts a count      ("four closures")
#   less_than        the phrase asserts a direction  ("a minor share of variance")
CLAIMS = [
    # (claim_id, doc, section, phrase, operator, reference, tolerance, metric)
    ("four closures, and how many cross a module", "national", "01_introduction.tex",
     "Two of the four cross a module", "count_equals", 2, 0.0,
     lambda: _closures_crossing_modules()),
    ("road against residential in CO2e", "national-supplement", "supplement.tex",
     # rc67: 1.4 -> 1.7. Household dung follows the survey, so residential is smaller and
     # road transport larger beside it; the sentence prints 1.7.
     "times its size", "ratio_within", 1.7, 0.05,
     lambda: _keycat("Road transport", "level_Mt_co2e_AR5")
             / _keycat("Residential fuel combustion", "level_Mt_co2e_AR5")),
    # rc67: 77 -> 34 under the reference; 77 is now configuration L's ratio and is bound
    # to its own phrase.
    ("residential PM against road PM", "national-supplement", "supplement.tex",
     "times road transport", "ratio_within", 34.0, 0.5,
     lambda: _air("residential", "PM2.5") / _air("transport", "PM2.5")),
    ("residential PM against road PM under configuration L", "national-supplement",
     "supplement.tex",
     "times under configuration~L", "ratio_within", 77.0, 0.5,
     lambda: _cell("residential_configurations_2024.csv", "configuration", "L", "pm25_kt")
             / _air("transport", "PM2.5")),
    ("the IPCC category count", "national", "08_key_categories.tex",
     # 22 -> 24 at the 2026-10-06 IPCC 2006 migration: manure management split into 3.A.2 and
     # 3.C.6, managed soils into 3.C.4 and 3.C.5. No category was added to the inventory and
     # no mass moved - the pairs sum to their predecessors - so this is a re-coding, not a
     # re-base. rc52 had added ammonia, steel and lubricants.
     "IPCC categories are key", "count_equals", 24, 0.0,
     lambda: float(len(_rows("national_key_categories.csv")))),
    # Restated in rc18: naming agriculture's factors dropped the unnamed share
    # from three quarters to about an eighth - the sentence and this relation
    # moved together, which is the contract. Restated again in rc41 Wave 4: scoping
    # the other nine sectors' factor, conversion and activity groups to their streams
    # took it to about a fiftieth.
    # rc67: re-pointed from the retired surrogate Sobol attribution to the parameter
    # graph's own row-private residual share (the product fact), 0.022 -> 0.025 with the
    # printed figure. The companion claim "the largest named parameter is the buffalo
    # enteric factor" is DELETED with its sentence: parameter-level importance is no
    # longer claimed.
    ("a small minority of the national variance has no named parameter",
     "national", "01_introduction.tex",
     "has no named parameter", "ratio_within", 0.025, 0.01,
     lambda: _product_fact("uncertainty_variance_share_residual_pct") / 100.0),
    # Written in the rc3 round, before the prose it binds: the paragraph that replaced
    # "moves by nearly seven" asserts negligibility, so negligibility is a checked relation.
    ("cross-module sharing is negligible at national and transport scale", "national",
     "07_uncertainty.tex", "negligible effect on both national and transport intervals",
     "less_than", 0.1, 0.0,
     lambda: max(abs(_mc("cross_sector", "TOTAL") - _mc("within_sector", "TOTAL")),
                 abs(_mc("cross_sector", "transport") - _mc("within_sector", "transport")))),
    ("every scenario move sits inside Monte Carlo noise", "national", "07_uncertainty.tex",
     "indistinguishable from Monte Carlo sampling noise", "less_than", 1.0, 0.0,
     lambda: _max_mc_noise_ratio()),
    # rc67: rewritten with its sentence. national_priority_rankings.csv carries no
    # parametric ranking any more; the parametric answer is a CATEGORY, the one the
    # released ensemble's drivers product ranks first by variance share.
    ("the parametric priority is enteric fermentation", "national",
     "07_uncertainty.tex",
     "its answer is enteric fermentation", "ratio_at_least", 1.0, 0.0,
     lambda: 1.0 if next(r["name"] for r in _rows_banner("pakemis_uncertainty_drivers.csv")
                         if r["grain"] == "category"
                         and r["rank_by_variance_share"] == "1") == "Enteric fermentation"
             else 0.0),
    # THE FOURTEENTH REVIEW'S FIRST DEFECT closed at rc19 with anchors in both
    # directions; at rc20 the anchored sentence itself became history when the
    # FY2015-16 product splits were recovered. The claims track the closed state
    # the same way they tracked the open one: the panel-is-complete sentence binds
    # to zero NE sector-years, an empty NE detail, and all ten sectors estimated
    # in the earliest year - so a NEW absence flips these before it flips prose.
    ("the panel is complete: zero NE sector-years",
     "national", "12_limitations.tex",
     "no sector-year in the panel is NE", "count_equals", 0, 0.0,
     lambda: _product_fact("annual_ne_sector_years")),
    ("all ten sectors estimated in the earliest year", "national",
     "12_limitations.tex",
     "The nine-year ten-sector panel is complete", "count_equals", 10, 0.0,
     lambda: _product_fact("first_fy_estimated_sector_count")),
    ("the recovered cells are road transport and industrial combustion", "national",
     "12_limitations.tex",
     "road transport and industrial", "ratio_at_least", 1.0, 0.0,
     lambda: 1.0 if next(r for r in _csv_rows("pakemis_product_facts.csv")
                         if r["fact_id"] == "annual_ne_detail")["value"] == ""
             else 0.0),
]


# A word that commits the sentence to a direction. "only", "just" and "merely" are
# deliberately absent: they qualify how BIG a movement is, not which way it goes, and banning
# them would make the guard reject honest prose.
DIRECTION_WORDS = {"widens": +1, "widening": +1, "rises": +1, "increases": +1, "up": +1,
                   "narrows": -1, "narrowing": -1, "falls": -1, "decreases": -1,
                   "reduces": -1, "shrinks": -1, "drops": -1}


# (movement_id, doc, section, pattern with TWO capture groups, from_metric, to_metric)
MOVEMENTS = [
    # RETIRED at rc16, not lost: once the nitrogen series became one parameter the
    # two scenarios round to the same figure, so there is no movement left to check
    # in these two sentences. The equality itself is checked as a CLAIM in each
    # (both now print 12.85 and both are anchored), and the surviving movement
    # entries below still bracket the scenarios where a difference remains.
    # Replacing the three retired national entries with movements that ARE real, so
    # the registry keeps its floor by carrying live comparisons rather than by
    # keeping dead ones: the sewer correction factor's category move, and the two
    # arms of the national interval about its own median.
    ("discussion sewer wastewater move", "national", "11_discussion.tex",
     r"moves domestic wastewater from \\SI\{([\d.]+)\}\{\\mega\\tonne\} to "
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("waste_totals_2024.csv", "co2e_Mt_AR5",
                          category="Sensitivity: wastewater on the river-discharge "
                                   "MCF (category total)"),
     lambda: _first_where("waste_totals_2024.csv", "co2e_Mt_AR5",
                          category="Domestic wastewater")),
    ("completeness gas rows hhv move", "national", "09_completeness.tex",
     r"moves the gas rows from \\SI\{([\d.]+)\}\{\\mega\\tonne\} to "
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     # The gas half is the category minus the liquid rows, and the liquid rows are
     # summed from the engine's own stream file rather than typed - they do not move
     # with the heating value, which is the sentence's whole point.
     lambda: _first_where("industry_totals_2024.csv", "co2e_Mt_AR5",
                          category="Sensitivity: gas at 900 Btu/scf")
             - _industry_liquid_Mt(),
     lambda: _first_where("industry_totals_2024.csv", "co2e_Mt_AR5",
                          category="Industrial fuel combustion (1A2)")
             - _industry_liquid_Mt()),
    ("completeness industrial category hhv move", "national", "09_completeness.tex",
     r"category as a whole from \\SI\{([\d.]+)\}\{\\mega\\tonne\} to "
     r"\\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _first_where("industry_totals_2024.csv", "co2e_Mt_AR5",
                          category="Sensitivity: gas at 900 Btu/scf"),
     lambda: _first_where("industry_totals_2024.csv", "co2e_Mt_AR5",
                          category="Industrial fuel combustion (1A2)")),
    ("uncertainty section road category", "national", "07_uncertainty.tex",
     r"road-transport category from \$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$\s*to\s*"
     r"\$\\pm\\SI\{([\d.]+)\}\{\\percent\}\$",
     lambda: _mc("within_sector", "Road transport"),
     lambda: _mc("cross_sector", "Road transport")),
]



def _temporal_grade(field):
    """rc41 T-1: the historical temporal grade's numbers, from the same functions the
    scorecard row is computed with and from the row's own printed arithmetic."""
    from pkinv.report import temporal_decomposition as td, pass2_scorecard as ps
    if field == "nine_year_pct":
        return td.variable_unobserved()[2]
    if field == "reference_pct":
        return td.variable_unobserved(ps.REFERENCE_PERIOD_ID)[2]
    if field == "target_pct":
        return ps.TARGET_VARIABLE_UNOBSERVED_PCT
    row = next(r for r in _rows_banner("pakemis_pass2_scorecard.csv")
               if r["outcome_id"] == "2b-historical-temporal-grade")
    m = re.search(r"\(([\d.]+) Mt of road fuel\) would land the nine-year figure at ([\d.]+)%",
                  row["note"])
    return float(m.group(1)) if field == "ocac_Mt" else float(m.group(2))


def _dung_relay():
    from pkinv.sectors.residential import combustion as res_combustion
    from pkinv.sectors.residential.data import ResidentialData
    return res_combustion.dung_air_dry_kg(ResidentialData())


def _generator_relay():
    from pkinv.sectors.residential.data import ResidentialData
    from pkinv.sectors.transport import road
    return road.generator_petrol_kt(ResidentialData())


def _waste_partition_relay():
    from pkinv.sectors.waste import swds
    from pkinv.sectors.waste.data import WasteData
    return swds.waste_generated(WasteData())


def _offroad_relay():
    from pkinv.sectors.transport import road
    from pkinv.sectors.transport.data import TransportData
    return road.off_road_TJ(TransportData())


# THE FOUR CLOSURES, as records rather than as a number in a docstring.
#
# This used to be `return 2.0` behind a lambda -- a literal wearing the costume of a metric,
# which is the Round 8 shape exactly: a check that reports passing while computing nothing.
# The count the manuscript prints is now derived from which modules each closure actually
# spans, so a closure that changed ends would move the printed number instead of leaving it
# to be maintained by hand.
#
# PRODUCER is the module that computes the quantity, CONSUMER the module that consumes it.
# Two cross; two are between categories inside one module, which is why "cross-sector" is
# the wrong name for the set (Section 4).
CLOSURES = [
    # (name, label, producer, consumer, physical_from, physical_to, accessor)
    #
    # producer/consumer is the SOFTWARE dependency: which module computes the number and
    # which module consumes it. physical_from/physical_to is the direction the quantity
    # moves between the sectors' books. The rc2 closure table printed the software arrow
    # for generator petrol -- Residential -> Transport -- under a column defined as "leaves
    # one sector's books and arrives on another's", which is exactly backwards: the petrol
    # leaves TRANSPORT's road control and arrives on RESIDENTIAL's books (1A3b -> 1A4b).
    # The two conventions coincide for dung and diverge for petrol, which is why the
    # registry carries both and a test compares the printed arrow against the physical one.
    ("dung-cake nitrogen", "sec:closure-dung",
     "agriculture", "residential", "agriculture", "residential", _dung_relay),
    ("household-generator petrol", "sec:closure-generator",
     "residential", "transport", "transport", "residential", _generator_relay),
    ("waste generation partition", "sec:closure-waste",
     "waste", "waste", "waste", "waste", _waste_partition_relay),
    ("road/off-road diesel partition", "sec:closure-offroad",
     "transport", "transport", "transport", "transport", _offroad_relay),
]


def _closure_count():
    return float(len(CLOSURES))


def _closures_crossing_modules():
    """How many of the asserted closures actually transfer between MODULES.

    Two do: agriculture's dung nitrogen arriving in residential, and transport's generator
    petrol arriving on residential's books. The waste fate partition is inside waste and the
    road/off-road split is inside transport, so calling all four "cross-sector" describes the
    architecture more grandly than it works.
    """
    return float(sum(1 for _n, _l, producer, consumer, _pf, _pt, _a in CLOSURES
                     if producer != consumer))


def _power_keycat_rows():
    """tab:keycat: level and variance shares for the two categories."""
    grid_var = _first_where("national_key_categories.csv",
                            "variance_share_pct_independent_approx",
                            ipcc_code="1.A.1.a")
    grid = _cell("power_totals_fy2023_24.csv", "category",
                 "Electricity and heat production", "co2e_Mt_AR5")
    captive = _cell("power_totals_fy2023_24.csv", "category",
                    "Captive gas self-generation (1A2)", "co2e_Mt_AR5")
    grid_pct = _first_where("power_uncertainty_fy2023_24.csv", "approach1_pct_grouped",
                            category="Electricity and heat production")
    cap_pct = _first_where("power_uncertainty_fy2023_24.csv", "approach1_pct_grouped",
                           category="Captive gas self-generation (1A2)")
    cap_var = grid_var * ((captive * cap_pct) / (grid * grid_pct)) ** 2
    return [[100.0 * grid / _sector("TOTAL"), grid_var],
            [100.0 * captive / _sector("TOTAL"), cap_var]]


def _residential_dung_chain():
    """The nitrogen -> VS -> TS ledger chain, computed by the engine itself."""
    from pkinv.sectors.residential.data import ResidentialData
    from pkinv.sectors.residential import combustion as rc
    data = ResidentialData()
    agri = rc.InventoryData()
    n_mt = sum(rc.diverted_n_by_species(agri).values()) / 1e9
    vs_mt = rc.dung_vs_kg(data, agri) / 1e9
    # rc67: dung_ts_kg follows the reference basis, the household survey, so this third
    # element is the survey cake less its moisture (9.62 Mt), no longer the ledger
    # chain's volatile solids with ash restored (51.69 Mt, which
    # pakemis_dung_residual_ledger.csv publishes).
    ts_mt = rc.dung_ts_kg(data, agri) / 1e9
    return n_mt, vs_mt, ts_mt


def _residential_dung_survey(which):
    """The household dung quantities the residential paper states, from the products.

    `household`: air-dry cake burned in households under the reference (Mt), the dung
    ledger's configuration-S household row. `diverted`: what agriculture diverts (Mt).
    `unresolved`: the diverted cake with no observed household destination (Mt).
    `round_ratio`: the 2024-25 round's per-household quantity over the 2018-19 round's,
    on the household counts the survey series itself is built on.
    """
    if which == "round_ratio":
        from pkinv.sectors.residential import hies, timeseries
        per_hh = {y: hies.national_quantity("dung_cake", s)[0] / timeseries.households(y)
                  for y, s in ((2019, "hies2019"), (2025, "hies2025"))}
        return per_hh[2025] / per_hh[2019]
    pick = {"household": ("S", "Household combustion"),
            "diverted": ("both", "Diverted to fuel"),
            "unresolved": ("S", "UNRESOLVED")}[which]
    return float(next(r for r in _rows("residential_dung_ledger_2024.csv")
                      if r["configuration"] == pick[0]
                      and r["claimant"].startswith(pick[1]))["Mt_air_dry"])


def _residential_config(configuration, column):
    """One cell of residential_configurations_2024.csv: S is the reference (household
    dung from the survey), L the configuration in which households burn all the diverted
    dung."""
    return float(next(r for r in _rows("residential_configurations_2024.csv")
                      if r["configuration"] == configuration)[column])


def _residential_dung_diag(survey, column):
    """One dung-cake cell of the HIES diagnostics table (design SE, tail shares)."""
    return float(next(r for r in _data_rows(os.path.join(
        "activity", "residential", "hies", "hies_diagnostics.csv"))
        if r["fuel"] == "dung_cake" and r["survey"] == survey)[column])


def _residential_ccac(item):
    """One row of the CCAC particulate bridge, matched on the start of its item label."""
    return float(next(r for r in _rows("residential_ccac_bridge_2024.csv")
                      if r["item"].startswith(item))["pm25_kt"])


def _agri_air_nh3_split():
    """NH3 by GROUP: the Wave A disaggregation gave the atoms product, species-stage
    and crop suffixes; the paper's split is over the groups, so rows sum by the
    parenthetical-stripped prefix (and housing/yard/storage fold into the historical
    'housing and storage' bucket the prose names)."""
    got = {}
    for r in _rows("air_pollutants_2024.csv"):
        if r["pollutant"] != "NH3":
            continue
        group = r["subitem"].rsplit(" (", 1)[0]
        if group in ("NH3 - housing", "NH3 - yard", "NH3 - storage"):
            group = "NH3 - housing and storage"
        got[group] = got.get(group, 0.0) + float(r["emissions_kt"])
    return got


def _nh3_district(district):
    """One district's agricultural NH3 (kt) from the held air-district product."""
    return sum(float(r["emissions_kt"]) for r in _rows("air_pollutants_district_2024.csv")
               if r["pollutant"] == "NH3" and r["district"] == district)


def _agri_districttop_named(district):
    """The engine's total for one district (rc42: the prose names the district beside each
    number, so a re-ranking cannot be papered over by an ordinal repair)."""
    got = {}
    for r in _rows("district_totals_2024.csv"):
        got[r["district"]] = got.get(r["district"], 0.0) + float(r["co2e_Mt_AR5"])
    return got[district]


def _karachi_census(column):
    """Karachi division's 2024 census head count: the seven census districts that resolve
    onto the one Karachi polygon."""
    from pkinv.core import adm2
    canonical = adm2.load_canonical()
    total = 0.0
    for r in _data_rows(os.path.join("activity", "livestock_district_2024.csv")):
        unit = canonical[adm2.resolve(r["district"])]
        if unit["province_id"] == "Sindh" and unit["shape_name"] == "Karachi":
            total += float(r[column] or 0.0)
    return total


def _agri_districttop_rows():
    """tab:districttop: rank + Mt for the eleven largest districts."""
    got = {}
    for r in _rows("district_totals_2024.csv"):
        key = (r["district"], r["province"])
        got[key] = got.get(key, 0.0) + float(r["co2e_Mt_AR5"])
    top = sorted(got.items(), key=lambda kv: kv[1], reverse=True)[:15]
    return [[float(i + 1), v] for i, (_k, v) in enumerate(top)]


# ---------------------------------------------------------------------------
# PROSE DESCRIBING A SUPERSEDED ARCHITECTURE
#
# Round 8 replaced the row-level correlation model with a parameter dependency graph: a
# component's draw is now the product of one multiplier per shared parameter that enters it,
# times a residual private to the row. The abstract, the introduction and Section 7.3 describe
# that model. Section 3.1, the closing paragraph of Section 7 and Table 5's caption still
# described its predecessor -- in the present tense, calling the parameter representation "the
# next revision of this machinery" while core/parameters.py was in the same release.
#
# An external reviewer read those paragraphs and concluded the engine had not been built. The
# claim was true and the paper denied it.
#
# An architectural claim is unguardable until it carries a number, so the repair has two
# halves: ban the superseded sentences while the engine contradicts them, and make the live
# model print a count that a claim can be anchored to.
_DECOMPOSITION = []


def _decomposition():
    """The per-row parameter decomposition the published Monte Carlo actually draws."""
    if not _DECOMPOSITION:
        from pkinv.core import parameters, registry
        comps, _cats, _sectors = registry.build_all()
        _DECOMPOSITION.append(parameters.decompose(comps))
    return _DECOMPOSITION[0]


def _multi_group_component_count():
    return float(sum(1 for _c, shared, _r, _o in _decomposition() if len(shared) > 1))


def _decomposed_component_count():
    return float(len(_decomposition()))


def _named_parameter_component_count():
    return float(sum(1 for _c, shared, _r, _o in _decomposition() if shared))


def _parameter_registry(which):
    """Sizes of the parameter registry, and of the part of it the published run draws.

    The registry declares far more groups than any one run uses, because a group with a single
    member or no usable sigma carries no variance. The paper quotes the DRAWN counts, which
    are the ones that can correlate anything.
    """
    from pkinv.core import parameters
    if which == "parameters":
        return float(len(parameters.registry()))
    drawn = collections.Counter()
    for _c, shared, _r, _o in _decomposition():
        # Count ROWS per group. Counter.update(dict) would add the sigmas instead, which
        # looks identical and answers a different question.
        for group in shared:
            drawn[group] += 1
    if which == "drawn_groups":
        return float(len(drawn))
    if which == "shared_groups":
        return float(sum(1 for _g, n in drawn.items() if n > 1))
    raise KeyError(which)


def _sobol_samples():
    from pkinv.report import variance_attribution
    return float(variance_attribution.N_SAMPLES)




def _over_decomposed_component_count():
    """Rows whose named parameters imply MORE variance than the component declares.

    core.parameters reports these rather than clipping them, by design: it is a disagreement
    between the registry and a sector's own uncertainty, and clipping would hide it.
    """
    return float(sum(1 for _c, _s, _r, over in _decomposition() if over))


# =============================================================================================
# THE OCTOBER 2026 COMPACT MANUSCRIPT, now v2 (paper_national/versions/v3/paper.tex);
# anchored to the national-v3 document rather than to the shipped version's supplement,
# which is where these 134 claims sat while both files shared one directory
#
# The rewrite restates the inventory in one file. It prints ~110 quantities, and when it
# arrived every one of them was prose: the coverage sweep reported 169 printed quantities
# "checked against nothing" across it and the technical supplement. A number that no getter
# resolves is exactly the failure this registry was built for - the release-integrity review
# that created it found a manuscript quoting 81 combinations where the table said 82.
#
# The helpers below exist so that restating a quantity does not DEFINE it a second time.
# =============================================================================================


def _mc_interval_width():
    """The published 95% interval's width, from the two endpoints that bound it.

    Derived from the same two claims the abstract and the conclusion already bind, rather
    than registered as a third independent number: a width that could drift from its own
    endpoints would be worse than no width at all.
    """
    rows = {r["scenario"]: r for r in
            read_rows("outputs/national_uncertainty_montecarlo.csv")
            if r.get("scope") == "national" and r.get("name") == "TOTAL"}
    r = rows["within_sector"]
    return float(r["P97.5_Mt"]) - float(r["P2.5_Mt"])


def _rebase_gross():
    """(smallest, largest) per-period gross mass the curated-district re-base moved.

    Read from outputs/pakemis_spatial_rebase_rc44.csv, which is the product that measured
    it and asserts the invariants beside it.
    """
    gross = [float(r["gross_Mt_AR5"]) for r in
             read_rows("outputs/pakemis_spatial_rebase_rc44.csv")
             if r["rebase"] == "rc63 curated station district"
             and r["product"] == "pakemis_adm2_sector_by_year.csv"
             and (r["gross_Mt_AR5"] or "").strip()]
    if not gross:
        raise KeyError("the re-base product carries no per-period gross rows for rc63")
    return min(gross), max(gross)


def _configuration(config_id, column):
    """One column of one row of outputs/national_configurations.csv."""
    for row in read_rows("outputs/national_configurations.csv"):
        if row["configuration_id"] == config_id:
            value = row[column]
            if value in ("", None):
                raise KeyError("%s has no %s" % (config_id, column))
            return float(value)
    raise KeyError("national_configurations.csv has no %r row" % config_id)


def _reference_grid():
    """The reference's booked grid figure: the legacy control's value less its own delta.

    Derived rather than read, because the reference row carries no alternative_value_Mt of
    its own - it IS the baseline. This is the same derivation the product's own family_role
    now uses, so the paper and the label cannot disagree.
    """
    return (_configuration("power_table3_legacy_control", "alternative_value_Mt")
            - _configuration("power_table3_legacy_control", "national_delta_Mt"))


def _sewer_population():
    """(sewer-connected millions, total millions, total/sewered) on the reference basis.

    The sanitation split is held at its JMP year and the population at the reference
    year's, which is what the engine does; computing it here from the same two tables is
    why the supplement's three figures cannot drift from the engine one at a time.
    """
    from pkinv.sectors.waste.data import WasteData
    data = WasteData()
    year = max(r["year"] for r in data.population)
    rows = [r for r in data.population if r["year"] == year]
    urban = sum(r["pop_urban"] for r in rows)
    rural = sum(r["pop_rural"] for r in rows)
    jmp = max(y for y, _setting in data.sanitation)
    sewered = (urban * float(data.sanitation[(jmp, "Urban")]["sewer"])
               + rural * float(data.sanitation[(jmp, "Rural")]["sewer"]))
    total = urban + rural
    return (sewered / 1e6, total / 1e6, total / sewered)


def _surrogate_samples():
    """The variance decomposition's sample size per matrix, from the module that uses it."""
    from pkinv.report import variance_attribution
    return float(variance_attribution.N_SAMPLES)


def _sweep(estimator, n):
    """One sum from the estimator sweep, by (estimator, sample size).

    Keyed on the PAIR: the file carries three sample sizes per estimator and the whole
    argument is that one of them is unstable across them, so a getter keyed on the
    estimator alone would resolve to whichever row came first.
    """
    for row in read_rows("outputs/pakemis_variance_estimator_sweep.csv"):
        if row["estimator"] == estimator and str(row["n_per_matrix"]) == str(n):
            return float(row["sum_of_indices"])
    raise KeyError("the sweep has no (%s, %s) row" % (estimator, n))


def _sweep_count(field, n):
    for row in read_rows("outputs/pakemis_variance_estimator_sweep.csv"):
        if row["estimator"] == "first_order" and str(row["n_per_matrix"]) == str(n):
            return float(row[field])
    raise KeyError("the sweep has no first_order row at n=%s" % n)


def _weights_basis(value=None):
    """Rows of the spatial weight registry, in total or for one spatial_time_basis class."""
    rows = read_rows("outputs/pakemis_spatial_weights_by_year.csv")
    if value is None:
        return len(rows)
    return sum(1 for r in rows if (r.get("spatial_time_basis") or "").strip() == value)


def _calibrations_inside_partial_or_large():
    """How many calibrations also carry a partial or large independence class.

    This is the overlap the supplement now names, and it is the exact size of the
    double-count the old breakdown made by adding two columns together.
    """
    return sum(1 for r in read_rows("data/shared/evidence/validation_catalog.csv")
               if (r.get("calibration_or_validation") or "").strip() == "calibration"
               and (r.get("independence_class") or "").strip() in ("partial", "large"))


def _catalog_count(field=None, value=None):
    """Rows of the validation catalog, optionally filtered, or rows with `field` non-blank.

    One getter for every count the supplement prints about the register, so the register
    and the prose cannot drift apart one number at a time.
    """
    rows = read_rows("data/shared/evidence/validation_catalog.csv")
    if field is None:
        return len(rows)
    if value is None:
        return sum(1 for r in rows if (r.get(field) or "").strip())
    return sum(1 for r in rows if (r.get(field) or "").strip() == value)


def _pick_freeze_n():
    """The pick-freeze sample size, from the module that runs it rather than retyped."""
    from pkinv.report import effluent_tail
    return effluent_tail.PICK_FREEZE_N


def _effluent_tail(row_kind, quantity):
    """One value from the effluent-tail diagnostic, by (row_kind, quantity).

    Keyed on the PAIR because `quantity` alone is not unique: `mean`, `median` and
    `variance` each appear once under `ensemble` and once under `surrogate`, and the whole
    point of the product is that those two differ. A getter keyed on the bare quantity
    would resolve to whichever row came first and would pass.
    """
    rows = read_rows("outputs/pakemis_effluent_tail_diagnostic.csv")
    for row in rows:
        if row["row_kind"] == row_kind and row["quantity"] == quantity:
            return float(row["value"])
    raise KeyError("pakemis_effluent_tail_diagnostic.csv has no (%s, %s) row"
                   % (row_kind, quantity))


def _as_registered(label):
    """Resolve through the claim that already owns this quantity, by its label.

    Three ways to anchor a restated number, and only one of them is safe. Copying the
    NUMBER is the defect the registry exists to prevent. Copying the getter's EXPRESSION
    creates a second definition that drifts from the first the next time one is re-anchored -
    and the drift is invisible, because both claims pass against their own copy. This
    resolves through the existing claim, so each quantity has exactly ONE definition and
    re-anchoring it moves every site that prints it.

    The lookup raises rather than returning None: if a label is renamed, every claim that
    borrows it fails loudly in test_claims, which is the behaviour wanted. A claim that
    silently stops resolving is a claim that silently stops guarding.
    """
    for entry in list(DOC_CLAIMS) + list(globals().get("LEGACY_NATIONAL_DOC_CLAIMS", ())):
        if entry[0] == label:
            return entry[4]()
    raise AssertionError(
        "no registered claim named %r to resolve through - a label was renamed and the "
        "claims that borrow it cannot see the quantity any more" % label)


def _reference_ef1():
    """The REFERENCE managed-soils EF1, read out of the main case's own scenario label.

    _faostat_ef1 above does this for the 2006 aggregate value. Both the reference 0.005 and
    the comparison 0.010 are now read from the same file, so the paper cannot print a factor
    pair that the sensitivity run did not actually use. Parked as a constant it would have
    been the one number in the substitution sentence that nothing checked.
    """
    for r in read_rows("outputs/eval/sensitivity.csv"):
        if r["scenario"].startswith("Main case"):
            m = re.search(r"EF1\s*=\s*([\d.]+)", r["scenario"])
            if m:
                return float(m.group(1))
    raise AssertionError("no main-case EF1 scenario in outputs/eval/sensitivity.csv")


def _window_change_pct():
    """The full-period increase as a percentage of the first year.

    Derived rather than read: no product ships this ratio, and the one existing getter whose
    value rounds to the same printed 17.1 is the appendix's "share not placed where it is
    physically emitted" - a completely different quantity that happens to round the same way.
    A value match would have anchored this sentence to that one. The arithmetic is the
    sentence's own: the change it just printed over the first year it just printed.
    """
    return 100.0 * (_as_registered("uncertainty window change")
                    / _as_registered("series covered total first year"))


def _series_year(label):
    """One period's covered total, by its printed label."""
    for r in _rows("pakemis_national_series.csv"):
        if r["row_kind"] == "covered_total" and r["period_label"] == label:
            return float(r["co2e_Mt_AR5"])
    raise AssertionError("no covered_total row for %s" % label)


def _series_year_min_after_peak():
    """The series MINIMUM among the periods after its maximum.

    This replaced _series_year_after_peak() on 2026-10-07. That getter returned peak+1,
    which was right while the peak was FY2021-22 and the fall was the very next year. The
    coal re-base moved the peak to FY2020-21 by 0.095 Mt, so peak+1 became FY2021-22 - the
    runner-up, 0.095 Mt below the peak - and the sentence's claim, that the series fell to
    its trough, was no longer the quantity being resolved. Keying on the minimum after the
    peak says what the sentence says and survives another move of the same size.
    """
    rows = [r for r in _rows("pakemis_national_series.csv")
            if r["row_kind"] == "covered_total"]
    rows.sort(key=lambda r: int(r["fiscal_end_year"]))
    peak = max(range(len(rows)), key=lambda i: float(rows[i]["co2e_Mt_AR5"]))
    after = rows[peak + 1:]
    if not after:
        raise AssertionError("the series peak is its last year; there is no fall after it")
    return min(float(r["co2e_Mt_AR5"]) for r in after)


def _streams_total():
    """Allocated plus unallocated source streams.

    The sectioned corpus deliberately left this DENOMINATOR out of its regex - its comment
    says so, after a hard-coded 190 unbound the claim when a withdrawn stream took it to 189.
    Letting the denominator be whatever the sentence says fixed the brittleness by removing
    the guard. Summing the two facts guards it without re-introducing a literal.
    """
    return (_product_fact("grid_streams_allocated")
            + _product_fact("grid_streams_unallocated"))


def _unallocated_share_pct():
    """Mass held above the grid, as a percentage of the national total."""
    return 100.0 * (_as_registered("national unallocated fy2023_24")
                    / _as_registered("national total"))


def _fgas_benchmark():
    """The external F-gas estimate, from the completeness-mass ledger's own screening row.

    The same 11.54 is a module-level constant in pkinv.report.completeness_mass, which
    asserts it against joint_uncertainty so the two surfaces give one answer. Reading the
    shipped row instead of importing the constant means the paper is anchored to what the
    ledger PUBLISHES, which is what a reader can check.
    """
    for r in _rows_banner("pakemis_completeness_mass.csv"):
        if r["ipcc_code"] == "2.F" and r["mass_basis"] == "external_benchmark_bound":
            return float(r["mass_high_Mt"])
    raise AssertionError("the completeness-mass ledger has lost its F-gas benchmark row")





def _dung_balance(element, field="S_side"):
    """One cell of the dung balance, by element. Substring match on the element name, because
    the priced-destination rows carry the destination in their own label."""
    for r in _rows_banner("pakemis_dung_balance.csv"):
        if r["element"].startswith(element):
            return r[field]
    raise AssertionError("no dung-balance element starting %r" % element)


def _dung_falsifiable(which):
    """The two numbers the falsifiable row states, parsed from the row it states them in.

    Parsed rather than recomputed here on purpose: the sentence in the companion and the row
    in the product must be the same arithmetic, and a second derivation in this file could
    agree with the engine while both disagreed with the published row.
    """
    if which == "implied_share":
        text = _dung_balance("Falsifiable implication", "L_side")
        return float(text.split("either ")[1].split(" pct")[0])
    if which == "observed_share":
        # FROM THE ROW THAT OWNS IT, not from this sentence. "the observed" appears twice in
        # the falsifiable text - once in "at the observed per-household intensity" - so a
        # split on it took the wrong half. The survey share is its own recomputed row.
        return float(_dung_balance("Survey users share"))
    if which == "intensity_factor":
        # "burn " appears twice in the sentence, so the match is on the whole phrase.
        # rc67: NOT the ratio of the two headline masses any more. The S-side headline is
        # the reference's interpolated quantity, and the factor is stated against the round
        # whose share and daily quantity the sentence quotes.
        return float(re.search(r"burn ([\d.]+) times the observed daily quantity",
                               _dung_balance("Falsifiable implication", "L_side")).group(1))
    raise AssertionError(which)


def _gas_closure(which):
    """The post-meter leak base's membership, from the gas-closure ledger itself.

    CLOSURE and GAP rows are excluded: they are identities and diagnostics over the delivered
    streams, not streams, and counting them would both inflate the stream count and
    double-count volume inside the total they check.
    """
    rows = [r for r in _rows_banner("national_gas_closure.csv")
            if r["annual_million_m3"] and not r["stream"].startswith(("CLOSURE", "GAP"))]
    inside = [r for r in rows if r["in_post_meter_leak_base"] == "yes"]
    outside = [r for r in rows if r["in_post_meter_leak_base"] == "no"]
    vol = lambda rs: sum(float(r["annual_million_m3"]) for r in rs)
    return {
        "streams": float(len(rows)), "total_volume": vol(rows),
        "inside_streams": float(len(inside)), "inside_volume": vol(inside),
        "inside_pct": 100.0 * vol(inside) / vol(rows),
        "outside_streams": float(len(outside)), "outside_volume": vol(outside),
        "feedstock_pct_of_base": 100.0 * vol(
            [r for r in inside if r["stream"] == "Fertilizer"]) / vol(inside),
    }[which]


def _gas_closure_variant(configuration, field="adjustment_Mt_co2e"):
    """The priced gross-delivered alternative, from the variant product."""
    for r in _rows_banner("national_gas_closure_variant.csv"):
        if r["configuration"] == configuration:
            return float(r[field])
    raise AssertionError("no gas-closure variant %r" % configuration)


def _rice_crosscheck(verdict=None, province=None, field="spam_gcd_gap_pp"):
    """The rice geography crosscheck: a count of unit rows, or one province's L1/2 figure.

    The supplement cited this instrument for two releases without giving its result, which is
    what the 23rd review caught. Every figure in that paragraph now resolves here.
    """
    rows = _rows_banner("pakemis_rice_geography_crosscheck.csv")
    if province is not None:
        for r in rows:
            if r["verdict"] == "summary" and r["province"] == province:
                return float(r[field])
        raise AssertionError("no summary row for province %r" % province)
    return float(sum(1 for r in rows if r["verdict"] == verdict))


def _gwp_ar5(gas):
    """One AR5 GWP-100 factor, from the engine's own table rather than a remembered number."""
    from pkinv.core.gwp import GWP
    return float(GWP["AR5"][gas])


def _btr(subject, field="ratio_pakemis_over_btr"):
    """One row of the year-matched comparison against Pakistan's own submission, by subject.

    Keyed on the SUBJECT rather than on the IPCC code, and that is not a convenience. The two
    accounts swap two codes - the submission books rice cultivation at 3.D and managed soils
    at 3.C, this inventory the other way round - so a getter keyed on the code would resolve
    the rice sentence to the soil row and the soil sentence to the rice row, and both would
    look plausible. The subject is the crosswalk's own primary key for exactly that reason.
    """
    for r in _rows_banner("pakemis_btr_comparison.csv"):
        if r["subject"] == subject:
            value = r[field]
            if value == "":
                raise AssertionError("the BTR comparison row %r has no %s; the tier does not "
                                     "admit one" % (subject, field))
            return float(value)
    raise AssertionError("no row named %r in the BTR comparison" % subject)


def _btr_tier_mass(tiers, field):
    """Total mass on one tier (or several) of the BTR comparison."""
    if isinstance(tiers, str):
        tiers = (tiers,)
    return sum(float(r[field]) for r in _rows_banner("pakemis_btr_comparison.csv")
               if r["tier"] in tiers and r[field] not in ("", None))

def _sobol_convergence(n, col):
    """One row of the held first-order convergence measurement, by sample size.

    The numbers this anchors are the EVIDENCE for withdrawing the first-order index, so they
    are the last place a stale figure should sit. They are held rather than rebuilt because
    the 131072 leg costs about four times the published attribution;
    scripts/measure_sobol_convergence.py reproduces them.
    """
    for r in _data_rows_nocomment("sobol_convergence.csv"):
        if int(r["samples_per_matrix"]) == n:
            return float(r[col])
    raise AssertionError("no %d-sample row in the Sobol convergence measurement" % n)

def _btr_gas(code, part):
    """A gas column of the held BTR transcription, by printed IPCC code.

    `part` is "co2" or "non_co2". The non-CO2 half exists as a question because the
    submission folds biomass burning into its land block: cropland's row mixes land-use CO2
    with fire CH4 and N2O, and only the second is comparable to this inventory's field
    burning. Raises rather than guessing where the row prints a dash for a gas, because the
    rendering cannot say which gas was dashed.
    """
    for r in _data_rows_nocomment("btr1_national_inventory.csv"):
        if r["btr_code"] != code:
            continue
        if part == "co2":
            if not r["co2_Mt_co2e"]:
                raise AssertionError("%s prints no CO2 cell" % code)
            return float(r["co2_Mt_co2e"])
        if not (r["ch4_Mt_co2e"] and r["n2o_Mt_co2e"]):
            raise AssertionError("%s prints no CH4/N2O split" % code)
        return float(r["ch4_Mt_co2e"]) + float(r["n2o_Mt_co2e"])
    raise AssertionError("no %s row in the BTR transcription" % code)

def _boundary_adjudication(cls):
    """How many audited stations carry one adjudication class."""
    return float(sum(1 for r in _rows_banner("pakemis_power_province_boundary_audit.csv")
                     if r.get("row_kind") == "station" and r.get("adjudication") == cls))

def _fgas_rate(stratum, field="shipped_operating_loss_pct_yr"):
    """One field of the F-gas leak-rate adjudication, by stratum."""
    for r in _rows_banner("pakemis_fgas_leak_rate_adjudication.csv"):
        if r["stratum"] == stratum:
            return float(r[field])
    raise AssertionError("no %r row in the F-gas leak-rate screening" % stratum)


def _fgas_range(stratum, column, end):
    for r in _rows_banner("pakemis_fgas_leak_rate_adjudication.csv"):
        if r["stratum"] == stratum:
            lo, hi = r[column].split("-")
            return float(lo if end == "lo" else hi)
    raise AssertionError("no %r row in the F-gas leak-rate screening" % stratum)


def _axis_fine_only(total=False):
    """Tables reading FINE AXIS ONLY against the published vintage, or how many there are.

    Counted from the product's working-tree rows, not its published ones: the claim the
    paper makes is about the tree it was built from.
    """
    rows = [r for r in _rows_banner("pakemis_release_axis_fingerprints.csv")
            if r["commit"] == "(working tree)"]
    if not rows:
        raise AssertionError("the axis product carries no working-tree row, so the "
                             "paper's count is anchored to nothing")
    if total:
        return float(len(rows))
    return float(sum(1 for r in rows
                     if r["verdict_against_the_published_vintage"].startswith("FINE AXIS ONLY")))


def _facility_licence(which):
    """Row counts of the published facility registry's own licence column.

    which is "total" or "odbl". Read from outputs/pakemis_facility_registry.csv rather
    than from the deposit manifest's reason string, so the paper's figures come from the
    data and not from the sentence that describes it.
    """
    rows = _rows("pakemis_facility_registry.csv")
    if which == "total":
        return float(len(rows))
    return float(sum(1 for r in rows if "odbl" in (r.get("licence") or "").lower()))




def _pointer_audit(verdict):
    """How many registered sources carry each pointer verdict, or checkability state."""
    rows = _rows_banner("pakemis_citation_pointer_audit.csv")
    if verdict == "scored":
        return float(sum(1 for r in rows if r["verdict"] in ("pointed", "unpointed")))
    if verdict.startswith("checkable:"):
        want = verdict.split(":", 1)[1]
        return float(sum(1 for r in rows if r["verdict"] == "pointed"
                         and r["pointer_checkable_here"].split(":")[0] == want))
    return float(sum(1 for r in rows if r["verdict"] == verdict))



def _minerals_screening(what):
    """Counts and worst cases from the minerals panel screening."""
    rows = _rows_banner("pakemis_minerals_panel_screening.csv")
    if what == "mineral_years":
        return float(len(rows))
    if what == "incomplete_but_covered":
        return float(sum(1 for r in rows if r["provinces_missing"] != "none"
                         and r["served_as_covered"] == "yes"))
    if what == "worst_served_share":
        return max(float(r["served_worst_month_share_pct"]) for r in rows)
    if what == "control_disagreements":
        return float(sum(1 for r in rows if r["control_agrees_with_panel"] == "NO"))
    if what.startswith("share:"):
        _tag, mineral, fy = what.split(":")
        for r in rows:
            if r["canonical_mineral"] == mineral and r["fiscal_year_start"] == fy:
                return float(r["panel_share_of_control_pct"])
        raise AssertionError("no %s FY%s row in the minerals screening" % (mineral, fy))
    if what == "max_rows_per_month":
        return float(max(max(int(n) for n in r["rows_per_month"].split(";"))
                         for r in rows))
    if what == "gas_duplication_ratio":
        quantity = {(r["canonical_mineral"], r["fiscal_year_start"]):
                    float(r["panel_quantity"]) for r in rows}
        return (quantity[("natural_gas", "2020")]
                / quantity[("natural_gas", "2018")])
    if what == "gas_oil_rows_per_month":
        picked = [r for r in rows if int(r["fiscal_year_start"]) == 2020
                  and r["canonical_mineral"] in ("natural_gas", "crude_oil")]
        return float(max(max(int(n) for n in r["rows_per_month"].split(";"))
                         for r in picked))
    raise AssertionError("unknown minerals-screening quantity %r" % what)


def _forest_screen(quantity, field="value"):
    """One row of the forest-land sign screening, by quantity label."""
    for r in _rows_banner("pakemis_forest_flux_adjudication.csv"):
        if r["quantity"] == quantity:
            return float(r[field])
    raise AssertionError("no %r row in the forest screening" % quantity)


def _forest_step():
    """The FAOSTAT forest-area step, which the screening publishes as identical values.

    Stored as "20.786/20.786/20.786" because the CONSTANCY is the finding; a single number
    would lose it. This returns the common value and asserts they are in fact one, so the
    paper's "exactly" cannot survive the series starting to vary.
    """
    for r in _rows_banner("pakemis_forest_flux_adjudication.csv"):
        if r["quantity"].startswith("FAOSTAT area step"):
            parts = {p for p in r["value"].split("/")}
            if len(parts) != 1:
                raise AssertionError(
                    "the FAOSTAT area steps now differ (%s), so the paper's \"exactly\" is "
                    "no longer true and the passage must change" % r["value"])
            return float(parts.pop())
    raise AssertionError("the screening publishes no FAOSTAT area step")


def _forest_conversion(year):
    """FAOSTAT's net forest conversion area for one year, from the screening's own note.

    The screening carries it beside each area row rather than as a row of its own, because
    the pair is the point: an area that rises while conversion is exactly zero is the shape
    of the assumption, not two independent facts.
    """
    for r in _rows_banner("pakemis_forest_flux_adjudication.csv"):
        if r["quantity"] == "forest area" and r["period"] == "CY%d" % year:
            import re as _re
            m = _re.search(r"net forest conversion in the same year: ([\d.]+) kha", r["note"])
            if m:
                return float(m.group(1))
    raise AssertionError("the screening carries no net forest conversion for %d" % year)


# --- rc67 getters: the products the reference re-base added --------------------------------
#
# Each reads one row of one product. They exist because the rewritten v3 paragraphs state
# quantities (the dung fate, the wastewater method comparison, the ensemble's drivers, the
# residential and waste scenarios) that no earlier claim owned.

def _dung_fate(period_id, variant_id, column):
    """One cell of outputs/pakemis_dung_fate_by_year.csv."""
    for r in _rows_banner("pakemis_dung_fate_by_year.csv"):
        if r["period_id"] == period_id and r["variant_id"] == variant_id:
            return float(r[column])
    raise KeyError((period_id, variant_id))


def _uncertainty_driver(grain, name, column):
    """One cell of outputs/pakemis_uncertainty_drivers.csv; shares are fractions there."""
    for r in _rows_banner("pakemis_uncertainty_drivers.csv"):
        if r["grain"] == grain and r["name"] == name:
            return float(r[column])
    raise KeyError((grain, name))


def _wastewater_method(scope, method, column, period_id="FY2023-24"):
    """One cell of outputs/pakemis_wastewater_method_comparison.csv."""
    for r in _rows_banner("pakemis_wastewater_method_comparison.csv"):
        if (r["scope"], r["method"], r["period_id"]) == (scope, method, period_id):
            return float(r[column])
    raise KeyError((scope, method, period_id))


def _waste_scenario(name):
    """The waste sector total under one structural scenario, Mt CO2e."""
    for r in _rows("waste_uncertainty_scenarios_2024.csv"):
        if r["structural_scenario"] == name:
            return float(r["deterministic"])
    raise KeyError(name)


def _residential_scenario(name):
    """The residential sector total under one structural scenario, Mt CO2e."""
    for r in _rows("residential_uncertainty_scenarios_2024.csv"):
        if r["structural_scenario"] == name:
            return float(r["deterministic"])
    raise KeyError(name)


def _hies_dung_rate_ratio():
    """Dung per household in the 2024-25 round over the 2018-19 round, on each round's own
    weighted households (33.2 and 39.9 million)."""
    totals = {r["survey"]: float(r["annual_total"])
              for r in _data_rows("activity/residential/hies/hies_national_totals.csv")
              if r["fuel"] == "dung_cake"}
    return (totals["hies2025"] / 39.9e6) / (totals["hies2019"] / 33.2e6)


def _coal_bound(test_id, pattern):
    """A percentage read out of one row of the power reference audit's rescue requirement."""
    for r in read_rows("outputs/pakemis_power_reference_audit.csv", comments=True):
        if r["test_id"] == test_id:
            m = re.search(pattern, r["rescue_requirement"])
            if m:
                return float(m.group(1))
    raise KeyError((test_id, pattern))


def _data_param(relpath, param, column):
    """One column of one row of a parameter file under data/ (value, lower or upper)."""
    for r in _data_rows(relpath):
        if r["param"] == param:
            return float(r[column])
    raise KeyError((relpath, param))


def _gas_crosswalk(stream, column, period_id="FY2023-24"):
    """One cell of outputs/pakemis_gas_flow_crosswalk.csv."""
    for r in _rows_banner("pakemis_gas_flow_crosswalk.csv"):
        if r["period_id"] == period_id and r["stream"] == stream:
            return float(r[column])
    raise KeyError((period_id, stream))


def _hies_concentration(survey):
    """The share of a round's reported dung held by its top five per cent of reporting
    households, in per cent, from the round's own diagnostics."""
    for r in _data_rows("sectors/residential/evidence/hies/hies_diagnostics.csv"):
        if r["survey"] == survey and r["fuel"] == "dung_cake":
            return 100.0 * float(r["top5pct_hh_share_of_total"])
    raise KeyError(survey)


# rc68 replaces the national article/supplement and revises the maintained
# technical report. Preserve former sentence-level claims as an explicit archive;
# only quantities/phrases actually present in an included source can be current
# prose claims. Every new generated national macro is independently checked by
# test_claim_matrix; the quantity-coverage sweep still rejects unregistered
# literal results. Sector claim and numerical-product audits remain unchanged.
def _current_national_sentence(doc, section, pattern, literal=False):
    revised = _RETIREMENTS.get("revised_sector_sections", {})
    if doc not in ("national", "national-supplement", "national-v3") and section not in revised.get(doc, []):
        return True
    from paper_numbers._common import _doc_path, active_sections
    if section not in active_sections(doc):
        return False
    path = _doc_path(doc, section)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if literal:
        return pattern in text
    return re.search(pattern, text) is not None

_RETIREMENTS = json.load(open(os.path.join(os.path.dirname(__file__), "retired_sentence_claims_rc68.json")))

def _declared_retired(kind, row, literal=False):
    return row[1] + "/" + row[0] in _RETIREMENTS[kind] and not _current_national_sentence(row[1], row[2], row[3], literal=literal)

LEGACY_NATIONAL_DOC_CLAIMS = tuple(r for r in DOC_CLAIMS if _declared_retired("doc_claim_ids", r))
DOC_CLAIMS = [r for r in DOC_CLAIMS if not _declared_retired("doc_claim_ids", r)]
LEGACY_NATIONAL_COMPARATIVE_CLAIMS = tuple(r for r in CLAIMS if _declared_retired("comparative_claim_ids", r, literal=True))
CLAIMS = [r for r in CLAIMS if not _declared_retired("comparative_claim_ids", r, literal=True)]
LEGACY_NATIONAL_MOVEMENTS = tuple(r for r in MOVEMENTS if _declared_retired("movement_ids", r))
MOVEMENTS = [r for r in MOVEMENTS if not _declared_retired("movement_ids", r)]


def _current_core_period_count():
    from pkinv.core.reporting_window import CORE_FY_STARTS
    return len(CORE_FY_STARTS)

def _current_air_species_count():
    from pkinv.report.air_annual import CORE7
    return len(CORE7)

def _current_configuration_count():
    from pkinv.core.configurations import ALL
    return len(ALL)

CLAIMS.extend([
    ("integrated ten fiscal years", "national-v3", "paper.tex", "ten fiscal years", "count_equals", 10, 0., _current_core_period_count),
    ("integrated three native greenhouse gases", "national-v3", "paper.tex", "The greenhouse gases are", "count_equals", 3, 0.,
     lambda: len({r["gas"] for r in _rows("pakemis_ghg_configuration_atoms.csv") if r["gas"]})),
    ("integrated seven core air species", "national-v3", "paper.tex", "The core air panel contains", "count_equals", 7, 0., _current_air_species_count),
    ("integrated four coherent configurations", "national-v3", "paper.tex", "These four configurations describe structural choices", "count_equals", 4, 0., _current_configuration_count),
    ("no provisional year in common trend", "national-v3", "paper.tex", "provisional FY2025--26 sources are excluded", "count_equals", 0, 0.,
     lambda: len([r for r in _rows("pakemis_ghg_configuration_atoms.csv") if r["period_id"] == "FY2025-26"])),
])


def _native_waste_interval(column):
    rows = _rows("pakemis_ghg_conditional_uncertainty.csv")
    selected = [r for r in rows if r["period_id"] == "FY2023-24" and r["configuration_id"] == "S_TAN"
                and r["sector_id"] == "waste" and r["species_or_metric"] == "CO2e_AR5"
                and r["dependence_case"] == "persistent_parameters"]
    if len(selected) != 1:
        raise AssertionError("expected one current native waste interval")
    return float(selected[0][column])

for _section in ("00_abstract.tex", "06_results.tex", "S1_uncertainty.tex"):
    DOC_CLAIMS.extend([
        ("native conditional waste lower " + _section, "waste", _section,
         r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\}",
         lambda: _native_waste_interval("P2_5_quantity"), 0.),
        ("native conditional waste upper " + _section, "waste", _section,
         r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\}",
         lambda: _native_waste_interval("P97_5_quantity"), 0.),
    ])
DOC_CLAIMS.extend([
    ("native waste current draw count", "waste", "S1_uncertainty.tex", r"uses \\num\{(\d+)\} realisations", lambda: _native_waste_interval("draws"), 0.),
    ("native waste current seed", "waste", "S1_uncertainty.tex", r"seed \\num\{(\d+)\}", lambda: _native_waste_interval("seed"), 0.),
    ("current admitted IPPU module abstract", "ippu", "00_abstract.tex", r"total is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _cell("ippu_totals_2024.csv", "category", "IPPU reference total", "co2e_Mt_AR5"), 0.),
    ("current admitted IPPU module results", "ippu", "06_results.tex", r"to the \\SI\{([\d.]+)\}\{\\mega\\tonne\} module total",
     lambda: _cell("ippu_totals_2024.csv", "category", "IPPU reference total", "co2e_Mt_AR5"), 0.),
])


def _native_fugitives_interval(column):
    selected = [r for r in _rows("pakemis_ghg_conditional_uncertainty.csv")
                if r["period_id"] == "FY2023-24" and r["configuration_id"] == "S_TAN"
                and r["sector_id"] == "fugitives" and r["species_or_metric"] == "CO2e_AR5"
                and r["dependence_case"] == "persistent_parameters"]
    if len(selected) != 1:
        raise AssertionError("expected one current native fugitives interval")
    return float(selected[0][column])

DOC_CLAIMS.extend([
    ("native conditional fugitives lower", "fugitives", "06_results.tex",
     r"reference 2\.5th--97\.5th percentiles are \\SIrange\{([\d.]+)\}\{[\d.]+\}",
     lambda: _native_fugitives_interval("P2_5_quantity"), 0.),
    ("native conditional fugitives upper", "fugitives", "06_results.tex",
     r"reference 2\.5th--97\.5th percentiles are \\SIrange\{[\d.]+\}\{([\d.]+)\}",
     lambda: _native_fugitives_interval("P97_5_quantity"), 0.),
])


def _agriculture_input_factor(category, item):
    from pkinv.sectors.agriculture.ef_library import InventoryData
    return InventoryData().efv(category, item)

DOC_CLAIMS.extend([
    ("current TAN cattle fraction", "agriculture", "04c_shared_ledger.tex", r"\\num\{([\d.]+)\} for cattle,", lambda: _agriculture_input_factor("nh3_emep_tan", "dairy_cattle"), 0.),
    ("current grazing small-ruminant fraction", "agriculture", "04c_shared_ledger.tex", r"\\num\{([\d.]+)\} for small ruminants", lambda: _agriculture_input_factor("nh3_emep_grazing", "sheep"), 0.),
    ("soil NOx native nitrogen fraction", "agriculture", "04c_shared_ledger.tex", r"estimated as approximately \\SI\{([\d.]+)\}\{\\percent\}", lambda: 100 * _agriculture_input_factor("soils", "NOx_frac_of_applied"), 0.),
])

DOC_CLAIMS.extend([
    ("railway ODbL alternative audited length fraction", "railways", "04_methods.tex",
     r"line-kilometres, \\SI\{([\d.]+)\}\{\\percent\} of the Year Book",
     lambda: 100 * _cell("railways_network_audit_2024.csv", "item", "active_total", "km")
             / __import__("pkinv.sectors.railways.data", fromlist=["RailwaysData"]).RailwaysData().p("route_km"), 0.),
    ("residential matched-scope relative difference", "residential", "05_validation.tex",
     r"---within\s*\\SI\{([\d.]+)\}\{\\percent\}",
     lambda: 100 * (_cell("residential_official_comparison_2024.csv", "benchmark_id", "crt2022", "own_Mt_co2e")
                   / _cell("residential_official_comparison_2024.csv", "benchmark_id", "crt2022", "official_Mt_co2e") - 1), 0.),
])


# =========================================================================================
# rc68, 15 October 2026: the integrated article's literal quantities. Every share, ratio and
# interval the revised paper.tex prints outside the generated macros resolves here from the
# released products, at the precision printed (tolerance 0 beyond half a unit in the last
# digit). A product moved by later work fails the claim rather than the sentence drifting.
# =========================================================================================
_V3_REF, _V3_LATEST, _V3_FIRST = "FY2023-24", "FY2024-25", "FY2015-16"


def _v3_air(period, pollutant, keep=lambda r: True, configuration="S_TAN"):
    return sum(float(r["emissions_Gg"]) for r in _rows("pakemis_air_annual_fy2015_16_fy2024_25.csv")
               if r["period_id"] == period and r["configuration_id"] == configuration
               and r["pollutant"] == pollutant and keep(r))


def _v3_air_share(pollutant, keep, period=_V3_REF):
    return 100.0 * _v3_air(period, pollutant, keep) / _v3_air(period, pollutant)


def _v3_ghg(period, keep=lambda r: True, configuration="S_TAN"):
    return sum(float(r["co2e_Mt_AR5"]) for r in _rows("pakemis_ghg_configuration_atoms.csv")
               if r["period_id"] == period and r["configuration_id"] == configuration
               and r["co2e_Mt_AR5"] and keep(r))


def _v3_ghg_share(keep, period=_V3_REF):
    return 100.0 * _v3_ghg(period, keep) / _v3_ghg(period)


_V3_MIDDLE_MODULES = ("power", "transport", "waste", "ippu", "residential", "fugitives", "industry")


def _v3_configuration_totals(period=_V3_REF):
    from pkinv.core.configurations import ALL
    return [_v3_ghg(period, configuration=c) for c in ALL]


def _v3_trend_rows(dependence="persistent_parameters"):
    return [r for r in _rows("pakemis_ghg_trend_uncertainty.csv")
            if r["configuration_id"] == "S_TAN" and r["sector_id"] == "national_covered"
            and r["species_or_metric"] == "CO2e_AR5" and r["dependence_case"] == dependence]


def _v3_endpoint(column):
    rows = [r for r in _v3_trend_rows() if r["start_period"] == _V3_FIRST and r["end_period"] == _V3_LATEST]
    assert len(rows) == 1, "expected one paired endpoint change"
    return float(rows[0][column])


def _v3_steps(dependence=None):
    """Consecutive annual changes; with a dependence case, those whose 95 % interval excludes zero."""
    from pkinv.core.reporting_window import CORE_FY_STARTS
    labels = ["FY%d-%02d" % (y, (y + 1) % 100) for y in CORE_FY_STARTS]
    pairs = set(zip(labels, labels[1:]))
    if dependence is None:
        return len(pairs)
    return sum(1 for r in _v3_trend_rows(dependence) if (r["start_period"], r["end_period"]) in pairs
               and (float(r["P2_5_quantity"]) > 0 or float(r["P97_5_quantity"]) < 0))


def _v3_air_interval(pollutant, column, period=_V3_REF):
    rows = [r for r in _rows("pakemis_air_conditional_uncertainty.csv")
            if r["period_id"] == period and r["configuration_id"] == "S_TAN" and r["pollutant"] == pollutant
            and r["sector_id"] == "national_covered" and r["dependence_case"] == "persistent_parameters"]
    assert len(rows) == 1
    return float(rows[0][column])


def _v3_structural(scenario, pollutant, column="case_covered_Gg", period=_V3_REF):
    rows = [r for r in _rows("pakemis_air_structural_sensitivities.csv")
            if r["period_id"] == period and r["configuration_id"] == "S_TAN"
            and r["scenario_id"] == scenario and r["pollutant"] == pollutant]
    assert len(rows) == 1
    return float(rows[0][column])


def _v3_btr(subject):
    rows = [r for r in _csv_rows("pakemis_btr_comparison.csv") if r["subject"] == subject]
    assert len(rows) == 1, subject
    return float(rows[0]["ratio_pakemis_over_btr"])


def _v3_edgar_industry(species, boundary):
    """PakEmis industry over EDGAR 1.A.2 (fossil, or fossil plus biomass) plus cement 2.A.1,
    FY2021-22 - the latest complete fiscal blend, exactly as Fig. 13 draws it."""
    row = next(r for r in _csv_rows("pakemis_industry_air_edgar_comparison.csv")
               if r["period_id"] == "FY2021-22" and r["species"] == species)
    pak = float(row["engine_industry_kt"])
    fossil = float(row["edgar_1a2_fossil_plus_2a1_kt"])
    if boundary == "fossil":
        return pak / fossil
    cement = fossil - float(row["edgar_1a2_fossil_kt"])
    return pak / (float(row["edgar_1a2_fossil_bio_kt"]) + cement)


def _v3_htap(sector, pick):
    ratios = [float(r["ratio_pakemis_over_htap"]) for r in _rows("pakemis_air_htap_comparison.csv")
              if r["configuration_id"] == "S_TAN" and r["pollutant"] == "NH3"
              and r["comparison_status"] == "sector_comparison" and r["comparison_sector"] == sector]
    assert len(ratios) == 5
    return pick(ratios)


def _v3_draws():
    rows = {r["draws"] for r in _rows("pakemis_ghg_conditional_uncertainty.csv")}
    assert len(rows) == 1
    return float(rows.pop())


def _v3_htap_rows(group, pollutant, configuration="S_TAN"):
    rows = [r for r in _csv_rows("pakemis_air_htap_species_comparison.csv")
            if r["configuration_id"] == configuration and r["comparison_group"] == group
            and r["pollutant"] == pollutant and r["comparison_status"] == "process_comparison"]
    assert len(rows) == 5, (group, pollutant, configuration)
    return rows


def _v3_htap_species(group, pollutant, pick, configuration="S_TAN"):
    return pick(float(r["ratio_pakemis_over_htap"]) for r in _v3_htap_rows(group, pollutant, configuration))


def _v3_htap_species_year(group, pollutant, period):
    return next(float(r["ratio_pakemis_over_htap"]) for r in _v3_htap_rows(group, pollutant)
                if r["period_id"] == period)


def _v3_residue_factor_ratios():
    """HTAP's residue-burning mass expressed as a factor on PakEmis's own burned dry matter,
    over PakEmis's factor, for every species and year compared."""
    return [float(r["htap_equivalent_factor_at_pakemis_activity"]) / float(r["pakemis_implied_factor"])
            for r in _csv_rows("pakemis_air_htap_species_comparison.csv")
            if r["configuration_id"] == "S_TAN" and r["comparison_group"] == "agricultural_residue_burning"
            and r["comparison_status"] == "process_comparison" and r["pakemis_implied_factor"]]


def _v3_diesel_ppm(fiscal_end_year):
    return float(next(r["ppm_central"] for r in _data_rows_nocomment("activity/transport/fuel_sulfur_by_year.csv")
                      if r["fuel"] == "Diesel" and int(r["fiscal_end_year"]) == fiscal_end_year))


_V3 = ("national-v3", "paper.tex")
DOC_CLAIMS.extend([(label,) + _V3 + tuple(rest) for label, *rest in [
    ("integrated CH4 share of aggregate", r"Methane contributes \\SI\{(\d+)\}\{\\percent\}",
     lambda: _v3_ghg_share(lambda r: r["gas"] == "CH4"), 0.),
    ("integrated agriculture share of aggregate", r"aggregate, and agriculture \\SI\{(\d+)\}\{\\percent\}",
     lambda: _v3_ghg_share(lambda r: r["sector_id"] == "agriculture"), 0.),
    ("integrated middle modules lowest share", r"each contribute between \\SI\{(\d+)\}\{\\percent\}",
     lambda: min(_v3_ghg_share(lambda r, m=m: r["sector_id"] == m) for m in _V3_MIDDLE_MODULES), 0.),
    ("integrated middle modules highest share", r"each contribute between \\SI\{\d+\}\{\\percent\} and \\SI\{(\d+)\}\{\\percent\}",
     lambda: max(_v3_ghg_share(lambda r, m=m: r["sector_id"] == m) for m in _V3_MIDDLE_MODULES), 0.),
    ("integrated configuration span low", r"aggregate ranges from \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: min(_v3_configuration_totals()), 0.),
    ("integrated configuration span high", r"aggregate ranges from \\SI\{[\d.]+\}\{\\mega\\tonne\} to \\SI\{([\d.]+)\}",
     lambda: max(_v3_configuration_totals()), 0.),
    ("integrated PM2.5 household share", r"Household fuel combustion accounts for \\SI\{(\d+)\}",
     lambda: _v3_air_share("PM2.5", lambda r: r["sector_id"] == "residential"), 0.),
    ("integrated PM2.5 waste burning share", r"open burning of waste for \\SI\{(\d+)\}",
     lambda: _v3_air_share("PM2.5", lambda r: r["sector_id"] == "waste"), 0.),
    ("integrated PM2.5 residue burning share", r"crop-residue burning for \\SI\{(\d+)\}",
     lambda: _v3_air_share("PM2.5", lambda r: r["category"] == "Field burning of residues"), 0.),
    ("integrated NOx agriculture share", r"agriculture \(\\SI\{(\d+)\}\{\\percent\}, mainly",
     lambda: _v3_air_share("NOx", lambda r: r["sector_id"] == "agriculture"), 0.),
    ("integrated NOx transport share", r"road and other transport \(\\SI\{(\d+)\}",
     lambda: _v3_air_share("NOx", lambda r: r["sector_id"] == "transport"), 0.),
    ("integrated NOx household share", r"households \(\\SI\{(\d+)\}\{\\percent\}\) and industry",
     lambda: _v3_air_share("NOx", lambda r: r["sector_id"] == "residential"), 0.),
    ("integrated NOx industry share", r"and industry \(\\SI\{(\d+)\}",
     lambda: _v3_air_share("NOx", lambda r: r["sector_id"] == "industry"), 0.),
    ("integrated NH3 agriculture share", r"Agriculture supplies \\SI\{(\d+)\}",
     lambda: _v3_air_share("NH3", lambda r: r["sector_id"] == "agriculture"), 0.),
    ("integrated NH3 managed soils share", r"managed soils give \\SI\{(\d+)\}",
     lambda: _v3_air_share("NH3", lambda r: r["category"] == "Managed soils"), 0.),
    ("integrated NH3 manure share", r"manure management \\SI\{(\d+)\}\{\\percent\}\.",
     lambda: _v3_air_share("NH3", lambda r: r["category"] == "Manure management"), 0.),
    ("integrated SO2 industry share", r"cement kilns give \\SI\{(\d+)\}",
     lambda: _v3_air_share("SO2", lambda r: r["sector_id"] == "industry"), 0.),
    ("integrated SO2 power share", r"power oil and diesel \\SI\{(\d+)\}",
     lambda: _v3_air_share("SO2", lambda r: r["sector_id"] == "power"), 0.),
    ("integrated CO household share", r"Households dominate CO \(\\SI\{(\d+)\}",
     lambda: _v3_air_share("CO", lambda r: r["sector_id"] == "residential"), 0.),
    ("integrated NMVOC road share", r"dominates NMVOC \(\\SI\{(\d+)\}",
     lambda: _v3_air_share("NMVOC", lambda r: r["sector_id"] == "transport"), 0.),
    ("integrated paired endpoint change", r"the change is \\SI\{([\d.]+)\}\{\\mega\\tonne\}",
     lambda: _v3_endpoint("deterministic_change"), 0.),
    ("integrated paired endpoint low", r"interval of \\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\mega\\tonne\} under persistent",
     lambda: _v3_endpoint("P2_5_quantity"), 0.),
    ("integrated paired endpoint high", r"interval of \\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\mega\\tonne\} under persistent",
     lambda: _v3_endpoint("P97_5_quantity"), 0.),
    ("integrated consecutive annual changes", r"Of the \\num\{(\d+)\} consecutive annual changes",
     lambda: _v3_steps(), 0.),
    ("integrated resolved steps persistent", r"annual changes, \\num\{(\d+)\} have intervals",
     lambda: _v3_steps("persistent_parameters"), 0.),
    ("integrated resolved steps annual errors", r"persistent parameters and \\num\{(\d+)\} under independently",
     lambda: _v3_steps("annual_activity_errors"), 0.),
    ("integrated power SO2 first year", r"\(from \\SI\{([\d.]+)\}\{\\giga\\gram\} to",
     lambda: _v3_air(_V3_FIRST, "SO2", lambda r: r["sector_id"] == "power"), 0.),
    ("integrated power SO2 latest year", r"\(from \\SI\{[\d.]+\}\{\\giga\\gram\} to \\SI\{([\d.]+)\}",
     lambda: _v3_air(_V3_LATEST, "SO2", lambda r: r["sector_id"] == "power"), 0.),
    ("integrated SO2 interval low", r"\\SIrange\{([\d.]+)\}\{[\d.]+\}\{\\giga\\gram\} SO\$_2\$ and",
     lambda: _v3_air_interval("SO2", "P2_5_Gg"), 0.),
    ("integrated SO2 interval high", r"\\SIrange\{[\d.]+\}\{([\d.]+)\}\{\\giga\\gram\} SO\$_2\$ and",
     lambda: _v3_air_interval("SO2", "P97_5_Gg"), 0.),
    ("integrated dung case GHG change", r"changes the GHG aggregate by about \\SI\{(\d+)\}",
     lambda: 100.0 * (_v3_ghg(_V3_REF, configuration="L_TAN") / _v3_ghg(_V3_REF) - 1.0), 0.),
    ("integrated dung case PM2.5", r"raises PM\$_\{2\.5\}\$ to \\SI\{([\d.]+)\}",
     lambda: _v3_structural("all_diverted_dung_household_combustion", "PM2.5"), 0.),
    ("integrated draw count", r"Conditional ensembles of \\num\{(\d+)\} realisations",
     _v3_draws, 0.),
    ("integrated BTR matched total", r"PakEmis is \\num\{([\d.]+)\} times the reported total",
     lambda: _v3_btr("TOTAL on categories both accounts estimate"), 0.),
    ("integrated BTR oil and gas fugitives", r"fugitive emissions are \\num\{([\d.]+)\} times",
     lambda: _v3_btr("Oil and natural gas fugitives"), 0.),
    ("integrated BTR enteric", r"enteric fermentation \\num\{([\d.]+)\} times",
     lambda: _v3_btr("Enteric fermentation"), 0.),
    ("integrated BTR wastewater", r"domestic wastewater \\num\{([\d.]+)\} times",
     lambda: _v3_btr("Domestic wastewater"), 0.),
    ("integrated BTR managed soils", r"managed soils are \\num\{([\d.]+)\} times",
     lambda: _v3_btr("Managed soils"), 0.),
    ("integrated EDGAR industry SO2 fossil", r"Industrial SO\$_2\$ is \\num\{([\d.]+)\} times",
     lambda: _v3_edgar_industry("SO2", "fossil"), 0.),
    ("integrated EDGAR industry SO2 fossil+bio", r"fossil account and \\num\{([\d.]+)\} times its fossil-plus-biomass",
     lambda: _v3_edgar_industry("SO2", "all"), 0.),
    ("integrated EDGAR industry PM2.5 fossil", r"PM\$_\{2\.5\}\$ is \\num\{([\d.]+)\} and",
     lambda: _v3_edgar_industry("PM2.5", "fossil"), 0.),
    ("integrated EDGAR industry PM2.5 fossil+bio", r"PM\$_\{2\.5\}\$ is \\num\{[\d.]+\} and \\num\{([\d.]+)\} times",
     lambda: _v3_edgar_industry("PM2.5", "all"), 0.),
    ("integrated HTAP road NH3 low", r"Road NH\$_3\$, a small source, is \\num\{([\d.]+)\} to",
     lambda: _v3_htap_species("road_exhaust", "NH3", min), 0.),
    ("integrated HTAP road NH3 high", r"Road NH\$_3\$, a small source, is \\num\{[\d.]+\} to \\num\{([\d.]+)\}",
     lambda: _v3_htap_species("road_exhaust", "NH3", max), 0.),
] + [
    ("integrated HTAP %s %s %s" % (group, species, end),
     r"%s \\num\{%s\} to \\num\{%s\}" % (anchor, "([\d.]+)" if end == "low" else "[\d.]+",
                                              "([\d.]+)" if end == "high" else "[\d.]+"),
     (lambda g=group, p=species, c=configuration, f=(min if end == "low" else max):
      _v3_htap_species(g, p, f, c)), 0.)
    for group, species, configuration, anchor in (
        ("road_exhaust", "NOx", "S_TAN", r"Road-exhaust NO\$_x\$ is"),
        ("road_exhaust", "CO", "S_TAN", r"times HTAP and CO"),
        ("road_exhaust", "PM2.5", "S_TAN", r"road PM\$_\{2\.5\}\$ is"),
        ("road_exhaust", "BC", "S_TAN", r"times and BC"),
        ("agriculture_livestock_and_soils", "NH3", "S_TAN", r"Livestock and soil NH\$_3\$ is"),
        ("agriculture_livestock_and_soils", "NH3", "S_IPCC", r"reference configuration and"),
        ("agriculture_livestock_and_soils", "NOx", "S_TAN", r"soil NO\$_x\$"))
    for end in ("low", "high")
] + [
    ("integrated HTAP road SO2 first", r"Road SO\$_2\$ is \\num\{([\d.]+)\} and",
     lambda: _v3_htap_species_year("road_exhaust", "SO2", "FY2015-16"), 0.),
    ("integrated HTAP road SO2 second", r"Road SO\$_2\$ is \\num\{[\d.]+\} and \\num\{([\d.]+)\} times",
     lambda: _v3_htap_species_year("road_exhaust", "SO2", "FY2016-17"), 0.),
    ("integrated HTAP road SO2 later low", r"first two years and \\num\{([\d.]+)\} to",
     lambda: min(_v3_htap_species_year("road_exhaust", "SO2", p) for p in ("FY2017-18", "FY2018-19", "FY2019-20")), 0.),
    ("integrated HTAP road SO2 later high", r"first two years and \\num\{[\d.]+\} to \\num\{([\d.]+)\}",
     lambda: max(_v3_htap_species_year("road_exhaust", "SO2", p) for p in ("FY2017-18", "FY2018-19", "FY2019-20")), 0.),
    ("integrated HTAP residue factor ratio low", r"implies emission factors \\num\{([\d.]+)\} to",
     lambda: min(_v3_residue_factor_ratios()), 0.),
    ("integrated HTAP residue factor ratio high", r"implies emission factors \\num\{[\d.]+\} to \\num\{([\d.]+)\}",
     lambda: max(_v3_residue_factor_ratios()), 0.),
    ("integrated SO2 power coverage change", r"diesel only, changes by \\SI\{(-?\d+)\}",
     lambda: _v3_air(_V3_LATEST, "SO2", lambda r: r["sector_id"] == "power")
             - _v3_air(_V3_FIRST, "SO2", lambda r: r["sector_id"] == "power"), 0.),
    ("integrated SO2 road change", r"Road transport changes by \\SI\{(-?\d+)\}",
     lambda: _v3_air(_V3_LATEST, "SO2", lambda r: r["sector_id"] == "transport")
             - _v3_air(_V3_FIRST, "SO2", lambda r: r["sector_id"] == "transport"), 0.),
    ("integrated diesel sulfur before step", r"steps from \\num\{(\d+)\} to",
     lambda: _v3_diesel_ppm(2017), 0.),
    ("integrated diesel sulfur after step", r"steps from \\num\{\d+\} to \\num\{(\d+)\}~ppm",
     lambda: _v3_diesel_ppm(2018), 0.),
]])

CLAIMS.extend([
    ("integrated methane is the largest part", "national-v3", "paper.tex",
     "Methane from livestock, rice and waste is the largest part of the GHG aggregate", "ratio_at_least", 0.5, 0.,
     lambda: _v3_ghg_share(lambda r: r["gas"] == "CH4") / 100.0),
    ("integrated households dominate PM2.5", "national-v3", "paper.tex",
     "household biomass combustion dominates primary PM$_{2.5}$", "ratio_at_least", 0.5, 0.,
     lambda: _v3_air_share("PM2.5", lambda r: r["sector_id"] == "residential") / 100.0),
    ("integrated industry dominates SO2", "national-v3", "paper.tex",
     "industrial fuel combustion dominates SO$_2$", "ratio_at_least", 0.5, 0.,
     lambda: _v3_air_share("SO2", lambda r: r["sector_id"] == "industry", period=_V3_LATEST) / 100.0),
    ("integrated kiln long season several times", "national-v3", "paper.tex",
     "raise SO$_2$ to several times the reference", "ratio_at_least", 3.0, 0.,
     lambda: min(_v3_structural(s, "SO2") for s in ("coal_allocation:fleet_bkoap_long_season",
                                                    "coal_allocation:fleet_hamdani_long_season"))
             / _v3_structural("coal_allocation:fleet_bkoap_long_season", "SO2", "reference_covered_Gg")),
    ("integrated power SO2 only oil and diesel", "national-v3", "paper.tex",
     "The power module carries SO$_2$ only among air pollutants", "count_equals", 1, 0.,
     lambda: len({r["pollutant"] for r in _rows("pakemis_air_annual_fy2015_16_fy2024_25.csv")
                  if r["sector_id"] == "power" and float(r["emissions_Gg"]) != 0})),
])

DOC_CLAIMS.extend([
    # The residential grid paragraph's two unit counts, read from the allocation products
    # that carry the units (the residential district file and the agricultural district base).
    ("residential allocation unit count", "residential", "06_results.tex",
     r"spreads over \\num\{(\d+)\} allocation units",
     lambda: len({r["adm2_id"] for r in _rows("residential_district_2024.csv")}), 0.),
    ("residential agricultural district count", "residential", "06_results.tex",
     r"The agricultural account has \\num\{(\d+)\} four-province districts",
     lambda: len({r["district"] for r in _rows("district_totals_2024.csv")
                  if "residual" not in r["district"]}), 0.),
])


def _v3_seam(column, period="FY2024-25"):
    row = next(r for r in _csv_rows("pakemis_coal_sector_reallocation.csv") if r["period_id"] == period)
    return float(row[column])


DOC_CLAIMS.extend([
    ("integrated coal seam share of period change", "national-v3", "paper.tex",
     r"allocation seam is \\SI\{([\d.]+)\}\{\\percent\} of the change",
     lambda: _v3_seam("seam_share_of_national_change_vs_base_S_TAN_pct"), 0.),
    ("integrated coal seam share of one-year change", "national-v3", "paper.tex",
     r"FY2024--25 but \\SI\{([\d.]+)\}\{\\percent\} of the one-year change",
     lambda: _v3_seam("seam_share_of_national_change_yoy_S_TAN_pct"), 0.),
])
