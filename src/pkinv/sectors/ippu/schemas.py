"""Shared tabular contracts for the IPPU inventory platform.

The registered national component contract remains the small mapping defined in
``pkinv.core.components``.  These rows sit one layer earlier: they preserve the activity,
material and provenance information needed to decide whether a component may be emitted at
all.  A missing process route is therefore a visible status, not a zero emission.
"""
from __future__ import annotations

import csv
from pkinv.activity.store import read_rows

NOTATION_KEYS = frozenset({"E", "NE", "NO", "IE", "NA", "C"})
PERIOD_BASES = frozenset({"calendar", "fiscal"})
# "comparison" is a fourth state and it is not a weaker control: the row is a second
# publication of a year the inventory already has, carried so that the agreement between two
# sources is checkable rather than asserted. It is deliberately NOT an activity candidate -
# IppuData.cement_activity_source skips it - because a year with two controls is a year that
# cannot resolve, and the point of the row is the opposite of ambiguity.
ACTIVITY_STATUSES = frozenset({"estimate", "control", "screen", "comparison"})
CHEMICAL_EVIDENCE_STATUSES = frozenset({
    "partial_activity_only", "historical_partial_activity",
    "plant_identified_activity_missing", "model_ready_national",
})
HFC_DATA_STATUSES = frozenset({"observed", "reported", "modelled", "imputed", "missing"})
MATURITY_LABELS = {
    0: "no evidence",
    1: "occurrence identified",
    2: "national control available",
    3: "partial facility activity",
    4: "model-ready national activity",
    5: "facility or Tier 2 activity",
    6: "measured or independently validated factor",
}


def read_csv(path):
    # comment-tolerant: several activity files carry a '#' provenance header
    # (the repo-wide pattern), and a reader that feeds the first comment line to
    # DictReader as the header turns every later access into a KeyError
    return read_rows(path)


def number(value):
    value = str(value or "").strip()
    return None if not value else float(value.replace(",", ""))


def validate_activity(rows):
    required = {"period_end_year", "period_basis", "ipcc_code", "product", "quantity",
                "unit", "source_id", "status", "data_tier"}
    for index, row in enumerate(rows, 2):
        missing = required - set(row)
        if missing:
            raise ValueError("activity row %d lacks %s" % (index, sorted(missing)))
        if row["period_basis"] not in PERIOD_BASES:
            raise ValueError("activity row %d has invalid period basis" % index)
        if row["status"] not in ACTIVITY_STATUSES:
            raise ValueError("activity row %d has invalid status" % index)
        if number(row["quantity"]) is None or number(row["quantity"]) < 0:
            raise ValueError("activity row %d has invalid quantity" % index)
    return rows


def validate_completeness(rows):
    codes = set()
    for index, row in enumerate(rows, 2):
        key = row["notation_key_2024"]
        if key not in NOTATION_KEYS:
            raise ValueError("completeness row %d has invalid notation key %r" % (index, key))
        code = row["ipcc_code"]
        if code in codes:
            raise ValueError("duplicate IPPU completeness code %s" % code)
        codes.add(code)
    for family in ("2.A", "2.B", "2.C", "2.D", "2.E", "2.F", "2.G"):
        if not any(code == family or code.startswith(family + ".") for code in codes):
            raise ValueError("IPPU completeness matrix omits %s" % family)
    return rows


def validate_chemical_activity(rows):
    """Validate the period-aware fertilizer-plant evidence contract.

    Plant discovery is deliberately separable from annual activity.  Blank production is
    therefore valid for an identified plant, but a model-ready row must provide production
    and the process fields needed by its IPCC category.
    """
    required = {"period_end_year", "period_basis", "facility_id", "ipcc_code", "product",
                "production_t", "evidence_status", "source_id", "source_reference"}
    seen = set()
    for index, row in enumerate(rows, 2):
        missing = required - set(row)
        if missing:
            raise ValueError("chemical activity row %d lacks %s" % (index, sorted(missing)))
        if row["period_basis"] not in PERIOD_BASES:
            raise ValueError("chemical activity row %d has invalid period basis" % index)
        if row["evidence_status"] not in CHEMICAL_EVIDENCE_STATUSES:
            raise ValueError("chemical activity row %d has invalid evidence status" % index)
        key = (row["period_end_year"], row["period_basis"], row["facility_id"],
               row["product"], row["source_id"])
        if key in seen:
            raise ValueError("duplicate chemical activity record %r" % (key,))
        seen.add(key)
        production = number(row.get("production_t"))
        if production is not None and production < 0:
            raise ValueError("chemical activity row %d has negative production" % index)
        for field in ("purity_fraction",):
            value = number(row.get(field))
            if value is not None and not 0 <= value <= 1:
                raise ValueError("chemical activity row %d has invalid %s" % (index, field))
        if row["evidence_status"] == "model_ready_national" and production is None:
            raise ValueError("model-ready chemical row %d lacks production" % index)
    return rows


def validate_nitric_monitoring(rows):
    """Validate historical CDM observations without treating CERs as annual N2O."""
    required = {"project_id", "facility_id", "monitoring_start", "monitoring_end", "metric",
                "value_t_co2e", "issuance_status", "source_reference", "evidence_role"}
    seen = set()
    for index, row in enumerate(rows, 2):
        missing = required - set(row)
        if missing:
            raise ValueError("nitric monitoring row %d lacks %s" % (index, sorted(missing)))
        key = (row["project_id"], row["monitoring_start"], row["monitoring_end"])
        if key in seen:
            raise ValueError("duplicate nitric monitoring period %r" % (key,))
        seen.add(key)
        if row["monitoring_start"] > row["monitoring_end"]:
            raise ValueError("nitric monitoring row %d has reversed dates" % index)
        value = number(row["value_t_co2e"])
        if value is None or value < 0:
            raise ValueError("nitric monitoring row %d has invalid value" % index)
        if "observation" not in row["evidence_role"]:
            raise ValueError("nitric monitoring row %d overstates its evidence role" % index)
    return rows


def validate_hfc_import_contract(rows):
    """Check that the external HFC template preserves supply, bank and loss concepts."""
    expected = {
        "year", "species", "application", "imports_t", "exports_t",
        "domestic_production_t", "destruction_t", "new_equipment_charge_t",
        "servicing_charge_t", "manufacturing_loss_fraction", "operating_loss_fraction",
        "retired_charge_t", "recovery_fraction", "destruction_fraction_of_recovered",
        "source_reference", "data_status",
    }
    by_field = {row.get("field"): row for row in rows}
    missing = expected - set(by_field)
    if missing:
        raise ValueError("HFC import contract lacks %s" % sorted(missing))
    for field in expected:
        if by_field[field].get("required") != "yes":
            raise ValueError("HFC import contract does not require %s" % field)
    return rows


def validate_company_boundary(rows):
    """Keep company production and material-flow boundaries explicit and unfilled."""
    required = {
        "period_end_year", "company", "reporting_scope", "period_start", "period_end",
        "plants_included", "production_basis", "clinker_production_t",
        "cement_production_t", "source_reference", "source_sha256",
        "boundary_confidence", "movement_coverage", "material_balance_status",
    }
    seen = set()
    for index, row in enumerate(rows, 2):
        missing = required - set(row)
        if missing:
            raise ValueError("company boundary row %d lacks %s" % (index, sorted(missing)))
        key = (row["period_end_year"], row["company"])
        if key in seen:
            raise ValueError("duplicate company boundary %r" % (key,))
        seen.add(key)
        if row["period_start"] > row["period_end"]:
            raise ValueError("company boundary row %d has reversed dates" % index)
        for field in ("clinker_production_t", "cement_production_t"):
            value = number(row.get(field))
            if value is not None and value < 0:
                raise ValueError("company boundary row %d has negative %s" % (index, field))
        if row["material_balance_status"] == "complete":
            flow_fields = ("opening_clinker_stock_t", "clinker_purchases_t",
                           "clinker_imports_t", "clinker_ground_t",
                           "domestic_clinker_sales_t", "clinker_exports_t",
                           "closing_clinker_stock_t")
            if any(number(row.get(field)) is None for field in flow_fields):
                raise ValueError("complete company balance row %d has missing flows" % index)
    return rows


def validate_nitric_monitoring_detail(rows):
    """Validate period-specific CDM measurements without turning them into current activity."""
    required = {
        "project_id", "facility_id", "monitoring_start", "monitoring_end",
        "document_url", "archive_status", "parameter", "parameter_value",
        "parameter_text", "evidence_role",
    }
    seen = set()
    for index, row in enumerate(rows, 2):
        missing = required - set(row)
        if missing:
            raise ValueError("nitric detail row %d lacks %s" % (index, sorted(missing)))
        key = (row["project_id"], row["monitoring_start"], row["monitoring_end"],
               row["parameter"])
        if key in seen:
            raise ValueError("duplicate nitric detail parameter %r" % (key,))
        seen.add(key)
        if row["monitoring_start"] > row["monitoring_end"]:
            raise ValueError("nitric detail row %d has reversed dates" % index)
        if number(row.get("parameter_value")) is None and not row.get("parameter_text", "").strip():
            raise ValueError("nitric detail row %d has no value" % index)
        if "historical" not in row["evidence_role"]:
            raise ValueError("nitric detail row %d overstates current evidence" % index)
    return rows


def validate_evidence_maturity(rows, completeness_rows):
    """Check the explicit 0--6 maturity ladder against formal notation keys."""
    completeness = {row["ipcc_code"]: row for row in completeness_rows}
    seen = set()
    for index, row in enumerate(rows, 2):
        code = row.get("ipcc_code", "")
        if code in seen:
            raise ValueError("duplicate maturity code %s" % code)
        seen.add(code)
        if code not in completeness:
            raise ValueError("maturity row %d has unknown code %s" % (index, code))
        level = int(row["maturity_level"])
        if level not in MATURITY_LABELS or row["maturity_label"] != MATURITY_LABELS[level]:
            raise ValueError("maturity row %d has inconsistent level and label" % index)
        notation = completeness[code]["notation_key_2024"]
        if notation == "E" and level < 4:
            raise ValueError("estimated code %s lacks model-ready maturity" % code)
        if notation == "NE" and level >= 4:
            raise ValueError("NE code %s is incorrectly marked model-ready" % code)
    if seen != set(completeness):
        raise ValueError("maturity and completeness code sets differ")
    return rows


def validate_facility_geocoding_overrides(rows):
    seen = set()
    for index, row in enumerate(rows, 2):
        facility_id = row.get("facility_id", "")
        if not facility_id or facility_id in seen:
            raise ValueError("invalid or duplicate facility override at row %d" % index)
        seen.add(facility_id)
        lat, lon = number(row.get("latitude")), number(row.get("longitude"))
        if lat is None or lon is None or not (23 <= lat <= 38 and 60 <= lon <= 78):
            raise ValueError("facility override row %d is outside Pakistan bounds" % index)
        if not row.get("coordinate_source_reference", "").strip():
            raise ValueError("facility override row %d lacks coordinate provenance" % index)
    return rows


def validate_cdm_access_manifest(rows):
    allowed = {"public_page_accessible", "remote_indexed_storage_blocked", "archived"}
    for index, row in enumerate(rows, 2):
        if row.get("access_status") not in allowed:
            raise ValueError("CDM access row %d has invalid status" % index)
        local_file, digest = row.get("local_file", "").strip(), row.get("sha256", "").strip()
        if bool(local_file) != bool(digest):
            raise ValueError("CDM access row %d has incomplete local provenance" % index)
        if row["access_status"] != "archived" and (local_file or digest):
            raise ValueError("CDM access row %d claims an unavailable local archive" % index)
    return rows
