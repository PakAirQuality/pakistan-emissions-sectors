"""Gates on the common draw ensemble - the twelfth review's draw_id contract.

The two closure identities the deterministic products enforce at 1e-9 must hold
INSIDE EVERY DRAW: twelve months sum to the year, provinces plus the
retained-at-ADM1 column sum to the nation. And draw d must be draw d everywhere:
the annual layer is a bit-identical prefix of the published national pool, so a
reader joining the three files on draw_id is looking at one realisation, not
three.

Run:  python3 -m unittest discover tests
"""
import json
import os
import unittest
from _support import ROOT

DRAWS = os.path.join(ROOT, "outputs", "mc_draws")
ANNUAL = os.path.join(DRAWS, "pakemis_ensemble_annual.parquet")
MONTHLY = os.path.join(DRAWS, "pakemis_ensemble_monthly.parquet")
SPATIAL = os.path.join(DRAWS, "pakemis_ensemble_spatial.parquet")


def _pd():
    import pandas as pd
    return pd


class TheClosures(unittest.TestCase):
    """Per-draw arithmetic, checked over every one of the 10,000 draws."""

    @classmethod
    def setUpClass(cls):
        pd = _pd()
        cls.annual = pd.read_parquet(ANNUAL)
        cls.categories = [c for c in cls.annual.columns
                          if c not in ("draw_id", "NATIONAL_TOTAL")]

    def test_ten_thousand_draws_and_twenty_categories(self):
        self.assertEqual(len(self.annual), 10000)
        self.assertEqual(len(self.categories), 23)   # rc52: + ammonia, steel, lubricants

    def test_national_equals_the_category_sum_in_every_draw(self):
        err = (self.annual[self.categories].sum(axis=1)
               - self.annual["NATIONAL_TOTAL"]).abs().max()
        self.assertLess(err, 1e-9)

    def test_every_draws_twelve_months_sum_to_its_annual_draw(self):
        pd = _pd()
        monthly = pd.read_parquet(MONTHLY)
        sums = monthly.groupby(["draw_id", "category"],
                               observed=True)["co2e_Mt_AR5"].sum().unstack()
        indexed = self.annual.set_index("draw_id")
        for c in self.categories:
            rel = (sums[c] - indexed[c]).abs().max() / max(indexed[c].max(), 1e-9)
            self.assertLess(rel, 1e-9, c)
        months = monthly.groupby("draw_id", observed=True)["month"].nunique()
        self.assertTrue((months == 12).all())

    def test_every_draws_provinces_plus_unallocated_sum_to_its_annual_draw(self):
        pd = _pd()
        spatial = pd.read_parquet(SPATIAL)
        sums = spatial.groupby(["draw_id", "category"],
                               observed=True)["co2e_Mt_AR5"].sum().unstack()
        indexed = self.annual.set_index("draw_id")
        for c in self.categories:
            rel = (sums[c] - indexed[c]).abs().max() / max(indexed[c].max(), 1e-9)
            self.assertLess(rel, 1e-9, c)

    def test_the_retained_placement_is_present_and_industrial(self):
        """The S4 ledger's retained-at-ADM1 mass must ride its own placement
        label, never be spread to the grid. rc47 Wave 4 changed WHO carries it:
        industry got its geography (kiln points, the clinker register,
        built-up), so the retained mass is now domestic aviation's cruise share
        - and industry appearing here again would mean its placement silently
        regressed, which is the second assertion."""
        pd = _pd()
        spatial = pd.read_parquet(SPATIAL)
        from pkinv.report import common_ensemble as ce
        retained = spatial[spatial["placement"] == ce.PLACEMENT_RETAINED]
        nonzero = retained.groupby("category",
                                   observed=True)["co2e_Mt_AR5"].max()
        self.assertGreater(nonzero.get("Domestic aviation", 0.0), 0.0)
        self.assertEqual(nonzero.get("Industrial fuel combustion (1A2)", 0.0),
                         0.0, "industry's placement regressed to retained")
        self.assertEqual(set(spatial["placement"].unique()),
                         {ce.PLACEMENT_GRIDDED, ce.PLACEMENT_RETAINED})


class ThePrefix(unittest.TestCase):
    """draw d is draw d: a fresh, shorter run reproduces the shipped draws
    bit-identically, which is what licenses calling the ensemble a prefix of
    the published 100,000-draw pool."""

    def test_a_500_draw_rerun_is_a_bit_identical_prefix(self):
        """Bit-identical on the platform that produced the shipped files; elsewhere the
        same draws to 1e-12 relative. rc40 ran this inside the validation package's Linux
        container (aarch64, glibc libm) and the rerun differed from the macOS-built files
        in the last bit (1e-16 relative) - summation order and libm, not the draws. The
        identity claim is a property of one run and is asserted as such: exact where the
        platform matches, and a tolerance that no re-seeding could pass elsewhere."""
        pd = _pd()
        from pkinv.report import common_ensemble as ce
        annual = pd.read_parquet(ANNUAL)
        order, cat_samples, total_samples, _det, _sector_of = \
            ce.annual_draws(n_iter=500)
        exact = True
        for c in list(order) + ["NATIONAL_TOTAL"]:
            shipped = annual[c].tolist()[:500]
            rerun = total_samples if c == "NATIONAL_TOTAL" else cat_samples[c]
            if shipped == rerun:
                continue
            exact = False
            worst = max(abs(a - b) / max(abs(a), 1e-12) for a, b in zip(shipped, rerun))
            self.assertLess(worst, 1e-12, "%s: the rerun differs from the shipped prefix by %.3e relative, "
                            "more than libm can explain - the draws are not the same draws" % (c, worst))
        if not exact:
            print("  prefix identical to 1e-12 relative, not bit for bit: a cross-platform rerun")


class TheProfiles(unittest.TestCase):
    """Drawn where measured, degenerate elsewhere - and both provable from the
    shipped files."""

    @classmethod
    def setUpClass(cls):
        pd = _pd()
        cls.pd = pd
        cls.annual = pd.read_parquet(ANNUAL).set_index("draw_id")
        cls.monthly = pd.read_parquet(MONTHLY)
        with open(MONTHLY.rsplit(".", 1)[0] + ".meta.json",
                  encoding="utf-8") as f:
            cls.meta = json.load(f)

    def test_the_drawn_categories_are_exactly_the_measured_ones(self):
        from pkinv.report import common_ensemble as ce
        self.assertEqual(sorted(ce.measured_profile_sigmas()),
                         self.meta["drawn_profile_categories"])

    def test_drawn_weights_vary_and_sum_to_one_inside_every_draw(self):
        for category in self.meta["drawn_profile_categories"]:
            block = self.monthly[self.monthly["category"] == category]
            shares = block.set_index(["draw_id", "month"])["co2e_Mt_AR5"] \
                .unstack().div(self.annual[category], axis=0)
            sums = shares.sum(axis=1)
            self.assertLess((sums - 1.0).abs().max(), 1e-9, category)
            self.assertGreater(shares.std(axis=0).max(), 0.0, category)

    def test_a_degenerate_category_has_identical_shares_in_every_draw(self):
        drawn = set(self.meta["drawn_profile_categories"])
        candidates = [c for c in self.annual.columns
                      if c not in drawn and c != "NATIONAL_TOTAL"]
        category = sorted(candidates)[0]
        block = self.monthly[self.monthly["category"] == category]
        shares = block.set_index(["draw_id", "month"])["co2e_Mt_AR5"] \
            .unstack().div(self.annual[category], axis=0)
        self.assertLess(shares.std(axis=0).max(), 1e-12, category)


class TheProvenance(unittest.TestCase):
    def test_every_sidecar_hash_matches_its_file(self):
        import hashlib
        for path in (ANNUAL, MONTHLY, SPATIAL):
            with open(path.rsplit(".", 1)[0] + ".meta.json",
                      encoding="utf-8") as f:
                meta = json.load(f)
            digest = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    digest.update(chunk)
            self.assertEqual(meta["sha256"], digest.hexdigest(),
                             os.path.basename(path))

    def test_the_conditionals_carry_no_probability_and_an_affected_mass(self):
        import csv
        path = os.path.join(ROOT, "outputs",
                            "pakemis_ensemble_spatial_conditionals.csv")
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(line for line in f
                                       if not line.startswith("#")))
        self.assertTrue(rows)
        for col in rows[0]:
            for word in ("probability", "weight", "likelihood", "prior"):
                self.assertNotIn(word, col.lower())
        for r in rows:
            self.assertGreater(float(r["affected_Mt"]), 0.0)

    def test_the_summary_declares_every_categorys_profile_status(self):
        import csv
        path = os.path.join(ROOT, "outputs", "pakemis_ensemble_summary.csv")
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(line for line in f
                                       if not line.startswith("#")))
        statuses = {r["name"]: r["profile_uncertainty_status"] for r in rows}
        self.assertEqual(statuses.pop("NATIONAL_TOTAL"), "not_applicable")
        # Wave 3 widened the drawn family: a two-instrument crosscheck's mean
        # absolute share gap is the same measured L1 quantity a hindcast WAPE is,
        # earned against a rival instrument instead of held truth. Both statuses
        # must actually occur - the crosscheck lane going silent would mean the
        # bracket reader lost its second source.
        allowed = {"drawn_measured_hindcast_dispersion",
                   "drawn_measured_crosscheck_disagreement",
                   "degenerate_no_measured_dispersion"}
        self.assertTrue(set(statuses.values()) <= allowed, statuses)
        self.assertIn("drawn_measured_hindcast_dispersion",
                      set(statuses.values()))
        self.assertIn("drawn_measured_crosscheck_disagreement",
                      set(statuses.values()))


if __name__ == "__main__":
    unittest.main()
