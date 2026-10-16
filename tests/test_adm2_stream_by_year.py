"""The per-stream district vector, for all nine periods.

The reference year's version has shipped since rc47; the other eight were computed in the same loop
and dropped, which is the whole reason a district question finer than a module could be answered for
one year only. Two things must hold, and they are the two that make this a product rather than a
convenience: it is the SAME generator as the reference-year file (so the two cannot drift), and it
closes to the provincial mass in every period (so the district partition it supports is exact).
"""
import collections
import csv
import os
import unittest

from _support import OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_adm2_stream_by_year.csv")
REFERENCE = os.path.join(OUTPUTS, "pakemis_adm2_stream_reference.csv")
ADM1 = os.path.join(OUTPUTS, "pakemis_adm1_by_year.csv")
from pkinv.core.reporting_window import CORE_PERIOD_IDS
PERIODS = CORE_PERIOD_IDS
RTOL = 1e-9


def rows(path):
    with open(path, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class TheNineYearStreamDistrictProduct(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows(OUT)

    def test_it_covers_every_period(self):
        self.assertEqual(sorted({r["period_id"] for r in self.rows}), sorted(PERIODS))

    def test_it_reproduces_the_reference_year_file(self):
        """One generator, two files. If these ever disagree beyond their shared precision, one of
        them is a second derivation of the same geography - the defect the ADM2 view rule exists to
        prevent. NOT byte-equality: this file prints ten significant digits and the reference-year
        file twelve, because twelve is precision a floating-point reduction over grid cells does not
        reproduce run to run (see grid_cube.adm2_stream_rows). Same rows, same keys, same values to
        the precision the arithmetic carries."""
        mine = {(r["source_stream_id"], r["shape_id"], r["allocation_status"]): r["emissions_Gg"]
                for r in self.rows if r["period_id"] == "FY2023-24"}
        theirs = {(r["source_stream_id"], r["shape_id"], r["allocation_status"]): r["emissions_Gg"]
                  for r in rows(REFERENCE)}
        self.assertEqual(set(mine), set(theirs), "the two files do not carry the same rows")
        for key, value in mine.items():
            a, b = float(value), float(theirs[key])
            if a == 0.0 or b == 0.0:
                self.assertEqual(a, b, str(key))
            else:
                self.assertAlmostEqual(a / b, 1.0, places=9, msg=str(key))

    def test_every_stream_closes_to_its_provincial_mass_in_every_period(self):
        placed = collections.defaultdict(float)
        for r in self.rows:
            if r["emissions_Gg"] == "":
                continue
            placed[(r["period_id"], r["source_stream_id"])] += float(r["emissions_Gg"])
        adm1 = collections.defaultdict(float)
        for r in rows(ADM1):
            adm1[(r["period_id"], r["source_stream_id"])] += float(r["emissions_Gg"] or 0.0)
        checked = 0
        for key, total in adm1.items():
            if key not in placed or total == 0.0:
                continue
            self.assertAlmostEqual(placed[key] / total, 1.0, delta=RTOL, msg=str(key))
            checked += 1
        self.assertGreater(checked, 1500, "the closure must actually bite across nine periods")

    def test_the_captive_stream_is_placed_in_every_period(self):
        """The stream the reporting axis moves at district grain. If it were ever unplaced, the
        district partition would be resting on a proportional split instead of its own points."""
        captive = [r for r in self.rows
                   if r["source_stream_id"].startswith("power|captive-gas-self-generation")
                   and r["emissions_Gg"] not in ("", "0")]
        self.assertEqual(sorted({r["period_id"] for r in captive}), sorted(PERIODS))
        for r in captive:
            self.assertEqual(r["reporting_sector"], "industry")
            self.assertEqual(r["module"], "power")
