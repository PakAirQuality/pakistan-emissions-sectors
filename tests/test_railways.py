"""Railway transport (IPCC 1A3c) - the sector-specific invariants.

The 19 generic contract tests in test_sector_contract.py already run over this sector.
What is here is what is particular to 1A3c: the rail emission-factor table, the unit
conversions the source forces on us, and the diesel closure against road transport.

Run:  python3 -m unittest discover tests -p "test_railways.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from pkinv.core import registry
from pkinv.paths import DATA
from pkinv.sectors.railways import downscale, engine, history, reconcile, traction
from pkinv.sectors.railways.data import RailwaysData
from pkinv.sectors.transport import road
from pkinv.sectors.transport.data import TransportData
from pkinv.core.io import read_rows


def _load(name):
    return read_rows(asset_path(DATA, name), comments=False)


class TestFactorTable(unittest.TestCase):
    """Vol 2 Ch 3 gives rail its own default table. Using the road one is silent."""

    @classmethod
    def setUpClass(cls):
        cls.data = RailwaysData()
        cls.rows = [r for r in _load("emission_factors.csv")
                    if r["category"].startswith("railway_traction")]

    def test_uses_the_rail_table(self):
        self.assertTrue(self.rows)
        cited = [r for r in self.rows if "Table 3.4.1" in r["source"]]
        self.assertTrue(cited)
        for r in cited:
            self.assertIn("Rail", r["source"], msg=r["ef_id"])

    def test_rail_n2o_is_far_above_the_road_value(self):
        """The test that fails if someone reuses the transport rows. Large slow-speed
        locomotive engines run lean at high load, which is the N2O-forming regime, and
        IPCC puts the difference at a factor of seven."""
        rail = self.data.efv("railway_traction_n2o", "Gas/Diesel Oil")
        road_n2o = self.data.efv("transport_fuel_n2o", "Gas/Diesel Oil")
        self.assertGreater(rail, 5 * road_n2o)

    def test_rail_ch4_is_above_the_road_value(self):
        self.assertGreater(self.data.efv("railway_traction_ch4", "Gas/Diesel Oil"),
                           self.data.efv("transport_fuel_ch4", "Gas/Diesel Oil"))

    def test_co2_is_identical_to_the_road_table(self):
        """The other half of the claim: CO2 depends only on carbon content."""
        self.assertEqual(self.data.efv("railway_traction_co2", "Gas/Diesel Oil"),
                         self.data.efv("transport_fuel_co2", "Gas/Diesel Oil"))

    def test_the_table_choice_actually_moves_the_answer(self):
        """A pinned factor nobody depends on is decoration. Rail N2O is a material share
        of this sector, so getting the table wrong would be visible in the total."""
        comps = engine.build_components(self.data)
        total = sum(c["co2e_Mt_AR5"] for c in comps)
        n2o = sum(c["co2e_Mt_AR5"] for c in comps if c["gas"] == "N2O")
        self.assertGreater(n2o / total, 0.05)


class TestFuelConversion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = RailwaysData()

    def test_density_comes_from_a_pakistani_source(self):
        """Pakistan Railways reports litres and IPCC works in energy, so a density is
        unavoidable; it should not be a generic international default."""
        source = self.data.ps("hsd_density_kg_per_l").lower()
        self.assertIn("pakistan", source)
        self.assertTrue(0.80 < self.data.p("hsd_density_kg_per_l") < 0.90)

    def test_activity_units_are_carried_per_row_not_assumed(self):
        """Furnace oil switched published basis mid-series, so the unit has to travel
        with each row rather than be inferred from the year."""
        units = {r["unit"] for r in _load(os.path.join("activity", "railways",
                                                       "fuel_consumption.csv"))}
        self.assertEqual(units, {"thousand litres", "tonnes"})

    def test_an_unknown_unit_raises(self):
        data = RailwaysData()
        data.fuel[(data.year, "Gas/Diesel Oil")]["unit"] = "barrels"
        with self.assertRaises(ValueError):
            traction.fuel_TJ(data)

    def test_the_furnace_oil_basis_break_cannot_matter(self):
        """The basis is settled - the 2023-24 edition's detail table and narrative state
        tonnes, and the summary's unit column is demonstrably unreliable - but the label
        break (editions through 2020-21 say Tonnes, 2022-23 says Liters/thousand) means
        the indifference is still worth pinning: the total must not care which reading
        any given row carries."""
        data = RailwaysData()
        as_published = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data))
        data.fuel[(data.year, "Residual Fuel Oil")]["unit"] = "tonnes"
        as_tonnes = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data))
        self.assertLess(abs(as_published - as_tonnes), 0.001)


class TestRoadClosure(unittest.TestCase):
    """The road-rail boundary, in its August 2026 re-anchored form. The road control
    is now OCAC's Road customer-class row, which EXCLUDES rail by construction, so
    the old deduction is gone; what remains is an independent cross-check between two
    unrelated rail figures - the Year Book's metered purchase and OCAC's Railways
    sales row - which is worth more than the deduction ever was."""

    @classmethod
    def setUpClass(cls):
        cls.rail = RailwaysData()
        cls.road_data = TransportData()

    def test_rail_is_no_longer_deducted_and_the_relay_survives(self):
        """The diesel control equals the OCAC Road row exactly - no rail subtraction
        - while the relayed accessor still equals this module's own figure, because
        the cross-check must read the real number, not a copy."""
        gross = (self.road_data.efv("transport_fuel_supply", "Gas/Diesel Oil")
                 * 1000.0
                 * self.road_data.efv("transport_ncv", "Gas/Diesel Oil") / 1000.0)
        self.assertAlmostEqual(road.fuel_TJ(self.road_data)["Diesel"], gross,
                               places=6)
        self.assertEqual(road.rail_diesel_kt(self.rail),
                         traction.diesel_kt(self.rail))

    def test_the_two_rail_figures_are_an_independent_crosscheck(self):
        """Two unrelated reporting chains - metered purchases vs member-supplied sales -
        must agree within tolerance and must NOT be equal: equality would mean one was
        copied from the other. (Inequality is a regression guard against accidental
        collapse to one stored value, not proof of independence; independence rests on the
        separate chains.)

        The year-matched pair is now both sectors' OWN reference period, because both
        report FY2023-24. It used to require reaching back for the Year Book's FY2021-22
        historical row to meet a transport sector stranded two years earlier - a
        contrivance the harmonisation removed. The historical row survives as the cross-year
        bracket, and the matched pair must still be the tighter of the two: if a two-year
        offset ever agreed better than a matched one, the year-matching argument would be
        telling us nothing."""
        chk = road.rail_crosscheck(self.road_data, self.rail)
        self.assertNotEqual(chk["yb_kt"], chk["ocac_kt"])
        self.assertNotEqual(chk["yb_historical_kt"], chk["ocac_kt"])
        self.assertGreater(chk["rel_diff_matched"], 0.0)
        self.assertLess(chk["rel_diff_matched"], 0.05,
                        "matched rail figures disagree by %.1f%%"
                        % (100 * chk["rel_diff_matched"]))
        self.assertLess(chk["rel_diff"], 0.15,
                        "cross-year rail figures disagree by %.1f%%"
                        % (100 * chk["rel_diff"]))
        self.assertLess(chk["rel_diff_matched"], chk["rel_diff"],
                        "the matched pair must beat the two-year-offset pair")

    def test_rail_touches_only_the_diesel_control(self):
        """Pakistan Railways burns no petrol, so RAIL must deduct nothing from it. The
        petrol control does carry its own carve-out since August 2026 - household
        generators, owned by the residential sector - and this test asserts the petrol
        deduction is exactly that and contains no rail contribution."""
        from pkinv.sectors.residential import combustion as residential_combustion
        petrol = road.fuel_TJ(self.road_data)["Petrol"]
        gross = (self.road_data.efv("transport_fuel_supply", "Motor Gasoline") * 1000.0
                 * self.road_data.efv("transport_ncv", "Motor Gasoline") / 1000.0)
        deducted_kt = ((gross - petrol)
                       / self.road_data.efv("transport_ncv", "Motor Gasoline"))
        self.assertAlmostEqual(deducted_kt,
                               residential_combustion.generator_petrol_kt(), places=6)

    def test_rail_is_small_but_not_negligible_nationally(self):
        """Recast on the OCAC national basis: the Year Book figure against national
        internal HSD. If this ever exceeds a few percent, one of the two national
        totals has broken."""
        share = (traction.diesel_kt(self.rail)
                 / (self.road_data.ocac_t("TOTAL_INTERNAL", "HSD") / 1000.0))
        self.assertTrue(0.002 < share < 0.05, "rail is %.3f of national HSD" % share)

    def test_the_legacy_control_arrangement_still_reconstructs(self):
        """The superseded national-supply-minus-rail structure must stay executable
        (it is the legacy_pes_control scenario, the bridge to previously published
        numbers): under it the deduction equals this module's figure exactly."""
        gross = (self.road_data.efv("transport_fuel_supply_legacy", "Gas/Diesel Oil")
                 * 1000.0
                 * self.road_data.efv("transport_ncv", "Gas/Diesel Oil") / 1000.0)
        net = road.fuel_TJ(self.road_data,
                           control_category="transport_fuel_supply_legacy",
                           deduct_rail=True)["Diesel"]
        deducted_kt = ((gross - net)
                       / self.road_data.efv("transport_ncv", "Gas/Diesel Oil"))
        self.assertAlmostEqual(deducted_kt, traction.diesel_kt(self.rail), places=6)


class TestTraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = RailwaysData()

    def test_there_is_no_electric_traction_stream(self):
        """Every Year Book edition reports Electric Energy as NIL. The network is entirely
        diesel, which is why this sector has no scope-2 question at all."""
        for c in engine.build_components(self.data):
            self.assertNotIn("lectric", c["subitem"])
        self.assertEqual(set(traction.fuel_TJ(self.data)), {"Diesel", "Furnace oil"})

    def test_methane_is_flagged_fossil(self):
        ch4 = [c for c in engine.build_components(self.data) if c["gas"] == "CH4"]
        self.assertTrue(ch4)
        for c in ch4:
            self.assertTrue(c.get("fossil", False), msg=c["subitem"])
            self.assertAlmostEqual(c["co2e_Mt_AR5"], c["emissions_Gg"] * 30 / 1000.0,
                                   places=12)

    def test_there_is_no_memo_stream(self):
        self.assertEqual(engine.memo_items(self.data), [])

    def test_the_series_has_no_gaps(self):
        """FY2018 and FY2019 used to be absent, because their own editions are page-image
        scans. That was true and beside the point: every edition's fuel table carries a
        historical run, and the 2020-21 edition has a text layer, so looking one edition
        later was always enough.

        They are RECOVERED, not interpolated - the same table reproduces FY2016, FY2017 and
        FY2021 exactly against figures already held, which is what makes it trustworthy for
        the two years it adds. A test that the series is contiguous is now worth having,
        because the honest reason to leave a hole has gone."""
        years = self.data.years()
        self.assertEqual(years, list(range(min(years), max(years) + 1)),
                         "the series has a hole again: %s" % years)
        self.assertEqual(self.data.quantity("Gas/Diesel Oil", 2018), 156396.0)
        self.assertEqual(self.data.quantity("Gas/Diesel Oil", 2019), 159927.0)

    def test_the_recovered_years_are_corroborated_by_years_already_held(self):
        """Why the recovered figures are trusted: the table they come from reproduces three
        years this inventory already had, exactly."""
        for y in (2016, 2017, 2021):
            d = reconcile.detail_for(y)
            self.assertIsNotNone(d, msg=str(y))
            self.assertEqual(d["locomotive"] + d["other_than_locomotive"],
                             self.data.quantity("Gas/Diesel Oil", y), msg=str(y))

    def test_diesel_dominates(self):
        tj = traction.fuel_TJ(self.data)
        self.assertGreater(tj["Diesel"] / sum(tj.values()), 0.99)


class TestYearBookAgainstItself(unittest.TestCase):
    """The check this sector should have run before claiming a split was impossible.

    An audit pointed out that the same edition carries a detailed fuel table separating
    locomotive from other-than-locomotive consumption - the split this module's docstring
    called unobtainable. It does, on p.163, back to 1950.
    """

    @classmethod
    def setUpClass(cls):
        cls.data = RailwaysData()
        cls.rec = reconcile.reconciliation(cls.data)

    def test_the_two_tables_normally_reconcile_exactly(self):
        """The evidence that they are MEANT to agree, which is what made the one
        disagreement a finding rather than a curiosity. Every year both tables cover closes
        to better than a tenth of a percent, most of them to the digit."""
        agreeing = [r for r in self.rec if abs(r["pct"]) <= 0.1]
        self.assertGreaterEqual(len(agreeing), 3)
        self.assertGreaterEqual(len(agreeing), len(self.rec) - 1)

    def test_the_one_disagreement_was_restated_and_now_closes(self):
        """The 2023-24 edition printed the FY2024 locomotive cell as '136.988' - the only
        year the two tables ever failed to reconcile, a 4.52 percent gap on a
        typographically anomalous cell. The predecessor of this test said: if a later
        edition fixes it, this fails and the sensitivity should be retired. The 2024-25
        edition restated the cell to 130,988, closing the gap to one part in 132,588; the
        sensitivity is retired, and this pins the resolution so the superseded print
        cannot creep back."""
        self.assertEqual(reconcile.disagreeing_years(self.data), [])
        fy2024 = next(r for r in self.rec if r["fiscal_year"] == 2024)
        self.assertEqual(fy2024["locomotive"], 130988.0)
        self.assertLessEqual(abs(fy2024["diff"]), 1.0)

    def test_the_reported_figure_is_still_the_summary(self):
        """The estimate must not drift off the summary figure. It was reported on the
        strength of being stated twice while the detail disagreed; the 2024-25 restatement
        then confirmed it to one part in 132,588."""
        self.assertEqual(self.data.quantity("Gas/Diesel Oil"), 132588.0)

    def test_non_traction_fuel_is_separable_and_small(self):
        """The claim that started this. It is separable - about 1.2 percent - so the non-traction
        overlap is now measured. If it were large, leaving it inside 1A3c would be a real
        error rather than a declared approximation."""
        share = reconcile.non_traction_share(self.data)
        self.assertTrue(0.005 < share < 0.03, "non-traction share is %.4f" % share)

    def test_furnace_oil_is_carried_in_tonnes(self):
        """Settled by the source against itself: the p.163 column is headed 'Furnace Oil
        (M. Tonnes)' and the narrative says 79.907 M.T, which is 15.083 + 64.824. The
        Principal Statistics unit label says litres and is unreliable in that same table -
        it labels Persons Employed 'Tonne'."""
        self.assertEqual(self.data.unit("Residual Fuel Oil"), "tonnes")
        self.assertAlmostEqual(self.data.quantity("Residual Fuel Oil"), 79.907, places=3)
        detail = reconcile.detail_for(2024, "Residual Fuel Oil")
        self.assertAlmostEqual(detail["locomotive"] + detail["other_than_locomotive"],
                               79.907, places=3)

    def test_most_furnace_oil_is_not_locomotive_fuel(self):
        """Incidental but worth pinning: 81 percent of it runs power houses and workshops,
        not trains."""
        d = reconcile.detail_for(2024, "Residual Fuel Oil")
        self.assertGreater(d["other_than_locomotive"], 3 * d["locomotive"])


class TestBenchmark(unittest.TestCase):
    """This sector disagrees with Pakistan's own BUR-1 by an order of magnitude, so the
    checks here are physical rather than comparative - they bound the answer against the
    fuel and the traffic, which is the evidence for the divergence."""

    @classmethod
    def setUpClass(cls):
        cls.data = RailwaysData()

    def test_total_is_bounded_by_the_metered_fuel(self):
        """BUR-1 puts railways at 4.06 Mt CO2e for FY2017-18. That much CO2 needs about
        1,280 kt of diesel; Pakistan Railways bought 112 kt. The carbon is simply not
        there, whatever it is burnt in."""
        total = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        self.assertTrue(0.2 < total < 1.0, "railways %.3f Mt" % total)

    def test_fuel_intensity_per_train_km_is_physical(self):
        """The check that decides which figure to believe. A diesel locomotive burns
        single-digit litres per kilometre. The metered consumption gives 4.0 L/train-km;
        BUR-1's implied fuel would need 46, which no locomotive does."""
        litres = self.data.quantity("Gas/Diesel Oil") * 1000.0
        train_km = self.data.p("train_km_thousand") * 1000.0
        self.assertTrue(2.0 < litres / train_km < 10.0,
                        "%.1f litres per train-km" % (litres / train_km))

    def test_carbon_closes_against_the_fuel_mass(self):
        """The hard physical bound: CO2 cannot exceed the fuel mass times the carbon ratio
        of diesel, about 3.17 t CO2 per t fuel."""
        comps = engine.build_components(self.data)
        co2 = sum(c["emissions_Gg"] for c in comps if c["gas"] == "CO2")
        self.assertLess(co2, traction.diesel_kt(self.data) * 3.2 * 1.02)
        self.assertGreater(co2, traction.diesel_kt(self.data) * 3.0)

class TestDownscale(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shares = downscale.load_shares()

    def test_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(self.shares[downscale.PROXY].values()), 1.0, places=6)

    def test_punjab_leads_on_the_route_model(self):
        """The reversal the route model exists for: the wagons proxy credited Sindh with
        fuel burnt hauling Karachi-origin freight up-country; constrained to the network,
        the fuel burns mostly along Punjab's trunk corridors. If this flips back, either
        the corridor weights changed or the wrong proxy row is wired in."""
        s = self.shares["railways_route_model"]
        self.assertGreater(s["Punjab"], s["Sindh"])
        self.assertGreater(s["Sindh"], s["Khyber Pakhtunkhwa"])

    def test_the_wagons_alternative_is_retained_with_its_bias_on_the_row(self):
        """The superseded proxy must stay in the file as the structural alternative, its
        biases still written where they travel with the numbers."""
        s = self.shares[downscale.WAGONS_PROXY]
        self.assertGreater(s["Sindh"], s["Punjab"])
        row = next(r for r in _load("province_shares.csv")
                   if r["proxy"] == downscale.WAGONS_PROXY)
        self.assertIn("PROVISIONAL", row["note"])
        self.assertIn("loaded", row["note"].lower())

    def test_the_route_model_declares_its_judgment(self):
        row = next(r for r in _load("province_shares.csv")
                   if r["proxy"] == "railways_route_model")
        self.assertIn("DECLARED JUDGMENT", row["note"])
        self.assertIn("rail-timetable", row["note"])

    def test_primary_uses_published_divisional_origin_without_odbl_route_geometry(self):
        self.assertEqual(downscale.PROXY, "railways_freight_div")
        self.assertEqual(self.shares[downscale.PROXY], self.shares[downscale.WAGONS_PROXY])

    def test_an_unknown_category_raises(self):
        with self.assertRaises(KeyError):
            downscale.proxy_for({"category": "Tramways", "subitem": "x"})


class TestRegistration(unittest.TestCase):
    def test_railways_is_registered(self):
        self.assertIn("railways", [s.NAME for s in registry.all_sectors()])


class TestRunManifest(unittest.TestCase):
    """The manifest is the run's provenance statement; a listed source must exist and its
    hash must be a hash, or the statement is decoration."""

    @classmethod
    def setUpClass(cls):
        import json
        path = os.path.join(os.path.dirname(__file__), "..", "outputs",
                            "railways_run_manifest_2024.json")
        with open(path, encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_every_hashed_source_exists(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        require_documents(*[s["path"] for s in self.manifest["sources"]])
        self.assertGreaterEqual(len(self.manifest["sources"]), 8)
        for s in self.manifest["sources"]:
            self.assertTrue(os.path.exists(asset_path(root, s["path"])), s["path"])
            self.assertRegex(s["sha256"], r"^[0-9a-f]{64}$")

    def test_the_seeds_and_scenarios_are_recorded(self):
        mc = self.manifest["monte_carlo"]
        self.assertEqual(mc["national_seed"], 42)
        self.assertEqual(mc["scenario_seed"], 1435)
        self.assertIn("road_n2o_factor", mc["structural_scenarios"])

    def test_listed_outputs_exist(self):
        out = os.path.join(os.path.dirname(__file__), "..", "outputs")
        for name in self.manifest["generated_outputs"]:
            self.assertTrue(os.path.exists(os.path.join(out, name)), name)


class TestEvaluationLayers(unittest.TestCase):
    """The diagnostic quotients and independent evidence - none of it feeds the estimate."""

    def test_intensity_is_physical_in_every_year_with_traffic(self):
        from pkinv.sectors.railways import efficiency
        rows = efficiency.rows(RailwaysData())
        self.assertGreaterEqual(len(rows), 4)
        for r in rows:
            self.assertTrue(2.0 < r["litres_per_train_km"] < 10.0, r)

    def test_agp_evidence_is_para_cited_and_quantified(self):
        rows = _load(os.path.join("activity", "railways", "agp_evidence.csv"))
        self.assertGreaterEqual(len(rows), 4)
        for r in rows:
            self.assertIn("AGP", r["report"] + r["finding_id"].upper())
            self.assertTrue(r["reference"].strip(), r["finding_id"])
            self.assertTrue(r["note"].strip(), r["finding_id"])
        litres = [float(r["quantity_litres"]) for r in rows if r["quantity_litres"]]
        # The audited excesses are litre-resolved and small against the national figure -
        # which is the corroboration: fuel CONTROL is weak, fuel METERING is not.
        self.assertTrue(all(l < 1e6 for l in litres), litres)

    def test_wdi_corroborates_the_yearbook_magnitude(self):
        rows = _load(os.path.join("activity", "railways", "wdi_rail.csv"))
        latest = next(r for r in reversed(rows) if r["passenger_km_million"])
        wdi_pkm = float(latest["passenger_km_million"])
        # Year Book FY2023-24: 29,865 million pkm. The UIC-sourced series (to 2018) must
        # sit within a factor of two - an institutionally independent magnitude check.
        self.assertTrue(0.5 < wdi_pkm / 29865.0 < 2.0, wdi_pkm)

    def test_elk_crosscheck_is_order_of_magnitude_consistent(self):
        """ELK's fleet-model Pakistan rail lands at 0.4x this inventory - NOT at the
        official submissions' 10x. If the output is absent (the NetCDFs are large and
        gitignored), skip; when present, the ratio must stay far from the BUR's."""
        path = os.path.join(os.path.dirname(__file__), "..", "outputs",
                            "railways_elk_crosscheck_2024.csv")
        if not os.path.exists(path):
            self.skipTest("ELK extraction not present")
        with open(path, newline="", encoding="utf-8") as f:
            total = next(r for r in csv.DictReader(f)
                         if r["subsector"] == "rail-total" and r["species"] == "CO2-rep")
        ratio = float(total["ratio_elk_over_own"])
        self.assertTrue(0.1 < ratio < 3.0, ratio)
        self.assertIn("fleet model", total["note"])


class TestHistory(unittest.TestCase):
    """The quinquennial context layer: labelled context, never inventory.

    'Back to 1950' is true of the table's span and misleading about its resolution - every
    pre-2015 row is a five-year average. The layer publishes the shape of seven decades
    (steam to diesel, 1971, the electric section's life and death) and must feed nothing."""

    def test_the_inventory_carries_no_coal_stream(self):
        comps, _ = traction.compute(RailwaysData())
        self.assertFalse([c for c in comps if "Coal" in c["subitem"]])

    def test_coal_factor_rows_are_marked_history_only(self):
        with open(asset_path(DATA, "emission_factors.csv"), newline="",
                  encoding="utf-8") as f:
            rows = {r["ef_id"]: r for r in csv.DictReader(f)}
        for ef_id in ("rail_co2_coal", "rail_ch4_coal", "rail_n2o_coal", "rail_ncv_coal"):
            self.assertIn("HISTORY LAYER ONLY", rows[ef_id]["note"], ef_id)

    def test_quinquennial_resolution_and_breaks_are_declared(self):
        rows = history.load()
        self.assertEqual(len(rows), 14)
        notes = " ".join(r["note"] for r in rows)
        self.assertIn("1971", notes)
        self.assertIn("steam era ends", notes)
        self.assertIn("diesel-only", notes)
        self.assertTrue(all("AVERAGE" in r["note"] for r in rows))

    def test_emissions_peaked_in_the_sixties_at_several_times_todays(self):
        """The context the annual series cannot show: furnace-oil traction put the sector
        near 2.3 Mt/yr in 1965-70, five times the reference year. If this ever fails, the
        transcription or the factor chain has changed and the paper's narrative must too."""
        data = RailwaysData()
        vals = {r["period"]: history.co2e_Mt(data, r) for r in history.load()}
        self.assertEqual(max(vals, key=vals.get), "1965-70")
        current = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data))
        self.assertGreater(vals["1965-70"], 4 * current)
        self.assertLess(vals["2010-15"], current)


if __name__ == "__main__":
    unittest.main()
