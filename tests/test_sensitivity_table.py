"""Sensitivity scenarios must re-slice the audited total consistently (main case unchanged)."""
import os
import sys
import unittest


def _agriculture_total_Mt():
    """The sector total, from the engine rather than from a literal.

    This was pinned at 221.09 and 221.22 across four test files, and every one of them broke
    when the sector was harmonised onto FY2023-24 - a change in the reporting period, not in
    any of the properties these tests exist to protect. The magnitude belongs to the engine;
    what a benchmark test owns is whether the benchmark moves it."""
    from pkinv.core import registry
    from pkinv.core.components import enrich_co2e
    sector = registry.get("agriculture")
    comps = sector.build_components(sector.load_data())
    enrich_co2e(comps)
    return sum(c["co2e_Mt_AR5"] for c in comps)


from pkinv.eval import sensitivity_table as st  # noqa: E402


class TestSensitivity(unittest.TestCase):
    def setUp(self):
        self.rows, self.total0 = st.scenarios()
        self.by = {r["scenario"]: r for r in self.rows}

    def test_main_case_is_the_audited_total(self):
        # The audited total is the engine's, not a literal - see _agriculture_total_Mt.
        # + 0.08 (FracGASF product-weighted) + 0.05 (NOx-N restored to the synthetic volatilisation
        # pool, which Eq 11.9 defines on NH3-N + NOx-N). See n_ledger_runs.py.
        main = self.rows[0]
        self.assertAlmostEqual(main["total"], _agriculture_total_Mt(), places=1)
        self.assertAlmostEqual(main["delta"], 0.0, places=6)

    def test_ef1_aggregate_roughly_doubles_the_soils_category(self):
        """EF1 is a direct multiplier on the direct-N2O term, so doubling it from 0.005 to the
        2006 aggregate 0.010 must roughly double managed soils.

        Asserted as a RATIO. The literal it replaces (near 39 Mt) had already been rewritten
        once when a manure-boundary correction shrank the nitrogen applied to soils, and broke
        again when the sector moved to FY2023-24 with a higher fertiliser offtake - neither of
        which is a fact about how EF1 scales, which is what this test is for."""
        r = self.by["Soil EF1 = 0.010 (2006 aggregate)"]
        base = self.by["Soil EF1 = 0.005 (IPCC 2019, primary)"]["soils"] \
            if "Soil EF1 = 0.005 (IPCC 2019, primary)" in self.by else self.rows[0]["soils"]
        self.assertGreater(r["soils"] / base, 1.25, "doubling EF1 barely moved soils")
        self.assertLess(r["soils"] / base, 2.0,
                        "soils cannot more than double: only the DIRECT term scales with EF1")
        self.assertGreater(r["total"], self.total0)

    def test_cui_anchor_matches_benchmark(self):
        """EF1=0.0055 should reproduce the Cui-2021 managed-soils benchmark.

        Read from data/benchmarks.csv rather than pinned: the point is agreement with the
        published empirical factor, not a particular megatonne figure. The agreement got
        BETTER when the sector moved onto FY2023-24 - the gap narrowed from roughly 4 percent
        to about 1 - which is the sort of thing a literal would have hidden as a failure."""
        import csv as _csv
        import os as _os
        from pkinv.assets import asset_path
        cui = None
        with open(asset_path(_os.path.dirname(__file__), "..", "data", "benchmarks.csv"),
                  newline="", encoding="utf-8") as handle:
            for row in _csv.DictReader(handle):
                if row["source"].startswith("Cui") and row["engine_category"] == "Managed soils":
                    cui = float(row["value_Mt_co2e"])
        self.assertIsNotNone(cui, "the Cui 2021 benchmark row has gone from benchmarks.csv")
        r = self.by["Soil EF1 = 0.0055 (Cui 2021 empirical)"]
        self.assertAlmostEqual(r["soils"] / cui, 1.0, delta=0.10)

    def test_gleam_row_comes_from_the_full_ledger_rerun(self):
        """The manure scenario must not be re-sliced. EF1 and SFw each touch one category, so
        swapping that category's total is exact; a different management split is not like that,
        because the coupled nitrogen ledger moves managed soils as well as manure management.

        Re-slicing held soils fixed and produced 232.05 Mt against the rerun's 231.13 -- two
        different answers for one scenario in two tables of the same paper. Nothing tested that they
        agreed, which is why they diverged."""
        import sys as _sys, os as _os
        from pkinv.eval import mms_structural_uncertainty as msu
        gleam_row = self.by["Manure MMS = GLEAM 3.0 South-Asia split"]
        rerun = [r for r in msu.scenarios() if "GLEAM" in r["configuration"]][0]
        self.assertAlmostEqual(gleam_row["total"], rerun["national_total_Mt"], places=6)
        self.assertAlmostEqual(gleam_row["soils"], rerun["managed_soils_Mt"], places=6)
        self.assertNotAlmostEqual(gleam_row["soils"], self.rows[0]["soils"], places=2,
                                  msg="soils must move with the management split, not stay fixed")

    def test_rice_scales_linearly_with_sfw(self):
        main_rice = self.rows[0]["rice"]
        awd = self.by["Rice intermittent SFw = 0.52 (AWD)"]["rice"]
        self.assertAlmostEqual(awd, main_rice * 0.52, places=2)

    def test_monotonic_ef1(self):
        cui = self.by["Soil EF1 = 0.0055 (Cui 2021 empirical)"]["soils"]
        agg = self.by["Soil EF1 = 0.010 (2006 aggregate)"]["soils"]
        wet = self.by["Soil EF1 = 0.016 (2019 wet climate)"]["soils"]
        self.assertTrue(cui < agg < wet)


if __name__ == "__main__":
    unittest.main()
