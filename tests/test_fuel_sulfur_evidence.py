"""Fuel sulfur: what was measured, what was specified, and which of the two the engine books.

SO2 is linear in fuel sulfur, so the number multiplying every sulfur-balance class is as
load-bearing as the activity it multiplies. The register `fuel_sulfur_evidence.csv` declares a
five-word basis vocabulary whose first entry is `measured_avg` - "consignment analyses of consumed
fuel" - and for the whole life of the air panel no row used it. At rc63 one does: brick-kiln coal
is the mean of three as-fired analyses, and the basis upgrade rather than the 3.2 percent level
change is what earned it. These tests hold the line at an observation must cite a held document and say what it cannot measure, a band must admit
the evidence that exists, and a disagreement between two booked rows must stay visible rather than
being averaged away.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest
from _support import readable  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

OBSERVATIONS = asset_path(ROOT, "data", "activity", "industry", "fuel_sulfur_observations.csv")
GRADE_MIX = asset_path(ROOT, "data", "activity", "industry", "furnace_oil_grade_mix.csv")
REGISTER = asset_path(ROOT, "data", "activity", "industry", "fuel_sulfur_evidence.csv")
CLASSES = asset_path(ROOT, "data", "air_source_classes.csv")
DECISION = os.path.join(ROOT, "outputs", "pakemis_fuel_sulfur_decision.csv")

# the four things an observation can be, and the distinction the whole table turns on
MEASURES = {"as_fired", "as_delivered", "as_sold", "specification", "resource"}
# the two furnace-oil grades' ceilings, which is all that is held
S_HSFO, S_LSFO = 3.5, 1.0


def _rows(path):
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheObservations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(OBSERVATIONS)

    def test_every_observation_cites_a_held_document(self):
        self.assertTrue(self.rows)
        for row in self.rows:
            self.assertTrue(row["source_path"], row["observation_id"])
            self.assertTrue(os.path.exists(asset_path(ROOT, row["source_path"]))
                            or not readable(row["source_path"]),
                            "%s cites %s, which is not held" % (row["observation_id"], row["source_path"]))

    def test_every_observation_says_what_it_cannot_measure(self):
        """The column that stops a specification being read as a measurement."""
        for row in self.rows:
            self.assertIn(row["what_it_measures"], MEASURES, row["observation_id"])
            self.assertTrue(row["what_it_does_not_measure"].strip(),
                            "%s states a sulfur figure without its blind spot" % row["observation_id"])
            self.assertTrue(row["observed_date"].strip(), row["observation_id"])

    def test_an_as_fired_analysis_and_a_resource_range_are_not_interchangeable(self):
        """The register's booked brick central is a `resource` figure and the one direct
        observation is `as_fired`. They must stay typed apart, because the whole diagnosis is
        that one has been standing in for the other."""
        kinds = {r["what_it_measures"] for r in self.rows}
        self.assertIn("as_fired", kinds, "no as-fired observation is held; item 3's premise is gone")
        fired = [r for r in self.rows if r["what_it_measures"] == "as_fired"]
        for row in fired:
            self.assertTrue(row["n_samples"], "%s must state its sample size" % row["observation_id"])

    def test_the_transcription_records_that_two_search_readings_were_wrong(self):
        """A held document settled a number that two search-engine reads got differently (1.0 wt %
        - which is the paper's own PSI LIMIT - and 0.24-0.89 wt %). The row carries that, so the
        next reader does not re-import either wrong value from a search."""
        row = next(r for r in self.rows if r["observation_id"] == "yasin_2012_hsd_multan_as_sold")
        for needle in ("0.24", "1.0 % by weight", "PSI LIMIT"):
            self.assertIn(needle, row["note"],
                          "the Yasin row must record the readings it corrects, including %r" % needle)
        self.assertAlmostEqual(float(row["s_pct_lo"]), 0.22, places=6)
        self.assertAlmostEqual(float(row["s_pct_hi"]), 0.46, places=6)


class TestTheGradeMix(unittest.TestCase):
    """The furnace-oil import split the register CITES and then discards."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(GRADE_MIX)

    def test_the_share_and_the_weighted_sulfur_are_what_the_tonnage_says(self):
        panel = [r for r in self.rows if r["period_id"]]
        self.assertTrue(panel)
        for row in panel:
            hsfo, lsfo = float(row["hsfo_tonnes"]), float(row["lsfo_tonnes"])
            share = hsfo / (hsfo + lsfo)
            self.assertAlmostEqual(float(row["hsfo_share"]), share, places=5, msg=row["period_id"])
            self.assertAlmostEqual(float(row["grade_weighted_s_pct"]),
                                   share * S_HSFO + (1.0 - share) * S_LSFO, places=3,
                                   msg=row["period_id"])

    def test_the_weighted_value_is_bounded_by_the_two_grades(self):
        """It is a mix of two ceilings, so it cannot leave them - and it is therefore an upper
        envelope rather than an assay, which is why nothing books it."""
        for row in (r for r in self.rows if r["grade_weighted_s_pct"]):
            self.assertGreaterEqual(float(row["grade_weighted_s_pct"]), S_LSFO)
            self.assertLessEqual(float(row["grade_weighted_s_pct"]), S_HSFO)

    def test_a_year_with_no_printed_low_sulphur_figure_gets_no_share(self):
        """An absence is typed, never a zero: FY2014-15 prints no LSFO quantity at all, which is
        not the same as the printed 0 of FY2018-19."""
        pre = [r for r in self.rows if not r["period_id"]]
        self.assertTrue(pre, "the pre-panel year should be carried so the trend into it is visible")
        for row in pre:
            self.assertEqual(row["lsfo_tonnes"], "")
            self.assertEqual(row["hsfo_share"], "")
            self.assertEqual(row["grade_weighted_s_pct"], "")

    def test_the_series_stops_where_the_source_stops(self):
        """Four panel years, not nine. The table ends at FY2018-19 and furnace-oil imports collapse
        after it, so an extrapolated fifth year would be an invention."""
        periods = {r["period_id"] for r in self.rows if r["period_id"]}
        self.assertEqual(periods, {"FY2015-16", "FY2016-17", "FY2017-18", "FY2018-19"})


class TestTheRegisterBooksWhatTheEvidenceSupports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.register = {r["evidence_id"]: r for r in _rows(REGISTER)}
        cls.classes = {r["source_class_id"]: r for r in _rows(CLASSES)}
        cls.observations = {r["observation_id"]: r for r in _rows(OBSERVATIONS)}

    def test_the_brick_band_admits_every_direct_observation(self):
        """THE REPAIR THIS ROUND MADE, pinned. A band that excludes a direct observation of its own
        quantity is wrong whatever its central is - and the band must keep admitting them as more
        arrive, which is how the fourth analysis would have been caught had it come first."""
        coal = self.register["coal_punjab_fields"]
        analyses = sorted(float(o["s_pct_central"]) for o in self.observations.values()
                          if o["fuel"] == "Brick-kiln coal"
                          and o["what_it_measures"] == "as_fired" and o["s_pct_central"])
        self.assertGreaterEqual(len(analyses), 3, "the CDPR/IGC analyses are missing")
        for value in analyses:
            self.assertGreaterEqual(value, float(coal["s_pct_lo"]), "band excludes %.2f" % value)
            self.assertLessEqual(value, float(coal["s_pct_hi"]), "band excludes %.2f" % value)
        # and the booked central now sits INSIDE what has been measured, which is the round's
        # reversal: on the first analysis alone it looked 89 percent too high
        self.assertGreaterEqual(float(coal["s_pct_central"]), analyses[0])
        self.assertLessEqual(float(coal["s_pct_central"]), analyses[-1])
        fired = analyses[0]
        self.assertLessEqual(float(coal["s_pct_lo"]), fired,
                             "the booked brick-coal band excludes the as-fired observation at "
                             "%.2f %% - the defect item 3 repaired" % fired)
        # THE RELEASE EVENT THIS GATE EXISTED TO CATCH, now declared. The central is the mean of
        # the as-fired analyses and the basis is the one the register has declared since rc58 and
        # never used. Both are asserted: a central that moved without the basis moving would be a
        # re-centring on the old kind of evidence, which is what the gate was written against.
        self.assertEqual(coal["basis"], "measured_avg",
                         "the brick row must state that its central comes from analyses of fuel "
                         "that was burned, not from resource ranges")
        self.assertAlmostEqual(float(coal["s_pct_central"]), sum(analyses)/len(analyses), places=3,
                               msg="the central must be the mean of the as-fired analyses held; if "
                                   "a different estimator is wanted that is a release event and "
                                   "belongs in the decision record")
        # and the uncertainty was NOT narrowed to flatter the new basis
        self.assertGreaterEqual(float(coal["uncert_pct"]), 60.0,
                                "n=3 spanning a factor of 2.5 does not license a precision claim, "
                                "and the unmeasured retention floors the combined term anyway")

    def test_light_diesel_oil_no_longer_borrows_road_diesel_sulfur(self):
        """It was a declared proxy resting on 'no Pakistani LDO specification is held'. One is."""
        ldo = self.classes["ind_ldo_boiler"]
        self.assertEqual(ldo["sulfur_evidence_id"], "ldo_psi_grade")
        for road in ("hsd_pre_euro2", "hsd_euro2_onward"):
            self.assertNotIn("ind_ldo_boiler", self.register[road]["applies_to"].split(";"),
                             "%s still claims LDO" % road)
        row = self.register["ldo_psi_grade"]
        self.assertAlmostEqual(float(row["s_pct_hi"]), 1.8, places=6,
                               msg="hi must be the PSI grade ceiling that justified the split")
        self.assertTrue(float(row["s_pct_lo"]) <= 0.05,
                        "lo must still reach the road-diesel value, which is the hypothesis this "
                        "row replaces - the band has to contain it")

    def test_kerosene_still_says_it_is_a_proxy(self):
        """Kerosene keeps the road-diesel row because no kerosene specification was located. That
        is a weaker claim than LDO's was and the register must not stop admitting it."""
        kero = self.classes["ind_kero_boiler"]
        self.assertEqual(kero["sulfur_evidence_id"], "hsd_pre_euro2;hsd_euro2_onward")
        note = self.register["hsd_euro2_onward"]["note"]
        self.assertIn("ind_kero_boiler", note,
                      "the road-diesel row must name the class it still stands in for")
        self.assertIn("no Pakistani kerosene specification", note,
                      "and must say why it is allowed to")

    def test_one_fuel_POOL_cannot_have_two_centrals(self):
        """THE INVARIANT, CORRECTED. The first version of this keyed on the `fuel` STRING and was
        too restrictive - a reviewer caught it.

        "Residual Fuel Oil" spans HSFO, LSFO and the very-low-sulphur product NRL introduced in
        September 2023; "Coal" spans every coalfield in the country. Keying on the name asserted
        that all fuel sharing a label must share a sulfur content, which is false and would have
        BLOCKED exactly the documented grade split the evidence warrants. The real principle is
        narrower: two modules drawing on the SAME physical supply pool in the same years must not
        independently assign it contradictory sulfur. Distinct documented pools may differ.

        So the key is `fuel_pool`, and a row claiming a distinct pool has to name it. That is what
        makes a future VLSFO row or a coalfield split expressible rather than forbidden."""
        live = [r for r in self.register.values() if r["applies_to"].strip()]
        self.assertTrue(live)
        by_pool = {}
        for row in live:
            self.assertTrue(row["fuel_pool"].strip(), "%s names no pool" % row["evidence_id"])
            by_pool.setdefault(row["fuel_pool"], []).append(row)
        for pool, rows in sorted(by_pool.items()):
            for a in rows:
                for b in rows:
                    if a is b:
                        continue
                    # the same pool in DIFFERENT years may legitimately differ - a regime step is
                    # a property of the pool over time, not a contradiction within it
                    overlap = (int(a["valid_from_fy_end"]) <= int(b["valid_to_fy_end"])
                               and int(b["valid_from_fy_end"]) <= int(a["valid_to_fy_end"]))
                    if not overlap:
                        continue
                    self.assertEqual(
                        a["s_pct_central"], b["s_pct_central"],
                        "%s and %s both price the pool %r in overlapping years at %s and %s. One "
                        "POOL has one sulfur; equipment changes the RETENTION, which is per class, "
                        "and a genuinely different product needs its own pool and the document "
                        "that establishes it."
                        % (a["evidence_id"], b["evidence_id"], pool,
                           a["s_pct_central"], b["s_pct_central"]))

    def test_a_transferred_row_says_where_it_was_carried_to(self):
        """`basis` says what KIND of evidence a number is. It does not say whether the number is
        being used on the population that was sampled, and conflating the two is how three batch
        analyses from three kilns become a national nine-year mean labelled `measured_avg`.

        The register now separates them, and the loader refuses a transferred row that says
        nothing about the transfer. This pins the one that matters most."""
        coal = self.register["coal_punjab_fields"]
        self.assertEqual(coal["basis"], "measured_avg")
        self.assertEqual(coal["application"], "transferred",
                         "three batches carried to a national nine-year mean is a transfer, and "
                         "labelling it own_population would be the misreading this column exists "
                         "to prevent")
        for needle in ("n=3", "ANALYTICAL BASIS", "batches"):
            self.assertIn(needle, coal["measured_scope"] + coal["transfer_basis"],
                          "the scope must state %r" % needle)
        for row in self.register.values():
            if row["application"] == "transferred":
                self.assertTrue(row["transfer_basis"].strip(), row["evidence_id"])
            self.assertTrue(row["measured_scope"].strip(), row["evidence_id"])

    def test_the_retired_power_row_is_kept_and_cannot_resolve(self):
        """A superseded value must be unreachable, not absent: the reasoning that produced it is
        worth reading, and a row that could still resolve would silently price a class at a
        central the evidence rejected."""
        retired = self.register["power_rfo_spec_range"]
        self.assertEqual(retired["applies_to"].strip(), "", "the retired row still claims classes")
        self.assertGreater(int(retired["valid_from_fy_end"]), int(retired["valid_to_fy_end"]),
                           "the retired row's validity window must be empty so it resolves for no year")
        self.assertIn("RETIRED", retired["note"])
        self.assertIn("Original note, preserved:", retired["note"],
                      "the superseded reasoning must survive the retirement")
        for cls_id in ("power_rfo_boiler", "power_rfo_engine", "power_rfo_turbine"):
            self.assertEqual(self.classes[cls_id]["sulfur_evidence_id"], "fo_hsfo_grade_mix")

    def test_the_two_furnace_oil_rows_no_longer_disagree(self):
        """ONE FUEL, TWO SECTORS, TWO CENTRALS - 2.27x apart. Resolving it means moving the power
        row, which item 3's scope excludes, so the disagreement is carried DECLARED. This test
        fails if someone averages them, and it fails if the declaration is quietly dropped: either
        would turn a known finding back into a coincidence."""
        note = self.register["fo_hsfo_grade_mix"]["note"]
        self.assertIn("power_rfo_spec_range", note,
                      "the row that absorbed the disagreement must still name what it absorbed")
        self.assertIn("RESOLVED AT rc63", note)
        # the predecessor of this test asserted the ratio was GREATER than 2.0 and said that if
        # the two ever converged it would be a release event needing evidence. It was, and this
        # is it: the held import grade split, 85.3-100 percent high-sulphur.
        self.assertIn("85.3-100", note, "the evidence that chose between the two must be named")

    def test_every_central_sits_inside_its_own_band(self):
        from pkinv.core import sulfur
        register = sulfur.load()          # load() raises on an out-of-band central and on a bad basis
        self.assertTrue(register)
        for row in register.values():
            lo, central, hi = (float(row[k]) for k in ("s_pct_lo", "s_pct_central", "s_pct_hi"))
            self.assertLessEqual(lo, central, row["evidence_id"])
            self.assertLessEqual(central, hi, row["evidence_id"])


class TestNothingWasAdoptedQuietly(unittest.TestCase):

    # The verdicts this release adopts, and nothing else may. This replaces a blanket
    # "everything stays booked" assertion: that guard did its job by failing when the brick
    # evidence finally earned its way in, and the honest successor names what was adopted rather
    # than either relaxing the rule or pretending nothing changed.
    ADOPTED = {
        "Brick-kiln coal sulfur": "ADOPTED",
        "Industrial furnace oil sulfur": "RESOLVED",
    }

    def test_the_sulfur_verdicts_adopt_exactly_what_was_declared(self):
        rows = [r for r in _rows(DECISION) if "sulfur" in r["stream"].lower()]
        self.assertTrue(rows, "the sulfur evidence is not scored in the decision record")
        decisions = [r for r in rows if r["test"] == "DECISION"]
        self.assertGreaterEqual(len(decisions), 3,
                                "each sulfur stream needs its own published verdict")
        for row in decisions:
            self.assertTrue(row["why"].strip(), row["stream"])
            expected = self.ADOPTED.get(row["stream"])
            if expected is None:
                self.assertTrue(row["decision"].startswith("OFFICIAL STAYS BOOKED"),
                                "%s reads %r and is not in the declared adoption set - if it has "
                                "earned its way in, declare it here" % (row["stream"], row["decision"]))
            else:
                self.assertTrue(row["decision"].startswith(expected),
                                "%s was declared %s and reads %r" % (row["stream"], expected, row["decision"]))

    def test_the_cross_sector_furnace_oil_violation_is_recorded_as_a_violation(self):
        """Not as a candidate's failure. The constraint is broken by the PAIR of booked rows."""
        rows = [r for r in _rows(DECISION)
                if r["stream"] == "Industrial furnace oil sulfur" and r["kind"] == "constraint"]
        self.assertTrue(rows)
        self.assertTrue(any(r["result"].startswith("VIOLATED") and r["subject"] == "the OFFICIAL series"
                            for r in rows),
                        "the furnace-oil disagreement must be scored against the OFFICIAL series")

    def test_retention_is_not_closed_and_says_why_for_each_campaign(self):
        """Two held campaigns bear on retention and NEITHER closes it, for different reasons that
        must stay distinguishable. One reports concentrations without the O2 or flow needed to
        normalise them, so a technology difference may be dilution - that is `untested`. The other
        reports factors that exceed what its own fuel can supply, which is a CANDIDATE breaking a
        constraint, not an absence. Collapsing the two into one word would lose the finding."""
        rows = [r for r in _rows(DECISION) if r["stream"] == "Brick-kiln sulfur retention"]
        tests = [r for r in rows if r["test"] != "DECISION"]
        self.assertTrue(tests)
        kinds = {r["kind"] for r in tests}
        self.assertEqual(kinds, {"constraint", "untested"},
                         "retention should be scored both ways; got %s" % sorted(kinds))
        untested = [r for r in tests if r["kind"] == "untested"]
        self.assertTrue(any("dilution" in r["finding"] for r in untested),
                        "the confound that makes the concentration campaign inconclusive must be named")
        broken = [r for r in tests if r["kind"] == "constraint"]
        self.assertTrue(all(r["subject"] == "the CANDIDATE" for r in broken),
                        "a published factor that breaks conservation is the CANDIDATE failing, not "
                        "the official series")
        self.assertTrue(any("2.51" in r["finding"] and "4.55" in r["finding"] for r in broken),
                        "the conservation arithmetic that convicts the factor belongs in the record")

    def test_the_brick_verdict_records_every_withdrawn_reading(self):
        """One test, scored FOUR ways in a single round, and all four on the page.

        DISAGREES   - one as-fired analysis held; the booked value looked 89 percent too high.
                      Too little evidence, read as a finding.
        CORROBORATED- four values including a blend component, mean 4.17, straddling the booked
                      value. The wrong evidence counted the right way; the miscount moved the mean
                      ACROSS the booked central and so across the sign of the conclusion.
        STRADDLES   - the measured mixture weighed equally against a proportioned 3.70, which the
                      source explicitly forbids reconstructing. Over-correction after two errors
                      of over-confidence.
        ADOPTED     - three as-fired analyses, mean 4.643, on the basis upgrade rather than the
                      level.

        A record showing only the survivor would teach nobody why the other three were wrong, and
        the three failure modes are different enough to be worth keeping apart."""
        rows = [r for r in _rows(DECISION) if r["stream"] == "Brick-kiln coal sulfur"]
        validations = [r for r in rows if r["kind"] == "validation"]
        adopted = [r for r in validations if "ADOPTED" in r["result"]]
        self.assertTrue(adopted, "the as-fired test should now favour the candidate")
        finding = adopted[0]["finding"]
        for withdrawn in ("DISAGREES", "CORROBORATED", "STRADDLES"):
            self.assertIn(withdrawn, finding,
                          "the withdrawn reading %r must stay on the page" % withdrawn)
        self.assertIn("component", finding,
                      "the reason the second reading was wrong - a blend component counted as a "
                      "fired fuel - is the transferable part")
        self.assertIn("proportional sum", finding,
                      "the reason the third was wrong - the source forbids that reconstruction - "
                      "is what stops it being tried again")

    def test_a_blend_component_is_not_a_fired_fuel(self):
        """The distinction that flipped the round's conclusion. The CDPR fixed-chimney kiln burns a
        two-to-one mixture, so its pure Hyderabad sample describes an input, not a charge. Typed
        as_fired it drags the mean of the held analyses from 4.64 to 4.17 - across the booked 4.5,
        and so across the sign of the finding."""
        obs = {o["observation_id"]: o for o in _rows(OBSERVATIONS)}
        row = obs["cdpr_igc_hyderabad_as_delivered"]
        self.assertEqual(row["what_it_measures"], "as_delivered")
        self.assertIn("MIXTURE", row["what_it_does_not_measure"],
                      "the row must say why it is not a fired fuel")
        fired = [float(o["s_pct_central"]) for o in obs.values()
                 if o["fuel"] == "Brick-kiln coal" and o["what_it_measures"] == "as_fired"
                 and o["s_pct_central"]]
        self.assertNotIn(2.75, fired, "the blend component leaked back into the fired set")
        # the booked central IS this mean since rc63, so compare against what it supersedes:
        # 4.5, the retired resource-range value. If the fired analyses ever average below it the
        # adoption argument has changed and the decision record must be re-scored.
        self.assertGreater(sum(fired)/len(fired), 4.5,
                           "with the component excluded the fired analyses average ABOVE the "
                           "retired resource-range central of 4.5; if that stops being true the "
                           "finding that justified adoption has changed")


if __name__ == "__main__":
    unittest.main()
