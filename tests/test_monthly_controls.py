"""The monthly controls register: partition, stamps, vocabularies, reconciliation.

The register is the monthly lane's seed (docs/monthly_lane.md), and its contract is
structural: exactly one row per (stream, month) - the cube-join hazard makes extra
rows for one key silently last-write-wins downstream, so uniqueness is asserted, not
assumed; every row names the edition it came from by hash; the vocabularies are
closed; and the register reconciles against the engine's own reader per fiscal year,
so it cannot drift from what the monthly layer actually consumes. The lane stays a
SEPARATE product: national_monthly_2024.csv must never grow edition columns.
"""
import csv
import os
import sys
import unittest
from pkinv.core.io import read_rows
from _support import ROOT


REGISTER = os.path.join(ROOT, "outputs", "pakemis_monthly_controls.csv")
NATIONAL = os.path.join(ROOT, "outputs", "national_monthly_2024.csv")


def _rows():
    return read_rows(REGISTER, comments=False)


class TestMonthlyControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_one_row_per_stream_month(self):
        keys = [(r["stream"], r["month"]) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))
        streams = {r["stream"] for r in self.rows}
        self.assertEqual(len(streams), 6)
        for stream in streams:
            months = [r["month"] for r in self.rows if r["stream"] == stream]
            self.assertEqual(len(months), 48, stream)

    def test_every_row_names_its_edition_by_hash(self):
        for r in self.rows:
            self.assertRegex(r["source_sha256"], r"^[0-9a-f]{64}$",
                             "%s %s" % (r["stream"], r["month"]))
            self.assertTrue(r["source_file"].strip())
            self.assertRegex(r["as_of"], r"^\d{4}-\d{2}$")

    def test_vocabularies_are_closed(self):
        for r in self.rows:
            self.assertIn(r["measurement"], ("direct", "cumulative_differenced"))
            self.assertIn(r["status"],
                          ("final", "provisional", "corrected", "superseded"))
            self.assertIn(r["t_class"], ("T1", "T2"))
        # every fiscal year the panel holds is closed, so the seed is all-final;
        # the first provisional row arrives with the first FY2025-26 edition
        self.assertEqual({r["status"] for r in self.rows}, {"final"})

    def test_register_reconciles_against_the_engines_reader(self):
        from pkinv.core import ocac_monthly
        from pkinv.report import monthly_controls as mc
        for stream, sector_row, products in mc.STREAMS:
            for fy in mc.FY_STARTS:
                engine, _ = ocac_monthly.tonnes(sector_row, products, fy)
                months = ["%s-%s" % (k[:4], k[4:]) for k in sorted(engine)]
                register = {r["month"]: float(r["tonnes"]) for r in self.rows
                            if r["stream"] == stream and r["month"] in months}
                self.assertEqual(len(register), 12, (stream, fy))
                for key, value in engine.items():
                    m = "%s-%s" % (key[:4], key[4:])
                    self.assertAlmostEqual(register[m], value, places=3,
                                           msg=(stream, m))

    def test_the_regime_narrative_matches_the_stamps(self):
        """FY2021 and FY2024 editions are direct monthly, FY2022 and FY2023
        cumulative-differenced - the regime changes the temporal benchmark's
        origins declare - EXCEPT July: a cumulative year's opening column IS the
        month and OCAC publishes it as a monthly edition, so 2022-07 and 2023-07
        are direct inside cumulative years. Asserted on the panel streams
        (aviation's record has its own edition kinds)."""
        panel = [r for r in self.rows if r["stream"] != "aviation_domestic_jp1"]
        for r in panel:
            year, month = (int(p) for p in r["month"].split("-"))
            fy = year if month >= 7 else year - 1
            expected = ("direct" if fy in (2021, 2024) or month == 7
                        else "cumulative_differenced")
            self.assertEqual(r["measurement"], expected, r["month"])

    def test_aviation_carries_the_published_revision_vocabulary(self):
        aviation = [r for r in self.rows
                    if r["stream"] == "aviation_domestic_jp1"]
        notes = {r["revision_note"] for r in aviation}
        self.assertIn("direct monthly report", notes)
        self.assertTrue(any("revised" in n or "corrected" in n for n in notes),
                        notes)

    def test_the_lane_is_a_separate_product(self):
        """The cube-join hazard, structurally: the national monthly product must
        not learn edition columns - the lane lives here, keyed once per month."""
        with open(NATIONAL, newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        self.assertNotIn("source_sha256", header)
        self.assertNotIn("as_of", header)


if __name__ == "__main__":
    unittest.main()
