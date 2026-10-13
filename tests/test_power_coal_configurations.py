"""Four accounts of the power-coal energy, and the one property that distinguishes them.

The reviewer's objection to the published power estimate is that nothing justifies it. The
answer is not a better number but a statement of what each candidate depends on - and the
distinction that matters is CIRCULARITY: a candidate whose energy is derived from a printed
heat rate contains the generation it is later divided by, so its implied efficiency restates
the regulator's own print rather than testing it. These tests hold that label to the data.
"""
import csv
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "pakemis_power_coal_configurations.csv")


def _rows(path):
    body = "".join(l for l in open(path, encoding="utf-8") if not l.startswith("#"))
    return list(csv.DictReader(io.StringIO(body)))


class TestTheConfigurations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the configurations have not been built here")
        cls.rows = _rows(OUT)

    def test_it_found_rows(self):
        """A closure test over an empty read passes; this is what stops that."""
        self.assertGreater(len(self.rows), 25)
        self.assertEqual(len({r["period_id"] for r in self.rows}), 9)

    def test_exactly_one_candidate_is_circular_and_it_is_named(self):
        circular = {r["configuration_id"] for r in self.rows
                    if r["circular_with_generation"] == "yes"}
        self.assertEqual(circular, {"C3_stations_heat_rate"},
                         "the circular route is no longer exactly C3, which is the one "
                         "property this file exists to publish")

    def test_the_non_circular_route_covers_the_whole_panel(self):
        """A route that is honest but only covers half the years cannot carry a re-base."""
        years = {r["period_id"] for r in self.rows
                 if r["configuration_id"] == "C1_stations_rank_default"}
        self.assertEqual(len(years), 9, "C1 no longer spans the panel")

    def test_circularity_matches_how_the_value_was_DERIVED(self):
        """Not whether the words "heat rate" appear - C1's basis says "NO heat rate", which
        contains them. What makes a route circular is deriving the calorific value FROM
        generation, so that is what is checked."""
        for r in self.rows:
            derived_from_generation = "generation x printed heat rate" in r["cv_basis"]
            self.assertEqual(
                r["circular_with_generation"] == "yes", derived_from_generation,
                "%s %s: circular_with_generation=%s but its calorific basis reads %r"
                % (r["period_id"], r["configuration_id"], r["circular_with_generation"],
                   r["cv_basis"]))

    def test_the_ratio_crosses_unity(self):
        """The finding the file carries: Table 3 is not biased in one direction, so no scalar
        correction exists. If the ratio stopped crossing, the mechanism claim would change."""
        lows, highs = [], []
        for r in self.rows:
            if r["configuration_id"] != "C1_stations_rank_default":
                continue
            v = r["ratio_to_C0"]
            if not v:
                continue
            parts = [float(x) for x in v.split("-")]
            lows.append(min(parts)); highs.append(max(parts))
        self.assertTrue(lows and highs)
        self.assertLess(min(lows), 1.0, "C1/C0 is never below one")
        self.assertGreater(max(highs), 1.0, "C1/C0 is never above one")

    def test_a_reconstructed_year_carries_an_interval_not_a_point(self):
        for r in self.rows:
            if r["configuration_id"] != "C1_stations_rank_default":
                continue
            if r["coal_energy_TJ"] == "":
                self.assertTrue(r["coal_energy_lo_TJ"] and r["coal_energy_hi_TJ"],
                                "%s has neither a point nor an interval" % r["period_id"])
                self.assertLess(float(r["coal_energy_lo_TJ"]), float(r["coal_energy_hi_TJ"]))

    def test_c1_and_c2_share_a_calorific_value(self):
        """The pair is only useful if it isolates the MASS question, which needs the calorific
        value held identical between them."""
        by = {}
        for r in self.rows:
            if r["configuration_id"] in ("C1_stations_rank_default", "C2_hdip_rank_default"):
                by.setdefault(r["period_id"], {})[r["configuration_id"]] = r["cv_TJ_per_Gg"]
        for period, pair in by.items():
            if len(pair) == 2:
                self.assertEqual(pair["C1_stations_rank_default"], pair["C2_hdip_rank_default"],
                                 "%s: C1 and C2 no longer share a calorific value, so their "
                                 "difference is not purely the mass account" % period)

    def test_every_row_names_both_its_sources(self):
        for r in self.rows:
            self.assertTrue(r["mass_source"], "%s %s names no mass source"
                            % (r["period_id"], r["configuration_id"]))
            self.assertTrue(r["cv_source"], "%s %s names no calorific source"
                            % (r["period_id"], r["configuration_id"]))

    def test_the_band_verdict_is_derived_and_not_typed(self):
        """Every verdict must follow from the numbers in its own row, so the column cannot
        drift from the efficiency it claims to grade."""
        from pkinv.sectors.power.reference_audit import BAND_LO, BAND_HI
        for r in self.rows:
            point = r["implied_net_efficiency_pct"]
            lo = r["implied_net_efficiency_lo_pct"] or point
            hi = r["implied_net_efficiency_hi_pct"] or point
            if not lo or not hi:
                self.assertEqual(r["efficiency_band_verdict"], "",
                                 "%s %s grades an efficiency it does not print"
                                 % (r["period_id"], r["configuration_id"]))
                continue
            lo, hi = float(lo), float(hi)
            if BAND_LO <= lo and hi <= BAND_HI:
                expected = "inside %g-%g" % (BAND_LO, BAND_HI)
            elif hi < BAND_LO or lo > BAND_HI:
                expected = "OUTSIDE %g-%g" % (BAND_LO, BAND_HI)
            else:
                expected = "straddles %g-%g" % (BAND_LO, BAND_HI)
            self.assertEqual(r["efficiency_band_verdict"], expected,
                             "%s %s" % (r["period_id"], r["configuration_id"]))

    def test_a_reconstructed_year_still_gets_a_verdict(self):
        """The four years with no printed mass used to carry no efficiency at all, because
        the point energy was None - so the panel test could only be stated for the five years
        that needed no reconstruction, which is precisely the half that was never in doubt."""
        intervals = [r for r in self.rows
                     if r["configuration_id"] == "C1_stations_rank_default"
                     and not r["coal_energy_TJ"]]
        self.assertEqual(len(intervals), 4, "the reconstructed-year count moved; re-anchor")
        for r in intervals:
            self.assertTrue(r["implied_net_efficiency_lo_pct"], r["period_id"])
            self.assertTrue(r["implied_net_efficiency_hi_pct"], r["period_id"])
            self.assertTrue(r["efficiency_band_verdict"], r["period_id"])

    def test_the_panel_separates_the_published_control_from_the_station_account(self):
        """THE RESULT THE RE-BASE RESTS ON, asserted so prose cannot drift from it.

        A count, not a tolerance: the published control is physically implausible in most
        years of the panel and the non-circular station account is plausible in all of them.
        If either number moves, the manuscript's claim has moved with it.
        """
        inside = {}
        for r in self.rows:
            inside.setdefault(r["configuration_id"], []).append(
                r["efficiency_band_verdict"].startswith("inside"))
        self.assertEqual(sum(inside["C0_table3"]), 2,
                         "Table 3's in-band year count moved")
        self.assertEqual(len(inside["C1_stations_rank_default"]), 9)
        # SEVEN, NOT NINE, and the change is a correction rather than a regression. The
        # station account's two bounded years (FY2016-17 and FY2017-18) STRADDLE the envelope
        # instead of sitting wholly inside it, because the commissioning lane's interval is
        # bounded by the intensity range its own two stations run at over the ledger years -
        # a range that includes a sharply curtailed year. A commissioning plant is a part-load
        # plant, so that is the relevant end of the range, not an outlier to discard. The
        # previous 9-of-9 rested on a narrower band whose exclusions no reader could
        # reconstruct; narrowing it back would be choosing the bound that closes.
        self.assertEqual(sum(inside["C1_stations_rank_default"]), 7,
                         "the station account's in-band year count moved")
        straddle = [r["period_id"] for r in self.rows
                    if r["configuration_id"] == "C1_stations_rank_default"
                    and r["efficiency_band_verdict"].startswith("straddles")]
        self.assertEqual(sorted(straddle), ["FY2016-17", "FY2017-18"],
                         "the straddling years are not the two whose coal is bounded")
