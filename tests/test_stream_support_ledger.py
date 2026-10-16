"""The stream-to-support ledger: rectangular, joined completely, and closed.

The twenty-first review's deliverable, held to three properties the hand-join it
replaces could not assert: the panel is RECTANGULAR (every stream x every period, typed
absence instead of silent row deletion); the three-way join is COMPLETE (every weights
row lands here, and the mass column agrees with the atomic table per stream-year); and
the support arithmetic CLOSES (located + fallback shares bound each other, ADM1-retained
mass appears exactly for the not-placed streams).

Run:  python3 -m unittest discover tests -p "test_stream_support_ledger.py"
"""
import os
import unittest

from pkinv.core.io import read_rows
from _support import OUT
from _support import require_built  # noqa: E402

PATH = os.path.join(OUT, "pakemis_stream_support_ledger.csv")


def _rows(name):
    return read_rows(os.path.join(OUT, name))


class TestTheLedgerIsRectangularAndComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(PATH)

    def test_the_panel_is_rectangular_with_typed_absence(self):
        streams = {r["source_stream_id"] for r in self.rows}
        periods = {r["period_id"] for r in self.rows}
        self.assertEqual(len(self.rows), len(streams) * len(periods),
                         "the panel is not rectangular")
        from pkinv.assets import asset_path
        from pkinv.paths import DATA
        self.assertEqual(periods, {r["period_id"] for r in
                                   read_rows(asset_path(DATA, "periods.csv"))})
        self.assertEqual(len(streams), 202)   # rc52: + ammonia, steel, lubricating oil, grease
        for r in self.rows:
            self.assertIn(r["status"], ("present", "not_present"))
            if r["status"] == "not_present":
                self.assertEqual(r["co2e_Mt_AR5"], "",
                                 "%s %s: a not_present row carries mass"
                                 % (r["period_id"], r["source_stream_id"]))

    def test_the_mass_join_agrees_with_the_atomic_table(self):
        from collections import defaultdict
        atomic = defaultdict(float)
        for r in _rows("pakemis_atomic_annual.csv"):
            atomic[(r["period_id"], r["source_stream_id"])] += float(r["co2e_Mt_AR5"])
        for r in self.rows:
            if r["status"] != "present":
                continue
            key = (r["period_id"], r["source_stream_id"])
            self.assertAlmostEqual(float(r["co2e_Mt_AR5"]), atomic.get(key, 0.0),
                                   places=6, msg=str(key))

    def test_the_native_mass_closes_against_the_atom(self):
        # the defect this pins: the builder once read a column the atomic table does not
        # have ("emissions_Gg"), so every present row shipped 0.000000 while the co2e
        # column beside it was correct - a closure on ONE of two mass columns is no
        # closure at all. Per (period, stream), the ledger's Gg must equal the sum of the
        # atom's emission_native_mass, and must be non-zero wherever the atom's is.
        from collections import defaultdict
        atomic = defaultdict(float)
        for r in _rows("pakemis_atomic_annual.csv"):
            atomic[(r["period_id"], r["source_stream_id"])] += float(r["emission_native_mass"])
        nonzero = 0
        for r in self.rows:
            if r["status"] != "present":
                continue
            key = (r["period_id"], r["source_stream_id"])
            want = atomic.get(key, 0.0)
            self.assertAlmostEqual(float(r["emissions_Gg"]), want, places=5, msg=str(key))
            if want > 0:
                self.assertGreater(float(r["emissions_Gg"]), 0.0, str(key))
                nonzero += 1
        self.assertGreater(nonzero, 1700, "the native-mass column is dead again")

    def test_every_weights_row_lands_here(self):
        weights = {(r["period_id"], r["source_stream_id"])
                   for r in _rows("pakemis_spatial_weights_by_year.csv")}
        here = {(r["period_id"], r["source_stream_id"]) for r in self.rows}
        self.assertEqual(weights, here)

    def test_the_retained_mass_is_exactly_the_unplaced_streams(self):
        from collections import defaultdict
        source = defaultdict(float)
        for row in _rows("pakemis_spatial_unallocated_by_year.csv"):
            source[(row["period_id"], row["source_stream_id"])] += \
                float(row["co2e_Mt_AR5"])
        for row in self.rows:
            # A declared stream with genuine zero activity can still have no geometry.
            # Test its retained quantity, not whether the rounded quantity is positive.
            key = (row["period_id"], row["source_stream_id"])
            expected = source[key]
            if row["spatial_time_basis"] != "unallocated":
                self.assertEqual(expected, 0.0, str(key))
            self.assertAlmostEqual(float(row["adm1_retained_Mt"] or 0), expected,
                                   delta=5.1e-9, msg=str(key))

    def test_located_and_substituted_shares_are_shares(self):
        for r in self.rows:
            if r["status"] != "present":
                continue
            for col in ("located_share", "substituted_share"):
                if r[col]:
                    v = float(r[col])
                    self.assertGreaterEqual(v, -1e-9, (col, r["source_stream_id"]))
                    self.assertLessEqual(v, 1.0 + 1e-9, (col, r["source_stream_id"]))

    def test_the_monthly_support_distinguishes_raster_from_administrative_products(self):
        for r in self.rows:
            if r["status"] != "present":
                continue
            if r["period_id"] == "FY2023-24":
                self.assertEqual(r["monthly_support"], "gridded_monthly")
            else:
                self.assertEqual(r["monthly_support"],
                                 "monthly_administrative_allocation; "
                                 "no_published_ghg_monthly_raster")

    def test_the_advertised_monthly_products_cover_the_ledger_periods(self):
        require_built()
        from pkinv.core import configurations as conf
        from pkinv.report.air_monthly_grid import path_for as monthly_path_for
        from pkinv.report.grid_cube import period_keys
        from netCDF4 import Dataset
        periods = {r["period_id"] for r in self.rows}
        adm = _rows("pakemis_ghg_configuration_adm2_monthly.csv")
        for cfg in conf.ALL:
            self.assertEqual({r["period_id"] for r in adm
                              if r["configuration_id"] == cfg}, periods, cfg)
            # Separate AP cubes are available for the full core and all four cases.
            # This says nothing about whether each GHG stream has an AP estimate.
            with Dataset(monthly_path_for(cfg)) as cube:
                self.assertEqual(cube.configuration_id, cfg)
                self.assertEqual(set(str(p) for p in cube.variables["period_id"][:]),
                                 {m for p in periods for m in period_keys(p).months}, cfg)
