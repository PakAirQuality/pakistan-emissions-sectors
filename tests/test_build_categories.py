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

KINDS = ("science", "validation", "manuscript", "release")


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

    def test_a_manuscript_phase_writes_only_presentation(self):
        allowed = ("paper_national/", "papers/", "paper_common/", "outputs/figures/",
                   "outputs/paper_figure_data/",
                   "outputs/paper_figures/", "outputs/dashboard.html",
                   "outputs/pakemis_paper_artefact_hashes.csv",
                   "outputs/pakemis_sector_note_facts.csv")
        for phase in run_all.PHASES:
            if phase.category == "manuscript":
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
        for label in ("Manuscript figures, v3 (tables and charts)", "Gridded figures",
                      "Integrated GHG and air manuscript figures",
                      "Integrated manuscript figure verification", "Sector technical-note facts"):
            self.assertNotIn(label, labels)

    def test_the_manuscript_group_is_the_manuscript_kind(self):
        self.assertEqual([p.label for p in build.phases_for_group("manuscript")],
                         [p.label for p in run_all.PHASES if p.category == "manuscript"])

    def test_no_development_phase_reads_a_later_kind_except_by_design(self):
        """A dev phase that read a manuscript or release product would read a stale copy.
        The only such reads are declared prior: (the previous release's artefact)."""
        later = {}
        for phase in run_all.PHASES:
            if phase.category in ("manuscript", "release"):
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
                          if p.category in ("manuscript", "release")})


if __name__ == "__main__":
    unittest.main()
