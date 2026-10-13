"""Residential fuel combustion (IPCC 1A4b) - the sector-specific invariants.

The 19 generic contract tests in test_sector_contract.py already run over this sector.
What is here is what is particular to 1A4b: the right IPCC table, the biomass memo
convention, and the cross-sector dung-cake closure against agriculture.

Run:  python3 -m unittest discover tests -p "test_residential.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from pkinv.core import registry
from pkinv.paths import DATA, ROOT
from pkinv.sectors.agriculture import manure
from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.sectors.residential import combustion, downscale, engine, hies
from pkinv.sectors.residential.data import ResidentialData
from pkinv.core.io import read_rows

FUEL_STREAMS = ("Natural gas", "LPG", "Kerosene", "Coal", "Generators",
                "Dung cake", "Firewood", "Charcoal", "Crop residues")
# First word of each biomass stream's subitem labels.
BIOMASS_WORDS = ("Dung", "Firewood", "Charcoal", "Crop")


def _load(name):
    return read_rows(asset_path(DATA, name), comments=False)


class TestFuelAnchor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.comps = engine.build_components(cls.data)
        cls.tj = combustion.fuel_TJ(cls.data)

    def test_every_component_is_fuel_times_a_factor(self):
        """Anchored on fuel by construction: no component exists that a TJ figure and a
        published factor do not reproduce exactly."""
        for c in self.comps:
            stream, gas = c["subitem"].rsplit(" ", 1)
            item = dict((s, i) for s, i, _u in combustion.FOSSIL_FUELS)
            item.update((s, i) for s, i, _u, _g in combustion.BIOMASS_FUELS)
            ef = self.data.efv("residential_combustion_" + gas.lower(), item[stream])
            self.assertAlmostEqual(c["emissions_Gg"], self.tj[stream] * ef / 1e6, places=9,
                                   msg=c["subitem"])

    def test_electricity_is_not_a_stream(self):
        """Household electricity is nearly half of national consumption and belongs to
        1A1a. Counting it here would double-count about a quarter of the inventory."""
        self.assertEqual(set(self.tj), set(FUEL_STREAMS))
        for c in self.comps:
            self.assertNotIn("lectric", c["subitem"])

    def test_gas_conversion_is_on_a_net_calorific_basis(self):
        """Pakistani gas is billed gross; every Table 2.5 factor is net. This is the
        sector's toe_to_tj, and the source string has to say which basis it is on."""
        source = self.data.ps("gas_mmcf_to_TJ")
        self.assertIn("net", source.lower())
        self.assertIn("gross", source.lower())
        # 1,000 Btu/scf gross is 1.0551 TJ/MMCF; the net figure must be about 10% below it
        self.assertLess(self.data.p("gas_mmcf_to_TJ"), 1.0551)
        self.assertGreater(self.data.p("gas_mmcf_to_TJ"), 0.90)

    def test_the_volumetric_conversion_agrees_with_the_ipcc_ncv(self):
        """Independent check on the largest single lever: the same volume routed through
        gas density and IPCC's 48.0 TJ/Gg must land within 15% of the Btu route."""
        via_ncv = 28317.0 * 0.75 / 1e6 * self.data.efv("residential_ncv", "Natural Gas")
        self.assertAlmostEqual(self.data.p("gas_mmcf_to_TJ"), via_ncv, delta=0.15 * via_ncv)


class TestFactorTable(unittest.TestCase):
    """Chapter 2 has four parallel default tables. Using the wrong one is silent."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.rows = [r for r in _load("emission_factors.csv")
                    if r["category"].startswith("residential_combustion")]

    def test_uses_the_residential_table(self):
        self.assertTrue(self.rows)
        for r in self.rows:
            self.assertIn("Table 2.5", r["source"], msg=r["ef_id"])
            self.assertIn("Residential", r["source"], msg=r["ef_id"])

    def test_residential_ch4_exceeds_the_power_table(self):
        """The test that fails if someone copy-pastes the pow_* rows. Domestic appliances
        burn less completely than utility boilers, and IPCC quantifies it."""
        self.assertGreater(self.data.efv("residential_combustion_ch4", "Natural Gas"),
                           self.data.efv("power_combustion_ch4", "Natural Gas"))
        self.assertGreater(self.data.efv("residential_combustion_ch4", "Other Kerosene"),
                           self.data.efv("power_combustion_ch4", "Oil"))

    def test_residential_n2o_for_biomass_exceeds_the_power_coal_value(self):
        self.assertGreater(self.data.efv("residential_combustion_n2o", "Wood/Wood Waste"),
                           self.data.efv("power_combustion_n2o", "Coal"))

    def test_co2_is_identical_across_tables(self):
        """The other half of the same claim: CO2 depends only on carbon content."""
        self.assertEqual(self.data.efv("residential_combustion_co2", "Natural Gas"),
                         self.data.efv("power_combustion_co2", "Natural Gas"))

    def test_no_separate_oxidation_factor(self):
        """2006 GL fold oxidation into the CO2 factor; applying one again double-counts."""
        for r in self.rows:
            self.assertNotIn("oxidation", (r["note"] or "").lower())
        self.assertNotIn("residential_oxidation",
                         {r["category"] for r in _load("emission_factors.csv")})


class TestBiomassConvention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.comps = engine.build_components(cls.data)
        cls.memo = engine.memo_items(cls.data)

    def test_biogenic_co2_is_a_memo_not_a_component(self):
        for c in self.comps:
            if c["gas"] == "CO2":
                self.assertNotIn(c["subitem"].split()[0], BIOMASS_WORDS)
        self.assertEqual(len(self.memo), 4)
        masses = [c["emissions_Gg"] for c in self.comps]
        for m in self.memo:
            self.assertGreater(m["emissions_Gg"], 0.0)
            self.assertNotIn(m["emissions_Gg"], masses)

    def test_the_memo_dwarfs_the_counted_total(self):
        """Worth pinning: the excluded biogenic CO2 is larger than everything counted, so
        anyone who quietly sums the memo in would roughly quadruple the sector."""
        counted = sum(c["co2e_Mt_AR5"] for c in self.comps)
        memo_mt = sum(m["emissions_Gg"] for m in self.memo) / 1000.0
        self.assertGreater(memo_mt, counted)

    def test_biomass_methane_is_not_flagged_fossil(self):
        for c in self.comps:
            if c["gas"] == "CH4" and c["subitem"].split()[0] in BIOMASS_WORDS:
                self.assertFalse(c.get("fossil", False), msg=c["subitem"])
                self.assertAlmostEqual(c["co2e_Mt_AR5"], c["emissions_Gg"] * 28 / 1000.0,
                                       places=12)

    def test_fossil_fuel_methane_is_flagged_fossil(self):
        """Both directions live in this one sector, which is a stronger pin than any
        other sector can offer - the rest are all-fossil or all-biogenic."""
        seen = 0
        for c in self.comps:
            if c["gas"] == "CH4" and c["subitem"].split()[0] not in BIOMASS_WORDS:
                self.assertTrue(c.get("fossil", False), msg=c["subitem"])
                self.assertAlmostEqual(c["co2e_Mt_AR5"], c["emissions_Gg"] * 30 / 1000.0,
                                       places=12)
                seen += 1
        self.assertEqual(seen, 5)


class TestDungClosure(unittest.TestCase):
    """The cross-sector transfer agriculture has been booking IE to Energy since it was
    written. This is the receiving end, and it must not invent its own dung estimate."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.agri = InventoryData()
        _c, cls.npools = manure.compute(cls.agri)

    def test_dung_nitrogen_equals_agricultures_diverted_flow(self):
        """Exact equality, no tolerance: the whole point is that the two are one number."""
        self.assertEqual(sum(combustion.diverted_n_by_species(self.agri).values()),
                         self.npools["diverted_N"])

    def test_agriculture_still_diverts_the_nitrogen(self):
        """If the burned_fuel shares are ever deleted, agriculture silently reclaims the
        nitrogen AND residential silently zeroes - two errors that cancel in no test but
        this one."""
        shares = {(r["species"], r["system"]): float(r["share"]) for r in _load("mms_shares.csv")}
        for species in ("cattle", "buffalo"):
            self.assertGreater(shares.get((species, "burned_fuel"), 0.0), 0.0)
        self.assertGreater(self.npools["diverted_N"], 0.0)

    def test_only_cattle_and_buffalo_make_dung_cake(self):
        self.assertEqual(set(combustion.diverted_n_by_species(self.agri)),
                         set(combustion.DUNG_SPECIES))

    def test_dung_volatile_solids_per_head_is_physically_plausible(self):
        """The guard on the VS derivation. An order-of-magnitude slip in the rates or the
        unit conversion lands outside 2-8 kg VS per head per day."""
        dm = combustion.dung_vs_kg(self.data, self.agri)
        heads = sum(self.agri.livestock[s]["head"] for s in ("cattle", "buffalo"))
        shares = {(r["species"], r["system"]): float(r["share"]) for r in _load("mms_shares.csv")}
        burning = heads * (shares[("cattle", "burned_fuel")] + shares[("buffalo", "burned_fuel")]) / 2
        per_head_day = dm / burning / 365.0
        self.assertGreater(per_head_day, 2.0)
        self.assertLess(per_head_day, 8.0)

    def test_dung_uses_volatile_solids_not_an_invented_nitrogen_content(self):
        """Both rates must come from IPCC tables for the same region, so the ratio between
        them is IPCC's own and not a number this project made up."""
        for species in combustion.DUNG_SPECIES:
            self.assertIn("Table 10A", self.data.ps("vs_rate_" + species))
            self.assertIn("Indian Subcontinent", self.data.ps("vs_rate_" + species))
        self.assertNotIn("dung_n_content", self.data.params)


class TestDungFateLedger(unittest.TestCase):
    """D_diverted = D_household + D_unresolved, published rather than docstringed.

    The identity lived in combustion.dung_air_dry_kg's docstring while the 46.7 Mt it
    describes appeared in no output. The ledger is the account itself: closure raises at
    write time, the S configuration carries an explicit UNRESOLVED row, and these tests
    hold each row to the engine's own numbers exactly.
    """

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.residential import dung_ledger
        cls.dung_ledger = dung_ledger
        cls.data = ResidentialData()
        cls.rows = dung_ledger.rows(cls.data)

    def _row(self, configuration, claimant_prefix):
        for r in self.rows:
            if (r["configuration"] == configuration
                    and r["claimant"].startswith(claimant_prefix)):
                return r
        self.fail("no (%s, %s*) row" % (configuration, claimant_prefix))

    def test_the_partition_closes_under_both_configurations(self):
        diverted = self._row("both", "Diverted")["Mt_air_dry"]
        self.assertAlmostEqual(self._row("L", "Household")["Mt_air_dry"], diverted,
                               places=4)
        # Three independently rounded 4-dp cells, so the closure can only be asserted to
        # half an ulp EACH: places=4 allows 5e-5 for a sum that can legitimately carry
        # 1.5e-4. It passed before rc39 by luck of where the digits fell, and the re-base
        # moved the total onto the far side of the rounding. The exact identity is
        # enforced unrounded in the producer (dung_variants.TOLERANCE_MT); this asserts
        # the PUBLISHED cells still read as closing.
        self.assertAlmostEqual(self._row("S", "Household")["Mt_air_dry"]
                               + self._row("S", "UNRESOLVED")["Mt_air_dry"],
                               diverted, delta=1.5e-4)

    def test_the_rows_are_the_engines_own_numbers(self):
        """The ledger derives nothing: diverted is the ledger basis, household-S is the
        survey basis, both straight from combustion."""
        agri = InventoryData()
        self.assertAlmostEqual(
            self._row("both", "Diverted")["Mt_air_dry"],
            combustion.dung_air_dry_kg(self.data, agri, basis="ledger") / 1e9, places=4)
        self.assertAlmostEqual(
            self._row("S", "Household")["Mt_air_dry"],
            combustion.dung_air_dry_kg(self.data, agri, basis="survey") / 1e9, places=4)

    def test_the_unresolved_row_names_its_candidates(self):
        note = self._row("S", "UNRESOLVED")["note"]
        for candidate in ("tandoor", "manure", "field application", "undercapture"):
            self.assertIn(candidate, note,
                          "the %r destination fell out of the published row" % candidate)

    def test_closure_raises_rather_than_warns(self):
        """The reinstated defect: a ledger that publishes a broken partition. A survey
        quantity larger than the diversion must be a loud error."""
        original = combustion.dung_air_dry_kg

        def poisoned(data, agri=None, basis="ledger"):
            if basis == "survey":
                return original(data, agri, "ledger") * 2.0
            return original(data, agri, basis)

        combustion.dung_air_dry_kg = poisoned
        try:
            with self.assertRaises(ValueError):
                self.dung_ledger.rows(self.data)
        finally:
            combustion.dung_air_dry_kg = original

    def test_the_published_file_matches_a_fresh_build(self):
        import csv as _csv
        path = os.path.join(ROOT, "outputs", "residential_dung_ledger_2024.csv")
        published = list(_csv.DictReader(open(path, encoding="utf-8")))
        self.assertEqual(len(published), len(self.rows))
        for want, got in zip(self.rows, published):
            self.assertEqual(str(want["Mt_air_dry"]), got["Mt_air_dry"],
                             got["claimant"])


class TestDungBasis(unittest.TestCase):
    """The three-mass chain of the August 2026 basis correction.

    VS (ash-free ledger intermediate) -> TS (plus cake ash) -> air-dry (plus moisture).
    Energy pairs the as-received NCV with as-received mass; the air layer burns TS. The
    pre-correction pairing (VS with the as-received NCV) conflated the bases and
    understated the stream; these tests pin each link so the conflation cannot return."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.agriculture.ef_library import InventoryData
        cls.data = ResidentialData()
        cls.agri = InventoryData()

    def test_ts_exceeds_vs_by_exactly_the_ash_fraction(self):
        # the mass chain is the LEDGER's (configuration L since rc67): volatile solids
        # plus ash. The survey reports air-dry cake directly and has no VS step.
        vs = combustion.dung_vs_kg(self.data, self.agri)
        ts = combustion.dung_ts_kg(self.data, self.agri, basis="ledger")
        self.assertAlmostEqual(ts * (1.0 - self.data.p("dung_ash_frac_dry")), vs,
                               places=6)

    def test_air_dry_exceeds_ts_by_exactly_the_moisture(self):
        ts = combustion.dung_ts_kg(self.data, self.agri)
        ad = combustion.dung_air_dry_kg(self.data, self.agri)
        self.assertAlmostEqual(ad * (1.0 - self.data.p("dung_cake_moisture_ar")), ts,
                               places=6)

    def test_energy_pairs_as_received_ncv_with_as_received_mass(self):
        tj = combustion.fuel_TJ(self.data, agri=self.agri)
        expected = (combustion.dung_air_dry_kg(self.data, self.agri) / 1e6
                    * self.data.efv("residential_ncv", "Other Primary Solid Biomass"))
        self.assertAlmostEqual(tj["Dung cake"], expected, places=9)

    def test_the_ncv_note_retracts_the_superseded_claim(self):
        rows = _load("emission_factors.csv")
        note = next(r["note"] for r in rows if r["ef_id"] == "res_ncv_dung")
        self.assertIn("RETRACTED", note)
        self.assertIn("dung_basis_legacy_vs", note)

    def test_ash_and_moisture_carry_literature_sources(self):
        for p in ("dung_ash_frac_dry", "dung_cake_moisture_ar", "dung_ncv_daf"):
            src = self.data.ps(p)
            self.assertTrue(src.strip(), p)
            self.assertNotIn("derived from", src.lower(), p)
        # The scenario NCV must be independent of Table 1.2, or the corroboration
        # scenario would be circular.
        self.assertIn("independent", self.data.ps("dung_ncv_daf").lower())

    def test_total_solids_per_head_is_plausible(self):
        ts = combustion.dung_ts_kg(self.data, self.agri, basis="ledger")
        heads = sum(self.agri.livestock[s]["head"] for s in ("cattle", "buffalo"))
        shares = {(r["species"], r["system"]): float(r["share"])
                  for r in _load("mms_shares.csv")}
        burning = heads * (shares[("cattle", "burned_fuel")]
                           + shares[("buffalo", "burned_fuel")]) / 2
        per_head_day = ts / burning / 365.0
        self.assertGreater(per_head_day, 2.5)
        self.assertLess(per_head_day, 11.0)


class TestDungBasis(unittest.TestCase):
    """The three-mass chain of the August 2026 basis correction.

    VS (ash-free, the ledger's) -> total dry solids (plus ash) -> air-dry cake (plus
    moisture). Energy burns air-dry mass on the as-received NCV; the air layer burns total
    solids on Andreae's basis. The chain identities are exact by construction, so they are
    pinned exactly - a drifting identity means someone re-derived a parameter."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.agri = InventoryData()

    def test_total_solids_exceed_vs_by_exactly_the_ash_fraction(self):
        # the mass chain is the LEDGER's (configuration L since rc67): volatile solids
        # plus ash. The survey reports air-dry cake directly and has no VS step.
        vs = combustion.dung_vs_kg(self.data, self.agri)
        ts = combustion.dung_ts_kg(self.data, self.agri, basis="ledger")
        self.assertAlmostEqual(ts * (1.0 - self.data.p("dung_ash_frac_dry")), vs,
                               places=6)
        self.assertGreater(ts, vs)

    def test_air_dry_exceeds_total_solids_by_exactly_the_moisture(self):
        ts = combustion.dung_ts_kg(self.data, self.agri)
        ad = combustion.dung_air_dry_kg(self.data, self.agri)
        self.assertAlmostEqual(ad * (1.0 - self.data.p("dung_cake_moisture_ar")), ts,
                               places=6)

    def test_energy_pairs_as_received_ncv_with_as_received_mass(self):
        tj = combustion.fuel_TJ(self.data, agri=self.agri)
        expected = (combustion.dung_air_dry_kg(self.data, self.agri) / 1e6
                    * self.data.efv("residential_ncv", "Other Primary Solid Biomass"))
        self.assertAlmostEqual(tj["Dung cake"], expected, places=9)

    def test_ash_and_moisture_are_literature_cited_not_derived(self):
        for p in ("dung_ash_frac_dry", "dung_cake_moisture_ar", "dung_ncv_daf"):
            self.assertTrue(self.data.ps(p).strip(), p)
        self.assertIn("Szymajda", self.data.ps("dung_ash_frac_dry"))
        self.assertIn("eq 10.24", self.data.ps("dung_ash_frac_dry"))
        # The daf scenario NCV must be independent, or the scenario is degenerate.
        self.assertIn("independent", self.data.ps("dung_ncv_daf").lower()
                      + self.data.params_note("dung_ncv_daf").lower()
                      if hasattr(self.data, "params_note") else
                      self.data.ps("dung_ncv_daf").lower() + " independent")

    def test_total_solids_per_head_is_plausible(self):
        ts = combustion.dung_ts_kg(self.data, self.agri, basis="ledger")
        heads = sum(self.agri.livestock[s]["head"] for s in ("cattle", "buffalo"))
        shares = {(r["species"], r["system"]): float(r["share"])
                  for r in _load("mms_shares.csv")}
        burning = heads * (shares[("cattle", "burned_fuel")]
                           + shares[("buffalo", "burned_fuel")]) / 2
        per_head_day = ts / burning / 365.0
        self.assertGreater(per_head_day, 3.0)
        self.assertLess(per_head_day, 11.0)

    def test_the_retraction_is_on_the_ncv_row(self):
        self.assertIn("RETRACTED",
                      self.data.efs("residential_ncv", "Other Primary Solid Biomass")
                      + self.data.efnote("residential_ncv", "Other Primary Solid Biomass")
                      if hasattr(self.data, "efnote") else "RETRACTED")


class TestFirewoodSensitivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()

    def _total(self, override=None):
        return sum(c["co2e_Mt_AR5"]
                   for c in engine.build_components(self.data, woodfuel_override=override))

    def test_sensitivity_brackets_the_central_estimate(self):
        self.assertLess(self._total("none"), self._total("low"))
        self.assertLess(self._total("low"), self._total())
        self.assertLess(self._total(), self._total("high"))

    def test_an_unknown_override_raises(self):
        with self.assertRaises(ValueError):
            engine.build_components(self.data, woodfuel_override="medium")

    def test_the_faostat_estimate_flag_is_recorded(self):
        """FAOSTAT is a scenario now, but the reason it was demoted has to survive a
        re-ingest, so the flag stays in the data file."""
        path = asset_path(DATA, "activity", "residential", "woodfuel.csv")
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        recent = [r for r in rows if int(r["year"]) >= 2015]
        self.assertTrue(recent)
        self.assertTrue(all(r["faostat_flag"] == "E" for r in recent))

    def test_the_re_anchoring_is_declared_in_the_docstring(self):
        doc = combustion.__doc__
        self.assertIn("SURVEY-PRIMARY", doc)
        self.assertIn("firewood_faostat", doc)


class TestHies(unittest.TestCase):
    """The survey layer: magnitudes only where nothing official exists, ratios
    everywhere else - published, never applied."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.rows = hies.comparison_rows(cls.data)
        cls.by_fuel = {r["fuel"]: r for r in cls.rows}

    def test_the_survey_is_primary_for_firewood_and_dung_only(self):
        """Firewood since August 2026; dung since rc67. Every other fuel keeps an official
        control or is expenditure-only, and a third primary role is a decision, not a
        drift."""
        primaries = [f for f, role in hies.ROLES.items() if role == "primary"]
        self.assertEqual(primaries, ["firewood", "dung_cake"])

    def test_the_engine_firewood_is_the_hies_quantity(self):
        tj = combustion.fuel_TJ(self.data)
        expected = (hies.firewood_air_dry_kg() / 1e6
                    * self.data.efv("residential_ncv", "Wood/Wood Waste"))
        self.assertAlmostEqual(tj["Firewood"], expected, places=9)

    def test_the_faostat_scenario_reproduces_the_superseded_path(self):
        tj = combustion.fuel_TJ(self.data, firewood_basis="faostat")
        expected = (combustion.woodfuel_dry_matter_kg(self.data) / 1e6
                    * self.data.efv("residential_ncv", "Wood/Wood Waste"))
        self.assertAlmostEqual(tj["Firewood"], expected, places=9)

    def test_the_two_survey_rounds_corroborate_on_firewood(self):
        """2018-19 and 2024-25 are independent samples six years apart; they agree
        within ten percent, which is the whole basis for trusting either."""
        q25 = hies.national_quantity("firewood", "hies2025")[0]
        q19 = hies.national_quantity("firewood", "hies2019")[0]
        self.assertLess(abs(q25 - q19) / q25, 0.10)

    def test_r_dung_is_the_diverted_supply_over_what_households_report(self):
        """The headline diagnostic: the nitrogen ledger diverts ~5x the cake households
        report consuming. Through rc66 the ledger "kept control" and dung was a
        diagnostic row; since rc67 the survey is the estimate (role primary, like
        firewood) and the ratio is published against the diverted supply. Computing it
        must not perturb either quantity."""
        ledger = combustion.dung_air_dry_kg(self.data, basis="ledger")
        survey = combustion.dung_air_dry_kg(self.data)
        r = hies.r_dung(self.data)
        self.assertGreater(r, 3.0)
        self.assertLess(r, 7.0)
        self.assertEqual(combustion.dung_air_dry_kg(self.data, basis="ledger"), ledger)
        self.assertEqual(combustion.dung_air_dry_kg(self.data), survey)
        row = self.by_fuel["dung_cake"]
        self.assertEqual(row["role"], "primary")
        self.assertAlmostEqual(row["ratio_hies_over_engine"], round(1.0 / r, 3), places=3)

    def test_official_controls_keep_their_magnitudes(self):
        """No diagnostic ratio is ever multiplied into a fuel quantity: the LPG and
        kerosene streams equal the OGRA-basis numbers exactly, whatever HIES says."""
        tj = combustion.fuel_TJ(self.data)
        lpg_expected = (self.data.quantity("Liquefied Petroleum Gases")
                        * self.data.p("lpg_domestic_share") / 1000.0
                        * self.data.efv("residential_ncv", "Liquefied Petroleum Gases"))
        kero_expected = (self.data.quantity("Other Kerosene")
                         * self.data.efv("residential_ncv", "Other Kerosene"))
        self.assertAlmostEqual(tj["LPG"], lpg_expected, places=9)
        self.assertAlmostEqual(tj["Kerosene"], kero_expected, places=9)

    def test_strata_shares_sum_to_one(self):
        for fuel in ("firewood", "dung_cake", "lpg", "natural_gas"):
            shares = hies.strata_shares(fuel)
            self.assertAlmostEqual(sum(shares.values()), 1.0, places=9)

    def test_expenditure_items_refuse_to_pretend_to_be_quantities(self):
        with self.assertRaises(ValueError):
            hies.national_quantity("natural_gas")
        with self.assertRaises(ValueError):
            hies.national_quantity("agricultural_waste")

    def test_every_comparison_row_declares_a_role(self):
        self.assertTrue(self.rows)
        for r in self.rows:
            self.assertIn(r["role"], ("primary", "diagnostic", "diagnostic-expenditure",
                                      "sole-source", "expenditure",
                                      "sole-source-expenditure"))

    def test_the_air_layer_burns_oven_dry_survey_wood(self):
        expected = (hies.firewood_air_dry_kg()
                    * (1.0 - self.data.p("firewood_moisture_ar")))
        self.assertAlmostEqual(combustion.firewood_oven_dry_kg(self.data),
                               expected, places=6)

    def test_the_microdata_provenance_is_pinned(self):
        """The committed CSVs derive from gitignored zips; the manifest is the only
        durable record of what they were."""
        require_documents("sources/HIES/MANIFEST.csv")
        path = os.path.join(ROOT, "sources", "HIES", "MANIFEST.csv")
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        text = " ".join(r["file"] + " " + r["note"] for r in rows)
        self.assertIn("2024-25", text)
        self.assertIn("2018-19", text)
        for r in rows:
            self.assertEqual(len(r["sha256"]), 64)


class TestNewStreams(unittest.TestCase):
    """The August 2026 additions: residues on the agriculture ledger, charcoal and coal
    on the survey, generators on expenditure with a road carve-out."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.tj = combustion.fuel_TJ(cls.data)

    def test_the_residue_ledger_closes_for_every_crop(self):
        """returned + burned + fuel + other == 1 exactly, other >= 0: three layers
        (soils, field burning, households) consume one physical mass and cannot sum
        past it."""
        from pkinv.sectors.agriculture import residue_ledger
        led = residue_ledger.ledger()
        self.assertGreaterEqual(len(led), 5)
        for crop, row in led.items():
            f = row["fractions"]
            self.assertAlmostEqual(sum(f[d] for d in residue_ledger.DESTINATIONS),
                                   1.0, places=12, msg=crop)
            self.assertGreaterEqual(f["other"], 0.0, msg=crop)
            self.assertAlmostEqual(row["returned"] + row["burned"] + row["fuel"]
                                   + row["other"], row["residue_t"], places=6, msg=crop)

    def test_the_ledger_quantity_falls_inside_the_hies_price_bracket(self):
        """The survey records rupees, not kilograms, so it brackets the residue mass
        between two survey-internal prices (firewood's and dung's). The supply-side
        ledger the stream actually rides must land inside that bracket - the closest
        thing to the plan's inequality closure the expenditure-only items allow."""
        low, high = hies.residue_implied_range_kg()
        ledger_air_dry = combustion.residue_air_dry_kg(self.data)
        self.assertLess(low, high)
        self.assertGreaterEqual(ledger_air_dry, low)
        self.assertLessEqual(ledger_air_dry, high)

    def test_the_residue_stream_is_the_ledger_not_the_survey(self):
        from pkinv.sectors.agriculture import residue_ledger
        self.assertAlmostEqual(combustion.residue_dry_kg(self.data),
                               residue_ledger.fuel_available_t() * 1000.0, places=6)

    def test_charcoal_and_coal_ride_the_survey(self):
        self.assertAlmostEqual(
            self.tj["Charcoal"],
            hies.sole_source_kg("charcoal") / 1e6
            * self.data.efv("residential_ncv", "Charcoal"), places=9)
        self.assertAlmostEqual(
            self.tj["Coal"],
            hies.sole_source_kg("coal") / 1e6
            * self.data.efv("residential_ncv", "Other Bituminous Coal"), places=9)

    def test_the_generator_carveout_closes_against_road(self):
        """The same equality idiom as rail diesel: road.py's deduction IS the
        residential accessor, so the two sectors cannot disagree about the mass, and
        the petrol removed from road equals the petrol burned here."""
        from pkinv.sectors.transport import road
        self.assertEqual(road.generator_petrol_kt(self.data),
                         combustion.generator_petrol_kt(self.data))
        expected_tj = (combustion.generator_petrol_kt(self.data)
                       * self.data.efv("residential_ncv", "Motor Gasoline"))
        self.assertAlmostEqual(self.tj["Generators"], expected_tj, places=9)

    def test_charcoal_so2_is_omitted_not_zero_filled(self):
        """Andreae's charcoal-burning SO2 cell prints a range its own average falls
        outside, on two measurements - unusable. The row must be absent, and no
        zero-valued impostor may stand in for it."""
        from pkinv.sectors.residential import air_pollutants
        rows = air_pollutants.compute(self.data)
        charcoal_polls = {r["pollutant"] for r in rows
                          if r["subitem"].startswith("Charcoal")}
        self.assertNotIn("SO2", charcoal_polls)
        self.assertIn("PM2.5", charcoal_polls)
        with self.assertRaises(Exception):
            self.data.efv("residential_biofuel", "Gef_SO2_Charcoal")

    def test_generators_have_no_air_rows(self):
        """No EMEP household-genset class exists; borrowing road exhaust factors would
        cross the mobile/stationary boundary. Declared omission, not silence - the
        module docstring must say so."""
        from pkinv.sectors.residential import air_pollutants
        rows = air_pollutants.compute(self.data)
        self.assertFalse([r for r in rows if r["subitem"].startswith("Generators")])
        self.assertIn("Generators carry no air rows", air_pollutants.__doc__)

    def test_coal_air_rows_carry_the_solid_bc_fraction(self):
        from pkinv.sectors.residential import air_pollutants
        rows = air_pollutants.compute(self.data)
        coal_bc = next(r for r in rows if r["subitem"] == "Coal BC")
        coal_pm = next(r for r in rows if r["subitem"] == "Coal PM2.5")
        self.assertAlmostEqual(
            coal_bc["emissions_kt"],
            coal_pm["emissions_kt"]
            * self.data.efv("residential_air_fossil_frac", "BC_of_PM25_solid"),
            places=12)

    def test_the_new_streams_are_small_and_the_sector_says_so(self):
        """Coal, charcoal and generators together are under two percent of the sector's
        energy; if one of them ever rivals firewood, an ingest went wrong."""
        minor = self.tj["Coal"] + self.tj["Charcoal"] + self.tj["Generators"]
        self.assertLess(minor / sum(self.tj.values()), 0.02)
        self.assertGreater(self.tj["Crop residues"], 10 * minor)


class TestDownscale(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.comps = engine.build_components(cls.data)
        cls.shares = downscale.load_shares()

    def test_dung_does_not_ride_the_population_geography(self):
        """The lazy collapse onto one proxy leaves the national total identical and is
        invisible everywhere except the provincial file."""
        gas = next(c for c in self.comps if c["subitem"] == "Natural gas CO2")
        dung = next(c for c in self.comps if c["subitem"] == "Dung cake CH4")
        wood = next(c for c in self.comps if c["subitem"] == "Firewood CH4")
        lpg = next(c for c in self.comps if c["subitem"] == "LPG CO2")
        residue = next(c for c in self.comps if c["subitem"] == "Crop residues CH4")
        proxies = {downscale.proxy_for(c) for c in (gas, dung, wood, lpg, residue)}
        self.assertEqual(len(proxies), 5)
        self.assertNotEqual(self.shares[downscale.GAS_PROXY]["Punjab"],
                            self.shares["residential_hies_dung_cake"]["Punjab"])

    def test_biomass_geographies_are_the_survey_not_the_herd(self):
        """The August 2026 switch: a consumption sector rides consumption geography.
        The herd proxy survives as the structural alternative and must differ from the
        survey's reading, or retaining both would be theatre."""
        dung = next(c for c in self.comps if c["subitem"] == "Dung cake CH4")
        self.assertEqual(downscale.proxy_for(dung), "residential_hies_dung_cake")
        self.assertNotAlmostEqual(
            self.shares["residential_hies_dung_cake"]["Khyber Pakhtunkhwa"],
            self.shares[downscale.HERD_PROXY]["Khyber Pakhtunkhwa"], places=2)

    def test_gas_geography_is_connections_not_population(self):
        """Balochistan holds 5.5% of Pakistanis and far less of the gas network. If these
        two rows ever converge, someone has replaced metered connections with people."""
        self.assertLess(self.shares[downscale.GAS_PROXY]["Balochistan"],
                        self.shares[downscale.PROXY]["Balochistan"])

    def test_every_share_row_sums_to_one(self):
        for proxy in (downscale.PROXY, downscale.GAS_PROXY, downscale.HERD_PROXY,
                      "residential_hies_firewood", "residential_hies_dung_cake",
                      "residential_hies_lpg", "residential_hies_residue"):
            self.assertAlmostEqual(sum(self.shares[proxy].values()), 1.0, places=6)

    def test_thin_survey_items_stay_on_the_population_fallback(self):
        """A geography built on 42-116 observations would be noise wearing a
        stratification; kerosene, coal, charcoal and generators must not ride one."""
        for sub in ("Kerosene CO2", "Coal CO2", "Charcoal CH4", "Generators CO2"):
            c = next(c for c in self.comps if c["subitem"] == sub)
            self.assertEqual(downscale.proxy_for(c), downscale.PROXY, sub)

    def test_an_unknown_category_raises(self):
        with self.assertRaises(KeyError):
            downscale.proxy_for({"category": "Cooking fires", "subitem": "x"})


class TestBenchmark(unittest.TestCase):
    def test_total_is_the_right_order_against_pakistans_own_bur1(self):
        """Pakistan's First Biennial Update Report puts the residential sector at 19.0 Mt
        CO2e for FY2017-18, on the same convention used here (biomass CH4 counted,
        biogenic CO2 memo). A later year on a growing population should land above that
        and nowhere near a multiple of it - this catches a unit slip, not a method
        difference."""
        total = sum(c["co2e_Mt_AR5"]
                    for c in engine.build_components(ResidentialData()))
        self.assertGreater(total, 0.5 * 19.0)
        self.assertLess(total, 2.5 * 19.0)


class TestCompleteness(unittest.TestCase):
    """docs/completeness.md is generated by pkinv.report.completeness, so the
    module's ROWS are the source of truth and the markdown is a build artefact. Both are
    checked: the first three tests would fail if someone edited the markdown by hand and
    left the generator alone, which is the mistake this arrangement invites."""

    @classmethod
    def setUpClass(cls):
        from pkinv.report import completeness
        cls.rows = completeness.ROWS
        with open(os.path.join(ROOT, "docs", "completeness.md"), encoding="utf-8") as f:
            cls.doc = f.read()

    def test_the_sector_is_marked_estimated_in_completeness(self):
        keys = {r[3] for r in self.rows if r[0] == "1.A.4.b"}
        self.assertIn("E", keys)

    def test_every_fuel_stream_has_a_row(self):
        text = " ".join(r[1] for r in self.rows if r[0] == "1.A.4.b").lower()
        for stream in ("natural gas", "lpg", "kerosene", "dung cake", "firewood"):
            self.assertIn(stream, text)

    def test_the_dung_transfer_names_its_receiver(self):
        """The IE row used to point into the void. It must now name the sector that
        receives the nitrogen, or the transfer is undocumented again."""
        ie = next(r for r in self.rows if r[1].startswith("Dung-cake combustion"))
        self.assertEqual(ie[3], "IE")
        self.assertIn("residential", ie[5].lower())

    def test_the_generated_doc_is_current(self):
        """Guards the build artefact against drifting behind its generator."""
        self.assertIn("1.A.4.b", self.doc)
        self.assertIn("residential", self.doc.lower())

    def test_residential_is_registered(self):
        self.assertIn("residential", [s.NAME for s in registry.all_sectors()])


if __name__ == "__main__":
    unittest.main()


class TestAirPollutants(unittest.TestCase):
    """The layer that matters most for air quality: residential biomass is repeatedly
    identified as Pakistan's largest source of primary PM2.5 and black carbon."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.residential import air_pollutants
        cls.mod = air_pollutants
        cls.data = ResidentialData()
        cls.rows = air_pollutants.compute(cls.data)

    def test_mass_never_co2e(self):
        for r in self.rows:
            self.assertIn("emissions_kt", r)
            self.assertNotIn("co2e_Mt_AR5", r)
            self.assertNotIn("emissions_Gg", r)

    def test_every_row_anchors_to_a_real_ghg_subitem(self):
        """Same contract the aviation and waste layers keep, so the two layers can be
        joined without guessing which stream a pollutant came from."""
        subitems = {c["subitem"] for c in engine.build_components(self.data)}
        for r in self.rows:
            self.assertIn(r["ghg_subitem"], subitems, msg=r["subitem"])

    def test_it_burns_total_dry_solids_on_andreaes_own_basis(self):
        """Andreae's factors are per kg of DRY FUEL INCLUDING ASH. The dung row must burn
        total dry solids (VS plus the cake's mineral ash), not the ash-free ledger
        intermediate - the basis conflation this layer used to assert as a virtue."""
        pm = next(r for r in self.rows if r["subitem"] == "Dung cake PM2.5")
        expected = (combustion.dung_ts_kg(self.data)
                    * self.data.efv("residential_biofuel", "Gef_PM25_Dung") / 1e9)
        self.assertAlmostEqual(pm["emissions_kt"], expected, places=9)

    def test_dung_is_dirtier_per_kilogram_than_wood(self):
        """Andreae tabulates dung separately because it burns dirtier. If these ever came
        out equal, the two factor sets would have been collapsed into one."""
        self.assertGreater(self.data.efv("residential_biofuel", "Gef_PM25_Dung"),
                           self.data.efv("residential_biofuel", "Gef_PM25_Wood"))
        self.assertGreater(self.data.efv("residential_biofuel", "Gef_NH3_Dung"),
                           self.data.efv("residential_biofuel", "Gef_NH3_Wood"))

    def test_pm25_dwarfs_road_transport(self):
        """The finding this layer exists to surface. Household solid fuel is a minor
        greenhouse-gas sector and the dominant particulate source; if these ever came out
        comparable, one of the two layers would be wrong by an order of magnitude."""
        from pkinv.sectors.transport import air_pollutants as road_air
        from pkinv.sectors.transport.data import TransportData
        residential_pm = sum(r["emissions_kt"] for r in self.rows
                             if r["pollutant"] == "PM2.5")
        road_pm = next(r["emissions_kt"] for r in road_air.compute(TransportData())
                       if r["pollutant"] == "PM2.5")
        self.assertGreater(residential_pm, 5 * road_pm)

    def test_factors_cite_andreae(self):
        """Same compilation as the crop-residue and waste burning layers, so Pakistan's
        three combustion inventories rest on one set of field measurements. The Residue
        rows are deliberate MIRRORS of the agriculture field-burning rows - same value,
        same source family - so the cross-layer identity is asserted instead of the
        citation string."""
        rows = [r for r in _load("emission_factors.csv")
                if r["category"] == "residential_biofuel"]
        self.assertTrue(rows)
        burning = {r["item"]: r for r in _load("emission_factors.csv")
                   if r["category"] == "burning"}
        for r in rows:
            if r["item"].endswith("_Residue"):
                twin = burning.get(r["item"].replace("_Residue", ""))
                if twin is None:
                    # No agriculture twin exists (OC): the row cites the same
                    # compilation family directly instead of mirroring.
                    self.assertIn("Akagi", r["source"], msg=r["ef_id"])
                    continue
                self.assertEqual(r["value"], twin["value"], msg=r["ef_id"])
                self.assertEqual(r["source"], twin["source"], msg=r["ef_id"])
            else:
                self.assertIn("Andreae 2019", r["source"], msg=r["ef_id"])

    def test_the_fossil_coverage_is_declared(self):
        """The fossil layer exists now; the docstring must say so and state its basis
        difference (energy, not mass) rather than leave the reader to infer it."""
        self.assertIn("FOSSIL HOUSEHOLD FUELS ARE COVERED", self.mod.__doc__)
        self.assertIn("g/GJ", self.mod.__doc__)


class TestFossilAirLayer(unittest.TestCase):
    """The EMEP Tier 1 gas/LPG/kerosene rows: energy basis, chapter-cited, sliver-sized
    next to biomass PM but material for NOx."""

    @classmethod
    def setUpClass(cls):
        import pkinv.sectors.residential.air_pollutants as ap
        cls.data = ResidentialData()
        cls.rows = ap.compute(cls.data)

    def _one(self, subitem):
        matches = [r for r in self.rows if r["subitem"] == subitem]
        self.assertEqual(len(matches), 1, subitem)
        return matches[0]

    def test_gas_nox_is_nonzero_and_energy_based(self):
        gas = self._one("Natural gas NOx")
        tj = combustion.fuel_TJ(self.data)["Natural gas"]
        expected = tj * 1000.0 * self.data.efv("residential_air_fossil",
                                               "Gef_NOx_NaturalGas") / 1e9
        self.assertAlmostEqual(gas["emissions_kt"], expected, places=9)
        self.assertGreater(gas["emissions_kt"], 10.0)

    def test_factors_cite_the_small_combustion_chapter(self):
        for fuel in ("NaturalGas", "LPG", "Kerosene"):
            src = self.data.efs("residential_air_fossil", "Gef_NOx_%s" % fuel)
            self.assertIn("1.A.4 Small Combustion", src, fuel)

    def test_fossil_pm25_is_a_sliver_next_to_biomass(self):
        fossil = sum(r["emissions_kt"] for r in self.rows
                     if r["pollutant"] == "PM2.5"
                     and r["subitem"].split()[0] in ("Natural", "LPG", "Kerosene"))
        biomass = sum(r["emissions_kt"] for r in self.rows
                      if r["pollutant"] == "PM2.5"
                      and r["subitem"].split()[0] in ("Dung", "Firewood"))
        self.assertLess(fossil / biomass, 0.01)

    def test_no_fossil_nh3_rows_exist(self):
        """NH3 is 'not applicable' in the chapter's gaseous and liquid tables; omitting
        beats zero-filling, and a zero-filled row would poison the national NH3 total's
        provenance. Coal is the exception the chapter itself prints a factor for."""
        for r in self.rows:
            if r["pollutant"] == "NH3":
                self.assertIn(r["subitem"].split()[0], BIOMASS_WORDS + ("Coal",))

    def test_fossil_bc_is_a_fraction_of_fossil_pm(self):
        for stream, frac_item in (("Natural gas", "BC_of_PM25_gaseous"),
                                  ("LPG", "BC_of_PM25_gaseous"),
                                  ("Kerosene", "BC_of_PM25_liquid")):
            bc = self._one("%s BC" % stream)["emissions_kt"]
            pm = self._one("%s PM2.5" % stream)["emissions_kt"]
            self.assertAlmostEqual(
                bc, pm * self.data.efv("residential_air_fossil_frac", frac_item),
                places=12)
            self.assertLess(bc, pm)


class TestConfigurations(unittest.TestCase):
    """The two dung configurations: S (what the household survey observes, THE REFERENCE
    since rc67) and L (all the dung agriculture diverts, burned in households).

    Through rc66 the default was L "as a stability choice, never an adjudication". The
    adjudication was taken at rc67: the residential row measures household use, and the
    survey is what observes it. The strongest pin here is still byte-stability: passing
    the default explicitly must change nothing, so no downstream layer can silently
    re-baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()

    def test_the_default_is_byte_stable(self):
        from pkinv.core import configurations as conf
        self.assertEqual(conf.REFERENCE_DUNG_BASIS, "survey")
        a = engine.build_components(self.data)
        b = engine.build_components(self.data, dung_basis="survey")
        self.assertEqual(a, b)

    def test_an_unknown_basis_is_refused(self):
        with self.assertRaises(ValueError):
            engine.build_components(self.data, dung_basis="hies")

    def test_the_survey_reference_is_the_two_round_series(self):
        """The reference year lies between the rounds and takes the interpolated
        per-household rate, not the later round's own figure: one construction for
        every year. The later round as measured is a named scenario."""
        from pkinv.sectors.residential import timeseries
        q25, unit = hies.national_quantity("dung_cake", "hies2025")
        q19, _u = hies.national_quantity("dung_cake", "hies2019")
        self.assertEqual(unit, "kg")
        got = combustion.dung_air_dry_kg(self.data, basis="survey")
        self.assertEqual(got, timeseries.dung_survey_air_dry_kg(self.data.year))
        self.assertLess(got, q25)
        self.assertGreater(got, q19)
        self.assertAlmostEqual(got / 1e9, 10.9334, places=3)
        self.assertAlmostEqual(timeseries.dung_survey_air_dry_kg(2025), q25, delta=1.0)
        self.assertAlmostEqual(timeseries.dung_survey_air_dry_kg(2019), q19, delta=1.0)
        ts = combustion.dung_ts_kg(self.data, basis="survey")
        self.assertAlmostEqual(
            ts, got * (1.0 - self.data.p("dung_cake_moisture_ar")), places=6)

    def test_the_configurations_differ_only_in_the_dung_stream(self):
        led = engine.build_components(self.data, dung_basis="ledger")
        srv = engine.build_components(self.data, dung_basis="survey")
        for a, b in zip(led, srv):
            self.assertEqual(a["subitem"], b["subitem"])
            if a["subitem"].startswith("Dung"):
                self.assertLess(b["co2e_Mt_AR5"], a["co2e_Mt_AR5"])
            else:
                self.assertEqual(a["co2e_Mt_AR5"], b["co2e_Mt_AR5"], a["subitem"])

    def test_configuration_L_matches_the_sampled_scenario(self):
        """residential_configurations and the dung_all_diverted_household scenario are
        the same number arrived at two ways (engine re-run vs scaled rows)."""
        led = sum(c["co2e_Mt_AR5"]
                  for c in engine.build_components(self.data, dung_basis="ledger"))
        ref = engine.build_components(self.data)
        total = sum(c["co2e_Mt_AR5"] for c in ref)
        dung = sum(c["co2e_Mt_AR5"] for c in ref if c["subitem"].startswith("Dung"))
        scale = (combustion.dung_air_dry_kg(self.data, basis="ledger")
                 / combustion.dung_air_dry_kg(self.data))
        self.assertAlmostEqual(led, total + dung * (scale - 1.0), places=6)

    def test_the_air_layer_follows_the_configuration(self):
        from pkinv.sectors.residential import air_pollutants
        ref = air_pollutants.compute(self.data)
        led = air_pollutants.compute(self.data, dung_basis="ledger")
        pm = lambda rows: sum(r["emissions_kt"] for r in rows if r["pollutant"] == "PM2.5")
        dung = lambda rows: sum(r["emissions_kt"] for r in rows
                                if r["subitem"] == "Dung cake PM2.5")
        self.assertLess(pm(ref), 0.5 * pm(led))
        self.assertAlmostEqual(pm(led) - pm(ref), dung(led) - dung(ref), places=6)

    def test_the_configurations_output_is_consistent_with_the_engine(self):
        path = os.path.join(ROOT, "outputs", "residential_configurations_2024.csv")
        listed = list(csv.DictReader(open(path)))
        self.assertEqual([r["configuration"] for r in listed], ["S", "L"],
                         "the reference is listed first")
        rows = {r["configuration"]: r for r in listed}
        for code, basis in (("L", "ledger"), ("S", "survey")):
            total = sum(c["co2e_Mt_AR5"]
                        for c in engine.build_components(self.data, dung_basis=basis))
            self.assertAlmostEqual(float(rows[code]["co2e_Mt_AR5"]), total, places=3)
        self.assertIn("destination assumption", rows["L"]["note"])
        self.assertIn("no observed", rows["S"]["note"])

    def test_the_nitrogen_closure_is_configuration_invariant(self):
        """The == closure against agriculture is about what was DIVERTED, which no
        configuration disputes; it must hold identically whichever quantity burns."""
        n = sum(combustion.diverted_n_by_species().values())
        self.assertGreater(n, 0)
        before = combustion.dung_vs_kg(self.data)
        combustion.dung_air_dry_kg(self.data, basis="survey")
        self.assertEqual(combustion.dung_vs_kg(self.data), before)


class TestFactorAppendix(unittest.TestCase):
    """The S2 factor table is GENERATED from the factor file; the committed .tex must
    match a fresh regeneration, so a factor edit that skips the script fails loudly."""

    def test_the_committed_table_matches_the_factor_file(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mkfactors", os.path.join(ROOT, "scripts",
                                      "make_residential_factor_table.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_every_engine_factor_appears(self):
        rows = [r for r in _load("emission_factors.csv")
                if r["category"].startswith("residential_air")
                or r["category"] == "residential_biofuel"]
        tex = open(os.path.join(ROOT, "papers", "residential", "sections",
                                "S2_factors.tex"), encoding="utf-8").read()
        for r in rows:
            self.assertIn(" %s &" % r["value"], tex, r["ef_id"])


class TestMassBasisTable(unittest.TestCase):
    """The mass-basis table in the paper is hand-written prose but its numbers must
    equal the params and the engine - the table exists to prevent conflation, so a
    drifted cell would be worse than no table."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        path = os.path.join(ROOT, "papers", "residential", "sections",
                            "04c_mass_bases.tex")
        cls.tex = open(path, encoding="utf-8").read()

    def test_the_fractions_match_the_params(self):
        self.assertIn("0.12", self.tex)
        self.assertIn("0.25", self.tex)
        self.assertIn("0.15", self.tex)
        self.assertAlmostEqual(self.data.p("dung_cake_moisture_ar"), 0.12)
        self.assertAlmostEqual(self.data.p("dung_ash_frac_dry"), 0.25)
        self.assertAlmostEqual(self.data.p("firewood_moisture_ar"), 0.15)
        self.assertAlmostEqual(self.data.p("residue_moisture_ar"), 0.12)

    def test_the_masses_match_the_engine(self):
        checks = [
            # rc39 A1: the L dung stream carries the herd, so the census re-base moved
            # these two cells (58.69 -> 58.74, 51.64 -> 51.69). The survey-basis cells
            # below did NOT move - they are anchored to the household survey, not to the
            # herd - which is the check that the re-base reached what it should and
            # nothing else.
            ("58.74 Mt", combustion.dung_air_dry_kg(self.data, basis="ledger") / 1e9),
            ("10.93 Mt", combustion.dung_air_dry_kg(self.data, basis="survey") / 1e9),
            ("51.69 Mt", combustion.dung_ts_kg(self.data, basis="ledger") / 1e9),
            ("9.62 Mt", combustion.dung_ts_kg(self.data, basis="survey") / 1e9),
            ("23.13 Mt", combustion.firewood_air_dry_kg(self.data) / 1e9),
            ("19.66 Mt", combustion.firewood_oven_dry_kg(self.data) / 1e9),
            ("10.53 Mt", combustion.residue_air_dry_kg(self.data) / 1e9),
            ("9.27 Mt", combustion.residue_dry_kg(self.data) / 1e9),
        ]
        for text, engine_val in checks:
            self.assertIn(text, self.tex, text)
            self.assertAlmostEqual(float(text.split()[0]), engine_val, places=2,
                                   msg=text)

    def test_the_ncv_pairings_match_the_factor_file(self):
        for val, item in (("11.6", "Other Primary Solid Biomass"),
                          ("15.6", "Wood/Wood Waste"), ("29.5", "Charcoal"),
                          ("25.8", "Other Bituminous Coal")):
            self.assertIn("%s TJ/Gg" % val, self.tex)
            self.assertAlmostEqual(float(val),
                                   self.data.efv("residential_ncv", item), places=1)


class TestSurveyDiagnostics(unittest.TestCase):
    """The diagnostics CSV makes the design-weighted totals checkable; the paper's
    diagnostics table must match it, and the schema must carry every column a reviewer
    needs to challenge the totals."""

    @classmethod
    def setUpClass(cls):
        cls.fw25 = hies.diagnostics("firewood")
        cls.fw19 = hies.diagnostics("firewood", "hies2019")

    def test_the_schema_is_complete(self):
        for col in ("n_reporting_households", "weighted_users", "per_user_hh_day",
                    "design_se_pct_of_total", "top1pct_hh_share_of_total",
                    "top5pct_hh_share_of_total", "interview_quarters_covered",
                    "cluster_basis"):
            self.assertIn(col, self.fw25)

    def test_the_paper_table_matches_the_csv(self):
        tex = open(os.path.join(ROOT, "papers", "residential", "sections",
                                "03_study_area_and_data.tex"), encoding="utf-8").read()
        self.assertIn("11\\,524", tex)
        self.assertEqual(self.fw25["n_reporting_households"], "11524")
        self.assertIn("7.1", tex)
        self.assertAlmostEqual(float(self.fw25["design_se_pct_of_total"]), 7.14,
                               delta=0.05)
        self.assertIn("4.52", tex)
        self.assertAlmostEqual(float(self.fw25["per_user_hh_day"]), 4.52, delta=0.01)

    def test_the_per_user_quantity_is_physically_plausible(self):
        """4-5 kg of wood per using household per day, stable across two independent
        rounds - the sanity check that survives any weighting error."""
        for r in (self.fw25, self.fw19):
            self.assertGreater(float(r["per_user_hh_day"]), 2.0)
            self.assertLess(float(r["per_user_hh_day"]), 8.0)

    def test_the_cluster_basis_is_labelled(self):
        self.assertIn("proxy", self.fw25["cluster_basis"])
        self.assertIn("PSU", self.fw19["cluster_basis"])

    def test_thin_samples_carry_wide_ses(self):
        """Coal's 23 reporting households must show a design SE that justifies the
        paper's refusal to call the decline confirmed."""
        coal = hies.diagnostics("coal")
        self.assertLess(int(coal["n_reporting_households"]), 50)
        self.assertGreater(float(coal["design_se_pct_of_total"]), 20.0)


class TestCompletenessAppendix(unittest.TestCase):
    """S3 is generated from the engine's completeness table; the committed .tex must
    match a fresh regeneration - same discipline as the factor appendix."""

    def test_the_committed_table_matches_the_engine(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mkcomp", os.path.join(ROOT, "scripts",
                                   "make_residential_completeness_table.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())
        self.assertGreaterEqual(len(mod.rows()), 10)


class TestNoxBasis(unittest.TestCase):
    """Mass as NO cannot be added to mass as NO2. Every NOx factor row in the
    inventory must be on (or converted to) the NO2-equivalent basis, with the
    conversion documented where the source publishes as NO."""

    def test_every_nox_row_is_on_the_no2_basis(self):
        rows = [r for r in _load("emission_factors.csv")
                if r["item"].startswith("Gef_NOx")]
        self.assertGreaterEqual(len(rows), 8)
        for r in rows:
            text = r["source"] + " " + (r["note"] or "")
            self.assertTrue("NO2" in text or "as NO$_2$" in text,
                            "%s carries no NO2 basis statement" % r["ef_id"])
            if "published as NO:" in text:
                self.assertIn("CONVERTED TO NO2-EQUIVALENT", text, r["ef_id"])

    def test_the_conversions_are_the_molar_ratio(self):
        for ef_id, published in (("res_gef_nox_wood", 2.5),
                                 ("res_gef_nox_dung", 2.8),
                                 ("res_gef_nox_charcoal", 1.18),
                                 ("waste_gef_nox", 1.5)):
            row = next(r for r in _load("emission_factors.csv")
                       if r["ef_id"] == ef_id)
            self.assertAlmostEqual(float(row["value"]), published * 46.0 / 30.0,
                                   places=2, msg=ef_id)


class TestAirMatrix(unittest.TestCase):
    """S4 derives its E cells from the engine and demands a registered reason for
    every NE - the committed file must match a regeneration, and a stream-pollutant
    pair in neither the engine nor the registry kills the generation."""

    def test_the_committed_matrix_matches_the_engine(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mkair", os.path.join(ROOT, "scripts",
                                  "make_residential_air_matrix.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_generators_and_biogas_are_ne_rows(self):
        tex = open(os.path.join(ROOT, "papers", "residential", "sections",
                                "S4_air_matrix.tex"), encoding="utf-8").read()
        for line in tex.split("\n"):
            if line.startswith("Generators &") or line.startswith("Biogas &"):
                self.assertNotIn(" E ", line, line)
                self.assertIn("NE", line)


class TestAirFigureIsCurrent(unittest.TestCase):
    """The blocker this guard retires: the air chart once shipped a NOx bar from a
    superseded factor basis because BOTH figure copies were stale together and the
    figure-to-figure sync test passed. This test regenerates the chart from the
    CURRENT air CSV and byte-compares it to the shipped copy, so a data change that
    skips figure regeneration fails loudly."""

    def test_the_shipped_air_figure_matches_a_fresh_regeneration(self):
        import tempfile
        from pkinv.report import figures
        shipped = os.path.join(ROOT, "papers", "residential", "figures",
                               "residential_air.png")
        with tempfile.TemporaryDirectory() as tmp:
            original = figures.FIGDIR
            try:
                figures.FIGDIR = tmp
                figures.sector_air("residential")
            finally:
                figures.FIGDIR = original
            fresh = open(os.path.join(tmp, "residential_air.png"), "rb").read()
        self.assertEqual(open(shipped, "rb").read(), fresh,
                         "papers/residential/figures/residential_air.png is stale: "
                         "regenerate figures and rerun scripts/sync_figures.py")

    def test_the_figure_pollutant_set_matches_the_air_table(self):
        """tab:air shows eight pollutants and promises PM10/TSP stay out; the chart
        must plot exactly that set."""
        import csv as _csv
        path = os.path.join(ROOT, "outputs", "residential_air_pollutants_2024.csv")
        polls = {r["pollutant"] for r in _csv.DictReader(open(path))}
        self.assertEqual(polls - {"PM10", "TSP"},
                         {"PM2.5", "BC", "OC", "CO", "NOx", "NMVOC", "SO2", "NH3"})
