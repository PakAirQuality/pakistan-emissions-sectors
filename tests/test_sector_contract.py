"""The sector contract, asserted against every registered sector.

Core allocates, aggregates and reconciles components without knowing any sector's
science. That only holds if every sector emits the same row shape, so these run over
`registry.all_sectors()` rather than over agriculture alone -- the point is that a
second sector cannot quietly diverge.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import datetime
import math
import os
import unittest

from pkinv.core import evidence, gwp, period, registry
from pkinv.core.components import ALL_KEYS, REQUIRED_KEYS
from _support import ROOT



def _build(sector):
    data = sector.load_data()
    return data, sector.build_components(data)



# The optional accessor set core/registry.py documents (rc34): a sector that
# exports one of these names must export a CALLABLE of that name - a constant
# or a stub under an accessor's name would be a silent lie to the report layer.
OPTIONAL_ACCESSORS = ("parameter_overrides", "gas_activity", "post_meter_factor",
                      "post_meter_param", "whole_gas_leak_share",
                      "gas_supply_balance_row", "coal_screen_rows",
                      "clinker_co2_Mt", "brick_kiln_screen_Mt", "bagasse_ceiling_Mt",
                      "components_for_year", "components_for_fiscal_year",
                      "series_components_for_year", "activity_basis")


class TestTheOptionalAccessors(unittest.TestCase):
    def test_every_exported_accessor_is_callable(self):
        for sector in registry.all_sectors():
            for name in OPTIONAL_ACCESSORS:
                if hasattr(sector, name):
                    self.assertTrue(callable(getattr(sector, name)),
                                    "%s.%s is not callable" % (sector.NAME, name))

    def test_the_closure_channel_stays_off_the_engine(self):
        """Power's plant-side closure and implied CV are DIAGNOSTIC accessors,
        reached through registry.diagnostics(); putting them on the engine
        would put an evidence class on the emissions path the isolation
        guards keep it off."""
        power = registry.get("power")
        self.assertFalse(hasattr(power, "gas_bridge"))
        self.assertFalse(hasattr(power, "coal_energy_restatement"))
        diag = registry.diagnostics("power")
        self.assertTrue(callable(diag.gas_bridge) and callable(diag.coal_energy_restatement))
        with self.assertRaises(KeyError):
            registry.diagnostics("waste")

    def test_the_gas_ledger_sectors_export_gas_activity(self):
        """The national gas ledger reaches three sectors by this name; losing
        one would silently drop a live throughput row."""
        for name in ("industry", "residential", "transport"):
            self.assertTrue(callable(getattr(registry.get(name), "gas_activity", None)), name)

    def test_the_report_layer_imports_no_sector_module_at_import_time(self):
        """rc34: importing a report module must not drag sector code - the
        three module-level offenders were made lazy."""
        import glob
        here = os.path.join(os.path.dirname(__file__), "..", "src", "pkinv", "report")
        offenders = []
        for path in sorted(glob.glob(os.path.join(here, "*.py"))):
            for line in open(path, encoding="utf-8"):
                if line.startswith(("from pkinv.sectors", "import pkinv.sectors")):
                    offenders.append(os.path.basename(path))
                    break
        self.assertEqual(offenders, [])

    def test_the_four_routed_reports_import_no_sector_module(self):
        here = os.path.join(os.path.dirname(__file__), "..", "src", "pkinv", "report")
        for name in ("longitudinal_uncertainty", "gas_closure",
                     "structural_trajectories", "annual_product"):
            text = open(os.path.join(here, name + ".py"), encoding="utf-8").read()
            self.assertNotIn("pkinv.sectors", text, name)

class TestSectorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sectors = registry.all_sectors()
        cls.built = {s.NAME: _build(s) for s in cls.sectors}

    def test_declared_attributes(self):
        for s in self.sectors:
            with self.subTest(sector=s.NAME):
                self.assertTrue(s.NAME and isinstance(s.NAME, str))
                self.assertIsInstance(s.CATEGORIES, tuple)
                self.assertTrue(s.CATEGORIES)
                self.assertEqual(len(set(s.CATEGORIES)), len(s.CATEGORIES))
                self.assertIsInstance(s.GASES, tuple)
                self.assertIsInstance(s.HAS_SINKS, bool)   # not merely truthy
                self.assertIsInstance(s.YEAR, int)

    def test_every_sector_declares_a_real_reference_period(self):
        """An integer year is not a period, and this one carried three meanings.

        Power and aviation used YEAR for the fiscal year OPENING in it; six sectors used it
        for the year CLOSING in it; waste used a calendar year; and agriculture - the largest
        sector - used it for a fiscal year opening in it, so 2024 meant FY2024-25 there and
        FY2023-24 in six other places. Nothing could see any of that, and the national
        manuscript ended up contradicting its own results table about which year the power
        sector reported.

        The dates are re-derived from the year and the declared convention, so a sector
        cannot declare a period its own year does not support.
        """
        for s in self.sectors:
            with self.subTest(sector=s.NAME):
                self.assertIn(s.YEAR_CONVENTION, period.CONVENTIONS)
                self.assertIsInstance(s.PERIOD_START, datetime.date)
                self.assertIsInstance(s.PERIOD_END, datetime.date)
                self.assertGreater(s.PERIOD_END, s.PERIOD_START)
                self.assertEqual(period.span_months(s.PERIOD_START, s.PERIOD_END), 12,
                                 "a reference period is twelve months")
                self.assertEqual((s.PERIOD_START, s.PERIOD_END),
                                 period.from_year(s.YEAR, s.YEAR_CONVENTION),
                                 "the declared period contradicts the declared year")

    def test_period_kinds_are_from_the_shared_vocabulary(self):
        """A row may say its activity is a counted stock rather than a flow; it may not
        invent a third thing."""
        for name, (_data, comps) in self.built.items():
            for c in comps:
                kind = c.get("activity_period_kind")
                if kind is not None:
                    self.assertIn(kind, period.PERIOD_KINDS, "%s: %r" % (name, kind))

    def test_the_livestock_categories_are_declared_enumerations(self):
        """The specific case the kind exists for. Enteric fermentation is the largest
        category in the inventory and rides a census count, not twelve months of activity;
        if it ever silently became a span, the monthly layer would be entitled to spread it
        over a seasonal profile it has no basis for."""
        _data, agri = self.built["agriculture"]
        enumerated = {c["category"] for c in agri
                      if c.get("activity_period_kind") == "enumeration"}
        self.assertEqual(enumerated, set(registry.get("agriculture").ENUMERATED_CATEGORIES))

    def test_row_shape(self):
        """No missing keys, and no unexpected ones either -- a sector inventing an
        'activity' column would otherwise ship something nothing downstream consumes."""
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            with self.subTest(sector=s.NAME):
                self.assertTrue(comps)
                for c in comps:
                    self.assertTrue(REQUIRED_KEYS <= set(c), "missing: %s" % (REQUIRED_KEYS - set(c)))
                    self.assertTrue(set(c) <= ALL_KEYS, "unexpected: %s" % (set(c) - ALL_KEYS))
                    self.assertIn(c["category"], s.CATEGORIES)
                    self.assertIn(c["gas"], s.GASES)
                    self.assertTrue(math.isfinite(c["emissions_Gg"]))
                    self.assertTrue(math.isfinite(c["uncert_pct"]) and c["uncert_pct"] >= 0)

    def test_metadata_classes_are_valid_where_present(self):
        """The evidence/temporal/spatial classes are optional while sectors adopt them,
        but a row that declares one must declare a real one.

        Silence is honest; a made-up class is not. This is the check that lets the keys
        stay optional without the vocabulary rotting - a typo'd "T5" or a sector inventing
        its own letter fails here rather than propagating into a published dataset that
        claims to say how well supported it is.
        """
        from pkinv.core import evidence
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            with self.subTest(sector=s.NAME):
                for c in comps:
                    bad = evidence.validate(c)
                    self.assertFalse(bad, "invalid metadata class on %s/%s: %s"
                                     % (c["category"], c["subitem"], bad))

    def test_every_row_is_classified_on_all_three_axes(self):
        """The migration is over: every sector, every row, every axis.

        This began as an all-or-nothing-per-sector rule with an ADOPTED ledger, because a
        half-classified sector is worse than an unclassified one - summarise() would report the
        classified fraction as if it were the sector. That was the right shape while ten
        modules adopted one at a time and the wrong shape once eight had not: a migration
        ledger with two entries in it is a record of the migration not happening.

        The classes are REQUIRED_KEYS now, so a missing one fails test_row_shape as well; this
        asserts the stronger thing, that each value is in its vocabulary.
        """
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            for c in comps:
                bad = evidence.validate(c)
                with self.subTest(sector=s.NAME, subitem=c["subitem"]):
                    self.assertFalse(bad, "%s/%s carries %s" % (s.NAME, c["subitem"], bad))
                    for key in ("evidence_class", "temporal_method", "spatial_method"):
                        self.assertTrue(c.get(key),
                                        "%s/%s has no %s" % (s.NAME, c["subitem"], key))

    def test_a_stock_is_never_reported_as_a_flow(self):
        """activity_period_kind must be one of the two the period contract defines, and the
        categories that ride a census enumeration must say so - the monthly layer spreads a
        span across twelve months and must not do that to a stock counted once."""
        from pkinv.core.period import PERIOD_KINDS
        enumerated = set()
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            for c in comps:
                self.assertIn(c["activity_period_kind"], PERIOD_KINDS,
                              "%s/%s" % (s.NAME, c["subitem"]))
                if c["activity_period_kind"] == "enumeration":
                    enumerated.add(c["category"])
        self.assertTrue(enumerated,
                        "no category is an enumeration - the livestock census rows have "
                        "stopped declaring themselves a stock")

    def test_every_source_id_resolves_in_the_source_key_register(self):
        """A stable key that resolves nowhere is a label.

        source_id was carried for a round before anything could look one up: the register of
        source DOCUMENTS is keyed by activity file, and no file knew which emission streams
        read it. data/source_keys.csv is the join, and both directions are asserted - an
        unused key is as much a defect as an unresolvable one, because it means a stream was
        renamed and its evidence quietly stopped being named.
        """
        import csv as _csv
        with open(asset_path(ROOT, "data", "source_keys.csv"), encoding="utf-8") as handle:
            rows = list(_csv.DictReader(l for l in handle if not l.startswith("#")))
        declared = {r["source_id"] for r in rows}
        files = {r["data_file"] for r in rows}
        with open(asset_path(ROOT, "data", "source_documents.csv"), encoding="utf-8") as h:
            registered = {r["data_file"] for r in _csv.DictReader(h)}
        self.assertFalse(sorted(files - registered),
                         "source_keys names activity files the source register does not: %s"
                         % sorted(files - registered))
        used = set()
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            used.update(c["source_id"] for c in comps)
        component_keys = {r["source_id"] for r in rows
                          if r.get("cited_by", "components") == "components"}
        self.assertFalse(sorted(used - declared),
                         "component rows cite source keys that resolve nowhere: %s"
                         % sorted(used - declared))
        self.assertFalse(sorted(component_keys - used),
                         "source_keys declares keys nothing cites: %s"
                         % sorted(component_keys - used))
        # A key may back a RECONCILIATION product rather than an emission stream - the
        # NFDC fertilizer registers feed the ammonia activity reconciliation, which is
        # deliberately outside the inventory total until its tier gate clears. Such a key
        # declares its consumer by name, and the consumer must exist: a key pointing at a
        # product nobody wrote is the same defect as a key nothing cites, one level up.
        for r in rows:
            consumer = r.get("cited_by", "components")
            if consumer.startswith("reconciliation:"):
                out = consumer.split(":", 1)[1]
                self.assertTrue(
                    os.path.exists(os.path.join(ROOT, "outputs", out)),
                    "%s says it is cited by %s, which does not exist"
                    % (r["source_id"], out))

    def test_every_declared_category_is_emitted(self):
        """A category declared but never emitted puts a phantom 0.00 row in the national
        table and a zero-width band in the Monte Carlo."""
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            emitted = {c["category"] for c in comps}
            with self.subTest(sector=s.NAME):
                self.assertEqual(set(s.CATEGORIES) - emitted, set())

    def test_category_subitem_is_unique(self):
        """(category, subitem) is a primary key: ten-plus modules match on it by exact
        string or substring, so a duplicate silently double-counts in every one."""
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            keys = [(c["category"], c["subitem"]) for c in comps]
            with self.subTest(sector=s.NAME):
                dupes = {k for k in keys if keys.count(k) > 1}
                self.assertEqual(dupes, set(), "duplicate (category, subitem): %s" % dupes)

    def test_correlation_groups_stay_within_one_category(self):
        """combine_sum groups across the whole component list, so a group spanning two
        categories would correlate across the boundary and shrink national uncertainty."""
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            by_group = {}
            for c in comps:
                g = c.get("corr_group")
                if g is not None:
                    self.assertTrue(g and isinstance(g, str))
                    by_group.setdefault(g, set()).add(c["category"])
            with self.subTest(sector=s.NAME):
                for g, cats in by_group.items():
                    self.assertEqual(len(cats), 1, "corr_group %r spans %s" % (g, cats))

    def test_signs_match_the_declared_sink_flag(self):
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            negatives = [c for c in comps if c["co2e_Mt_AR5"] < 0]
            with self.subTest(sector=s.NAME):
                if s.HAS_SINKS:
                    self.assertTrue(negatives, "HAS_SINKS but no component is negative")
                else:
                    self.assertEqual(negatives, [], "negative component in a no-sink sector")

    def test_gases_are_known_to_gwp(self):
        """Fail at registration rather than KeyError-ing partway through a run."""
        for s in self.sectors:
            with self.subTest(sector=s.NAME):
                for ar in ("AR5", "AR6"):
                    self.assertTrue(set(s.GASES) <= set(gwp.GWP[ar]),
                                    "unknown to %s: %s" % (ar, set(s.GASES) - set(gwp.GWP[ar])))

    def test_co2e_is_exactly_the_gwp_conversion(self):
        """Exact ==, not almost-equal: the pipeline claims determinism, so pin it."""
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            with self.subTest(sector=s.NAME):
                for c in comps:
                    fossil = c.get("fossil", False)
                    for ar in ("AR5", "AR6"):
                        self.assertEqual(
                            c["co2e_Mt_" + ar],
                            gwp.to_co2e(c["gas"], c["emissions_Gg"], ar, fossil) / 1000.0)

    def test_build_is_deterministic(self):
        """The whole `git diff outputs/` regression check rests on this property."""
        for s in self.sectors:
            _, first = self.built[s.NAME]
            _, second = _build(s)
            with self.subTest(sector=s.NAME):
                self.assertEqual([(c["category"], c["subitem"], c["gas"]) for c in first],
                                 [(c["category"], c["subitem"], c["gas"]) for c in second])
                self.assertEqual([c["emissions_Gg"] for c in first],
                                 [c["emissions_Gg"] for c in second])

    def test_proxy_resolves_for_every_component(self):
        for s in self.sectors:
            _, comps = self.built[s.NAME]
            shares = s.load_shares()
            with self.subTest(sector=s.NAME):
                for c in comps:
                    self.assertIn(s.proxy_for(c), shares)

    def test_proxy_raises_on_an_unknown_category(self):
        """A silent default would misallocate a whole category between provinces while
        leaving the national total identical -- invisible in national_totals_2024.csv."""
        for s in self.sectors:
            with self.subTest(sector=s.NAME):
                with self.assertRaises(KeyError):
                    s.proxy_for({"category": "No Such Category", "subitem": "x"})


class TestYearsFailLoudly(unittest.TestCase):
    """A sector asked for a year it cannot support must RAISE, never return a number.

    Three sectors did the opposite, and all three returned figures a reader would have
    accepted: waste at 2024 gave 8.9 Mt instead of ~37 because its population panel ran
    out and burning and disposal collapsed to nearly zero; power gave 5.6 instead of 63.6
    because grid combustion zeroed while captive generation - which took no year argument
    at all - carried on; industry returned exactly 0.0 for every year but one, which is
    indistinguishable from a sector that genuinely emits nothing.

    None raised. None warned. Each is the shape of error this inventory is least able to
    catch by inspection, and the multi-year work now beginning would have walked straight
    into all three on its first loop. This test is the guard, and it is deliberately
    registry-driven so a new sector is covered the day it registers.

    The band is wide on purpose. It is not asserting that a sector's history is smooth -
    demand really does move - only that a year either produces something of the right order
    or fails. A tenfold collapse is not a trend.
    """

    SPAN = range(2015, 2027)
    LO, HI = 0.1, 10.0        # multiples of the sector's own reference-year total

    def test_every_sector_either_computes_or_raises(self):
        """THE BASELINE IS THE SECTOR'S OWN REFERENCE BUILD, NOT A YEAR-PASSED CALL.

        This test used to compute `reference` through `build_components(data, sector.YEAR)` --
        the same call it was probing. Agriculture's signature was `(data, *args, **kwargs)`
        forwarding into `run_inventory.build_components(data, ef1_override=None)`, so the year
        became an emission factor and the reference became 4,819,139 Mt against a published
        223.26. The acceptance band is a multiple of the reference, so it widened by the same
        factor and every probe year landed inside it. The check ran, examined the sector, and
        passed on a number twenty-one thousand times too large: the defect it hunts also
        corrupted the yardstick it measured against.

        Taking the baseline from the no-argument build removes that coupling. And "accepted the
        year and returned nonsense" is now reported separately from "raised", because the old
        `except TypeError: continue` silently excused the one sector that did neither.
        """
        from pkinv.core import registry
        problems = []
        for sector in registry.all_sectors():
            data = sector.load_data()
            reference = sum(c["co2e_Mt_AR5"] for c in sector.build_components(data))
            if reference <= 0:
                continue
            for year in self.SPAN:
                try:
                    total = sum(c["co2e_Mt_AR5"]
                                for c in self._build(sector, data, year))
                except TypeError:
                    break         # takes no year at all; covered by its own sector tests
                except Exception:
                    continue      # refusing a year it cannot support is always acceptable
                if not (self.LO * reference <= total <= self.HI * reference):
                    problems.append(
                        "%s at %d returned %.3f Mt against its own reference build of %.3f - "
                        "it should raise instead of returning a wrong number"
                        % (sector.NAME, year, total, reference))
        self.assertFalse(problems, "silent year failures:\n  " + "\n  ".join(problems))


class TestRegistry(unittest.TestCase):
    def test_sector_names_are_unique(self):
        names = [s.NAME for s in registry.all_sectors()]
        self.assertEqual(len(set(names)), len(names))

    def test_category_names_are_globally_unique(self):
        """key_categories, completeness and the dashboard pool every sector into one
        category namespace, so two sectors both naming a category would silently merge."""
        seen = {}
        for s in registry.all_sectors():
            for cat in s.CATEGORIES:
                self.assertNotIn(cat, seen,
                                 "%r declared by both %s and %s" % (cat, seen.get(cat), s.NAME))
                seen[cat] = s.NAME


class TestCoreMonteCarloSinks(unittest.TestCase):
    """The sink branch, proven on a fixture rather than on a registered sector.

    LULUCF would be the obvious second client -- it is already in the repo and genuinely
    has sinks -- but the paper's Supplementary Note S1 scopes it as exploratory Tier 1 and
    excludes it from every total, benchmark, key-category analysis and uncertainty
    estimate, noting that both its magnitude and its sign are uncertain and that it still
    needs an uncertainty of its own. Registering it would mean inventing that number, so
    the branch is exercised here instead until the science supplies one.
    """

    FIXTURE = [
        {"category": "Sink", "subitem": "forest", "gas": "CO2", "emissions_Gg": -1000.0,
         "uncert_pct": 30.0, "co2e_Mt_AR5": -1.0, "co2e_Mt_AR6": -1.0},
        {"category": "Source", "subitem": "x", "gas": "CO2", "emissions_Gg": 3000.0,
         "uncert_pct": 20.0, "co2e_Mt_AR5": 3.0, "co2e_Mt_AR6": 3.0},
    ]

    def test_sinks_keep_their_sign(self):
        from pkinv.core import montecarlo as mc
        stats, _ = mc.run(self.FIXTURE, ["Sink", "Source"], n_iter=500, seed=1, has_sinks=True)
        self.assertLess(stats["Sink"]["p50"], 0.0)
        self.assertGreater(stats["Source"]["p50"], 0.0)
        self.assertLess(stats["TOTAL"]["p50"], stats["Source"]["p50"])

    def test_without_the_flag_a_sink_is_dropped(self):
        """Documents why HAS_SINKS exists: the historic filter silently discards sinks,
        which would report a land sector's band on gross emissions."""
        from pkinv.core import montecarlo as mc
        stats, _ = mc.run(self.FIXTURE, ["Sink", "Source"], n_iter=200, seed=1, has_sinks=False)
        self.assertEqual(stats["Sink"]["p50"], 0.0)

    def test_copysign_is_a_no_op_for_positive_values(self):
        """Why agriculture's Monte-Carlo stream is unchanged by the sink branch."""
        import math
        for v in (1.0, 3.7, 221.22, 1e-9):
            self.assertEqual(math.copysign(abs(v) * math.exp(0.3), v), v * math.exp(0.3))


class TestAgricultureSpecifics(unittest.TestCase):
    """Sector-local invariants that are deliberately not part of the general contract."""

    def setUp(self):
        self.sector = registry.get("agriculture")
        self.data = self.sector.load_data()

    def test_all_methane_is_biogenic(self):
        """Enteric, manure, rice and residue burning are all biogenic, so agriculture
        never sets the fossil flag and AR6 CH4 stays at 27."""
        for c in self.sector.build_components(self.data):
            self.assertFalse(c.get("fossil", False),
                             "%s/%s claims fossil CH4" % (c["category"], c["subitem"]))

    def test_soils_receives_manure_nitrogen(self):
        """The manure -> npools -> soils ordering, asserted rather than assumed."""
        pools = self.sector.intermediates(self.data)["npools"]
        for key in ("FON_N", "FPRP_cattle_N", "FPRP_other_N"):
            self.assertGreater(pools[key], 0.0)

    def test_intermediates_are_not_cached(self):
        """timeseries._apply_year mutates data in place across 35 years on one object;
        a cache would leak one year's nitrogen into another."""
        before = self.sector.intermediates(self.data)["npools"]["excreted_N"]
        self.data.livestock["buffalo"]["head"] *= 2
        after = self.sector.intermediates(self.data)["npools"]["excreted_N"]
        self.assertNotEqual(after, before)


if __name__ == "__main__":
    unittest.main()
