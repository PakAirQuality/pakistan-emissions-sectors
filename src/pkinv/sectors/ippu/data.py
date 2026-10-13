"""Source-neutral data library for industrial processes and product use.

The original IPPU module loaded one Pocket Book row directly into the cement
equation.  This loader keeps that interface for the national inventory while
also exposing competing activity controls, clinker trade, F-gas consumption
controls, facilities, and the complete 2.A--2.G acquisition matrix.
"""
from __future__ import annotations

from pkinv.activity.store import input_exists as _input_exists
import csv
import os
from collections import defaultdict
from functools import cached_property

from pkinv.paths import DATA
from pkinv.sectors.ippu import schemas
from pkinv.activity.store import read_rows
from pkinv.assets import asset_path

YEAR = 2024                       # fiscal year ending June 2024
REFERENCE_CEMENT_SOURCE = "pbs_qim_fy2023_24"


def _read(path):
    return read_rows(path, comments=False)


def _num(value):
    return schemas.number(value)


class IppuMetadata:
    """Descriptive registers loaded only by publication or explicit inspection.

    None of these five registers admits an activity to the numerical model.
    Scientific evidence gates remain eager in IppuData below.
    """
    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir, self.year = data_dir, year

    def _metadata_rows(self, name):
        return schemas.read_csv(asset_path(self.data_dir, "activity", "ippu", name))

    @cached_property
    def hfc_import_contract_rows(self):
        return schemas.validate_hfc_import_contract(
            self._metadata_rows("hfc_inventory_import_contract.csv"))

    @cached_property
    def data_request_packet_rows(self):
        path = asset_path(self.data_dir, "activity", "ippu", "data_request_packets.csv")
        return schemas.read_csv(path) if _input_exists(path) else []

    @cached_property
    def source_manifest_rows(self):
        return self._metadata_rows("source_manifest.csv")

    @cached_property
    def completeness_rows(self):
        return schemas.validate_completeness(self._metadata_rows("master_data_gap_matrix.csv"))

    @cached_property
    def evidence_maturity_rows(self):
        return schemas.validate_evidence_maturity(
            self._metadata_rows("evidence_maturity.csv"), self.completeness_rows)


class IppuData(IppuMetadata):
    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir, self.year = data_dir, year
        root = asset_path(data_dir, "activity", "ippu")

        self.ef = {}
        for row in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(row["category"], row["item"])] = {
                "value": _num(row["value"]), "uncert_pct": _num(row["uncert_pct"]),
                "source": row["source"]}

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for row in _read(asset_path(data_dir, "ippu_params.csv")):
            self.params[row["param"]] = _num(row["value"])
            self.param_uncert[row["param"]] = _num(row["uncert_pct"])
            self.param_source[row["param"]] = row["source"]

        # Preserve the legacy table and produced_kt() interface for the registered
        # national sector and downstream code that still reads provincial anchors.
        self.production = {}
        for row in _read(asset_path(root, "production.csv")):
            self.production[(int(row["fiscal_year"]), row["product"])] = {
                "pakistan": float(row["pakistan_000_tons"]),
                "punjab": float(row["punjab_000_tons"]), "source": row["source"]}

        self.activity_rows = schemas.validate_activity(
            schemas.read_csv(asset_path(root, "national_activity.csv")))
        self.activities = defaultdict(list)
        for row in self.activity_rows:
            self.activities[(int(row["period_end_year"]), row["product"])].append(row)

        self.trade_rows = schemas.read_csv(asset_path(root, "clinker_trade_monthly.csv"))
        self.annual_trade_rows = schemas.read_csv(
            asset_path(root, "clinker_trade_annual.csv"))
        self.cement_monthly_2022_rows = schemas.read_csv(
            asset_path(root, "cement_monthly_2022.csv"))
        self.company_clinker_rows = schemas.read_csv(
            asset_path(root, "company_clinker_2023_24.csv"))
        self.cement_producer_census_rows = schemas.read_csv(
            asset_path(root, "cement_producer_census_2023_24.csv"))
        self.company_boundary_rows = schemas.validate_company_boundary(
            schemas.read_csv(asset_path(root, "company_boundary_audit.csv")))
        self.hfc_control_rows = schemas.read_csv(
            asset_path(root, "hfc_consumption_controls.csv"))
        self.facility_rows = schemas.read_csv(asset_path(root, "facilities.csv"))
        self.chemical_plant_evidence_rows = schemas.read_csv(
            asset_path(root, "chemical_plant_evidence.csv"))
        self.chemical_plant_activity_rows = schemas.validate_chemical_activity(
            schemas.read_csv(asset_path(root, "chemical_plant_activity.csv")))
        self.nitric_acid_monitoring_rows = schemas.validate_nitric_monitoring(
            schemas.read_csv(asset_path(root, "nitric_acid_monitoring.csv")))
        self.nitric_acid_monitoring_detail_rows = schemas.validate_nitric_monitoring_detail(
            schemas.read_csv(asset_path(root, "nitric_acid_monitoring_detail.csv")))
        self.cdm_access_manifest_rows = schemas.validate_cdm_access_manifest(
            schemas.read_csv(asset_path(root, "cdm_access_manifest.csv")))
        self.facility_geocoding_override_rows = schemas.validate_facility_geocoding_overrides(
            schemas.read_csv(asset_path(root, "facility_geocoding_overrides.csv")))

        # NFDC AFR 2024-25 extractions - four tables, held under data/nfdc beside the
        # agriculture sector's annex files because they are extractions of the same
        # document. They feed the ammonia reconciliation only; nothing here becomes a
        # component. The monthly gas annex is the only one that covers FY2023-24, the
        # reference year, which is why the feed/fuel split for that year is observed
        # rather than borrowed from the year after it.
        nfdc = asset_path(data_dir, "nfdc")
        self.fertilizer_production_rows = schemas.read_csv(
            asset_path(nfdc, "afr2025_production_by_manufacturer.csv"))
        self.fertilizer_gas_rows = schemas.read_csv(
            asset_path(nfdc, "afr2025_fertilizer_gas_by_plant.csv"))
        self.fertilizer_offtake_rows = schemas.read_csv(
            asset_path(nfdc, "afr2025_offtake_by_product.csv"))
        self.fertilizer_gas_monthly_rows = schemas.read_csv(
            asset_path(nfdc, "afr2025_fertilizer_gas_monthly.csv"))
        # rc52 (boundary program Wave C): the nine-year activity series the three activated
        # categories ride - NFDC production by product and fiscal year (ammonia), and OCAC's
        # non-energy sectoral sales (lubricants). Steel reads the QIM panel through core.pbs_qim.
        self.fertilizer_production_series_rows = schemas.read_csv(
            asset_path(nfdc, "nfdc_production_by_product_series.csv"))
        self.ocac_non_energy_rows = schemas.read_csv(
            asset_path(data_dir, "activity", "industry", "ocac_non_energy_sectoral.csv"))

    def efv(self, category, item):
        return self.ef[(category, item)]["value"]

    def efu(self, category, item):
        return self.ef[(category, item)]["uncert_pct"]

    def efs(self, category, item):
        return self.ef[(category, item)]["source"]

    def p(self, name):
        return self.params[name]

    def pu(self, name):
        return self.param_uncert[name]

    def ps(self, name):
        return self.param_source[name]

    def produced_kt(self, product, year=None):
        """Legacy national production control in kt, retained for compatibility."""
        return self.production[(self.year if year is None else year, product)]["pakistan"]

    def activity(self, product, source_id=None, year=None):
        """Return one normalized activity row, with ambiguity rejected explicitly."""
        key = (self.year if year is None else int(year), product)
        rows = list(self.activities.get(key, ()))
        if source_id is not None:
            rows = [row for row in rows if row["source_id"] == source_id]
        if len(rows) != 1:
            raise KeyError("expected one activity for %r, found %d" % ((key, source_id), len(rows)))
        return {**rows[0], "quantity": _num(rows[0]["quantity"])}

    def cement_activity_kt(self, source_id=REFERENCE_CEMENT_SOURCE, year=None):
        row = self.activity("Cement", source_id, year)
        if row["unit"] != "kt":
            raise ValueError("cement activity must be expressed in kt")
        return row["quantity"]

    def cement_activity_source(self, year=None):
        """Which source carries cement for this year, resolved from the data.

        The reference source wins where it has a row, so the reference year's provenance is
        unchanged and the resolution is only ever reached for the other years. Where no
        source carries the year this RAISES: cement activity is held for FY2021-22 onwards
        only, and a year without it is NE - the same rule the trade gate applies to the
        other half of the balance.
        """
        end_year = self.year if year is None else int(year)
        rows = self.activities.get((end_year, "Cement"), ())
        # A COMPARISON row is not a candidate. Where two publications cover one year, one of
        # them is the activity control and the other is what makes their agreement checkable;
        # treating the second as an alternative source would turn a bridge into an ambiguity
        # and make the year unresolvable.
        rows = [row for row in rows if row.get("status") != "comparison"]
        sources = sorted({row["source_id"] for row in rows})
        if REFERENCE_CEMENT_SOURCE in sources:
            return REFERENCE_CEMENT_SOURCE
        if len(sources) == 1:
            return sources[0]
        if not sources:
            raise KeyError("no cement activity is held for period_end_year %d; the year is "
                           "NE, not zero" % end_year)
        raise KeyError("cement activity for %d comes from %d sources (%s) and none is the "
                       "reference: choose one explicitly rather than letting this guess"
                       % (end_year, len(sources), ", ".join(sources)))

    def clinker_trade_kt(self, flow, year=None):
        """Sum July--June HS 252310 trade into the requested fiscal end year."""
        if flow not in ("export", "import"):
            raise ValueError("flow must be export or import")
        end_year = self.year if year is None else int(year)
        start = "%04d-07" % (end_year - 1)
        end = "%04d-06" % end_year
        selected = [row for row in self.trade_rows
                    if row["flow"] == flow and start <= row["month"] <= end]
        months = {row["month"] for row in selected}
        if len(months) != 12:
            raise ValueError("clinker %s coverage is %d/12 months for FY%d" %
                             (flow, len(months), end_year))
        return sum(_num(row["quantity_t"]) for row in selected) / 1000.0

    def clinker_trade_source(self):
        sources = {row["source_reference"] for row in self.trade_rows}
        return "; ".join(sorted(sources))

    def calendar_cement_activity_kt(self, year):
        selected = [row for row in self.cement_monthly_2022_rows
                    if row["month"].startswith("%d-" % int(year))]
        if len({row["month"] for row in selected}) != 12:
            raise ValueError("calendar cement coverage is not 12 months for %d" % year)
        return sum(_num(row["cement_kt"]) for row in selected)

    def annual_clinker_trade_kt(self, flow, year):
        selected = [row for row in self.annual_trade_rows
                    if int(row["calendar_year"]) == int(year) and row["flow"] == flow]
        if len(selected) != 1:
            raise ValueError("expected one calendar trade row for %d %s" % (year, flow))
        return _num(selected[0]["quantity_t"]) / 1000.0

    def annual_clinker_trade_source(self, year):
        selected = [row for row in self.annual_trade_rows
                    if int(row["calendar_year"]) == int(year)]
        return "; ".join(sorted({row["source_reference"] for row in selected}))

    def company_clinker(self, year=None):
        """Return reported company clinker production without scaling uncovered firms."""
        end_year = self.year if year is None else int(year)
        rows = [dict(row) for row in self.company_clinker_rows
                if int(row["period_end_year"]) == end_year]
        numeric_fields = ("clinker_production_t", "cement_production_t",
                          "opening_clinker_stock_t", "clinker_purchases_t",
                          "clinker_imports_t", "clinker_ground_t",
                          "domestic_clinker_sales_t", "clinker_exports_t",
                          "closing_clinker_stock_t")
        for row in rows:
            for field in numeric_fields:
                row[field] = _num(row.get(field))
        return rows

    def census_clinker_kt(self, year=None):
        """The audited 16-company producer census's total clinker production, in kt.

        The rc30 reference activity (the eighteenth review's re-base): every census
        entity reports actual production - Fecto's 651,048 t arrived with the FY2025
        annual report's comparative table - so the sum is an observed national
        activity, not a model. Raises if any census entity is missing a value,
        because a partial sum silently read as the national census is exactly the
        floor-vs-total confusion the boundary audit exists to prevent.
        """
        rows = self.company_clinker(year)
        census = self.cement_producer_census(year)
        if not rows:
            raise ValueError(
                "no producer census is held for period_end_year=%s; cement activity "
                "for that year rides the Tier-1 model, declared as such"
                % (year if year is not None else self.year))
        if len(rows) != len(census):
            raise ValueError(
                "the company clinker table (%d rows) does not cover the producer "
                "census (%d entities); the census sum would be a floor, not the "
                "reference activity" % (len(rows), len(census)))
        return sum(row["clinker_production_t"] for row in rows) / 1000.0

    def cement_producer_census(self, year=None):
        end_year = self.year if year is None else int(year)
        rows = [dict(row) for row in self.cement_producer_census_rows
                if int(row["period_end_year"]) == end_year]
        for row in rows:
            row["clinker_production_t"] = _num(row.get("clinker_production_t"))
        return rows

    def facility_geocoding_audit(self):
        """Return one provenance row per facility, retaining unresolved coordinates."""
        overrides = {row["facility_id"]: row
                     for row in self.facility_geocoding_override_rows}
        audit = []
        for facility in self.facility_rows:
            override = overrides.get(facility["facility_id"])
            if override:
                audit.append({**facility, **override})
            else:
                audit.append({
                    **facility,
                    "coordinate_source": "facility source reference",
                    "coordinate_source_reference": facility["source_reference"],
                    "coordinate_quality": "official locality only",
                    "boundary_scope": "district or named locality",
                    "geocode_status": "exact_coordinate_unresolved",
                    "note": facility["note"],
                })
        if len(audit) != len(self.facility_rows):
            raise AssertionError("facility geocoding audit lost records")
        return audit
