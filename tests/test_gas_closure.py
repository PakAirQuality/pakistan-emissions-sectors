"""The national gas closure: the identity holds, bases are closed, the double-claim
is quantified. The closure is a DIAGNOSTIC - it must never alter a total - so the
tests assert its arithmetic and its honesty, not any emission value."""
import csv
import os
import io
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "national_gas_closure.csv")

BASES = ("delivered-sold",
         "delivered-sold; also metered-downstream-of-loss for the leak factor",
         "metered-downstream-of-loss", "consumed-reported", "feedstock")


def _rows():
    return read_rows(OUT, comments=False)


class TestGasClosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()
        # A GAP row states what is not established about a stream already counted
        # elsewhere, so it carries no volume and is not part of the delivered identity.
        # Including it made float("") raise rather than fail, which is how the identity
        # test first reported the new row (2026-10-07).
        cls.uses = [r for r in cls.rows
                    if not r["stream"].startswith(("CLOSURE", "GAP"))]
        cls.gaps = [r for r in cls.rows if r["stream"].startswith("GAP")]
        cls.total = next(r for r in cls.rows
                         if r["stream"] == "CLOSURE: delivered total")
        cls.claim = next(r for r in cls.rows
                         if r["stream"] == "CLOSURE: declared double-claim")

    def test_the_identity_holds(self):
        self.assertAlmostEqual(sum(float(r["annual_million_m3"]) for r in self.uses),
                               float(self.total["annual_million_m3"]), delta=0.5)

    def test_every_stream_declares_a_closed_basis(self):
        for r in self.uses + self.gaps:
            self.assertIn(r["metering_basis"], BASES, r["stream"])

    def test_the_gap_row_carries_no_volume_and_names_the_stream_it_qualifies(self):
        """A GAP row must not be addable. It says which meter a counted stream's activity
        describes, so a volume on it would invite someone to sum it into the delivered
        total - and the identity above would then close on a quantity counted twice."""
        self.assertTrue(self.gaps, "the gas account declares no unestablished boundary; "
                                   "if that is now true the power row's ledger_status "
                                   "should no longer read reconciled_different_meter")
        for r in self.gaps:
            self.assertEqual(r["annual_million_m3"], "", r["stream"])
            self.assertEqual(r["mmcfd"], "", r["stream"])
            self.assertTrue(r["claimed_by"].strip(), r["stream"])
            self.assertIn("NOT A MISSING SOURCE", r["note"], r["stream"])

    def test_the_double_claim_is_quantified_and_removed(self):
        """rc19: the row still quantifies the leak base, and now states that the
        reference booking removed the double-claim rather than keeping it."""
        self.assertIn("REMOVED at rc19", self.claim["note"])
        self.assertIn("NET of that share", self.claim["note"])
        self.assertIn("named alternative", self.claim["note"])
        base = sum(float(r["annual_million_m3"]) for r in self.uses
                   if r["in_post_meter_leak_base"] == "yes")
        self.assertAlmostEqual(float(self.claim["annual_million_m3"]), base,
                               delta=0.5)

    def test_the_feedstock_row_names_what_changed(self):
        """Through rc66 this row was inside the leak base and its note called that "the
        sharpest inconsistency this closure surfaces". rc67 removed it; the row now says
        where the feedstock sits, where its carbon is booked, and which scenario keeps
        the old membership."""
        fert = next(r for r in self.uses if r["stream"] == "Fertilizer: feedstock")
        self.assertEqual(fert["claimed_by"], "EXCLUDED FROM COMBUSTION")
        self.assertEqual(fert["in_post_meter_leak_base"], "no")
        self.assertIn("OUTSIDE the post-meter leak base", fert["note"])
        self.assertIn("post_meter_including_feedstock", fert["note"])
        self.assertNotIn("sharpest inconsistency", fert["note"])

    def test_the_unestimated_use_is_declared(self):
        commercial = next(r for r in self.uses if r["stream"] == "Commercial")
        self.assertEqual(commercial["claimed_by"], "NOT ESTIMATED")

    def test_the_output_regenerates_identically(self):
        from pkinv.report import gas_closure
        fresh = gas_closure.build()
        self.assertEqual(len(fresh), len(self.rows))
        for f, s in zip(fresh, self.rows):
            self.assertEqual(str(f["annual_million_m3"]), s["annual_million_m3"],
                             f["stream"])



class TestLiveJoins(unittest.TestCase):
    """rc14: the ledger joins Table 3.31 to the LIVE module quantities and must
    abort when a same-publication pair drifts. The positive control proves the
    closure has teeth; the vocabulary test keeps the statuses closed."""

    def test_matched_classes_carry_live_quantities(self):
        with open(OUT, newline="", encoding="utf-8") as f:
            rows = {r["stream"]: r for r in csv.DictReader(f)}
        for stream in ("Residential", "General industry", "Cement",
                       "Captive power", "CNG"):
            self.assertEqual(rows[stream]["ledger_status"],
                             "matched_same_publication", stream)
            self.assertTrue(rows[stream]["live_module_mmcfd"].strip(), stream)
        self.assertEqual(rows["Power"]["ledger_status"],
                         "reconciled_different_meter")
        self.assertIn("implied HHV", rows["Power"]["note"])

    def test_statuses_are_from_the_closed_vocabulary(self):
        from pkinv.report import gas_closure
        with open(OUT, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["ledger_status"]:
                    self.assertIn(r["ledger_status"],
                                  gas_closure.LEDGER_STATUSES, r["stream"])

    def test_a_perturbed_live_quantity_aborts_the_build(self):
        """The positive control: 1% drift on a same-publication pair must be a
        build failure, not a silent column."""
        from pkinv.report import gas_closure
        with self.assertRaises(SystemExit):
            gas_closure.build(live_overrides={"General industry": 291 * 1.01})

    def test_the_per_draw_boundary_is_declared(self):
        """rc19 declared the decorrelation; Wave 6 closed it. The OGRA-metered
        combustion/feedstock side shares one activity draw, and the leak side
        now holds per draw through the fugitives file's parameter channel - the
        ledger must say BOTH halves, and must no longer describe the leak as a
        deferred identity."""
        with open(OUT, newline="", encoding="utf-8") as f:
            rows = {r["stream"]: r for r in csv.DictReader(f)}
        note = rows["CLOSURE: shared activity, drawn independently"]["note"]
        self.assertIn("delivered_gas_ogra_3_31", note)
        self.assertIn("holds per draw", note)
        self.assertIn("POST_METER_INDUSTRIAL_MULTIPLIER", note)
        self.assertIn("gas_coupling_scalers", note)
        self.assertIn("separately injected island", note)
        self.assertIn("NEPRA", note)


class TestGrossDeliveredGasVariant(unittest.TestCase):
    """rc19 inverted the variant: the reference is NET of the post-meter leaked
    share (the fourteenth review's physical-atmosphere identity, enforced in the
    booking), and the named alternative restores gross delivered-gas accounting.
    The variant file carries the arithmetic; the configurations product carries
    the POSITIVE delta back to the old gross total."""

    def test_the_variant_file_carries_the_restoration(self):
        import csv
        path = os.path.join(os.path.dirname(OUT), "national_gas_closure_variant.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = {r["configuration"]: r for r in csv.DictReader(
                line for line in handle if not line.startswith("#"))}
        self.assertEqual(float(rows["reference"]["adjustment_Mt_co2e"]), 0.0)
        self.assertIn("CANONICAL SINCE rc19", rows["reference"]["note"])
        adj = float(rows["gross_delivered_gas_accounting"]["adjustment_Mt_co2e"])
        self.assertGreater(adj, 0.0)
        # magnitude sanity: whole-gas leaked share (~1.0%) divided back out of
        # the burned-and-leaked classes' NET gas co2e (~28.6 Mt) - a fraction
        # of a megatonne, never more
        self.assertLess(adj, 1.0)

    def test_the_restoration_prices_booked_not_imputed_co2(self):
        """The rc17 correction, held through the inversion: the base must be
        what the modules book (net, since rc19; the imputed base is printed
        beside it, superseded), the share must be whole gas, and the gross view
        must divide the share back out, not multiply it on."""
        from pkinv.report import gas_closure
        rows = {r["configuration"]: r for r in gas_closure.variant_rows()}
        row = rows["gross_delivered_gas_accounting"]
        booked_net = float(row["booked_net_gas_co2e_of_those_classes_Mt"])
        imputed = float(row["imputed_gas_co2_superseded_Mt"])
        share = float(row["leaked_mass_share_pct"]) / 100.0
        self.assertAlmostEqual(float(row["adjustment_Mt_co2e"]),
                               booked_net * share / (1.0 - share), places=2)
        self.assertLess(booked_net, imputed,
                        "the volume-imputed base overstated grid power against "
                        "its NEPRA TOE booking; booked must sit below it")
        self.assertAlmostEqual(share, (6.1 / 0.90) / 680.0, places=5)

    def test_the_booked_base_is_the_engines_net_booking(self):
        """The variant's base and the engines must be the same number: the sum
        of the four claims' gas rows AS BOOKED (net) times s/(1-s) is exactly
        what the engines would add back if they stopped netting."""
        from pkinv.report import gas_closure
        from pkinv.sectors.fugitives import post_meter
        booked_net = gas_closure._booked_gas_co2e_mt()
        share = post_meter.whole_gas_leak_share()
        gross = booked_net / (1.0 - share)
        self.assertAlmostEqual(gross - booked_net, 0.28767, places=4)

    def test_the_variant_reaches_the_national_configurations(self):
        import csv
        path = os.path.join(os.path.dirname(OUT), "national_configurations.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = {r["configuration_id"]: r for r in csv.DictReader(
                line for line in handle if not line.startswith("#"))}
        self.assertIn("gross_delivered_gas_accounting", rows,
                      "the boundary decision must ship with its other side "
                      "priced - the gross view as a named configuration")
        row = rows["gross_delivered_gas_accounting"]
        self.assertGreater(float(row["national_delta_Mt"]), 0.0)
        self.assertIn("cross-sector", row["module"])


if __name__ == "__main__":
    unittest.main()

class TestThePostMeterBaseHasOneDefinition(unittest.TestCase):
    """The post-meter leak base is defined twice, and the two must agree.

    WHY. src/pkinv/sectors/fugitives/data.py:136-137 takes the anchor-year base from
    `post_meter_nonresidential` in anchor_activity_2023_24.csv (and, for the history years,
    from `eligible_postmeter_mmcfd` x conversion); data.py:150 and :238-260 take membership
    from the `include_in_ipcc_post_meter` column of post_meter_end_use_2023_24.csv. A base
    whose SIZE and whose MEMBERSHIP live in different files can drift apart silently - one
    end use re-labelled, and the leak would be charged on a volume that no longer matches
    the streams it is said to cover. At rc61 they agree: 2439.23 MMCFD x 10.3356 = 25,211
    million m3. This pins them.
    """
    MMCFD_TO_MILLION_M3_PER_YEAR = 1e6 * 0.028316846592 * 365.0 / 1e6   # 10.3356

    @staticmethod
    def _rows(path):
        with io.open(path, encoding="utf-8") as handle:
            body = "".join(l for l in handle if not l.startswith("#"))
        return list(csv.DictReader(io.StringIO(body)))

    def test_the_anchor_base_equals_the_column_defined_membership(self):
        root = os.path.join(ROOT, "data", "sectors", "fugitives", "activity")
        end_use = [r for r in self._rows(os.path.join(root, "post_meter_end_use_2023_24.csv"))
                   if not r["end_use"].startswith("Total")]
        included = [r for r in end_use if r["include_in_ipcc_post_meter"].strip().lower() == "yes"]
        self.assertEqual(len(included), 6, [r["end_use"] for r in included])
        mmcfd = sum(float(r["throughput_mmcfd"]) for r in included)
        anchor = next(r for r in self._rows(os.path.join(root, "anchor_activity_2023_24.csv"))
                      if r["activity_id"] == "post_meter_nonresidential")
        self.assertEqual(anchor["unit"], "million_m3")
        expected = mmcfd * self.MMCFD_TO_MILLION_M3_PER_YEAR
        self.assertAlmostEqual(float(anchor["value"]), expected, delta=expected * 1e-4,
                               msg="anchor post_meter_nonresidential %s vs %.2f from the six "
                                   "included end uses (%.2f MMCFD): the base's size and its "
                                   "membership have diverged" % (anchor["value"], expected, mmcfd))

    def test_fertiliser_gas_is_two_flows_and_only_the_burned_one_is_in_the_base(self):
        """Through rc66 the whole fertiliser class sat in the leak base and this test held
        the inconsistency visible, saying its removal was "a scientific decision for the
        author". The author took it at rc67: chemical feedstock is outside the base, the
        process fuel the plants burn is inside. The printed row keeps its `yes` (it is one
        of the six classes whose sum is the anchor value, and the engine withholds the
        feed from that sum); the ledger carries it as two rows that add back to the print.
        """
        root = os.path.join(ROOT, "data", "sectors", "fugitives", "activity")
        fert = next(r for r in self._rows(os.path.join(root, "post_meter_end_use_2023_24.csv"))
                    if r["end_use"] == "Fertilizer")
        self.assertEqual(fert["include_in_ipcc_post_meter"].strip().lower(), "yes")
        closure = {r["stream"]: r for r in self._rows(
            os.path.join(ROOT, "outputs", "national_gas_closure.csv"))}
        self.assertNotIn("Fertilizer", closure, "the unsplit row must not come back")
        feed, fuel = closure["Fertilizer: feedstock"], closure["Fertilizer: process fuel"]
        self.assertEqual(feed["in_post_meter_leak_base"], "no")
        self.assertEqual(feed["ledger_status"], "feedstock_excluded")
        self.assertEqual(fuel["in_post_meter_leak_base"], "yes")
        self.assertEqual(fuel["ledger_status"], "combusted_booked_on_production")
        self.assertAlmostEqual(float(feed["mmcfd"]) + float(fuel["mmcfd"]),
                               float(fert["throughput_mmcfd"]), places=2)
        self.assertAlmostEqual(float(feed["mmcfd"]) / float(fert["throughput_mmcfd"]),
                               229237.0 / (229237.0 + 45219.0), places=4,
                               msg="the split is NFDC Annex-28's metered feed and fuel gas")

    def test_the_engine_charges_the_base_the_ledger_states(self):
        """The ledger's `yes` rows and the fugitives engine's post-meter activity are the
        same volume. A membership stated in one place and applied in another is the
        defect rc67 removed; this is what keeps it removed."""
        import sys
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from pkinv.sectors.fugitives import segment_inventory
        from pkinv.sectors.fugitives.data import FugitivesData
        closure = self._rows(os.path.join(ROOT, "outputs", "national_gas_closure.csv"))
        stated = sum(float(r["annual_million_m3"]) for r in closure
                     if r["in_post_meter_leak_base"] == "yes" and r["mmcfd"])
        charged = next(r for r in segment_inventory.inventory_rows(FugitivesData())
                       if r["subitem"] == "Post-meter industrial and power"
                       and r["gas"] == "CH4")["activity_value"]
        self.assertAlmostEqual(stated, charged, delta=charged * 1e-4)
