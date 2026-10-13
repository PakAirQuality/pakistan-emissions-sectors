"""scripts/check_conservation.py is in the suite: every by-gas identity it states must hold
on the shipped tree, and the script must say so with exit 0.

The identities were asserted at the CO2e grain by a dozen tests before; a gas that moved
while the CO2e total held would have passed all of them. This runs the script itself, so
the thing a reader runs is the thing the suite guards."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "check_conservation.py")


class TestConservationByGas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = subprocess.run([sys.executable, SCRIPT], cwd=ROOT,
                                 capture_output=True, text=True)

    def test_every_identity_holds_and_the_script_exits_zero(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout[-3000:] + self.result.stderr[-2000:])
        self.assertIn("conservation: ALL HOLD", self.result.stdout)
        self.assertNotIn("FAILS", self.result.stdout)

    def test_the_eight_identities_are_all_reported(self):
        """A script that silently dropped an identity would still exit 0."""
        for tag in ("I1 ", "I2 ", "I3 ", "I3b ", "I4 ", "I5 ", "N1 ", "N2 "):
            self.assertIn(tag, self.result.stdout, "identity %s is no longer reported" % tag.strip())

    def test_the_positive_control_the_script_can_fail(self):
        """Run with a tolerance no real data meets: the script must report failures.
        Otherwise 'ALL HOLD' is what it prints regardless of the data."""
        run = subprocess.run([sys.executable, SCRIPT, "--tolerance", "0"], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 1, run.stdout[-1000:])
        self.assertIn("FAILS", run.stdout)


if __name__ == "__main__":
    unittest.main()
