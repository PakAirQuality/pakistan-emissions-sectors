"""Publish IPPU descriptive registers, combined QA and provenance independently.

The numerical stage supplies completed checks and a small context document.
Changing a request, completeness annotation or import schema therefore requires
only this task; admission-affecting evidence stays in the numerical stage.
"""
from __future__ import annotations

import hashlib
import json
import os

from pkinv.assets import resolve
from pkinv.core.io import write_table
from pkinv.core.runner import QA_FIELDS, Runner
from pkinv.paths import ROOT, OUTPUTS
from pkinv.sectors.ippu import completeness
from pkinv.sectors.ippu.data import IppuMetadata
from pkinv.assets import asset_path

OUTPUT_NAMES = (
    "ippu_completeness_2024.csv", "ippu_evidence_maturity.csv",
    "ippu_data_acquisition_requests.csv", "ippu_hfc_inventory_import_contract.csv",
    "ippu_data_request_packets.csv", "ippu_source_manifest.csv",
)
INPUT_PATHS = tuple("data/nfdc/" + name for name in (
    "afr2025_production_by_manufacturer.csv", "afr2025_fertilizer_gas_by_plant.csv",
    "afr2025_offtake_by_product.csv", "afr2025_fertilizer_gas_monthly.csv")) + tuple(
    "data/activity/ippu/" + name for name in (
        "national_activity.csv", "clinker_trade_monthly.csv", "company_clinker_2023_24.csv",
        "cement_producer_census_2023_24.csv", "cement_monthly_2022.csv", "clinker_trade_annual.csv",
        "master_data_gap_matrix.csv", "hfc_consumption_controls.csv", "hfc_inventory_import_contract.csv",
        "chemical_plant_evidence.csv", "chemical_plant_activity.csv", "nitric_acid_monitoring.csv",
        "nitric_acid_monitoring_detail.csv", "cdm_access_manifest.csv", "company_boundary_audit.csv",
        "evidence_maturity.csv", "facility_geocoding_overrides.csv", "data_request_packets.csv",
        "facilities.csv", "source_manifest.csv"))


def metadata_checks(data):
    run = Runner("ippu_metadata")
    run.gate("evidence_maturity",
             len(data.evidence_maturity_rows) == len(data.completeness_rows) and
             next(row for row in data.evidence_maturity_rows
                  if row["ipcc_code"] == "2.A.1")["maturity_level"] == "4",
             note="every completeness row has a validated 0-6 maturity state")
    codes = {row["ipcc_code"] for row in data.completeness_rows}
    for family in ("2.A", "2.B", "2.C", "2.D", "2.E", "2.F", "2.G"):
        run.gate("completeness_" + family,
                 any(code == family or code.startswith(family + ".") for code in codes),
                 note="master matrix covers " + family)
    return run.checks


def combined_checks(context, descriptive, outputs=OUTPUTS):
    checks = list(context["checks"])
    position = next(i for i, row in enumerate(checks) if row["check"] == "company_boundary_audit") + 1
    checks.insert(position, descriptive[0])
    checks.extend(descriptive[1:])
    declared = context["declared"]
    missing = sorted(name for name in declared if not os.path.isfile(asset_path(outputs, name)))
    checks.append({"check": "declared outputs written", "passed": not missing,
                   "actual": len(declared) - len(missing), "expected": len(declared),
                   "note": ("missing: " + ", ".join(missing) if missing else
                            "every output this runner declares was written by this run")})
    return checks


def validate_numerical_outputs(context, root=ROOT):
    """Never republish numerical QA against files other than those it checked."""
    for relative, expected in context["numerical_outputs"].items():
        path = asset_path(root, relative)
        try:
            with open(path, "rb") as handle:
                actual = hashlib.sha256(handle.read()).hexdigest()
        except FileNotFoundError:
            actual = None
        if actual != expected:
            raise ValueError("IPPU numerical output changed or missing: %s; rebuild numerical stage" % relative)


def main():
    with open(asset_path(ROOT, "build", "ippu", "numerical_context.json"), encoding="utf-8") as handle:
        context = json.load(handle)
    if context.get("schema") != "pkinv.ippu-numerical-context/v1":
        raise ValueError("unsupported IPPU numerical context")
    validate_numerical_outputs(context)
    data = IppuMetadata()
    run = Runner("ippu_metadata", declared=OUTPUT_NAMES)
    rows = (data.completeness_rows, data.evidence_maturity_rows, completeness.request_rows(),
            data.hfc_import_contract_rows, data.data_request_packet_rows, data.source_manifest_rows)
    for name, values in zip(OUTPUT_NAMES, rows):
        run.write_dicts(name, values)
    run.finalize()
    checks = combined_checks(context, metadata_checks(data))
    write_table(asset_path(OUTPUTS, "ippu_qa_2024.csv"), QA_FIELDS, checks)
    failing = [row for row in checks if not row["passed"]]
    if failing:
        raise AssertionError("ippu QA failed: %s" % failing)
    manifest = dict(context["manifest"])
    manifest["inputs"] = []
    for relative in INPUT_PATHS:
        with open(resolve(asset_path(ROOT, relative)), "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        manifest["inputs"].append({"path": relative, "sha256": digest})
    with open(asset_path(OUTPUTS, "ippu_run_manifest_2024.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    print("IPPU metadata: six registers, combined QA and source manifest published")


if __name__ == "__main__":
    main()
