"""The joint uncertainty statement, and the correlation rule it asks readers to apply.

A rule that lives in a column is a rule nobody checks. The load-bearing test here is a WORKED
EXAMPLE: scale a category's interval onto its district shares, sum the districts back up, and
assert the linear rule reproduces the category interval while quadrature does not. Without the
positive control the first assertion passes on any arithmetic at all.

The other property is monotonic: a FINER figure may never carry a narrower bound than a
coarser one. A district-month value is the national total's uncertainty plus everything the
allocation and the profile could have got wrong, and if it ever came out narrower then a
bracket has been applied where it does not bite.

Run:  python3 -m unittest discover tests -p "test_joint_uncertainty.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.paths import OUTPUTS
from pkinv.report import joint_uncertainty as joint
from pkinv.core.io import read_rows


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name))


class TestTheCorrelationRule(unittest.TestCase):
    """Within a category the parametric error is one draw: the same emission factor moves
    every district and every month together. That is what makes linear addition correct and
    quadrature wrong, and getting it backwards would make a national total look an order of
    magnitude more certain than the Monte Carlo says it is."""

    def test_summing_districts_linearly_reproduces_the_category_interval(self):
        row = next(r for r in _rows("pakemis_joint_uncertainty.csv")
                   if r["resolution"] == "annual_adm2"
                   and r["category"] == "Enteric fermentation")
        total = float(row["estimate_Mt"])
        low_pct = float(row["envelope_low_pct"])

        # A plausible district split - the shares do not matter to the property, only that
        # they partition the category, which is what a real ADM2 panel does.
        shares = [0.42, 0.23, 0.15, 0.11, 0.06, 0.03]
        self.assertAlmostEqual(sum(shares), 1.0, places=9)
        pieces = [total * share for share in shares]
        band = [piece * abs(low_pct) / 100.0 for piece in pieces]

        linear = sum(band)
        self.assertAlmostEqual(linear, total * abs(low_pct) / 100.0, places=6,
                               msg="the districts do not sum back to the category")

    def test_quadrature_would_understate_it_and_that_is_the_point(self):
        """The positive control. Without it the test above passes on any arithmetic."""
        total, low_pct = 151.559, -22.15
        shares = [0.42, 0.23, 0.15, 0.11, 0.06, 0.03]
        band = [total * share * abs(low_pct) / 100.0 for share in shares]
        quadrature = sum(value ** 2 for value in band) ** 0.5
        linear = sum(band)
        self.assertLess(quadrature, 0.7 * linear,
                        "quadrature should collapse this interval; if it no longer does, the "
                        "example has stopped being able to tell the two rules apart")

    def test_the_rule_is_published_on_every_row(self):
        for row in _rows("pakemis_joint_uncertainty.csv"):
            self.assertEqual(float(row["correlation_within_category"]), 1.0)
            self.assertIn("linearly", row["aggregation_rule"])
            self.assertIn("never in quadrature", row["aggregation_rule"])

    def test_across_categories_the_rule_defers_to_the_monte_carlo(self):
        """THE DIRECTION MATTERS AND THE FIRST CUT OF THIS GOT IT WRONG. Adding the twenty
        category intervals linearly inflated the national bound from -10.0/+15.7 to
        -22.0/+45.3. That is not a conservative reading of the evidence, it is a different
        and wrong one: it asserts every sector's factors move together, which the correlation
        model explicitly denies. So the annual national envelope must BE the MC's own
        national interval, not a re-derivation of it."""
        mc = next(r for r in _rows("national_uncertainty_montecarlo.csv")
                  if r["aggregation_level"] == "national"
                  and r["scenario"] == "cross_sector")
        _total, low, high = joint.national_envelope()["annual_national"]
        self.assertAlmostEqual(low, -float(mc["rel_down_pct_95"]), places=6)
        self.assertAlmostEqual(high, float(mc["rel_up_pct_95"]), places=6)

    def test_the_summed_categories_would_disagree_and_are_not_used(self):
        """The control on the one above: linear cross-category addition gives a materially
        different answer, so deferring to the MC is a choice this file makes rather than an
        arithmetic coincidence."""
        rows = [r for r in _rows("pakemis_joint_uncertainty.csv")
                if r["resolution"] == "annual_national"]
        total = sum(float(r["estimate_Mt"]) for r in rows)
        summed = sum(float(r["estimate_Mt"]) * abs(float(r["envelope_low_pct"])) / 100.0
                     for r in rows)
        _t, low, _h = joint.national_envelope()["annual_national"]
        self.assertGreater(100.0 * summed / total, 1.5 * abs(low),
                           "linear cross-category addition no longer differs from the MC, so "
                           "this file's choice between them has stopped being observable")


class TestTheEnvelopeIsABoundAndSaysSo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_joint_uncertainty.csv")

    # The four resolutions are a LATTICE, not a chain, and asserting a chain is how this test
    # first failed. monthly_national and annual_adm2 are incomparable: one adds a timing
    # bracket and the other a placement bracket, and railways has timing priced at 15.1% with
    # placement unpriced, so its monthly national bound is legitimately wider than its annual
    # district one. Only the four real refinement edges may be asserted.
    REFINEMENTS = (("annual_national", "monthly_national"),
                   ("annual_national", "annual_adm2"),
                   ("monthly_national", "monthly_adm2"),
                   ("annual_adm2", "monthly_adm2"))

    def test_a_finer_figure_is_never_more_certain_than_a_coarser_one(self):
        """A district-month value carries the national uncertainty PLUS whatever the profile
        and the allocation could have got wrong; if it ever came out narrower along a real
        refinement edge, a bracket has been applied where it does not bite."""
        by_category = {}
        for row in self.rows:
            by_category.setdefault(row["category"], {})[row["resolution"]] = row

        def width(row):
            return float(row["envelope_high_pct"]) - float(row["envelope_low_pct"])

        for category, at in sorted(by_category.items()):
            for coarser, finer in self.REFINEMENTS:
                self.assertGreaterEqual(
                    width(at[finer]), width(at[coarser]) - 1e-9,
                    "%s narrows from %s to %s" % (category, coarser, finer))

    def test_the_two_middle_resolutions_are_not_assumed_comparable(self):
        """The control on the lattice. If every category ever agreed on the ordering of
        monthly_national against annual_adm2, the partial order above would be indistinguishable
        from a chain and the next person would simplify it back into one."""
        by_category = {}
        for row in self.rows:
            by_category.setdefault(row["category"], {})[row["resolution"]] = row
        orderings = set()
        for at in by_category.values():
            timing = float(at["monthly_national"]["timing_pct"])
            placement = float(at["annual_adm2"]["placement_pct"])
            if timing != placement:
                orderings.add(timing > placement)
        self.assertEqual(orderings, {True, False},
                         "the two middle resolutions no longer disagree in both directions, "
                         "so the lattice has collapsed to a chain and should be re-read")

    def test_the_envelope_contains_the_parametric_interval(self):
        for row in self.rows:
            self.assertLessEqual(float(row["envelope_low_pct"]),
                                 float(row["parametric_low_pct"]) + 1e-9, row["category"])
            self.assertGreaterEqual(float(row["envelope_high_pct"]),
                                    float(row["parametric_high_pct"]) - 1e-9, row["category"])

    def test_no_component_is_priced_where_it_cannot_bite(self):
        """A placement bracket cannot move a national total and a timing bracket cannot move
        an annual one. Carrying either would widen a bound for a reason that does not apply,
        which is the mirror of the error the monotonic test catches."""
        for row in self.rows:
            _p, has_timing, has_placement = joint.APPLIES[row["resolution"]]
            if not has_timing:
                self.assertEqual(row["timing_status"], joint.NOT_APPLICABLE, row["category"])
                self.assertEqual(float(row["timing_pct"]), 0.0)
            if not has_placement:
                self.assertEqual(row["placement_status"], joint.NOT_APPLICABLE,
                                 row["category"])
                self.assertEqual(float(row["placement_pct"]), 0.0)

    def test_what_the_envelope_does_not_contain_is_named(self):
        """The column that keeps this product honest. An envelope that silently omitted an
        unpriced bracket would be narrower than the truth while reading as though it were
        wider. The counts live in the shipped file (an earlier docstring froze them
        and went stale twice); what is asserted is the naming, not a count."""
        named = 0
        for row in self.rows:
            unpriced = {name for name, status in (("timing", row["timing_status"]),
                                                  ("placement", row["placement_status"]))
                        if status == joint.UNPRICED}
            self.assertEqual(set(filter(None, row["unpriced_components"].split(";")))
                             - {"none"}, unpriced, row["category"])
            named += bool(unpriced)
        self.assertGreater(named, 0,
                           "every component is priced everywhere, which would be excellent "
                           "news and should be checked before it is believed")

    def test_a_bracket_never_claims_to_be_a_probability(self):
        for row in self.rows:
            self.assertIn("probabilistic", row["parametric_kind"])
            self.assertIn("carrying no probability", row["bracket_kind"])
            self.assertIn("bound, not a distribution", row["envelope_kind"])

    def test_every_priced_component_names_its_source(self):
        for row in self.rows:
            for status, source in ((row["timing_status"], row["timing_source"]),
                                   (row["placement_status"], row["placement_source"])):
                if status == joint.PRICED:
                    self.assertTrue(source.strip(),
                                    "%s prices a bracket and names no source" % row["category"])
                else:
                    self.assertFalse(source.strip(), row["category"])


class TestItCoversTheInventoryItClaimsTo(unittest.TestCase):
    def test_every_monte_carlo_category_appears(self):
        mc = {r["name"] for r in _rows("national_uncertainty_montecarlo.csv")
              if r["aggregation_level"] == "category"}
        published = {r["category"] for r in _rows("pakemis_joint_uncertainty.csv")}
        self.assertEqual(mc, published)

    def test_a_category_the_map_does_not_know_stops_the_build(self):
        """Fails closed. A category silently dropped from this table would read as a figure
        with no uncertainty at all, which is the strongest and least true claim available."""
        original = dict(joint.CATEGORY_MODULE)
        joint.CATEGORY_MODULE.pop("Rice cultivation")
        try:
            with self.assertRaises(ValueError) as caught:
                joint.build()
        finally:
            joint.CATEGORY_MODULE.clear()
            joint.CATEGORY_MODULE.update(original)
        self.assertIn("Rice cultivation", str(caught.exception))

    def test_it_regenerates_identically(self):
        committed = _rows("pakemis_joint_uncertainty.csv")
        fresh = joint.build()
        self.assertEqual(len(committed), len(fresh))
        for shipped, built in zip(committed, fresh):
            self.assertEqual(shipped["category"], built["category"])
            self.assertEqual(shipped["resolution"], built["resolution"])
            self.assertAlmostEqual(float(shipped["envelope_low_pct"]),
                                   built["envelope_low_pct"], places=6)


if __name__ == "__main__":
    unittest.main()


class TestTheValidationMatrixHasNoSilentHoles(unittest.TestCase):
    """The registry has always understood a declared absence as a first-class entry - its own
    docstring says so - and was never made COMPLETE. Eleven (module, property) cells had
    neither a comparison nor a declared absence: agriculture's magnitude, ippu's geography and
    the timing of eight modules. A cell with nothing in it reads as a property that was never
    at issue, which is exactly the silence the coverage matrix pattern was built to end.

    The guard is the Gate 1 pattern applied to validation: absence is a value, and a new
    sector arriving with no independent check has to say so rather than be discovered.
    """

    PROPERTIES = ("magnitude", "timing", "geography")

    def test_every_module_and_property_resolves_to_a_row(self):
        registry = _rows("pakemis_validation_catalog.csv")
        covered = {(row["module"], row["property_tested"]) for row in registry}
        modules = {row["module"] for row in _rows("pakemis_source_streams.csv")}
        holes = sorted((module, prop) for module in modules for prop in self.PROPERTIES
                       if (module, prop) not in covered)
        self.assertFalse(holes,
                         "no comparison and no declared absence for: %s" % holes)

    def test_a_declared_absence_says_what_would_close_it(self):
        for row in _rows("pakemis_validation_catalog.csv"):
            if row["calibration_or_validation"] != "declared-absence":
                continue
            self.assertGreater(len(row["interpretation_limit"]), 60,
                               "%s declares an absence and explains almost nothing about it"
                               % row["validation_id"])
            self.assertEqual(row["result_output"], "none", row["validation_id"])

    def test_the_guard_catches_a_removed_module(self):
        """Positive control: a module the registry never mentions must be reported."""
        covered = {(row["module"], row["property_tested"])
                   for row in _rows("pakemis_validation_catalog.csv")}
        holes = [("a_new_sector", prop) for prop in self.PROPERTIES
                 if ("a_new_sector", prop) not in covered]
        self.assertEqual(len(holes), 3)


class TestADeclaredAbsenceIsNotAnUncheckedOne(unittest.TestCase):
    """The guard that would have caught six rows I wrote the release before.

    Completing the validation coverage matrix, eleven declared-absence rows were added - and
    the coverage matrix was completed by DECLARING absences rather than by looking for the
    evidence, which is the failure mode a coverage matrix exists to prevent. Four of them were
    simply false: benchmark_spatial_allocation.csv had been scoring agriculture's district
    allocation against MNFSR crop records all along, and benchmark_temporal_hindcast.csv had
    been scoring power_liquids, industry_diesel and railways_diesel. Two more were pointers to
    evidence dressed as absences.

    So: a declared absence may not stand where a benchmark product carries a SCORED result for
    that module or one of its categories. The discriminator is a scored result and not a
    mention - the word "industry" appears in a magnitude benchmark's scope note beside a ratio
    of n/a, and reading that as coverage would replace one wrong claim with another.
    """

    # Declared, never inferred from the filename: which property each product can speak to. A
    # magnitude benchmark cannot refute a geography absence however many times it names the
    # module.
    PROPERTY_OF = {
        "national_benchmark_comparison.csv": "magnitude",
        "benchmark_spatial_allocation.csv": "geography",
        "benchmark_kiln_allocation.csv": "geography",
        "benchmark_temporal_hindcast.csv": "timing",
    }
    SCORED = ("scored", "priced", "matched")

    def _evidence(self, product):
        """{lowercased blob} of the rows that carry a scored result, or None."""
        try:
            rows = _rows(product)
        except (FileNotFoundError, IndexError):
            return None
        scored = [r for r in rows
                  if str(r.get("status", "")).lower() in self.SCORED]
        if not scored:
            return None
        return " ".join(" ".join(str(v) for v in r.values()) for r in scored).lower()

    def test_no_declared_absence_stands_over_a_scored_result(self):
        categories = {}
        for row in _rows("pakemis_source_streams.csv"):
            categories.setdefault(row["module"], set()).add(row["ipcc_category"].lower())
        problems = []
        for row in _rows("pakemis_validation_catalog.csv"):
            if row["calibration_or_validation"] != "declared-absence":
                continue
            keys = {row["module"].lower()} | categories.get(row["module"], set())
            for product, prop in sorted(self.PROPERTY_OF.items()):
                if prop != row["property_tested"]:
                    continue
                blob = self._evidence(product)
                if blob and any(key in blob for key in keys):
                    problems.append("%s declares an absence while %s carries a scored result "
                                    "for it" % (row["validation_id"], product))
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))

    def test_the_guard_reads_scored_rows_only(self):
        """Positive control on the discriminator. benchmark_spatial_allocation.csv lists
        enteric fermentation and manure management with status NO_RECORD - no district
        livestock record was found to score them against - and treating that as coverage
        would be the mirror of the defect this test exists for."""
        rows = _rows("benchmark_spatial_allocation.csv")
        self.assertTrue([r for r in rows if r["status"] == "NO_RECORD"],
                        "the NO_RECORD rows are gone, so this control watches nothing")
        blob = self._evidence("benchmark_spatial_allocation.csv")
        self.assertNotIn("enteric fermentation", blob,
                         "a NO_RECORD row leaked into the scored evidence")


class TestCompletenessIsTheFifthKind(unittest.TestCase):
    """rc18: completeness rides the lattice as a BOUND beside the interval -
    never a distribution inside it - and its national composition is anchored
    to the registers it reads."""

    def test_bounded_categories_carry_a_bound_and_a_source(self):
        rows = _rows("pakemis_joint_uncertainty.csv")
        bounded = {r["category"] for r in rows if r["completeness_bound_Mt"]}
        self.assertEqual(bounded, {"Industrial fuel combustion (1A2)",
                                   "Cement production",
                                   "Residential fuel combustion",
                                   "Managed soils"})
        for r in rows:
            if r["completeness_bound_Mt"]:
                self.assertIn("national_priority_rankings.csv",
                              r["completeness_bound_source"], r["category"])
            else:
                self.assertEqual(r["completeness_bound_source"],
                                 "no_bound_declared", r["category"])

    def test_the_bound_is_resolution_invariant(self):
        """Absent mass does not change with the resolution a figure is read
        at - a bound that varied by resolution would be a second arithmetic."""
        rows = _rows("pakemis_joint_uncertainty.csv")
        per_category = {}
        for r in rows:
            per_category.setdefault(r["category"], set()).add(
                r["completeness_bound_Mt"])
        for category, values in per_category.items():
            self.assertEqual(len(values), 1, category)

    def test_the_fgas_literal_is_anchored_to_the_benchmarks_register(self):
        """FGAS_BOUND_MT is a literal because no engine category exists to
        carry it; this pins it to the number inside the benchmark register's
        own note so it cannot drift alone."""
        import re
        from pkinv.report import joint_uncertainty as ju
        from pkinv.paths import DATA
        text = open(asset_path(DATA, "benchmarks.csv"),
                    encoding="utf-8").read()
        m = re.search(r"F-gases \(([\d.]+) Mt\)", text)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), ju.FGAS_BOUND_MT)

    def test_the_national_composition_sums_only_disjoint_bounds(self):
        from pkinv.report import joint_uncertainty as ju
        national = ju.completeness_national()
        industry = next(float(r["completeness_bound_Mt"])
                        for r in _rows("pakemis_joint_uncertainty.csv")
                        if r["category"] == "Industrial fuel combustion (1A2)"
                        and r["completeness_bound_Mt"])
        self.assertAlmostEqual(national["composable_bound_Mt"],
                               industry + ju.FGAS_BOUND_MT, places=6)
        self.assertIn("not summed", national["not_composed"])

    def test_the_screened_state_is_populated(self):
        """The state built for the screenings sat EMPTY for two releases: the
        1A2 register row inherited POWER (the code's first estimated sibling)
        and aviation's 1.A.5.b had no sector at all, so the in_scope
        configurations lit nothing. Custodial overrides fixed both, and Wave 4
        moved the gate from module-keyed to CODE-mapped - which is why the
        F-gas screening finally lights 2.F (its id lacks the in_scope
        substring the old gate matched on) and the new screens light their own
        codes whether or not a custodial sector is assigned. The power-labelled
        1.A.2 cell is the captive fleet's: its configuration retired at rc47
        Wave 0 (captive coal sits inside the booked brick residual), but the
        cell stays SCREENED through the register path - the captive screening
        product still bounds the excluded FO/diesel and the coal share of
        booked mass, which is exactly what the state means."""
        rows = _rows("pakemis_coverage_matrix.csv")
        screened = {(r["ipcc_code"], r["sector"]) for r in rows
                    if r["state"] == "screened"}
        self.assertEqual(screened, {("1.A.2", "industry"), ("1.A.2", "power"),
                                    ("1.A.5.b", "aviation"), ("2.F", ""),
                                    ("2.B.2", ""),   # 2.B.1 left the screen at rc52 (ammonia in the reference)
                                    ("1.A.4.a", ""), ("1.B.1", "")})
