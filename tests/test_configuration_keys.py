"""The configuration vocabulary, held closed across every product (rc31).

The eighteenth review found one alternative wearing four names; the vocabulary
now lives in pkinv.core.configurations and every product that keys on a
configuration must draw from it. These tests hold the closure, the L identity
(non-residential sectors identical by construction, so their rows are absent
rather than duplicated), and the numeric closures that make the L rows a
configuration rather than a decoration.

rc67 (2026-10-13): the roles swapped. Through rc66 the reference burned all the
diverted dung in households and the survey reading was the alternative, published
as S_2023_24. The reference now carries the survey's dung and the alternative is
the ledger, L_2023_24. Everything below that used to say "survey rows" says
"ledger rows", the alternative is the LARGER side, and the typed row for the
diverted dung with no household destination belongs to the reference, in every
year, where it used to be one row under S.
"""
import csv
import io
import os
import unittest

from pkinv.core import configurations as conf
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows(name):
    return read_rows(os.path.join(OUT, name))


class TestTheVocabularyIsClosed(unittest.TestCase):
    def test_the_vocabulary_is_exactly_two_ids(self):
        self.assertEqual(conf.ALL, (conf.REFERENCE, conf.LEDGER))
        self.assertEqual(conf.REFERENCE, "REF_2023_24")
        self.assertEqual(conf.LEDGER, "L_2023_24")
        # the air panel's nine-year ledger series (air spatial Wave A; the survey series
        # until rc67, when the survey became the reference): its own id, because
        # L_2023_24 is period-named and may not be manufactured for history; the
        # greenhouse-gas vocabulary conf.ALL is UNCHANGED by it
        self.assertEqual(conf.AIR_ALL, (conf.REFERENCE, conf.LEDGER_SERIES))
        self.assertEqual(conf.LEDGER_SERIES, "L_HERD1624")

    def test_the_one_dung_switch_says_survey(self):
        """rc67: the reference dung basis is the household survey and the alternative is
        the ledger. One switch names it; an engine called with neither name must refuse
        rather than fall back to whichever basis it used to default to."""
        from pkinv.sectors.residential import combustion
        self.assertEqual(conf.REFERENCE_DUNG_BASIS, "survey")
        self.assertEqual(conf.ALTERNATIVE_DUNG_BASIS, "ledger")
        self.assertEqual(combustion.reference_basis(), "survey")
        self.assertEqual(combustion.reference_basis("ledger"), "ledger")
        with self.assertRaises(ValueError):
            combustion.reference_basis("hies")
        self.assertEqual(conf.LEDGER_DISPLAY, "all_diverted_dung_household_fuel")

    def test_the_retired_ids_resolve_to_the_reference_and_ship_nowhere(self):
        """S_2023_24 and S_HIES1925 named the survey reading while it was the
        alternative. What they named is the reference now, so they map to it and no
        configuration-keyed product may still carry either."""
        self.assertEqual(conf.RETIRED, {"S_2023_24": conf.REFERENCE,
                                        "S_HIES1925": conf.REFERENCE})
        self.assertFalse(set(conf.RETIRED) & (set(conf.ALL) | set(conf.AIR_ALL)))
        for name in ("pakemis_annual_fy2015_16_fy2023_24.csv",
                     "pakemis_monthly_fy2015_16_fy2023_24.csv",
                     "pakemis_monthly_ledger_2024.csv",
                     "pakemis_adm1_ledger_2024.csv",
                     "pakemis_adm2_ledger_2024.csv",
                     "pakemis_air_annual_fy2015_16_fy2023_24.csv",
                     "residential_configurations_by_year.csv"):
            ids = {r["configuration_id"] for r in _rows(name)}
            self.assertFalse(ids & set(conf.RETIRED), name)

    def test_the_annual_product_draws_from_it(self):
        ids = {r["configuration_id"]
               for r in _rows("pakemis_annual_fy2015_16_fy2023_24.csv")}
        self.assertEqual(ids, set(conf.ALL))

    def test_the_monthly_product_draws_from_it(self):
        ids = {r["configuration_id"]
               for r in _rows("pakemis_monthly_fy2015_16_fy2023_24.csv")}
        self.assertLessEqual(ids, set(conf.ALL))

    def test_the_ledger_layers_carry_the_ledger_id(self):
        self.assertEqual({r["configuration_id"]
                          for r in _rows("pakemis_monthly_ledger_2024.csv")},
                         {conf.LEDGER})
        self.assertEqual({r["configuration_id"]
                          for r in _rows("pakemis_adm2_ledger_2024.csv")},
                         {conf.LEDGER})


class TestTheLedgerRowsClose(unittest.TestCase):
    def test_annual_ledger_rows_are_residential_only(self):
        """The identity: every non-residential sector is IDENTICAL under L by
        construction, so its L rows are deliberately absent - duplication would
        invite the two copies to drift. The id is period-named, so the rows are the
        reference year's and no other."""
        led = [r for r in _rows("pakemis_annual_fy2015_16_fy2023_24.csv")
               if r["configuration_id"] == conf.LEDGER]
        self.assertTrue(led)
        self.assertEqual({r["sector"] for r in led}, {"residential"})
        self.assertEqual({r["period_label"] for r in led}, {"FY2023-24"})
        self.assertEqual({r["grain"] for r in led}, {"category_gas"})

    def test_annual_totals_are_the_register_values(self):
        """Each side of the register against the annual product. Through rc66 the
        alternative's rows summed to the register's S (then 24.334, the 2024-25 round as
        measured); they are configuration L's now (29.467), and the reference's own
        residential rows are the register's S (24.22, the two-round series)."""
        annual = [r for r in _rows("pakemis_annual_fy2015_16_fy2023_24.csv")
                  if r["sector"] == "residential" and r["period_label"] == "FY2023-24"
                  and r["grain"] == "category_gas" and r["co2e_Mt_AR5"]]
        register = {r["configuration"]: float(r["co2e_Mt_AR5"])
                    for r in _rows("residential_configurations_2024.csv")}
        ledger = sum(float(r["co2e_Mt_AR5"]) for r in annual
                     if r["configuration_id"] == conf.LEDGER)
        reference = sum(float(r["co2e_Mt_AR5"]) for r in annual
                        if r["configuration_id"] == conf.REFERENCE)
        self.assertAlmostEqual(ledger, register["L"], places=3)
        self.assertAlmostEqual(reference, register["S"], places=3)
        self.assertGreater(ledger, reference)

    def test_the_register_lists_the_reference_first(self):
        """residential_configurations_2024.csv: S, the reference, then L. The order is
        what a reader takes for the headline, and it was L then S through rc66."""
        rows = _rows("residential_configurations_2024.csv")
        self.assertEqual([r["configuration"] for r in rows], ["S", "L"])
        self.assertIn("reference", rows[0]["dung_quantity_basis"])
        self.assertTrue(rows[0]["note"].startswith("the reference"))
        self.assertNotIn("reference", rows[1]["dung_quantity_basis"])

    def test_the_national_identity_holds(self):
        """REF national - residential S + residential L == the published L total.

        The same identity as before rc67 with the two sides exchanged: the reference
        file carries the survey's dung, so the ledger total is reached by taking the
        survey's residential out and putting the ledger's in."""
        register = {r["configuration"]: float(r["co2e_Mt_AR5"])
                    for r in _rows("residential_configurations_2024.csv")}
        ref_total = next(float(r["co2e_Mt_AR5"])
                         for r in _rows("national_all_sectors.csv")
                         if r["row_kind"] == "national_total")
        led_total = next(float(r["co2e_Mt_AR5"])
                         for r in _rows("national_all_sectors_ledger.csv")
                         if r["row_kind"] == "national_total")
        # the register publishes three decimals, so the identity is exact only
        # to the coarser of the two roundings
        self.assertAlmostEqual(ref_total - register["S"] + register["L"],
                               led_total, places=2)
        self.assertGreater(led_total, ref_total)

    def test_the_national_files_name_their_own_dung_axis(self):
        """The reference file says S on every row and the ledger file says L. A file
        renamed without its axis column following is the half-done rename this guards."""
        self.assertEqual({r["residential_dung_axis"]
                          for r in _rows("national_all_sectors.csv")}, {"S"})
        self.assertEqual({r["residential_dung_axis"]
                          for r in _rows("national_all_sectors_ledger.csv")}, {"L"})

    def test_the_dung_residual_row_ships_typed(self):
        """The diverted dung with no household destination. Through rc66 it was ONE
        row, under S_2023_24, because only the alternative left dung unburned. Since
        rc67 the reference leaves it unburned in every year, so the row belongs to the
        reference, appears once per fiscal year, and configuration L (which burns all
        of it) has none. It carries a mass in its note and never a CO2e."""
        rows = [r for r in _rows("pakemis_annual_fy2015_16_fy2023_24.csv")
                if r["grain"] == "residual_no_pathway"]
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({r["period_label"] for r in rows}), 9)
        for row in rows:
            self.assertEqual(row["configuration_id"], conf.REFERENCE)
            self.assertEqual(row["sector"], "residential")
            self.assertEqual(row["category"], "Diverted dung, unresolved fate")
            self.assertIn("no emissions pathway", row["gap_id"])
            self.assertEqual(row["co2e_Mt_AR5"], "")
            self.assertEqual(row["co2e_Mt_AR6"], "")
            self.assertEqual(row["gas"], "")

    def test_the_residual_mass_is_diverted_less_household(self):
        """The mass each residual row quotes is that year's unresolved mass in the
        dung-fate product (47.81 Mt in FY2023-24; the single rc66 row said 46.72,
        measured against the 2024-25 round alone)."""
        import re
        fate = {r["period_id"]: float(r["unresolved_Mt"])
                for r in _rows("pakemis_dung_fate_by_year.csv")
                if r["is_reference"] == "yes"}
        rows = [r for r in _rows("pakemis_annual_fy2015_16_fy2023_24.csv")
                if r["grain"] == "residual_no_pathway"]
        for row in rows:
            quoted = float(re.search(r"\(([0-9.]+) Mt air-dry mass", row["gap_id"]).group(1))
            self.assertAlmostEqual(quoted, fate[row["period_label"]], delta=0.006,
                                   msg=row["period_label"])
        self.assertAlmostEqual(fate["FY2023-24"], 47.81, places=2)

    def test_the_ledger_spatial_products_conserve_every_gas(self):
        """rc41 (the nineteenth review's S-1): the second-configuration ADM2 product used
        to be every residential row rescaled by one per-province CO2e ratio, which moved
        CO2 by -3,206.85 Gg and CH4 by +101.47 Gg against its monthly product while the
        CO2e aggregate looked right. The products are gridded stream by stream now, and
        this holds each GAS: national L (the monthly L product) == ADM1 L == ADM2 L +
        OUTSIDE, and L - REF per gas is exactly the two dung-cake streams' difference.

        Since rc67 the second configuration is L and the difference is POSITIVE: the
        ledger burns more dung than the survey reports, so its CH4 and N2O are larger."""
        def by_gas(rows, value="emissions_Gg", **where):
            out = {}
            for r in rows:
                if any(r.get(k) != v for k, v in where.items()):
                    continue
                if r.get("absence_reason") or r[value] == "":
                    continue
                out[r["gas"]] = out.get(r["gas"], 0.0) + float(r[value])
            return out
        national = by_gas(_rows("pakemis_monthly_ledger_2024.csv"))
        adm1 = by_gas(_rows("pakemis_adm1_ledger_2024.csv"))
        adm2 = by_gas(_rows("pakemis_adm2_ledger_2024.csv"))   # shapes + OUTSIDE
        self.assertEqual(set(national), set(adm1))
        self.assertEqual(set(national), set(adm2))
        for gas, total in national.items():
            self.assertLess(abs(adm1[gas] - total), max(1e-6 * total, 1e-6), "ADM1 %s" % gas)
            self.assertLess(abs(adm2[gas] - total), max(1e-6 * total, 1e-6), "ADM2 %s" % gas)
        ref = by_gas(_rows("national_monthly_2024.csv"), sector="residential")
        dung_ref = by_gas([r for r in _rows("national_monthly_2024.csv")
                           if r["sector"] == "residential" and "dung" in r["subitem"].lower()])
        dung_l = by_gas([r for r in _rows("pakemis_monthly_ledger_2024.csv")
                         if "dung" in r["subitem"].lower()])
        for gas in national:
            delta = dung_l.get(gas, 0.0) - dung_ref.get(gas, 0.0)
            self.assertLess(abs((national[gas] - ref[gas]) - delta), 1e-6,
                            "%s: L - REF is not the dung streams' difference" % gas)
        self.assertEqual(dung_l.get("CO2", 0.0), dung_ref.get("CO2", 0.0),
                         "the dung basis moves CO2 - it must not")
        for gas in ("CH4", "N2O"):
            self.assertGreater(dung_l[gas], dung_ref[gas],
                               "%s: the ledger must burn more dung than the survey" % gas)

    def test_the_ledger_adm2_rows_are_stream_grained(self):
        rows = _rows("pakemis_adm2_ledger_2024.csv")
        self.assertEqual({r["module"] for r in rows}, {"residential"})
        self.assertEqual(len({r["source_stream_id"] for r in rows}), 23)
        self.assertTrue(any(r["province"] == "OUTSIDE" for r in rows))
        self.assertTrue(any(r["absence_reason"] == "unresolved-in-grid" for r in rows))

if __name__ == "__main__":
    unittest.main()
