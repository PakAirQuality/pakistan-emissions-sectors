"""The build's declared dependencies agree with its list order.

run_all.PHASES is an explicit list, ordered by position, with the reasons for
that order living in comments for years - and the two incidents this guards
against (the annual product built before the series it validates against, the
product-facts registry publishing the PREVIOUS run's artefact count because it
ran before the inventory it reads) were each a comment that stopped being
true. Phases now DECLARE what they read and write, and check_order() fails
when the declarations contradict the order.

The declarations are a tri-state on purpose: reads=None means "not audited",
never "no dependencies". The floor test keeps the audited set from decaying.
"""
import dataclasses
import os
import sys
import unittest


from pkinv import run_all
from pkinv.run_all import Phase, check_order
from _support import ROOT


def _labels():
    return [p.label for p in run_all.PHASES]


class TestTheRealBuildIsConsistent(unittest.TestCase):
    def test_no_declared_read_precedes_its_writer(self):
        self.assertEqual(check_order(run_all.PHASES), [])

    def test_every_phase_has_a_key_output(self):
        for p in run_all.PHASES:
            self.assertTrue(p.writes, p.label)
            self.assertTrue(p.key_output.startswith(("outputs/", "data/", "paper_national/")),
                            p.label)

    def test_labels_are_unique_and_the_flags_are_where_the_side_tuples_were(self):
        labels = _labels()
        self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual([p.label for p in run_all.PHASES if p.network],
                         [])
        self.assertEqual([p.label for p in run_all.PHASES if p.prints_only],
                         ["Waste air pollutants", "Transport air pollutants",
                          "Residential air pollutants", "Railways air pollutants",
                          "Aviation air pollutants"])
        # rc41: the ADM2 registry phase rewrites only what differs (a rerun is byte-identical
        # and touches nothing), so like the figure sync it is checked for existence only
        self.assertEqual([p.label for p in run_all.PHASES if p.idempotent],
                         ["ADM2 reporting units", "Residential own-year degree-days",
                          "Compatibility input views", "Canonical activity tables",
                          "Semantic release", "Sync paper figures"])


class TestTheCheckerCatchesSabotage(unittest.TestCase):
    """Three in-memory mutations of PHASES, each caught by the rule's name.
    Nothing on disk is touched - PHASES is data."""

    def _mutate(self, label, **changes):
        return [dataclasses.replace(p, **changes) if p.label == label else p
                for p in run_all.PHASES]

    def test_a_read_nothing_writes_is_rule_one(self):
        phases = self._mutate("National rollup", reads=("outputs/never_written.csv",))
        problems = check_order(phases)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("rule 1", problems[0])
        self.assertIn("no phase writes", problems[0])

    def test_a_read_a_later_phase_writes_is_rule_one_and_names_it(self):
        """Reorder: the ensemble before the cube whose provincial check it
        reads - the exact edge the rc32 comment guarded in prose."""
        phases = list(run_all.PHASES)
        cube = next(i for i, p in enumerate(phases) if p.label == "Gridded monthly cube")
        ens = next(i for i, p in enumerate(phases) if p.label == "Common draw ensemble")
        self.assertLess(cube, ens)
        phases[cube], phases[ens] = phases[ens], phases[cube]
        problems = [m for m in check_order(phases) if "Common draw ensemble" in m]
        self.assertTrue(problems, "the checker did not notice the ensemble ran before the cube")
        self.assertTrue(all("rule 1" in m and "LATER phase writes" in m for m in problems),
                        problems)

    def test_a_glob_matching_nothing_is_rule_two(self):
        phases = self._mutate("National uncertainty", reads=("glob:outputs/*no_such_thing*",))
        problems = check_order(phases)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("rule 2", problems[0])

    def test_two_producers_is_rule_three(self):
        phases = self._mutate("National key categories",
                              writes=("outputs/national_key_categories.csv",
                                      "outputs/national_all_sectors.csv"))
        problems = check_order(phases)
        self.assertTrue(any("rule 3" in m for m in problems), problems)


class TestTheDeclaredSetDoesNotDecay(unittest.TestCase):
    FLOOR = 20

    def test_at_least_the_audited_edges_are_declared(self):
        declared = [p.label for p in run_all.PHASES if p.reads is not None]
        self.assertGreaterEqual(len(declared), self.FLOOR,
                                "phases with declared reads fell to %d; a declaration was "
                                "deleted instead of corrected" % len(declared))

    def test_an_undeclared_phase_is_none_not_empty(self):
        """A phase nobody audited must say so (None), not claim independence (())."""
        p = Phase("x", "pkinv.nothing", writes=("outputs/x.csv",))
        self.assertIsNone(p.reads)


if __name__ == "__main__":
    unittest.main()
