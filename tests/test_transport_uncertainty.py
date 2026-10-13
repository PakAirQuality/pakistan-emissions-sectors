"""Tests for the transport sector's uncertainty module.

The module's claims worth pinning: the reference scenario IS the engine, the published
sensitivity rows cannot diverge from their run_transport twins, the declaration rows
are declarations (not samples), the private seed stays off every other stream, and the
grouped-vs-independent inequality runs in the DOCUMENTED direction - grouped below
independent, because demoting the fleet term removes distribution noise the
independent view counts as magnitude uncertainty.

Run:  python3 -m unittest discover tests
"""
import unittest

from pkinv.sectors.transport import cng_gap, engine, offroad, uncertainty
from pkinv.sectors.transport.data import TransportData


def _scen(rows, name):
    return next(r for r in rows if r["structural_scenario"] == name)


class TestApproach1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = TransportData()
        cls.a1 = uncertainty.approach1(cls.data)

    def test_total_is_the_engine_total(self):
        comps = engine.build_components(self.data)
        self.assertAlmostEqual(self.a1["co2e_Mt_AR5"],
                               sum(c["co2e_Mt_AR5"] for c in comps), places=9)

    def test_grouped_sits_below_independent_for_the_documented_reason(self):
        """The 25-percent fleet term is demoted because vehicle-km shares are
        normalised within each fuel - it redistributes a fixed total. Removing it
        pulls grouped BELOW independent, the opposite of the residential sector,
        and the docstring says so. If this inequality flips, either the demotion
        logic broke or the stamped uncertainties changed shape."""
        self.assertLess(self.a1["approach1_pct_grouped"],
                        self.a1["approach1_pct_independent"])

    def test_crossfuel_is_the_conservative_bound_of_the_grouped_family(self):
        """One publication, one annualisation: correlating the petroleum controls
        across fuels can only add variance to the within-fuel grouped figure."""
        self.assertGreater(self.a1["approach1_pct_grouped_crossfuel"],
                           self.a1["approach1_pct_grouped"])

    def test_the_band_is_a_plausible_fuel_anchored_number(self):
        """All three views must live in the neighbourhood the fuel controls imply:
        far below the fleet model's own softness, above the controls' floor."""
        for k in ("approach1_pct_grouped", "approach1_pct_grouped_crossfuel",
                  "approach1_pct_independent"):
            self.assertTrue(5.0 < self.a1[k] < 25.0, "%s = %.1f" % (k, self.a1[k]))

    def test_decomposition_shares_sum_to_one(self):
        decomp = uncertainty.variance_decomposition(self.data)
        self.assertAlmostEqual(sum(r["variance_share_pct"] for r in decomp),
                               100.0, places=1)
        self.assertEqual({r["stream"] for r in decomp}, {"Petrol", "Diesel", "CNG"})


class TestStructuralScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = TransportData()
        # Small n_iter: every deterministic assertion below is exact regardless, and
        # the reproducibility test re-runs at the same size.
        cls.rows = uncertainty.structural_scenarios(cls.data, n_iter=200)

    def test_reference_is_the_engine(self):
        comps = engine.build_components(self.data)
        self.assertAlmostEqual(_scen(self.rows, "reference")["deterministic"],
                               sum(c["co2e_Mt_AR5"] for c in comps), places=9)

    def test_cng_hhv_900_equals_the_published_sensitivity_row(self):
        """run_transport writes 'Sensitivity: CNG at 900 Btu/scf' from the same
        engine call; the two products must be one number or the paper can quote a
        scenario table and a totals table that disagree."""
        expected = sum(c["co2e_Mt_AR5"]
                       for c in engine.build_components(self.data, cng_hhv_btu=900))
        self.assertAlmostEqual(_scen(self.rows, "cng_hhv_900")["deterministic"],
                               expected, places=9)

    def test_offroad_n2o_scenario_reconciles_with_the_diagnostic(self):
        """Scaling the off-road N2O rows by 3.9/28.6 must move the sector by
        exactly the off-road N2O total times (1 - the ratio)."""
        comps = engine.build_components(self.data)
        off_n2o = sum(c["co2e_Mt_AR5"] for c in comps
                      if c["category"] == offroad.CATEGORY and c["gas"] == "N2O")
        scale = (self.data.efv("transport_fuel_n2o", "Gas/Diesel Oil")
                 / self.data.efv("offroad_machinery_n2o", "Gas/Diesel Oil"))
        ref = _scen(self.rows, "reference")["deterministic"]
        got = _scen(self.rows, "offroad_n2o_road_factor")["deterministic"]
        self.assertAlmostEqual(ref - got, off_n2o * (1.0 - scale), places=9)

    def test_cng_excluded_removes_exactly_the_cng_stream(self):
        comps = engine.build_components(self.data)
        cng_total = sum(c["co2e_Mt_AR5"] for c in comps
                        if c["subitem"].startswith("CNG"))
        ref = _scen(self.rows, "reference")["deterministic"]
        got = _scen(self.rows, "cng_excluded")["deterministic"]
        self.assertAlmostEqual(ref - got, cng_total, places=9)

    def test_fleet_energy_band_brackets_by_the_crosscheck_bounds(self):
        """The band prices the two-basis disagreement: metered gas implies 0.87
        MJ/km against a 1.2-6.0 plausibility band, so BOTH bounds sit above the
        reference - which is the FLEET-MODEL-HIGH verdict in scenario form."""
        ref = _scen(self.rows, "reference")["deterministic"]
        low = _scen(self.rows, "cng_fleet_energy_low")["deterministic"]
        high = _scen(self.rows, "cng_fleet_energy_high")["deterministic"]
        self.assertGreater(low, ref)
        self.assertGreater(high, low)
        summary = cng_gap.summary(self.data)
        self.assertEqual(summary["verdict"], "FLEET-MODEL-HIGH")

    def test_declaration_rows_are_declarations_not_samples(self):
        for name in ("class_split_declaration", "air_factor_provenance"):
            r = _scen(self.rows, name)
            self.assertEqual(r["P2.5"], "")
            self.assertEqual(r["P97.5"], "")
            self.assertEqual(r["interpretation"], uncertainty.INTERPRETATION)

    def test_class_split_declaration_shows_an_unchanged_total(self):
        """The whole point of the anchor: the class split cannot move the sector."""
        self.assertAlmostEqual(
            _scen(self.rows, "class_split_declaration")["deterministic"],
            _scen(self.rows, "reference")["deterministic"], places=9)

    def test_every_row_carries_the_interpretation(self):
        for r in self.rows:
            self.assertEqual(r["interpretation"], uncertainty.INTERPRETATION)

    def test_reproducible_under_the_private_seed(self):
        again = uncertainty.structural_scenarios(self.data, n_iter=200)
        for a, b in zip(self.rows, again):
            self.assertEqual(a, b)


class TestSeedDiscipline(unittest.TestCase):
    def test_the_private_seed_is_off_every_other_stream(self):
        """The national MC runs on 42; residential, railways and power keep private
        scenario seeds. A collision would make two 'independent' scenario tables
        draw the same stream."""
        from pkinv.core import montecarlo as mc_core
        others = {mc_core.SEED, 1404, 1435, 4242}
        self.assertNotIn(uncertainty.SCENARIO_SEED, others)


class TestInputsRegister(unittest.TestCase):
    def test_every_row_is_classed_and_sourced(self):
        rows = uncertainty.inputs_register(TransportData())
        self.assertGreaterEqual(len(rows), 15)
        for r in rows:
            self.assertIn(r["uncertainty_class"], ("parametric", "structural"))
            self.assertTrue(r["source"])

    def test_the_fleet_term_is_registered_as_distribution_only(self):
        rows = uncertainty.inputs_register(TransportData())
        fleet_row = next(r for r in rows
                         if r["variable"] == "Fleet composition and VKT")
        self.assertEqual(fleet_row["distribution"], "distribution-only")
        self.assertIn("DEMOTED", fleet_row["note"])


if __name__ == "__main__":
    unittest.main()
