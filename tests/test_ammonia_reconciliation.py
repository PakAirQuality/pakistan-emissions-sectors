"""The ammonia reconciliation - four pathways, a tiered gate, and the bug the gate hid.

Three invariants this file exists to hold. The GATE opens on evidence_status and nothing
else - it read a key no data row carries from Round 7 to Round 11, so it could never open,
and only a positive-case test proves the repair. The PATHWAYS stay four, independent, and
unaveraged - the disagreement between them is the finding, and the red flag against the
official CRT activity is asserted as arithmetic, not prose. NOTHING ACTIVATES - no
reconciliation row, tier readiness or kernel output may reach components or totals while
the pathways disagree.

Run:  python3 -m unittest discover tests -p "test_ammonia_reconciliation.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.ippu import ammonia_reconciliation, cement, chemicals, engine
from pkinv.sectors.ippu.data import IppuData
from pkinv.core.io import read_rows


def _rows(name):
    """A generated table from outputs/ - written by pkinv.sectors.ippu.run_ippu."""
    return read_rows(os.path.join(OUTPUTS, name), comments=False)


def _load(*parts):
    return read_rows(asset_path(DATA, *parts), comments=False)


def _synthetic_plant_row(**overrides):
    row = {"period_end_year": "2024", "period_basis": "calendar",
           "facility_id": "fert_test_plant", "ipcc_code": "2.B.1",
           "product": "Ammonia", "production_t": "500000",
           "evidence_status": "partial_activity_only"}
    row.update(overrides)
    return row


class TestTheGateOpensOnTheRightKey(unittest.TestCase):
    """The bug: activation_audit read row["status"]; the activity schema's column is
    evidence_status. The negative case always passed - the gate was closed for the wrong
    reason - so only an opening gate can prove the repair."""

    def test_model_ready_evidence_opens_the_gate(self):
        rows = chemicals.activation_audit(
            [_synthetic_plant_row(evidence_status="model_ready_national")],
            2024, "calendar")
        ammonia = next(r for r in rows if r["ipcc_code"] == "2.B.1")
        self.assertTrue(ammonia["national_estimate_activated"])
        self.assertEqual(ammonia["gate_status"], "E")
        self.assertEqual(ammonia["remaining_evidence"], "")

    def test_the_wrong_key_no_longer_opens_or_closes_anything(self):
        """A row carrying model_ready_national under the OLD key must not activate:
        the gate listens to the schema's column, not to the key it read for four rounds."""
        row = _synthetic_plant_row()
        row["status"] = "model_ready_national"
        rows = chemicals.activation_audit([row], 2024, "calendar")
        ammonia = next(r for r in rows if r["ipcc_code"] == "2.B.1")
        self.assertFalse(ammonia["national_estimate_activated"])
        self.assertEqual(ammonia["gate_status"], "NE")

    def test_real_data_still_gates_ne(self):
        data = IppuData()
        rows = chemicals.activation_audit(data.chemical_plant_activity_rows,
                                          2024, "calendar")
        self.assertTrue(all(not r["national_estimate_activated"] for r in rows))


class TestTierReadiness(unittest.TestCase):
    """Readiness and activation are different questions, and the tier table only ever
    answers the first."""

    def test_national_inputs_make_tier_one_ready_and_nothing_more(self):
        data = IppuData()
        rows = chemicals.tier_readiness(
            data.chemical_plant_activity_rows,
            {"national_nh3_production_t": 4.5e6, "urea_production_t": 6.78e6},
            2024, "calendar")
        t = {(r["ipcc_code"], r["tier"]): r for r in rows}
        self.assertTrue(t[("2.B.1", 1)]["tier_ready"])
        self.assertFalse(t[("2.B.1", 2)]["tier_ready"])
        self.assertFalse(t[("2.B.1", 3)]["tier_ready"])
        self.assertFalse(t[("2.B.2", 3)]["tier_ready"],
                         "2.B.2 tier 3 has no schema column to be ready through")

    def test_todays_honest_state_is_urea_only(self):
        """No national NH3 series exists and capacity is documented for one plant of
        seven, so tier 1 is NOT ready today - the recovery leg is, the activity is not."""
        data = IppuData()
        urea_t = sum(float(r["production_000t"]) * 1000.0
                     for r in data.fertilizer_production_rows
                     if r["product"] == "Urea" and r["fiscal_year"] == "2023-24")
        rows = chemicals.tier_readiness(
            data.chemical_plant_activity_rows,
            {"urea_production_t": urea_t}, 2024, "calendar")
        tier1 = next(r for r in rows if r["ipcc_code"] == "2.B.1" and r["tier"] == 1)
        self.assertFalse(tier1["tier_ready"])
        self.assertIn("urea production", tier1["evidence_held"])

    def test_readiness_never_claims_activation(self):
        data = IppuData()
        rows = chemicals.tier_readiness(
            data.chemical_plant_activity_rows,
            {"national_nh3_production_t": 4.5e6, "urea_production_t": 6.78e6},
            2024, "calendar")
        for r in rows:
            self.assertNotEqual(r["activation_status"], "E")
            if r["tier_ready"]:
                self.assertIn("reconcile before activating", r["activation_status"])


class TestTheFourPathways(unittest.TestCase):
    """The reconciliation's shape and its central arithmetic, pinned."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.ippu import official_reporting
        cls.data = IppuData()
        cls.background = official_reporting.extract_background()
        cls.rows = ammonia_reconciliation.reconciliation_table(cls.data, cls.background)

    def test_four_families_seven_rows_nothing_averaged(self):
        self.assertEqual(len(self.rows), 7)
        self.assertEqual({r["pathway"] for r in self.rows},
                         {"official CRT", "plant census", "product stoichiometry",
                          "gas balance"})
        for r in self.rows:
            self.assertTrue(r["activation_status"].startswith("diagnostic"), r["pathway"])

    def test_the_reference_year_is_measured_twice_and_never_averaged(self):
        """Two institutions, one fiscal year, two rows. The anti-averaging rule applies
        between records as much as between pathways: if these ever collapsed into one row
        the cross-source agreement would stop being visible, which is the only thing that
        makes an independent record worth holding."""
        pair = [r for r in self.rows
                if r["pathway"] == "gas balance" and r["period"] == "2023-24"]
        self.assertEqual(len(pair), 2)
        self.assertEqual({r["source_id"] for r in pair},
                         {"ogra_industry_gas", "nfdc_afr_2024_25"})
        self.assertNotEqual(pair[0]["nh3_kt_central"], pair[1]["nh3_kt_central"])
        nfdc = next(r for r in pair if r["source_id"] == "nfdc_afr_2024_25")
        self.assertIn("OBSERVED", nfdc["note"])
        self.assertNotIn("borrowed as", nfdc["note"])

    def test_crt_pathway_pins_the_official_row(self):
        crt = next(r for r in self.rows if r["pathway"] == "official CRT")
        self.assertAlmostEqual(crt["nh3_kt_central"], 11467.472, places=3)
        self.assertAlmostEqual(crt["implied_recovered_co2_kt"], 4724.42666666667,
                               places=6)
        self.assertTrue(crt["red_flag"])
        self.assertFalse(crt["independent_of_crt"])

    def test_the_red_flag_is_arithmetic_not_prose(self):
        """The gas the CRT activity implies must exceed what the sector draws by enough
        that no heating-value assumption can close it: the NFDC gas ceiling sits below
        two thirds of the official activity."""
        crt = next(r for r in self.rows if r["pathway"] == "official CRT")
        gas = next(r for r in self.rows
                   if r["pathway"] == "gas balance" and r["period"] == "2024-25")
        self.assertLess(gas["nh3_kt_high"], crt["nh3_kt_central"] * 2.0 / 3.0)

    def test_gas_pathway_band(self):
        gas = next(r for r in self.rows
                   if r["pathway"] == "gas balance" and r["period"] == "2024-25")
        self.assertTrue(6300 < gas["nh3_kt_low"] < gas["nh3_kt_high"] < 7200,
                        "band %.0f-%.0f" % (gas["nh3_kt_low"], gas["nh3_kt_high"]))

    def test_product_pathway_urea_floor_is_exact(self):
        p25 = next(r for r in self.rows
                   if r["pathway"] == "product stoichiometry"
                   and r["period"] == "2024-25")
        self.assertAlmostEqual(p25["nh3_kt_low"], 6780 * 0.567, places=6)
        self.assertGreater(p25["nh3_kt_central"], p25["nh3_kt_low"])

    def test_urea_recovery_identity(self):
        """recovered / (44/60) recovers the urea, and the urea's NH3 floor is 0.567 of
        it - the two factors must stay consistent through the parameter file."""
        recovery = ammonia_reconciliation.urea_recovery(
            6780.0, self.data.p("urea_co2_recovery_factor"),
            self.data.p("nh3_per_urea"))
        urea_back = recovery["recovered_co2_kt"] / self.data.p("urea_co2_recovery_factor")
        self.assertAlmostEqual(urea_back, 6780.0, places=9)
        self.assertAlmostEqual(recovery["nh3_floor_kt"] / urea_back,
                               self.data.p("nh3_per_urea"), places=12)

    def test_plant_pathway_is_a_flagged_floor(self):
        plant = next(r for r in self.rows if r["pathway"] == "plant census")
        self.assertTrue(plant["floor_flag"])
        self.assertEqual(plant["implied_net_co2_kt"], "")
        self.assertTrue(500 < plant["nh3_kt_low"] < plant["nh3_kt_high"] < 600)

    def test_the_activated_categories(self):
        # rc52: ammonia entered the reference through its gate (Tier 1 calibrated, nine years),
        # with iron and steel and lubricant use; the reconciliation stays diagnostic beside it
        self.assertEqual(engine.CATEGORIES, (cement.CATEGORY, "Ammonia production",
                                             "Iron and steel production", "Lubricant use"))
        components = engine.build_components(self.data)
        self.assertEqual(sum(1 for c in components if c["category"] == "Ammonia production"), 1)


class TestTheExtractedTables(unittest.TestCase):
    """The AFR extraction closes against the printed totals, row by row."""

    def test_gas_split_closes(self):
        rows = _load("nfdc", "afr2025_fertilizer_gas_by_plant.csv")
        plants = [r for r in rows if r["plant"] != "Total"]
        total = next(r for r in rows if r["plant"] == "Total")
        self.assertEqual(len(plants), 12)
        self.assertEqual(sum(float(r["feed_mmcf"] or 0) for r in plants), 234001.0)
        self.assertEqual(float(total["total_mmcf"]), 281153.0)
        # The printed fuel rows sum to 47,151 against the printed 47,152 - the source's
        # own 1-MMCF rounding slip, held visible rather than reconciled away.
        self.assertEqual(sum(float(r["fuel_mmcf"] or 0) for r in plants), 47151.0)
        self.assertIn("rounding slip", total["note"])

    def test_production_urea_totals(self):
        rows = _load("nfdc", "afr2025_production_by_manufacturer.csv")
        by = lambda year: sum(float(r["production_000t"]) for r in rows
                              if r["product"] == "Urea" and r["fiscal_year"] == year
                              and r["production_000t"])
        self.assertEqual(by("2023-24"), 6591.0)
        self.assertEqual(by("2024-25"), 6780.0)

    def test_every_row_carries_its_source(self):
        for name in ("afr2025_production_by_manufacturer.csv",
                     "afr2025_fertilizer_gas_by_plant.csv",
                     "afr2025_offtake_by_product.csv",
                     "afr2025_fertilizer_gas_monthly.csv"):
            for r in _load("nfdc", name):
                self.assertIn("NFDC", r["source"], name)


class TestTable5Offtake(unittest.TestCase):
    """The offtake table the bridge used to carry as Python constants."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _load("nfdc", "afr2025_offtake_by_product.csv")

    def test_no_printed_subtotal_survives_as_a_product(self):
        products = {r["product"] for r in self.rows}
        for subtotal in ("Total Urea", "Grand Total", "Total domestic", "Total",
                         "Total NP", "Total DAP"):
            self.assertNotIn(subtotal, products)

    def test_urea_legs_reconstruct_the_printed_total(self):
        for year, printed in (("2023-24", 6579.0), ("2024-25", 5890.0)):
            legs = sum(float(r["offtake_kt"]) for r in self.rows
                       if r["product"] == "Urea" and r["fiscal_year"] == year
                       and r["offtake_kt"].strip())
            self.assertEqual(legs, printed, year)

    def test_the_unattributed_products_say_so(self):
        """NPK's and AS print with no supply qualifier while the review's own subtotals
        imply an allocation across them. The extraction records that rather than
        inventing a split."""
        unclassified = {r["product"] for r in self.rows
                        if r["supply_basis"] == "unclassified"}
        self.assertEqual(unclassified, {"NPK's", "AS"})
        for row in self.rows:
            if row["supply_basis"] == "unclassified":
                self.assertIn("never attributes", row["note"])
        self.assertEqual({r["supply_basis"] for r in self.rows},
                         {"domestic", "imported", "unclassified"})


class TestAnnex28MonthlyGas(unittest.TestCase):
    """The reference year's own gas, and the internal check against Table 40."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _load("nfdc", "afr2025_fertilizer_gas_monthly.csv")

    def _sum(self, year, consumption=None):
        return sum(float(r["mmcf"]) for r in self.rows
                   if r["fiscal_year"] == year and r["mmcf"].strip()
                   and (consumption is None or r["consumption"] == consumption))

    def test_shape(self):
        for year in ("2023-24", "2024-25"):
            year_rows = [r for r in self.rows if r["fiscal_year"] == year]
            self.assertEqual(len({(r["gas_supplier"], r["plant"]) for r in year_rows}), 14)
            self.assertEqual(len({r["month"] for r in year_rows}), 12)
            self.assertEqual(len(year_rows), 14 * 2 * 12)
        self.assertEqual({r["consumption"] for r in self.rows}, {"Feed", "Fuel"})

    def test_the_reference_year_totals(self):
        """Tolerance 3, because the annex does not close on itself: the monthly cells run
        a few MMCF above the printed year lines. That is the review's rounding, held
        visible rather than reconciled away."""
        self.assertAlmostEqual(self._sum("2023-24", "Feed"), 229236, delta=3)
        self.assertAlmostEqual(self._sum("2023-24", "Fuel"), 45213, delta=7)
        self.assertAlmostEqual(self._sum("2023-24"), 274449, delta=8)

    def test_page_two_agrees_with_table_40(self):
        """Two printings of one year in one document, reached by different routes. If
        these ever diverged, one of the two extractions would be wrong and nothing else
        would say so."""
        self.assertAlmostEqual(self._sum("2024-25"), 281153, delta=3)
        self.assertAlmostEqual(self._sum("2024-25", "Feed"), 234001, delta=3)

    def test_the_february_typo_is_corrected_and_declared(self):
        feb = [r for r in self.rows
               if r["fiscal_year"] == "2023-24" and r["month"] == "Feb"]
        self.assertTrue(feb)
        for row in feb:
            self.assertEqual(int(row["calendar_year"]), 2024)
            self.assertIn("FEB ' 23", row["note"])

    def test_no_printed_total_row_survives(self):
        for row in self.rows:
            self.assertNotIn(row["plant"], ("Total", "Grand Total"))


class TestTheTwoGasSourcesAgree(unittest.TestCase):
    """A regulator and an industry body on the same fiscal year, and the limit of it."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("ippu_fertilizer_gas_cross_source_2024.csv")

    def test_they_land_within_one_percent(self):
        difference = next(r for r in self.rows if r["record"] == "difference")
        self.assertTrue(-1.0 < float(difference["agreement_pct"]) < 0.0,
                        difference["agreement_pct"])

    def test_both_records_are_present_and_independent(self):
        self.assertEqual(len(self.rows), 3)
        institutions = {r["institution"] for r in self.rows if r["institution"]}
        self.assertEqual(len(institutions), 2)
        for row in self.rows:
            self.assertTrue(row["activation_status"].startswith("diagnostic"))

    def test_the_note_states_what_agreement_does_not_buy(self):
        difference = next(r for r in self.rows if r["record"] == "difference")
        self.assertIn("UPPER bounds", difference["note"])
        self.assertIn("neither activates 2.B.1", difference["note"])


class TestTheMonthlyProfileClaimsNothing(unittest.TestCase):
    """An observed shape that no reported category is allowed to take."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("ippu_fertilizer_gas_monthly_2024.csv")

    def test_it_is_applied_to_nothing(self):
        self.assertEqual(len(self.rows), 24)
        for row in self.rows:
            self.assertTrue(row["applied_to"].startswith("nothing"), row["month"])
            self.assertTrue(row["activation_status"].startswith("diagnostic"))

    def test_shares_close_per_year(self):
        for year in ("2023-24", "2024-25"):
            share = sum(float(r["share_of_year"]) for r in self.rows
                        if r["fiscal_year"] == year)
            self.assertAlmostEqual(share, 1.0, places=4)

    def test_the_stream_is_baseload(self):
        """The finding, pinned: ammonia gas barely moves across the year. If this ever
        exceeded a quarter, the profile would have become worth applying somewhere and
        the diagnostic framing would need revisiting."""
        for year in ("2023-24", "2024-25"):
            totals = [float(r["total_mmcf"]) for r in self.rows
                      if r["fiscal_year"] == year]
            self.assertLess(max(totals) / min(totals), 1.25, year)

    def test_the_ammonia_monthly_rows_claim_no_shape(self):
        """rc52: ammonia is a reference component, so it HAS monthly rows - and every one of
        them is the declared flat profile (T4): no fertilizer month was borrowed as a shape,
        which is what this test used to guard by asserting the rows were absent."""
        ammonia = [row for row in _rows("ippu_monthly_2024.csv") if "ammonia" in " ".join(row.values()).lower()]
        self.assertEqual(len(ammonia), 12)
        for row in ammonia:
            joined = " ".join(row.values()).lower()
            self.assertNotIn("fertil", joined.replace("nfdc prints annual production", ""))
            self.assertIn("t4", joined)
            self.assertIn("flat", joined)


class TestTheUreaBridge(unittest.TestCase):
    """Production and application reconcile through the identity, never by equality."""

    @classmethod
    def setUpClass(cls):
        cls.rows = ammonia_reconciliation.urea_bridge(IppuData())

    def _flow(self, year, name):
        return next(r for r in self.rows
                    if r["fiscal_year"] == year and r["flow"].startswith(name))

    def test_the_residual_is_the_identity_and_is_not_zeroed(self):
        # rc42 (P-3): the application side reads Annex-5's exact national row (6,578.838 kt
        # in 2023-24) where Table 5 rounds to 6,579, so the 2023-24 residual is 233.162
        for year, expected in (("2023-24", 233.162), ("2024-25", 890.276)):
            production = self._flow(year, "production")["urea_kt"]
            imports = self._flow(year, "imports")["urea_kt"]
            offtake = self._flow(year, "offtake")["urea_kt"]
            residual = self._flow(year, "stock change")["urea_kt"]
            self.assertAlmostEqual(residual, production + imports - offtake, places=9)
            self.assertAlmostEqual(residual, expected, places=9)
            self.assertNotEqual(residual, 0.0,
                                "a zero residual here would mean forced agreement")

    def test_the_two_ipcc_sides_are_labelled(self):
        sides = {r["ipcc_side"] for r in self.rows}
        self.assertIn("2.B.1 recovery basis", sides)
        self.assertIn("3.H application basis", sides)

    def test_no_leg_is_still_a_python_literal(self):
        """Round 11 built the bridge on module constants because Table 5 had not been
        extracted. Every activity quantity in this repository lives in a registered CSV,
        and this is the assertion that keeps the bridge inside that rule."""
        for row in self.rows:
            self.assertNotIn("not yet extracted", row["status"], row["flow"])
        for row in self.rows:
            if row["status"] in ("derived", "inferred nil"):
                continue
            if row["flow"].startswith(("production", "imports", "offtake")):
                self.assertIn("data/nfdc/", row["source"], row["flow"])

    def test_the_3h_method_note_records_the_gap_as_closed(self):
        """This used to pin the words "working pointer" - the phrasing of a DEFERRAL. rc39 A3
        discharged the deferral by reading NFDC's printed offtake, so pinning the deferral's
        wording would now hold the ledger to a state the code has left. What must survive is
        the row itself and the mass it names: a ledger that quietly dropped its own closed
        finding would lose the record that the gap ever existed."""
        note = next(r for r in self.rows if r["flow"] == "3.H method note")
        self.assertIn("0.80", note["note"])
        self.assertIn("closed", note["status"])
        self.assertIn("6,578,838", note["note"])
        self.assertAlmostEqual(float(note["urea_kt"]), 6578.838, delta=0.01)


if __name__ == "__main__":
    unittest.main()
