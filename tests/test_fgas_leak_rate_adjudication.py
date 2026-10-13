"""The F-gas leak-rate screening asserts its own findings, so an outgrown one is loud.

The product is outputs/pakemis_fgas_leak_rate_adjudication.csv, built by
scripts/build_fgas_leak_rate_adjudication.py. 2.F contributes zero to every national
total, so nothing here can move a number; what these guards protect is the STATEMENT -
that one of the three refrigeration/AC strata applies a rate IPCC's own table excludes
for a part of what it lumps, and that the leak rate moves the channel mix far more than
it moves the mass. If the bank's parameters change so that either stops being true, the
screening is wrong in prose and these tests say so rather than passing quietly.
"""
import csv
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCT = os.path.join(ROOT, "outputs", "pakemis_fgas_leak_rate_adjudication.csv")
BUILDER = os.path.join(ROOT, "scripts", "build_fgas_leak_rate_adjudication.py")
VERDICTS = {"one-to-one", "lumped, admissible", "lumped, inadmissible for a part",
            "not governed by this table"}


def rows():
    with open(PRODUCT, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheScreening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()

    def test_the_file_is_populated_and_covers_every_stratum_the_bank_runs(self):
        """The positive control: an empty or truncated file must fail here first."""
        self.assertGreaterEqual(len(self.rows), 6)
        self.assertEqual(
            {r["stratum"] for r in self.rows if r["row_kind"] == "bank_stratum"},
            {"refrigeration", "stationary AC", "mobile AC", "aerosol", "fire protection"},
            "the screening no longer covers exactly the bank's five strata; a stratum "
            "that exists in the bank and not here is an unadjudicated rate")
        self.assertEqual(
            [r["row_kind"] for r in self.rows].count("official_reading"), 1,
            "the official reading of 2.F is the row the strata are compared WITH; "
            "without it the file states a parameter critique and no benchmark")

    def test_nothing_here_is_a_total_column(self):
        measures = {"co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"}
        self.assertFalse(measures & set(self.rows[0]),
                         "the screening has grown a column a national total is summed "
                         "from; 2.F contributes zero and this must stay a screening")

    def test_the_verdict_vocabulary_is_closed(self):
        seen = {r["verdict"] for r in self.rows}
        self.assertEqual(seen - VERDICTS, set(),
                         "undeclared verdict(s) %s" % sorted(seen - VERDICTS))
        self.assertEqual(VERDICTS - seen, set(),
                         "declared verdict(s) %s no longer occur; a stale allowance "
                         "hides the next one" % sorted(VERDICTS - seen))

    def test_every_row_cites_what_it_was_read_from(self):
        for row in self.rows:
            wanted = ("Table 7.9" if row["row_kind"] == "bank_stratum"
                      else "Pakistan CRT")
            self.assertIn(wanted, row["source"], row["stratum"])
            self.assertTrue(row["reference_year"].strip(), row["stratum"])

    def test_the_finding_still_holds_one_stratum_applies_an_excluded_rate(self):
        """The screening's first finding, asserted rather than described."""
        bad = [r for r in self.rows
               if r["verdict"] == "lumped, inadmissible for a part"]
        self.assertEqual([r["stratum"] for r in bad], ["refrigeration"],
                         "the set of strata whose single rate IPCC's table excludes for a "
                         "part has changed; the screening's prose names refrigeration "
                         "alone and must be re-stated")
        self.assertNotEqual(bad[0]["sub_applications_whose_band_excludes_it"], "none")

    def test_the_mechanism_still_holds_the_rate_moves_the_mix_not_the_mass(self):
        """The second finding: with zero recovery, retirement absorbs the leak-rate choice.

        Asserted as an INEQUALITY between two spans rather than as either span's value,
        because the numbers move with every re-parameterisation of the bank and the claim
        does not: the operating channel must swing wider than the stratum total does.
        """
        for row in self.rows:
            if (row["verdict"] == "not governed by this table"
                    or row["row_kind"] != "bank_stratum"):
                continue
            op_lo, op_hi = (float(v) for v in
                            row["operating_channel_low_to_high_Mt"].split("-"))
            total_lo = float(row["stratum_at_envelope_low_Mt"])
            total_hi = float(row["stratum_at_envelope_high_Mt"])
            self.assertGreater(
                op_hi - op_lo, total_hi - total_lo,
                "%s: the operating channel spans %.5f Mt across the band envelope and the "
                "stratum total spans %.5f - the screening's claim is that the first is "
                "always wider, because gas the operating channel does not leak is still "
                "emitted at retirement. If that has stopped holding, the retirement "
                "channel or the recovery fraction has changed"
                % (row["stratum"], op_hi - op_lo, total_hi - total_lo))

    def test_the_channels_sum_to_the_stratum_total(self):
        for row in self.rows:
            if (row["verdict"] == "not governed by this table"
                    or row["row_kind"] != "bank_stratum"):
                continue
            parts = (float(row["stratum_operating_channel_Mt"])
                     + float(row["stratum_retirement_channel_Mt"]))
            total = float(row["stratum_emissions_Mt_co2e_AR5"])
            self.assertLessEqual(
                parts, total + 1e-5,
                "%s: operating + retirement exceeds the stratum total, so one of the "
                "three is not what its name says" % row["stratum"])
            self.assertGreater(parts, 0.9 * total,
                               "%s: operating + retirement is far below the total, so a "
                               "third channel carries mass this screening does not name"
                               % row["stratum"])

    def test_the_official_reading_is_one_species_as_one_percent_of_its_stock(self):
        """The benchmark row's own arithmetic, so a mis-read cell cannot pass as a finding."""
        crt = [r for r in self.rows if r["row_kind"] == "official_reading"][0]
        stock = float(crt["crt_declared_stock_t"])
        factor = float(crt["shipped_operating_loss_pct_yr"])
        emitted = float(crt["crt_emitted_t"])
        self.assertAlmostEqual(
            emitted, stock * factor / 100.0, places=9,
            msg="the CRT row no longer satisfies emissions = stock x factor, so one of "
                "the three cells was read from the wrong place")
        # ... and that the tonnes and the CO2e column are the same quantity. Asserted
        # separately and loosely, because the CO2e column is rounded to 5 dp of Mt and a
        # first version of this guard reconstructed the tonnage THROUGH that rounding and
        # failed on its own arithmetic.
        self.assertAlmostEqual(
            float(crt["stratum_emissions_Mt_co2e_AR5"]), emitted * 12400.0 / 1e6,
            places=5, msg="the CRT row's tonnes and CO2e disagree beyond rounding")
        self.assertIn("HFC-23", crt["note"])
        self.assertIn("2.F.1.a", crt["stratum"])

    def test_it_regenerates_identically(self):
        before = open(PRODUCT, "rb").read()
        run = subprocess.run([sys.executable, BUILDER], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(PRODUCT, "rb").read(),
                         "the screening does not regenerate byte-identically")


if __name__ == "__main__":
    unittest.main()
