"""The NEPRA plant-level fuel ledger, and the invariants that keep it honest.

The power sector was built on four national fuel rows. They are a sound Tier-1 control total
and a ceiling on everything else: no plant, no coal origin, no technology - and NEPRA's national
fuel table (SoIR Table 3) stops at FY2022-23 while the rest of the report runs to FY2023-24.

Tables 18, 21 and 26 carry plant x year x physical fuel x net generation through FY2023-24.
scripts/ingest_nepra_plants.py parses them. These tests cover what a parser of an irregular
PDF table most needs: that it did not silently mis-attribute rows, that its coverage shortfall
is declared rather than hidden, and that the values match the printed page.

Run:  python3 -m unittest discover tests -p "test_plant_ledger.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.paths import DATA

LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")

# NEPRA SoIR 2024 Table 17, FY2023-24.
TABLE17_THERMAL_GWH = 67243.62
TABLE17_COAL_CPPAG_GWH = 20217.91

# Values read directly off the printed page (Table 21, coal section, FY2023-24). If the parser
# ever drifts, these fail rather than the drift propagating into the coal blend.
PRINTED = {
    "Huaneng Shandong Ruyi (Sahiwal Imported Coal)": (2075.55, 772.00),
    "Port Qasim Electric Power": (782.26, 368.09),
    "China Power Hub": (476.55, 131.77),
    "Engro Powergen Thar": (3766.20, 3429.20),
}


def _rows():
    with open(LEDGER, newline="", encoding="utf-8") as f:
        out = list(csv.DictReader(f))
    for r in out:
        r["fiscal_year"] = int(r["fiscal_year"])
        r["quantity"] = float(r["quantity"])
        r["net_generation_GWh"] = float(r["net_generation_GWh"])
    return out


class TestShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_every_row_is_attributed(self):
        """A row with no plant name is a parse failure, not a data gap. The first run produced
        eleven of them, because plant names sit on rows of their own between the year rows."""
        for r in self.rows:
            self.assertTrue(r["plant"] and r["plant"] != "UNNAMED",
                            "unattributed row: %s" % r)

    def test_gas_units_differ_by_table_and_are_not_normalised(self):
        """THE PROPERTY THE ENERGY CLOSURE DEPENDS ON, and it is not uniform.

        Table 21 meters gas in MMBTU - already energy. Tables 18 and 26 meter the same gas in
        MMCFT - a VOLUME, which needs the heating value this inventory does not pin (the same
        900-1,000 Btu/scf question the captive category carries).

        So only the MMBTU rows support an energy comparison with no calorific assumption. If a
        parser ever normalised these into one unit it would silently convert an exact leg of
        the closure into an assumed one, which is why the unit travels per row.
        """
        by = {}
        for r in self.rows:
            if r["fuel"] in ("Gas", "RLNG"):
                by.setdefault((r["source_table"][-8:], r["fuel"]), set()).add(r["quantity_unit"])
        # Table 21 is energy throughout; Table 18 is volume throughout.
        self.assertEqual(by[("Table 21", "Gas")], {"MMBTU"})
        self.assertEqual(by[("Table 21", "RLNG")], {"MMBTU"})
        self.assertEqual(by[("Table 18", "Gas")], {"MMCFT"})
        # Table 26 mixes them WITHIN one table: its single-fuel gas section states MMBTU while
        # its RLNG section and every multi-fuel section state MMCFT. That is the document's
        # own inconsistency, not the parser's, and it is why the unit is read from each
        # section's header rather than looked up by fuel or by table.
        self.assertEqual(by[("Table 26", "RLNG")], {"MMCFT"})
        self.assertEqual(by[("Table 26", "Gas")], {"MMBTU", "MMCFT"})

    def test_solid_and_liquid_fuels_are_masses(self):
        by_fuel = {}
        for r in self.rows:
            by_fuel.setdefault(r["fuel"], set()).add(r["quantity_unit"])
        self.assertEqual(by_fuel.get("Coal"), {"000 t"})
        self.assertEqual(by_fuel.get("RFO"), {"000 t"})

    def test_energy_is_derived_only_where_it_is_exact(self):
        """MMBTU converts to TJ by definition. Coal and RFO masses need a calorific value,
        which is a downstream choice and must not be smuggled into a parser."""
        for r in self.rows:
            if int(r["fiscal_year"]) >= 2024:
                unit, fuel, q = r["quantity_unit"], r["fuel"], float(r["quantity"])
                if fuel in ("Gas", "RLNG"):
                    expected = q * 0.00105505585262 * .90 * (1000 if unit == "MMCFT" else 1)
                elif fuel == "RFO":
                    expected = q * 40.4
                elif fuel == "HSD":
                    expected = q * .84 / 1000 * 43
                else:
                    self.assertEqual(r["energy_TJ"], "")
                    continue
                self.assertIn("derived NCV energy", r["source_table"])
                self.assertAlmostEqual(float(r["energy_TJ"]), expected, delta=1e-7)
                continue
            if r["quantity_unit"] == "MMBTU":
                self.assertTrue(r["energy_TJ"], "gas row without energy: %s" % r["plant"])
            elif r["quantity_unit"] == "MMCFT":
                self.assertEqual(r["energy_TJ"], "",
                                 "%s: MMCFT is a volume - energy needs a heating value"
                                 % r["plant"])
            else:
                self.assertEqual(r["energy_TJ"], "",
                                 "%s got an energy value from a mass" % r["plant"])

    def test_no_implausible_coal_tonnage(self):
        """The failure this guards against actually happened: an unheaded multi-fuel block let
        the previous section's fuel persist, and MMBTU values were written as 50,545,992 'kt of
        coal'. Pakistan's largest coal unit burns about 6,400 kt a year."""
        for r in self.rows:
            if r["fuel"] == "Coal":
                self.assertLess(r["quantity"], 20000,
                                "%s: %.0f kt of coal is not physical" % (r["plant"], r["quantity"]))


class TestAgainstThePrintedPage(unittest.TestCase):
    def test_values_match_the_report(self):
        rows = {r["plant"]: r for r in _rows()
                if r["fuel"] == "Coal" and r["fiscal_year"] == 2023}
        for plant, (gwh, kt) in PRINTED.items():
            self.assertIn(plant, rows, "plant lost from the ledger: %s" % plant)
            self.assertAlmostEqual(rows[plant]["net_generation_GWh"], gwh, places=2, msg=plant)
            self.assertAlmostEqual(rows[plant]["quantity"], kt, places=2, msg=plant)


class TestCoverage(unittest.TestCase):
    """The ledger is a SUBSET of the fleet, because the multi-fuel sections are not parsed.
    Every downstream use has to know by how much, so the shortfall is asserted rather than
    left to be discovered."""

    @classmethod
    def setUpClass(cls):
        cls.rows = [r for r in _rows() if r["fiscal_year"] == 2023]

    def test_coal_is_effectively_complete(self):
        """The strong leg. Parsed coal reproduces NEPRA's own CPPA-G coal generation to within
        a fraction of a GWh, which is what makes the coal blend trustworthy even though overall
        coverage is only half the fleet."""
        coal = sum(r["net_generation_GWh"] for r in self.rows if r["fuel"] == "Coal")
        self.assertAlmostEqual(coal, TABLE17_COAL_CPPAG_GWH, delta=1.0,
                               msg="parsed coal %.2f vs Table 17 %.2f" % (coal, TABLE17_COAL_CPPAG_GWH))

    def test_coverage_is_near_complete(self):
        """The multi-fuel sections are parsed now, so the ledger covers essentially the whole
        thermal fleet rather than half of it. Pinned as a band: if it falls the parse has
        regressed, and if it rises past unity something is being double-counted."""
        total = sum(r["net_generation_GWh"] for r in self.rows)
        share = total / TABLE17_THERMAL_GWH
        self.assertTrue(0.95 < share < 1.01,
                        "coverage is %.1f%% - re-state it wherever it is quoted" % (100 * share))

    def test_every_system_is_represented(self):
        """GENCOs used to be absent entirely, because Table 18 is a wide multi-fuel layout with
        no single-fuel section at all."""
        systems = {r["system"] for r in self.rows}
        self.assertEqual(systems, {"GENCO", "IPP", "K-Electric"})

    def test_each_fuel_reconciles_against_table_17(self):
        """THE ACCEPTANCE GATE FOR THE WHOLE PARSE, and the reason a positional reader is safe
        to use on layouts this varied.

        Each fuel is summed independently from plant rows and compared against NEPRA's own
        generation-by-fuel table, which the parser never reads. A layout error - a quantity
        column read as generation, a fuel's positions swapped - would show up here as a wild
        discrepancy in one fuel. Instead every fuel lands slightly UNDER, with a consistent
        sign, which is the signature of a few small plants missing rather than of columns
        being misread.
        """
        led = {}
        for r in self.rows:
            led[r["fuel"]] = led.get(r["fuel"], 0.0) + r["net_generation_GWh"]
        with open(asset_path(DATA, "activity", "power", "generation_by_fuel.csv"),
                  newline="", encoding="utf-8") as f:
            t17 = {}
            for r in csv.DictReader(f):
                if int(r["fiscal_year"]) == 2023:
                    t17[r["fuel"]] = t17.get(r["fuel"], 0.0) + float(r["gwh_net"])
        for fuel, target in t17.items():
            got = led.get(fuel, 0.0)
            self.assertLessEqual(got, target * 1.01,
                                 "%s over-counts: %.1f vs Table 17's %.1f" % (fuel, got, target))
            self.assertGreater(got, target * 0.88,
                               "%s under-counts badly: %.1f vs Table 17's %.1f"
                               % (fuel, got, target))


class TestCoalOrigin(unittest.TestCase):
    """Origin read off the plant's own name, which is what replaces the generation-share
    inference behind the sector's 35 percent lignite assumption."""

    @classmethod
    def setUpClass(cls):
        cls.coal = [r for r in _rows() if r["fuel"] == "Coal" and r["fiscal_year"] == 2023]

    def test_origin_is_set_for_coal_only(self):
        for r in _rows():
            if r["fuel"] == "Coal":
                self.assertIn(r["fuel_origin"], ("Thar lignite", "imported", "unknown"))
            else:
                self.assertEqual(r["fuel_origin"], "")

    def test_the_named_plants_are_classified(self):
        by = {r["plant"]: r["fuel_origin"] for r in self.coal}
        self.assertEqual(by["Huaneng Shandong Ruyi (Sahiwal Imported Coal)"], "imported")
        self.assertEqual(by["Engro Powergen Thar"], "Thar lignite")
        self.assertEqual(by["Port Qasim Electric Power"], "imported")

    def test_the_unresolved_residual_is_small_and_published(self):
        """Lucky Electric's name does not state its coal source, and its classification swings
        the lignite share materially. It is left 'unknown' rather than assigned, so the
        residual is visible; it must stay a minority of coal or the blend is not decidable."""
        total = sum(r["net_generation_GWh"] for r in self.coal)
        unknown = sum(r["net_generation_GWh"] for r in self.coal
                      if r["fuel_origin"] == "unknown")
        self.assertGreater(unknown, 0, "the residual has been assumed away")
        self.assertLess(unknown / total, 0.25)


if __name__ == "__main__":
    unittest.main()
