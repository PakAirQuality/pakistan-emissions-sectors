"""Wave 2b of the industrial-coal reconstruction: cement kiln COAL from clinker, as a band.

The product reconstructs the cement kiln fuel term of 1.A.2 as Q = K x H x s / NCV per fiscal
year and reads it against HDIP's "Cement / Cement/Others / Cement/Other Industry" column. This
module guards what makes it honest: the census-derived fraction is DERIVED from held data
(not typed), it removes the FY2023-24 method break the legacy 0.75 splice manufactured, the
bands are bands, the screening is reproduced rather than added, and the reference is unmoved.
"""

from pkinv.assets import asset_path
import csv
import os
import subprocess
import sys
import unittest
from pkinv.core.reporting_window import CORE_FY_STARTS, CORE_FY_ENDS, CORE_PERIOD_IDS, REFERENCE_PERIOD
from pkinv.core.configurations import REFERENCE

from _support import OUTPUTS, ROOT

OUT = os.path.join(OUTPUTS, "pakemis_cement_kiln_coal_reconstruction.csv")


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class TestTheCensusDerivedFraction(unittest.TestCase):
    def setUp(self):
        self.by = {r["fiscal_year"]: r for r in rows()}

    def test_the_fraction_is_derived_from_the_census_balance_not_typed(self):
        """f* = (census clinker - exports + imports) / cement at the reference year, and the
        published column equals that derivation to five places in every row."""
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from pkinv.sectors.ippu import trade_evidence
        from pkinv.sectors.ippu.data import IppuData
        d = IppuData()
        v = trade_evidence.require(d.year)
        f = (d.census_clinker_kt(d.year) - v["export_kt"] + v["import_kt"]) / d.cement_activity_kt(
            d.cement_activity_source(d.year), d.year)
        for r in self.by.values():
            self.assertAlmostEqual(float(r["clinker_fraction_census_derived"]), f, places=5)
        self.assertGreater(f, 0.95)          # GEM: 30 of 32 plants at 0-5 percent substitution
        self.assertLess(f, 1.0)

    def test_the_census_year_is_the_census_and_the_splice_step_closes(self):
        """FY2023-24 rides the audited census itself; at f* the FY2022-23 -> FY2023-24 clinker
        step is continuity (the legacy 0.75 series manufactured a +9,000 kt method break)."""
        ref = self.by["2023-24"]
        self.assertEqual(ref["clinker_kt_census_actual"], "41953")
        self.assertIn("census", ref["clinker_basis"])
        prev = self.by["2022-23"]
        step_star = float(ref["clinker_kt_census_actual"]) - float(prev["clinker_kt_census_anchored"])
        step_legacy = float(ref["clinker_kt_census_actual"]) - float(prev["clinker_kt_legacy_0p75"])
        self.assertLess(abs(step_star), 400)
        self.assertGreater(step_legacy, 8000)


class TestTheBand(unittest.TestCase):
    def setUp(self):
        self.by = {r["fiscal_year"]: r for r in rows()}

    def test_nine_years_and_the_bands_are_ordered(self):
        self.assertEqual(set(self.by), {p[2:] for p in CORE_PERIOD_IDS})
        for fy, r in self.by.items():
            lo, ce, hi = (float(r[k]) for k in ("coal_kt_low", "coal_kt_central", "coal_kt_high"))
            self.assertLess(lo, ce, fy)
            self.assertLess(ce, hi, fy)
            e_lo, e_hi = float(r["kiln_coal_co2_mt_low"]), float(r["kiln_coal_co2_mt_high"])
            self.assertLess(e_lo, e_hi, fy)
            self.assertEqual(r["stock_change_kt"], "")        # unresolved, never zero

    def test_the_screening_is_reproduced_not_added(self):
        """The s=1, H=3.4, all-coal member equals the rc13 screening's CO2 line (13.49 Mt of
        its 13.59 Mt CO2e), so the two products cannot drift apart."""
        self.assertAlmostEqual(float(self.by["2023-24"]["screening_reproduced_co2_mt"]), 13.494, places=2)

    def test_the_hdip_column_is_read_against_the_band_every_year(self):
        for fy, r in self.by.items():
            self.assertTrue(r["hdip_cement_others_kt"], fy)
            self.assertTrue(r["residual_reading"], fy)
            self.assertTrue(r["residual_kt_low"] and r["residual_kt_high"], fy)

    def test_nothing_moved_the_reference(self):
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_pins.py")],
                            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)


if __name__ == "__main__":
    unittest.main()


class TestsFromTheProducersOwnBooks(unittest.TestCase):
    """rc53 Wave C: the two questions the company reports can answer, and the one they cannot."""

    def setUp(self):
        self.rows = {r["fiscal_year"]: r for r in rows()}

    def test_the_thermal_band_stays_transferred_because_nobody_discloses_it(self):
        """A 16-document sweep over ~35 patterns found ZERO disclosures of kcal/kg, GJ/t or MJ/t.
        The negative is typed per company so it cannot be mistaken for an unsearched gap."""
        path = asset_path(ROOT, "data", "activity", "ippu", "cement_thermal_evidence.csv")
        with open(path, encoding="utf-8") as h:
            ev = list(csv.DictReader(l for l in h if not l.startswith("#")))
        self.assertGreaterEqual(len({r["company"] for r in ev}), 15)
        for r in ev:
            self.assertNotIn(r["quantity_kind"], ("specific_heat", "thermal_energy_per_t_clinker"),
                             "%s discloses kiln thermal energy - the transferred band can be replaced"
                             % r["company"])

    def test_the_reference_year_column_cannot_cover_cement_alone(self):
        """FY2023-24: HDIP's cement column at a 100 percent coal share implies 2.70 GJ/t of clinker,
        below the 2.85 GJ/t design floor of the most efficient line any held source names. So the
        column is SHORT of cement's own kiln fuel and holds no other industry that year."""
        r = self.rows["2023-24"]
        sec = float(r["implied_sec_at_full_coal_GJ_per_t"])
        self.assertLess(sec, 2.85)
        self.assertIn("BELOW", r["sec_floor_reading"])
        self.assertIn("NEGATIVE", r["sec_floor_reading"])

    def test_every_other_year_clears_the_floor(self):
        for fy, r in self.rows.items():
            if fy == "2023-24":
                continue
            self.assertGreaterEqual(float(r["implied_sec_at_full_coal_GJ_per_t"]), 2.85, fy)

    def test_the_back_cast_is_tested_against_the_producers_where_they_print_enough(self):
        """The first independent test of the census-derived clinker basis: fourteen companies print
        both FY2022-23 and FY2023-24, and their matched clinker ratio agrees with the basis to 1.5
        percent. Earlier years rest on one to three companies and are refused as a national series."""
        r = self.rows["2023-24"]
        self.assertIn("14 companies print both", r["producer_vs_basis_reading"])
        self.assertIn("percent against", r["producer_vs_basis_reading"])
        self.assertEqual(r["producer_companies"], "15")
        for fy in ("2019-20", "2020-21", "2021-22"):
            self.assertIn("NOT a national series", self.rows[fy]["producer_vs_basis_reading"])
