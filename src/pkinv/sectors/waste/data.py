"""Data library for the open-waste-burning sector.

Same contract as the agriculture loader: every number the engine uses comes from a file
under data/, and no emission factor is hard-coded in a calculation module. Shares
emission_factors.csv with the other sectors, namespaced by the `waste_burning` category.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

YEAR = 2024          # FY2023-24, the common reference period
#
# WAS 2023 - "last year of the census-interpolated population panel" - which made the sector
# report a calendar year while eight others reported July to June. The panel now carries a
# 2024 row PROJECTED one year past the 7th Census anchor at its own intercensal growth rate,
# for the fiscal year's midpoint of 1 January 2024 (scripts/project_waste_population.py).
#
# That is an extrapolation where every other year of the panel is an interpolation, and the
# sector's population-driven rows say so by carrying evidence class E3 rather than E2: the
# quantity is derived from a published census plus a growth assumption rather than read from
# a census. Six months of alignment is worth one year of extrapolation on a stock that moves
# 2.6 percent a year; the reverse trade - leaving the offset undeclared - is what this round
# exists to stop.


def _read(path):
    return read_rows(path, comments=False)


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


class WasteData:
    """Population panel, emission factors and waste parameters for one run."""

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

        self.params, self.param_source = {}, {}
        self.param_uncert, self.param_bounds = {}, {}
        for r in _read(asset_path(data_dir, "waste_params.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_source[r["param"]] = r["source"]
            self.param_uncert[r["param"]] = _num(r["uncert_pct"])
            # lower/upper carry the row's OWN published range (never invented); a
            # bounded parameter can be drawn asymmetrically instead of forcing its
            # stated range into a symmetric percentage - the rc11 wastewater repair
            lo, hi = _num(r.get("lower")), _num(r.get("upper"))
            if lo is not None and hi is not None:
                self.param_bounds[r["param"]] = (lo, hi)

        # District population panel, 2000-2023. Kept in full so the sector can drive a
        # time series without re-reading, and so province shares are derived from the
        # same rows the national total is built from.
        # Sanitation pathway shares (WHO/UNICEF JMP) and protein supply (FAOSTAT Food
        # Balance Sheets) drive domestic wastewater; both were the blockers that kept 4D
        # marked NE until they were fetched.
        self.sanitation = {}
        for r in _read(asset_path(data_dir, "activity", "wastewater",
                                    "sanitation_shares.csv")):
            self.sanitation[(int(r["year"]), r["setting"])] = {
                "open": float(r["open_defecation_pct"]) / 100.0,
                "latrine": float(r["latrines_and_other_pct"]) / 100.0,
                "septic": float(r["septic_tanks_pct"]) / 100.0,
                "sewer": float(r["sewer_connection_pct"]) / 100.0,
                "unimproved": float(r["unimproved_pct"]) / 100.0}

        self.protein = {}
        for r in _read(asset_path(data_dir, "activity", "wastewater", "protein.csv")):
            self.protein[int(r["year"])] = float(r["protein_g_per_capita_day"])

        self.population = _read(asset_path(data_dir, "activity", "waste",
                                             "population_district.csv"))
        for r in self.population:
            r["year"] = int(r["year"])
            for k in ("pop_total", "pop_rural", "pop_urban"):
                r[k] = float(r[k])

        # HIES 2024-25 household disposal routes (scripts/ingest_hies_waste.py) -
        # survey EVIDENCE, not an input to the central estimate. The central partition
        # stays on the What a Waste uncollected fractions; the survey shares feed the
        # hies_route_shares structural scenario and the validation comparison only.
        self.hies_routes = {}
        for r in _read(asset_path(data_dir, "activity", "waste",
                                    "hies_disposal_routes.csv")):
            self.hies_routes[(r["scope"], r["region"], r["route"])] = {
                "share": float(r["share_of_region"]),
                "households_weighted": float(r["households_weighted"]),
                "label": r["route_label"],
            }

    def hies_share(self, region, route, scope="national"):
        return self.hies_routes[(scope, region, str(route))]["share"]

    # ---- accessors, mirroring the agriculture library ----
    def efv(self, category, item):
        return self.ef[(category, item)]["value"]

    def efu(self, category, item):
        return self.ef[(category, item)]["uncert_pct"]

    def efs(self, category, item):
        return self.ef[(category, item)]["source"]

    def p(self, name):
        return self.params[name]

    def pu(self, name):
        return self.param_uncert[name]

    def ps(self, name):
        return self.param_source[name]

    def population_for(self, year=None):
        """District population rows for one year.

        RAISES on a year the panel does not cover, rather than returning []. An empty list
        used to propagate silently: burning and disposal both collapse to nearly zero and
        the sector returned 8.9 Mt instead of ~37, with no exception and no warning. A
        plausible wrong number is the worst failure mode this inventory has, and a
        multi-year loop over sectors would have hit it on the first year past the panel.
        """
        year = self.year if year is None else year
        # Population is fixed within a parameter ensemble. Index its rows once,
        # preserving their order and references; uncertain fate parameters are
        # still evaluated afresh in every draw. Replacing/extending the panel
        # invalidates the index.
        token = (id(self.population), len(self.population))
        if getattr(self, "_population_index_token", None) != token:
            index = {}
            for row in self.population:
                index.setdefault(row["year"], []).append(row)
            self._population_index = index
            self._population_index_token = token
        rows = self._population_index.get(year, [])
        if not rows:
            years = sorted({r["year"] for r in self.population})
            raise KeyError(
                "no district population for %s: the panel covers %d-%d. Extend "
                "data/activity/waste/population_district.csv before running this year."
                % (year, min(years), max(years)))
        return rows
