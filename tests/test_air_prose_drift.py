"""The air layer's several descriptions of itself agree (rc58 W0).

The coverage matrix, the absence ledger, the reporting-sector axis, the power paper's air
table and the national supplement each describe which sources are estimated, screened or
absent - and through rc57 they disagreed: the matrix said industry was screened while the
supplement said it had no layer at all, and the power table said "grid plus captive" while
the axis reported captive under industry. Written to FAIL on the rc57 tree, this module holds
the descriptions to each other:
  * every file a matrix note names exists, and every gap it cites is in the gap register;
  * the ledger's sectors are exactly the matrix's screened sectors plus industry's typed
    absences, and no ledger row prices a cell the matrix marks E;
  * captive generation is reported where the axis says (industry), in every air output;
  * the supplement no longer says industrial combustion has no layer.
"""

from pkinv.assets import asset_path
import csv
import os
from pkinv.paths import PAPER_NATIONAL_MAIN, PAPER_NATIONAL_SECTIONS  # noqa: E402
import re
import unittest

from pkinv.core.io import read_rows

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "outputs")
DATA = asset_path(ROOT, "data")


def _o(name):
    return read_rows(os.path.join(OUT, name))


class TestTheMatrixNamesRealThings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coverage = _o("pakemis_air_coverage_matrix.csv")
        cls.gaps = {r["gap_id"] for r in read_rows(asset_path(DATA, "data_gaps.csv"))}

    def test_every_file_named_in_a_note_exists(self):
        names = set()
        for c in self.coverage:
            names.update(re.findall(r"[A-Za-z0-9_]+\.csv", c["note"].replace("\n", "")))
        for n in sorted(names):
            self.assertTrue(os.path.exists(os.path.join(OUT, n)), "matrix note names a missing file %s" % n)

    def test_every_gap_cited_exists_and_every_absence_has_one_or_a_reason(self):
        for c in self.coverage:
            if c["gap_id"]:
                self.assertIn(c["gap_id"], self.gaps, c)
            if c["state"] != "E":
                self.assertTrue(c["note"], c)


class TestTheLedgerMatchesTheMatrix(unittest.TestCase):
    def test_ledger_sectors_and_cells(self):
        """rc60: power SO2 is the FIRST cell that is estimated and screened at once, and the
        rule it used to break has been rewritten rather than relaxed.

        The old rule was `no scenario number may stand beside an estimated cell`, full stop.
        That was right while a scenario always covered the same sources as the estimate beside
        it - adding them would double count, choosing between them was a coin toss. Power SO2 is
        the case that separates the rule from its purpose: the oil and diesel fleet is estimated
        per station, and what remains in the screening is the fuel the admission did NOT take -
        disjoint by construction, because the screening is linear in fuel mass and is scaled by
        the unadmitted fraction (power.air_pollutants.admitted_remainder_fraction).

        So the pairing is allowed exactly where the screened number is a declared remainder, and
        nowhere else. Every other sector keeps the original rule, and power keeps it for every
        pollutant but SO2.
        """
        coverage = _o("pakemis_air_coverage_matrix.csv")
        ledger = _o("pakemis_air_absence_screening_by_year.csv")
        screened = {c["sector_id"] for c in coverage if c["state_basis"].endswith("screening-only")}
        self.assertEqual(screened, {"power"})
        self.assertEqual({r["sector_id"] for r in ledger}, {"power", "industry", "fugitives"})

        remainder = self._declared_remainder_cells()
        self.assertEqual(len(remainder), 9,
                         "power SO2 is the only declared remainder and it must cover all nine "
                         "periods; a gap would mean a year is screened whole beside an estimate")

        e_cells = {(c["period_id"], c["sector_id"], c["pollutant"])
                   for c in coverage if c["state"] == "E"}
        for r in ledger:
            if not (r["scenario_uncontrolled_kt"] or r["scenario_controlled_kt"]):
                continue
            cell = (r["period_id"], r["sector_id"], r["pollutant"])
            if cell in remainder:
                continue
            self.assertNotIn(cell, e_cells, "a scenario number beside an estimated cell")

    def _declared_remainder_cells(self):
        """The cells whose screened number says, on the row, that it is only the remainder."""
        out = set()
        for r in _o("power_air_screening_fy2015_16_fy2023_24.csv"):
            if "REMAINDER ONLY" in r.get("basis", ""):
                out.add((r["period_id"], "power", r["pollutant"]))
        return out


class TestCaptiveIsReportedWhereTheAxisSays(unittest.TestCase):
    def test_axis_industry_and_no_power_air_output_carries_captive(self):
        axis = {(r["module"], r["category"]): r["reporting_sector"]
                for r in read_rows(asset_path(DATA, "stream_reporting_sector.csv"))}
        self.assertEqual(axis[("power", "Captive gas self-generation (1A2)")], "industry")
        for name in ("power_air_pollutants_fy2023_24.csv", "power_air_screening_fy2015_16_fy2023_24.csv"):
            with open(os.path.join(OUT, name), encoding="utf-8") as f:
                cats = {r["category"] for r in csv.DictReader(f)}
            self.assertFalse([c for c in cats if "aptive" in c], name)
        atoms = _o("pakemis_air_atomic_annual.csv")
        captive = {a["sector_id"] for a in atoms if a["category"].startswith("Captive")}
        self.assertEqual(captive, {"industry"})
        # rc60: power now contributes atoms of its OWN, and the captive boundary is untouched
        # by that - the grid classes are main-activity generation and name no captive category.
        power = {a["category"] for a in atoms if a["sector_id"] == "power"}
        self.assertFalse([c for c in power if "aptive" in c],
                         "a captive category reached the power atoms; it is priced once, under "
                         "industry, and admitting grid oil must not have moved it")

    def test_the_power_paper_table_says_grid_only(self):
        with open(os.path.join(ROOT, "papers", "power", "sections", "06b_air_pollutants.tex"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("Grid plus captive", text)
        self.assertIn("Grid only", text)


class TestTheSupplementAgrees(unittest.TestCase):
    def test_industry_is_not_described_as_having_no_layer(self):
        with open(os.path.join(PAPER_NATIONAL_MAIN, "supplement.tex"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("Industry, IPPU & absent", text)
        self.assertNotIn("industrial combustion and IPPU process pollutants have no layer", text)
        self.assertIn("Industry & provisional estimate", text)
        with open(os.path.join(PAPER_NATIONAL_SECTIONS, "12_limitations.tex"), encoding="utf-8") as f:
            lim = f.read()
        self.assertNotIn("industrial\ncombustion and IPPU process pollutants, which have no layer at all", lim)

    def test_ippu_and_fugitives_are_not_described_as_having_no_layer(self):
        """rc59: the two register modules entered the panel; every description that said
        'no layer' must now say provisional estimate, and the matrix must agree."""
        with open(os.path.join(PAPER_NATIONAL_MAIN, "supplement.tex"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("IPPU, fugitives & absent", text)
        self.assertNotIn("have no layer at", text)
        self.assertIn("IPPU & provisional estimate", text)
        self.assertIn("Fugitives & provisional estimate", text)
        with open(os.path.join(PAPER_NATIONAL_SECTIONS, "12_limitations.tex"), encoding="utf-8") as f:
            lim = f.read()
        self.assertNotIn("fugitive NMVOC, which have no layer at all", lim)
        from pkinv.semantic import release_json
        texts = " ".join(l["message"] for l in release_json.BASE_LIMITATIONS)
        self.assertNotIn("have no air-pollutant layer", texts)
        self.assertIn("rc59", texts)
        coverage = _o("pakemis_air_coverage_matrix.csv")
        for module in ("ippu", "fugitives"):
            states = {c["pollutant"]: c["state"] for c in coverage if c["sector_id"] == module and c["period_id"] == "FY2023-24"}
            self.assertEqual(states["NMVOC"], "E", module)
            self.assertEqual(states["NOx"], "E", module)
        self.assertEqual({c["state"] for c in coverage if c["sector_id"] == "fugitives" and c["pollutant"] == "NH3"}, {"NE"})


if __name__ == "__main__":
    unittest.main()
