"""Climate TRACE national, monthly and airport aviation corroboration."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
from collections import defaultdict
import csv
import json
import math
import os

from scipy.stats import spearmanr

from pkinv.paths import DATA, ROOT

NATIONAL = asset_path(ROOT, "sources", "Aviation",
                        "climatetrace_aviation_PAK_2015_2024.json")
AIRPORTS = asset_path(ROOT, "sources", "Aviation",
                        "climatetrace_airports_PAK_2021_2024.json")
ACTIVITY = asset_path(DATA, "activity", "aviation")


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# rc41: consumed derivatives of the two Climate TRACE packages (see
# monthly.OCAC_EXTRACT). The airport table embeds the nearest-airport match the
# extractor made against data/activity/aviation/airports.csv, so --check also
# re-derives that match.
NATIONAL_EXTRACT = asset_path(ACTIVITY, "climatetrace_national_monthly_extract.csv")
NATIONAL_FIELDS = ("calendar_year", "month", "fiscal_year", "scope", "co2_t", "source",
                   "independence", "license")
AIRPORTS_EXTRACT = asset_path(ACTIVITY, "climatetrace_airport_monthly_extract.csv")
AIRPORTS_FIELDS = ("source_id", "source_name", "scope", "month", "fiscal_year", "co2_t",
                   "fuel_t", "flight_count", "airport_icao", "airport_iata",
                   "match_distance_km", "match_status")


def national_monthly(extract_csv=None):
    from pkinv.core.documents import read_extract

    return read_extract(extract_csv or NATIONAL_EXTRACT,
                        {"calendar_year": int, "fiscal_year": int, "co2_t": float})


def airport_monthly(extract_csv=None):
    from pkinv.core.documents import read_extract

    return read_extract(extract_csv or AIRPORTS_EXTRACT,
                        {"fiscal_year": int, "co2_t": float, "fuel_t": float,
                         "flight_count": float, "match_distance_km": float})


def extract_national_monthly(path=None):
    output = []
    for package in _load(path or NATIONAL):
        for row in package["response"]["subsectors"]["timeseries"]:
            output.append({
                "calendar_year": int(row["year"]),
                "month": "%04d-%02d" % (row["year"], row["month"]),
                "fiscal_year": int(row["year"]) if int(row["month"]) >= 7 else int(row["year"]) - 1,
                "scope": ("domestic" if row["subsector"] == "domestic-aviation"
                          else "international"),
                "co2_t": float(row["emissionsQuantity"]),
                "source": "Climate TRACE v7",
                "independence": "partial; possible shared surveillance/performance inputs",
                "license": "CC BY 4.0",
            })
    return output


def national_periods(rows):
    grouped = defaultdict(float)
    counts = defaultdict(set)
    for row in rows:
        for period, year in (("calendar", row["calendar_year"]),
                             ("fiscal", row["fiscal_year"])):
            grouped[(period, year, row["scope"])] += float(row["co2_t"])
            counts[(period, year)].add(row["month"])
    output = []
    for period, year in sorted({(p, y) for p, y, _s in grouped}):
        domestic = grouped[(period, year, "domestic")]
        international = grouped[(period, year, "international")]
        output.append({
            "period_type": period,
            "year": year,
            "months_available": len(counts[(period, year)]),
            "period_status": "complete" if len(counts[(period, year)]) == 12 else "partial",
            "domestic_co2_t": domestic,
            "international_co2_t": international,
            "combined_co2_t": domestic + international,
        })
    return output


def _distance_km(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _airport_reference():
    airports = list(_activity_rows(asset_path(ACTIVITY, "airports.csv"), comments=False))
    controls = {row["airport_icao"]: row for row in _activity_rows(asset_path(ACTIVITY, "airport_controls_2023_24.csv"), comments=False)}
    return [row for row in airports if row["airport_icao"] in controls and
            row["latitude_deg"] and row["longitude_deg"]], controls


def extract_airport_monthly(path=None, match_limit_km=25.0):
    reference, _controls = _airport_reference()
    output = []
    for source in _load(path or AIRPORTS):
        centroid = source["centroid"]
        candidates = sorted((
            (_distance_km(float(centroid["latitude"]), float(centroid["longitude"]),
                          float(row["latitude_deg"]), float(row["longitude_deg"])), row)
            for row in reference), key=lambda pair: pair[0])
        distance, airport = candidates[0]
        matched = distance <= match_limit_km
        for row in source.get("emissions", []):
            month = "%04d-%02d" % (row["year"], row["month"])
            output.append({
                "source_id": source["id"], "source_name": source["name"],
                "scope": "domestic" if source["subsector"] == "domestic-aviation" else "international",
                "month": month,
                "fiscal_year": int(row["year"]) if int(row["month"]) >= 7 else int(row["year"]) - 1,
                "co2_t": float(row["emissionsQuantity"]),
                "fuel_t": float(row.get("activity") or 0.0),
                "flight_count": float(row.get("capacity") or 0.0),
                "airport_icao": airport["airport_icao"] if matched else "UNMATCHED",
                "airport_iata": airport["airport_iata"] if matched else "",
                "match_distance_km": distance,
                "match_status": "nearest_within_25km" if matched else "unmatched",
            })
    return output


def airport_comparison(rows, fiscal_year=2023):
    _reference, controls = _airport_reference()
    grouped = defaultdict(lambda: defaultdict(float))
    for row in rows:
        if int(row["fiscal_year"]) == fiscal_year:
            for field in ("co2_t", "fuel_t", "flight_count"):
                grouped[row["airport_icao"]][(row["scope"], field)] += float(row[field])
    output = []
    for icao, values in sorted(grouped.items()):
        control = controls.get(icao, {})
        domestic_mv = float(control.get("domestic_commercial_movements") or 0)
        international_mv = float(control.get("international_commercial_movements") or 0)
        output.append({
            "fiscal_year": fiscal_year, "airport_icao": icao,
            "airport": control.get("airport", "unmatched Climate TRACE source"),
            "pcaa_domestic_movements": domestic_mv,
            "pcaa_international_movements": international_mv,
            "climatetrace_domestic_co2_t": values[("domestic", "co2_t")],
            "climatetrace_international_co2_t": values[("international", "co2_t")],
            "climatetrace_domestic_flights": values[("domestic", "flight_count")],
            "climatetrace_international_flights": values[("international", "flight_count")],
            "domestic_co2_per_pcaa_movement_t": (values[("domestic", "co2_t")] / domestic_mv
                                                   if domestic_mv else ""),
            "international_co2_per_pcaa_movement_t": (values[("international", "co2_t")] / international_mv
                                                        if international_mv else ""),
        })
    return output


def spatial_diagnostics(comparison_rows):
    output = []
    for scope in ("domestic", "international"):
        pairs = [(float(row["pcaa_%s_movements" % scope]),
                  float(row["climatetrace_%s_co2_t" % scope]))
                 for row in comparison_rows
                 if float(row["pcaa_%s_movements" % scope]) > 0 and
                 float(row["climatetrace_%s_co2_t" % scope]) > 0]
        coefficient, pvalue = spearmanr([x for x, _y in pairs], [y for _x, y in pairs])
        output.append({"fiscal_year": 2023, "scope": scope,
                       "airports_compared": len(pairs),
                       "spearman_rank_correlation": coefficient,
                       "spearman_p_value": pvalue,
                       "interpretation": "spatial corroboration; not independent observation"})
    return output
