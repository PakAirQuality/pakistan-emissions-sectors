"""Every build phase says what kind of work it is, and the build groups follow the kinds.

WHY (rc69). The development group used to be "every phase except eleven labels", written
when those eleven were all the finalisation there was. Five figure and verification stages
added later - the v3 tables and charts, the gridded figures, the integrated figures and their
check, the sector-note TeX - were not on the list, so every `make dev` rendered the papers'
figures. A list of exclusions fails silently for whatever it did not foresee. The registry
now carries a closed category per phase, with no default, and these tests hold the groups
to it.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv import build, run_all                                       # noqa: E402

KINDS = ("science", "validation", "figures", "release")


class TestEveryPhaseHasAKind(unittest.TestCase):
    def test_the_vocabulary_is_closed_and_every_phase_is_listed_once(self):
        self.assertEqual(tuple(run_all.CATEGORIES), KINDS)
        listed = [l for labels in run_all.CATEGORIES.values() for l in labels]
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(sorted(listed), sorted(p.label for p in run_all.PHASES))
        for phase in run_all.PHASES:
            self.assertIn(phase.category, KINDS, phase.label)

    def test_an_unlisted_phase_stops_the_registry(self):
        stray = run_all.Phase("A phase nobody classified", "scripts/x.py", writes=("x",))
        with self.assertRaises(ValueError):
            run_all._with_categories(list(run_all.PHASES) + [stray])

    def test_a_figures_phase_writes_only_presentation(self):
        allowed = ("outputs/figures/", "outputs/dashboard.html")
        for phase in run_all.PHASES:
            if phase.category == "figures":
                for path in phase.writes:
                    self.assertTrue(path.startswith(allowed), "%s writes %s" % (phase.label, path))


class TestTheGroupsFollowTheKinds(unittest.TestCase):
    def test_dev_builds_science_and_validation_only(self):
        dev = build.phases_for_group("dev")
        self.assertEqual({p.category for p in dev}, {"science", "validation"})
        self.assertEqual(len(dev), sum(1 for p in run_all.PHASES
                                       if p.category in ("science", "validation")
                                       and not p.network))

    def test_no_figure_stage_is_in_dev(self):
        labels = {p.label for p in build.phases_for_group("dev")}
        for label in ("Inventory figures", "Dashboard"):
            self.assertNotIn(label, labels)

    def test_the_figures_group_is_the_figures_kind(self):
        self.assertEqual([p.label for p in build.phases_for_group("figures")],
                         [p.label for p in run_all.PHASES if p.category == "figures"])

    def test_no_development_phase_reads_a_later_kind_except_by_design(self):
        """A dev phase that read a figures or release product would read a stale copy.
        The only such reads are declared prior: (the previous release's artefact)."""
        later = {}
        for phase in run_all.PHASES:
            if phase.category in ("figures", "release"):
                for path in phase.writes:
                    later[path] = phase.label
        for phase in build.phases_for_group("dev"):
            for read in phase.reads or ():
                if read.startswith("prior:"):
                    continue
                path = read.split(":", 1)[-1]
                for written, label in later.items():
                    hit = path == written or (written.endswith("/") and path.startswith(written))
                    self.assertFalse(hit, "%s reads %s, written by %s" % (phase.label, read, label))

    def test_finalization_is_derived_from_the_kinds(self):
        self.assertEqual(build.FINALIZATION,
                         {p.label for p in run_all.PHASES
                          if p.category in ("figures", "release")})


class TestTheUncertaintyPairRunsSideBySide(unittest.TestCase):
    """rc69: the two conditional-uncertainty phases cost about 640 s of a cold build. They are
    audited and adjacent so the scheduler can batch them; a reorder or a lost flag would put
    them back in series without any test noticing the time."""

    PAIR = ("GHG conditional uncertainty", "Air conditional uncertainty")

    def test_both_are_audited_adjacent_and_write_disjoint_files(self):
        labels = [p.label for p in run_all.PHASES]
        first, second = (labels.index(l) for l in self.PAIR)
        self.assertEqual(second, first + 1)
        a, b = (run_all.PHASES[i] for i in (first, second))
        self.assertTrue(a.audited and b.audited)
        self.assertFalse(set(a.writes) & set(b.writes))
        self.assertFalse(set(a.writes) & set(b.reads or ()))
        self.assertFalse(set(b.writes) & set(a.reads or ()))


if __name__ == "__main__":
    unittest.main()
