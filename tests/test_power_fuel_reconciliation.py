"""The plant/fuel/year reconciliation closes on generation, and says what it does not know.

The review asked for a reconciliation over the panel with exact source-table locations. The
risk in such a file is not a wrong number but a quiet one: a year whose coal generation no row
accounts for, or a reconstructed mass printed as though it were observed. Both are asserted.

WHY THIS FILE WAS REWRITTEN. The first version was written against a DESIGN, not against the
module: it keyed on `row_kind`, `evidence_grade`, `fiscal_start_year`, `mass_lo_kt` and
`source_table`, none of which the producer ever wrote. `setUpClass` raised `KeyError` on the
first line, so unittest reported the class as one error and ran NONE of the seven tests - the
product shipped in a release with no test exercising it at all. A test that cannot read its
own subject is worse than no test, because the suite counts it. The names below are taken from
`FIELDS` in src/pkinv/sectors/power/fuel_reconciliation.py, and `test_the_schema_is_the_one_the_producer_writes`
now fails loudly if they drift again instead of erroring in setup.
"""
import collections
import csv
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(ROOT, "outputs", "pakemis_power_fuel_reconciliation.csv")
AUDIT = os.path.join(ROOT, "outputs", "pakemis_power_reference_audit.csv")
GEN = os.path.join(ROOT, "data", "sectors", "power", "activity", "generation_by_fuel.csv")

# A typed absence is never a zero (repo numbers discipline), so the mass reader must not
# coerce one. These are the forms the activity tables use.
ABSENT = ("", "NE", "NO", "IE", "C", "NA")

STATION = "enumerated station"
BOOKED = "booked total"
RECON_LANE = "reconstructed lane"


def _rows(path):
    with open(path, encoding="utf-8") as handle:
        body = "".join(l for l in handle if not l.startswith("#"))
    return list(csv.DictReader(io.StringIO(body)))


def _mass(row):
    """The row's mass in kt, or None where the row declares an absence."""
    value = (row.get("mass_kt") or "").strip()
    return None if value in ABSENT else float(value)


def _start_year(period_id):
    """"FY2023-24" -> 2023. The fiscal START year, which is the key both tables use."""
    return int(period_id[2:6])


class TestTheReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the reconciliation has not been built here")
        cls.rows = _rows(OUT)
        cls.station = [r for r in cls.rows if r["plant_coverage_class"] == STATION]
        cls.booked = [r for r in cls.rows if r["plant_coverage_class"] == BOOKED]
        cls.lane = [r for r in cls.rows
                    if r["plant_coverage_class"] == RECON_LANE]

    def test_the_schema_is_the_one_the_producer_writes(self):
        """THE GUARD THE LAST VERSION LACKED. Compared against the producer's own FIELDS, so a
        renamed column fails here with a readable diff rather than erroring in setUpClass and
        silently retiring every other test in this file."""
        from pkinv.sectors.power.fuel_reconciliation import FIELDS
        self.assertEqual(list(self.rows[0].keys()), list(FIELDS),
                         "the shipped header and the producer's FIELDS have diverged")
        for name in ("plant_coverage_class", "quantity_class", "ncv_basis",
                     "reconstruction_rule", "mass_source_edition", "mass_source_table"):
            self.assertIn(name, FIELDS, "%s is the column this file keys on" % name)

    def test_it_found_rows(self):
        """A closure test over an empty read passes; this is what stops that."""
        self.assertGreater(len(self.station), 20)
        self.assertEqual(len(self.booked), 9, "one booked-account row per panel year")
        self.assertEqual(sorted(r["period_id"] for r in self.booked),
                         sorted({r["period_id"] for r in self.station}),
                         "a year with stations but no booked total, or the reverse")

    def test_every_coal_gwh_is_accounted_for(self):
        """The whole point. Generation the station rows do not place would be coal in the
        national total with no mass anywhere against it."""
        cppag = {int(r["fiscal_year"]): float(r["gwh_net"]) for r in _rows(GEN)
                 if "oal" in r["fuel"] and r["system"] == "CPPA-G"}
        placed = collections.defaultdict(float)
        panel = {_start_year(r["period_id"]) for r in self.booked}
        for r in self.station:
            if (r["net_generation_GWh"] or "").strip() not in ABSENT:
                placed[_start_year(r["period_id"])] += float(r["net_generation_GWh"])
        # The reconstructed lane counts as accounted for: generation that is PRINTED, with
        # a bounded mass and the rule that bounded it, is explained. Generation that is
        # merely absent is not. This is the distinction the test exists to hold - and the
        # lane it protects had been dropped by a schema rewrite for a whole release.
        for r in self.lane:
            placed[_start_year(r["period_id"])] += float(r["net_generation_GWh"])
        bad = []
        for year, gwh in sorted(cppag.items()):
            if year not in panel:
                continue
            if abs(gwh - placed.get(year, 0.0)) > 1.0:
                bad.append("FY%d: %.2f printed, %.2f placed" % (year, gwh, placed.get(year, 0.0)))
        self.assertFalse(bad, "coal generation neither a station row nor a declared "
                              "reconstructed-lane row accounts for:\n  " + "\n  ".join(bad))

    def test_a_reconstructed_lane_row_is_bounded_and_states_no_point(self):
        """The lane must stay an interval. A point mass here would be a reconstruction
        presented as an observation, and the whole reason the row exists is that no edition
        prints one."""
        self.assertTrue(self.lane, "the reconstructed commissioning lane is missing")
        for r in self.lane:
            self.assertEqual(r["quantity_class"], "reconstructed", r["period_id"])
            self.assertIsNone(_mass(r), "%s states a POINT mass for the reconstructed lane"
                              % r["period_id"])
            lo, hi = float(r["mass_lo_kt"]), float(r["mass_hi_kt"])
            self.assertLess(lo, hi, "%s has a degenerate interval" % r["period_id"])
            self.assertGreater(lo, 0.0)
            self.assertIn("GWh/kt", r["reconstruction_rule"],
                          "%s does not state the band it was bounded by" % r["period_id"])
            self.assertIn("generation_by_fuel.csv", r["generation_source"],
                          "%s does not point at the control it was derived from"
                          % r["period_id"])

    def test_the_lane_years_are_the_documented_ones(self):
        """coal_plant_fuel_back_years.csv names FY2016-17 (873.17 GWh) and FY2017-18
        (11,783.11 GWh) in its own header. Those two must appear here, with those values, or
        the data layer and the product disagree about what is missing."""
        found = {r["period_id"]: float(r["net_generation_GWh"]) for r in self.lane}
        self.assertAlmostEqual(found.get("FY2016-17", 0.0), 873.17, places=1)
        self.assertAlmostEqual(found.get("FY2017-18", 0.0), 11783.11, places=1)

    def test_the_lane_is_bounded_by_the_panel_s_own_intensities(self):
        """The band must be COMPUTED from the panel, not a remembered pair of numbers. The
        previous version of this lane carried 2.13-2.72 as a judgement no reader could
        reconstruct; this asserts the published interval is the generation over the band the
        imported-coal stations actually run at."""
        from pkinv.sectors.power.fuel_reconciliation import _intensity_band, rows
        lo_i, hi_i = _intensity_band(rows())
        self.assertLess(lo_i, hi_i)
        for r in self.lane:
            gwh = float(r["net_generation_GWh"])
            self.assertAlmostEqual(float(r["mass_lo_kt"]), gwh / hi_i, places=1,
                                   msg="%s low bound is not generation / the band's top"
                                       % r["period_id"])
            self.assertAlmostEqual(float(r["mass_hi_kt"]), gwh / lo_i, places=1,
                                   msg="%s high bound is not generation / the band's floor"
                                       % r["period_id"])

    def test_a_derived_mass_is_never_presented_as_a_measurement(self):
        """`quantity_class` is the column the review asked for: it separates a METERED
        quantity, printed as such by the edition beside it, from a DERIVED one computed from
        generation and an intensity. A derived row must say how it was derived, or the reader
        cannot tell the two apart from the number alone."""
        for r in self.rows:
            self.assertIn(r["quantity_class"], ("metered", "derived", "reconstructed"),
                          "%s %s" % (r["period_id"], r["plant"]))
            if r["quantity_class"] in ("derived", "reconstructed"):
                self.assertTrue(r["reconstruction_rule"].strip(),
                                "%s %s is derived and states no rule"
                                % (r["period_id"], r["plant"]))

    def test_a_metered_station_row_carries_a_mass_and_a_source(self):
        for r in self.station:
            if r["quantity_class"] != "metered":
                continue
            if _mass(r) is None:
                continue                  # a declared absence, tested below
            self.assertIn("NEPRA SoIR", r["mass_source_table"],
                          "%s %s names no source document" % (r["period_id"], r["plant"]))
            self.assertTrue(r["mass_source_edition"].strip(),
                            "%s %s names no edition" % (r["period_id"], r["plant"]))

    def test_an_absent_mass_is_typed_and_never_zero(self):
        """Numbers discipline: a station the edition does not print must read as an absence,
        not as a station that burned nothing."""
        for r in self.station:
            value = (r.get("mass_kt") or "").strip()
            self.assertNotEqual(value, "0", "%s %s states a zero mass"
                                % (r["period_id"], r["plant"]))
            if value in ABSENT:
                self.assertTrue(r["note"].strip() or r["rank_evidence"].strip(),
                                "%s %s is absent with nothing said about why"
                                % (r["period_id"], r["plant"]))

    def test_the_derived_lane_is_only_where_no_edition_prints(self):
        """Derivation is a last resort, not a convenience: FY2016-17 and FY2017-18 are in no
        per-station coal table any held edition prints."""
        years = {r["period_id"] for r in self.rows if r["quantity_class"] == "derived"}
        self.assertEqual(years, {"FY2016-17", "FY2017-18", "FY2018-19", "FY2021-22"},
                         "derivation has spread beyond the years no edition covers")

    def test_the_two_energy_bases_are_never_blended(self):
        """The booked basis and the generation-implied basis live in separate columns, which is
        the whole reason the preference between them can be stated at all."""
        for r in self.rows:
            self.assertIn(r["ncv_basis"], ("rank_default", "generation_implied"),
                          "%s %s" % (r["period_id"], r["plant"]))
            booked = (r["energy_TJ_booked_basis"] or "").strip()
            implied = (r["energy_TJ_generation_implied_basis"] or "").strip()
            if booked and implied:
                self.assertNotEqual(booked, implied,
                                    "%s %s prints one number under both bases, so the "
                                    "circularity argument cannot be checked"
                                    % (r["period_id"], r["plant"]))

    def test_the_station_account_fits_inside_national_supply(self):
        """THE MATCHED-BOUNDARY CHECK, and the reason the re-base happened. The audit's B1
        bound refutes NEPRA Table 3's energy: it needs more coal than the country supplied.
        The station account this file publishes must survive the same test on the same
        denominator, or the account that replaced the refuted one is no better."""
        audit = [r for r in _rows(AUDIT) if r["test_id"] == "B1_the_bound"]
        self.assertEqual(len(audit), 1, "the supply bound is no longer a single audit row")
        verdict = audit[0]["verdict"]
        # "INFEASIBLE" through rc66. The supply series has no stock term, so the bound
        # shows an excess that only an unrecorded drawdown could meet: implausible, and
        # worded as that (rc67, the review's Priority 4).
        self.assertIn("EXCEEDS SUPPLY UNLESS STOCKS FELL", verdict,
                      "B1 no longer sets Table 3's requirement against supply")
        self.assertNotIn("INFEASIBLE", verdict)
        supplied = float(verdict.replace(",", "").split("against")[1].split("kt")[0])
        year = audit[0]["period_id"]
        station = sum(m for m in (_mass(r) for r in self.station
                                  if r["period_id"] == year) if m is not None)
        self.assertGreater(station, 0.0, "no station mass read for %s" % year)
        self.assertLess(station, supplied,
                        "%s: the station account needs %.0f kt against %.0f kt supplied, so "
                        "it fails the same bound that refutes the account it replaced"
                        % (year, station, supplied))

    def test_the_check_flag_agrees_with_the_shipped_file(self):
        """--check must be able to PASS. It could not: it rebuilt the expected text by hand
        instead of calling table_text, and read the shipped file in text mode, where universal
        newlines collapse CRLF to LF - so a CRLF product compared unequal to itself and the
        flag reported DIFFERS on a file it had just written. A check that always fails is
        indistinguishable from one that always passes: nobody can act on either."""
        from pkinv.core.io import table_text
        from pkinv.sectors.power.fuel_reconciliation import BANNER, FIELDS, rows
        with open(OUT, encoding="utf-8", newline="") as handle:
            held = handle.read()
        self.assertEqual(held, table_text(list(FIELDS), rows(), banner=BANNER.splitlines()),
                         "the shipped reconciliation is not what the producer now writes")

    def test_the_other_consumer_can_still_read_this_product(self):
        """THE GUARD FOR THE DEFECT THAT ACTUALLY SHIPPED.

        pkinv.sectors.power.coal_configurations is the only other reader of this file, and it
        runs in the FULL build alone - so when a schema rewrite renamed the columns, nothing
        caught it for a release: this file's own test could not read its subject either, and
        the next full build died on KeyError('row_kind'). A schema check that only protects
        the test's own reading protects nothing about the consumer.

        Calling build() rather than inspecting the module's source, because the question is
        whether it can read what is shipped, not whether it mentions the right strings.
        """
        from pkinv.sectors.power import coal_configurations
        rows = coal_configurations.build()
        self.assertTrue(rows, "the configurations consumer produced no rows")
        periods = {r["period_id"] for r in rows if r.get("period_id")}
        self.assertEqual(len(periods), 9,
                         "the consumer resolved %d periods, not the panel's nine - it is "
                         "reading a key this product no longer carries" % len(periods))
        configs = {r["configuration_id"] for r in rows}
        self.assertGreaterEqual(len(configs), 4,
                                "the four coal-energy configurations are not all built")


if __name__ == "__main__":
    unittest.main()
