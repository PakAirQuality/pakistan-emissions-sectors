"""rc68 air review: checks run on the FINAL exported air records, never on an intermediate.

Each test reads the published CSVs in outputs/ and recomputes the property from their rows:
nested particulate species, the chemical mass convention, monthly and spatial closure per
pollutant, the screening/covered separation, the sulfur boundary on SO2 records, the power
control-evidence fields and the matched-boundary EDGAR industrial ratio.
"""
import collections
import csv
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs")
CORE7 = ("BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2")


def rows(name):
    with io.open(os.path.join(OUT, name), encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _f(value):
    return float(value) if value not in ("", None) else None


ATOMS = None


def atoms():
    global ATOMS
    if ATOMS is None:
        ATOMS = rows("pakemis_air_atomic_annual.csv")
    return ATOMS


def national():
    out = collections.defaultdict(float)
    for r in rows("pakemis_air_annual_fy2015_16_fy2024_25.csv"):
        out[(r["period_id"], r["configuration_id"], r["pollutant"])] += float(r["emissions_Gg"])
    return out


class NestedSpecies(unittest.TestCase):
    """BC + OC <= PM2.5 <= PM10 <= TSP wherever the same emitting process carries both."""

    def _groups(self, records, keys):
        groups = collections.defaultdict(lambda: collections.defaultdict(float))
        for r in records:
            groups[tuple(r[k] for k in keys)][r["pollutant"]] += float(r["emissions_Gg"])
        return groups

    def assert_nested(self, groups, rel=1e-6, absolute=2e-6):
        pairs = 0
        for key, species in groups.items():
            for small, large in (("PM2.5", "PM10"), ("PM10", "TSP"), ("PM2.5", "TSP")):
                if small in species and large in species:
                    pairs += 1
                    self.assertLessEqual(species[small], species[large] * (1 + rel) + absolute,
                                         "%s > %s at %r" % (small, large, key))
            if "BC" in species or "OC" in species:
                self.assertIn("PM2.5", species, "a carbon component with no matched PM2.5 at %r" % (key,))
                self.assertLessEqual(species.get("BC", 0.0) + species.get("OC", 0.0),
                                     species["PM2.5"] * (1 + rel) + absolute, "BC+OC > PM2.5 at %r" % (key,))
        return pairs

    def test_final_atoms_per_source_process_and_year(self):
        groups = self._groups(atoms(), ("period_id", "configuration_id", "sector_id",
                                        "source_class_id", "process"))
        self.assertGreater(self.assert_nested(groups), 400)

    def test_final_monthly_records_per_process_and_month(self):
        groups = self._groups(rows("pakemis_air_monthly.csv"),
                              ("period_id", "configuration_id", "sector_id", "source_class_id",
                               "process", "month"))
        self.assert_nested(groups)

    def test_annual_rollup_bc_within_pm25_per_category(self):
        groups = self._groups(rows("pakemis_air_annual_fy2015_16_fy2024_25.csv"),
                              ("period_id", "configuration_id", "sector_id", "category"))
        self.assert_nested(groups)

    def test_no_product_carries_a_cross_species_total_or_secondary_species(self):
        banned = {"ALL", "TOTAL", "SUM", "O3", "OZONE", "PM_AMBIENT", "SECONDARY_PM"}
        for name in ("pakemis_air_annual_fy2015_16_fy2024_25.csv", "pakemis_air_monthly.csv",
                     "pakemis_air_atomic_annual.csv", "air_pollutants_adm1.csv",
                     "pakemis_air_adm1_by_year.csv", "pakemis_air_temporal_support.csv"):
            seen = {r["pollutant"].upper() for r in rows(name)}
            self.assertFalse(seen & banned, name)
            self.assertFalse([s for s in seen if "+" in s], name)


class MassConvention(unittest.TestCase):
    def test_every_atom_states_its_chemical_mass_convention(self):
        want = {"NOx": "NO2-equivalent", "NH3": "not NH3-N", "SO2": "not S",
                "BC": "component of PM2.5", "OC": "component of PM2.5",
                "PM10": "contains PM2.5", "TSP": "contains PM2.5"}
        for r in atoms():
            basis = r["pollutant_mass_basis"]
            self.assertNotEqual(basis, "native mass", r["pollutant"])
            self.assertNotIn("CO2e", basis)
            if r["pollutant"] in want:
                self.assertIn(want[r["pollutant"]], basis, r["pollutant"])

    def test_nitrogen_factors_are_converted_not_reported_as_n(self):
        for r in atoms():
            if r["pollutant"] == "NH3" and "NH3-N" in r["factor_unit"]:
                self.assertIn("17/14", r["factor_unit"])
            if r["pollutant"] == "NOx" and "NOx-N" in r["factor_unit"]:
                self.assertIn("46/14", r["factor_unit"])


class TemporalAndSpatialClosure(unittest.TestCase):
    """Per species, period and configuration; tolerance = six-decimal rounding of the rows."""

    @classmethod
    def setUpClass(cls):
        cls.national = national()

    def _close(self, parts, tolerance):
        worst = 0.0
        self.assertEqual(set(parts), set(self.national))
        for key, nat in self.national.items():
            worst = max(worst, abs(parts[key] - nat))
            self.assertAlmostEqual(parts[key], nat, delta=tolerance, msg=key)
        return worst

    def test_monthly_sums_to_annual(self):
        parts = collections.defaultdict(float)
        for r in rows("pakemis_air_monthly.csv"):
            parts[(r["period_id"], r["configuration_id"], r["pollutant"])] += float(r["emissions_Gg"])
        self.assertLess(self._close(parts, 1e-4), 1e-4)

    def test_adm1_plus_unallocated_and_adm2_plus_unallocated_close_on_national(self):
        unalloc = collections.defaultdict(float)
        for r in rows("pakemis_air_unallocated_by_year.csv"):
            self.assertEqual(r["level"], "below_adm1")
            unalloc[(r["period_id"], r["configuration_id"], r["pollutant"])] += float(r["emissions_Gg"])
        adm1 = collections.defaultdict(float)
        for r in rows("pakemis_air_adm1_by_year.csv"):
            adm1[(r["period_id"], r["configuration_id"], r["pollutant"])] += float(r["emissions_Gg"])
        self._close(adm1, 1e-3)              # below-ADM1 mass IS placed at ADM1
        adm2 = collections.defaultdict(float)
        for r in rows("pakemis_air_adm2_by_year.csv"):
            adm2[(r["period_id"], r["configuration_id"], r["pollutant"])] += float(r["emissions_Gg"])
        placed = {k: adm2.get(k, 0.0) + unalloc.get(k, 0.0) for k in self.national}
        self._close(placed, 1e-3)

    def test_evidence_shares_are_per_pollutant_mass(self):
        temporal = collections.defaultdict(float)
        shares = collections.defaultdict(float)
        for r in rows("pakemis_air_temporal_support.csv"):
            key = (r["period_id"], r["configuration_id"], r["pollutant"])
            temporal[key] += float(r["emissions_Gg"])
            shares[key] += float(r["mass_share"])
        self._close(temporal, 1e-3)
        for key, total in shares.items():
            self.assertAlmostEqual(total, 1.0, places=9, msg=key)
        spatial = collections.defaultdict(float)
        for r in rows("pakemis_air_spatial_support_by_year.csv"):
            spatial[(r["period_id"], r["configuration_id"], r["pollutant"])] += float(r["emissions_Gg"])
        self._close(spatial, 1e-3)


class ScreeningStaysOutside(unittest.TestCase):
    def test_power_covered_panel_is_admitted_oil_so2_only(self):
        panel = [r for r in rows("pakemis_air_annual_fy2015_16_fy2024_25.csv") if r["sector_id"] == "power"]
        self.assertEqual({r["pollutant"] for r in panel}, {"SO2"})
        power_atoms = [a for a in atoms() if a["sector_id"] == "power"]
        self.assertTrue(power_atoms)
        for a in power_atoms:
            self.assertEqual(a["maturity"], "provisional_estimate")
            self.assertNotIn("coal", a["source_class_id"].lower())
            self.assertNotIn("gas", a["source_class_id"].lower())

    def test_screening_rows_are_labelled_scenarios_and_never_in_the_panel(self):
        screening = rows("power_air_screening_fy2015_16_fy2024_25.csv")
        self.assertEqual({r["scenario"] for r in screening}, {"uncontrolled", "controlled_case"})
        coal = sum(float(r["emissions_kt"]) for r in screening
                   if r["fuel"] == "Coal" and r["pollutant"] == "SO2" and r["scenario"] == "uncontrolled")
        self.assertGreater(coal, 0.0)
        panel_power = sum(float(r["emissions_Gg"]) for r in rows("pakemis_air_annual_fy2015_16_fy2024_25.csv")
                          if r["sector_id"] == "power" and r["configuration_id"] == "S_TAN")
        admitted = sum(float(a["emissions_Gg"]) for a in atoms()
                       if a["sector_id"] == "power" and a["configuration_id"] == "S_TAN")
        self.assertAlmostEqual(panel_power, admitted, delta=1e-4)

    def test_reference_year_province_layer_marks_every_screening_row(self):
        for name in ("air_pollutants_adm1.csv", "air_pollutants_adm2.csv"):
            data = rows(name)
            kinds = collections.Counter(r["estimate_kind"] for r in data)
            self.assertEqual(set(kinds), {"covered_estimate", "screening_scenario_not_in_covered_total"}, name)
            for r in data:
                if r["sector_id"] == "power":
                    self.assertEqual(r["estimate_kind"], "screening_scenario_not_in_covered_total", r)
                else:
                    self.assertEqual(r["estimate_kind"], "covered_estimate", r)

    def test_absences_are_typed_not_zero(self):
        estimated = {(c["period_id"], c["sector_id"], c["pollutant"])
                     for c in rows("pakemis_air_coverage_matrix.csv") if c["state"] == "E"}
        for r in rows("pakemis_air_annual_fy2015_16_fy2024_25.csv"):
            self.assertIn((r["period_id"], r["sector_id"], r["pollutant"]), estimated, r)
        states = {r["state"] for r in rows("pakemis_air_source_coverage.csv")}
        self.assertLessEqual(states, {"E", "NE", "IE", "NA", "NO"})


class SulfurBoundary(unittest.TestCase):
    def test_brick_kiln_so2_states_fuel_raw_material_and_retention_separately(self):
        brick = [a for a in atoms() if a["pollutant"] == "SO2" and a["source_class_id"].startswith("brick_")]
        self.assertTrue(brick)
        for a in brick:
            text = a["structural_sensitivity"]
            self.assertIn("FUEL sulfur only", text)
            self.assertIn("raw-material (clay) sulfur NOT estimated", text)
            self.assertIn("ASSUMED fraction, not measured removal", text)
            self.assertIn("not a national sampling design", text)

    def test_every_sulfur_balance_so2_atom_names_its_boundary(self):
        for a in atoms():
            if a["pollutant"] == "SO2" and a["calculation_module"] == "pkinv.sectors.industry.air_pollutants":
                self.assertIn("SO2 boundary:", a["structural_sensitivity"], a["source_class_id"])
                self.assertFalse(a["structural_sensitivity"].startswith(";"))

    def test_road_sulfur_is_a_declared_policy_case_not_compliance(self):
        road = [a for a in atoms() if a["sector_id"] == "transport" and a["pollutant"] == "SO2"]
        self.assertTrue(road)
        for a in road:
            self.assertIn("not a pump", a["structural_sensitivity"])
            self.assertIn("policy/specification dates", a["structural_sensitivity"])


class PowerControlEvidence(unittest.TestCase):
    def test_installed_design_assumed_and_demonstrated_are_separate_fields(self):
        evidence = rows("pakemis_air_power_control_evidence.csv")
        self.assertTrue(evidence)
        for r in evidence:
            self.assertTrue(r["installation_evidence"].startswith("not_established"), r)
            self.assertEqual(r["operation_evidence"], "not_demonstrated_by_this_document")
            self.assertTrue(r["assumed_removal_in_screening"], r)
            self.assertEqual(r["admission_status"], "scenario_only")
        for r in rows("pakemis_air_power_design_cases.csv"):
            self.assertIn("not a maximum", r["limitations"])
            self.assertIn("not_in_central_panel", r["coverage_scope"])


class EdgarIndustryMatchedBoundary(unittest.TestCase):
    def test_matched_ratio_is_engine_over_1a2_plus_2a1_and_drives_the_reading(self):
        data = rows("pakemis_industry_air_edgar_comparison.csv")
        compared = [r for r in data if r["ratio_engine_over_edgar_fossil_plus_2a1"]]
        self.assertGreaterEqual(len(compared), 42)
        for r in compared:
            engine = float(r["engine_industry_kt"])
            matched = float(r["edgar_1a2_fossil_plus_2a1_kt"])
            ratio = engine / matched
            self.assertAlmostEqual(float(r["ratio_engine_over_edgar_fossil_plus_2a1"]), ratio, delta=6e-4)
            self.assertAlmostEqual(float(r["ratio_engine_over_edgar_fossil_bio_plus_2a1"]),
                                   engine / float(r["edgar_1a2_fossil_bio_plus_2a1_kt"]), delta=6e-4)
            self.assertIn("matched boundary", r["reading"])
            band = ("within" if 0.5 <= ratio <= 2.0 else "above" if ratio > 2.0 else "below")
            self.assertTrue(r["reading"].startswith(band), (r["species"], r["period_id"], ratio, r["reading"]))
            self.assertIn("not separable", r["decomposition"])


class HtapSpeciesComparison(unittest.TestCase):
    """The process-boundary HTAPv3.2 comparison, checked against the held workbook and the atoms."""

    @classmethod
    def setUpClass(cls):
        cls.data = rows("pakemis_air_htap_species_comparison.csv")

    def test_every_core_species_period_and_configuration_is_present(self):
        keys = {(r["period_id"], r["configuration_id"], r["pollutant"]) for r in self.data}
        self.assertEqual({k[2] for k in keys}, set(CORE7))
        self.assertEqual(len({k[0] for k in keys}), 10)
        self.assertEqual(len({k[1] for k in keys}), 4)

    def test_ratios_only_on_complete_matched_processes(self):
        for r in self.data:
            start = int(r["period_id"][2:6])
            if r["ratio_pakemis_over_htap"]:
                self.assertEqual(r["comparison_status"], "process_comparison", r)
                self.assertLessEqual(start + 1, 2020)
                self.assertAlmostEqual(float(r["ratio_pakemis_over_htap"]),
                                       float(r["pakemis_Gg"]) / float(r["htap_Gg"]), places=9)
            if start + 1 > 2020:
                self.assertEqual(r["htap_Gg"], "")
                self.assertEqual(r["comparison_status"], "no_complete_external_fiscal_period")
            if r["comparison_status"] == "boundary_difference_context_only":
                self.assertEqual(r["ratio_pakemis_over_htap"], "")
            self.assertIn("not independent", r["shared_input_note"])
        groups = {r["comparison_group"] for r in self.data if r["comparison_status"] == "process_comparison"}
        self.assertNotIn("public_power", groups)
        self.assertNotIn("residential", groups)

    def test_pakemis_side_equals_the_final_atoms(self):
        want = collections.defaultdict(float)
        for a in atoms():
            if (a["sector_id"] == "transport" and a["process"] in ("exhaust", "evaporative")
                    and a["configuration_id"] == "S_TAN"):
                want[(a["period_id"], a["pollutant"])] += float(a["emissions_Gg"])
        got = {(r["period_id"], r["pollutant"]): float(r["pakemis_Gg"]) for r in self.data
               if r["comparison_group"] == "road_exhaust" and r["configuration_id"] == "S_TAN" and r["pakemis_Gg"]}
        self.assertEqual(set(got), set(want))
        for key, value in want.items():
            self.assertAlmostEqual(got[key], value, delta=1e-5, msg=key)

    def test_htap_side_equals_the_held_publisher_workbook(self):
        import zipfile
        import openpyxl
        path = os.path.join(ROOT, "data", "raw", "htap", "edgar_HTAPv32_SO2.zip")
        with zipfile.ZipFile(path) as archive:
            book = openpyxl.load_workbook(io.BytesIO(archive.read("edgar_HTAPv3_2_SO2.xlsx")),
                                          read_only=True, data_only=True)
        fiscal = collections.defaultdict(float)
        for values in book["edgar_HTAPv3_2_SO2"].iter_rows(min_row=2, values_only=True):
            if values[3] == "PAK" and str(values[4]).endswith("5.1_Road_Transport"):
                for month, mass in enumerate(values[5:17], 1):
                    start = values[2] - (month <= 6)
                    fiscal[start] += float(mass) / 1000.0
        book.close()
        got = {int(r["period_id"][2:6]): float(r["htap_Gg"]) for r in self.data
               if r["comparison_group"] == "road_exhaust" and r["pollutant"] == "SO2"
               and r["configuration_id"] == "S_TAN" and r["htap_Gg"]}
        self.assertEqual(sorted(got), [2015, 2016, 2017, 2018, 2019])
        for start, value in got.items():
            self.assertAlmostEqual(value, fiscal[start], delta=1e-9 * max(1.0, value), msg=start)

    def test_implied_factor_is_pakemis_mass_over_its_own_activity(self):
        for r in self.data:
            if r["pakemis_implied_factor"]:
                per = 1e3 if r["pakemis_activity_unit"] == "kt_fuel" else 1e6
                self.assertAlmostEqual(float(r["pakemis_implied_factor"]),
                                       float(r["pakemis_Gg"]) / float(r["pakemis_activity"]) * per, places=9)


if __name__ == "__main__":
    unittest.main()
