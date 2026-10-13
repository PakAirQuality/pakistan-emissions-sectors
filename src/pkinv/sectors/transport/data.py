"""Data library for the road transport sector (IPCC 1A3b)."""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

YEAR = 2024          # FY2023-24, the common reference period
#
# WAS 2022, "the latest year with all four provinces reported" - and that was the wrong thing
# to optimise. The reference period is set by the MAGNITUDE control, which OCAC publishes for
# nine fiscal years; the provincial split is a SHAPE, and a shape can be borrowed from a
# neighbouring year without moving a single tonne. Pinning the sector to FY2021-22 to keep a
# twelve-month provincial panel left the national total carrying a transport figure from
# before the post-2022 demand contraction, two years adrift of eight other sectors, to protect
# an allocation that the total does not depend on.
#
# The shape now comes from downscale.SHAPE_PERIODS, which brackets this year with the two
# fiscal years OCAC did print twelve area pages for, and every row says so.

# The fleet panel (vkt.csv, fuel_split.csv) ends at 2023, one year short of the control. The
# composition therefore rides the nearest year that exists, declared here rather than
# discovered later: registrations move slowly and the split is normalised within each fuel,
# so a one-year-old fleet redistributes the control without changing it.
FLEET_YEAR = 2023

# The class split weights vehicle-kilometres by energy intensity; these are the three
# points of the declared MJ/km band that the split can be built on. "mid" is the
# reference; "lo" and "hi" are the published class-composition scenarios.
INTENSITY_BASES = ("lo", "mid", "hi")


def _read(p):
    return read_rows(p, comments=False)


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


class TransportData:
    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir, self.year = data_dir, year
        A = asset_path(data_dir, "activity", "transport")

        self.ef = {}
        for r in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(r["category"], r["item"])] = {
                "value": _num(r["value"]), "uncert_pct": _num(r["uncert_pct"]),
                "source": r["source"]}

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for r in _read(asset_path(data_dir, "transport_params.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_uncert[r["param"]] = _num(r["uncert_pct"])
            self.param_source[r["param"]] = r["source"]

        self.vehicles = _read(asset_path(A, "vehicles_district.csv"))
        for r in self.vehicles:
            r["year"] = int(r["year"])
            r["vehicles"] = float(r["vehicles"])

        self.vkt = {}
        for r in _read(asset_path(A, "vkt.csv")):
            self.vkt[(r["ei_class"], int(float(r["year"])))] = float(r["vkt_km_per_vehicle"])

        self.fuel_split = {}
        for r in _read(asset_path(A, "fuel_split.csv")):
            self.fuel_split[(r["ei_class"], int(float(r["year"])), r["fuel"])] = float(r["share"])

        self.gkm = {}
        for r in _read(asset_path(A, "emission_factors_gkm.csv")):
            self.gkm[(r["ei_class"], r["fuel"])] = {
                k: float(r[k]) for k in ("NOx", "CO", "NMVOC", "PM2.5", "PM10", "SO2", "NH3")}

        # CNG gas supply, MMCFD by fiscal year. A volume rather than a fleet quantity: this
        # sector's CNG emissions come from metered gas, not from the vehicle model.
        self.cng = {}
        for r in _read(asset_path(A, "cng_gas.csv")):
            self.cng[int(r["fiscal_year"])] = float(r["mmcfd"])

        # OCAC sectoral sales, tonnes, by (inventory_year, sector_row, product) - the
        # customer-class table the petrol and diesel controls are read from since the
        # August 2026 re-anchor, and the boundary the fuel ledger closes over.
        self.ocac = {}
        for r in _read(asset_path(A, "ocac_sectoral_annual.csv")):
            self.ocac[(int(r["inventory_year"]), r["sector_row"], r["product"])] = \
                float(r["tonnes"])

    def cng_mmcfd(self, year=None):
        """CNG gas supply for the year. Indexed, not .get(): a missing year must raise rather
        than silently drop the stream and shrink the sector without saying so."""
        return self.cng[self.year if year is None else year]

    def cng_years(self):
        return sorted(self.cng)

    def ocac_t(self, sector_row, product, year=None):
        """OCAC sectoral sales in tonnes. Indexed, not .get(): a missing cell must
        raise rather than silently zero a boundary row."""
        return self.ocac[(self.year if year is None else year, sector_row, product)]

    def ocac_years(self):
        return sorted({y for (y, _s, _p) in self.ocac})

    def efv(self, c, i):
        return self.ef[(c, i)]["value"]

    def efu(self, c, i):
        return self.ef[(c, i)]["uncert_pct"]

    def p(self, n):
        return self.params[n]

    def pu(self, n):
        return self.param_uncert[n]

    def ps(self, n):
        return self.param_source[n]

    def mjkm(self, ei_class, fuel, basis="mid"):
        """Energy intensity of one (class, fuel) cell, MJ per vehicle-kilometre.

        DECLARED ENGINEERING JUDGEMENT, not Pakistani measurement. Only the lo/hi
        bands are stored (transport_params.csv, mjkm_lo_*/mjkm_hi_*); the central
        value is DEFINED here as their midpoint rather than stored a second time.
        Two reasons: a stored central could drift from the band that generates the
        class_intensity_low/high scenarios, and defining it as the midpoint makes
        the reference case the midpoint of the pair that brackets it, by
        construction rather than by coincidence.

        These weights move COMPOSITION only. Each fuel's shares are normalised to
        one, so no choice of intensity can change a fuel control total or the
        sector magnitude - it can only change which classes the fuel is assigned
        to, and (through the off-road partition) which IPCC category carries it.

        Indexed rather than .get(): a (class, fuel) cell the fleet model produces
        but the band table does not cover must RAISE. Falling back to a silent zero
        would give that cell no weight and hand its share of the fuel to the other
        classes without saying so - exactly the kind of invisible reallocation this
        module exists to prevent.
        """
        lo_key = "mjkm_lo_%s_%s" % (ei_class, fuel)
        hi_key = "mjkm_hi_%s_%s" % (ei_class, fuel)
        if lo_key not in self.params or hi_key not in self.params:
            raise KeyError(
                "no MJ/km band for (%s, %s): %s / %s absent from "
                "data/transport_params.csv. The class split cannot be "
                "intensity-weighted for this cell and must not silently fall back "
                "to distance." % (ei_class, fuel, lo_key, hi_key))
        lo, hi = self.params[lo_key], self.params[hi_key]
        if basis not in INTENSITY_BASES:
            raise ValueError("intensity basis must be one of %r, got %r"
                             % (INTENSITY_BASES, basis))
        return {"lo": lo, "mid": (lo + hi) / 2.0, "hi": hi}[basis]

    def stock_series(self, province, district, ei_class):
        """{year: cumulative registered stock} for one district and class."""
        return {r["year"]: r["vehicles"] for r in self.vehicles
                if r["province"] == province and r["district"] == district
                and r["ei_class"] == ei_class}

    def cells(self, year=None):
        """Distinct (province, district, ei_class) reported in `year`."""
        year = self.year if year is None else year
        return sorted({(r["province"], r["district"], r["ei_class"])
                       for r in self.vehicles if r["year"] == year})

    # A registration year counts as usable only if it reports at least this share of the
    # best-covered year's district-class cells. The panel's final year is always partial
    # because provinces file at different times, and a partial year is indistinguishable
    # from a shrinking fleet unless something checks.
    FLEET_COVERAGE_FLOOR = 0.75

    def fleet_coverage(self):
        """{year: share of the best-covered year's district-class cell count}."""
        counts = {}
        for r in self.vehicles:
            counts[r["year"]] = counts.get(r["year"], 0) + 1
        best = max(counts.values())
        return {y: n / best for y, n in sorted(counts.items())}

    def fleet_year(self, at_or_below=None):
        """The most recent registration year complete enough to carry the class split.

        RAISES if no year qualifies. Returns the requested year when it qualifies, and
        otherwise the nearest earlier year that does - the borrowed-shape rule the
        provincial allocation follows, applied to composition.

        at_or_below defaults to the sector's own year. It exists because the trap this
        function guards against used to be re-enterable through the front door: the engine's
        `year` argument went straight into effective_vkt, so build_components(data, 2024)
        rode the partial 271-cell 2024 panel while build_components(data) rode the complete
        2023 one - two different class splits for the same twelve months, 1.2 Mt of diesel
        walking between 1A3b and 1A4c depending on how the caller spelled the reference
        year. Every requested year now passes through the same completeness rule.
        """
        cap = self.year if at_or_below is None else at_or_below
        coverage = self.fleet_coverage()
        qualified = [y for y, share in coverage.items()
                     if share >= self.FLEET_COVERAGE_FLOOR]
        usable = [y for y in qualified if y <= cap]
        if not usable and qualified:
            # BORROWED FORWARD, for the series years before the panel matured: no
            # registration year at or below the request clears the floor (the panel only
            # reaches 75 percent coverage in 2019), so the shape comes from the EARLIEST
            # complete year instead. Same declared move as borrowing 2023's shape for the
            # 2024 reference, in the other direction: registrations move slowly, each
            # fuel's shares are normalised to one, and no borrowed shape can move a control
            # total - only the class composition, which the series' held_constant column
            # declares for these years.
            return min(qualified)
        if not usable:
            raise KeyError(
                "no vehicle-registration year at any coverage reports at least %.0f%% of the "
                "panel's best-covered year (coverage: %s)"
                % (100 * self.FLEET_COVERAGE_FLOOR,
                   ", ".join("%d %.0f%%" % (y, 100 * s) for y, s in coverage.items())))
        return max(usable)

    def vkt_for(self, ei_class, year):
        """Punjab's VKT series runs 2003-2023; clamp outside it."""
        yrs = [y for (c, y) in self.vkt if c == ei_class]
        y = min(max(year, min(yrs)), max(yrs))
        return self.vkt[(ei_class, y)]

    def split_for(self, ei_class, year):
        yrs = [y for (c, y, f) in self.fuel_split if c == ei_class]
        y = min(max(year, min(yrs)), max(yrs))
        return {f: s for (c, yy, f), s in self.fuel_split.items()
                if c == ei_class and yy == y}
