"""Gates on the PBS minerals ingest and the wiring contract it now serves.

Monthly provincial production of natural gas, crude oil, coal and limestone. The parse enforces
both of the document's own controls; each canonical mineral resolves in five or six of the
eight held editions because PBS re-lays the names year to year. For two releases that coverage
was the reason nothing read the table, enforced by a test. An external review overruled the
refusal - observed years at T2, missing years days-weighted T4, never a borrowed shape - and
the fugitives upstream streams now ride the panel under exactly that contract, held by the
gates in TheWiringContract below.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

PANEL = asset_path(ROOT, "data", "activity", "monthly", "pbs_minerals_month_province.csv")
SUMMARY = os.path.join(ROOT, "outputs", "pbs_minerals_parse_summary.csv")

HELD_YEARS = ("2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023")
ABSENT = "FY2015-16"
CANONICAL = ("coal", "crude_oil", "limestone", "natural_gas")


def _rows(path):
    return read_rows(path)


class TheParse(unittest.TestCase):
    def setUp(self):
        self.summary = _rows(SUMMARY)[0]

    def test_all_eight_held_editions_were_parsed(self):
        self.assertEqual(8, int(self.summary["files_parsed"]))
        self.assertEqual(8, int(self.summary["fiscal_years_held"]))

    def test_the_absent_year_is_a_declared_literal(self):
        """FY2015-16 is not held. An empty cell would read as "nothing missing", which is the
        difference between a gap and a silence."""
        self.assertEqual(ABSENT, self.summary["fiscal_years_absent"])

    def test_the_group_control_closes_for_most_mineral_years(self):
        closed = int(self.summary["mineral_years_closing_group_control"])
        total = int(self.summary["mineral_years"])
        self.assertGreater(closed / total, 0.90,
                           "only %d of %d mineral-years close on their own Total row"
                           % (closed, total))

    def test_the_editions_without_a_year_total_column_are_read_anyway(self):
        """FY2021-22 prints twelve columns and no year total. A rule demanding thirteen
        rejected every row in it silently and reported the year as absent while the file was
        in hand - so the row control has to be recorded as missing, never manufactured."""
        years = {r["fiscal_year_start"] for r in _rows(PANEL)}
        self.assertEqual(set(HELD_YEARS), years)
        controls = {r["row_control"] for r in _rows(PANEL)}
        self.assertEqual({"year_total", "absent-in-edition"}, controls)

    def test_a_row_without_a_year_total_carries_no_invented_one(self):
        for row in _rows(PANEL):
            if row["row_control"] == "absent-in-edition":
                self.assertEqual("", row["year_total_printed"])


class TheTotalRowIsNotAProvince(unittest.TestCase):
    def test_no_row_is_carried_under_the_group_control_label(self):
        """The per-mineral "Total" row is the control, and carrying it as a province would
        double every mineral in the table."""
        provinces = {r["province"] for r in _rows(PANEL)}
        self.assertNotIn("Total", provinces)


class TheWiringContract(unittest.TestCase):
    """WHAT REPLACED THE UNWIRING GATE, and why it went.

    `test_nothing_reads_this_table` enforced the decision that a panel covering five or six of
    nine years must not feed a profile, and said in its own docstring to delete it with the
    reason when the coverage question was settled. It was settled by an external review's
    ruling, not by better coverage: observed years at T2, missing years days-weighted T4, no
    year wearing another's shape. `core/pbs_minerals.py` implements that contract; these gates
    hold it.
    """

    def test_the_reader_serves_exactly_the_covered_years(self):
        """Eight of nine for both streams since the Wave-2 parse repairs, each from a
        file already held: FY2021-22's gas row prints as bare "Gas" (one canonical
        key); FY2022-23's three-line name wrap orphaned a province and manufactured a
        "Barrel)" mineral (the stitch in ingest_pbs_minerals.parse); and FY2016-17
        prints gas and oil as TOTAL-only national rows the parser used to discard as
        empty-group controls - the total IS that edition's observation. The one absent
        year, FY2015-16, is the bulletin not held: the live request."""
        from pkinv.core import pbs_minerals as pm
        expected = {"natural_gas": set(range(2016, 2024)),
                    "crude_oil": set(range(2016, 2024))}
        for mineral, years in expected.items():
            got = {fy for fy in range(2015, 2024) if pm.covers(mineral, fy)}
            self.assertEqual(years, got, mineral)

    def test_an_uncovered_year_is_days_weighted_not_borrowed(self):
        """The half of the ruling that forbids as firmly as the other half requires.
        The fixture year moved 2016 -> 2015 when the total-only recovery covered 2016;
        FY2015-16 is the one remaining uncovered year (bulletin not held)."""
        from pkinv.core import monthly as cm, pbs_minerals as pm
        shares, method, covered = pm.profile_or_flat(pm.NATURAL_GAS, 2015)
        self.assertFalse(covered)
        self.assertEqual(shares, cm.days_weighted_profile(2015))
        self.assertEqual({"T4"}, set(method.values()))

    def test_a_covered_year_is_its_own_twelve_months_at_t2(self):
        from pkinv.core import pbs_minerals as pm
        shares, method = pm.profile(pm.NATURAL_GAS, 2023)
        self.assertEqual(12, len(shares))
        self.assertAlmostEqual(1.0, sum(shares.values()), places=12)
        self.assertEqual({"T2"}, set(method.values()))

    def test_the_covered_years_differ_from_one_another(self):
        from pkinv.core import pbs_minerals as pm
        shapes = {fy: tuple(round(v, 9) for _m, v in sorted(pm.profile(
            pm.NATURAL_GAS, fy)[0].items())) for fy in (2017, 2018, 2019, 2020, 2023)}
        self.assertEqual(len(shapes), len(set(shapes.values())))

    def test_only_upstream_fugitive_streams_ride_the_production_shape(self):
        """Production must never shape a demand-side stream: deliveries and send-out have
        their own season that field output does not observe."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "pbs_minerals", "--include=*.py",
             os.path.join(ROOT, "src", "pkinv", "sectors")],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        readers = {line.split(":")[0] for line in result.stdout.decode().splitlines()}
        self.assertEqual({os.path.join(ROOT, "src", "pkinv", "sectors", "fugitives",
                                       "monthly.py")}, readers)
        text = open(os.path.join(ROOT, "src", "pkinv", "sectors", "fugitives",
                                 "monthly.py"), encoding="utf-8").read()
        for demand_side in ("Gas distribution", "Gas transmission", "Post-meter", "LNG"):
            self.assertNotIn('"%s"' % demand_side,
                             text[text.index("GAS_UPSTREAM"):text.index("OIL_UPSTREAM")],
                             "%s is demand-side and must not ride production" % demand_side)


if __name__ == "__main__":
    unittest.main()
