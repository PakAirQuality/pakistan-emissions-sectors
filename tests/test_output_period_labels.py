"""An output that names a fiscal year must name its own.

THE DEFECT. The transport fuel ledger described its control rows as "OCAC Sectoral Sales
FY2021-22, TOTAL INTERNAL row" for a full release after the sector moved to FY2023-24. The
numbers were current; only the label was two years behind. Nothing could see it: every value
test compares numbers, and this was a string.

A basis that names the wrong year is worse than no basis at all, because it is checkable and
wrong - a reader who goes to the FY2021-22 OCAC table to verify the row will find a different
number and conclude the inventory is broken.

THE RULE, and why it is scoped the way it is. A `basis` column says what a row was computed
FROM, so a fiscal year in it is a claim about this run and must match the sector's reporting
period. A `note` column is prose and legitimately refers to other years - the year-matched
railway cross-check against a historical row, a demand collapse in a neighbouring year, a
superseded edition quoted as history - so notes are not checked here. That is the line
between a provenance claim and a discussion.
"""
import csv
import glob
import os
import re
import sys
import unittest


from pkinv.core import period, registry   # noqa: E402
from _support import OUT, ROOT

FISCAL = re.compile(r"FY\d{4}-\d{2}")


def _sector_labels():
    """{sector name: its reporting-period label}."""
    return {s.NAME: period.label(s.PERIOD_START, s.PERIOD_END)
            for s in registry.all_sectors()}


class TestBasisColumnsNameTheReportingPeriod(unittest.TestCase):

    def test_every_basis_that_names_a_year_names_the_right_one(self):
        labels = _sector_labels()
        offenders, checked = [], 0
        for path in sorted(glob.glob(os.path.join(OUT, "*.csv"))):
            name = os.path.basename(path)
            sector = next((s for s in labels if name.startswith(s + "_")), None)
            if sector is None:
                continue
            with open(path, newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or "basis" not in reader.fieldnames:
                    continue
                for row in reader:
                    basis = row.get("basis") or ""
                    for found in FISCAL.findall(basis):
                        checked += 1
                        if found != labels[sector]:
                            offenders.append(
                                "%s: a basis says %s, but %s reports %s\n      %s"
                                % (name, found, sector, labels[sector], basis[:110]))
        self.assertGreater(checked, 0,
                           "no basis column names a fiscal year at all - either the outputs "
                           "have moved or this check has stopped reading them")
        self.assertFalse(offenders,
                         "these outputs describe their own run with the wrong year:\n  "
                         + "\n  ".join(offenders))

    def test_the_check_would_catch_the_defect_it_was_written_for(self):
        """A guard that cannot fail is not a guard. This proves the matcher rejects the exact
        string that shipped, rather than trusting that it would."""
        labels = _sector_labels()
        shipped = ("OCAC Sectoral Sales FY2021-22, TOTAL INTERNAL row "
                   "(data/activity/transport/ocac_sectoral_annual.csv)")
        found = FISCAL.findall(shipped)
        self.assertEqual(found, ["FY2021-22"])
        self.assertNotEqual(found[0], labels["transport"])


if __name__ == "__main__":
    unittest.main()
