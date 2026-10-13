"""The atomic annual table: does it hold only parts, and do the parts add up?

Two properties make this table worth having. It must contain NO aggregate — the moment a
total sits beside its parts, a naive sum is wrong and correctness goes back to depending on
every reader filtering a magic string. And it must reproduce the published series exactly,
because it is a re-expression of the same arithmetic, not a second one; if it disagreed,
the repository would have two vintages of the national total and no way to say which is
right.

The two legacy products keep their mixed shape - about a hundred and sixty call sites read
national_all_sectors.csv by the magic string "TOTAL" and moving that row would break all of
them while moving no number - so what changed is that the row kind is now a TYPED COLUMN
beside the name. The last class here holds both halves of that bargain: row_kind must agree
with the magic string it replaces (a typed column that disagreed with the name would be
worse than no column at all), and the atomic table must reproduce both legacy files cell for
cell, which is what makes them derivable rather than merely consistent today.

Run:  python3 -m unittest discover tests -p "test_atomic_annual.py"
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import re
import unittest

from pkinv.paths import DATA, OUTPUTS
from pkinv.report import atomic_annual as aa
from pkinv.core.io import read_rows


def _rows(name, base=OUTPUTS):
    return read_rows(os.path.join(base, name), comments=False)


class TestItHoldsOnlyParts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_atomic_annual.csv")

    def test_no_aggregate_row_is_present(self):
        """The two magic strings that make the existing products unsafe to sum."""
        for row in self.rows:
            self.assertNotIn(row["sector_id"], ("TOTAL", "COVERED_TOTAL"))
            self.assertNotEqual(row["category"], "TOTAL")

    def test_the_atom_has_no_row_kind_column_at_all(self):
        """The stronger form of the rule above, and the reason it is stated separately.

        `row_kind` exists because two shipped files mix parts with their totals and cannot
        stop. This table does not mix them, so it must not carry the column: a `row_kind`
        here would be an invitation to add the one value it exists to distinguish. A table
        whose every row is a part says so by having nowhere to say anything else.
        """
        self.assertNotIn("row_kind", self.rows[0].keys())
        self.assertNotIn("row_kind", aa.FIELDS)
        for name in ("aggregation_level",):
            self.assertNotIn(name, self.rows[0].keys())

    def test_the_key_is_unique(self):
        key = lambda r: (r["period_id"], r["component_id"], r["gas"],
                         r["configuration_id"], r["geography_id"])
        keys = [key(r) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_row_declares_both_placeholder_axes(self):
        """configuration_id and geography_id are constant today. Constant is a declared
        limitation; absent would be a silence."""
        self.assertEqual({r["configuration_id"] for r in self.rows},
                         {aa.REFERENCE_CONFIGURATION})
        self.assertEqual({r["geography_id"] for r in self.rows},
                         {aa.NATIONAL_GEOGRAPHY})

    def test_nothing_is_blank_that_should_not_be(self):
        for row in self.rows:
            for column in ("period_id", "component_id", "sector_id", "estimate_status",
                           "activity_status", "configuration_id", "geography_id",
                           "release_id", "method_id", "uncertainty_model_id"):
                self.assertTrue(str(row[column]).strip(),
                                "%s blank on %s" % (column, row["component_id"]))

    def test_absent_sector_periods_are_rows_carrying_no_number(self):
        """ZERO, down from eleven, and the last two closed from the public record.

        The first nine closed without an outside acquisition: the clinker trade panel,
        the State Bank cement series, Statistical Year Book 2020 Table 13.2, and the
        OGRA image scan that only needed rendering. The last two - industry and
        transport FY2015-16, "blocked on an OCAC edition that exists nowhere in the
        record" - closed at rc20 when the fifteenth review pointed out the record was
        wrong: the Pakistan Oil Report 2015-2016 is publicly served as an image
        flipbook, and its page-50 table is transcribed under a quadruple identity gate
        (sectors/transport/ocac_image_edition.py). The count stays asserted exactly so
        that a NEW absence has to be a deliberate edit here and in
        national_series.GAPS."""
        absent = [r for r in self.rows if r["estimate_status"] == "absent"]
        self.assertEqual(len(absent), 0,
                         sorted((r["sector_id"], r["period_id"]) for r in absent))

    def test_no_row_is_carried_at_the_coarse_grain_any_more(self):
        """THE COARSE PATH IS NOW UNUSED, and both halves of its history matter.

        An earlier draft returned [] for the pre-reference agriculture history, which silently
        dropped half the inventory and printed FY2015-16 at 135.85 Mt against the series'
        305.42. The fix emitted those rows at a declared coarser grain, and this test asserted
        they existed and said so.

        They no longer exist, because the grain was never really coarse: `fiscal_series` had
        been computing all thirty-five components for every year and discarding them while
        `annual_product.components_for` returned None and claimed no split was available.

        THE MECHANISM STAYS AND IS STILL RIGHT for any sector-period that genuinely has only a
        category total - what changed is that nothing claims it falsely. So the assertion is
        inverted rather than deleted: no row may sit at the coarse grain, and if one appears
        again it is either a real new absence that must be justified here, or the false one
        coming back.
        """
        coarse = [r for r in self.rows if r["estimate_status"] == "E-category-gas"]
        self.assertEqual([], coarse,
                         "%d rows fell back to the category-gas grain: %s"
                         % (len(coarse), sorted({(r["sector_id"], r["period_id"])
                                                 for r in coarse})))
        self.assertNotIn("(no component split)", {r["subitem"] for r in self.rows})


class TestItClosesToThePublishedSeries(unittest.TestCase):
    def test_national_totals_reproduce_the_series(self):
        atom = collections.defaultdict(float)
        for row in _rows("pakemis_atomic_annual.csv"):
            if row["co2e_Mt_AR5"]:
                atom[row["period_id"]] += float(row["co2e_Mt_AR5"])
        series = {r["period_label"]: float(r["co2e_Mt_AR5"])
                  for r in _rows("pakemis_national_series.csv")
                  if r["sector"] == "COVERED_TOTAL"}
        self.assertEqual(set(atom), set(series))
        for period, got in atom.items():
            self.assertAlmostEqual(got, series[period], places=3, msg=period)

    def test_the_reference_period_is_the_headline(self):
        atom = sum(float(r["co2e_Mt_AR5"])
                   for r in _rows("pakemis_atomic_annual.csv")
                   if r["period_id"] == "FY2023-24" and r["co2e_Mt_AR5"])
        national = next(float(r["co2e_Mt_AR5"])
                        for r in _rows("national_all_sectors.csv")
                        if r["sector"] == "TOTAL")
        self.assertAlmostEqual(atom, national, places=3)

    def test_aggregates_are_derived_and_agree(self):
        rows = _rows("pakemis_atomic_annual.csv")
        published = _rows("pakemis_atomic_annual_aggregates.csv")
        by_sector = collections.defaultdict(float)
        for row in rows:
            if row["co2e_Mt_AR5"]:
                by_sector[(row["period_id"], row["sector_id"])] += float(row["co2e_Mt_AR5"])
        for row in published:
            if row["aggregation_level"] != "sector":
                continue
            key = (row["period_id"], row["sector_id"])
            self.assertAlmostEqual(float(row["co2e_Mt_AR5"]), by_sector[key],
                                   places=6, msg=str(key))


class TestThePeriodRegistry(unittest.TestCase):
    def test_it_equals_what_period_py_computes(self):
        """The table materialises core/period.py. If the two drift, the ids on every
        atomic row stop meaning what the code says they mean."""
        from pkinv.core import period
        from pkinv.report import periods
        for row in _rows("periods.csv", base=DATA):
            start, end = period.fiscal(int(row["fiscal_start_year"]))
            self.assertEqual(row["period_id"], period.label(start, end))
            self.assertEqual(row["period_start"], start.isoformat())
            self.assertEqual(row["period_end"], end.isoformat())
            self.assertEqual(int(row["days"]), (end - start).days + 1)
        self.assertEqual(len(_rows("periods.csv", base=DATA)), len(periods.rows()))

    def test_exactly_one_reference_period(self):
        reference = [r for r in _rows("periods.csv", base=DATA)
                     if r["is_reference"] == "True"]
        self.assertEqual(len(reference), 1)
        self.assertEqual(reference[0]["period_id"], "FY2023-24")

    def test_the_leap_year_is_a_day_longer(self):
        days = {r["period_id"]: int(r["days"]) for r in _rows("periods.csv", base=DATA)}
        self.assertEqual(days["FY2015-16"], 366)
        self.assertEqual(days["FY2016-17"], 365)


class TestTheLegacyProductsAreTypedAndDerivable(unittest.TestCase):
    """The mixed-grain files, after Pass 1 Step 4."""

    ROLLUPS = ("national_all_sectors.csv", "national_all_sectors_ledger.csv")

    def test_row_kind_agrees_with_the_magic_string_it_replaces(self):
        """Both directions. A typed column that disagreed with the name would be a third
        way to be wrong, not a fix."""
        for name in self.ROLLUPS:
            for row in _rows(name):
                want = "national_total" if row["sector"] == "TOTAL" else "sector"
                self.assertEqual(row["row_kind"], want, "%s / %s" % (name, row["sector"]))
        for row in _rows("pakemis_national_series.csv"):
            want = "covered_total" if row["sector"] == "COVERED_TOTAL" else "sector"
            self.assertEqual(row["row_kind"], want, row["sector"])

    def test_the_vocabulary_is_closed_and_the_totals_are_countable(self):
        for name in self.ROLLUPS:
            kinds = collections.Counter(r["row_kind"] for r in _rows(name))
            self.assertEqual(set(kinds), {"sector", "national_total"})
            self.assertEqual(kinds["national_total"], 1, name)
        kinds = collections.Counter(r["row_kind"]
                                    for r in _rows("pakemis_national_series.csv"))
        self.assertEqual(set(kinds), {"sector", "covered_total"})
        self.assertEqual(kinds["covered_total"], 9)

    def test_the_total_row_is_the_sum_of_the_rows_typed_as_parts(self):
        """What the mixed shape costs: this is the sum a naive reader would get wrong."""
        for name in self.ROLLUPS:
            rows = _rows(name)
            parts = sum(float(r["co2e_Mt_AR5"]) for r in rows if r["row_kind"] == "sector")
            total = next(float(r["co2e_Mt_AR5"]) for r in rows
                         if r["row_kind"] == "national_total")
            self.assertAlmostEqual(parts, total, places=3, msg=name)

    def test_the_atom_reproduces_the_rollup_sector_by_sector(self):
        """The reference-year rollup is derivable from the atom: not a second arithmetic
        path, a projection of the same one."""
        atom = collections.defaultdict(float)
        for row in _rows("pakemis_atomic_annual.csv"):
            if row["period_id"] == "FY2023-24" and row["co2e_Mt_AR5"]:
                atom[row["sector_id"]] += float(row["co2e_Mt_AR5"])
        shipped = {r["sector"]: float(r["co2e_Mt_AR5"])
                   for r in _rows("national_all_sectors.csv") if r["row_kind"] == "sector"}
        self.assertEqual(set(atom), set(shipped))
        for sector, got in atom.items():
            self.assertAlmostEqual(got, shipped[sector], places=3, msg=sector)

    def test_the_atom_reproduces_the_series_cell_for_cell(self):
        """Every sector-year, not just the nine national totals - a table can close on its
        margins while every interior cell is wrong."""
        atom = collections.defaultdict(float)
        for row in _rows("pakemis_atomic_annual.csv"):
            if row["co2e_Mt_AR5"]:
                atom[(row["period_id"], row["sector_id"])] += float(row["co2e_Mt_AR5"])
        for row in _rows("pakemis_national_series.csv"):
            if row["row_kind"] != "sector" or row["co2e_Mt_AR5"] == "absent":
                continue
            key = (row["period_label"], row["sector"])
            self.assertIn(key, atom, "the atom has no rows for %s" % (key,))
            self.assertAlmostEqual(atom[key], float(row["co2e_Mt_AR5"]),
                                   places=3, msg=str(key))

    def test_the_absent_sector_years_are_absent_in_both(self):
        """A gap the series declares and the atom quietly fills would be the worse of the
        two failures: the reader sees a number and no warning."""
        series_absent = {(r["period_label"], r["sector"])
                         for r in _rows("pakemis_national_series.csv")
                         if r["co2e_Mt_AR5"] == "absent"}
        atom_absent = {(r["period_id"], r["sector_id"])
                       for r in _rows("pakemis_atomic_annual.csv")
                       if r["estimate_status"] == "absent"}
        self.assertEqual(series_absent, atom_absent)

    def test_every_aggregation_level_equals_its_parts(self):
        """category_gas, sector and national, each against the same atom."""
        rows = [r for r in _rows("pakemis_atomic_annual.csv") if r["co2e_Mt_AR5"]]
        # `covered_total` is the same roll-up as `national` for a period the inventory does
        # not fully cover - the level names what a reader may conclude, not a different sum.
        keys = {"category_gas": lambda r: (r["period_id"], r["sector_id"],
                                           r["category"], r["gas"]),
                "sector": lambda r: (r["period_id"], r["sector_id"]),
                "national": lambda r: (r["period_id"],),
                "covered_total": lambda r: (r["period_id"],)}
        summed = {level: collections.defaultdict(float) for level in keys}
        for row in rows:
            for level, key in keys.items():
                summed[level][key(row)] += float(row["co2e_Mt_AR5"])
        # The two top levels partition the periods between them, so each period's total is
        # counted once whichever name it carries.
        summed["covered_total"] = summed["national"]
        seen = collections.Counter()
        for row in _rows("pakemis_atomic_annual_aggregates.csv"):
            level = row["aggregation_level"]
            key = keys[level]({"period_id": row["period_id"],
                               "sector_id": row["sector_id"],
                               "category": row["category"], "gas": row["gas"]})
            self.assertAlmostEqual(float(row["co2e_Mt_AR5"]), summed[level][key],
                                   places=6, msg="%s %s" % (level, key))
            seen[level] += 1
        self.assertEqual(seen["national"] + seen["covered_total"], len(summed["national"]),
                         "every period must appear once under exactly one top level")
        for level in ("category_gas", "sector"):
            self.assertEqual(seen[level], len(summed[level]),
                             "%s: published %d groups, the atom has %d"
                             % (level, seen[level], len(summed[level])))


class TestNoNewReaderPatternMatchesTheName(unittest.TestCase):
    """The condition attached to keeping the legacy shape.

    Typing the row kind is only worth anything if the untyped way stops spreading. Every
    production reader was converted when the column landed; what this guard defends is the
    NEXT one, written by someone who greps for an example and finds an old line.

    The two WRITERS are exempt because they are where the kind is decided - `row_kind` is
    derived from the sector name there, so the name is the input, not a shortcut around the
    column. Tests are exempt by file, not by line: a test that checks the typed column
    against the name it replaces has to mention both, and freezing the file list means a
    NEW test file cannot quietly reintroduce the habit while the existing equivalence
    checks stay readable.
    """

    PATTERN = re.compile(r"""["']sector["']\]\s*[!=]=\s*["'](TOTAL|COVERED_TOTAL)["']""")
    WRITERS = ("src/pkinv/report/national_rollup.py", "src/pkinv/report/national_series.py")
    TEST_FILES = ("tests/test_annual_product.py", "tests/test_atomic_annual.py",
                  "tests/test_category_ledger.py", "tests/test_national_rollup.py",
                  "tests/test_national_series.py", "tests/paper_numbers/test_release_integrity.py",
                  "tests/test_source_streams.py", "tests/test_uncertainty_reconciliation.py")

    def _hits(self, *trees):
        root = os.path.join(os.path.dirname(__file__), "..")
        found = []
        for tree in trees:
            for base, _dirs, names in os.walk(asset_path(root, tree)):
                if "__pycache__" in base:
                    continue
                for name in sorted(names):
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(base, name)
                    relative = os.path.relpath(path, root).replace(os.sep, "/")
                    with open(path, encoding="utf-8") as handle:
                        for number, line in enumerate(handle, 1):
                            if self.PATTERN.search(line):
                                found.append((relative, number, line.strip()))
        return found

    def test_no_production_reader_outside_the_two_writers(self):
        offenders = ["%s:%d  %s" % hit for hit in self._hits("src", "scripts")
                     if hit[0] not in self.WRITERS]
        self.assertFalse(offenders,
                         "these read the row kind out of the sector NAME. Read the typed "
                         "column instead: row_kind == 'sector' / 'national_total' on the "
                         "rollups, 'covered_total' on the series:\n  "
                         + "\n  ".join(offenders))

    def test_no_new_test_file_learns_the_habit(self):
        offenders = sorted({hit[0] for hit in self._hits("tests")}
                           - set(self.TEST_FILES))
        self.assertFalse(offenders,
                         "new test files matching on the sector name: %s. Use row_kind, or "
                         "add the file here if it genuinely has to check the name against "
                         "the column." % ", ".join(offenders))


class TestItRegeneratesIdentically(unittest.TestCase):
    def test_the_atomic_table_regenerates_identically(self):
        fresh = aa.build()
        shipped = _rows("pakemis_atomic_annual.csv")
        self.assertEqual(len(fresh), len(shipped))
        for got, want in zip(fresh, shipped):
            for column in aa.FIELDS:
                self.assertEqual(str(got[column]), want[column],
                                 "%s drifted for %s" % (column, want["component_id"]))


if __name__ == "__main__":
    unittest.main()
