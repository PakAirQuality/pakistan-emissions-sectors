"""The kiln fleet's three dated observations, and the band built on them.

THE CONTRADICTION IS THE FINDING, so these tests exist to stop it being resolved by accident.
Two counts of the Punjab fleet disagree in both directions - BKOAP's November 2020 roll says
10,394 kilns with 22.4 percent zig-zag, Hamdani's July 2023 detection says 9,491 with 13.7 -
and a one-way conversion programme cannot LOWER a zig-zag share. So the two are not two
measurements of one quantity; they are measurements of different quantities (an owners'
association's administrative roll against Sentinel-2 morphology) and averaging them would
manufacture a number neither source supports.

Nothing here is booked. The engine burns HDIP's national brick column, and these tests assert
that the reconstruction stays beside it rather than entering it.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBSERVATIONS = asset_path(ROOT, "data", "activity", "industry", "brick_kiln_fleet_observations.csv")
BY_YEAR = os.path.join(ROOT, "outputs", "pakemis_brick_kiln_fleet_by_year.csv")
DECISION = os.path.join(ROOT, "outputs", "pakemis_industrial_coal_decision.csv")

# the printed BKOAP scalars, which the per-district transcription must reproduce
PRINTED_TOTAL, PRINTED_CONVERTED, PRINTED_DISTRICTS = 10394, 2330, 36
# Lahore, the district this whole round is about, as each source reads it
LAHORE = {"bkoap": (277.0, 250.0), "hamdani": (182.0, 47.0)}


def _rows(path):
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheObservations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(OBSERVATIONS)

    def test_the_transcription_reproduces_the_printed_totals(self):
        """36 districts summing to the two scalars the same page prints. This is the only
        check that can catch a dropped or doubled row, and it is why the one corrected row
        below is a correction rather than a preference."""
        district = [r for r in self.rows
                    if r["observation_id"].startswith("bkoap_2020_") and r["geography_level"] == "district"]
        self.assertEqual(len(district), PRINTED_DISTRICTS)
        self.assertEqual(sum(int(r["kilns_total"]) for r in district), PRINTED_TOTAL)
        self.assertEqual(sum(int(r["kilns_zigzag"]) for r in district), PRINTED_CONVERTED)

    def test_the_one_corrected_row_records_the_value_it_did_not_use(self):
        """Bahawalnagar prints 450 and cannot be 450: 82 converted at the row's own 33.1
        percent is 247.7, and the column as printed overshoots its own total by exactly
        450 - 248. A correction that did not publish the printed value would be a silent
        edit of a source, so the printed value is carried in its own column."""
        row = next(r for r in self.rows if r["observation_id"] == "bkoap_2020_bahawalnagar")
        self.assertEqual(int(row["kilns_total"]), 248)
        self.assertTrue(row["printed_value_if_corrected"].startswith("450"),
                        "the printed-value column must carry the PRINTED value, not the used one")
        self.assertIn("10,596", row["printed_value_if_corrected"],
                      "the arithmetic that convicts the printed value belongs in the row")
        # and no other row is silently corrected
        corrected = [r["observation_id"] for r in self.rows if r["printed_value_if_corrected"]]
        self.assertEqual(corrected, ["bkoap_2020_bahawalnagar"])

    def test_every_row_cites_a_held_document_and_says_what_it_cannot_measure(self):
        for row in self.rows:
            self.assertTrue(row["source_file"], row["observation_id"])
            self.assertTrue(os.path.exists(asset_path(ROOT, row["source_file"])),
                            "%s cites %s, which is not held" % (row["observation_id"], row["source_file"]))
            self.assertTrue(row["what_it_does_not_measure"].strip(),
                            "%s claims a count without stating its blind spot" % row["observation_id"])
            self.assertTrue(row["observation_date"], row["observation_id"])

    def test_no_row_asserts_that_a_kiln_was_operating(self):
        """The register's own status is `prospective` and neither source states firing. A row
        that said `operating` would be the assumption this whole table exists to refuse."""
        for row in self.rows:
            blob = " ".join(row.values()).lower()
            self.assertNotIn("operating_status", blob)
            for claim in ("kilns_operating", "confirmed operating", "known to be firing"):
                self.assertNotIn(claim, blob, row["observation_id"])
        detection = [r for r in self.rows if r["observation_id"].startswith("hamdani_")]
        self.assertTrue(detection)
        for row in detection:
            self.assertIn("detection is not operation", row["what_it_does_not_measure"])


class TestTheTwoReadingsStayApart(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(BY_YEAR)
        cls.observations = _rows(OBSERVATIONS)

    def test_lahore_holds_both_readings_without_reconciliation(self):
        """277/250 and 182/47, carried side by side in all nine periods. No third value
        appears - no mean, no interpolation between the two dates, no 'best estimate'."""
        lahore = [r for r in self.rows if r["adm2_id"] == "punjab_lahore"]
        self.assertEqual(len(lahore), 9 * 2, "nine periods x two readings")
        seen = {}
        for row in lahore:
            seen.setdefault(row["reading"], set()).add(
                (float(row["kilns_total"]), float(row["kilns_zigzag"])))
        self.assertEqual(set(seen), set(LAHORE))
        for reading, pairs in seen.items():
            self.assertEqual(pairs, {LAHORE[reading]},
                             "%s moved between periods; a single cross-section cannot" % reading)

    def test_the_zigzag_share_falls_between_the_dates_which_is_why_neither_is_dropped(self):
        """The finding, asserted so that a later 'tidy-up' cannot quietly reverse it."""
        punjab = [r for r in self.rows if r["adm2_id"].startswith("punjab_") and r["period_id"] == "FY2023-24"]
        by_reading = {}
        for row in punjab:
            total, zz = by_reading.get(row["reading"], (0.0, 0.0))
            by_reading[row["reading"]] = (total + float(row["kilns_total"]), zz + float(row["kilns_zigzag"]))
        bkoap, hamdani = by_reading["bkoap"], by_reading["hamdani"]
        self.assertGreater(bkoap[0], hamdani[0], "the later reading counts fewer kilns")
        self.assertGreater(bkoap[1] / bkoap[0], hamdani[1] / hamdani[0],
                           "the zig-zag share falls between the two dates - the thing a one-way "
                           "conversion programme cannot do, and the reason the two readings are "
                           "carried rather than reconciled")

    def test_every_punjab_district_carries_both_readings(self):
        """BKOAP is a Punjab association, so a district outside Punjab has the detection only;
        inside Punjab, a district with one reading and not the other would be a silent choice."""
        by_district = {}
        for row in self.rows:
            by_district.setdefault(row["adm2_id"], set()).add(row["reading"])
        for adm2, readings in sorted(by_district.items()):
            if adm2.startswith("punjab_"):
                self.assertEqual(readings, {"bkoap", "hamdani"}, adm2)
            else:
                self.assertEqual(readings, {"hamdani"},
                                 "%s is outside Punjab and cannot have a BKOAP roll" % adm2)

    def test_the_fuel_model_is_a_band_with_no_central(self):
        """Operating days is the open term and the two held sources differ by 2.9x - 215
        declared against 73.9 implied. A central value would be a choice between them made by
        arithmetic rather than by evidence, so there is none."""
        self.assertTrue(self.rows)
        for row in self.rows:
            self.assertEqual(row["coal_kt_central"], "",
                             "%s/%s invented a central value" % (row["adm2_id"], row["reading"]))
            low, high = float(row["coal_kt_low"]), float(row["coal_kt_high"])
            self.assertLess(low, high)
            self.assertGreater(low, 0.0)
            self.assertTrue(row["days_low_basis"].strip() and row["days_high_basis"].strip(),
                            "both ends of the band must name the source of their firing season")
        low_basis = {r["days_low_basis"] for r in self.rows}
        high_basis = {r["days_high_basis"] for r in self.rows}
        self.assertEqual(len(low_basis), 1)
        self.assertEqual(len(high_basis), 1)
        self.assertIn("73.9", low_basis.pop())
        self.assertIn("215", high_basis.pop())

    def test_a_carried_cross_section_says_it_is_carried(self):
        """Eight of nine periods are not the year the fleet was counted, and every one of
        their rows says so in its own year_basis rather than reading as an annual series."""
        for row in self.rows:
            self.assertTrue(row["year_basis"].strip(), row["period_id"])
            if row["period_id"] not in ("FY2020-21", "FY2023-24"):
                self.assertIn("carried", row["year_basis"].lower(),
                              "%s %s reads as if it were observed in that period"
                              % (row["period_id"], row["reading"]))


class TestNothingIsBooked(unittest.TestCase):

    def test_the_decision_record_adopts_nothing(self):
        """The bar the coal work already set: a reconstruction enters the inventory only when
        it beats the booked series on a declared test, and it has not."""
        rows = _rows(DECISION)
        self.assertTrue(rows)
        self.assertIn("decision", rows[0], "the decision column was renamed; this test is now blind")
        verdicts = {r["decision"].strip() for r in rows if r["decision"].strip()}
        self.assertTrue(verdicts, "no row carries a decision at all")
        # a closed vocabulary rather than a substring search: a new verdict word is a change of
        # policy and must be read by a person, not absorbed by a test looking for "adopt"
        for verdict in sorted(verdicts):
            self.assertTrue(verdict.startswith("OFFICIAL STAYS BOOKED"),
                            "the decision record says %r, which is not the standing verdict; if "
                            "the reconstruction has earned its way in, that is a release event "
                            "and this test is where it gets declared" % verdict)


if __name__ == "__main__":
    unittest.main()
