"""The industrial boundary ledger: the priced rows ARE the atom table's industrial
boundary (1.A.2 including captive + IPPU), per period and gas; the reference-year
aggregate closes to the covered-direct-industrial number; every priced component
carries all nine periods (the back-cast invariant); non-priced rows price nothing
into a total (empty co2e_Mt), and the diagnostic stays a diagnostic."""
import collections
import csv
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUTS = os.path.join(os.path.dirname(HERE), "outputs")
LEDGER = os.path.join(OUTPUTS, "pakemis_industry_boundary_ledger.csv")
ATOMS = os.path.join(OUTPUTS, "semantic", "fact_annual.csv")
REF = "REF_2023_24"


def _rows(path):
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


class IndustryBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = _rows(LEDGER)
        cls.priced = [r for r in cls.ledger if r["boundary_status"] == "priced"]

    def test_priced_rows_close_to_the_atom_table(self):
        """Per period, the ledger's priced sum equals the atoms' industrial boundary."""
        want = collections.defaultdict(float)
        for r in _rows(ATOMS):
            if r["configuration_id"] != REF:
                continue
            # the boundary is the industry and ippu REPORTING sectors: captive gas
            # self-generation enters through data/stream_reporting_sector.csv (sector_id
            # power, reporting_sector industry), not through a code match
            if r["reporting_sector"] in ("industry", "ippu"):
                want[r["period_id"]] += float(r["co2e_Mt_AR5"])
        got = collections.defaultdict(float)
        for r in self.priced:
            got[r["period_id"]] += float(r["co2e_Mt"])
        self.assertEqual(set(got), set(want))
        for period, mt in want.items():
            # the ledger prints 6 decimals per row; summed rounding stays under n x half-ulp
            self.assertAlmostEqual(got[period], mt, delta=5e-5, msg=period)

    def test_reference_year_is_the_covered_direct_industrial_number(self):
        ref = sum(float(r["co2e_Mt"]) for r in self.priced if r["period_id"] == "FY2023-24")
        # rc52: 49.95 + ammonia 3.243 + steel 0.393 + lubricants 0.083 = 53.67 (covered direct sources)
        self.assertAlmostEqual(ref, 53.67, places=2)

    def test_every_priced_component_carries_all_nine_periods(self):
        """The back-cast invariant: no component may enter the covered aggregate for
        a subset of years (that would manufacture an apparent trend)."""
        by_component = collections.defaultdict(set)
        for r in self.priced:
            by_component[(r["ipcc_code"], r["component"], r["gas"])].add(r["period_id"])
        for key, periods in by_component.items():
            self.assertEqual(len(periods), 9, msg=str(key))

    def test_non_priced_rows_price_nothing(self):
        for r in self.ledger:
            if r["boundary_status"] != "priced":
                self.assertEqual(r["co2e_Mt"], "", msg=r["component"])
        # the diagnostics name themselves diagnostics, never residuals - EDGAR's reference-year
        # coverage row, the independent UNSD benchmark (Wave 1b) and, since the boundary
        # program's Wave A, one EDGAR SHAPE row per period (the nine-year divergence)
        diags = [r for r in self.ledger if r["boundary_status"] == "diagnostic"]
        series = [d for d in diags if d["component"] == "EDGAR 1.A.2 series divergence"]
        unsd_series = [d for d in diags if d["component"] == "UNSD 1.A.2 series benchmark"]
        self.assertEqual(len(diags), 2 + len(series) + len(unsd_series))
        periods = sorted({r["period_id"] for r in self.priced})
        self.assertEqual(sorted(d["period_id"] for d in series), periods)
        # UNSD's calendar series ends at CY2023: the fiscal blend exists for every period but the
        # last (FY2023-24 needs CY2024), and the builder types that absence by omitting the row
        self.assertEqual(sorted(d["period_id"] for d in unsd_series), periods[:-1])
        for d in series + unsd_series:
            self.assertIn("never a", d["note"].replace("never an", "never a"))
            float(d["bound_high_Mt"])                       # the signed divergence, engine minus benchmark
        self.assertIn("never an EDGAR residual", next(d["note"] for d in diags if d["component"] == "EDGAR 1.A.2 coverage gap"))
        self.assertIn("independent benchmark", next(d["note"] for d in diags if "UNSD" in d["component"]))

    def test_the_states_are_a_closed_vocabulary(self):
        self.assertEqual(
            {r["boundary_status"] for r in self.ledger},
            {"priced", "screened_not_priced", "typed_absent", "diagnostic"})

    def test_captive_is_claimed_for_the_industrial_aggregate(self):
        captive = [r for r in self.priced if r["component"] == "Captive gas self-generation"]
        self.assertTrue(captive)
        for r in captive:
            self.assertEqual(r["module_home"], "power")
            self.assertEqual(r["ipcc_code"], "1.A.2")
        # and it is the reporting axis, not a code match, that claims it
        atoms = [r for r in _rows(ATOMS) if r["configuration_id"] == REF
                 and r["category"] == "Captive gas self-generation (1A2)"]
        self.assertTrue(atoms)
        self.assertEqual({r["sector_id"] for r in atoms}, {"power"})
        self.assertEqual({r["reporting_sector"] for r in atoms}, {"industry"})


if __name__ == "__main__":
    unittest.main()
