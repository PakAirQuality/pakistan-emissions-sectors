"""Cell-audited extraction of Pakistan's 2022 UNFCCC 1.B.2 CRT."""
from __future__ import annotations

from pkinv.assets import asset_path

import hashlib
import io
import os
import zipfile
from collections import defaultdict

from pkinv.paths import ROOT
from pkinv.sectors.fugitives import segment_inventory
from pkinv.core import documents
from pkinv.core.source_extracts import materialized

CRT_SOURCE = asset_path(ROOT, "sources", "Aviation", "PAK_CRT_2024.zip")
CRT_WORKBOOK = "ENERGY-PAK-CRT.xlsx"


def _payload(path=CRT_SOURCE):
    documents.require(path, "the UNFCCC CRT tables are read here")
    with open(path, "rb") as handle:
        package = handle.read()
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        workbook = archive.read(CRT_WORKBOOK)
    return package, workbook


@materialized("fugitives_extract_crt")
def extract_crt(path=CRT_SOURCE):
    from openpyxl import load_workbook

    package, workbook_payload = _payload(path)
    workbook = load_workbook(io.BytesIO(workbook_payload), data_only=True,
                             read_only=True)
    summary = workbook["Table1"]
    detailed = workbook["Table1.B.2"]
    output = []
    for row_number, row in enumerate(detailed.iter_rows(values_only=True), 1):
        label = str(row[1] or "").strip()
        if not label.startswith("1.B.2") or row_number in (10, 20, 31, 40):
            continue
        output.append({
            "inventory_year": int(detailed["L1"].value),
            "worksheet": "Table1.B.2",
            "row": row_number,
            "category": label,
            "activity_type": row[2],
            "activity_unit": row[3],
            "activity_value": row[4],
            "co2_ief_kg_per_unit": row[5],
            "ch4_ief_kg_per_unit": row[6],
            "n2o_ief_kg_per_unit": row[7],
            "co2_kt": row[8],
            "ch4_kt": row[9],
            "n2o_kt": row[10],
            "notation_key": row[11],
            "source_reference": "Table1.B.2!B%d:L%d" % (row_number, row_number),
        })
    total_row = list(summary.iter_rows(min_row=42, max_row=42, values_only=True))[0]
    total = {
        "inventory_year": int(detailed["L1"].value),
        "category": total_row[1],
        "co2_kt": float(total_row[2]),
        "ch4_kt": float(total_row[3]),
        "n2o_kt": float(total_row[4]),
        "total_co2e_kt": float(total_row[9]),
        "source_reference": "Table1!B42:J42",
        "source_zip_file": os.path.basename(path),
        "source_zip_sha256": hashlib.sha256(package).hexdigest(),
        "workbook_file": CRT_WORKBOOK,
        "workbook_sha256": hashlib.sha256(workbook_payload).hexdigest(),
    }
    return total, output


@materialized("fugitives_audit_cells")
def audit_cells(path=CRT_SOURCE):
    from openpyxl import load_workbook

    package, workbook_payload = _payload(path)
    workbook = load_workbook(io.BytesIO(workbook_payload), data_only=False,
                             read_only=False)
    specifications = [
        ("Table1", "C42", "1B2_CO2", "kt CO2"),
        ("Table1", "D42", "1B2_CH4", "kt CH4"),
        ("Table1", "E42", "1B2_N2O", "kt N2O"),
        ("Table1", "J42", "1B2_total", "kt CO2e"),
    ]
    for row in range(11, 41):
        specifications.extend([
            ("Table1.B.2", "B%d" % row, "row_%d_category" % row, "text"),
            ("Table1.B.2", "E%d" % row, "row_%d_activity" % row, "reported unit"),
            ("Table1.B.2", "I%d" % row, "row_%d_CO2" % row, "kt CO2"),
            ("Table1.B.2", "J%d" % row, "row_%d_CH4" % row, "kt CH4"),
            ("Table1.B.2", "K%d" % row, "row_%d_N2O" % row, "kt N2O"),
            ("Table1.B.2", "L%d" % row, "row_%d_notation" % row, "notation key"),
        ])
    output = []
    for sheet, cell, field, unit in specifications:
        value = workbook[sheet][cell].value
        output.append({
            "worksheet": sheet,
            "cell": cell,
            "field": field,
            "raw_value": value,
            "unit": unit,
            "formula": value if workbook[sheet][cell].data_type == "f" else "",
            "source_zip_sha256": hashlib.sha256(package).hexdigest(),
            "workbook_sha256": hashlib.sha256(workbook_payload).hexdigest(),
        })
    return output


def reproduce_reported_rows(path=CRT_SOURCE):
    """Test whether reported activity times IEF reproduces each native-gas cell."""
    _total, rows = extract_crt(path)
    output = []
    gas_fields = (("CO2", "co2_ief_kg_per_unit", "co2_kt"),
                  ("CH4", "ch4_ief_kg_per_unit", "ch4_kt"),
                  ("N2O", "n2o_ief_kg_per_unit", "n2o_kt"))
    for row in rows:
        if not isinstance(row["activity_value"], (int, float)):
            continue
        for gas, factor_field, emission_field in gas_fields:
            factor = row[factor_field]
            reported = row[emission_field]
            if not isinstance(factor, (int, float)) or not isinstance(reported, (int, float)):
                continue
            calculated = float(row["activity_value"]) * float(factor) / 1_000_000.0
            output.append({
                "inventory_year": row["inventory_year"],
                "worksheet": row["worksheet"],
                "row": row["row"],
                "category": row["category"],
                "gas": gas,
                "activity_value": row["activity_value"],
                "activity_unit": row["activity_unit"],
                "ief_kg_per_unit": factor,
                "calculated_kt": calculated,
                "reported_kt": reported,
                "difference_kt": calculated - float(reported),
                "closes": abs(calculated - float(reported)) < 1e-9,
                "formula": "activity_value * IEF_kg_per_unit / 1e6",
            })
    return output


COMMON_GWP = {"CO2": 1.0, "CH4": 30.0, "N2O": 265.0}


def _native_total(rows):
    gases = defaultdict(float)
    for row in rows:
        for gas, field in (("CO2", "co2_kt"), ("CH4", "ch4_kt"),
                           ("N2O", "n2o_kt")):
            value = row.get(field)
            if isinstance(value, (int, float)):
                gases[gas] += float(value)
    return dict(gases)


def _inventory_native(rows, segments):
    gases = defaultdict(float)
    for row in rows:
        if row["subitem"] in segments:
            gases[row["gas"]] += float(row["emissions_Gg"])
    return dict(gases)


def _common_mt(gases):
    return sum(gases.get(gas, 0.0) * gwp for gas, gwp in COMMON_GWP.items()) / 1000.0


def _subtract(left, right):
    return {gas: left.get(gas, 0.0) - right.get(gas, 0.0) for gas in COMMON_GWP}


def _add(left, right):
    return {gas: left.get(gas, 0.0) + right.get(gas, 0.0) for gas in COMMON_GWP}


def official_common_metric(path=CRT_SOURCE):
    """Preserve the submitted value and provide a native-gas common-GWP comparison."""
    total, _rows = extract_crt(path)
    gases = {"CO2": total["co2_kt"], "CH4": total["ch4_kt"],
             "N2O": total["n2o_kt"]}
    return {
        **total,
        "submitted_mt_co2e": total["total_co2e_kt"] / 1000.0,
        "common_ar5_fossil_ch4_mt_co2e": _common_mt(gases),
        "submitted_implied_ch4_gwp": ((total["total_co2e_kt"] - total["co2_kt"] -
                                        total["n2o_kt"] * 265.0) / total["ch4_kt"]),
        "common_metric_note": "CO2=1, fossil CH4=30 and N2O=265; native gases unchanged",
    }


def reconstruction_waterfall(data, year=2022, path=CRT_SOURCE):
    """Decompose the official-to-reconstructed difference without mixing GWPs."""
    total, official_rows = extract_crt(path)
    if total["inventory_year"] != year:
        raise ValueError("CRT year and reconstruction year differ")
    reconstructed = segment_inventory.inventory_rows(data, year=year)
    official_by_row = {row["row"]: row for row in official_rows}
    current = {"CO2": total["co2_kt"], "CH4": total["ch4_kt"],
               "N2O": total["n2o_kt"]}
    output = []

    def append(label, delta, role, note):
        nonlocal current
        current = _add(current, delta)
        output.append({
            "order": len(output), "step": label, "role": role,
            "delta_ch4_Gg": delta.get("CH4", 0.0),
            "delta_co2_Gg": delta.get("CO2", 0.0),
            "delta_n2o_Gg": delta.get("N2O", 0.0),
            "delta_common_mt_co2e": _common_mt(delta),
            "cumulative_ch4_Gg": current.get("CH4", 0.0),
            "cumulative_co2_Gg": current.get("CO2", 0.0),
            "cumulative_n2o_Gg": current.get("N2O", 0.0),
            "cumulative_common_mt_co2e": _common_mt(current),
            "note": note,
        })

    append("Pakistan CRT 2022 on common GWP", {gas: 0.0 for gas in COMMON_GWP},
           "starting value", "Submitted native gases; CO2=1, fossil CH4=30, N2O=265")
    vent_flare = _native_total([official_by_row[32], official_by_row[36]])
    append("Remove separately reported venting and flaring",
           {gas: -vent_flare.get(gas, 0.0) for gas in COMMON_GWP},
           "boundary harmonization", "2019 Tier-1 segment factors are inclusive")

    replacements = [
        ("Replace oil production", [12], {"Oil production"}),
        ("Replace oil transport", [13], {"Oil pipeline transport"}),
        ("Replace oil refining", [14], {"Oil refining"}),
        ("Replace gas production and gathering", [22],
         {"Gas production", "Gas gathering"}),
        ("Replace gas processing", [23], {"Gas processing", "Sour-gas processing"}),
        ("Replace gas transmission", [24], {"Gas transmission"}),
        ("Replace gas distribution", [25], {"Gas distribution"}),
    ]
    for label, official_ids, segments in replacements:
        old = _native_total([official_by_row[index] for index in official_ids])
        new = _inventory_native(reconstructed, segments)
        append(label, _subtract(new, old), "matched-category replacement",
               "official row(s) %s -> %s" % (official_ids, "; ".join(sorted(segments))))

    additions = [
        ("Add LNG import terminals", {"LNG import terminals"}),
        ("Add post-meter appliances", {"Post-meter appliances"}),
        ("Add post-meter industrial and power", {"Post-meter industrial and power"}),
    ]
    for label, segments in additions:
        append(label, _inventory_native(reconstructed, segments),
               "public-data 2019 segment absent from CRT", "; ".join(sorted(segments)))

    target = _inventory_native(reconstructed, {row["subitem"] for row in reconstructed})
    residual = _subtract(target, current)
    append("Numerical closure", residual, "rounding/assertion residual",
           "must close exactly to the reconstructed native-gas ledger")
    if any(abs(value) > 1e-9 for value in _subtract(current, target).values()):
        raise AssertionError("CRT waterfall does not close to reconstructed ledger")
    return output


def fiscal_year_bracket(data, path=CRT_SOURCE):
    """Bracket calendar 2022 with the two adjacent public fiscal reconstructions."""
    official = official_common_metric(path)
    output = []
    for year, label in ((2022, "FY2021-22"), (2023, "FY2022-23")):
        rows = segment_inventory.inventory_rows(data, year=year)
        gases = _inventory_native(rows, {row["subitem"] for row in rows})
        reconstructed = _common_mt(gases)
        output.append({
            "calendar_inventory_year": 2022,
            "adjacent_fiscal_period": label,
            "reconstructed_common_mt_co2e": reconstructed,
            "official_submitted_mt_co2e": official["submitted_mt_co2e"],
            "official_common_mt_co2e": official["common_ar5_fossil_ch4_mt_co2e"],
            "ratio_to_official_common_metric": (
                reconstructed / official["common_ar5_fossil_ch4_mt_co2e"]),
            "period_note": "fiscal bracketing only; no monthly interpolation",
        })
    return output
