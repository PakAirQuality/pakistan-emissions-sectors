"""Data library for railway transport (IPCC 1A3c)."""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

YEAR = 2024          # FY2023-24, the latest Pakistan Railways Year Book


def _read(p):
    return read_rows(p, comments=False)


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


class RailwaysData:
    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir, self.year = data_dir, year

        self.ef = {}
        for r in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(r["category"], r["item"])] = {
                "value": _num(r["value"]), "uncert_pct": _num(r["uncert_pct"]),
                "source": r["source"]}

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for r in _read(asset_path(data_dir, "railways_params.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_uncert[r["param"]] = _num(r["uncert_pct"])
            self.param_source[r["param"]] = r["source"]

        self.fuel = {}
        for r in _read(asset_path(data_dir, "activity", "railways", "fuel_consumption.csv")):
            self.fuel[(int(r["fiscal_year"]), r["fuel"])] = {
                "quantity": float(r["quantity"]), "unit": r["unit"],
                "published_unit_label": r["published_unit_label"]}

    def efv(self, c, i):
        return self.ef[(c, i)]["value"]

    def efu(self, c, i):
        return self.ef[(c, i)]["uncert_pct"]

    def efs(self, c, i):
        return self.ef[(c, i)]["source"]

    def p(self, n):
        return self.params[n]

    def pu(self, n):
        return self.param_uncert[n]

    def ps(self, n):
        return self.param_source[n]

    def years(self):
        """Fiscal years with a diesel figure. FY2014-FY2024 with no gaps.

        It used to have two. FY2018 and FY2019 were recorded as unavailable because their
        own editions are page-image scans - which was true and beside the point: every
        edition's fuel table carries a historical run, and the 2020-21 edition has a text
        layer. Looking one edition later was always enough."""
        return sorted({y for (y, f) in self.fuel if f == "Gas/Diesel Oil"})

    def quantity(self, fuel, year=None):
        return self.fuel[(self.year if year is None else year, fuel)]["quantity"]

    def unit(self, fuel, year=None):
        return self.fuel[(self.year if year is None else year, fuel)]["unit"]
