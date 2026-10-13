"""The forest-land screening: the two accounts disagree on the SIGN, and nothing enters a total.

WHY THIS EXISTS (T-LAND-2). The land lane established that no official land SERIES exists to
import, so the question became which land component could be built reproducibly. The answer is
none yet, and the reason is the thing worth guarding: Pakistan's own submission books forest
land as a SOURCE of +28.44 Mt CO2 and FAOSTAT books it as a SINK of -4.107 Mt in the same
year. They do not differ by a factor or a vintage; they differ in direction, over a gap of
about seven per cent of the national total.

Two properties have to hold for the screening to mean anything.

FIRST, IT MUST STAY OUTSIDE THE INVENTORY. LULUCF is excluded by declared scope, and a
screening that leaked into a total would move a pin by the back door. No test can prove a
negative about every consumer, so this asserts the narrower thing it can: the product carries
no column a total is built from, and the national pins are untouched by its existence.

SECOND, THE DIAGNOSTIC MUST KEEP SAYING WHAT IT SAYS. FAOSTAT's area series rises at exactly
+20.786 kha a year for 2020 through 2023 - constant to three decimals, which is interpolation
between FRA anchors rather than observation - and its net forest conversion is exactly zero
from 2020. If FAOSTAT ever publishes a series that varies, the only annual source available
starts carrying annual information and the blocker changes shape. That should surface here
rather than in a reader's arithmetic.

Run:  python3 -m unittest discover tests -p "test_forest_flux_adjudication.py"
"""
import csv
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(ROOT, "outputs", "pakemis_forest_flux_adjudication.csv")


def _rows():
    with io.open(OUT, encoding="utf-8") as handle:
        lines = [l for l in handle.read().split("\n") if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


class TestTheScreening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the forest screening has not been generated here")
        cls.rows = _rows()

    def test_the_two_accounts_still_disagree_on_the_sign(self):
        """The finding. If they ever agree, a component becomes buildable and this says so."""
        sub = [r for r in self.rows
               if r["account"].startswith("Pakistan") and r["quantity"] == "forest land flux"]
        fao = [r for r in self.rows
               if r["account"] == "FAOSTAT" and r["quantity"] == "forest land flux"
               and r["period"] == "CY2020"]
        self.assertTrue(sub and fao, "both accounts must be present to compare")
        a, b = float(sub[0]["value"]), float(fao[0]["value"])
        self.assertLess(
            a * b, 0.0,
            "the submission (%.2f) and FAOSTAT (%.2f) no longer disagree in SIGN. That is a "
            "material change: the screening's whole finding is that a forest component cannot "
            "be built while they point in opposite directions, and if they now agree the "
            "blocker should be re-stated rather than this test relaxed." % (a, b))

    def test_the_faostat_annual_series_is_still_interpolation(self):
        """A constant step is the evidence that the only annual source has no annual content."""
        step = [r for r in self.rows if r["quantity"].startswith("FAOSTAT area step")]
        self.assertTrue(step, "the area-step diagnostic is gone")
        values = [float(v) for v in step[0]["value"].split("/")]
        self.assertGreater(len(values), 2, "fewer than three steps to compare")
        self.assertEqual(
            len(set(values)), 1,
            "FAOSTAT's forest-area steps now differ (%s). If the series has started carrying "
            "annual information the screening's second finding has changed and the note must "
            "change with it." % values)

    def test_nothing_here_is_a_total_column(self):
        """The scope guarantee this product can actually assert about itself."""
        measures = {"co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"}
        self.assertFalse(
            measures & set(self.rows[0]),
            "the screening has grown a column a national total is summed from; LULUCF is "
            "outside the reported boundary and this product must stay a screening")
        # Every row declares a sign convention, and the conventions themselves are a
        # published list rather than a word test. The first attempt whitelisted the
        # opening word, which read as a rule but was only this file's vocabulary: it
        # passed "positive is a SOURCE" and rejected "gains are removals, losses are
        # emissions", which is the CRT's own wording and a perfectly stated convention.
        # A new convention must now be added here on purpose.
        declared = {
            "positive is a SOURCE",
            "negative is a SINK",
            "n.a.",
            "gains are removals, losses are emissions",
            "above 1 means forest is being LOST",
            "positive is forest GAIN",
            "the submission minus FAOSTAT",
        }
        seen = set()
        for row in self.rows:
            stated = row["sign_meaning"].strip()
            self.assertTrue(stated,
                            "%s states no sign convention; a land flux without one is "
                            "unusable" % row["quantity"])
            seen.add(stated)
        self.assertEqual(seen - declared, set(),
                         "undeclared sign convention(s) %s - add them above with intent"
                         % sorted(seen - declared))
        self.assertEqual(declared - seen, set(),
                         "declared sign convention(s) %s no longer appear; a stale "
                         "allowance hides the next one" % sorted(declared - seen))

    def test_every_row_cites_where_it_came_from(self):
        for row in self.rows:
            self.assertTrue(row["source"].strip(),
                            "%s / %s cites no source" % (row["account"], row["quantity"]))

    def test_it_regenerates_identically(self):
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "scripts",
                                         "build_forest_flux_adjudication.py"), "--check"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0,
                         "the forest screening is stale; run make forest-flux.\n%s%s"
                         % (r.stdout, r.stderr))


if __name__ == "__main__":
    unittest.main()
