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

# The audit's expected routing. Masses moved with A1-A3; the SHARES and the assignment did
# not, which is what this pins.
EXPECTED_SHARE = {
    "glw_livestock": 80.8,
    "spam_rice": 7.9,
    "cropland": 7.5,
    "manure_applied": 3.6,
    "firms_fire": 0.3,
}


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
        self.assertTrue(surfaces <= set(EXPECTED_SHARE),
                        "unexpected surfaces: %s" % (surfaces - set(EXPECTED_SHARE)))

    def test_the_routing_reproduces_the_audit(self):
        agg = collections.defaultdict(float)
        for r in self.rows:
            agg[r["allocation_surface"]] += float(r["co2e_Mt_AR5"] or 0)
        total = sum(agg.values())
        for surface, expected in EXPECTED_SHARE.items():
            self.assertIn(surface, agg, surface)
            self.assertAlmostEqual(100.0 * agg[surface] / total, expected, delta=0.1,
                                   msg=surface)

    def test_the_surfaces_sum_to_the_published_sector_total(self):
        total = sum(float(r["co2e_Mt_AR5"] or 0) for r in self.rows)
        self.assertAlmostEqual(total, 223.454471, places=4)

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
        """The exception had been recorded for releases as a string in a numeric column and
        a line in a fallback register. Neither said how much. rc41: the mass is PRICED per
        stream - the fraction of each affected stream that fell back, at its own gas and
        methane origin - so 8.000949 (the whole Sindh module mass of every gas in native Gg,
        no GWP) became 0.522157 Mt CO2e; and the agriculture events that this table filed
        under Larkana/Sindh are the "Other" province panel's, named as such now.

        rc42 (S-2): the livestock census reaches the grid through the canonical crosswalk,
        and its "Larkana District" unit - a census unit with no polygon - is a named row of
        the district panel that the cube turns into this same event, so Sindh's shape_missing
        rows now carry an agriculture module too (enteric and manure, 1.249831 Mt); the
        residential and waste mass is unchanged at 0.522157.

        rc45: 0.522157 becomes 0.522273. Larkana is a census unit with no polygon, so what
        falls back is its SHARE of Sindh's residential and waste mass, and that share is a
        district population - which now reads the fiscal midpoint, the mean of the two
        calendar years a fiscal year spans, rather than the year it opens in. A district's
        population share moves a little when the vintage moves, and this is that. The
        agriculture figure does not move: enteric fermentation and manure management are
        split by the livestock census, not by people.

        rc67 (2026-10-13): 0.522273 becomes 0.482831, and the pin is split by module so the
        next move names its owner. Residential fell from 0.212406 to 0.172964 because
        household dung follows the survey in every year (10.93 Mt of cake where the
        reference burned 58.74), and Larkana's share of a smaller Sindh dung stream is a
        smaller fallback. Waste moved from 0.309867 to 0.306129 with wastewater nitrous
        oxide on the 2019 Refinement (rc67)."""
        larkana = [r for r in self.rows
                   if r["exception_kind"] == "shape_missing" and r["province"] == "Sindh"]
        self.assertEqual({r["module"] for r in larkana}, {"agriculture", "residential", "waste"})
        self.assertAlmostEqual(sum(float(r["affected_mass_Mt_AR5"]) for r in larkana
                                   if r["module"] == "residential"), 0.172964, places=5)
        self.assertAlmostEqual(sum(float(r["affected_mass_Mt_AR5"]) for r in larkana
                                   if r["module"] == "waste"), 0.306129, places=5)
        # rc47 Wave 1: 1.249831 -> 2.079202. The old figure was enteric+manure only,
        # because the CROP categories' panel was the SPAM-proxy product - and a proxy
        # summed within a polygon that does not exist is zero, so Larkana's crop
        # activity simply wasn't there to fall back. The PBS panel records it
        # (~0.83 Mt of rice/soils/urea share), and it now falls back the declared
        # way instead of not existing.
        self.assertAlmostEqual(sum(float(r["affected_mass_Mt_AR5"]) for r in larkana
                                   if r["module"] == "agriculture"), 2.079202, places=5)
        other = [r for r in self.rows
                 if r["exception_kind"] == "shape_missing" and r["province"] == "Other"]
        self.assertEqual({r["module"] for r in other}, {"agriculture", "residential"})
        # rc47 Wave 1: 42 -> 26. The sixteen departed events are the crop categories'
        # ICT mass: under the proxy product it sat in the "Other residual" row (no
        # polygon, guaranteed fallback); the PBS panel names ict_islamabad, which HAS
        # a polygon, so that mass now lands on it instead of falling back.
        self.assertEqual(sum(int(r["affected_stream_count"]) for r in other), 26)

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
