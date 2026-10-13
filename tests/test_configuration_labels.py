"""A configuration's prose must not restate a number its own row already carries.

WHY THIS TEST EXISTS. outputs/national_configurations.csv gives each configuration a
`family_role` - a short phrase telling a reader what the member is and what its power figure
is. Those figures were typed into the label. The coal re-base moved the power account by
17.78 Mt and two of them did not move with it: the reference read "grid 57.82 Mt" where it
had become 40.04, and the K-Electric member "grid 61.83" where it had become 44.05. Each sat
beside the correct value, in `alternative_value_Mt`, in the same row.

No test could see it, because it is prose inside a data file: the numeric columns were right,
the identity held, the conservation checks passed, and the sentence a human reads was wrong.
The repair was to format the figure FROM the row, and this test holds that repair - and holds
the class, not the two instances. Any quantity a label states about its own configuration
must agree with the column that holds it.
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                     # noqa: E402

OUT = os.path.join(ROOT, "outputs", "national_configurations.csv")

# "grid 40.04 Mt", "sector 16.088" - a quantity a label asserts about its own row.
QUANTITY = re.compile(r"\b(grid|sector)\s+(\d+(?:\.\d+)?)")


class TestNoLabelRestatesItsOwnNumber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the configurations product is not built here")
        cls.rows = read_rows(OUT)

    def test_no_unfilled_template_reaches_a_reader(self):
        """The figures are substituted from the row. A placeholder that escaped the
        substitution would print literally, which is a defect this project has shipped
        before - a template variable reaching a reader is worse than a stale number,
        because it is obviously broken and still got published."""
        for row in self.rows:
            for field in ("family_role", "note"):
                self.assertNotIn("{", row.get(field) or "",
                                 "%s: %s carries an unfilled template"
                                 % (row["configuration_id"], field))

    def test_a_grid_figure_in_a_label_matches_its_own_row(self):
        """The guard that would have caught the 17.78 Mt staleness."""
        checked = 0
        for row in self.rows:
            role = row.get("family_role") or ""
            value = (row.get("alternative_value_Mt") or "").strip()
            if not value:
                continue
            for _word, printed in QUANTITY.findall(role):
                self.assertAlmostEqual(
                    float(printed), float(value), delta=0.01,
                    msg="%s: the label says %s while alternative_value_Mt is %s. A label "
                        "that restates its row's own number goes stale the moment that "
                        "number moves - format it from the row instead of typing it."
                        % (row["configuration_id"], printed, value))
                checked += 1
        self.assertGreater(checked, 0,
                           "no label states a quantity about its own row any more. If the "
                           "labels stopped carrying figures that is an improvement, but "
                           "this test is then checking nothing and should be retired "
                           "rather than left passing vacuously.")

    def test_the_reference_row_states_the_booked_power_figure(self):
        """The reference carries no alternative_value_Mt of its own - it IS the baseline -
        so its label's figure is derived from the legacy control's value less that
        control's delta. It must equal the booked grid total, not the superseded one."""
        rows = {r["configuration_id"]: r for r in self.rows}
        reference = rows.get("inventory_reference")
        legacy = rows.get("power_table3_legacy_control")
        if not reference or not legacy:
            self.skipTest("the power control family is not in this build")
        printed = QUANTITY.findall(reference.get("family_role") or "")
        self.assertTrue(printed,
                        "the reference's role no longer states its grid figure; a reader "
                        "comparing the family's members has nothing to compare the "
                        "alternatives against")
        expected = (float(legacy["alternative_value_Mt"])
                    - float(legacy["national_delta_Mt"]))
        self.assertAlmostEqual(float(printed[0][1]), expected, delta=0.01,
                               msg="the reference's label says %s; the legacy control's "
                                   "own value less its own delta is %.5f. These disagree "
                                   "only if one of them predates the coal re-base."
                                   % (printed[0][1], expected))

    def test_the_legacy_control_is_marked_not_preferred(self):
        """It reproduces the total every release before the re-base published, so a reader
        can land on it by searching for that number. The row has to say what it is."""
        rows = {r["configuration_id"]: r for r in self.rows}
        legacy = rows.get("power_table3_legacy_control")
        if not legacy:
            self.skipTest("the legacy control is not in this build")
        role = legacy["family_role"]
        self.assertIn("LEGACY PUBLISHED CONTROL", role)
        self.assertIn("not preferred", role)


if __name__ == "__main__":
    unittest.main()
