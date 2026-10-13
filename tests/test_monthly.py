"""The monthly layer: the closure invariant, and the two sectors that carry it.

The invariant under test is the one the product specification names: for every stream the
twelve months sum to the annual inventory exactly, so moving emissions between months can
neither create nor destroy any. These tests are written to fail if that stops being true,
and to fail if a monthly value ever ships without declaring how it was resolved in time.
"""
import csv
import os
import unittest

from pkinv.core import evidence, monthly
from pkinv.paths import OUTPUTS
from pkinv.sectors.industry import combustion as ind_combustion
from pkinv.sectors.industry import monthly as ind_monthly
from pkinv.sectors.industry.data import IndustryData


def _comp(cat, sub, gas, mt):
    return {"category": cat, "subitem": sub, "gas": gas, "emissions_Gg": mt * 1000.0,
            "uncert_pct": 10.0, "co2e_Mt_AR5": mt, "co2e_Mt_AR6": mt}


class TestMonths(unittest.TestCase):
    def test_a_fiscal_year_runs_july_to_june(self):
        m = monthly.months_for(2023)
        self.assertEqual(len(m), 12)
        self.assertEqual(m[0], "202307")
        self.assertEqual(m[-1], "202406")
        self.assertEqual(m, sorted(m))

    def test_a_flat_profile_sums_to_one(self):
        self.assertAlmostEqual(sum(monthly.flat_profile(2023).values()), 1.0, places=12)

    def test_an_empty_profile_raises_rather_than_defaulting_to_uniform(self):
        """A profile carrying no information must say so by being declared T4, not by
        silently becoming a uniform one inside the normaliser."""
        with self.assertRaises(ValueError):
            monthly.normalise({m: 0.0 for m in monthly.months_for(2023)})


class TestClosure(unittest.TestCase):
    def setUp(self):
        self.components = [_comp("C", "a", "CO2", 12.0), _comp("C", "b", "CH4", 3.0)]

    def test_a_profile_reproduces_the_annual_total(self):
        rows = monthly.apply_profile(self.components, monthly.flat_profile(2023),
                                     2023, "T4")
        self.assertEqual(len(rows), 24)
        monthly.check_closure(rows, self.components)   # raises on failure

    def test_a_broken_profile_raises(self):
        """The whole point of the layer: a monthly product that does not close is a
        different inventory wearing the same name, and the run must stop."""
        rows = monthly.apply_profile(self.components, monthly.flat_profile(2023),
                                     2023, "T4")
        rows[0]["co2e_Mt_AR5"] *= 2
        with self.assertRaises(AssertionError):
            monthly.check_closure(rows, self.components)

    def test_a_missing_month_raises(self):
        short = dict(monthly.flat_profile(2023))
        short.pop("202401")
        with self.assertRaises(ValueError):
            monthly.apply_profile(self.components, short, 2023, "T4")

    def test_an_undeclared_temporal_class_raises(self):
        with self.assertRaises(ValueError):
            monthly.apply_profile(self.components, monthly.flat_profile(2023), 2023, "T9")

    def test_the_class_may_vary_by_month(self):
        """One direct edition and eleven reconstructions is the real shape of the OCAC
        year; collapsing it to the weaker class everywhere would discard the observed
        month."""
        rows = monthly.apply_profile(self.components, monthly.flat_profile(2023), 2023,
                                     lambda c, m: "T1" if m == "202307" else "T2")
        self.assertEqual({r["temporal_method"] for r in rows if r["month"] == "202307"},
                         {"T1"})
        self.assertEqual({r["temporal_method"] for r in rows if r["month"] != "202307"},
                         {"T2"})


class TestIndustryMonthly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = IndustryData()
        cls.components, _memo = ind_combustion.compute(cls.data)
        from pkinv.core.components import enrich_co2e
        enrich_co2e(cls.components)
        _components, cls.rows = ind_monthly.rows(cls.data, cls.components)

    def test_twelve_months_close_to_the_annual_sector(self):
        monthly.check_closure(self.rows, self.components)
        self.assertAlmostEqual(sum(r["co2e_Mt_AR5"] for r in self.rows),
                               sum(c["co2e_Mt_AR5"] for c in self.components), places=10)

    def test_every_row_declares_how_it_was_resolved_in_time(self):
        for r in self.rows:
            self.assertIn(r["temporal_method"], evidence.TEMPORAL)
            self.assertTrue(r["basis"])

    def test_the_liquid_months_are_differenced_not_modelled(self):
        """June's cumulative column IS the annual figure, so the reconstruction is an
        arithmetic identity on published numbers rather than a profile."""
        for code in self.data.liquid_products():
            tonnes, _method = ind_monthly.monthly_tonnes(code)
            self.assertAlmostEqual(sum(tonnes.values()),
                                   self.data.liquid_tonnes(code), places=6)

    def test_july_is_observed_and_the_rest_reconstructed(self):
        _shares, methods = ind_monthly.profiles(self.data)
        for code, by_month in methods.items():
            self.assertEqual(by_month["202307"], "T1", code)
            self.assertEqual({v for m, v in by_month.items() if m != "202307"}, {"T2"},
                             code)

    def test_the_gas_streams_declare_their_flat_profile(self):
        """The gas streams ride PBS QIM production as a declared PROXY since rc20:
        T3 (output is not fuel), with the proxy series named in the basis. The old
        contract - flat with the reason on the row - re-arms automatically in any
        year the QIM panel does not reach."""
        gas = [r for r in self.rows if ind_monthly._code_of(r) is None]
        self.assertTrue(gas)
        for r in gas:
            self.assertEqual(r["temporal_method"], "T3")
            self.assertIn("PROXY", r["basis"])
            self.assertIn("QIM", r["basis"])

    def test_the_liquids_are_not_flat(self):
        shares = {}
        for r in self.rows:
            if ind_monthly._code_of(r):
                shares[r["month"]] = shares.get(r["month"], 0.0) + r["co2e_Mt_AR5"]
        self.assertGreater(max(shares.values()), 1.5 * min(shares.values()))

    def test_a_backwards_cumulative_series_would_raise(self):
        """OCAC editions that disagree with each other must stop the run, not be clipped
        to zero and averaged away."""
        real = ind_monthly._panel_rows
        code = self.data.liquid_products()[0]

        def broken():
            out = []
            for r in real():
                r = dict(r)
                if (r["product"] == code and r["month"] == "2024-03"
                        and r["report_kind"] == "cumulative"):
                    r["tonnes"] = "0"
                out.append(r)
            return out

        ind_monthly._panel_rows = broken
        try:
            with self.assertRaises(ValueError):
                ind_monthly.monthly_tonnes(code)
        finally:
            ind_monthly._panel_rows = real


class TestWrittenOutput(unittest.TestCase):
    def test_the_written_file_carries_the_class_on_every_row(self):
        path = os.path.join(OUTPUTS, "industry_monthly_2024.csv")
        if not os.path.exists(path):
            self.skipTest("run python3 -m pkinv.sectors.industry.monthly first")
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        # 360 since rc46 Wave 2: +72 = two solid-fuel streams x three gases x twelve months.
        self.assertEqual(len(rows), 360)
        for r in rows:
            self.assertIn(r["temporal_method"], evidence.TEMPORAL)

    def test_the_residential_file_carries_it_too(self):
        path = os.path.join(OUTPUTS, "residential_monthly_2024.csv")
        if not os.path.exists(path):
            self.skipTest("run python3 -m pkinv.sectors.residential.monthly first")
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        self.assertEqual(len(rows), 108)          # 9 streams x 12 months
        for r in rows:
            self.assertEqual(r["temporal_method"], "T3")


if __name__ == "__main__":
    unittest.main()
