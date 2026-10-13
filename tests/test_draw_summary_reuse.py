"""The waste summary is exactly the prefix of the national draw pool."""
import unittest
from unittest.mock import patch

from pkinv.core import mc_draws
from pkinv.sectors.waste import uncertainty
from pkinv.sectors.waste.data import WasteData


class DrawSummaryReuse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = WasteData()
        cls.expected, sums, totals = uncertainty.parameter_rerun_mc(
            cls.data, n_iter=30, return_samples=True)
        cls.columns = dict(sums, MODULE_TOTAL=totals)
        cls.meta = {"seed": uncertainty.RERUN_SEED, "n_iter": 30,
                    "distribution_id": "parameter_rerun_ledger_true",
                    "rng": mc_draws.RNG_IDENTITY,
                    "deterministic": {("MODULE_TOTAL" if r["scope"] == "SECTOR" else r["scope"]):
                                      r["deterministic"] for r in cls.expected}}

    def test_summary_preserves_every_statistic_without_resampling(self):
        with patch.object(mc_draws, "read", return_value=(self.columns, self.meta)), patch.object(
                uncertainty, "parameter_rerun_mc", side_effect=AssertionError("resampling")):
            actual = uncertainty.summary_from_draw_file(self.data, n_iter=30)
        self.assertEqual(actual, self.expected)

    def test_different_seed_is_rejected(self):
        with patch.object(mc_draws, "read", return_value=(self.columns, self.meta)):
            with self.assertRaisesRegex(ValueError, "seed, count or engine"):
                uncertainty.summary_from_draw_file(self.data, n_iter=30, seed=1)

    def test_stale_deterministic_values_are_rejected(self):
        meta = dict(self.meta, deterministic=dict(self.meta["deterministic"], MODULE_TOTAL=-1))
        with patch.object(mc_draws, "read", return_value=(self.columns, meta)):
            with self.assertRaisesRegex(ValueError, "stale"):
                uncertainty.summary_from_draw_file(self.data, n_iter=30)
