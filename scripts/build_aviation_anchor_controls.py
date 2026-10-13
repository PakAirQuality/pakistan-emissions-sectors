"""Build source-faithful FY2023-24 aviation control tables.

The PCAA tables describe airport and airline activity; OCAC describes petroleum
customer classes.  This script deliberately preserves those source concepts instead
of translating them into IPCC categories during ingestion.
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
import subprocess

from pkinv.paths import DATA, ROOT
from ingest_aviation import parse_pdf
from pkinv.assets import asset_path

FY = 2023
LABEL = "2023-24"
SOURCE_DIR = asset_path(ROOT, "sources", "Aviation")
OUT_DIR = asset_path(DATA, "activity", "aviation")
AIRPORT_PDF = asset_path(SOURCE_DIR, "major-traffic-flow-airports-2023-24.pdf")
AIRLINE_PDF = asset_path(SOURCE_DIR, "major-traffic-flow-airlines-2023-24.pdf")
AIRPORT_REGISTER = asset_path(SOURCE_DIR, "ourairports_airports_2026-08-06.csv")
# Hand-resolved coordinates the snapshot cannot supply (Islamkot's OurAirports
# row matches none of the four code columns). A held row WINS over an absent
# match - the facility_geocoding_overrides discipline - so a rebuild can never
# regress a resolution to UNRESOLVED, which is what rc34 found it doing.
COORDINATE_OVERRIDES = asset_path(OUT_DIR, "airport_coordinate_overrides.csv")
ALIASES = asset_path(OUT_DIR, "airport_aliases.csv")
FUEL = asset_path(OUT_DIR, "fuel_sales.csv")
NUMBER = re.compile(r"-?[\d,]+(?:\.\d+)?")
AIRLINE_ROW = re.compile(r"^\s*([A-Z0-9]{3})\s+(.+)$")


def _write(name, rows, fields):
    path = asset_path(OUT_DIR, name)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def airport_controls():
    year, parsed, _ = parse_pdf(AIRPORT_PDF)
    if year != FY:
        raise ValueError("unexpected airport control year %s" % year)
    with open(ALIASES, newline="", encoding="utf-8") as handle:
        aliases = list(csv.DictReader(handle))
    by_icao = {row["icao"]: row for row in aliases if row["icao"]}
    rows = []
    for source in parsed:
        alias = by_icao.get(source["icao"])
        if not alias:
            raise ValueError("unresolved airport %s" % source["icao"])
        rows.append({
            "fiscal_year": FY, "fiscal_year_label": LABEL,
            "airport_icao": alias["icao"], "airport_iata": alias["iata"],
            "airport": alias["airport"], "province_territory": alias["province"],
            "domestic_commercial_movements": int(source["com_dom"]),
            "international_commercial_movements": int(source["com_intl"]),
            "noncommercial_movements": int(source["noncom"]),
            "domestic_passengers": int(source["pax_dom"]),
            "international_passengers": int(source["pax_intl"]),
            "domestic_cargo_t": source["cargo_dom_t"],
            "international_cargo_t": source["cargo_intl_t"],
            "domestic_mail_t": source["mail_dom_t"],
            "international_mail_t": source["mail_intl_t"],
            "source_reference": os.path.basename(AIRPORT_PDF),
            "source_sha256": _sha256(AIRPORT_PDF),
        })
    return sorted(rows, key=lambda row: row["airport_icao"])


def airline_controls():
    text = subprocess.run(["pdftotext", "-layout", AIRLINE_PDF, "-"], check=True,
                          capture_output=True, text=True).stdout
    section = None
    rows, pending = [], None
    for line in text.splitlines():
        stripped = line.strip()
        if "PAKISTAN CIVIL AVIATION AUTHORITY" in line or "Sub Total" in line or "Grand Total" in line:
            pending = None
        if stripped == "Domestic":
            section = "domestic"
            continue
        if stripped == "International":
            section = "international"
            continue
        if not section or "Sub Total" in line or "Grand Total" in line:
            continue
        match = AIRLINE_ROW.match(line)
        if not match:
            if (pending is not None and stripped and stripped == stripped.upper()
                    and len(stripped) <= 32 and not NUMBER.search(stripped)
                    and stripped not in {"AIRLINE", "SERVICES", "DOMESTIC", "INTERNATIONAL"}):
                pending["airline"] = (pending["airline"] + " " + stripped).strip()
            continue
        code, rest = match.groups()
        values = list(NUMBER.finditer(rest))
        if len(values) != 17:
            continue
        name = rest[:values[0].start()].strip()
        nums = [float(value.group().replace(",", "")) for value in values]
        dep, arr = int(nums[0]), int(nums[1])
        pending = {
            "fiscal_year": FY, "fiscal_year_label": LABEL, "traffic_scope": section,
            "airline_icao": code, "airline": " ".join(name.split()),
            "departures": dep, "arrivals": arr, "movements": dep + arr,
            "passengers_embarked": int(nums[2]), "passengers_disembarked": int(nums[3]),
            "passengers_terminal": int(nums[4]), "passengers_transit": int(nums[5]),
            "passengers_total": int(nums[6]),
            "cargo_loaded_t": nums[7], "cargo_unloaded_t": nums[8],
            "cargo_terminal_t": nums[9], "cargo_transit_t": nums[10],
            "cargo_total_t": nums[11], "mail_loaded_t": nums[12],
            "mail_unloaded_t": nums[13], "mail_terminal_t": nums[14],
            "mail_transit_t": nums[15], "mail_total_t": nums[16],
            "passengers_per_service_movement": nums[6] / (dep + arr) if dep + arr else "",
            "passengers_embarked_per_departure": nums[2] / dep if dep else "",
            "source_reference": os.path.basename(AIRLINE_PDF),
            "source_sha256": _sha256(AIRLINE_PDF),
        }
        rows.append(pending)
    if not rows:
        raise ValueError("no airline controls parsed")
    return rows


def fuel_controls():
    from pkinv.activity.compatibility_views import aviation_fuel_rows
    return aviation_fuel_rows()


def _coordinate_overrides():
    if not os.path.exists(COORDINATE_OVERRIDES):
        return {}
    with open(COORDINATE_OVERRIDES, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    return {row["airport_icao"]: row for row in rows}


def airports(controls):
    with open(AIRPORT_REGISTER, newline="", encoding="utf-8") as handle:
        register = list(csv.DictReader(handle))
    overrides = _coordinate_overrides()
    by_code = {}
    for row in register:
        for key in ("ident", "icao_code", "gps_code", "iata_code"):
            if row.get(key):
                by_code.setdefault(row[key].upper(), row)
    rows = []
    for control in controls:
        item = by_code.get(control["airport_icao"]) or by_code.get(control["airport_iata"])
        held = overrides.get(control["airport_icao"])
        if item is None and held is not None:
            item = held
        rows.append({
            "airport_icao": control["airport_icao"], "airport_iata": control["airport_iata"],
            "airport": control["airport"],
            "latitude_deg": item["latitude_deg"] if item else "",
            "longitude_deg": item["longitude_deg"] if item else "",
            "elevation_ft": item["elevation_ft"] if item else "",
            "province_territory": control["province_territory"],
            "commercial_service_fy2023_24": "yes" if (
                control["domestic_commercial_movements"] +
                control["international_commercial_movements"]) else "no",
            "domestic_service_fy2023_24": "yes" if control["domestic_commercial_movements"] else "no",
            "international_service_fy2023_24": "yes" if control["international_commercial_movements"] else "no",
            "coordinate_source": (item["coordinate_source"] if item is held and held
                                  else os.path.basename(AIRPORT_REGISTER) if item
                                  else "UNRESOLVED"),
            "coordinate_source_sha256": (item["coordinate_source_sha256"] if item is held and held
                                         else _sha256(AIRPORT_REGISTER) if item else ""),
        })
    return rows


def international_airports():
    """Coordinate controls for documented foreign endpoints only."""
    with open(AIRPORT_REGISTER, newline="", encoding="utf-8") as handle:
        register = list(csv.DictReader(handle))
    by_code = {}
    for row in register:
        for key in ("ident", "icao_code", "gps_code", "iata_code"):
            if row.get(key):
                by_code.setdefault(row[key].upper(), row)
    with open(asset_path(OUT_DIR, "route_evidence_2023_24.csv"), newline="",
              encoding="utf-8") as handle:
        evidence = [row for row in csv.DictReader(handle)
                    if row["boundary"] == "international"]
    codes = sorted({row[field] for row in evidence
                    for field in ("origin_icao", "destination_icao")
                    if row[field] and not row[field].startswith("OP")})
    rows = []
    for code in codes:
        item = by_code.get(code)
        if not item:
            raise ValueError("unresolved international route airport %s" % code)
        rows.append({
            "airport_icao": code, "airport_iata": item.get("iata_code", ""),
            "airport": item.get("name", ""), "latitude_deg": item["latitude_deg"],
            "longitude_deg": item["longitude_deg"],
            "elevation_ft": item.get("elevation_ft", ""),
            "country_code": item.get("iso_country", ""),
            "coordinate_source": os.path.basename(AIRPORT_REGISTER),
            "coordinate_source_sha256": _sha256(AIRPORT_REGISTER),
        })
    return rows


def main():
    airport_rows = airport_controls()
    airline_rows = airline_controls()
    fuel_rows = fuel_controls()
    _write("airport_controls_2023_24.csv", airport_rows, list(airport_rows[0]))
    _write("airline_controls_2023_24.csv", airline_rows, list(airline_rows[0]))
    airport_metadata = airports(airport_rows)
    _write("airports.csv", airport_metadata, list(airport_metadata[0]))
    international_metadata = international_airports()
    _write("international_airports.csv", international_metadata,
           list(international_metadata[0]))
    _, _, printed = parse_pdf(AIRPORT_PDF)
    mappings = {
        "domestic_commercial_movements": "com_dom",
        "international_commercial_movements": "com_intl",
        "noncommercial_movements": "noncom",
        "domestic_passengers": "pax_dom", "international_passengers": "pax_intl",
        "domestic_cargo_t": "cargo_dom_t", "international_cargo_t": "cargo_intl_t",
        "domestic_mail_t": "mail_dom_t", "international_mail_t": "mail_intl_t",
    }
    reconciliation = []
    for field, source_field in mappings.items():
        row_sum = sum(float(row[field]) for row in airport_rows)
        national = float(printed[source_field])
        reconciliation.append({"control_table": "airport", "field": field,
                               "published_national_total": national,
                               "published_row_sum": row_sum,
                               "source_table_difference": national - row_sum,
                               "status": "exact" if abs(national - row_sum) < 1e-9
                               else "published_rounding_or_source_discrepancy"})
    domestic_airline_movements = sum(row["movements"] for row in airline_rows
                                     if row["traffic_scope"] == "domestic")
    reconciliation.append({"control_table": "airline_vs_airport",
                           "field": "domestic_commercial_movements",
                           "published_national_total": sum(
                               row["domestic_commercial_movements"] for row in airport_rows),
                           "published_row_sum": domestic_airline_movements,
                           "source_table_difference": 40600 - domestic_airline_movements,
                           "status": "explicit_scope_residual"})
    _write("control_reconciliation_2023_24.csv", reconciliation,
           list(reconciliation[0]))
    print("airport controls=%d airline controls=%d fuel controls=%d airports=%d foreign endpoints=%d" %
          (len(airport_rows), len(airline_rows), len(fuel_rows), len(airport_metadata),
           len(international_metadata)))


if __name__ == "__main__":
    main()
