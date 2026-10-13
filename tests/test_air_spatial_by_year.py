"""The nine-year air spatial products close, inherit, and say what they are.

The acceptance identity, asserted for EVERY (pollutant, period, configuration) cell of
the cross and not a sample:

    covered panel == ADM1 == grid + unallocated_below_adm1
                 == ADM2 + outside_frame + unallocated_below_adm1

and the inheritance property that makes the family honest: an air anchor's provincial
shares are ITS GREENHOUSE-GAS STREAM'S shares for the same period, bit-for-bit from the
same dispatch - the air lane may never invent geography of its own.
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import unittest

import numpy as np

from pkinv.paths import DATA, OUTPUTS

PANEL = os.path.join(OUTPUTS, "pakemis_air_annual_fy2015_16_fy2023_24.csv")
ADM1 = os.path.join(OUTPUTS, "pakemis_air_adm1_by_year.csv")
ADM2 = os.path.join(OUTPUTS, "pakemis_air_adm2_by_year.csv")
UNALLOC = os.path.join(OUTPUTS, "pakemis_air_unallocated_by_year.csv")
GHG_ADM1 = os.path.join(OUTPUTS, "pakemis_adm1_by_year.csv")
REF_NC = os.path.join(OUTPUTS, "pakemis_air_grid_0p05_annual_fy2015_16_fy2023_24.nc")
LEDGER_NC = os.path.join(
    OUTPUTS, "pakemis_air_grid_0p05_annual_ledger_fy2015_16_fy2023_24.nc")
GHG_NC = os.path.join(OUTPUTS, "pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc")

POLLUTANTS = ("BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2")
VAR_OF = {"BC": "bc_emissions", "CO": "co_emissions", "NH3": "nh3_emissions",
          "NMVOC": "nmvoc_emissions", "NOx": "nox_emissions",
          "PM2.5": "pm25_emissions", "SO2": "so2_emissions"}
CONFIGS = ("REF_2023_24", "L_HERD1624")
RTOL_CSV = 1e-6      # float64 CSV legs
RTOL_GRID = 2e-4     # the cells are stored float32; a 90,780-cell sum keeps ~4 digits


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


def _sum_by(rows, keys, value="emissions_Gg", where=None):
    out = collections.defaultdict(float)
    for r in rows:
        if where and any(r[k] != v for k, v in where.items()):
            continue
        out[tuple(r[k] for k in keys)] += float(r[value])
    return dict(out)


class TestTheConservationIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from netCDF4 import Dataset
        cls.panel = _sum_by(_rows(PANEL),
                            ("period_id", "configuration_id", "pollutant"))
        cls.adm1 = _sum_by(_rows(ADM1),
                           ("period_id", "configuration_id", "pollutant"))
        cls.adm2 = _sum_by(_rows(ADM2),
                           ("period_id", "configuration_id", "pollutant"))
        unalloc = _rows(UNALLOC)
        cls.below = _sum_by(unalloc, ("period_id", "configuration_id", "pollutant"),
                            where={"level": "below_adm1"})
        # rc60: a THIRD level. `below_adm1` is mass placed at ADM1 and no finer;
        # `below_national` is mass that has no defensible province either, and it enters the
        # identity one rung higher - before ADM1 rather than after it. The admitted oil and
        # diesel power SO2 is the case: it is a reviewed SUBSET of the furnace-oil fleet and
        # cannot ride that fleet's district OR provincial vector, which put it 1.3-2.2x high in
        # Lahore and 7 Gg into a Quetta with no furnace-oil station. The register knows every
        # plant's district; publishing it needs the admitted classes to carry their own spatial
        # anchor, and until they do the mass is national-grain and typed as such.
        cls.national = _sum_by(unalloc, ("period_id", "configuration_id", "pollutant"),
                               where={"level": "below_national"})
        cls.outside = _sum_by(unalloc, ("period_id", "configuration_id", "pollutant"),
                              where={"level": "outside_frame"})
        cls.grid = {}
        for cfg, path in (("REF_2023_24", REF_NC), ("L_HERD1624", LEDGER_NC)):
            with Dataset(path) as ds:
                pids = [str(v) for v in ds.variables["period_id"][:]]
                for pol in POLLUTANTS:
                    data = ds.variables[VAR_OF[pol]][:]
                    filled = np.ma.filled(data, 0.0)
                    filled[filled < 0] = 0.0        # FILL cells drop out of the sum
                    for t, pid in enumerate(pids):
                        cls.grid[(pid, cfg, pol)] = float(filled[t].sum())
        cls.cells = sorted(cls.panel)

    def test_the_cross_is_complete(self):
        """9 periods x 2 configurations x 7 pollutants, in the panel and every leg."""
        self.assertEqual(len(self.cells), 9 * 2 * 7)
        self.assertEqual(sorted(self.adm1), self.cells)
        self.assertEqual(sorted(self.grid), self.cells)

    def test_panel_equals_adm1_plus_what_has_no_province(self):
        for key in self.cells:
            self.assertAlmostEqual(
                self.panel[key], self.adm1[key] + self.national.get(key, 0.0),
                delta=RTOL_CSV * max(abs(self.panel[key]), 1e-9),
                msg="panel != ADM1 + below_national at %r" % (key,))

    def test_panel_equals_grid_plus_unallocated(self):
        for key in self.cells:
            lhs = self.panel[key]
            rhs = (self.grid[key] + self.below.get(key, 0.0)
                   + self.national.get(key, 0.0))
            self.assertAlmostEqual(
                lhs, rhs, delta=RTOL_GRID * max(abs(lhs), 1e-9),
                msg="panel != grid + unallocated at %r (%.9g vs %.9g)"
                    % (key, lhs, rhs))

    def test_panel_equals_adm2_plus_outside_plus_unallocated(self):
        for key in self.cells:
            lhs = self.panel[key]
            rhs = (self.adm2.get(key, 0.0) + self.outside.get(key, 0.0)
                   + self.below.get(key, 0.0) + self.national.get(key, 0.0))
            self.assertAlmostEqual(
                lhs, rhs, delta=RTOL_CSV * max(abs(lhs), 1e-9),
                msg="panel != ADM2 + outside + unallocated at %r" % (key,))

    def test_nothing_is_published_at_national_grain_any_more(self):
        """THE LEVEL THIS TEST WAS WRITTEN FOR IS GONE, and that is the result.

        rc60 typed the admitted power SO2 `below_national` - published nationally, placed
        nowhere - because its mass could not honestly ride its anchor's vector and had none of
        its own. The test that stood here asserted that level was populated, and that only the
        power classes populated it. rc61 gave those classes a frame
        (pkinv.report.power_admission_vectors), so the level is empty, and the assertion
        inverts: nothing may sit at national grain, and if something ever does again it must
        arrive with a test that says why rather than inheriting this one's permission.

        The mass did not vanish. It is at ADM2, and `test_the_admitted_power_so2_is_placed_where
        _the_register_says` below holds it to the register's own districts.
        """
        national = [r for r in _rows(UNALLOC) if r["level"] == "below_national"]
        self.assertEqual(national, [],
                         "something is published at national grain again: %s"
                         % sorted({(r["sector_id"], r["pollutant"]) for r in national}))

    def test_the_admitted_power_so2_is_placed_where_the_register_says(self):
        """The placement, checked against its own source rather than against itself.

        Two things could go wrong and neither would show in a total: the frame could conserve
        mass while putting it in the wrong districts, or it could quietly fall back to the
        anchor stream's vector. Both are caught by comparing the published ADM2 rows with the
        admission register district by district - and by naming Quetta, which carried 7 Gg of
        power SO2 under the inherited vector and has no furnace-oil station at all.
        """
        from pkinv.core.io import read_rows as _read
        register = collections.defaultdict(float)
        for r in _read(asset_path(DATA, "activity", "power", "power_so2_admission.csv")):
            if r["disposition"] == "provisional_estimate":
                register[(r["period_id"], r["adm2_id"])] += float(r["so2_Gg"])
        published = collections.defaultdict(float)
        for r in _rows(ADM2):
            if (r["sector_id"] == "power" and r["pollutant"] == "SO2"
                    and r["configuration_id"] == "REF_2023_24"):
                published[(r["period_id"], r["adm2_ids"])] += float(r["emissions_Gg"] or 0.0)

        self.assertAlmostEqual(sum(published.values()), sum(register.values()), places=4)
        for (period, adm2_id), mass in register.items():
            hit = sum(v for (p, ids), v in published.items()
                      if p == period and adm2_id in ids.split(";"))
            self.assertAlmostEqual(hit, mass, places=4,
                                   msg="%s %s: published %.6f against the register's %.6f"
                                       % (period, adm2_id, hit, mass))
        quetta = sum(v for (_p, ids), v in published.items() if "quetta" in ids)
        self.assertEqual(quetta, 0.0,
                         "power SO2 is in Quetta again, which has no furnace-oil station - the "
                         "frame has fallen back to the anchor stream's vector")

    def test_every_below_adm1_row_is_typed_for_every_period_and_configuration(self):
        """Two anchors are placed at ADM1 and nowhere finer, each with its own typed
        reason: aviation cruise (no native geometry) and, since rc59, the brick coal
        outside the surveyed kiln frame (industry: placed on the brick stream's
        provincial shares, never spread over kilns that were not surveyed). Both must
        exist for all nine periods under both configurations, so a reader of any year
        can close the arithmetic without borrowing another year's row."""
        rows = [r for r in _rows(UNALLOC) if r["level"] == "below_adm1"]
        for r in rows:
            self.assertIn(r["sector_id"], ("aviation", "industry"), r)
            if r["sector_id"] == "aviation":
                self.assertIn("cruise", r["reason"])
            else:
                self.assertIn("outside the surveyed kiln frame", r["reason"])
                self.assertIn("brick-kiln-coal", r["source_stream_id"])
        want = {("FY20%02d-%02d" % (y, y + 1), cfg)
                for y in range(15, 24) for cfg in CONFIGS}
        for sector in ("aviation", "industry"):
            got = {(r["period_id"], r["configuration_id"]) for r in rows if r["sector_id"] == sector}
            self.assertEqual(got, want, sector)


class TestTheIdentityHoldsPerSector(unittest.TestCase):
    """The same identity, one axis finer: a SECTOR's provinces, and its districts, sum to that
    sector's national figure - for every (period, configuration, sector, pollutant).

    Every test above closes per pollutant, and all of them passed for the whole life of this
    family while a sector's provinces did NOT sum to its national figure: the atom loader
    labelled each anchor stream with the last sector it read, so general-industry gas
    combustion was filed under IPPU (which borrows that stream as its geography) and 32 kt
    of fugitive NMVOC under transport, in every period. The mass was all there and in the
    right place; it carried the wrong name, and a closure that sums over sectors cannot see
    a name. Written to FAIL on that tree."""

    KEYS = ("period_id", "configuration_id", "sector_id", "pollutant")
    # The panel prints six decimals per row and a sector cell sums a handful of rows, so a small
    # sector cannot be held to a relative tolerance alone: aviation's 0.030 Gg of PM2.5 differs
    # from its provinces by one unit in the sixth place. The defect this class exists for moved
    # 0.3 to 32 Gg between sectors - five to seven orders above this floor.
    ATOL = 5e-6

    def close(self, lhs, rhs, what, key):
        self.assertAlmostEqual(lhs, rhs, delta=max(RTOL_CSV * abs(lhs), self.ATOL),
                               msg="%s for %r (%.9g vs %.9g)" % (what, key, lhs, rhs))

    @classmethod
    def setUpClass(cls):
        cls.panel = _sum_by(_rows(PANEL), cls.KEYS)
        cls.adm1 = _sum_by(_rows(ADM1), cls.KEYS)
        cls.adm2 = _sum_by(_rows(ADM2), cls.KEYS)
        unalloc = _rows(UNALLOC)
        cls.below = _sum_by(unalloc, cls.KEYS, where={"level": "below_adm1"})
        cls.national = _sum_by(unalloc, cls.KEYS, where={"level": "below_national"})
        cls.outside = _sum_by(unalloc, cls.KEYS, where={"level": "outside_frame"})

    def test_no_sector_appears_or_disappears_between_the_grains(self):
        nonzero = lambda table: {k for k, v in table.items() if abs(v) > self.ATOL}
        self.assertEqual(nonzero(self.panel), nonzero(self.adm1) | nonzero(self.national))

    def test_a_sectors_provinces_sum_to_its_national_figure(self):
        for key, lhs in sorted(self.panel.items()):
            rhs = self.adm1.get(key, 0.0) + self.national.get(key, 0.0)
            self.close(lhs, rhs, "panel != ADM1", key)

    def test_a_sectors_districts_sum_to_its_national_figure(self):
        for key, lhs in sorted(self.panel.items()):
            rhs = (self.adm2.get(key, 0.0) + self.outside.get(key, 0.0)
                   + self.below.get(key, 0.0) + self.national.get(key, 0.0))
            self.close(lhs, rhs, "panel != ADM2 + outside + unallocated", key)

    def test_two_sectors_may_share_one_anchor_stream_and_keep_their_names(self):
        """The case that broke it, held by name: the general-industry gas stream carries
        industry's combustion AND the IPPU class that borrows it, as two rows."""
        by_stream = collections.defaultdict(set)
        for r in _rows(ADM1):
            by_stream[r["source_stream_id"]].add(r["sector_id"])
        shared = {s: sectors for s, sectors in by_stream.items() if len(sectors) > 1}
        self.assertTrue(shared, "no anchor is shared by two sectors: the case this guards has gone")
        gas = "industry|industrial-fuel-combustion-(1a2)|general-industry-gas-co2|co2"
        self.assertEqual(shared.get(gas), {"industry", "ippu"})


class TestTheAllocationIsInherited(unittest.TestCase):
    """The air lane may never INVENT geography. Through rc60 that was the same sentence as
    "every anchor's provincial shares are its greenhouse-gas stream's shares", and the test
    below was that sentence. rc61 separates the two, because they had quietly stopped meaning
    the same thing.

    Inheriting the anchor's provinces is right while the air mass IS the stream's mass. The
    admitted power SO2 is not: it is a reviewed SUBSET of its anchor's fleet - the 54-89 percent
    of CPPA furnace oil the admission register could price, station by station - so the whole
    fleet's province vector is not this mass's vector, and applying it was measured to put
    Lahore at 1.3-2.2 times the register's own figure and 7 Gg into a Quetta that has no
    furnace-oil station.

    So the rule is now: a class either inherits, or rides a frame that declares its own
    provinces AND publishes them. The exception list is closed and asserted below - an anchor
    diverging without a declared frame is still the defect this test was written to catch.
    """

    #: The only anchors allowed to depart, and the frame that entitles each. Read from the
    #: register rather than hard-coded, so adding a fifth class cannot smuggle in a divergence.
    @staticmethod
    def declaring_anchors():
        from pkinv.report.air_spatial_by_year import frame_of_class
        from pkinv.core.io import read_rows as _read
        frames = frame_of_class()
        declaring = {c for c, f in frames.items() if f.startswith("power_admission:")}
        anchors = set()
        for r in _read(asset_path(DATA, "air_source_classes.csv")):
            if r["source_class_id"] in declaring:
                anchors.add(r["ghg_anchor_subitem"])
        return declaring, anchors

    def test_the_only_classes_that_declare_their_own_provinces_are_the_admitted_power_ones(self):
        declaring, anchors = self.declaring_anchors()
        self.assertEqual(declaring, {"power_rfo_boiler", "power_rfo_engine",
                                     "power_rfo_turbine", "power_hsd_turbine"})
        self.assertEqual(anchors, {"Furnace Oil CO2", "Diesel Oil CO2"})

    def test_adm1_shares_match_the_ghg_streams(self):
        ghg = collections.defaultdict(dict)
        for r in _rows(GHG_ADM1):
            ghg[(r["period_id"], r["source_stream_id"])][r["province"]] = \
                float(r["emissions_Gg"])
        air = collections.defaultdict(dict)
        for r in _rows(ADM1):
            if r["configuration_id"] != "REF_2023_24":
                continue
            key = (r["period_id"], r["source_stream_id"], r["pollutant"])
            air[key][r["province"]] = float(r["emissions_Gg"])
        # the declaring anchors carry SO2 from the admitted power classes and nothing else;
        # every other pollutant on those same streams still inherits, so the exception is
        # per (anchor, pollutant) rather than per anchor
        _declaring, _anchors = self.declaring_anchors()
        excepted = {sid for sid in {k[1] for k in air}
                    if "furnace-oil" in sid or "diesel-oil" in sid}
        checked = departed = 0
        for (pid, sid, pol), vec in air.items():
            if sid in excepted and pol == "SO2":
                departed += 1
                continue
            ref = ghg.get((pid, sid))
            if ref is None or sum(ref.values()) <= 0.0:
                continue
            total_air, total_ghg = sum(vec.values()), sum(ref.values())
            if total_air == 0.0:
                continue                     # a zero mass has no shares to inherit
            for province, mass in vec.items():
                self.assertAlmostEqual(
                    mass / total_air, ref.get(province, 0.0) / total_ghg,
                    delta=1e-9,
                    msg="province share diverges for %s %s %s" % (pid, sid, province))
            checked += 1
        self.assertGreater(checked, 400, "the inheritance check must actually bite")
        self.assertGreater(departed, 0,
                           "no anchor departed; the admitted power SO2 is not being placed on "
                           "its own frame and this test has stopped testing the amendment")

    def test_the_declared_provinces_are_the_registers_own(self):
        """And the departure is not a licence - it must reproduce the admission register
        exactly, per class and per period, or the frame has invented geography after all."""
        from pkinv.core.io import read_rows as _read
        from pkinv.report import power_admission_vectors as pav
        register = collections.defaultdict(lambda: collections.defaultdict(float))
        for r in _read(asset_path(DATA, "activity", "power", "power_so2_admission.csv")):
            if r["disposition"] != "provisional_estimate":
                continue
            class_id = pav.CLASS_OF[(r["fuel"], r["equipment_class"])][0]
            register[(class_id, r["period_id"])][r["province"]] += float(r["so2_Gg"])
        from pkinv.core.gis.grid import build_grid
        frames = pav.build(build_grid())
        self.assertEqual(len(frames), 29)
        for key, frame in frames.items():
            declared = register[key]
            total = sum(declared.values())
            for province, mass in declared.items():
                self.assertAlmostEqual(
                    frame.province_marginal.get(province, 0.0), mass / total, delta=1e-9,
                    msg="%s %s %s" % (key[0], key[1], province))

    def test_no_period_borrows_another_period_s_magnitude(self):
        """Adjacent periods must differ in every pollutant layer: a copied year would
        be an L1 distance of ~0. The threshold is loose - it exists to catch a
        wholesale copy, not to legislate year-on-year variation."""
        from netCDF4 import Dataset
        with Dataset(REF_NC) as ds:
            for pol in POLLUTANTS:
                data = np.ma.filled(ds.variables[VAR_OF[pol]][:], 0.0)
                data[data < 0] = 0.0
                for t in range(data.shape[0] - 1):
                    l1 = float(np.abs(data[t + 1] - data[t]).sum())
                    total = float(data[t].sum())
                    if total <= 0.0:
                        continue
                    self.assertGreater(
                        l1, 1e-6 * total,
                        "%s: periods %d and %d are byte-copies" % (pol, t, t + 1))


class TestTheLedgerConfiguration(unittest.TestCase):
    """rc67 (2026-10-13): the second file was the survey-anchored configuration
    S_HIES1925 and it was the smaller side. The survey series is the reference now; the
    second file is the ledger series L_HERD1624 (every year's diverted dung burned in
    households), and it is the larger side in every period."""

    def test_l_differs_from_ref_by_exactly_the_panel_delta(self):
        """sum(L grid) - sum(REF grid) == L panel - REF panel per (period, pollutant):
        the ledger file re-places the ledger MASSES on the same weights, nothing else."""
        panel = _sum_by(_rows(PANEL), ("period_id", "configuration_id", "pollutant"))
        from netCDF4 import Dataset
        with Dataset(REF_NC) as ref, Dataset(LEDGER_NC) as led:
            pids = [str(v) for v in ref.variables["period_id"][:]]
            self.assertEqual(pids, [str(v) for v in led.variables["period_id"][:]])
            for pol in POLLUTANTS:
                a = np.ma.filled(ref.variables[VAR_OF[pol]][:], 0.0)
                b = np.ma.filled(led.variables[VAR_OF[pol]][:], 0.0)
                a[a < 0] = 0.0
                b[b < 0] = 0.0
                for t, pid in enumerate(pids):
                    want = (panel[(pid, "L_HERD1624", pol)]
                            - panel[(pid, "REF_2023_24", pol)])
                    got = float(b[t].sum() - a[t].sum())
                    self.assertAlmostEqual(
                        got, want,
                        delta=RTOL_GRID * max(abs(panel[(pid, "REF_2023_24", pol)]),
                                              1e-9),
                        msg="L-REF grid delta != panel delta for %s %s" % (pid, pol))

    def test_the_ledger_file_is_the_larger_in_every_period(self):
        """The direction of the swap, on the cells. Dung smoke is mostly particulate, so
        the ledger file's PM2.5 exceeds the reference file's in every one of the nine
        periods, by the panel's own difference (349.19 Gg in FY2023-24). A file still
        holding the pre-rc67 survey masses under the new name would close every identity
        above and fail here."""
        panel = _sum_by(_rows(PANEL), ("period_id", "configuration_id", "pollutant"))
        from netCDF4 import Dataset
        with Dataset(REF_NC) as ref, Dataset(LEDGER_NC) as led:
            pids = [str(v) for v in ref.variables["period_id"][:]]
            a = np.ma.filled(ref.variables[VAR_OF["PM2.5"]][:], 0.0)
            b = np.ma.filled(led.variables[VAR_OF["PM2.5"]][:], 0.0)
            a[a < 0] = 0.0
            b[b < 0] = 0.0
            self.assertEqual(len(pids), 9)
            for t, pid in enumerate(pids):
                self.assertGreater(float(b[t].sum()), float(a[t].sum()), pid)
                self.assertGreater(panel[(pid, "L_HERD1624", "PM2.5")],
                                   panel[(pid, "REF_2023_24", "PM2.5")], pid)
        self.assertAlmostEqual(panel[("FY2023-24", "L_HERD1624", "PM2.5")]
                               - panel[("FY2023-24", "REF_2023_24", "PM2.5")],
                               349.190, delta=0.01)

    def test_the_files_declare_their_configuration(self):
        from netCDF4 import Dataset
        with Dataset(REF_NC) as ds:
            self.assertEqual(ds.configuration_id, "REF_2023_24")
        with Dataset(LEDGER_NC) as ds:
            self.assertEqual(ds.configuration_id, "L_HERD1624")
            self.assertIn("dung", ds.configurations)


class TestTheFilesSayWhatTheyAre(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from netCDF4 import Dataset
        cls.ds = Dataset(REF_NC)
        cls.ghg = Dataset(GHG_NC)

    @classmethod
    def tearDownClass(cls):
        cls.ds.close()
        cls.ghg.close()

    def test_no_view_dimension_and_the_attribute_says_why(self):
        self.assertNotIn("spatial_view", self.ds.dimensions)
        self.assertIn("does not claim the others", self.ds.spatial_view)

    def test_the_frame_is_the_greenhouse_gas_cube_s_frame(self):
        """Same lattice, same time axis: the two families may never drift."""
        for var in ("time", "lat", "lon"):
            self.assertTrue(
                np.array_equal(self.ds.variables[var][:], self.ghg.variables[var][:]),
                "%s axis differs from the greenhouse-gas cube" % var)
        self.assertEqual([str(v) for v in self.ds.variables["period_id"][:]],
                         [str(v) for v in self.ghg.variables["period_id"][:]])
        self.assertEqual(self.ds.grid_spec_id, self.ghg.grid_spec_id)
        self.assertIn("crs_wkt", self.ds.variables["crs"].ncattrs())

    def test_the_scope_is_declared_on_the_file(self):
        self.assertIn("covered_sources_only", self.ds.coverage_scope)
        self.assertIn("not a national air total", self.ds.coverage_scope)

    def test_fill_marks_outside_pakistan_and_nothing_else(self):
        from pkinv.core.gis.grid import build_grid
        grid = build_grid()
        outside = grid.province_id < 0
        raw = self.ds.variables["nox_emissions"]
        raw.set_auto_mask(False)
        data = raw[0, :, :]
        self.assertTrue((data[outside] == -9999.0).all())
        self.assertTrue((data[~outside] >= 0.0).all())

    def test_the_shipped_files_stay_small(self):
        for path in (REF_NC, LEDGER_NC):
            size = os.path.getsize(path)
            self.assertLess(size, 16e6,
                            "%s outgrew its 16 MB budget (%.1f MB)"
                            % (os.path.basename(path), size / 1e6))


if __name__ == "__main__":
    unittest.main()
