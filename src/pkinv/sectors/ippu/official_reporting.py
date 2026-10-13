"""Cell-audited extraction of Pakistan's 2022 IPPU Common Reporting Tables."""
from __future__ import annotations

import hashlib
import io
import os
import zipfile

from pkinv.paths import ROOT
from pkinv.core import documents
from pkinv.core.source_extracts import materialized
from pkinv.assets import asset_path

CRT_SOURCE = asset_path(ROOT, "sources", "Aviation", "PAK_CRT_2024.zip")
CRT_WORKBOOK = "IPPU-PAK-CRT.xlsx"


def _payload(path=CRT_SOURCE):
    documents.require(path, "the UNFCCC CRT tables are read here")
    with open(path, "rb") as handle:
        package = handle.read()
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        workbook = archive.read(CRT_WORKBOOK)
    return package, workbook


def _hashes(path=CRT_SOURCE):
    package, workbook = _payload(path)
    return (package, workbook, hashlib.sha256(package).hexdigest(),
            hashlib.sha256(workbook).hexdigest())


@materialized("ippu_extract_summary")
def extract_summary(path=CRT_SOURCE):
    """Extract native gases and reported F-gas CO2e from Table 2(I)."""
    from openpyxl import load_workbook

    package, payload, package_hash, workbook_hash = _hashes(path)
    del package
    workbook = load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
    sheet = workbook["Table2(I)"]
    output = []
    for row_number, values in enumerate(sheet.iter_rows(
            min_row=10, max_row=61, min_col=2, max_col=15, values_only=True), 10):
        values = list(values)
        label = str(values[0] or "").strip()
        if not label:
            continue
        output.append({
            "inventory_year": int(sheet["O1"].value), "worksheet": sheet.title,
            "row": row_number, "category": label,
            "co2_kt": values[1], "ch4_kt": values[2], "n2o_kt": values[3],
            "hfc_co2e_kt": values[4], "pfc_co2e_kt": values[5],
            "mixed_hfc_pfc_co2e_kt": values[6], "sf6_kt": values[7],
            "nf3_kt": values[8], "nox_kt": values[9], "co_kt": values[10],
            "nmvoc_kt": values[11], "sox_kt": values[12],
            "total_co2e_kt": values[13],
            "source_reference": "Table2(I)!B%d:O%d" % (row_number, row_number),
            "source_zip_sha256": package_hash, "workbook_sha256": workbook_hash,
        })
    return output


@materialized("ippu_extract_background")
def extract_background(path=CRT_SOURCE):
    """Extract the category activity/factor/emission/recovery ledger."""
    from openpyxl import load_workbook

    _package, payload, package_hash, workbook_hash = _hashes(path)
    workbook = load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
    sheet = workbook["Table2(I).A-H"]
    output = []
    for row_number, values in enumerate(sheet.iter_rows(
            min_row=10, max_row=95, min_col=2, max_col=14, values_only=True), 10):
        values = list(values)
        label = str(values[0] or "").strip()
        if not label:
            continue
        output.append({
            "inventory_year": int(sheet["N1"].value), "worksheet": sheet.title,
            "row": row_number, "category": label,
            "activity_description": values[1], "activity_kt": values[2],
            "co2_ief_t_per_t": values[3], "ch4_ief_t_per_t": values[4],
            "n2o_ief_t_per_t": values[5], "co2_kt": values[6],
            "ch4_kt": values[7], "n2o_kt": values[8],
            "co2_fossil_recovery_kt": values[9],
            "co2_biogenic_recovery_kt": values[10],
            "ch4_recovery_kt": values[11], "n2o_recovery_kt": values[12],
            "source_reference": "Table2(I).A-H!B%d:N%d" % (row_number, row_number),
            "source_zip_sha256": package_hash, "workbook_sha256": workbook_hash,
        })
    return output


def reproduce_background(path=CRT_SOURCE, tolerance_kt=1e-6):
    """Reproduce every numeric activity x IEF row, including reported recovery."""
    output = []
    for row in extract_background(path):
        activity = row["activity_kt"]
        if not isinstance(activity, (int, float)):
            continue
        gases = (("CO2", "co2_ief_t_per_t", "co2_kt",
                  ("co2_fossil_recovery_kt", "co2_biogenic_recovery_kt")),
                 ("CH4", "ch4_ief_t_per_t", "ch4_kt", ("ch4_recovery_kt",)),
                 ("N2O", "n2o_ief_t_per_t", "n2o_kt", ("n2o_recovery_kt",)))
        for gas, factor_field, emission_field, recovery_fields in gases:
            factor, reported = row[factor_field], row[emission_field]
            if not isinstance(factor, (int, float)) or not isinstance(reported, (int, float)):
                continue
            recovery = sum(float(row[field]) for field in recovery_fields
                           if isinstance(row[field], (int, float)))
            calculated = float(activity) * float(factor) + recovery
            difference = calculated - float(reported)
            output.append({
                "inventory_year": row["inventory_year"], "worksheet": row["worksheet"],
                "row": row["row"], "category": row["category"], "gas": gas,
                "activity_kt": activity, "ief_t_per_t": factor,
                "recovery_kt": recovery, "calculated_final_kt": calculated,
                "reported_final_kt": reported, "difference_kt": difference,
                "closes": abs(difference) <= tolerance_kt,
                "formula": "activity_kt * IEF_t_per_t + reported_recovery_kt",
            })
    return output


@materialized("ippu_extract_fgas_species")
def extract_fgas_species(path=CRT_SOURCE):
    """Retain every numeric F-gas species row and its aggregation level."""
    from openpyxl import load_workbook

    _package, payload, package_hash, workbook_hash = _hashes(path)
    workbook = load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
    sheet = workbook["Table2(II).B-Hs2"]
    output, parent = [], ""
    for row_number, values in enumerate(sheet.iter_rows(
            min_row=10, max_row=sheet.max_row, min_col=2, max_col=12,
            values_only=True), 10):
        values = list(values)
        label = str(values[0] or "").strip()
        if label.startswith("2."):
            parent = label
            continue
        emissions = [values[index] for index in (8, 9, 10)]
        if not label or not any(isinstance(value, (int, float)) for value in emissions):
            continue
        output.append({
            "inventory_year": int(sheet["M1"].value), "worksheet": sheet.title,
            "row": row_number, "parent_category": parent, "species": label,
            "manufacturing_emissions_t": emissions[0],
            "stock_emissions_t": emissions[1], "disposal_emissions_t": emissions[2],
            "numeric_emissions_t": sum(float(value) for value in emissions
                                       if isinstance(value, (int, float))),
            "aggregation_level": parent.split(".")[1].count(".") + 1 if "." in parent else 0,
            "source_reference": "%s!B%d:L%d" % (sheet.title, row_number, row_number),
            "source_zip_sha256": package_hash, "workbook_sha256": workbook_hash,
        })
    return output


@materialized("ippu_audit_cells")
def audit_cells(path=CRT_SOURCE):
    """Create a reviewable raw-cell trail for all principal IPPU tables."""
    from openpyxl import load_workbook

    _package, payload, package_hash, workbook_hash = _hashes(path)
    workbook = load_workbook(io.BytesIO(payload), data_only=False, read_only=False)
    regions = (("Table2(I)", 10, 61, 2, 15),
               ("Table2(I).A-H", 10, 95, 2, 14))
    output = []
    for sheet_name, row_start, row_end, col_start, col_end in regions:
        sheet = workbook[sheet_name]
        for row in range(row_start, row_end + 1):
            for column in range(col_start, col_end + 1):
                cell = sheet.cell(row, column)
                if cell.value is None:
                    continue
                raw = str(cell.value)
                output.append({
                    "worksheet": sheet_name, "cell": cell.coordinate,
                    "raw_value": raw, "cell_value_sha256": hashlib.sha256(
                        raw.encode("utf-8")).hexdigest(),
                    "formula": raw if cell.data_type == "f" else "",
                    "source_zip_sha256": package_hash, "workbook_sha256": workbook_hash,
                })
    return output
