"""Data library for the power sector (IPCC 1A1).

Coal activity is station fuel consumed times documented rank-specific net calorific
values. Other fuels retain their declared energy controls. Physical fuel mass,
energy and generation remain separate quantities; rank NCV uncertainty is retained.

YEARS ARE FISCAL, July to June.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

YEAR = 2023          # FY2023-24, the latest year in SIR 2025 Table 3
#
# THE VINTAGE SPLIT IS GONE. This sector used to report FY2022-23 grid alongside
# FY2023-24 captive gas and sum them, because the 2024 edition's national fuel table
# stopped at FY2022-23 and nothing newer had been fetched. The 2025 edition carries
# FY2023-24, so grid and captive now describe the same twelve months.


def _read(path):
    return read_rows(path, comments=False)


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


class PowerData:
    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir, self.year = data_dir, year

        self.ef = {}
        for r in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(r["category"], r["item"])] = {
                "value": _num(r["value"]), "uncert_pct": _num(r["uncert_pct"]),
                "source": r["source"]}

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for r in _read(asset_path(data_dir, "power_params.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_uncert[r["param"]] = _num(r["uncert_pct"])
            self.param_source[r["param"]] = r["source"]

        # The lignite share of coal, per fiscal year, derived once from the plant fuel
        # ledger and held as data so the emissions path never imports the closure that
        # carries default NCVs (tests/test_plant_closure.py enforces the separation).
        self.coal_blend = {int(r["fiscal_start_year"]): r
                           for r in _read(asset_path(data_dir,
                                                       "power_coal_blend_by_year.csv"))}

        self.fuel = _read(asset_path(data_dir, "activity", "power", "fuel_consumed.csv"))
        for r in self.fuel:
            r["fiscal_year"] = int(r["fiscal_year"])
            r["toe"] = float(r["toe"])

        # WHICH COAL-ENERGY ACCOUNT THE ENGINE BOOKS. fuel_consumed.csv stays a faithful
        # transcription of NEPRA Table 3 with a source on every row, and C0 in the
        # configurations product still reads it directly - which is what lets the superseded
        # control ship beside the reference instead of disappearing. This table declares the
        # account, one row per year, and fuel_for() applies it to COAL ONLY.
        self.coal_booking = {}
        for r in read_rows(asset_path(data_dir, "activity", "power",
                                      "coal_energy_booking.csv"), comments=True):
            if r["fuel"] != "Coal":
                raise ValueError(
                    "coal_energy_booking.csv books %r: this table is the coal account and "
                    "nothing else, because every other fuel's Table 3 figure stands" % r["fuel"])
            self.coal_booking[int(r["fiscal_year"])] = {
                "toe": float(r["booked_toe"]),
                "lo": float(r["booked_lo_toe"]),
                "hi": float(r["booked_hi_toe"]),
                "basis": r["basis"],
                "superseded_toe": _num(r["superseded_toe"]),
                "evidence_grade": r["evidence_grade"]}
        self.coal_rank_account = {}
        for row in read_rows(asset_path(data_dir, "activity", "power", "coal_rank_account.csv"), comments=True):
            self.coal_rank_account.setdefault(int(row["fiscal_year"]), []).append(row)

        self.generation = _read(asset_path(data_dir, "activity", "power",
                                             "generation_by_fuel.csv"))
        for r in self.generation:
            r["fiscal_year"] = int(r["fiscal_year"])
            r["gwh_net"] = float(r["gwh_net"])

        # Captive self-generation (1A2). A separate series labelled by fiscal-year END
        # (captive_year=2024 is FY2023-24) where the grid series labels by START
        # (YEAR=2023 is FY2023-24) - the same reference year under opposite conventions,
        # which an earlier note here misread as two vintages.
        # Fuel quality as published RANGES, not point values - see the file's own notes and
        # sectors/power/air_pollutants.py for why AP-42 forces this.
        self.quality = {}
        for r in _read(asset_path(data_dir, "power_fuel_quality.csv")):
            self.quality[(r["fuel"], r["property"])] = (_num(r["lo"]), _num(r["hi"]))

        self.captive = _read(asset_path(data_dir, "activity", "power", "captive_gas.csv"))
        for r in self.captive:
            r["fiscal_year"] = int(r["fiscal_year"])
            r["total_mmcfd"] = float(r["total_mmcfd"])

    def efv(self, category, item):
        return self.ef[(category, item)]["value"]

    def coal_uncertainty_drivers(self, year=None, gas="CO2"):
        """Shared mass, rank-NCV and factor widths on the booked account.

        Commissioning endpoints remain conditional structural bounds; they are
        never converted to a 95% width. Rank NCV widths summarise IPCC ranges.
        """
        year = self.year if year is None else year
        rank_rows = self.coal_rank_account.get(year)
        if not rank_rows:
            raise KeyError("no rank uncertainty account for FY%d" % year)
        widths = {"activity:coal:power_station_mass": self.p("activity_uncert_coal")}
        for row in rank_rows:
            rank, share = row["fuel_rank"], float(row["energy_share"])
            widths["factor:ncv:" + rank] = share * float(row["ncv_uncert_pct_95"])
        if gas == "CO2":
            share = self.coal_energy_lignite_share(year)
            lig, bit = self.efv("power_combustion_co2", "Lignite"), self.efv("power_combustion_co2", "Other Bituminous Coal")
            blend = share * lig + (1 - share) * bit
            widths["factor:co2:Lignite"] = share * lig / blend * self.efu("power_combustion_co2", "Lignite")
            widths["factor:co2:Other Bituminous Coal"] = (1 - share) * bit / blend * self.efu("power_combustion_co2", "Other Bituminous Coal")
        else:
            widths["factor:%s:Other Bituminous Coal" % gas.lower()] = self.efu("power_combustion_" + gas.lower(), "Coal")
        return widths

    def efu(self, category, item):
        return self.ef[(category, item)]["uncert_pct"]

    def coal_energy_lignite_share(self, year=None):
        """Share of booked coal heat supplied by lignite, not electricity share."""
        year = self.year if year is None else year
        rows = self.coal_rank_account.get(year)
        if not rows:
            raise KeyError("no coal rank energy account for FY%d" % year)
        total = sum(float(row["energy_TJ"]) for row in rows)
        if total <= 0:
            raise ValueError("non-positive booked coal energy for FY%d" % year)
        return sum(float(row["energy_TJ"]) for row in rows
                   if row["fuel_rank"] == "Lignite") / total

    def p(self, name):
        return self.params[name]

    def pu(self, name):
        return self.param_uncert[name]

    def ps(self, name):
        return self.param_source[name]

    def coal_blend_share(self, year):
        """The lignite share of coal generation in one fiscal year.

        Raises rather than defaulting on an unknown year: a silent zero here would say
        "all imported coal", which is a claim about the fleet, not an absence of one.
        """
        try:
            return float(self.coal_blend[int(year)]["lignite_share"])
        except KeyError:
            raise KeyError(
                "no coal blend share for FY%d-%02d; data/power_coal_blend_by_year.csv "
                "covers %d-%d and a year outside it needs its own evidenced row"
                % (year, (year + 1) % 100,
                   min(self.coal_blend), max(self.coal_blend))) from None

    def fuel_for(self, year=None):
        """{fuel: TOE} for one fiscal year.

        RAISES on a year the fuel table does not cover. An empty dict used to zero grid
        combustion while captive generation - which takes no year at all - carried on
        regardless, so the sector returned 5.6 Mt instead of 63.6 and looked like a real
        answer. Grid and captive must fail together or not at all.
        """
        year = self.year if year is None else year
        out = {r["fuel"]: r["toe"] for r in self.fuel if r["fiscal_year"] == year}
        if not out:
            years = sorted({r["fiscal_year"] for r in self.fuel})
            raise KeyError(
                "no fuel consumption for FY%d-%02d: the table covers FY%d-%02d to "
                "FY%d-%02d (data/activity/power/fuel_consumed.csv)"
                % (year, (year + 1) % 100, min(years), (min(years) + 1) % 100,
                   max(years), (max(years) + 1) % 100))
        if "Coal" in out:
            # RAISES on a year the booking table does not cover, rather than falling back to
            # Table 3. A silent fallback would make the reference series depend on which years
            # someone had got round to booking, and the failure would look like data.
            if year not in self.coal_booking:
                raise KeyError(
                    "no coal booking for FY%d-%02d: data/activity/power/coal_energy_booking.csv "
                    "covers FY%d-%02d to FY%d-%02d, and the engine does not fall back to "
                    "Table 3 for a year it has not booked"
                    % (year, (year + 1) % 100,
                       min(self.coal_booking), (min(self.coal_booking) + 1) % 100,
                       max(self.coal_booking), (max(self.coal_booking) + 1) % 100))
            out["Coal"] = self.coal_booking[year]["toe"]
        return out

    def table3_coal_toe(self, year=None):
        """The coal TOE NEPRA Table 3 PRINTS, which is NOT what the engine books.

        THE ONE ACCESSOR, because three copies of this read appeared within an hour of the
        re-base and a fourth site kept reading fuel_for() by mistake. plant_ledger's coal-NCV
        diagnostic divides Table 3's energy by the ledger's coal mass and calls the result
        implied_NCV_TJ_per_Gg; after the re-base it was dividing the BOOKED energy - derived
        from that same mass - by the mass, so it reported a ratio of 1.0000006 and its own
        test, which asserts the discrepancy is large, caught it. A diagnostic whose name says
        Table 3 must read Table 3.
        """
        year = self.year if year is None else year
        for r in self.fuel:
            if r["fiscal_year"] == year and "oal" in r["fuel"] and "Table 3" in r["source"]:
                return r["toe"]
        raise KeyError("no Table 3 coal row for FY%d-%02d" % (year, (year + 1) % 100))

    def generation_for(self, year=None):
        year = self.year if year is None else year
        return [r for r in self.generation if r["fiscal_year"] == year]

    def fuel_quality(self, fuel, prop):
        """(lo, hi) for a fuel-quality property. Indexed, not .get(): a missing analysis must
        raise rather than silently default to a convenient number."""
        return self.quality[(fuel, prop)]

    def captive_year(self):
        return int(self.p("captive_year"))

    def captive_total_mmcfd(self, year=None):
        year = self.captive_year() if year is None else year
        for r in self.captive:
            if r["fiscal_year"] == year:
                return r["total_mmcfd"]
        raise KeyError("no captive gas figure for FY%s" % year)
