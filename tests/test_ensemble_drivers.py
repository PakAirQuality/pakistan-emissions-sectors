"""What drives the national uncertainty is read from the ensemble that is released.

WHY. Through rc66 driver statements rested on three things that disagreed: the Approach 1
quadrature, a Sobol decomposition of a surrogate of the model, and prose. rc67 retired the
surrogate products and made outputs/pakemis_uncertainty_drivers.csv the one source: shares of
the released ensemble's own variance and tails. These tests hold it to being a decomposition
(the shares sum to one because the total is the sum of its categories), to being computed
from the shipped draws, and to claiming nothing at parameter grain beyond the one row it can
support.
"""
import csv
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import ensemble_drivers as drivers          # noqa: E402

PRODUCT = os.path.join(ROOT, "outputs", "pakemis_uncertainty_drivers.csv")
SHARES = ("variance_share", "upper_tail_excess_share", "lower_tail_excess_share")


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheDrivers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(PRODUCT)
        cls.categories = [r for r in cls.rows if r["grain"] == "category"]
        cls.sectors = [r for r in cls.rows if r["grain"] == "sector"]
        cls.columns, cls.total = drivers.load()

    def test_the_shares_are_a_decomposition(self):
        """Category shares sum to one, and so do sector shares: the total is the sum of
        its categories in every draw, so covariance with the total partitions its variance."""
        for group, name in ((self.categories, "category"), (self.sectors, "sector")):
            for share in SHARES:
                got = sum(float(r[share]) for r in group)
                self.assertAlmostEqual(got, 1.0, delta=2e-5 * len(group),
                                       msg="%s %s sums to %.6f" % (name, share, got))

    def test_every_ensemble_category_is_a_row(self):
        self.assertEqual({r["name"] for r in self.categories}, set(self.columns))
        self.assertEqual(len({r["n_draws"] for r in self.rows}), 1)
        self.assertEqual(int(self.rows[0]["n_draws"]), len(self.total))

    def test_the_shares_are_the_shipped_draws_own(self):
        """Recomputed here from the parquet, independently of the builder's own loop."""
        n = len(self.total)
        mean_t = sum(self.total) / n
        var_t = sum((t - mean_t) ** 2 for t in self.total) / (n - 1)
        for r in self.categories:
            x = self.columns[r["name"]]
            mean_x = sum(x) / n
            cov = sum((a - mean_x) * (b - mean_t) for a, b in zip(x, self.total)) / (n - 1)
            self.assertAlmostEqual(float(r["variance_share"]), cov / var_t, places=5,
                                   msg=r["name"])

    def test_ranks_follow_the_variance_share(self):
        for group in (self.categories, self.sectors):
            ordered = sorted(group, key=lambda r: -float(r["variance_share"]))
            self.assertEqual([int(r["rank_by_variance_share"]) for r in ordered],
                             list(range(1, len(group) + 1)))

    def test_fixing_the_leading_category_narrows_the_interval(self):
        ordered = sorted(self.total)
        from pkinv.core import montecarlo
        width = montecarlo.percentile(ordered, 0.975) - montecarlo.percentile(ordered, 0.025)
        lead = min(self.categories, key=lambda r: int(r["rank_by_variance_share"]))
        fixed = float(lead["national_p97_5_if_fixed"]) - float(lead["national_p2_5_if_fixed"])
        self.assertLess(fixed, width, "%s leads the variance and fixing it must narrow "
                        "the interval" % lead["name"])

    def test_one_parameter_row_and_no_parameter_ranking(self):
        """The effluent factor is the only parameter the product speaks about, and it is
        not ranked against categories: parameter-level importance is not claimed."""
        parameters = [r for r in self.rows if r["grain"] == "parameter"]
        self.assertEqual(len(parameters), 1)
        row = parameters[0]
        self.assertIn("ww_ef_effluent", row["name"])
        self.assertEqual(row["rank_by_variance_share"], "")
        wastewater = next(r for r in self.categories if r["name"] == "Domestic wastewater")
        self.assertLessEqual(float(row["variance_share"]),
                             float(wastewater["variance_share"]) + 1e-6,
                             "one factor cannot carry more variance than its category")
        self.assertGreater(float(row["variance_share"]), 0.0)

    def test_the_retired_surrogate_products_are_gone(self):
        for name in ("national_variance_attribution.csv",
                     "pakemis_variance_estimator_sweep.csv",
                     "pakemis_effluent_tail_diagnostic.csv"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, "outputs", name)), name)
        for module in ("variance_attribution", "variance_estimator_sweep", "effluent_tail"):
            self.assertFalse(os.path.exists(
                os.path.join(ROOT, "src", "pkinv", "report", module + ".py")), module)


if __name__ == "__main__":
    unittest.main()
