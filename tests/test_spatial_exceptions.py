"""rc39 A9: every agriculture stream names the raster it is actually spread on.

The spatial decomposition published `allocation_surface = population` for ALL THIRTY-FOUR
agriculture streams. That is true of none of them: livestock rides GLW, rice MapSPAM, burning
the FIRMS record, fertiliser and residue cropland, applied manure its own surface.

The cause was structural rather than a typo. The decomposition resolved a surface per
GEOMETRY, through data/stream_grid_proxy.csv, and that register deliberately omits
agriculture - its banner says so, to avoid duplicating a mapping that already exists in
core/gis/proxy_map. So the join found nothing for this sector and fell through to whatever
another module had declared for the same shared `diffuse:adm2_pbs2023` geometry. One geometry
carries thirty-four streams on five different rasters, so a per-geometry answer cannot be
right for more than one of them.

The sector now publishes its own stream -> raster dispatch and the decomposition asks for it,
keyed on component_id. An earlier version keyed on category NAME and silently half-worked -
four categories resolved, 29.2 Mt left on the wrong surface - because the ledger says
"Agricultural soils" where the engine says "Managed soils".
"""
import collections
import csv
import os
import unittest

from _support import OUTPUTS, read_rows

# The admitted reference-period source families; their masses come from the current
# source account, so a legitimate census or activity revision does not require a new
# hard-coded national percentage in this routing test.
EXPECTED_SURFACES = {"glw_livestock", "spam_rice", "cropland", "manure_applied",
                     "firms_fire"}


def _agriculture():
    return [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_spatial_decomposition.csv"))
            if r["module"] == "agriculture"]


class TestEveryStreamNamesItsRealSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _agriculture()

    def test_the_sweep_found_the_sector(self):
        self.assertEqual(len(self.rows), 34)

    def test_no_stream_claims_population(self):
        """The specific defect, pinned by name: population is not a surface any agriculture
        stream is spread on."""
        wrong = sorted({r["sub_category"] for r in self.rows
                        if r["allocation_surface"] == "population"})
        self.assertFalse(wrong, "streams still claiming population: %s" % wrong)

    def test_every_stream_names_one_of_the_five_rasters(self):
        surfaces = {r["allocation_surface"] for r in self.rows}
        self.assertTrue(surfaces <= EXPECTED_SURFACES,
                        "unexpected surfaces: %s" % (surfaces - EXPECTED_SURFACES))

    def test_each_surface_mass_matches_the_independent_source_stream_account(self):
        from pkinv.sectors.agriculture import engine
        dispatch = engine.grid_surface_by_stream()
        expected = collections.defaultdict(float)
        for row in read_rows(os.path.join(OUTPUTS, "pakemis_source_streams.csv")):
            if row["module"] == "agriculture":
                surface = dispatch[row["source_stream_id"]]
                expected[surface] += float(row["emissions_ar5"])
        actual = collections.defaultdict(float)
        for row in self.rows:
            actual[row["allocation_surface"]] += float(row["co2e_Mt_AR5"] or 0)
        self.assertEqual(set(actual), EXPECTED_SURFACES)
        self.assertEqual(set(actual), set(expected))
        for surface, value in expected.items():
            self.assertAlmostEqual(actual[surface], value, places=6, msg=surface)

    def test_the_surfaces_sum_to_the_published_sector_total(self):
        total = sum(float(r["co2e_Mt_AR5"] or 0) for r in self.rows)
        source = sum(float(r["emissions_ar5"]) for r in read_rows(
            os.path.join(OUTPUTS, "pakemis_source_streams.csv"))
            if r["module"] == "agriculture")
        self.assertAlmostEqual(total, source, places=6)

    def test_the_dispatch_is_the_one_the_grid_allocates_with(self):
        """Not a second copy: the decomposition and the gridded product must ask the same
        two functions, or they will drift into disagreeing about where mass went."""
        from pkinv.sectors.agriculture import engine
        by_stream = engine.grid_surface_by_stream()
        self.assertTrue(by_stream)
        # The decomposition publishes (sub_category, gas), not the id; the LEDGER it reads
        # carries both, so the join goes through there - which is also the path the
        # decomposition itself takes.
        ledger = {(r["sub_category"], r["gas"]): r["source_stream_id"]
                  for r in read_rows(os.path.join(OUTPUTS, "pakemis_source_streams.csv"))
                  if r["module"] == "agriculture"}
        checked = 0
        for r in self.rows:
            stream_id = ledger.get((r["sub_category"], r["gas"]))
            expected = by_stream.get(stream_id) if stream_id else None
            if expected:
                checked += 1
                self.assertEqual(r["allocation_surface"], expected, r["sub_category"])
        self.assertGreater(checked, 25, "the join matched almost nothing")


class TestTheExceptionsCarryTheirMass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(os.path.join(OUTPUTS, "pakemis_spatial_exceptions.csv"))

    def test_the_kinds_are_present(self):
        """rc41: two kinds became four - the province built-up fallback of the located-object
        sets (the largest exception in the inventory, absent from this table until now)
        and the absent-raster class (no event this release)."""
        kinds = {r["exception_kind"] for r in self.rows}
        self.assertEqual(kinds, {"shape_missing", "proxy_empty", "province_points_absent"})

    def test_larkana_is_quantified_per_stream(self):
        """Price actual missing-shape events, rather than pinning obsolete sector totals.

        The source fallback ledger records each stream's affected share and its own
        gas/GWP conversion. The exceptions export must aggregate those fractions, not
        substitute the whole province or a previous release's fixed megatonnes.
        """
        events = read_rows(os.path.join(OUTPUTS, "pakemis_grid_fallbacks.csv"))
        for province, modules in (("Sindh", {"agriculture", "residential", "waste"}),
                                  ("Other", {"agriculture", "residential"})):
            actual = [r for r in self.rows if r["exception_kind"] == "shape_missing"
                      and r["province"] == province]
            self.assertEqual({r["module"] for r in actual}, modules)
            expected = collections.defaultdict(float)
            stream_ids = collections.defaultdict(set)
            for row in events:
                if row["scope"] == "district" and row["province"] == province:
                    expected[row["module"]] += float(row["affected_Mt_AR5"])
                    stream_ids[row["module"]].add(row["source_stream_id"])
                    self.assertGreater(float(row["weight_share"]), 0.0)
                    self.assertLess(float(row["weight_share"]), 1.0)
            for row in actual:
                module = row["module"]
                self.assertAlmostEqual(float(row["affected_mass_Mt_AR5"]),
                                       expected[module], delta=5.1e-7, msg=module)
                self.assertEqual(int(row["affected_stream_count"]),
                                 len(stream_ids[module]), module)

    def test_the_seven_rice_fallbacks_are_quantified(self):
        rice = [r for r in self.rows
                if r["exception_kind"] == "proxy_empty" and r["module"] == "agriculture"]
        self.assertEqual(len(rice), 7)
        self.assertEqual({r["used_surface"] for r in rice}, {"uniform"})
        # rc41: 0.271190 was the whole rice mass of those shapes; the stream's own fraction
        # that rode the uniform fallback was 0.019347 Mt. rc47 Wave 1: 0.029107 - the
        # reference-year rice split now comes from the PBS panel rather than the SPAM
        # proxy, and the panel puts more rice share on exactly the shapes whose SPAM
        # raster is empty (which is the divergence table's point, measured).
        self.assertAlmostEqual(sum(float(r["affected_mass_Mt_AR5"]) for r in rice),
                               0.029107, places=5)

    def test_the_sindh_coal_fallback_is_gone(self):
        """34.4 Mt of the Sindh coal grid stream rode built-up through rc41 because the
        dispatch read one coordinate table; rc42 (the twentieth review's S-1) reads the
        coal fleet's GEM/Climate TRACE points and the Sindh row is gone. What remains of
        the province-points-absent kind is small and named."""
        sindh = [r for r in self.rows if r["exception_kind"] == "province_points_absent"
                 and r["province"] == "Sindh" and r["module"] == "power"
                 and "coal" in r["affected_streams"].lower()]
        self.assertEqual(sindh, [], [r["affected_mass_Mt_AR5"] for r in sindh])
        # The blanket "and what remains is under 5 Mt" that used to sit here was a magnitude
        # bound standing in for a structural claim, and rc44 breached it honestly: pricing the
        # grid fleet's unlocated fuel took this kind from 4.3 to 14.81 Mt without a single
        # tonne becoming less well described. A bound like that can only ever be relaxed, so
        # it is replaced by the reconciliation below, which has teeth in both directions.

    def test_the_absent_points_mass_reconciles_with_the_decomposition(self):
        """THE CROSS-FILE INVARIANT (rc44). Mass that rides a substitute because a province
        has no located object is counted twice, independently: here as an exception row, and
        in pakemis_spatial_decomposition.csv as unresolved mass. The two are built by
        different code from different intermediates and must agree per module - if the ledger
        under-reports, mass is being substituted without an exception row, which is precisely
        the silence this register exists to prevent."""
        from _support import rows as _rows
        declared = {}
        for r in self.rows:
            if r["exception_kind"] == "province_points_absent":
                declared[r["module"]] = declared.get(r["module"], 0.0) \
                    + float(r["affected_mass_Mt_AR5"])
        unresolved = {}
        for r in _rows("pakemis_spatial_decomposition.csv"):
            mt = float(r["unresolved_Mt_AR5"] or 0.0)
            if mt:
                unresolved[r["module"]] = unresolved.get(r["module"], 0.0) + mt
        for module in ("power", "ippu"):
            self.assertAlmostEqual(declared[module], unresolved[module], places=2, msg=module)
        # The gap this block used to pin CLOSED at rc46 Wave 5: the LNG terminals'
        # 0.129 Mt was unresolved because the pair was a typed refusal (coordinates not
        # held), and Wave 0 acquired the two GEM-exact coordinates that Wave 5 wired as
        # facilities:lng_terminals. Asserted in the new direction so a regression - the
        # refusal quietly returning - is as visible as the gap used to be.
        self.assertNotIn("fugitives", declared)
        self.assertNotIn("fugitives", unresolved)

    def test_every_row_says_whether_it_can_be_resolved(self):
        for r in self.rows:
            self.assertIn(r["resolution_status"], ("open", "permanent"), r["unit_or_shape"])
            self.assertTrue(r["resolvable_by"], r["unit_or_shape"])

    def test_the_mass_grain_is_declared(self):
        """rc41: the mass is the stream's own, priced in the register; the row says so."""
        for r in self.rows:
            self.assertTrue(r["mass_grain"].startswith("stream:"), r["mass_grain"])


class TestTheNestingGapIsClosed(unittest.TestCase):
    """rc39 published the gap (1.836 Mt); rc40 G2 closed it. The check stays published as
    the evidence, and this asserts the evidence says zero."""

    def test_every_province_nests_exactly(self):
        rows = read_rows(os.path.join(OUTPUTS, "pakemis_adm2_nesting_check.csv"))
        total = next(r for r in rows if r["province"] == "TOTAL")
        self.assertLess(float(total["abs_difference_Mt_AR5"]), 1e-5,
                        "the ADM2 physical view no longer nests into the allocation")
        for r in rows:
            if r["province"] != "TOTAL":
                # 1e-5 is floating-point accumulation over ~9,000 cell-months (Punjab
                # lands at 4e-6); the pre-fix gap was 0.91 Mt, five orders above this.
                self.assertLess(abs(float(r["difference_Mt_AR5"])), 1e-5, r["province"])

    def test_no_cell_was_orphaned_by_the_nested_partition(self):
        """A boundary-file change that leaves a cell with no claimant in its own province
        would silently fall back to the cross-province split; this makes it loud."""
        from pkinv.core.gis import cube as cube_core
        self.assertTrue(all(v == 0 for v in cube_core.NESTED_ORPHANS.values()),
                        cube_core.NESTED_ORPHANS)

    def test_every_province_is_covered(self):
        rows = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_adm2_nesting_check.csv"))
                if r["province"] != "TOTAL"]
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertTrue(r["difference_Mt_AR5"], r["province"])


if __name__ == "__main__":
    unittest.main()
