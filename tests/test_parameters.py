"""The parameter-level uncertainty model, and the identity it rests on.

WHAT THIS REPLACED. A component carried one `uncert_pct` and at most one `corr_group` string,
and the manuscript declared the consequence as a limitation for two rounds: a real emissions row
depends on several uncertain quantities at once - an activity, a conversion, a factor - each
shared with a different set of other rows. One string cannot say that, so the power module sat
outside the cross-sector factor scenario entirely and the key-category variance ranking assumed
categories were independent while livestock counts drove two of them.

THE IDENTITY. core.uncertainty.product() combines relative uncertainties in quadrature, so a
component's variance is already an additive decomposition:

    sigma^2_component = sum over shared groups sigma^2_g  +  sigma^2_residual

Preserving it is what makes this a generalisation rather than a replacement, and the first test
class proves that directly.
"""

from pkinv.assets import asset_path
import math
import os
import sys
import unittest


from pkinv.core import montecarlo, parameters, registry   # noqa: E402
from _support import ROOT

_BUILT = registry.build_all()


def _components():
    comps = [dict(c) for c in _BUILT[0]]
    for c in comps:
        c["_mc_key"] = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
    return comps


class TestTheModelContainsTheOldOne(unittest.TestCase):
    """With nothing shared, the parameter mode must be the per-component mode.

    This is the load-bearing test of the rebuild. A new uncertainty model that cannot reproduce
    the old one in the degenerate case is not a generalisation of it, and every band it
    publishes would be moving for two reasons at once - the new structure and an unnoticed
    change in the arithmetic - with no way to tell them apart.
    """

    def test_with_no_shared_parameters_every_category_matches(self):
        """Both sides stripped of correlation: no parameter groups on one, no corr_group on
        the other. What remains is the same arithmetic drawn the same way, and it must agree
        to the last place - which it does, for all nineteen categories.

        Comparing against an UNSTRIPPED per-component run was the first version and it failed
        on managed soils by ten points, correctly: agriculture declares a correlation group
        over its indirect nitrogen pathways, so the two runs were being asked to agree about a
        structure only one of them had.
        """
        cats = list(_BUILT[1])
        stripped = [dict(c, corr_group=None) for c in _components()]
        original = parameters.groups_for
        try:
            parameters.groups_for = lambda component, scopes=None: []
            degenerate, _ = montecarlo.run(stripped, cats, n_iter=4000, stream="parameter")
        finally:
            parameters.groups_for = original
        per_component, _ = montecarlo.run(stripped, cats, n_iter=4000, stream="per_component")
        for category in cats:
            self.assertAlmostEqual(
                degenerate[category]["rel_pct"], per_component[category]["rel_pct"], places=6,
                msg="%s differs between the degenerate parameter mode and per-component"
                    % category)

    def test_the_national_total_differs_only_by_the_declared_groups(self):
        """The national total is the one place the degenerate case SHOULD differ: the
        per-component mode also applies the sector-declared corr_group strings, which is
        exactly the correlation the parameter model supplies through named groups instead."""
        comps, cats = _components(), list(_BUILT[1])
        original = parameters.groups_for
        try:
            parameters.groups_for = lambda component, scopes=None: []
            degenerate, _ = montecarlo.run(comps, cats, n_iter=4000, stream="parameter")
        finally:
            parameters.groups_for = original
        per_component, _ = montecarlo.run(comps, cats, n_iter=4000, stream="per_component")
        self.assertLess(degenerate["TOTAL"]["rel_pct"], per_component["TOTAL"]["rel_pct"],
                        "with no correlation at all the national band should be narrower than "
                        "one carrying the sector-declared groups")


class TestTheDecompositionIsAnIdentity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = parameters.decompose(_BUILT[0])

    def test_named_and_residual_reconstruct_the_declared_variance(self):
        """The identity, wherever the row reconciles.

        A derived row's marginal is the recomposed parameter variance instead, and the next
        tests cover that case. The tolerance for calling a row derived is relative, so a
        handful sit just inside it and are excluded here by the same test the decomposition
        itself uses.
        """
        checked = tolerated = 0
        for c, shared, residual, derived in self.rows:
            if not c.get("uncert_pct") or derived:
                continue
            total = parameters.sigma_log(c["uncert_pct"])
            named = sum(s * s for s in shared.values())
            if named > total * total:
                # rc41: inside the decomposition's own relative tolerance - the published
                # uncert_pct is rounded and the recomposition lands a fraction of a percent
                # above it; the residual is zero there by construction. Scoping every
                # sector's factor groups (P-1) put 87 rows in this band, so it is counted
                # rather than skipped: an unexplained excess beyond the tolerance would
                # have raised in the decomposition itself.
                self.assertLessEqual(named, total * total * (1.0 + parameters.OVER_DECOMPOSITION_TOL),
                                     "%s/%s" % (c["_sector"], c["subitem"]))
                self.assertEqual(residual, 0.0, "%s/%s" % (c["_sector"], c["subitem"]))
                tolerated += 1
                continue
            checked += 1
            self.assertAlmostEqual(named + residual * residual, total * total, places=9,
                                   msg="%s/%s" % (c["_sector"], c["subitem"]))
        self.assertGreater(checked + tolerated, 100, "almost nothing reconciles - the identity "
                                                     "is not holding anywhere")
        self.assertGreater(checked, 40)

    def test_a_derived_row_has_zero_residual_and_a_disposition(self):
        """The sampled marginal of a derived row is exactly its named parameter variance --
        no invisible extra term -- and every one carries an audited disposition."""
        dispositions = parameters.load_dispositions()
        derived_rows = [(c, shared, residual) for c, shared, residual, d in self.rows if d]
        self.assertTrue(derived_rows, "no row is derived; update the registry and the prose "
                                      "together if the sectors now cover their parameters")
        for c, shared, residual in derived_rows:
            key = (c["_sector"], parameters.original_category(c), c["subitem"], c["gas"])
            self.assertEqual(residual, 0.0, "%s/%s" % (c["_sector"], c["subitem"]))
            self.assertEqual(dispositions.get(key), "derive_row_from_parameters",
                             "%s is derived without a disposition" % (key,))

    def test_no_residual_is_negative(self):
        for _c, _shared, residual, _derived in self.rows:
            self.assertGreaterEqual(residual, 0.0)

    def test_an_undeclared_excess_raises_instead_of_clamping(self):
        """THE REINSTATED DEFECT. The rc2 clamp -- residual = sqrt(max(total^2 - named, 0))
        -- silently sampled more variance than 23 rows declared while two docstrings
        promised no marginal moved. An over-decomposed row with no disposition must now be
        a loud error, proven here on a synthetic row whose named parameters exceed its
        declared width."""
        row = None
        for c, _s, _r, derived in self.rows:
            if derived:
                row = dict(c)
                break
        self.assertIsNotNone(row)
        with self.assertRaises(ValueError) as ctx:
            parameters.decompose([row], dispositions={})
        self.assertIn("no disposition", str(ctx.exception))

    def test_a_derived_marginal_is_reproduced_by_the_simulation(self):
        """The reviewer's gate: every marginal is reproduced by simulation.

        The worst audited row (railways diesel CO2, declared 5.4 against a derived 6.5) is
        simulated alone through the parameter mode; its sampled 95 percent half-width must
        match the analytic lognormal marginal of its named parameters within Monte Carlo
        noise, and must NOT match the declared width it used to sample."""
        target = None
        for c, shared, _r, derived in self.rows:
            if derived and c["_sector"] == "railways" and c["gas"] == "CO2":
                target = (dict(c), shared)
        self.assertIsNotNone(target, "the audited railways CO2 row is gone; re-point this")
        c, shared = target
        named = math.sqrt(sum(s * s for s in shared.values()))
        c["_mc_key"] = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
        stats, _ = montecarlo.run([c], [c["category"]], n_iter=20000, stream="parameter")
        sampled = stats[c["category"]]["rel_pct"]
        analytic = parameters.pct_from_sigma(named)
        self.assertLess(abs(sampled - analytic), 0.6,
                        "sampled %.2f%% against the analytic derived marginal %.2f%%"
                        % (sampled, analytic))
        self.assertGreater(abs(sampled - c["uncert_pct"]), 0.6,
                           "the sampled width matches the DECLARED %.2f%% -- the derived "
                           "marginal is not being sampled" % c["uncert_pct"])

    def test_a_component_can_depend_on_several_groups(self):
        """The whole point. Under the old model a row carried one correlation group."""
        counts = [len(shared) for _c, shared, _r, _o in self.rows]
        self.assertGreater(max(counts), 1)
        self.assertGreater(sum(1 for n in counts if n > 1), 50,
                           "almost no row has more than one dependency, so the rebuild has "
                           "not changed what it was built to change")

    def test_power_is_no_longer_excluded_from_cross_sector_sharing(self):
        """The specific defect. Power's grid rows carried a sector-declared TOE group, and
        because a row could hold only one group they were excluded from the fuel-carbon
        scenario entirely. They must now carry both."""
        for c, shared, _r, _o in self.rows:
            if c["_sector"] == "power" and c["subitem"].startswith("Gas "):
                self.assertIn("1a1a_toe_activity", shared)
                self.assertTrue(any(g.startswith("factor:") for g in shared),
                                "power's gas rows carry the TOE conversion but no fuel factor")
                return
        self.fail("no power gas row found")


class TestTheScopeMapResolvesBothWays(unittest.TestCase):
    """A declared mapping that names something absent, or omits something present, is the
    failure mode data/source_keys.csv was written to prevent in 8a. Same discipline here."""

    def test_every_scope_pattern_matches_at_least_one_component(self):
        comps = _BUILT[0]
        scopes = parameters.scope_map()
        unmatched = []
        for group, rules in scopes.items():
            if not any(parameters._matches(c, *rule[:3]) for c in comps for rule in rules):
                unmatched.append(group)
        self.assertFalse(unmatched, "scope entries matching no component: %s" % unmatched)

    def test_every_multi_component_group_is_scoped_or_self_scoping(self):
        """A dependency group spanning several components must be declared, unless it scopes
        itself through core.factors - which the fuel factors do, and which is why they are
        deliberately absent from the scope file rather than duplicated into it."""
        comps = _BUILT[0]
        scopes = parameters.scope_map()
        touched = {}
        for c in comps:
            for g in parameters.groups_for(c, scopes):
                touched.setdefault(g, set()).add((c["_sector"], c["subitem"]))
        for group, rows in touched.items():
            if len(rows) > 1:
                self.assertTrue(group in scopes or group.startswith("factor:"),
                                "%s spans %d components and is neither declared nor a fuel "
                                "factor" % (group, len(rows)))

    def test_the_cross_category_links_the_review_named_are_present(self):
        """Three specific shared quantities the independent-category ranking got wrong."""
        comps = _BUILT[0]
        scopes = parameters.scope_map()
        categories = {}
        for c in comps:
            for g in parameters.groups_for(c, scopes):
                categories.setdefault(g, set()).add(c["category"])
        self.assertGreaterEqual(len(categories.get("livestock:buffalo", set())), 2,
                                "the buffalo count does not span enteric and manure")
        self.assertGreaterEqual(len(categories.get("1a3b_diesel_control", set())), 2,
                                "the road diesel control does not span road and off-road")
        self.assertGreaterEqual(len(categories.get("waste_generation", set())), 2,
                                "waste generation does not span disposal and open burning")


class TestCommonRandomNumbers(unittest.TestCase):
    """The two covariance scenarios must share their randomness (the review's 3.7).

    Keyed on the group STRING, the within-sector run's "<sector>|<group>" renaming reseeded
    every grouped stream, so comparing the scenarios mixed the structural effect with a
    wholesale re-draw. The per_component mode documented and fixed exactly this; the fix
    never reached the parameter mode that ships. Both now key through
    montecarlo.group_representatives / group_stream_key.
    """

    def test_the_representative_key_is_scenario_invariant(self):
        cross = montecarlo.group_stream_key("factor:co2:Gas/Diesel Oil", "row-a", True)
        within = montecarlo.group_stream_key("transport|factor:co2:Gas/Diesel Oil",
                                             "row-a", False)
        self.assertEqual(cross, within,
                         "the sector holding the representative draws differently in the "
                         "two scenarios; the comparison is a re-draw again")

    def test_the_group_string_keying_is_the_stored_defect(self):
        """The rc2 seeds, reproduced: keying on the group name gives the two scenarios
        unrelated streams for the same physical factor. If this ever passes with equal
        seeds, stream_seed lost its keying and everything else here is vacuous."""
        old_cross = montecarlo.stream_seed(42, "group|factor:co2:Gas/Diesel Oil")
        old_within = montecarlo.stream_seed(42, "group|transport|factor:co2:Gas/Diesel Oil")
        self.assertNotEqual(old_cross, old_within)

    def test_two_groups_sharing_a_representative_draw_different_streams(self):
        """A row carrying several groups is often the lexicographic first of more than one;
        the physical group name in the key is what keeps their draws independent."""
        k1 = montecarlo.group_stream_key("factor:co2:Gas/Diesel Oil", "row-a", True)
        k2 = montecarlo.group_stream_key("factor:ncv:Gas/Diesel Oil", "row-a", True)
        self.assertNotEqual(k1, k2)

    def test_the_published_pair_shares_its_randomness_end_to_end(self):
        """Run both scenarios small and compare a single-group component's draws: the
        representative row's realisations must be identical across scenarios."""
        comps = [c for c in _components() if c["_sector"] == "railways"]
        cats = sorted({c["category"] for c in comps})
        _stats_w, _t, samples_w = montecarlo.run(comps, cats, n_iter=500,
                                                 stream="parameter", cross_sector=False,
                                                 return_samples=True)
        _stats_c, _t2, samples_c = montecarlo.run(comps, cats, n_iter=500,
                                                  stream="parameter", cross_sector=True,
                                                  return_samples=True)
        # Railways is one sector, so every group's representative is its own; the two
        # scenarios must produce identical draws for the whole category.
        for cat in cats:
            self.assertEqual(samples_w[cat], samples_c[cat],
                             "a single-sector category draws differently across scenarios "
                             "-- common random numbers are broken")


class TestTheResolutionRegistries(unittest.TestCase):
    """The three declared files behind _group_sigma, resolved both ways."""

    @classmethod
    def setUpClass(cls):
        cls.params = parameters.registry()
        cls.by_group = parameters.by_group(cls.params)
        cls.rules = parameters.load_group_rules()
        cls.bindings = parameters.load_member_bindings()
        cls.exclusions = parameters.load_scope_exclusions()

    def test_every_rule_names_a_real_multi_member_group(self):
        for group, rule in self.rules.items():
            self.assertIn(rule, ("select", "product", "blend"), group)
            members = self.by_group.get(group, [])
            self.assertGreater(len(members), 1,
                               "%s has a declared rule but %d drawable members"
                               % (group, len(members)))

    def test_every_binding_names_a_registry_parameter(self):
        ids = {p["parameter_id"] for p in self.params}
        for pid in self.bindings:
            self.assertIn(pid, ids, "%s is bound but not in the registry" % pid)

    def test_every_select_group_is_fully_bound(self):
        """Every drawable member of a select group carries a binding row; an unbound
        member would be silently unreachable, which is the median defect wearing a
        different face."""
        for group, rule in self.rules.items():
            if rule != "select":
                continue
            for p in self.by_group[group]:
                self.assertIn(p["parameter_id"], self.bindings,
                              "select group %s has unbound member %s"
                              % (group, p["parameter_id"]))

    def test_every_exclusion_names_a_real_group_and_substitute(self):
        groups = set(self.by_group)
        ids = {p["parameter_id"] for p in self.params}
        modules = {p["module"] for p in self.params} | {"industry"}
        for (module, group), substitute in self.exclusions.items():
            self.assertIn(module, modules)
            self.assertIn(group, groups,
                          "exclusion for %s names group %s, which carries no variance"
                          % (module, group))
            self.assertTrue(substitute in groups or substitute in ids
                            or substitute == "declared-row-residual",
                            "exclusion (%s, %s) names substitute %r, which is neither a "
                            "dependency group, a parameter, nor the declared sentinel"
                            % (module, group, substitute))

    def test_every_heterogeneous_scoped_group_has_a_rule(self):
        """The completeness guard: a reached multi-member group whose members disagree on
        width either resolves by table identity (factor:*) or carries a declared rule.
        decompose() raises on the gap; this states the property directly so the failure
        names the registry rather than the first row that trips it."""
        comps = _BUILT[0]
        scopes = parameters.scope_map()
        reached = set()
        for c in comps:
            reached.update(parameters.groups_for(c, scopes))
        for group in reached:
            members = self.by_group.get(group, [])
            if len(members) < 2 or all(p["parameter_id"].startswith("ef:")
                                       for p in members):
                continue
            sigmas = sorted(parameters.sigma_log(p["uncert_pct_95"]) for p in members)
            if sigmas[-1] - sigmas[0] < 1e-9:
                continue
            self.assertIn(group, self.rules,
                          "%s is reached, heterogeneous and has no declared rule" % group)

    def test_the_reconciliation_registry_matches_the_live_rows_both_ways(self):
        """Every derive disposition is a live derived row and every live derived row has
        one; a disposition that starts reconciling must be retired deliberately, because a
        stale audit row is a claim about a defect that no longer exists.

        The rc18 vintage_width_mismatch rows are the declared exception: they bind
        in the HISTORICAL panel years, where the year's own activity width differs
        from the registry's reference vintage, and must reconcile exactly at the
        reference year - the second assertion holds that shape, so the exemption
        cannot hide an ordinary always-derived row."""
        import csv as _csv
        with open(asset_path(ROOT, "data", "uncertainty_reconciliation.csv")) as handle:
            causes = {(r["module"], r["category"], r["subitem"], r["gas"]):
                      r["cause"] for r in _csv.DictReader(
                          line for line in handle if not line.startswith("#"))}
        vintage = {k for k, cause in causes.items()
                   if cause == "vintage_width_mismatch"}
        rows = parameters.decompose(_BUILT[0])
        live = {(c["_sector"], parameters.original_category(c), c["subitem"], c["gas"])
                for c, _s, _r, derived in rows if derived}
        declared = {k for k, action in parameters.load_dispositions().items()
                    if action == "derive_row_from_parameters"} - vintage
        self.assertEqual(declared, live,
                         "derive dispositions and live derived rows disagree:\n  only "
                         "declared: %s\n  only live: %s"
                         % (sorted(declared - live), sorted(live - declared)))
        self.assertFalse(vintage & live,
                         "a vintage_width_mismatch row derives AT THE REFERENCE "
                         "year - its cause claims it reconciles there, so either "
                         "the cause is wrong or the reference widths drifted: %s"
                         % sorted(vintage & live))
        self.assertTrue(vintage, "the rc18 vintage rows are gone; if they were "
                                 "retired deliberately, retire this exception too")

    def test_every_audited_row_names_a_live_component(self):
        keys = {("%s" % c["_sector"], c["category"], c["subitem"], c["gas"])
                for c in _BUILT[0]}
        for key in parameters.load_dispositions():
            self.assertIn(key, keys, "audit row %s matches no live component" % (key,))

    def test_the_confidence_vocabulary_is_closed_and_total(self):
        """Every drawable width states what it means (the review's 3.3), in one of the two
        honest conventions; a third convention must be declared before it is drawn."""
        for p in parameters.drawable(self.params):
            self.assertIn(p["confidence_interpretation"],
                          parameters.CONFIDENCE_VOCABULARY, p["parameter_id"])


class TestTheRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.params = parameters.registry()

    def test_structural_parameters_are_never_drawn(self):
        """A structural fork is a choice between readings of evidence, and data/scenarios.csv
        already registers it. Sampling one would put a probability on something this inventory
        declines to put a probability on."""
        for p in parameters.drawable(self.params):
            self.assertEqual(p["kind"], "parametric", p["parameter_id"])

    def test_a_shared_factor_is_one_group_across_sectors(self):
        """pow_co2_hsd and tr_co2_diesel are two rows for one number - 74100 kg/TJ for
        gas/diesel oil. Grouping by ef_id would make the power sector's diesel carbon content
        independent of the transport sector's."""
        groups = parameters.by_group(self.params)
        diesel = groups.get("factor:co2:Gas/Diesel Oil", [])
        self.assertGreater(len(diesel), 1,
                           "the diesel carbon content resolves to one sector's row only")

    def test_the_registry_covers_agriculture(self):
        """Agriculture is half the inventory and had no parameter table at all; its activity
        widths live in the activity files, which is where they are read from."""
        agri = [p for p in self.params if p["module"] == "agriculture"]
        self.assertGreater(len(agri), 10)
        self.assertTrue(any(p["dependency_group"].startswith("livestock:") for p in agri))



class TestOneNitrogenSeriesIsOneParameter(unittest.TestCase):
    """The eleventh review asked for the acknowledged missing shared draws. One is
    already a defect rather than an omission: urea CO2 is derived from the SAME
    audited national nitrogen offtake that drives managed soils
    (sectors/agriculture/liming_urea.py reads fertilizer["nitrogen_N_offtake"]),
    yet the scope registry named it twice - once per category - so a draw moved the
    two independently. One physical quantity, one parameter, both categories."""

    def test_the_nitrogen_offtake_scope_spans_soils_and_urea(self):
        import csv, os
        path = asset_path(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "data", "parameter_scope.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = [r for r in csv.DictReader(
                line for line in handle if not line.startswith("#"))]
        nitro = [r for r in rows
                 if r["dependency_group"].startswith("fertiliser:nitrogen_N")]
        self.assertEqual(len(nitro), 1,
                         "the national nitrogen offtake is scoped under %d ids; it "
                         "is one series and one draw must move every category it "
                         "feeds" % len(nitro))
        cats = nitro[0]["category_pattern"]
        self.assertIn("Managed soils", cats)
        # rc39 A4: the scope spans managed soils and UREA APPLICATION. It used to say
        # "Liming", which was the combined category's name - the nitrogen offtake never
        # multiplied a liming row, and 3.G is now NE with no engine category at all.
        self.assertIn("Urea application", cats)

if __name__ == "__main__":
    unittest.main()
