"""Observed monthly OCAC--OECD reconciliation from cumulative public reports."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
from collections import defaultdict
import csv
import hashlib
import os
import re
import subprocess

from pkinv.paths import DATA, ROOT

ACTIVITY = asset_path(DATA, "activity", "aviation")
SOURCE_DIR = asset_path(ROOT, "sources", "Aviation", "ocac_monthly")
OECD_SOURCE = asset_path(ROOT, "sources", "Aviation",
                           "OECD_air_transport_PAK_2019_2025.csv")
CUSTOMERS = ("Domestic Avi-PIA", "Domestic Avi-Others",
             "Overseas/Foreign Aviation", "Government Aviation", "Government Other")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pdf_text(path):
    result = subprocess.run(["pdftotext", "-layout", path, "-"], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.split("\f", 1)[0]


def _column_span(header, column):
    names = ["100 LL", "HOBC", "NAPHTHA", "MS", "JP-8", "JP-1", "KERO",
             "HSD", "LDO", "FO", "TOTAL"]
    positions = [(name, header.find(name)) for name in names if header.find(name) >= 0]
    positions.sort(key=lambda x: x[1])
    index = next(i for i, (name, _p) in enumerate(positions) if name == column)
    center = positions[index][1] + len(column) / 2.0
    previous = (positions[index - 1][1] + len(positions[index - 1][0]) / 2.0
                if index else 0.0)
    following = (positions[index + 1][1] + len(positions[index + 1][0]) / 2.0
                 if index + 1 < len(positions) else len(header))
    return int((previous + center) / 2.0), int((center + following) / 2.0)


def _number(fragment):
    match = re.search(r"\d[\d, ]*", fragment)
    return float(re.sub(r"[, ]", "", match.group(0))) if match else 0.0


def extract_cumulative(path):
    """Read first-page Pakistan JP-1 source rows, using printed column positions."""
    text = _pdf_text(path)
    lines = text.splitlines()
    header = next(line for line in lines if "SECTOR" in line and "JP-1" in line)
    left, right = _column_span(header, "JP-1")
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
        if "Domestic Avi-PIA" in line:
            values["Domestic Avi-PIA"] = _number(line[left:right])
        elif "Domestic Avi-Others" in line:
            values["Domestic Avi-Others"] = _number(line[left:right])
        elif section == "government" and re.match(r"\s*Aviation\b", line):
            values["Government Aviation"] = _number(line[left:right])
        elif section == "government" and re.match(r"\s*Others\b", line):
            values["Government Other"] = _number(line[left:right])
        elif section == "overseas" and re.match(r"\s*Aviation\b", line):
            values["Overseas/Foreign Aviation"] = _number(line[left:right])
    missing = set(CUSTOMERS) - set(values)
    if missing:
        raise ValueError("%s: missing OCAC rows %s" % (path, ", ".join(sorted(missing))))
    return values


# rc41: CONSUMED DERIVATIVES. The reconciliation study read 48 OCAC monthly PDFs
# (pdftotext), the OECD air-transport csv, two Climate TRACE JSON packages, the ERA5
# route-weather NetCDF and the ADS-B pilot package live - none of which the validation
# package ships. scripts/ingest_aviation_study_inputs.py runs the extract_* functions
# below over the held documents into tables under data/activity/aviation/ with exactly
# the columns the study reads (data/consumed_derivatives.csv); the study reads the
# tables, and --check re-derives them wherever the documents are held.
OCAC_EXTRACT = asset_path(ACTIVITY, "ocac_monthly_extract.csv")
OCAC_EXTRACT_FIELDS = ("fiscal_year", "period_end", "period_index", "report_kind",
                       "local_file", "source_sha256", "customer_category", "reported_t")
OECD_EXTRACT = asset_path(ACTIVITY, "oecd_monthly_extract.csv")
OECD_EXTRACT_FIELDS = ("fiscal_year", "month", "territory_domestic_co2_t",
                       "territory_international_co2_t", "territory_combined_co2_t",
                       "resident_combined_co2_t", "foreign_combined_co2_t")


def _sources(source_csv):
    return list(_activity_rows(source_csv, comments=False))


def extract_ocac_monthly(source_csv=None, source_dir=None):
    """Every tracked OCAC monthly report's five JP-1 customer cells, from the PDFs."""
    sources = _sources(source_csv or asset_path(ACTIVITY, "ocac_cumulative_sources.csv"))
    source_dir = source_dir or SOURCE_DIR
    rows = []
    for src in sorted(sources, key=lambda r: (int(r["fiscal_year"]), int(r["period_index"]))):
        path = asset_path(source_dir, src["local_file"])
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        values = extract_cumulative(path)
        digest = _sha256(path)
        for customer in CUSTOMERS:
            rows.append({"fiscal_year": int(src["fiscal_year"]), "period_end": src["period_end"],
                         "period_index": int(src["period_index"]),
                         "report_kind": src["report_kind"].strip().lower(),
                         "local_file": src["local_file"], "source_sha256": digest,
                         "customer_category": customer, "reported_t": values[customer]})
    return rows


def ocac_monthly(source_csv=None, extract_csv=None):
    from pkinv.activity.store import read_rows

    sources = _sources(source_csv or asset_path(ACTIVITY, "ocac_cumulative_sources.csv"))
    extract = {(row["local_file"], row["customer_category"]): row
               for row in read_rows(extract_csv or OCAC_EXTRACT)}
    cumulative, monthly = [], []
    previous = {}
    for src in sorted(sources, key=lambda r: (int(r["fiscal_year"]), int(r["period_index"]))):
        year = int(src["fiscal_year"])
        for customer in CUSTOMERS:
            cell = extract.get((src["local_file"], customer))
            if cell is None:
                raise KeyError("%s: no row for %r in %s - run scripts/ingest_aviation_study_inputs.py "
                               "over the held reports" % (src["local_file"], customer, OCAC_EXTRACT))
            value = float(cell["reported_t"])
            prior = previous.get((year, customer), 0.0)
            report_kind = src["report_kind"].strip().lower()
            if report_kind == "monthly":
                difference = value
                running_total = prior + value
            elif report_kind == "cumulative":
                difference = value - prior
                running_total = value
            else:
                raise ValueError("%s: unknown report_kind %r" % (src["local_file"], report_kind))
            status = "PASS" if difference >= 0 else "REVISION_NEGATIVE"
            base = {"fiscal_year": year, "period_end": src["period_end"],
                    "period_index": int(src["period_index"]), "customer_category": customer,
                    "fuel_type": "JP-1", "source_url": src["source_url"],
                    "source_file": src["local_file"], "source_sha256": cell["source_sha256"],
                    "report_kind": report_kind, "reported_t": value,
                    "revision_note": src["revision_note"]}
            cumulative.append({**base, "cumulative_t": running_total})
            monthly.append({**base, "monthly_t": difference, "difference_status": status})
            previous[(year, customer)] = running_total
    return cumulative, monthly


def oecd_monthly(extract_csv=None):
    from pkinv.core.documents import read_extract

    return read_extract(extract_csv or OECD_EXTRACT,
                        {"fiscal_year": int, **{f: float for f in OECD_EXTRACT_FIELDS[2:]}})


def extract_oecd_monthly(path=None):
    path = path or OECD_SOURCE
    raw = list(_activity_rows(path, comments=False))
    wanted = {"TER_DOM", "TER_INT", "RES_DOM_IN", "RES_INT_FROM",
              "NRES_DOM_IN", "NRES_INT_FROM"}
    values = defaultdict(float)
    for row in raw:
        if row["FLIGHT_TYPE"] == "_T" and row["EMISSIONS_SOURCE"] in wanted:
            values[(row["TIME_PERIOD"], row["EMISSIONS_SOURCE"])] += float(row["OBS_VALUE"])
    rows = []
    for month in sorted({month for month, _code in values}):
        fiscal_year = int(month[:4]) if int(month[5:]) >= 7 else int(month[:4]) - 1
        territory_domestic = values[(month, "TER_DOM")]
        territory_international = values[(month, "TER_INT")]
        resident = values[(month, "RES_DOM_IN")] + values[(month, "RES_INT_FROM")]
        foreign = values[(month, "NRES_DOM_IN")] + values[(month, "NRES_INT_FROM")]
        rows.append({"fiscal_year": fiscal_year, "month": month,
                     "territory_domestic_co2_t": territory_domestic,
                     "territory_international_co2_t": territory_international,
                     "territory_combined_co2_t": territory_domestic + territory_international,
                     "resident_combined_co2_t": resident, "foreign_combined_co2_t": foreign})
    return rows


def reconciliation(monthly_fuel, monthly_oecd, co2_per_t=3.16):
    fuel = defaultdict(float)
    for row in monthly_fuel:
        fuel[(int(row["fiscal_year"]), row["period_end"], row["customer_category"])] += float(row["monthly_t"])
    oecd = {(int(row["fiscal_year"]), row["month"]): row for row in monthly_oecd}
    rows = []
    for year, month in sorted({(y, m) for y, m, _c in fuel}):
        benchmark = oecd.get((year, month))
        if not benchmark:
            continue
        resident_fuel = sum(fuel[(year, month, c)] for c in
                            ("Domestic Avi-PIA", "Domestic Avi-Others"))
        foreign_fuel = fuel[(year, month, "Overseas/Foreign Aviation")]
        commercial_fuel = resident_fuel + foreign_fuel
        resident_co2 = resident_fuel * co2_per_t
        foreign_co2 = foreign_fuel * co2_per_t
        total_co2 = commercial_fuel * co2_per_t
        rows.append({
            "fiscal_year": year, "month": month, "resident_ocac_fuel_t": resident_fuel,
            "foreign_ocac_fuel_t": foreign_fuel, "commercial_ocac_fuel_t": commercial_fuel,
            "resident_ocac_co2_t": resident_co2, "resident_oecd_co2_t": benchmark["resident_combined_co2_t"],
            "resident_ratio": resident_co2 / benchmark["resident_combined_co2_t"] if benchmark["resident_combined_co2_t"] else "",
            "foreign_ocac_co2_t": foreign_co2, "foreign_oecd_co2_t": benchmark["foreign_combined_co2_t"],
            "foreign_ratio": foreign_co2 / benchmark["foreign_combined_co2_t"] if benchmark["foreign_combined_co2_t"] else "",
            "combined_ocac_co2_t": total_co2,
            "combined_oecd_co2_t": benchmark["territory_combined_co2_t"],
            "combined_ratio": total_co2 / benchmark["territory_combined_co2_t"] if benchmark["territory_combined_co2_t"] else "",
            "domestic_oecd_co2_t": benchmark["territory_domestic_co2_t"],
            "resident_difference_t": resident_co2 - benchmark["resident_combined_co2_t"],
            "foreign_difference_t": foreign_co2 - benchmark["foreign_combined_co2_t"],
            "combined_difference_t": total_co2 - benchmark["territory_combined_co2_t"],
        })
    return rows


def summary(rows):
    output = []
    for year in sorted({int(r["fiscal_year"]) for r in rows}):
        selected = [r for r in rows if int(r["fiscal_year"]) == year]
        for component in ("resident", "foreign", "combined"):
            ratios = [float(r[component + "_ratio"]) for r in selected
                      if r[component + "_ratio"] != ""]
            differences = [float(r[component + "_difference_t"]) for r in selected]
            denominators = [float(r[component + "_oecd_co2_t"]) for r in selected]
            output.append({"fiscal_year": year, "component": component,
                           "months_available": len(ratios),
                           "mean_monthly_ratio": sum(ratios) / len(ratios),
                           "monthly_mape_pct": sum(abs(x - 1) for x in ratios) / len(ratios) * 100,
                           "annual_signed_bias_pct": sum(differences) / sum(denominators) * 100})
    return output
