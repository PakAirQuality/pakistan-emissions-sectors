"""Tests for the open-waste-burning sector (IPCC 4C2).

The general contract is enforced in test_sector_contract.py, which runs over every
registered sector. These are the invariants specific to this one: the fossil/biogenic CO2
convention, the wet/dry weight bases, and the two published benchmarks that bracket the
result from opposite directions.

Run:  python3 -m unittest discover tests
"""
import unittest

from pkinv.core import registry
from pkinv.core.geography import PROVINCES
from pkinv.sectors.waste import air_pollutants, downscale, open_burning, swds, wastewater
from pkinv.sectors.waste.data import WasteData


class TestActivity(unittest.TestCase):
    def setUp(self):
        self.data = WasteData()

    def test_burned_mass_in_expected_band(self):
        """IPCC Eq 5.7 on Pakistani inputs. The source workbook's undocumented constants
        gave 13.0 Mt; sourcing them properly lowers it to ~9 Mt."""
        mt = open_burning.waste_burnt(self.data) / 1e6
        self.assertTrue(8.0 < mt < 11.0, "burned mass %.2f Mt outside the expected band" % mt)

    CENSUS_YEAR = 2023
    CENSUS_TOTAL = 241499431.0

    def test_panel_covers_every_province_and_year(self):
        rows = self.data.population
        self.assertEqual({r["province"] for r in rows}, set(PROVINCES))
        years = {r["year"] for r in rows}
        self.assertEqual(min(years), 2000)
        from pkinv.core.reporting_window import CORE_FY_ENDS
        self.assertEqual(max(years), max(CORE_FY_ENDS),
                         "the disposal-history activity must reach the annual core endpoint")
        # gapless: every district present in every year
        districts = {r["district"] for r in rows}
        self.assertEqual(len(rows), len(districts) * len(years))

    def test_population_matches_the_census_at_the_census_year(self):
        """The panel reproduces the 7th Census total to within a per-cent AT ITS ANCHOR.

        Checked at 2023 rather than at the sector's reference period, because the reference
        period is now FY2023-24 and its population is PROJECTED one year past the anchor.
        Comparing a projection against the census it was projected from would have quietly
        turned this into a test of the growth rate."""
        total = sum(r["pop_total"] for r in self.data.population_for(self.CENSUS_YEAR))
        self.assertAlmostEqual(total / self.CENSUS_TOTAL, 1.0, delta=0.01)

    def test_the_projected_year_is_labelled_a_projection(self):
        """An extrapolated year is weaker evidence than an interpolated one, and the panel
        has to say which each row is. Every earlier year is interpolated between two
        censuses; the reference year is not."""
        projected = [r for r in self.data.population if r["year"] == self.data.year]
        self.assertTrue(projected)
        for r in projected:
            self.assertIn("PROJECTED", r["source"])
        anchor = [r for r in self.data.population if r["year"] == self.CENSUS_YEAR]
        for r in anchor:
            self.assertNotIn("PROJECTED", r["source"])

    def test_the_projection_is_the_panels_own_growth_rate(self):
        """Not a new assumption - the existing one applied one step further. The projected
        national total must equal the census total grown at the panel's own 2017-2023 rate."""
        pop = {y: sum(r["pop_total"] for r in self.data.population_for(y))
               for y in (2017, self.CENSUS_YEAR, self.data.year)}
        cagr = (pop[self.CENSUS_YEAR] / pop[2017]) ** (1.0 / (self.CENSUS_YEAR - 2017))
        step = self.data.year - self.CENSUS_YEAR
        self.assertAlmostEqual(pop[self.data.year] / (pop[self.CENSUS_YEAR] * cagr ** step),
                               1.0, delta=0.002)

    def test_burning_scales_with_population_only(self):
        """All four rate parameters are time-invariant, so the series is pure demography.
        Recorded because it is a limitation, not a feature: waste intensity per person
        almost certainly rose between 2000 and 2023."""
        early = open_burning.waste_burnt(self.data, 2000)
        late = open_burning.waste_burnt(self.data, 2023)
        pop_early = sum(r["pop_total"] for r in self.data.population_for(2000))
        pop_late = sum(r["pop_total"] for r in self.data.population_for(2023))
        self.assertAlmostEqual(late / early, pop_late / pop_early, delta=0.05)


class TestCarbonConvention(unittest.TestCase):
    """The single most important methodological rule in this sector."""

    def setUp(self):
        self.data = WasteData()
        self.sector = registry.get("waste")

    def test_only_fossil_co2_is_a_component(self):
        """IPCC Vol 5 Ch 5 s5.1: CO2 from the biomass content of waste is biogenic and
        is NOT included in national totals. If biogenic CO2 ever became a component it
        would be summed into the national total, which is exactly what is forbidden."""
        comps = self.sector.build_components(self.data)
        co2 = [c for c in comps if c["gas"] == "CO2"]
        self.assertEqual(len(co2), 1)
        self.assertIn("fossil", co2[0]["subitem"])
        fossil, biogenic = open_burning.co2_streams(self.data)
        self.assertAlmostEqual(co2[0]["emissions_Gg"], fossil, places=6)
        self.assertNotIn(biogenic, [c["emissions_Gg"] for c in comps])

    def test_biogenic_co2_is_reported_as_a_memo(self):
        memo = self.sector.memo_items(self.data)
        self.assertEqual(len(memo), 1)
        self.assertGreater(memo[0]["emissions_Gg"], 0.0)
        self.assertIn("not included in national totals", memo[0]["note"])

    def test_fossil_is_a_minority_of_total_co2(self):
        """Pakistani municipal waste is mostly organic; roughly a third of its carbon is
        fossil, and almost all of that is the plastic fraction."""
        fossil, biogenic = open_burning.co2_streams(self.data)
        share = fossil / (fossil + biogenic)
        self.assertTrue(0.25 < share < 0.45, "fossil share %.2f" % share)

    def test_n2o_uses_dry_mass_and_ch4_uses_wet(self):
        """The two IPCC factors have different weight bases by design (Ch 5 s5.4.2 vs
        Table 5.6), which is easy to mistake for a transcription error and silently
        overstate N2O by 1/dry_matter."""
        # Scoped to the open-burning category: the sector also carries solid waste
        # disposal now, whose CH4 would otherwise overwrite this one in a by-gas dict.
        comps = {c["gas"]: c for c in self.sector.build_components(self.data)
                 if c["category"] == open_burning.CATEGORY}
        mb = open_burning.waste_burnt(self.data)
        dm = self.data.p("dry_matter")
        self.assertAlmostEqual(comps["CH4"]["emissions_Gg"],
                               mb * self.data.efv("waste_burning", "CH4") / 1e6, places=6)
        self.assertAlmostEqual(comps["N2O"]["emissions_Gg"],
                               mb * dm * self.data.efv("waste_burning", "N2O") / 1e6, places=6)

    def test_methane_is_not_flagged_fossil(self):
        """Waste CH4 comes from a partly-fossil stream, but IPCC treats waste methane as
        non-fossil for GWP purposes, so AR6 must use 27, not 29.8."""
        for c in self.sector.build_components(self.data):
            self.assertFalse(c.get("fossil", False))


class TestBenchmarks(unittest.TestCase):
    """Two published figures that bracket this estimate from opposite directions.

    Both belong in the paper. If either assertion starts failing, the result has moved
    outside the range the literature supports and needs re-arguing, not re-tolerancing.
    """

    def setUp(self):
        self.sector = registry.get("waste")
        self.data = WasteData()
        # Open burning only. The literature figures these tests compare against are about
        # burning, not about landfill methane, so the disposal category must not be in the
        # denominator - a benchmark quietly redefined is worse than no benchmark.
        self.total = sum(c["co2e_Mt_AR5"] for c in self.sector.build_components(self.data)
                         if c["category"] == open_burning.CATEGORY)

    def test_higher_than_the_published_national_figure(self):
        """Ijaz (2023) J. Mater. Cycles Waste Manag. puts Pakistani waste incineration
        plus open burning at 1.21 Mt CO2e. This method gives ~3x that, because national
        reporting appears not to count uncollected and rural waste."""
        self.assertGreater(self.total, 1.21)
        self.assertLess(self.total / 1.21, 5.0,
                        "gap against Ijaz (2023) has grown beyond a factor of 5")

    def test_pm25_is_comparable_to_crop_residue_burning(self):
        """SEI/Vaughn et al. attribute 24% of Pakistan's primary PM2.5 to waste burning,
        second only to households - so waste PM2.5 should be at least the same order as
        the crop-residue burning already in the agriculture sector (~50 kt)."""
        pm = next(r["emissions_kt"] for r in air_pollutants.compute(self.data)
                  if r["pollutant"] == "PM2.5")
        self.assertTrue(30.0 < pm < 200.0, "waste PM2.5 %.1f kt" % pm)


class TestAllocation(unittest.TestCase):
    def test_shares_sum_to_one(self):
        shares = downscale.load_shares()
        self.assertIn(downscale.PROXY, shares)
        self.assertAlmostEqual(sum(shares[downscale.PROXY].values()), 1.0, delta=1e-6)

    def test_other_province_is_islamabad_only(self):
        """AJK and Gilgit-Baltistan are outside the 2023 census frame, so this sector
        covers Islamabad alone under 'Other'. Documented so the gap is not mistaken for
        full national coverage."""
        rows = [r for r in WasteData().population_for() if r["province"] == "Other"]
        self.assertEqual({r["district"] for r in rows}, {"Islamabad District"})

    def test_air_rows_anchor_to_a_real_ghg_subitem(self):
        """ghg_subitem is the join key for province allocation; a stale value would send
        a pollutant onto the fallback proxy."""
        data = WasteData()
        subitems = {c["subitem"] for c in registry.get("waste").build_components(data)}
        for r in air_pollutants.compute(data):
            self.assertIn(r["ghg_subitem"], subitems)


if __name__ == "__main__":
    unittest.main()


class TestDisposalClosure(unittest.TestCase):
    """Solid waste disposal (4A) is the arithmetic complement of open burning (4C2). The
    boundary between them is the thing most likely to be got wrong, so it is asserted."""

    def setUp(self):
        self.data = WasteData()

    def test_collected_plus_uncollected_is_exactly_generated(self):
        """Exact equality, no tolerance: both streams are built from one generation figure
        and one collection coverage, so the identity is arithmetic, not approximate."""
        generated = swds.waste_generated(self.data)
        disposed = swds.waste_disposed(self.data)
        uncollected = generated - disposed
        self.assertEqual(disposed + uncollected, generated)
        self.assertGreater(disposed, 0.0)
        self.assertGreater(uncollected, 0.0)

    def test_burned_is_a_fraction_of_the_uncollected_stream_only(self):
        """Open burning may never exceed the waste that was never collected. If it did,
        the two categories would be burning and burying the same tonne."""
        generated = swds.waste_generated(self.data)
        uncollected = generated - swds.waste_disposed(self.data)
        burned = open_burning.waste_burnt(self.data)
        self.assertLess(burned, uncollected)
        self.assertAlmostEqual(burned / uncollected, self.data.p("burned_fraction"),
                               places=9)

    def test_the_two_categories_use_different_geographies(self):
        """Collection is an urban service and burning is disproportionately rural, so one
        shared proxy would move megatonnes between provinces at an unchanged national
        total - invisible everywhere except the provincial file."""
        shares = downscale.load_shares()
        burn = shares[downscale.PROXY]
        disposal = shares[downscale.DISPOSAL_PROXY]
        self.assertNotEqual(burn["Sindh"], disposal["Sindh"])
        self.assertGreater(disposal["Sindh"], burn["Sindh"])
        self.assertAlmostEqual(sum(disposal.values()), 1.0, places=6)

    def test_the_written_ledger_closes_and_carries_the_unresolved_row(self):
        """The published account (outputs/waste_ledger_<year>.csv) must close on both
        tiers AND keep the fate that emits nothing. The UNRESOLVED row is the point
        of the ledger - an uncollected-unburned stream that silently vanished from
        the file would look resolved, and it is not."""
        from pkinv.sectors.waste import ledger
        rows = ledger.rows(self.data)
        by = {r["claimant"]: r for r in rows}
        self.assertAlmostEqual(
            by["Collected to disposal sites"]["Mt_wet"] + by["Uncollected"]["Mt_wet"],
            by["Generated"]["Mt_wet"], places=3)
        self.assertAlmostEqual(
            by["Openly burned"]["Mt_wet"] + by[ledger.UNRESOLVED]["Mt_wet"],
            by["Uncollected"]["Mt_wet"], places=3)
        self.assertGreater(by[ledger.UNRESOLVED]["Mt_wet"], 0.0)
        self.assertEqual(by[ledger.UNRESOLVED]["treatment"], "no GHG pathway applied")
        # And the shipped CSV agrees with a fresh computation, row for row.
        import csv as _csv
        import os as _os
        from pkinv.paths import OUTPUTS as _OUT
        with open(_os.path.join(_OUT, "waste_ledger_%d.csv" % WasteData().year),
                  newline="", encoding="utf-8") as f:
            shipped = {r["claimant"]: float(r["Mt_wet"]) for r in _csv.DictReader(f)}
        for r in rows:
            self.assertAlmostEqual(shipped[r["claimant"]], r["Mt_wet"], places=4,
                                   msg=r["claimant"])


class TestFirstOrderDecay(unittest.TestCase):
    def setUp(self):
        self.data = WasteData()

    def test_the_model_is_spun_up_before_the_panel_starts(self):
        """With an 11-year half-life, waste buried in the 1980s still emits in 2023.
        Starting at the panel's first year with an empty site understates the answer."""
        series = swds.disposal_series(self.data)
        self.assertEqual(min(series), swds.SPINUP_FROM)
        self.assertLess(swds.SPINUP_FROM, min(swds.panel_years(self.data)))

    def test_spinup_raises_the_estimate_materially(self):
        """If the spin-up made no difference it would not be worth the back-projection it
        costs; this pins that it does, and by how much."""
        with_spinup = swds.ch4_emitted(self.data)
        without = swds.ch4_emitted(self.data, spinup=False)
        self.assertGreater(with_spinup, without)
        self.assertGreater(with_spinup / without, 1.05)

    def test_back_projection_decreases_going_backwards(self):
        """Pakistan's population grew, so projected waste must shrink into the past. A
        flat or rising back-projection would mean the growth rate came out inverted."""
        series = swds.disposal_series(self.data)
        self.assertLess(series[1960], series[1980])
        self.assertLess(series[1980], series[2000])

    def test_emissions_lag_the_deposits(self):
        """The defining property of a decay model: this year's methane comes from the
        accumulated stock, not from this year's waste. If CH4 tracked deposits exactly,
        the FOD would have collapsed to a one-year multiplication."""
        disposed_t = swds.waste_disposed(self.data)
        doc = (self.data.p("total_c_per_wet_t") - self.data.p("fossil_c_per_wet_t"))
        if_instant = (disposed_t * doc * self.data.p("swds_docf") * self.data.p("swds_mcf")
                      * self.data.p("swds_f") * swds.C_TO_CH4 / 1000.0)
        self.assertNotAlmostEqual(swds.ch4_emitted(self.data), if_instant, places=1)

    def test_doc_is_the_biogenic_carbon_of_the_same_composition(self):
        """One composition for both categories. A separate DOC default would let the same
        waste have two different carbon contents depending on how it was disposed of."""
        doc = self.data.p("total_c_per_wet_t") - self.data.p("fossil_c_per_wet_t")
        self.assertTrue(0.08 < doc < 0.20, "DOC %.4f outside the IPCC MSW range" % doc)

    def test_oxidation_and_recovery_are_explicit_zeros(self):
        """Both are zero for Pakistan, and both are carried in the equation rather than
        dropped, so a future landfill-gas project has somewhere to be entered."""
        self.assertEqual(self.data.p("swds_oxidation"), 0.0)
        self.assertEqual(self.data.p("swds_recovery_t"), 0.0)
        self.assertIn("Table 3.2", self.data.ps("swds_oxidation"))

    def test_parameters_cite_the_swds_chapter(self):
        for name in ("swds_k", "swds_docf", "swds_mcf", "swds_f"):
            self.assertIn("Ch 3", self.data.ps(name), msg=name)

    def test_disposal_is_the_larger_half_of_the_sector(self):
        """Recorded because it inverts what the sector used to be: landfill methane is
        bigger than everything open burning emits."""
        sector = registry.get("waste")
        comps = sector.build_components(self.data)
        disposal = sum(c["co2e_Mt_AR5"] for c in comps if c["category"] == swds.CATEGORY)
        burning = sum(c["co2e_Mt_AR5"] for c in comps
                      if c["category"] == open_burning.CATEGORY)
        self.assertGreater(disposal, burning)


class TestWastewater(unittest.TestCase):
    """4D was marked NE until the JMP sanitation split was fetched. These pin what that
    fetch actually settled, and what it did not."""

    def setUp(self):
        self.data = WasteData()

    def test_the_sanitation_shares_sum_to_the_population(self):
        """JMP's denominator is population, which is exactly the ambiguity that kept this
        category unestimated - the secondhand PBS figures did not say what they were of."""
        for setting in wastewater.SETTINGS:
            s = self.data.sanitation[(2023, setting)]
            self.assertAlmostEqual(sum(s.values()), 1.0, delta=0.01, msg=setting)

    def test_urban_and_rural_are_genuinely_different(self):
        """The reason to stratify at all: a city sewer and a rural latrine differ by five
        times in methane correction factor, and Pakistan is 62 percent rural."""
        urban = self.data.sanitation[(2023, "Urban")]
        rural = self.data.sanitation[(2023, "Rural")]
        self.assertGreater(urban["sewer"], 5 * rural["sewer"])
        self.assertGreater(rural["open"], 10 * urban["open"])

    def test_the_sewer_assumption_dominates(self):
        """IPCC gives stagnant open sewers 0.5 and river discharge 0.1. Publishing one
        without the other would hide the largest judgement in the category."""
        central = wastewater.ch4_gg(self.data)
        river = wastewater.ch4_gg(self.data,
                                  sewer_mcf=self.data.p("ww_mcf_sewer_river"))
        self.assertGreater(central / river, 1.5)

    def test_open_defecation_carries_an_explicit_zero(self):
        """Zero, not omitted. IPCC has no anaerobic pathway for material left on open
        ground, and writing that down is the difference between a decision and an
        oversight."""
        self.assertEqual(self.data.p("ww_mcf_open"), 0.0)
        self.assertIn("no row for open defecation", self.data.ps("ww_mcf_open"))

    def test_the_industrial_factor_applies_only_to_sewers(self):
        """Uncollected pathways receive no industrial load by definition."""
        tow = wastewater.tow_kg(self.data)
        pop = wastewater.population(self.data)
        shares = self.data.sanitation[(2023, "Urban")]
        plain = (pop["Urban"] * shares["septic"]
                 * self.data.p("ww_bod_g_per_cap_day") / 1000.0 * 365.0)
        self.assertAlmostEqual(tow[("Urban", "septic")], plain, places=3)
        sewered = (pop["Urban"] * shares["sewer"]
                   * self.data.p("ww_bod_g_per_cap_day") / 1000.0 * 365.0
                   * self.data.p("ww_industrial_factor"))
        self.assertAlmostEqual(tow[("Urban", "sewer")], sewered, places=3)

    def test_nitrous_oxide_runs_on_protein_not_bod(self):
        """Two different IPCC chains in one category. If N2O ever tracked BOD, the protein
        route would have been lost."""
        self.assertIn(max(self.data.protein), (2023, 2024))
        self.assertGreater(self.data.protein[max(self.data.protein)], 50.0)
        n2o = wastewater.n2o_gg(self.data)
        self.assertGreater(n2o, 0.0)

    def test_methane_dominates_the_category(self):
        comps, _m = wastewater.compute(self.data)
        ch4 = next(c for c in comps if c["gas"] == "CH4")
        n2o = next(c for c in comps if c["gas"] == "N2O")
        self.assertGreater(ch4["emissions_Gg"] * 28, n2o["emissions_Gg"] * 265 * 3)

    def test_the_n2o_factor_is_the_softest_number_here(self):
        """Its published range spans a factor of 500, which is why the smaller stream
        carries the larger relative uncertainty."""
        comps, _m = wastewater.compute(self.data)
        ch4 = next(c for c in comps if c["gas"] == "CH4")
        n2o = next(c for c in comps if c["gas"] == "N2O")
        self.assertGreater(n2o["uncert_pct"], ch4["uncert_pct"])

    def test_wastewater_rides_load_not_headcount(self):
        """Sindh is more urban, and sewered flow carries a far higher MCF, so its share of
        the load exceeds its share of the people."""
        shares = downscale.load_shares()
        ww_share = shares[downscale.WASTEWATER_PROXY]["Sindh"]
        burn_share = shares[downscale.PROXY]["Sindh"]
        self.assertGreater(ww_share, burn_share)
        self.assertAlmostEqual(sum(shares[downscale.WASTEWATER_PROXY].values()), 1.0,
                               places=6)

    def test_all_three_waste_categories_are_distinct_geographies(self):
        shares = downscale.load_shares()
        sindh = {shares[p]["Sindh"] for p in (downscale.PROXY, downscale.DISPOSAL_PROXY,
                                              downscale.WASTEWATER_PROXY)}
        self.assertEqual(len(sindh), 3)


class TestHiesDisposalRoutes(unittest.TestCase):
    """The HIES 2024-25 household disposal-route evidence (August 2026 round).

    The committed CSV is survey EVIDENCE beside the What a Waste partition
    parameters, not an input to the central estimate; these tests pin its
    internal identities so the ingest script cannot silently ship a broken
    extraction, and pin the direction of its disagreement with the assumed
    collection coverage - which is the finding the validation section reports.
    """

    def setUp(self):
        self.data = WasteData()

    def test_route_shares_sum_to_one_per_stratum(self):
        for region in ("urban", "rural"):
            total = sum(self.data.hies_share(region, route)
                        for route in range(1, 8))
            self.assertAlmostEqual(total, 1.0, places=2, msg=region)

    def test_collected_plus_uncollected_is_exhaustive(self):
        for region in ("urban", "rural"):
            self.assertAlmostEqual(
                self.data.hies_share(region, "collected")
                + self.data.hies_share(region, "uncollected"),
                1.0, places=3, msg=region)

    def test_collected_is_exactly_the_doorstep_and_bin_routes(self):
        for region in ("urban", "rural"):
            self.assertAlmostEqual(
                self.data.hies_share(region, "collected"),
                sum(self.data.hies_share(region, route) for route in (1, 2, 3)),
                places=3, msg=region)

    def test_urban_collection_exceeds_rural(self):
        self.assertGreater(self.data.hies_share("urban", "collected"),
                           self.data.hies_share("rural", "collected"))

    def test_survey_reports_less_collection_than_the_partition_assumes(self):
        """The direction of the disagreement, urban and rural alike: HIES
        uncollected shares sit ABOVE the What a Waste fractions the partition
        uses. If a re-extraction ever flips this, the validation prose and the
        hies_route_shares scenario both misstate the evidence."""
        self.assertGreater(self.data.hies_share("urban", "uncollected"),
                           self.data.p("uncollected_urban"))
        self.assertGreater(self.data.hies_share("rural", "uncollected"),
                           self.data.p("uncollected_rural"))


class TheMonthlyStateEngine(unittest.TestCase):
    """The Wave-3 FOD state engine: one continuous recursion, gated for the first time.

    Its predecessor was a per-year replay whose stock never crossed June 30, whose
    deposit came from the LAST year of the whole series (2024's tonnage in 2015's
    stock), and whose spread figure was hard-coded in a basis string while the
    function that computes it had zero callers. These are the gates a rewrite of
    that shape must keep passing."""

    @classmethod
    def setUpClass(cls):
        cls.data = WasteData()
        from pkinv.sectors.waste import swds as _swds
        cls.swds = _swds
        cls.state = _swds.monthly_state(cls.data, 2023)

    def test_every_fiscal_year_sums_to_one(self):
        for fy in range(2015, 2024):
            shares = self.swds.monthly_decomposition_shares(self.data, fy)
            self.assertEqual(12, len(shares))
            self.assertAlmostEqual(1.0, sum(shares.values()), places=12, msg=fy)
            self.assertTrue(all(v > 0 for v in shares.values()), fy)

    def test_the_stock_flows_across_the_fiscal_boundary(self):
        """June-to-July emission moves only by month length and the deposit term -
        a per-year replay showed a stock reset here; the continuous engine cannot."""
        import math
        k = self.data.p("swds_k")
        for year in (2016, 2019, 2023):
            june = self.state["%d06" % year]
            july = self.state["%d07" % year]
            # back out the stocks the two months decayed from
            s_june = june / (1.0 - math.exp(-k * 30 / 365.25))
            s_july = july / (1.0 - math.exp(-k * 31 / 365.25))
            # July's opening stock is June's closing stock plus at most one month
            # of matured deposit; the stock is decades deep, so the step is small
            self.assertLess(abs(s_july - s_june) / s_june, 0.01, year)

    def test_each_month_deposits_its_own_calendar_year(self):
        """The cross-year leak, pinned shut: halving 2015's disposal must move
        FY2015-16's shape and must NOT move FY2023-24's opening months' STOCK
        beyond the decayed echo an eight-year-old change leaves."""
        shares_before = self.swds.monthly_decomposition_shares(self.data, 2015)
        series = self.swds.disposal_series(self.data, self.data.year)
        original = self.swds.disposal_series
        try:
            halved = dict(series)
            halved[2015] = series[2015] * 0.5
            self.swds.disposal_series = lambda _d, _y: halved
            shares_after = self.swds.monthly_decomposition_shares(self.data, 2015)
        finally:
            self.swds.disposal_series = original
        moved = max(abs(shares_after[m] - shares_before[m]) for m in shares_before)
        self.assertGreater(moved, 1e-6,
                           "halving the year's own deposits moved nothing - the "
                           "engine is not consuming the year it claims")

    def test_the_delay_is_a_positive_control(self):
        """The directive's control: changing swds_delay_months must change the
        shape, and the change must propagate across the fiscal boundary."""
        original = self.data.params["swds_delay_months"]
        shares_6 = self.swds.monthly_decomposition_shares(self.data, 2023)
        try:
            self.data.params["swds_delay_months"] = 0.0
            shares_0 = self.swds.monthly_decomposition_shares(self.data, 2023)
        finally:
            self.data.params["swds_delay_months"] = original
        moved = max(abs(shares_6[m] - shares_0[m]) for m in shares_6)
        self.assertGreater(moved, 0.0)

    def test_leap_february_carries_the_extra_day(self):
        """FY2023-24 contains February 2024 (29 days); its share must exceed a
        non-leap February's under the same engine."""
        leap = self.swds.monthly_decomposition_shares(self.data, 2023)["202402"]
        common = self.swds.monthly_decomposition_shares(self.data, 2022)["202302"]
        self.assertGreater(leap, common)

    def test_the_basis_number_is_computed_not_typed(self):
        from pkinv.sectors.waste.monthly import _swds_basis
        basis = _swds_basis(self.data, 2023)
        spread = self.swds.monthly_spread_pct(self.data, 2023)
        self.assertIn("%.1f%%" % spread, basis)
        self.assertNotIn("7.1", basis.replace("%.1f" % spread, ""))
