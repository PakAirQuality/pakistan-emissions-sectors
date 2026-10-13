"""Data library for residential fuel combustion (IPCC 1A4b)."""
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows
from pkinv.assets import asset_path

YEAR = 2024          # FY2023-24: the latest full fiscal year OGRA tabulates by sector


def _read(p):
    return read_rows(p, comments=False)


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


class ResidentialData:
    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir, self.year = data_dir, year
        A = asset_path(data_dir, "activity", "residential")

        self.ef = {}
        for r in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(r["category"], r["item"])] = {
                "value": _num(r["value"]), "uncert_pct": _num(r["uncert_pct"]),
                "source": r["source"]}

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for r in _read(asset_path(data_dir, "residential_params.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_uncert[r["param"]] = _num(r["uncert_pct"])
            self.param_source[r["param"]] = r["source"]

        self.fuel = {}
        for r in _read(asset_path(A, "fuel_supply.csv")):
            self.fuel[(int(r["fiscal_year"]), r["fuel"])] = {
                "quantity": float(r["quantity"]), "unit": r["unit"], "source": r["source"]}

        self.woodfuel = {}
        for r in _read(asset_path(A, "woodfuel.csv")):
            self.woodfuel[int(r["year"])] = float(r["woodfuel_m3"])

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

    def quantity(self, fuel, year=None):
        return self.fuel[(self.year if year is None else year, fuel)]["quantity"]

    def woodfuel_m3(self, year=None):
        """FAOSTAT runs a year ahead of and behind the fiscal series; clamp to its range."""
        year = self.year if year is None else year
        yrs = sorted(self.woodfuel)
        return self.woodfuel[min(max(year, yrs[0]), yrs[-1])]
