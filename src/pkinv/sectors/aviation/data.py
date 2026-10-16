"""Data library for the civil aviation sector.

Same contract as the other sector loaders: every number comes from a file under data/,
and no emission factor is hard-coded in a calculation module. Shares
emission_factors.csv, namespaced by the `aviation_*` categories.

YEARS ARE FISCAL, July to June, as published by the CAA. Year 2023 means Jul 2023 to
Jun 2024. Recorded here because it is nowhere in the source spreadsheet and it moves the
COVID trough: FY2019 already contains the March-June 2020 shutdown, so the low point is
FY2020.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

YEAR = 2023          # detailed reference FY2023-24; observed panel extends through FY2024-25


def _read(path):
    return read_rows(path, comments=False)


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


class AviationData:
    """Airport movement panel, fleet mix, emission factors and parameters."""

    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir = data_dir
        self.year = year

        self.ef = {}
        for r in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(r["category"], r["item"])] = {
                "value": _num(r["value"]),
                "uncert_pct": _num(r["uncert_pct"]),
                "source": r["source"],
            }

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for r in _read(asset_path(data_dir, "aviation_params.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_uncert[r["param"]] = _num(r["uncert_pct"])
            self.param_source[r["param"]] = r["source"]

        self.movements = _read(asset_path(data_dir, "activity", "aviation",
                                            "movements_airport.csv"))
        for r in self.movements:
            r["year"] = int(r["year"])
            for k in ("com_dom_mv", "com_intl_mv", "noncom_mv", "pax_dom", "pax_intl"):
                r[k] = float(r[k])

        self.fleet = _read(asset_path(data_dir, "aviation_fleet_mix.csv"))
        for r in self.fleet:
            r["year_from"], r["year_to"] = int(r["year_from"]), int(r["year_to"])
            r["share"] = float(r["share"])

        self.engine_map = {}
        for r in _read(asset_path(data_dir, "aviation_engine_map.csv")):
            for key in ("engine_count", "fuel_kg_per_lto", "nox_kg_per_lto",
                        "co_kg_per_lto", "hc_kg_per_lto"):
                r[key] = _num(r[key])
            r["imputed"] = r["imputed"].strip().lower() == "true"
            self.engine_map[r["aircraft"]] = r

        self.fuel_sales = _read(asset_path(data_dir, "activity", "aviation",
                                             "fuel_sales.csv"))
        for r in self.fuel_sales:
            r["fiscal_year"] = int(r["fiscal_year"])
            r["tonnes"] = float(r["tonnes"])

        self.aviation_benchmarks = _read(asset_path(data_dir, "activity", "aviation",
                                                      "benchmarks.csv"))
        for r in self.aviation_benchmarks:
            r["fiscal_year"] = int(r["fiscal_year"])
            r["co2_t"] = float(r["co2_t"])

        operator_path = asset_path(data_dir, "activity", "aviation", "operator_groups.csv")
        self.operator_groups = _read(operator_path)
        self.operator_by_icao = {r["icao_operator"]: r for r in self.operator_groups}
        aircraft_path = asset_path(data_dir, "activity", "aviation", "aircraft_aliases.csv")
        self.aircraft_aliases = _read(aircraft_path)
        self.aircraft_by_icao = {r["icao_type"]: r for r in self.aircraft_aliases}

    def inventory_aircraft(self, icao_type):
        row = self.aircraft_by_icao.get((icao_type or "").upper())
        return row["inventory_aircraft"] if row else icao_type

    def openap_aircraft(self, icao_type):
        row = self.aircraft_by_icao.get((icao_type or "").upper())
        return row["openap_type"] if row and row["openap_type"] else None

    # ---- accessors ----
    def efv(self, category, item):
        return self.ef[(category, item)]["value"]

    def efu(self, category, item):
        return self.ef[(category, item)]["uncert_pct"]

    def p(self, name):
        return self.params[name]

    def pu(self, name):
        return self.param_uncert[name]

    def ps(self, name):
        return self.param_source[name]

    def movements_for(self, year=None):
        year = self.year if year is None else year
        rows = [r for r in self.movements if r["year"] == year]
        if not rows:
            raise KeyError("No observed airport movements for FY%d-%02d; missing activity cannot become zero emissions" % (year, (year + 1) % 100))
        return rows

    def fuel_sales_for(self, year=None):
        year = self.year if year is None else year
        rows = [r for r in self.fuel_sales if r["fiscal_year"] == year]
        if not rows:
            raise KeyError("No aviation fuel sales for FY%d-%02d" % (year, (year + 1) % 100))
        return rows

    def benchmarks_for(self, year=None, source=None):
        year = self.year if year is None else year
        return [r for r in self.aviation_benchmarks
                if r["fiscal_year"] == year and (source is None or r["source"] == source)]

    def fleet_for(self, segment, year=None):
        """{aircraft: share} for a segment in a year. Shares must sum to 1."""
        year = self.year if year is None else year
        mix = {r["aircraft"]: r["share"] for r in self.fleet
               if r["segment"] == segment and r["year_from"] <= year <= r["year_to"]}
        if not mix:
            raise KeyError("no %s fleet mix covering FY%d" % (segment, year))
        total = sum(mix.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError("%s fleet shares for FY%d sum to %.6f, not 1.0"
                             % (segment, year, total))
        return mix
