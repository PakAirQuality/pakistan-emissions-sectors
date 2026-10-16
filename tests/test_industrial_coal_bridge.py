"""Wave 4 of the industrial-coal reconstruction: the replacement bridge and the reference
decision. This guards the honesty properties: the identity is printed as a band, the one
promoted component (the clinker basis) carries a point with the expected per-year deltas and
zero at the census year, every bounded component carries a band with NO manufactured central,
the official columns are the atoms verbatim, and the national pins do not move.
"""
import csv
import os
import subprocess
import sys
import unittest
from collections import defaultdict

from _support import OUTPUTS, ROOT

OUT = os.path.join(OUTPUTS, "pakemis_industrial_coal_bridge.csv")
ATOMS = os.path.join(OUTPUTS, "pakemis_atomic_annual.csv")


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


def banner():
    with open(OUT, encoding="utf-8") as h:
        return [l for l in h if l.startswith("#")]


class TestTheIdentity(unittest.TestCase):
    def test_the_identity_is_printed_as_a_band_and_the_official_delta_is_the_waterfall(self):
        text = "".join(banner())
        self.assertIn("dE_new = dE_official + dE_end - dE_start", text)
        self.assertIn("lies in [", text)
        # The endpoint is the declared core, not the former nine-year window.
        import re
        by_year = defaultdict(float)
        for row in rows():
            if row["component"].startswith("1.A.2"):
                by_year[row["fiscal_year"]] += float(row["official_mt_co2e"] or 0)
        endpoints = sorted(by_year)
        expected = by_year[endpoints[-1]] - by_year[endpoints[0]]
        match = re.search(r"dE_official = ([+-]?[\d.]+) Mt", text)
        self.assertIsNotNone(match)
        self.assertAlmostEqual(float(match.group(1)), expected, delta=.011)
        self.assertIn("+37.1", text)                        # the 2.A.1 promotion, back-years summed


class TestThePromotedComponent(unittest.TestCase):
    def setUp(self):
        self.clinker = {r["fiscal_year"]: r for r in rows() if r["component"].startswith("2.A.1")}

    def test_nine_years_a_point_not_a_band_and_the_census_year_is_unchanged(self):
        from pkinv.core.reporting_window import CORE_FY_STARTS
        self.assertEqual(set(self.clinker), {"%d-%02d" % (y, (y+1)%100) for y in CORE_FY_STARTS})
        for fy, r in self.clinker.items():
            self.assertEqual(r["reconstructed_low_mt"], r["reconstructed_high_mt"], fy)
            self.assertEqual(r["reconstructed_central_mt"], r["reconstructed_high_mt"], fy)
        ref = self.clinker["2023-24"]
        self.assertEqual(float(ref["delta_vs_official_low_mt"]), 0.0)
        self.assertIn("unchanged", ref["decision"])

    def test_the_back_year_deltas_are_the_census_fraction_applied(self):
        """+3.96..+5.57 Mt per year, +37.1 in total - the joint re-base's size on 2.A.1."""
        deltas = [float(r["delta_vs_official_low_mt"]) for fy, r in self.clinker.items() if fy < "2023-24"]
        self.assertEqual(len(deltas), 8)
        self.assertTrue(all(3.9 < d < 5.7 for d in deltas), deltas)
        self.assertAlmostEqual(sum(deltas), 37.13, places=1)
        for fy, r in self.clinker.items():
            if fy < "2023-24":
                self.assertTrue(r["decision"].startswith("PROMOTE"), fy)


class TestTheBoundedComponents(unittest.TestCase):
    def setUp(self):
        self.by = defaultdict(dict)
        for r in rows():
            self.by[r["component"]][r["fiscal_year"]] = r

    def test_every_solid_component_is_bounded_with_no_manufactured_central(self):
        solid = [c for c in self.by if c.startswith("1.A.2")]
        self.assertEqual(len(solid), 3)
        for c in solid:
            for fy, r in self.by[c].items():
                self.assertTrue(r["decision"].startswith("BOUNDED"), (c, fy))
                self.assertEqual(r["reconstructed_central_mt"], "", (c, fy))

    def test_the_cement_band_brackets_and_the_others_are_retained_not_zeroed(self):
        cement = self.by["1.A.2 cement kiln coal"]
        for fy, r in cement.items():
            self.assertLess(float(r["reconstructed_low_mt"]), float(r["reconstructed_high_mt"]), fy)
        others = self.by["1.A.2 other industrial coal (inside the HDIP cement column)"]
        # peak years carry other-industry coal inside the column; the column's own label admits it
        self.assertGreater(float(others["2018-19"]["activity_high_kt"]), 3000)
        self.assertIn("RETAINED", others["2018-19"]["boundary_note"])

    def test_the_brick_band_names_the_stock_confound(self):
        brick = self.by["1.A.2 brick-kiln coal (+ unsplit others)"]
        self.assertIn("STOCKPILE", brick["2023-24"]["boundary_note"])
        self.assertIn("row 1 audit", brick["2023-24"]["boundary_note"])


class TestTheOfficialColumnsAreTheAtoms(unittest.TestCase):
    def test_official_mt_equals_the_reference_atoms(self):
        atoms = defaultdict(float)
        with open(ATOMS, encoding="utf-8") as h:
            for r in csv.DictReader(l for l in h if not l.startswith("#")):
                if r.get("configuration_id", "S_TAN") != "S_TAN" or not r.get("co2e_Mt_AR5"):
                    continue
                fy = (r.get("period_label") or r.get("period_id", "")).replace("FY", "")
                if r["subitem"].startswith("Brick-kiln coal"):
                    atoms[(fy, "brick")] += float(r["co2e_Mt_AR5"])
                elif r["subitem"] == "Clinker calcination CO2":
                    atoms[(fy, "clinker")] += float(r["co2e_Mt_AR5"])
        for r in rows():
            if r["component"].startswith("1.A.2 brick"):
                self.assertAlmostEqual(float(r["official_mt_co2e"]), atoms[(r["fiscal_year"], "brick")], places=3)
            if r["component"].startswith("2.A.1"):
                # the RECONSTRUCTED end is the reference atom (the re-base landed in rc50); the
                # OFFICIAL end is the legacy 0.75 clinker priced at the same factor - never the
                # atom, which is what the rc50 build read and thereby double-applied the delta
                # the bridge prints 3 dp: half an ulp plus the float
                self.assertAlmostEqual(float(r["reconstructed_central_mt"]), atoms[(r["fiscal_year"], "clinker")], delta=0.0006)
                self.assertAlmostEqual(float(r["reconstructed_central_mt"]) - float(r["official_mt_co2e"]),
                                       float(r["delta_vs_official_low_mt"]), delta=0.0011)
                if r["fiscal_year"] == "2015-16":
                    self.assertAlmostEqual(float(r["official_mt_co2e"]), 13.815, places=3)
                    self.assertAlmostEqual(float(r["reconstructed_central_mt"]), 17.779, places=3)
                    self.assertAlmostEqual(float(r["delta_vs_official_low_mt"]), 3.964, places=3)

    def test_nothing_moved_the_reference(self):
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_pins.py")],
                            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)


if __name__ == "__main__":
    unittest.main()
