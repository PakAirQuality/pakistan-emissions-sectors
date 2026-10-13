"""Scientific and accounting invariants for the IPPU platform."""
import unittest

from pkinv.core import registry
from pkinv.core.gwp import to_co2e
from pkinv.sectors.ippu import (cement, chemicals, completeness, downscale, engine,
                                fgases, material_flows, official_reporting, uncertainty)
from pkinv.sectors.ippu.data import IppuData
from pkinv.core.io import read_rows


class TestCementMaterialBalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = IppuData()
        cls.balance = cement.clinker_balance(cls.data)

    def test_matched_fiscal_trade_totals(self):
        self.assertAlmostEqual(self.data.clinker_trade_kt("export"), 3792.074, places=6)
        self.assertAlmostEqual(self.data.clinker_trade_kt("import"), 26.131, places=6)

    def test_clinker_balance_closes(self):
        self.assertAlmostEqual(material_flows.check_cement_balance(self.balance), 0.0)
        expected = 39566.0 * 0.75 - 26.131 + 3792.074
        self.assertAlmostEqual(self.balance["clinker_production_kt"], expected, places=9)

    def test_trade_correction_has_the_ipcc_sign(self):
        corrected = cement.clinker_balance(self.data, include_trade=True)
        legacy = cement.clinker_balance(self.data, include_trade=False)
        self.assertAlmostEqual(corrected["clinker_production_kt"] -
                               legacy["clinker_production_kt"], 3792.074 - 26.131)
        self.assertGreater(corrected["clinker_production_kt"],
                           legacy["clinker_production_kt"])

    def test_reference_is_the_census_and_the_model_is_the_diagnostic(self):
        """rc30 re-base: the reference is the observed census (41.953170 Mt clinker
        x 0.52 t/t = 21.8156484 Mt CO2); the trade-corrected model survives intact
        as the diagnostic and its own value is asserted through the memo."""
        components = engine.build_components(self.data)
        total = sum(row["co2e_Mt_AR5"] for row in components if row["category"] == cement.CATEGORY)
        self.assertAlmostEqual(total, 21.81564840, places=8)
        # rc52: the module total adds ammonia, steel and lubricants
        self.assertAlmostEqual(sum(row["co2e_Mt_AR5"] for row in components), 25.53535915, places=6)
        _components, memo = cement.compute(self.data)
        census, model = memo
        self.assertEqual(census["activity_basis"], "producer_census")
        self.assertEqual(model["configuration_status"], "diagnostic_model")
        self.assertAlmostEqual(
            model["clinker_production_kt"] *
            self.data.efv("ippu_cement", "Clinker") / 1000.0,
            17.38903036, places=8)

    def test_cement_activity_period_tag_is_corrected(self):
        fy2022 = self.data.cement_activity_kt("sbp_stat_supplement_fy2024", 2022)
        fy2024 = self.data.cement_activity_kt("pbs_qim_fy2023_24", 2024)
        self.assertEqual(fy2022, 48011.0)
        self.assertEqual(fy2024, 39566.0)

    def test_valid_structural_space_is_census_plus_two_diagnostics(self):
        rows = uncertainty.structural_scenarios(self.data)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["scenario_id"], "producer_census_observed")
        self.assertEqual({row["cement_source"] for row in rows[1:]},
                         {"pbs_qim_fy2023_24"})
        self.assertEqual({row["clinker_fraction"] for row in rows[1:]}, {0.75, 0.95})
        self.assertEqual({row["trade_included"] for row in rows[1:]}, {True})
        self.assertTrue(all(row["probability_weight"] == "" for row in rows))

    def test_trade_omission_is_a_method_benchmark(self):
        rows = uncertainty.method_benchmarks(self.data)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(not row["trade_included"] for row in rows))
        self.assertIn("period-tagging error", rows[1]["interpretation"])

    def test_company_clinker_is_the_complete_census_and_the_reference(self):
        """rc30: Fecto's 651,048 t (FY2025 annual report, comparative table) closed
        the census; the sum IS the reference activity, and it now sits ABOVE both
        model inferences - the direction the old floor-vs-model comparison priced
        as a possibility."""
        rows = self.data.company_clinker()
        reported_t = sum(row["clinker_production_t"] for row in rows)
        low_inferred_t = self.balance["clinker_production_kt"] * 1000.0
        high_inferred_t = cement.clinker_balance(self.data, fraction=0.95)[
            "clinker_production_kt"] * 1000.0
        self.assertEqual(len(rows), 16)
        self.assertEqual(reported_t, 41953170.0)
        self.assertEqual(self.data.census_clinker_kt() * 1000.0, reported_t)
        self.assertAlmostEqual(reported_t / low_inferred_t * 100.0, 125.456382,
                               places=5)
        self.assertAlmostEqual(reported_t / high_inferred_t * 100.0, 101.449756,
                               places=5)
        self.assertGreater(reported_t, low_inferred_t)
        self.assertGreater(reported_t, high_inferred_t)

    def test_no_producer_remains_unresolved(self):
        """The inverse of the pre-rc30 test that asserted Fecto's absence: a census
        entity with a missing value would silently turn the reference back into a
        floor, so absence of gaps is now the asserted property."""
        census = self.data.cement_producer_census()
        unresolved = [row for row in census if row["clinker_production_t"] is None]
        self.assertEqual(unresolved, [])
        fecto = next(row for row in census if row["company"] == "Fecto Cement Limited")
        self.assertEqual(fecto["clinker_production_t"], 651048.0)
        self.assertEqual(fecto["clinker_production_status"], "reported")

    def test_flying_exact_production_is_not_capacity_imputation(self):
        row = next(row for row in self.data.company_clinker()
                   if row["company"] == "Flying Cement Company Limited")
        self.assertEqual(row["clinker_production_t"], 322624.0)
        self.assertEqual(row["cement_production_t"], 321500.0)
        self.assertIn("scanned official filing", row["note"])

    def test_company_boundary_audit_keeps_movements_missing(self):
        self.assertEqual(len(self.data.company_boundary_rows), 16)
        fecto = next(row for row in self.data.company_boundary_rows
                     if row["company"] == "Fecto Cement Limited")
        self.assertEqual(fecto["production_basis"],
                         "actual production, annual-report comparative")
        self.assertEqual(fecto["clinker_production_t"], "651048")
        self.assertTrue(all(row["material_balance_status"] == "incomplete"
                            for row in self.data.company_boundary_rows))

    def test_company_flow_gaps_are_not_imputed(self):
        audits = [material_flows.company_clinker_balance(row)
                  for row in self.data.company_clinker()]
        self.assertTrue(all(not row["balance_complete"] for row in audits))
        self.assertTrue(all("opening_clinker_stock_t" in row["missing_fields"]
                            for row in audits))

    def test_calendar_2022_reconstruction_is_matched(self):
        row = cement.calendar_reconstruction(self.data, 2022)
        self.assertEqual(row["cement_activity_kt"], 44331.0)
        self.assertAlmostEqual(row["clinker_exports_kt"], 1341.58)
        self.assertAlmostEqual(row["clinker_imports_kt"], 3.999)
        self.assertAlmostEqual(row["co2_mt"], 17.98463212)


class TestScopeAndCompleteness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = IppuData()
        cls.components = engine.build_components(cls.data)
        cls.matrix = completeness.matrix()

    def test_process_fuel_boundary_is_declared(self):
        self.assertIn("PROCESS EMISSIONS ONLY", cement.__doc__)
        self.assertIn("1A2", cement.__doc__)

    def test_registered_estimate_is_evidence_supported_only(self):
        self.assertEqual({row["gas"] for row in self.components}, {"CO2"})
        self.assertEqual({row["category"] for row in self.components},
                         {"Cement production", "Ammonia production", "Iron and steel production", "Lubricant use"})
        self.assertEqual(registry.get("ippu").GASES, ("CO2",))
        self.assertEqual(engine.memo_items(self.data), [])

    def test_matrix_covers_every_ippu_family(self):
        codes = {row["ipcc_code"] for row in self.matrix}
        for family in ("2.A", "2.B", "2.C", "2.D", "2.E", "2.F", "2.G"):
            self.assertTrue(any(code == family or code.startswith(family + ".")
                                for code in codes), family)

    def test_missing_activity_is_not_silently_zero(self):
        keys = {row["notation_key_2024"] for row in self.matrix}
        self.assertIn("NE", keys)
        # rc52: 2.B.1 is estimated; nitric acid stays NE and soda ash is NA (Solvay) - typed, never zero
        self.assertEqual(next(row for row in self.matrix if row["ipcc_code"] == "2.B.2")["notation_key_2024"], "NE")
        self.assertEqual(next(row for row in self.matrix if row["ipcc_code"] == "2.B.7")["notation_key_2024"], "NA")

    def test_hfc_consumption_is_a_control_not_an_emission(self):
        row = next(row for row in self.data.hfc_control_rows
                   if int(row["calendar_year"]) == 2024)
        self.assertEqual(float(row["value_t_co2e"]), 9815266.0)
        self.assertEqual(row["role"], "control")
        self.assertFalse(any(component["gas"].startswith("HFC")
                             for component in self.components))

    def test_partial_chemical_evidence_does_not_bypass_gate(self):
        rows = chemicals.activation_audit(self.data.chemical_plant_activity_rows,
                                          2024, "calendar")
        ammonia = next(row for row in rows if row["ipcc_code"] == "2.B.1")
        nitric = next(row for row in rows if row["ipcc_code"] == "2.B.2")
        self.assertEqual(ammonia["reported_target_year_production_t"], 311242.0)
        self.assertFalse(ammonia["national_estimate_activated"])
        self.assertFalse(nitric["national_estimate_activated"])

    def test_chemical_evidence_never_mixes_period_bases(self):
        calendar = chemicals.activation_audit(self.data.chemical_plant_activity_rows,
                                              2022, "calendar")
        fiscal = chemicals.activation_audit(self.data.chemical_plant_activity_rows,
                                            2022, "fiscal")
        ammonia = next(row for row in calendar if row["ipcc_code"] == "2.B.1")
        nitric = next(row for row in calendar if row["ipcc_code"] == "2.B.2")
        self.assertEqual(ammonia["reported_target_year_production_t"], 604995.0)
        self.assertEqual(nitric["reported_target_year_production_t"], 563701.0)
        self.assertTrue(all(row["reported_target_year_production_t"] == 0 for row in fiscal))

    def test_cdm_monitoring_is_historical_observation_only(self):
        rows = self.data.nitric_acid_monitoring_rows
        self.assertTrue(rows)
        self.assertTrue(all("observation" in row["evidence_role"] for row in rows))
        self.assertTrue(all(int(row["monitoring_end"][:4]) <= 2022 for row in rows))
        self.assertFalse(any(row.get("evidence_status") == "model_ready_national"
                             for row in rows))

    def test_cdm_detail_is_period_specific_and_not_current_activity(self):
        rows = self.data.nitric_acid_monitoring_detail_rows
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["monitoring_start"] == "2008-04-01" for row in rows))
        self.assertEqual({row["facility_id"] for row in rows}, {"fert_pakarab_multan"})
        self.assertTrue(all("historical" in row["evidence_role"] for row in rows))

    def test_blocked_cdm_documents_do_not_claim_local_hashes(self):
        blocked = [row for row in self.data.cdm_access_manifest_rows
                   if row["access_status"] == "remote_indexed_storage_blocked"]
        self.assertTrue(blocked)
        self.assertTrue(all(not row["local_file"] and not row["sha256"] for row in blocked))

    def test_hfc_contract_keeps_equipment_and_servicing_charge_separate(self):
        fields = {row["field"] for row in self.data.hfc_import_contract_rows}
        self.assertIn("new_equipment_charge_t", fields)
        self.assertIn("servicing_charge_t", fields)
        self.assertNotIn("supplied_charge_t", fields)

    def test_request_packets_are_drafts_only(self):
        self.assertEqual(len(self.data.data_request_packet_rows), 4)
        self.assertEqual({row["status"] for row in self.data.data_request_packet_rows},
                         {"gmail_draft_created_not_sent"})

    def test_facility_registry_has_unique_ids(self):
        ids = [row["facility_id"] for row in self.data.facility_rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("fert_agritech_mianwali", ids)
        self.assertIn("cement_maple_iskanderabad", ids)

    def test_facility_geocoding_audit_retains_unresolved_records(self):
        """The audit keeps all 34, located or not, and the located count only ever rises.

        It used to name the eight resolved ids one by one. That list was correct while it was
        the whole story and became a maintenance task the moment eleven more plants were
        located from the GEM cement tracker - and a test that has to be edited to accept an
        improvement teaches people to edit it. What matters is asserted instead: no record is
        dropped when it cannot be placed, every placement cites where it came from, and the
        ammonia plants are still openly unlocated because the held OSM extract does not name
        them (data/source_search_log.csv, ippu-ammonia-coords-01).
        """
        rows = self.data.facility_geocoding_audit()
        self.assertEqual(len(rows), 34)
        resolved = {row["facility_id"] for row in rows
                    if row["geocode_status"] == "exact_coordinate_resolved"}
        self.assertGreaterEqual(len(resolved), 19,
                                "a facility that had a coordinate has lost it")
        for row in rows:
            self.assertTrue(row["coordinate_source_reference"], row["facility_id"])
        ammonia = {row["facility_id"] for row in rows
                   if row["facility_id"].startswith("fert_")}
        self.assertTrue(ammonia)
        self.assertFalse(ammonia & resolved,
                         "an ammonia plant has acquired a coordinate; the search log says the "
                         "held sources do not name them, so either that changed and the log "
                         "should say so, or the point came from somewhere unrecorded")

    def test_evidence_maturity_is_explicit_notation_companion(self):
        self.assertEqual(len(self.data.evidence_maturity_rows), len(self.matrix))
        cement_row = next(row for row in self.data.evidence_maturity_rows
                          if row["ipcc_code"] == "2.A.1")
        ammonia = next(row for row in self.data.evidence_maturity_rows
                       if row["ipcc_code"] == "2.B.1")
        self.assertEqual((cement_row["maturity_level"], ammonia["maturity_level"]),
                         ("4", "4"))   # rc52: ammonia is model-ready national activity

    def test_no_silent_historical_interpolation(self):
        rows = completeness.historical_coverage(self.data.activity_rows)
        row_1990 = next(row for row in rows if row["year"] == 1990)
        self.assertIn("no public activity", row_1990["coverage_status"])


class TestReusableCategoryKernels(unittest.TestCase):
    def test_ammonia_recovery_ledger_closes(self):
        component, ledger = chemicals.ammonia_component(
            1000.0, 2.0, recovered_to_urea_kt=750.0,
            recovered_other_kt=50.0)
        self.assertEqual(component["emissions_Gg"], 1200.0)
        self.assertAlmostEqual(ledger["closure_residual_kt"], 0.0)

    def test_nitric_acid_abatement_is_explicit(self):
        unabated, _ = chemicals.nitric_acid_component(1000.0, 5.0)
        abated, ledger = chemicals.nitric_acid_component(
            1000.0, 5.0, abated_share=1.0, destruction_efficiency=0.9,
            abatement_utilisation=0.8)
        self.assertLess(abated["emissions_Gg"], unabated["emissions_Gg"])
        self.assertAlmostEqual(ledger["destroyed_n2o_kt"], 3.6)

    def test_fgas_bank_conserves_mass(self):
        ledgers, components = fgases.run_bank("HFC-134a", "refrigeration", [{
            "year": 2024, "supplied_charge_t": 100.0,
            "manufacturing_loss_fraction": 0.02, "operating_loss_fraction": 0.10,
            "retired_charge_t": 20.0, "recovery_fraction": 0.5,
            "destruction_fraction_of_recovered": 0.25}])
        self.assertAlmostEqual(ledgers[0]["closure_residual_t"], 0.0)
        self.assertEqual(components[0]["gas"], "HFC-134a")

    def test_fgas_future_rows_require_distinct_charge_flows(self):
        row = {"year": 2024, "species": "HFC-134a", "application": "stationary AC",
               "imports_t": 100, "exports_t": 0, "domestic_production_t": 0,
               "destruction_t": 0, "new_equipment_charge_t": 70,
               "servicing_charge_t": 20, "manufacturing_loss_fraction": 0.02,
               "operating_loss_fraction": 0.10, "retired_charge_t": 5,
               "recovery_fraction": 0.5, "destruction_fraction_of_recovered": 0.25,
               "source_reference": "test", "data_status": "reported"}
        self.assertEqual(fgases.validate_inventory_rows([row]), [row])

    def test_species_gwps_are_supported(self):
        self.assertEqual(to_co2e("HFC-23", 1.0, "AR5"), 12400.0)
        self.assertEqual(to_co2e("HFC-134a", 1.0, "AR6"), 1530.0)
        self.assertEqual(to_co2e("SF6", 1.0, "AR5"), 23500.0)


class TestOfficialCRT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = official_reporting.extract_summary()
        cls.background = official_reporting.extract_background()
        cls.reproduction = official_reporting.reproduce_background()

    def test_total_and_principal_rows_are_extracted(self):
        total = next(row for row in self.summary if row["category"].startswith("2. Total"))
        self.assertAlmostEqual(total["co2_kt"], 49109.0924713271)
        self.assertAlmostEqual(total["hfc_co2e_kt"], 2.938240231879871)

    def test_ammonia_recovery_is_not_lost(self):
        row = next(row for row in self.background if row["row"] == 21)
        self.assertAlmostEqual(row["co2_fossil_recovery_kt"], -4724.42666666667)

    def test_every_numeric_crt_formula_closes(self):
        self.assertEqual(len(self.reproduction), 7)
        self.assertTrue(all(row["closes"] for row in self.reproduction))


class TestDownscale(unittest.TestCase):
    def test_current_proxy_reconciles_but_is_provisional(self):
        shares = downscale.load_shares()[downscale.PROXY]
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=6)
        self.assertAlmostEqual(shares["Punjab"], 0.424486, places=6)

    def test_unknown_category_raises(self):
        with self.assertRaises(KeyError):
            downscale.proxy_for({"category": "Lime production", "subitem": "x"})


if __name__ == "__main__":
    unittest.main()


def _registry_rows(path):
    """This module works off IppuData; these two guards read the SHIPPED tables instead, and
    deliberately - what failed was a product on disk, not a computation."""
    import csv
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full = path if os.path.isabs(path) else os.path.join(root, "outputs", path)
    return read_rows(full)


def _repo(*parts):
    import os
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), *parts)


class TestTheTwoRegistriesDescribeTheSameFacilities(unittest.TestCase):
    """A sector registry and the master registry may not disagree about the same facility.

    They did, for four releases. `outputs/ippu_facility_registry.csv` said eight of the
    thirty-four cement and fertiliser installations carried a coordinate; the IPPU slice of
    `outputs/pakemis_facility_registry.csv` said nineteen. Both read the same override file;
    only one of the two writers is in `make national`, so only one of them had been rebuilt
    since the GEM cement tracker landed eleven more coordinates.

    Nothing compared them, so nothing knew. The manuscript was anchored to the stale one and
    told readers eight - a claim the registry check passed, because the register it checked
    against was the wrong vintage.

    Written over any sector that publishes its own registry rather than over IPPU by name: a
    second one appearing would be enrolled by existing, not by someone remembering.
    """

    SECTOR_REGISTRIES = {"ippu": "ippu_facility_registry.csv"}

    def _master(self, module):
        return {r["facility_id"]: r for r in _registry_rows("pakemis_facility_registry.csv")
                if r["module"] == module}

    def test_the_sector_registry_names_the_same_facilities_as_the_master(self):
        for module, name in sorted(self.SECTOR_REGISTRIES.items()):
            sector = {r["facility_id"] for r in _registry_rows(name)}
            master = set(self._master(module))
            self.assertEqual(sector, master,
                             "%s and the master registry cover different %s facilities: "
                             "only in sector %s; only in master %s"
                             % (name, module, sorted(sector - master)[:5],
                                sorted(master - sector)[:5]))

    def test_they_agree_on_which_facilities_are_located(self):
        for module, name in sorted(self.SECTOR_REGISTRIES.items()):
            master = self._master(module)
            disagree = [(r["facility_id"], r["geocode_status"],
                         master[r["facility_id"]]["geocode_status"])
                        for r in _registry_rows(name)
                        if r["facility_id"] in master
                        and r["geocode_status"] != master[r["facility_id"]]["geocode_status"]]
            self.assertFalse(disagree,
                             "%s and the master registry disagree about %d facilities; the "
                             "first few are %s" % (name, len(disagree), disagree[:3]))

    def test_both_agree_with_the_override_register_they_read(self):
        """The third vintage. Both registries derive from the same override file, so the
        count they report is checkable against it rather than against each other only -
        two files agreeing on a wrong number is still a wrong number."""
        held = sum(1 for r in _registry_rows(
            _repo("data", "activity", "ippu", "facility_geocoding_overrides.csv"))
                   if r["latitude"].strip())
        for module, name in sorted(self.SECTOR_REGISTRIES.items()):
            located = sum(1 for r in _registry_rows(name)
                          if r["geocode_status"] == "exact_coordinate_resolved")
            self.assertEqual(located, held,
                             "%s reports %d located and the override register holds %d "
                             "coordinates" % (name, located, held))
