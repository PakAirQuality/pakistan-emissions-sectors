"""The gas-flow crosswalk: each delivered stream has a flow kind, a factor boundary and a
carbon destination, and the account closes on volume in every year.

WHY. Through rc66 the post-meter leak factor was charged on fertiliser feedstock, which is
reformed and never burned. The gas ledger said so in a note; nothing classified the streams
by the kind of flow they are, which is what the factor's definition turns on. The crosswalk
(outputs/pakemis_gas_flow_crosswalk.csv) is that classification, and these tests hold it to
the three things a reader relies on: the vocabulary is closed, the volumes are the
regulator's, and the base it states is the base the engine charges.
"""
import collections
import csv
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import gas_flow_crosswalk as crosswalk          # noqa: E402
from pkinv.sectors.fugitives.data import FugitivesData            # noqa: E402

PRODUCT = os.path.join(ROOT, "outputs", "pakemis_gas_flow_crosswalk.csv")
ACTIVITY = os.path.join(ROOT, "data", "sectors", "fugitives", "activity")


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheCrosswalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(PRODUCT)
        cls.by_period = collections.defaultdict(list)
        for row in cls.rows:
            cls.by_period[row["period_id"]].append(row)
        cls.data = FugitivesData()

    def test_nine_periods_and_a_closed_vocabulary(self):
        self.assertEqual(len(self.by_period), 9)
        for row in self.rows:
            self.assertIn(row["flow_kind"], crosswalk.FLOW_KINDS, row["stream"])
            self.assertIn(row["carbon_status"], crosswalk.CARBON_STATUSES, row["stream"])
            self.assertTrue(row["carbon_category"], row["stream"])
            self.assertTrue(row["leak_treatment"], row["stream"])
        self.assertEqual({r["flow_kind"] for r in self.rows}, set(crosswalk.FLOW_KINDS) - {
            "leakage_represented_elsewhere"},
            "five kinds classify a volume; the sixth is a leak treatment, carried in its "
            "own column on the streams it applies to")
        self.assertTrue(any(r["leak_treatment"].startswith("leakage_represented_elsewhere")
                            for r in self.rows))

    def test_feedstock_is_outside_the_base_and_process_fuel_inside_every_year(self):
        for period, rows in self.by_period.items():
            by = {r["stream"]: r for r in rows}
            feed, fuel = by["Fertiliser: feedstock"], by["Fertiliser: process fuel"]
            self.assertEqual(feed["flow_kind"], "chemical_feedstock")
            self.assertEqual(feed["in_post_meter_base"], "no", period)
            self.assertEqual(feed["post_meter_ch4_kt"], "", period)
            self.assertEqual(fuel["flow_kind"], "process_fuel")
            self.assertEqual(fuel["in_post_meter_base"], "yes", period)
            whole = by["MEMO: fertiliser class (feed + process fuel)"]
            self.assertAlmostEqual(float(feed["mmcfd"]) + float(fuel["mmcfd"]),
                                   float(whole["mmcfd"]), places=1, msg=period)

    def test_the_additive_rows_sum_to_the_printed_consumption(self):
        """The fugitives history carries the regulator's SECTOR SUBTOTAL through FY2020-21
        and its consumption WITH company own use from FY2021-22, so the control is met by
        the sector rows alone in the first six years and by sectors plus own use after.
        Either way no volume is unaccounted and none is invented."""
        control = crosswalk.controls()
        for period, rows in self.by_period.items():
            year = int(period[2:6]) + 1
            additive = [r for r in rows if r["additive_to_delivered"] == "yes"]
            sectors = sum(float(r["mmcfd"]) for r in additive
                          if r["stream"] != "Own use and other")
            everything = sum(float(r["mmcfd"]) for r in additive)
            target = sectors if year <= 2021 else everything
            self.assertAlmostEqual(target, control[year][0],
                                   delta=crosswalk.ROUNDING_MMCFD, msg=period)

    def test_the_stated_base_is_the_base_the_engine_charges(self):
        """The defect this product exists for was a membership stated in one place and
        applied in another. Every year, the streams flagged as in the base must be the
        activity the fugitives ledger multiplies its factor by."""
        from pkinv.sectors.fugitives import segment_inventory
        for period, rows in self.by_period.items():
            year = int(period[2:6]) + 1
            stated = sum(float(r["million_m3"]) for r in rows
                         if r["in_post_meter_base"] == "yes")
            charged = next(r for r in segment_inventory.inventory_rows(self.data, year=year)
                           if r["subitem"] == "Post-meter industrial and power"
                           and r["gas"] == "CH4")
            self.assertAlmostEqual(stated, charged["activity_value"],
                                   delta=charged["activity_value"] * 1e-3, msg=period)
            leak = next(r for r in rows if r["stream"].startswith("MEMO: post-meter"))
            self.assertAlmostEqual(float(leak["post_meter_ch4_kt"]),
                                   charged["emissions_Gg"], delta=0.2, msg=period)

    def test_the_feed_fraction_is_labelled_wherever_it_is_carried(self):
        for period, rows in self.by_period.items():
            feed = next(r for r in rows if r["stream"] == "Fertiliser: feedstock")
            word = "observed" if period == "FY2023-24" else "carried"
            self.assertIn("feed fraction %s from FY2023-24" % word, feed["note"], period)

    def test_the_carbon_comparison_is_published_as_open(self):
        """The ledger closes on volume. It does not close on carbon, and the product must
        say so in the row instead of leaving two numbers side by side to be read as one."""
        for period, rows in self.by_period.items():
            memo = next(r for r in rows if r["stream"].startswith("MEMO: fertiliser"))
            low, high, booked = (float(memo["gas_carbon_potential_Mt_CO2_low"]),
                                 float(memo["gas_carbon_potential_Mt_CO2_high"]),
                                 float(memo["carbon_booked_Mt_CO2"]))
            self.assertLess(low, high)
            self.assertLess(booked, low, "%s: if the booked carbon ever enters the band, "
                            "the note calling this an open difference is stale" % period)
            self.assertIn("OPEN DIFFERENCE", memo["note"])

    def test_no_stream_claims_a_combustion_booking_it_does_not_have(self):
        by = {r["stream"]: r for r in self.by_period["FY2023-24"]}
        self.assertEqual(by["Commercial"]["carbon_status"], "not_estimated_declared")
        self.assertIn("K-Electric", by["Power"]["carbon_basis"])
        self.assertEqual(by["Transmission and distribution losses"]["additive_to_delivered"],
                         "no")


class TestTheHeldClassTables(unittest.TestCase):
    """The engine's fertiliser class against the two other places the same print lives."""

    def test_the_engine_ingest_agrees_with_the_class_series_where_it_is_comparable(self):
        held = {int(r["fiscal_year"]): float(r["total_mmcfd"])
                for r in _rows(os.path.join(ACTIVITY, "fertilizer_gas_class.csv"))}
        self.assertEqual(sorted(held), list(range(2016, 2025)))
        compared = 0
        for r in _rows(os.path.join(ROOT, "outputs", "ogra_gas_class_series.csv")):
            if r["gas_class"] != "fertilizer" or r["class_comparable"] != "yes":
                continue
            year = int(r["period_id"][2:6]) + 1
            if year in held:
                self.assertEqual(held[year], float(r["mmcfd_total"]), r["period_id"])
                compared += 1
        self.assertEqual(compared, 7, "seven editions carry a text layer and a comparable row")

    def test_the_two_transcribed_years_close_on_their_printed_subtotals(self):
        rows = _rows(os.path.join(ACTIVITY, "ogra_sector_gas_2021_2023.csv"))
        printed = {"2021": (1788.0, 943.0, 1153.0, 3884.0)}
        for year, expected in printed.items():
            sectors = [r for r in rows if r["fiscal_year"] == year
                       and r["gas_class"] not in ("own_use_and_other", "td_losses")]
            sums = tuple(sum(float(r[c]) for r in sectors) for c in (
                "sngpl_mmcfd", "ssgcl_mmcfd", "independent_mmcfd", "total_mmcfd"))
            self.assertEqual(sums, expected, year)
        restated = [r for r in rows if r["fiscal_year"] == "2023"
                    and r["gas_class"] not in ("own_use_and_other", "td_losses")]
        self.assertAlmostEqual(sum(float(r["total_mmcfd"]) for r in restated), 3373.0,
                               delta=1.0, msg="the 2022-23 edition's printed sub total")
        for r in rows:
            self.assertAlmostEqual(
                float(r["sngpl_mmcfd"]) + float(r["ssgcl_mmcfd"])
                + float(r["independent_mmcfd"]), float(r["total_mmcfd"]), places=6,
                msg="%s %s" % (r["fiscal_year"], r["gas_class"]))

    def test_the_fertiliser_rows_agree_between_the_two_ingests(self):
        engine = {r["fiscal_year"]: r["total_mmcfd"]
                  for r in _rows(os.path.join(ACTIVITY, "fertilizer_gas_class.csv"))}
        for r in _rows(os.path.join(ACTIVITY, "ogra_sector_gas_2021_2023.csv")):
            if r["gas_class"] == "fertilizer":
                self.assertEqual(engine[r["fiscal_year"]], r["total_mmcfd"])

    def test_the_reference_year_row_is_the_end_use_partitions_row(self):
        partition = next(r for r in _rows(os.path.join(
            ACTIVITY, "post_meter_end_use_2023_24.csv")) if r["end_use"] == "Fertilizer")
        engine = next(r for r in _rows(os.path.join(ACTIVITY, "fertilizer_gas_class.csv"))
                      if r["fiscal_year"] == "2024")
        self.assertEqual(float(partition["throughput_mmcfd"]), float(engine["total_mmcfd"]))


class TestTheProductIsCurrent(unittest.TestCase):
    def test_the_builder_reproduces_the_shipped_file(self):
        built = crosswalk.build()
        shipped = _rows(PRODUCT)
        self.assertEqual(len(built), len(shipped))
        for a, b in zip(built, shipped):
            self.assertEqual({k: str(v) for k, v in a.items()}, b)

    def test_the_module_runs_as_a_script(self):
        run = subprocess.run([sys.executable, "-c",
                              "import pkinv.report.gas_flow_crosswalk as m; m.build()"],
                             cwd=ROOT, capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"),
                                      PKINV_ROOT=ROOT))
        self.assertEqual(run.returncode, 0, run.stderr[-800:])


if __name__ == "__main__":
    unittest.main()
