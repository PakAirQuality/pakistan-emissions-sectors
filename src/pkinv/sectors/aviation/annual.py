"""Long-run OCAC aviation-fuel controls and matched OECD comparisons."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
from collections import defaultdict
import csv
import os
import re

from pkinv.paths import DATA, ROOT
from pkinv.sectors.aviation import monthly

ACTIVITY = asset_path(DATA, "activity", "aviation")
SOURCE_DIR = asset_path(ROOT, "sources", "Aviation", "ocac_annual")
SOURCE_CSV = asset_path(ACTIVITY, "ocac_annual_sources.csv")

ROWS = (
    ("Domestic Avi-PIA", "transport", r"Domestic Avi-PIA"),
    ("Domestic Avi-Others", "transport", r"Domestic Avi-Others"),
    ("Government Aviation", "government", r"Aviation\b"),
    ("Government Other", "government", r"Others\b"),
    ("Overseas/Foreign Aviation", "overseas", r"Aviation\b"),
)


def _extract_columns(path, fuels=("100 LL", "JP-8", "JP-1")):
    text = monthly._pdf_text(path)
    lines = text.splitlines()
    header = next(line for line in lines if "SECTOR" in line and "JP-1" in line)
    spans = {fuel: monthly._column_span(header, fuel) for fuel in fuels}
    values = {}
    section = ""
    for line in lines:
        stripped = line.strip()
        if stripped == "TRANSPORT":
            section = "transport"
        elif stripped == "GOVERNMENT":
            section = "government"
        elif stripped.startswith("OVERSEAS/FOREIGN"):
            section = "overseas"
        for customer, wanted_section, pattern in ROWS:
            if section != wanted_section or not re.match(r"\s*" + pattern, line):
                continue
            for fuel, (left, right) in spans.items():
                values[(customer, fuel)] = monthly._number(line[left:right])
    missing = {(customer, fuel) for customer, _section, _pattern in ROWS for fuel in fuels} - set(values)
    if missing:
        raise ValueError("%s: missing OCAC annual cells %s" % (path, sorted(missing)))
    return values


# rc41: the consumed derivative of the nine annual reports (see monthly.OCAC_EXTRACT).
EXTRACT_CSV = asset_path(ACTIVITY, "ocac_annual_extract.csv")
EXTRACT_FIELDS = ("fiscal_year", "period_label", "local_file", "source_sha256",
                  "customer_category", "fuel_type", "reported_t")


def extract_source_rows(source_csv=None, source_dir=None):
    """Every tracked OCAC annual report's customer x fuel cells, from the PDFs, in the
    order the report prints them (the study's product keeps that order)."""
    source_csv = source_csv or SOURCE_CSV
    source_dir = source_dir or SOURCE_DIR
    sources = list(_activity_rows(source_csv, comments=False))
    output = []
    for src in sources:
        path = asset_path(source_dir, src["local_file"])
        values = _extract_columns(path)
        digest = monthly._sha256(path)
        for (customer, fuel), tonnes in values.items():
            output.append({"fiscal_year": int(src["fiscal_year"]),
                           "period_label": src["period_label"], "local_file": src["local_file"],
                           "source_sha256": digest, "customer_category": customer,
                           "fuel_type": fuel, "reported_t": tonnes})
    return output


def source_rows(source_csv=None, extract_csv=None):
    """Return every tracked OCAC aviation source cell without reclassification."""
    from pkinv.activity.store import read_rows

    source_csv = source_csv or SOURCE_CSV
    sources = list(_activity_rows(source_csv, comments=False))
    cells = defaultdict(list)
    for row in read_rows(extract_csv or EXTRACT_CSV):
        cells[row["local_file"]].append(row)
    output = []
    for src in sources:
        if not cells.get(src["local_file"]):
            raise KeyError("%s: no rows in %s - run scripts/ingest_aviation_study_inputs.py "
                           "over the held reports" % (src["local_file"], EXTRACT_CSV))
        for cell in cells[src["local_file"]]:
            output.append({
                "fiscal_year": int(src["fiscal_year"]),
                "period_label": src["period_label"],
                "customer_category": cell["customer_category"],
                "fuel_type": cell["fuel_type"],
                "reported_t": float(cell["reported_t"]),
                "source_url": src["source_url"],
                "source_file": src["local_file"],
                "source_sha256": cell["source_sha256"],
                "revision_note": src["revision_note"],
                "classification_status": "customer-labelled; not IPCC geography",
            })
    return output


def summaries(rows, co2_per_t=3.16):
    by_year = defaultdict(lambda: defaultdict(float))
    for row in rows:
        by_year[int(row["fiscal_year"])][(row["customer_category"], row["fuel_type"])] += float(row["reported_t"])
    output = []
    for year, values in sorted(by_year.items()):
        resident = sum(values[(customer, "JP-1")] for customer in
                       ("Domestic Avi-PIA", "Domestic Avi-Others"))
        foreign = values[("Overseas/Foreign Aviation", "JP-1")]
        government = sum(values[(customer, "JP-1")] for customer in
                         ("Government Aviation", "Government Other"))
        jp8 = sum(value for (customer, fuel), value in values.items() if fuel == "JP-8")
        avgas = sum(value for (customer, fuel), value in values.items() if fuel == "100 LL")
        output.append({
            "fiscal_year": year,
            "resident_commercial_jp1_t": resident,
            "foreign_commercial_jp1_t": foreign,
            "commercial_jp1_t": resident + foreign,
            "government_jp1_t": government,
            "tracked_aviation_jp1_t": resident + foreign + government,
            "government_jp8_t": jp8,
            "tracked_100ll_t": avgas,
            "commercial_co2_t": (resident + foreign) * co2_per_t,
        })
    return output


def oecd_comparison(summaries_, oecd_rows, co2_per_t=3.16):
    grouped = defaultdict(lambda: defaultdict(float))
    months = defaultdict(set)
    for row in oecd_rows:
        year = int(row["fiscal_year"])
        months[year].add(row["month"])
        for key in ("territory_domestic_co2_t", "territory_international_co2_t",
                    "territory_combined_co2_t", "resident_combined_co2_t",
                    "foreign_combined_co2_t"):
            grouped[year][key] += float(row[key])
    output = []
    for item in summaries_:
        year = int(item["fiscal_year"])
        if not months[year]:
            continue
        complete = len(months[year]) == 12
        resident_co2 = item["resident_commercial_jp1_t"] * co2_per_t
        foreign_co2 = item["foreign_commercial_jp1_t"] * co2_per_t
        combined_co2 = resident_co2 + foreign_co2
        benchmark = grouped[year]
        output.append({
            "fiscal_year": year,
            "months_matched": len(months[year]),
            "period_status": "complete" if complete else "partial",
            "resident_ocac_co2_t": resident_co2,
            "resident_oecd_co2_t": benchmark["resident_combined_co2_t"],
            "resident_ratio": resident_co2 / benchmark["resident_combined_co2_t"],
            "foreign_ocac_co2_t": foreign_co2,
            "foreign_oecd_co2_t": benchmark["foreign_combined_co2_t"],
            "foreign_ratio": foreign_co2 / benchmark["foreign_combined_co2_t"],
            "combined_ocac_co2_t": combined_co2,
            "combined_oecd_co2_t": benchmark["territory_combined_co2_t"],
            "combined_ratio": combined_co2 / benchmark["territory_combined_co2_t"],
            "oecd_domestic_co2_t": benchmark["territory_domestic_co2_t"],
            "oecd_international_co2_t": benchmark["territory_international_co2_t"],
            "offset_cancellation_fraction": 1.0 - abs(
                (resident_co2 - benchmark["resident_combined_co2_t"]) +
                (foreign_co2 - benchmark["foreign_combined_co2_t"])) / max(1e-12,
                abs(resident_co2 - benchmark["resident_combined_co2_t"]) +
                abs(foreign_co2 - benchmark["foreign_combined_co2_t"])),
        })
    return output


def monthly_annual_closure(monthly_rows, annual_rows):
    monthly_values = defaultdict(float)
    for row in monthly_rows:
        monthly_values[(int(row["fiscal_year"]), row["customer_category"],
                        row["fuel_type"])] += float(row["monthly_t"])
    output = []
    for row in annual_rows:
        if row["fuel_type"] != "JP-1" or row["customer_category"] not in monthly.CUSTOMERS:
            continue
        key = (int(row["fiscal_year"]), row["customer_category"], row["fuel_type"])
        if key not in monthly_values:
            continue
        difference = monthly_values[key] - float(row["reported_t"])
        output.append({
            "fiscal_year": key[0], "customer_category": key[1], "fuel_type": key[2],
            "sum_public_monthly_t": monthly_values[key],
            "final_annual_report_t": float(row["reported_t"]),
            "monthly_minus_annual_t": difference,
            "closure_status": "exact" if abs(difference) < 1e-9 else "annual_revision_or_rounding",
        })
    return output
