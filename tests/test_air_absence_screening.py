"""The absence-screening ledger: scenario ends beside the panel, never inside it.

Three properties, each the reason a defect class cannot ship: the pair orders
(controlled <= uncontrolled wherever both ends are priced), the ledger reproduces
the screening files' own sums exactly (no third derivation of the same numbers),
and the covered panel's headline is UNCHANGED by the ledger's existence (the
laundering guard - a covered total plus a scenario end is neither an estimate nor
a bound, and no code path may compute it). Since rc58 industry is a covered estimate:
its ledger rows exist only for the cells the coverage matrix still types NE, and they
carry no number."""
import collections
import csv
import os
import unittest

from pkinv.paths import OUTPUTS

LEDGER = os.path.join(OUTPUTS, "pakemis_air_absence_screening_by_year.csv")
POWER = os.path.join(OUTPUTS, "power_air_screening_fy2015_16_fy2023_24.csv")
COVERAGE = os.path.join(OUTPUTS, "pakemis_air_coverage_matrix.csv")
PANEL = os.path.join(OUTPUTS, "pakemis_air_annual_fy2015_16_fy2023_24.csv")


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


class TestTheScenarioPair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = _rows(LEDGER)

    def test_controlled_never_exceeds_uncontrolled(self):
        pairs = 0
        for r in self.ledger:
            if r["scenario_controlled_kt"] and r["scenario_uncontrolled_kt"]:
                self.assertLessEqual(
                    float(r["scenario_controlled_kt"]),
                    float(r["scenario_uncontrolled_kt"]) + 1e-9,
                    "%s %s %s: the pair is inverted" %
                    (r["period_id"], r["sector_id"], r["pollutant"]))
                pairs += 1
        self.assertGreaterEqual(pairs, 36, "the pair property must actually bite")

    def test_industry_ledger_rows_exist_only_for_ne_cells_and_carry_no_number(self):
        """rc58: a ledger row for an industry cell that is E would invite the double count
        the rule forbids; the rows that remain are typed absences with a gap and no kt."""
        ne = {(c["period_id"], c["pollutant"]) for c in _rows(COVERAGE)
              if c["sector_id"] == "industry" and c["state"] != "E"}
        rows = [r for r in self.ledger if r["sector_id"] == "industry"]
        self.assertEqual({(r["period_id"], r["pollutant"]) for r in rows}, ne)
        self.assertTrue(rows, "industry keeps at least its NH3 absences")
        for r in rows:
            self.assertEqual(r["scenario_controlled_kt"], "")
            self.assertEqual(r["scenario_uncontrolled_kt"], "")
            self.assertTrue(r["gap_id"])
            self.assertTrue(r["controlled_absence_reason"])

    def test_every_ledger_row_says_why_the_absence_is_an_absence(self):
        """The field was blank exactly where it mattered most, and only industry was checked.

        `controlled_absence_reason` used to mean "explain a MISSING scenario end", so a row
        that successfully priced a PAIR got an empty string - all nine periods of power CO,
        NOx, PM2.5 and SO2, thirty-six rows, and precisely the four pollutants whose absence
        IS the control-device question. The engine serves this field in query_air's
        completeness block, so a reader asking for power SO2 got two scenario numbers and a
        gap id with nothing saying in words what the gap was. The old test asserted the
        reason only for industry's numberless rows, which is why the blank survived: the
        assertion was on the tier that could not exhibit the bug.
        """
        blank = sorted((r["period_id"], r["sector_id"], r["pollutant"])
                       for r in self.ledger
                       if not (r.get("controlled_absence_reason") or "").strip())
        self.assertFalse(
            blank,
            "%d ledger rows carry no reason at all. Every row in this file exists because "
            "something is absent; a row that cannot say what is the one kind of row this "
            "ledger must not contain.\n  %s"
            % (len(blank), "\n  ".join(map(str, blank[:12]))))

    def test_a_priced_pair_names_the_acquisition_that_would_replace_it(self):
        """A bracket is only honest if it says what would collapse it."""
        pairs = [r for r in self.ledger
                 if r["scenario_controlled_kt"] and r["scenario_uncontrolled_kt"]]
        self.assertTrue(pairs, "the ledger should still carry power's priced pairs")
        for r in pairs:
            reason = r["controlled_absence_reason"]
            self.assertIn("NEITHER IS THE ESTIMATE", reason,
                          "a priced pair must say that neither end is the estimate: %s/%s"
                          % (r["period_id"], r["pollutant"]))
            self.assertTrue(r["gap_id"],
                            "a priced pair with no gap_id names no acquisition: %s/%s"
                            % (r["period_id"], r["pollutant"]))

    def test_the_reason_is_the_gap_registers_own_words(self):
        """Built from data_gaps.csv, not retyped, so it cannot drift from the register.

        Resolved through the asset shim rather than a literal path: the register's published
        identity is data/data_gaps.csv and its file has moved once already.
        """
        from pkinv.assets import asset_path as _ap
        from pkinv.paths import DATA as _DATA
        path = _ap(_DATA, "data_gaps.csv")
        if not os.path.exists(path):
            self.skipTest("data_gaps.csv is not resolvable in this checkout")
        gaps = _rows(path)
        row = next((g for g in gaps if g.get("gap_id") == "air-power-controlled"), None)
        self.assertIsNotNone(row, "the register lost the air-power-controlled gap")
        pair = next(r for r in self.ledger
                    if r["scenario_controlled_kt"] and r["scenario_uncontrolled_kt"])
        for field in ("category", "unblocks", "holder"):
            self.assertIn(row[field], pair["controlled_absence_reason"],
                          "the ledger's reason no longer quotes the register's %s, so the "
                          "two can drift" % field)

    def test_the_ledger_reproduces_the_screening_sums_exactly(self):
        """One derivation: the ledger's cells are the screening files' own sums."""
        power = collections.defaultdict(float)
        for r in _rows(POWER):
            if r["emissions_kt"]:
                power[(r["period_id"], r["scenario"], r["pollutant"])] += \
                    float(r["emissions_kt"])
        checked = 0
        for r in self.ledger:
            for col, src_key in (("scenario_uncontrolled_kt", "uncontrolled"),
                                 ("scenario_controlled_kt", "controlled_case")):
                if not r[col]:
                    continue
                self.assertEqual(r["sector_id"], "power", "only power carries scenario ends")
                want = power[(r["period_id"], src_key, r["pollutant"])]
                self.assertAlmostEqual(float(r[col]), want, delta=1e-4 + 1e-6 * want,
                                       msg="%s %s %s %s" % (r["period_id"],
                                                            r["sector_id"],
                                                            r["pollutant"], col))
                checked += 1
        self.assertGreater(checked, 50)

    def test_a_screened_number_never_stands_beside_an_estimate_of_the_same_thing(self):
        """THE LAUNDERING GUARD, restated at rc60 to say what it was always for.

        It used to read `no panel row names power`. That was the right test while power was
        wholly screened, and it is the wrong one now: the oil and diesel fleet's SO2 is
        estimated per station, so power is legitimately in the panel - for that one pollutant.

        What must never happen has not changed. A scenario number and an estimate of THE SAME
        SOURCES cannot stand side by side, because a reader adding them would count that mass
        twice, and a reader choosing between them has no way to know which is which. The
        screening's oil and diesel SO2 is therefore narrowed to the fuel the admission did not
        take, exactly and not approximately - the screening is linear in fuel mass, so scaling
        by the unadmitted fraction IS the remainder. Every such row says so in its basis.

        So the guard is now: a sector may appear in both, and where it does, the screened rows
        of the admitted pollutant must declare themselves a remainder. Absence was only ever a
        cheap way of getting disjointness; this asks for disjointness itself.
        """
        sectors = {r["sector_id"] for r in _rows(PANEL)}
        self.assertIn("industry", sectors)
        self.assertIn("power", sectors, "power's admitted SO2 is missing from the panel")

        panel_pollutants = {r["pollutant"] for r in _rows(PANEL) if r["sector_id"] == "power"}
        self.assertEqual(panel_pollutants, {"SO2"},
                         "only SO2 is admitted for power; anything else in the panel is "
                         "standing beside its own screening with nothing to separate them")

        power_rows = list(_rows(POWER))
        self.assertFalse([r for r in power_rows if r["category"].startswith("Captive")],
                         "captive is priced once, in the industry atoms")

        # and the overlap itself: every screened oil or diesel SO2 row in a period where that
        # fuel was admitted must say it is only the remainder
        admitted = {(r["period_id"], {"RFO": "Furnace Oil", "HSD": "Diesel Oil"}[r["fuel"]])
                    for r in _admission() if r["disposition"] == "provisional_estimate"}
        overlapping = [r for r in power_rows if r["pollutant"] == "SO2"
                       and (r["period_id"], r["fuel"]) in admitted]
        self.assertGreaterEqual(len(overlapping), 20)
        for r in overlapping:
            self.assertIn("REMAINDER ONLY", r["basis"],
                          "%s %s screens a fuel the panel also estimates, and does not say it "
                          "is the remainder" % (r["period_id"], r["fuel"]))


def _admission():
    from pkinv.core.io import read_rows
    return read_rows(os.path.join(os.path.dirname(__file__), "..", "data", "activity",
                                  "power", "power_so2_admission.csv"))


class TestTheEnvelopeBlock(unittest.TestCase):
    """The engine serves the ledger BESIDE a fiscal-period answer - and the answer's
    values are what they were before the block existed (the panel goldens' frozen
    receipts, which hash the VALUES alone, are the standing proof; this test pins
    the block's own shape)."""

    @classmethod
    def setUpClass(cls):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("duckdb not installed")
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(OUTPUTS), "tests"))
        from semantic._golden import open_engine
        cls.engine = open_engine()

    def test_a_panel_answer_carries_the_absence_block(self):
        from pakemis_query.models import QueryAir
        env = self.engine.query_air(QueryAir(pollutants=("NOx",),
                                             periods=("FY2022-23",)))
        block = env["completeness"]
        # rc58: NOx is a covered industry species, so only power's pair rides the block;
        # an NH3 answer carries industry's typed absence beside power's unscreened row
        self.assertEqual({r["sector_id"] for r in block}, {"power"})
        nh3 = self.engine.query_air(QueryAir(pollutants=("NH3",), periods=("FY2022-23",)))
        ind = [r for r in nh3["completeness"] if r["sector_id"] == "industry"]
        self.assertEqual(len(ind), 1)
        self.assertEqual(ind[0]["gap_id"], "air-industry-nh3")
        self.assertEqual(ind[0]["scenario_uncontrolled_kt"], "")
        power = next(r for r in block if r["sector_id"] == "power")
        self.assertTrue(float(power["scenario_controlled_kt"])
                        <= float(power["scenario_uncontrolled_kt"]))
        self.assertEqual(power["gap_id"], "air-power-controlled")
        # and the headline is the covered sum alone - nowhere near covered+screening
        covered = float(env["values"][0]["exact"])
        # rc58: the covered NOx headline gained industry's 137.3 kt (676.75 -> 814.03);
        # rc59: ippu's 5.2 and fugitives' 0.6 kt (814.03 -> 819.81)
        # rc67: household dung follows the survey in every year, so residential NOx in
        # FY2022-23 fell from 328.42 to 151.45 kt (819.81 -> 642.84). 819.81 is still
        # served, under the ledger series L_HERD1624.
        self.assertLess(abs(covered - 642.84) / 642.84, 0.02,
                        "the headline must remain the covered panel's own sum")
        ledger = self.engine.query_air(QueryAir(pollutants=("NOx",),
                                                periods=("FY2022-23",),
                                                configuration_id="L_HERD1624"))
        self.assertLess(abs(float(ledger["values"][0]["exact"]) - 819.81) / 819.81, 0.02,
                        "the ledger series must still carry the pre-rc67 headline")


if __name__ == "__main__":
    unittest.main()
