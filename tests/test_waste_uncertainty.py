"""Tests for the waste sector's uncertainty module (August 2026 round).

Three claims are load-bearing and pinned here. The mixture representation of the sewer
MCF is EXACT - its endpoints must reproduce the two published readings to the digit,
or the mixture is quietly a different model. The grouped Approach 1 must decompose the
way its note says it does - generation coupling widening, partition anticorrelation
narrowing. And the inputs register must cover every parameter in waste_params.csv
bidirectionally, so a parameter added to the data file without a register row (or a
register row for a deleted parameter) fails instead of shipping silently.

Run:  python3 -m unittest discover tests
"""
import csv
import math
import os
import unittest

from pkinv.assets import asset_path
from pkinv.paths import OUTPUTS
from pkinv.sectors.waste import engine, uncertainty, wastewater
from pkinv.sectors.waste.data import WasteData
from pkinv.core.io import read_rows


def _totals_cell(category):
    with open(os.path.join(OUTPUTS, "waste_totals_%d.csv" % WasteData().year),
              newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["category"] == category:
                return float(r["co2e_Mt_AR5"])
    raise KeyError(category)


def _scenarios():
    return {r["structural_scenario"]: r for r in read_rows(os.path.join(OUTPUTS, "waste_uncertainty_scenarios_%d.csv" % WasteData().year), comments=False)}


class TestMixture(unittest.TestCase):
    def setUp(self):
        self.data = WasteData()

    def test_endpoints_reproduce_the_published_readings_exactly(self):
        self.assertEqual(uncertainty.sewer_mcf_mixture(self.data, 1.0, 0.0, 0.0),
                         self.data.p("ww_mcf_sewer"))
        self.assertEqual(uncertainty.sewer_mcf_mixture(self.data, 0.0, 1.0, 0.0),
                         self.data.p("ww_mcf_sewer_river"))

    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            uncertainty.sewer_mcf_mixture(self.data, 0.5, 0.4, 0.0)

    def test_the_mixture_is_monotone_between_the_endpoints(self):
        t = self.data.p("ww_treated_share")
        mid = uncertainty.sewer_mcf_mixture(self.data, (1 - t) / 2, (1 - t) / 2, t)
        self.assertLess(self.data.p("ww_mcf_sewer_river"), mid)
        self.assertLess(mid, self.data.p("ww_mcf_sewer"))


class TestGroupedApproach1(unittest.TestCase):
    def setUp(self):
        self.rows = uncertainty.approach1(WasteData())
        self.sector = self.rows[-1]

    def test_sector_total_matches_the_shipped_file(self):
        self.assertAlmostEqual(self.sector["co2e_Mt_AR5"], _totals_cell("TOTAL"),
                               places=4)

    def test_independent_matches_the_published_approach1(self):
        """The independent figure is what the pooled national treatment sees. The
        rc11 wastewater repair MOVED it - from the 47.8 published while the effluent
        factor carried a symmetric 100% against its 500-fold range, to about 57%
        under the log-variance-matched declaration - and this pin moves with it.
        The quadrature is itself only a symmetric shadow at this width; the
        sector's published interval is the parameter-rerun MC's percentiles."""
        # 56.99 through rc66; the effluent factor's declared width fell from 401 to 267
        # per cent with the 2019 Refinement's range (rc67)
        self.assertAlmostEqual(self.sector["approach1_pct_independent"], 51.08,
                               delta=0.1)

    def test_generation_coupling_outweighs_partition_anticorrelation(self):
        """The net direction of the two couplings, pinned so the S1 prose cannot drift
        from the computation: shared generation widens the band by more than the signed
        partition term narrows it, so grouped > independent - but only slightly."""
        grouped = self.sector["approach1_pct_grouped"]
        indep = self.sector["approach1_pct_independent"]
        self.assertGreater(grouped, indep)
        self.assertLess(grouped - indep, 2.0)

    def test_the_partition_term_is_smaller_grouped_than_independent(self):
        """The anticorrelation itself: the signed partition contribution must be smaller
        in absolute terms than the same 30% treated as independent quadrature. Recomputed
        here from the components, not read from a note."""
        data = WasteData()
        comps = engine.build_components(data)
        part = [c for c in comps if c["category"] in uncertainty.PARTITIONED]
        u = data.pu("uncollected_urban") / 100.0
        from pkinv.sectors.waste import open_burning, swds
        gen = swds.waste_generated(data)
        u_eff = (gen - swds.waste_disposed(data)) / gen
        elas = {open_burning.CATEGORY: 1.0, swds.CATEGORY: -u_eff / (1.0 - u_eff)}
        signed = abs(sum(u * c["co2e_Mt_AR5"] * elas[c["category"]] for c in part))
        quad = math.sqrt(sum((u * c["co2e_Mt_AR5"]) ** 2 for c in part))
        self.assertLess(signed, quad)


class TestStructuralScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shipped = _scenarios()

    def test_reference_equals_the_engine_total(self):
        self.assertAlmostEqual(float(self.shipped["reference"]["deterministic"]),
                               _totals_cell("TOTAL"), places=3)

    def test_stagnant_endpoint_equals_reference(self):
        """w_stagnant=1 must be IDENTICAL to the central case - the proof that the
        mixture representation changes nothing at the endpoint."""
        self.assertEqual(self.shipped["sewer_all_stagnant"]["deterministic"],
                         self.shipped["reference"]["deterministic"])

    def test_flowing_endpoint_equals_the_published_sensitivity(self):
        """The scenario must reproduce the river-MCF sector total the runner has always
        published: TOTAL - central 4D1 + the river 4D1 category total."""
        river_sector = (_totals_cell("TOTAL") - _totals_cell("Domestic wastewater")
                        + _totals_cell("Sensitivity: wastewater on the river-discharge "
                                       "MCF (category total)"))
        self.assertAlmostEqual(float(self.shipped["sewer_all_flowing"]["deterministic"]),
                               river_sector, places=3)

    def test_bod_and_spinup_scenarios_agree_with_the_runner(self):
        india_sector = (_totals_cell("TOTAL") - _totals_cell("Domestic wastewater")
                        + _totals_cell("Sensitivity: wastewater on India's BOD rate "
                                       "(category total)"))
        self.assertAlmostEqual(float(self.shipped["bod_india"]["deterministic"]),
                               india_sector, places=3)
        spinup_sector = (_totals_cell("TOTAL") - _totals_cell("Solid waste disposal")
                         + _totals_cell("Sensitivity: disposal without spin-up"))
        self.assertAlmostEqual(float(self.shipped["no_spinup"]["deterministic"]),
                               spinup_sector, places=3)

    def test_equal_mix_sits_strictly_between_the_endpoints(self):
        mix = float(self.shipped["sewer_equal_mix"]["deterministic"])
        self.assertLess(float(self.shipped["sewer_all_flowing"]["deterministic"]), mix)
        self.assertLess(mix, float(self.shipped["sewer_all_stagnant"]["deterministic"]))

    def test_hies_partition_lowers_the_sector(self):
        """More uncollected waste means more immediate burning and less slow decay; the
        net must FALL, which is the direction the validation prose reports."""
        self.assertLess(float(self.shipped["hies_route_shares"]["deterministic"]),
                        float(self.shipped["reference"]["deterministic"]))

    def test_every_row_declares_its_interpretation(self):
        for name, r in self.shipped.items():
            if r["P2.5"] == "":
                self.assertIn("deterministic endpoint", r["interpretation"], name)
            else:
                self.assertEqual(r["interpretation"], uncertainty.INTERPRETATION,
                                 name)

    def test_the_effluent_endpoints_state_the_reviewers_arithmetic(self):
        """The seventh review scaled the N2O component to the published factor
        endpoints to show +/-100% was incompatible with the stated evidence. The
        endpoint scenarios must reproduce exactly that arithmetic as sector totals.

        rc67: the component is the 2019 Refinement's, and only its EFFLUENT part (2.541
        of 2.572 Mt) rides the effluent factor; the plant part does not. The endpoints
        are the Refinement's 0.0005 and 0.075 (the 2006 Guidelines' 0.25 through rc66,
        when the whole 3.03 Mt scaled)."""
        low = float(self.shipped["effluent_ef_low"]["deterministic"])
        high = float(self.shipped["effluent_ef_high"]["deterministic"])
        base = float(self.shipped["reference"]["deterministic"])
        data = WasteData()
        effluent = sum(r["n2o_effluent_Gg"]
                       for r in wastewater.nitrogen_pathways(data)) * 265.0 / 1000.0
        self.assertAlmostEqual(effluent, 2.5415, places=3)
        self.assertEqual(data.param_bounds["ww_ef_effluent"], (0.0005, 0.075))
        self.assertAlmostEqual(low, base - effluent + effluent * 0.0005 / 0.005, delta=0.02)
        self.assertAlmostEqual(high, base - effluent + effluent * 0.075 / 0.005, delta=0.05)
        self.assertEqual(self.shipped["effluent_ef_low"]["P2.5"], "")
        self.assertEqual(self.shipped["effluent_ef_high"]["P2.5"], "")

    def test_the_river_mcf_range_is_priced_conditionally(self):
        """The river MCF's own 0-0.2 range, conditional on the flowing reading:
        the low case removes sewered CH4 entirely, so it must sit below the
        default flowing case, which must sit below the high case."""
        low = float(self.shipped["sewer_flowing_river_low"]["deterministic"])
        mid = float(self.shipped["sewer_all_flowing"]["deterministic"])
        high = float(self.shipped["sewer_flowing_river_high"]["deterministic"])
        self.assertLess(low, mid)
        self.assertLess(mid, high)

    def test_shipped_scenarios_match_a_fresh_computation(self):
        fresh = {r["structural_scenario"]: r
                 for r in uncertainty.structural_scenarios(n_iter=200)}
        self.assertEqual(set(fresh), set(self.shipped))
        for name in fresh:
            self.assertAlmostEqual(float(self.shipped[name]["deterministic"]),
                                   fresh[name]["deterministic"], places=3, msg=name)


class TestInputsRegister(unittest.TestCase):
    def test_register_covers_waste_params_bidirectionally(self):
        """Every parameter in waste_params.csv appears in the register, and every
        register key exists in the file - a parameter added without a row, or a row
        for a deleted parameter, fails here instead of shipping silently."""
        data = WasteData()
        self.assertEqual(set(data.params), set(uncertainty._REGISTER))

    def test_structural_rows_are_never_sampled(self):
        for r in uncertainty.inputs_register(WasteData()):
            if r["uncertainty_class"] == "structural":
                self.assertEqual(r["distribution"], "not sampled", r["variable"])
            elif r["variable"] in uncertainty.BOUNDED_DRAW:
                self.assertIn("bounded log split-triangular", r["distribution"])
            else:
                self.assertEqual(r["distribution"], "lognormal", r["variable"])

    def test_the_national_mc_stream_is_untouched(self):
        """The module's whole reason for a private seed: its runs must not perturb the
        pooled national file. Assert the seed is not the national one."""
        from pkinv.core import montecarlo as mc_core
        self.assertNotEqual(uncertainty.SCENARIO_SEED, mc_core.SEED)
        self.assertNotEqual(uncertainty.RERUN_SEED, mc_core.SEED)


class TestBoundedDraw(unittest.TestCase):
    """The rc11 repair's distribution: published endpoints bound the draw, the IPCC
    default is mode and median, and the closed-form sigma matches the shape."""

    LOW, MODE, HIGH = 0.0005, 0.005, 0.075    # the 2019 Refinement's range (0.25 through rc66)

    def test_median_is_the_mode(self):
        self.assertAlmostEqual(
            uncertainty.bounded_log_split_triangular(0.5, self.LOW, self.MODE,
                                                     self.HIGH),
            self.MODE, places=12)

    def test_the_published_endpoints_bound_every_draw(self):
        import random
        rng = random.Random(11)
        for _ in range(2000):
            x = uncertainty.bounded_log_split_triangular(rng.random(), self.LOW,
                                                         self.MODE, self.HIGH)
            self.assertGreaterEqual(x, self.LOW)
            self.assertLessEqual(x, self.HIGH)

    def test_closed_form_sigma_matches_a_sample(self):
        import math as m
        import random
        rng = random.Random(13)
        logs = [m.log(uncertainty.bounded_log_split_triangular(
            rng.random(), self.LOW, self.MODE, self.HIGH)) for _ in range(50000)]
        mean = sum(logs) / len(logs)
        sample = m.sqrt(sum((v - mean) ** 2 for v in logs) / len(logs))
        closed = uncertainty.log_split_triangular_sigma(self.LOW, self.MODE,
                                                        self.HIGH)
        self.assertAlmostEqual(sample, closed, delta=0.01)

    def test_the_declared_width_round_trips_through_sigma_log(self):
        """The declared uncert_pct exists to be consumed by sigma_log; the national
        stream must sample the bounded shape's own log-variance, not the wider
        value a percentile-span declaration would produce."""
        from pkinv.core.montecarlo import sigma_log
        data = WasteData()
        eq = uncertainty.equivalent_bounded_uncert_pct(data, "ww_ef_effluent")
        true = uncertainty.log_split_triangular_sigma(self.LOW, self.MODE,
                                                      self.HIGH)
        self.assertAlmostEqual(sigma_log(eq), true, places=6)
        # about 644 per cent on the Refinement's range (about 1135 on the 2006 range)
        self.assertGreater(uncertainty.bounded_span_pct(data, "ww_ef_effluent"),
                           600.0)


class TestParameterRerunMC(unittest.TestCase):
    """The seventh review's architectural demand: draw the inputs, rebuild the
    sector, and let the fate ledger's closure hold in every single draw."""

    @classmethod
    def setUpClass(cls):
        # 400 draws: the closure assertion runs inside parameter_rerun_mc for each,
        # so a single passing call IS the ledger-true property at this n
        cls.rows = {r["scope"]: r
                    for r in uncertainty.parameter_rerun_mc(n_iter=400)}

    def test_every_draw_closed_the_ledger(self):
        for r in self.rows.values():
            self.assertEqual(r["ledger_closed_in_every_draw"], "yes")

    def test_the_sector_interval_is_asymmetric_upward(self):
        """The bounded effluent factor's long right tail: the mean sits above the
        deterministic value and the upper arm is much longer than the lower."""
        s = self.rows["SECTOR"]
        self.assertGreater(s["mean"], s["deterministic"])
        self.assertGreater(s["P97.5"] - s["P50"], s["P50"] - s["P2.5"])

    def test_percentiles_are_ordered(self):
        for r in self.rows.values():
            self.assertLess(r["P2.5"], r["P50"])
            self.assertLess(r["P50"], r["P97.5"])

    def test_the_deterministic_totals_are_the_shipped_ones(self):
        self.assertAlmostEqual(self.rows["SECTOR"]["deterministic"],
                               _totals_cell("TOTAL"), places=4)


class TestNationalScopeRepair(unittest.TestCase):
    """The two scope defects the rc11 audit found in the SHIPPED national
    decomposition - both proven red against the shipped file before the
    regeneration that turns them green."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(OUTPUTS, "national_uncertainty_decomposition.csv")
        with open(path, newline="", encoding="utf-8") as f:
            cls.rows = [r for r in csv.DictReader(f) if r["module"] == "waste"]

    def _row(self, subitem):
        return next(r for r in self.rows if r["subitem"] == subitem)

    def test_the_n2o_row_names_the_effluent_factor_not_bod(self):
        """19.13% of the N2O row's variance was attributed to BOD and Bo - two
        parameters that never enter it (N2O derives from protein, as the paper
        itself states) - while the effluent factor, the softest number in the
        sector, hid inside residual:waste."""
        groups = self._row("Domestic wastewater N2O")["dependency_groups"]
        self.assertNotIn("ww_bod", groups)
        self.assertNotIn("ww_bo=", groups)
        self.assertIn("ww_ef_effluent", groups)

    def test_the_ch4_row_keeps_bod_and_bo(self):
        groups = self._row("Domestic wastewater CH4")["dependency_groups"]
        self.assertIn("ww_bod_g_per_cap_day", groups)
        self.assertIn("ww_bo=", groups)

    def test_the_partition_is_signed_anticorrelated(self):
        """Unsigned sharing drew disposal and burning POSITIVELY correlated - the
        opposite of the physics the sector's own Approach 1 states. The disposal
        member of waste_partition must now carry a negative sigma."""
        import re
        for r in self.rows:
            if r["category"] != "Solid waste disposal":
                continue
            m = re.search(r"waste_partition=(-?[\d.]+)", r["dependency_groups"])
            if m:
                self.assertLess(float(m.group(1)), 0.0, r["subitem"])
        burning = [r for r in self.rows if r["category"] == "Open burning of waste"]
        signs = [re.search(r"waste_partition=(-?[\d.]+)", r["dependency_groups"])
                 for r in burning]
        self.assertTrue(any(m and float(m.group(1)) > 0 for m in signs))


class TestBoundedParamsDeclareNoSymmetricWidth(unittest.TestCase):
    """The ninth review found Appendix F printing "±100%" for the effluent factor
    beside its own 500-fold published range - a residue of the treatment the
    seventh review rejected, faithfully republished by the table generator
    because the DATA FILE still carried it. A parameter drawn bounded
    split-triangular has no honest symmetric width to declare in the CSV: its
    width column must be empty, and the published equivalent lives in
    equivalent_bounded_uncert_pct(), never a hand-kept number."""

    def test_no_bounded_draw_param_declares_a_symmetric_pct(self):
        import csv
        from pkinv.sectors.waste import uncertainty as wu
        path = asset_path(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "data", "waste_params.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = {r["param"]: r for r in csv.DictReader(
                line for line in handle if not line.startswith("#"))}
        for param in wu.BOUNDED_DRAW:
            self.assertEqual(rows[param]["uncert_pct"].strip(), "",
                             "%s is drawn bounded split-triangular but the data "
                             "file still declares a symmetric pct - the exact "
                             "cell Appendix F republishes" % param)
            self.assertTrue(rows[param]["lower"].strip() and
                            rows[param]["upper"].strip(),
                            "%s must keep its published bounds" % param)
