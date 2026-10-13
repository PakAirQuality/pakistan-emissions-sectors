"""The Table 3 coal energy fails a physical test the plant route passes.

WHY THIS TEST EXISTS. The power grid-control family publishes three readings of the same
national coal combustion as co-equal members, and for several releases the whole statement
of the disagreement was a single-year ratio: Table 3 implies 24.20 TJ/Gg where the plant
ledger implies 12.01, a factor of 2.01. A single-year ratio invites a single-year
explanation, and the hypotheses register duly filled with them - a calorific convention, a
gross basis, a scope difference, a stock change. Every one of those is a CONSTANT bias in
one direction.

Read across the whole ledger span the bias is not constant: it changes sign. That is what
this holds. The measurement is deliberately the one that does not use mass - each energy
figure divided by the coal generation NEPRA itself reports - so no error in Table 21's
tonnages can explain it away, and a plant set that is too wide cannot produce it either,
because too much coal makes energy too HIGH in every year and never too low in one.

WHAT IS ASSERTED, AND WHAT IS NOT. That the sign flip is present and that the plant route
stays admissible or near it. NOT that Table 3 is wrong: the official CRT filing agrees with
the regulator's coal energy to 2 per cent, which is standing counter-evidence the selection
rule cites, and nothing here overturns it. The finding is narrower - whichever reading is
right, it cannot be one that holds constant across the panel - and that is a constraint on
the hypotheses, not a verdict on the tables.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

OUT = os.path.join(ROOT, "outputs", "pakemis_power_coal_energy_adjudication.csv")

# A coal station's net thermal efficiency. The band is engineering, not tuning: a poor
# subcritical unit at the bottom, an ultra-supercritical one at the top.
COAL_EFF_LO, COAL_EFF_HI = 30.0, 45.0
# The plant route touches 45.7 in FY2021-22, just outside. Allowed explicitly rather than
# by widening the band, so the exception stays visible.
PLANT_ROUTE_TOLERANCE = 1.0


class TestTheTwoNepraTablesCannotBothDescribeOneFleet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the adjudication has not been built in this checkout")
        cls.rows = read_rows(OUT, comments=True)

    def _eff(self, key):
        return {r["period_id"]: float(r[key]) for r in self.rows if r[key]}

    def test_the_table3_discrepancy_changes_sign_across_the_panel(self):
        """The finding no constant explanation survives."""
        eff = self._eff("table3_implied_efficiency_pct")
        self.assertGreaterEqual(len(eff), 5, "the panel should span the ledger years")
        above = [p for p, v in eff.items() if v > COAL_EFF_HI]
        below = [p for p, v in eff.items() if v < COAL_EFF_LO]
        self.assertTrue(
            above and below,
            "Table 3's implied fleet efficiency no longer falls on BOTH sides of the "
            "admissible band (%g-%g). If it now sits on one side only, a constant scope or "
            "convention could explain it and the basis-change hypothesis in "
            "power_table3_hypotheses.csv needs restating.\n  %s"
            % (COAL_EFF_LO, COAL_EFF_HI,
               "\n  ".join("%s %.1f%%" % kv for kv in sorted(eff.items()))))

    def test_the_plant_route_stays_physically_admissible(self):
        """The asymmetry is the point: one route is a fleet and the other is not.

        READ THE SCOPE, because this test is weaker than it looks. The plant route's energy
        is its fleet calorific value times mass, and that CV is itself generation x heat rate
        / mass, so the product returns generation x heat rate and the efficiency is NEPRA's
        printed heat rates rearranged. Where the CV covers all the mass the identity holds to
        1.000 and 0.986 - see test_the_plant_route_is_circular_where_its_cv_covers_the_mass.
        So this asserts that NEPRA's own heat rates imply a plausible fleet, which they do by
        construction. It is kept because a BREAK in it would be informative, not because
        passing it corroborates anything.
        """
        eff = self._eff("plant_implied_efficiency_pct")
        bad = {p: v for p, v in eff.items()
               if not (COAL_EFF_LO - PLANT_ROUTE_TOLERANCE <= v
                       <= COAL_EFF_HI + PLANT_ROUTE_TOLERANCE)}
        self.assertFalse(
            bad,
            "the plant-level route left the admissible band by more than %g points: %s. "
            "If it does, the adjudication no longer distinguishes the two routes and the "
            "hypothesis it supports must be withdrawn."
            % (PLANT_ROUTE_TOLERANCE, bad))

    def test_the_two_mass_free_routes_agree_on_direction(self):
        """Composition-only uses no heat rates; the plant route uses no rank defaults.

        They are not independent of Table 21's mass, but they are independent of each
        OTHER's central assumption, and both must fall as the fleet turns to lignite.
        """
        rows = sorted(self.rows, key=lambda r: r["fiscal_start_year"])
        comp = [float(r["composition_only_ncv_TJ_per_Gg"]) for r in rows]
        plant = [float(r["plant_implied_ncv_TJ_per_Gg"]) for r in rows
                 if r["plant_implied_ncv_TJ_per_Gg"]]
        lig = [float(r["lignite_share_of_mass_pct"]) for r in rows]
        self.assertGreater(lig[-1], lig[0], "the fleet should be more lignite by the end")
        self.assertLess(comp[-1], comp[0],
                        "composition-only NCV must FALL as the lignite share rises")
        self.assertLess(plant[-1], plant[0],
                        "the plant-route NCV must fall as the lignite share rises")

    def test_table3_moves_the_wrong_way_against_its_own_fleet(self):
        rows = sorted(self.rows, key=lambda r: r["fiscal_start_year"])
        t3 = [float(r["table3_implied_ncv_TJ_per_Gg"]) for r in rows]
        lig = [float(r["lignite_share_of_mass_pct"]) for r in rows]
        self.assertGreater(
            t3[-1], t3[0],
            "Table 3's implied NCV no longer RISES while the lignite share goes %.0f%% -> "
            "%.0f%%. That was the finding; if it has changed, restate it."
            % (lig[0], lig[-1]))

    def test_the_break_is_inside_one_edition_not_between_two(self):
        """The correction that mattered: I first called this an edition change.

        It is not. NEPRA SoIR 2024's Table 3 prints FY2018-19 to FY2021-22 side by side,
        so the doubling of TOE per tonne is between two adjacent columns of ONE published
        table - a harder fact than a revision between editions, and a different one. If a
        later ingest re-sources either year from a different edition the claim in Section 7
        stops being true, and nothing else would notice.
        """
        src = {r["fiscal_year"]: r["source"] for r in
               read_rows(os.path.join(ROOT, "data", "sectors", "power", "activity",
                                      "fuel_consumed.csv"))
               if "oal" in r["fuel"]}
        a, b = src.get("2020"), src.get("2021")
        self.assertTrue(a and b, "the coal rows for FY2020-21 and FY2021-22 are missing")
        edition = lambda t: t.split(", Table")[0]
        self.assertEqual(
            edition(a), edition(b),
            "FY2020-21 and FY2021-22 coal energy now come from DIFFERENT editions (%r vs "
            "%r). Section 7 says the break is inside one edition's own table; re-check it."
            % (edition(a), edition(b)))
        self.assertIn("2024", edition(a),
                      "the edition behind both columns is no longer SoIR 2024: %r" % a)

    def test_the_energy_moves_against_the_same_reports_mass_and_generation(self):
        """Energy up, mass and generation down, in one report. The core contradiction."""
        rows = {r["period_id"]: r for r in self.rows}
        x, y = rows["FY2020-21"], rows["FY2021-22"]
        g = lambda r, k: float(r[k])
        self.assertGreater(g(y, "table3_coal_toe"), g(x, "table3_coal_toe"),
                           "Table 3's coal energy no longer rises across the break")
        self.assertLess(g(y, "table21_mass_kt"), g(x, "table21_mass_kt"),
                        "coal mass no longer falls across the break")
        self.assertLess(g(y, "coal_generation_GWh"), g(x, "coal_generation_GWh"),
                        "coal generation no longer falls across the break")

    def test_only_the_per_station_account_is_admissible_across_the_panel(self):
        """The result that picks one of three accounts of the same coal.

        Refined twice. I first read the instability as Table 3's conversion doubling; it is
        not - against HDIP's own tonnage, which Table 3 says it derives from, the conversion
        is 0.447 in both FY2019-20 and FY2020-21. What moves is the ratio of the two tonnage
        accounts. The physical test then separates them, and the asymmetry is the finding.
        """
        t21 = {r["period_id"]: float(r["table21_mass_implied_efficiency_pct"])
               for r in self.rows if r["table21_mass_implied_efficiency_pct"]}
        hdip = {r["period_id"]: float(r["hdip_mass_implied_efficiency_pct"])
                for r in self.rows if r["hdip_mass_implied_efficiency_pct"]}
        self.assertGreaterEqual(len(t21), 5)
        self.assertGreaterEqual(len(hdip), 5)
        out21 = {p: v for p, v in t21.items()
                 if not (COAL_EFF_LO <= v <= COAL_EFF_HI)}
        self.assertFalse(
            out21,
            "NEPRA's per-station tonnage left the admissible band: %s. Section 7 says it is "
            "the only one of the three accounts that does not; re-check that sentence."
            % out21)
        outh = {p: v for p, v in hdip.items() if not (COAL_EFF_LO <= v <= COAL_EFF_HI)}
        self.assertTrue(
            outh,
            "HDIP's national tonnage is now admissible in every year, so the asymmetry the "
            "finding rests on has gone. Re-state it.")

    def test_the_two_tonnage_accounts_cross_unity_across_the_break(self):
        """A scope difference cannot cross unity. That is why scope cannot be the answer."""
        r = {x["period_id"]: float(x["hdip_over_table21"]) for x in self.rows
             if x["hdip_over_table21"]}
        self.assertLess(r["FY2020-21"], 1.0,
                        "HDIP's tonnage is no longer BELOW the per-station account before "
                        "the break (%.2f)" % r["FY2020-21"])
        self.assertGreater(r["FY2021-22"], 1.0,
                           "HDIP's tonnage is no longer ABOVE it after the break (%.2f)"
                           % r["FY2021-22"])

    def test_table3s_conversion_against_its_own_source_is_stable_early(self):
        """The correction: the conversion is not what doubled."""
        t = {r["period_id"]: float(r["table3_toe_per_hdip_tonne"]) for r in self.rows
             if r["table3_toe_per_hdip_tonne"]}
        self.assertAlmostEqual(
            t["FY2019-20"], t["FY2020-21"], places=2,
            msg="Table 3's TOE per tonne of HDIP coal is no longer equal across FY2019-20 "
                "and FY2020-21 (%.3f vs %.3f); Section 7 calls them identical."
                % (t["FY2019-20"], t["FY2020-21"]))

    def test_every_period_carries_a_verdict(self):
        blank = [r["period_id"] for r in self.rows if not r["verdict"]]
        self.assertFalse(blank, "periods with no verdict: %s" % blank)

    def test_the_plant_route_is_circular_where_its_cv_covers_the_mass(self):
        """The identity, asserted rather than left for a reader to notice.

        plant_energy_TJ = fleet_CV x total mass, and fleet_CV = sum(generation x heat rate)
        / the mass it is weighted over, so the route is identically that sum divided by its
        coverage - in every year, not only where coverage is complete. That is why it cannot
        test NEPRA's heat rates: it contains them.

        If someone makes the route independent, this fails, and the right response is to say
        so in the module - not to delete the test. If the route silently stops being an
        identity while still being presented as corroboration, that is the defect this
        catches.
        """
        BTU_TO_TJ = 1.05505585262e-9
        cv_rows = read_rows(os.path.join(ROOT, "outputs",
                                         "power_implied_coal_cv_fy2023_24.csv"))
        checked, problems = 0, []
        for row in self.rows:
            coverage = row.get("fleet_cv_mass_coverage_pct") or ""
            if not (coverage and row["plant_energy_TJ"]):
                continue
            year = row["fiscal_start_year"]
            # The CV's own weight base: non-outlier stations with a printed heat rate. A
            # first version of this took every station with a heat rate and reported a
            # spurious 0.844 for FY2021-22, whose CV excludes one outlier.
            stations = [r for r in cv_rows
                        if r["fiscal_year"] == year and r["hr_btu_kwh"]
                        and r["evidence_class"] != "outlier"
                        and not r["plant"].startswith(("FLEET", "imported", "Thar lignite",
                                                       "Table 3", "ALL"))]
            if not stations:
                continue
            implied = sum(float(r["net_generation_GWh"]) * 1e6 * float(r["hr_btu_kwh"])
                          * BTU_TO_TJ for r in stations)
            # plant_energy = CV x total_mass and CV = implied / covered_mass, so the route is
            # implied / coverage. Exact in every year, not only where coverage is complete.
            expected = implied / (float(coverage) / 100.0)
            checked += 1
            ratio = float(row["plant_energy_TJ"]) / expected if expected else 0.0
            if not 0.98 <= ratio <= 1.02:
                problems.append("%s: plant_energy_TJ / (sum(gen x heat rate) / coverage) "
                                "= %.3f" % (year, ratio))
        self.assertGreaterEqual(checked, 4,
                                "the identity was checked only %d times" % checked)
        self.assertFalse(problems,
                         "the plant route is no longer the sum of generation x printed heat "
                         "rate where its CV covers the mass. If that is deliberate, the "
                         "module's 'IS NOT INDEPENDENT EVIDENCE' note has to change with "
                         "it:\n  " + "\n  ".join(problems))

    def test_the_conversion_channel_carries_the_level_discrepancy(self):
        """The corrected conclusion, held so the old one cannot come back.

        The banner used to infer where the break was from which RATIO was steadier across
        years - the conversion spreads 1.35x against the mass accounts' 2.03x - and concluded
        the disagreement lay in the mass accounts. Variance is not location. Decomposed in
        logs against the non-circular physical route, the conversion channel carries the
        majority of the level discrepancy in every year of the panel.
        """
        shares = {r["fiscal_start_year"]: float(r["conversion_channel_share_pct"])
                  for r in self.rows if r.get("conversion_channel_share_pct")}
        self.assertGreaterEqual(len(shares), 4,
                                "only %d years publish a channel share" % len(shares))
        minority = {y: v for y, v in shares.items() if v <= 50.0}
        self.assertFalse(
            minority,
            "the conversion channel is no longer the majority of the level discrepancy in "
            "%s. The banner's conclusion rests on it being so; if the decomposition has "
            "moved, the conclusion must be rewritten rather than this threshold lowered."
            % minority)

    def test_the_fleet_cv_coverage_is_published_for_every_year(self):
        """A bias that is noted but not published does not travel with the number.

        The fleet CV is weighted over the stations with a printed heat rate and multiplied by
        TOTAL mass, so where coverage is short the plant route's energy is inflated by
        1/coverage. Two of the five years run at 69 and 72 per cent, because the only lignite
        station has no printed heat rate and an imported-only CV of about 23 TJ/Gg is applied
        to lignite tonnes worth about 11.
        """
        for row in self.rows:
            if not row["plant_energy_TJ"]:
                continue
            self.assertTrue(row.get("fleet_cv_mass_coverage_pct"),
                            "%s publishes a plant-route energy with no coverage figure "
                            "beside it" % row["fiscal_start_year"])
            self.assertLessEqual(float(row["fleet_cv_mass_coverage_pct"]), 100.5,
                                 "%s reports coverage above 100 per cent"
                                 % row["fiscal_start_year"])

    def test_the_central_conclusion_survives_a_wider_envelope(self):
        """The asymmetry must not depend on where the band's edges are put.

        The 30-45 band is a plausibility screen from general thermal practice, not a
        Pakistani measurement, and three cells change side under a wider 28-47: Table 3 at
        45.1 in FY2019-20 and 29.6 in FY2021-22, and the HDIP account at 29.1 in FY2023-24.
        Two of those are quoted in verdict strings. An earlier version of the banner said the
        verdicts did not turn on the edges, which was false.

        What this holds is the part that does not turn on them: the per-station account is
        inside BOTH bands in every year and Table 3 is outside both in three of five. If that
        stops being true the file's conclusion is band-dependent and has to say so in its own
        voice rather than resting on a screen nobody sourced.
        """
        WIDE_LO, WIDE_HI = 28.0, 47.0
        inside_both, outside_both = 0, 0
        for row in self.rows:
            station = row["table21_mass_implied_efficiency_pct"]
            if station:
                v = float(station)
                self.assertTrue(
                    COAL_EFF_LO <= v <= COAL_EFF_HI and WIDE_LO <= v <= WIDE_HI,
                    "the per-station account reads %.1f in FY%s, outside one of the two "
                    "bands; the adjudication's conclusion is now band-dependent"
                    % (v, row["fiscal_start_year"]))
                inside_both += 1
            t3 = row["table3_implied_efficiency_pct"]
            if t3:
                v = float(t3)
                if not (COAL_EFF_LO <= v <= COAL_EFF_HI) and not (WIDE_LO <= v <= WIDE_HI):
                    outside_both += 1
        self.assertGreaterEqual(inside_both, 5,
                                "only %d per-station readings were checked" % inside_both)
        self.assertGreaterEqual(
            outside_both, 3,
            "Table 3 is now outside both bands in only %d years. The asymmetry between the "
            "accounts is what this file concludes from; if it has narrowed, the conclusion "
            "needs restating." % outside_both)

    def test_no_station_departs_from_its_own_electricity_per_tonne(self):
        """A per-station detector, not a hard-coded exception.

        Found by looking: Sahiwal prints 1,443.97 kt against 6,881.4 GWh in FY2021-22 -
        4.766 GWh per kilotonne where its own other four years run 2.44 to 2.72 - so roughly
        1,174 kt is missing from a NEPRA table. Nothing in this repository named it, and it
        matters because putting the tonnes back moves that year's HDIP-over-Table-21 ratio
        from 1.053 to 0.961 and the crossing the adjudication reasons from moves a year
        later. (The crossing itself survives: FY2022-23 and FY2023-24 stay above unity.)

        The threshold is deliberately loose. A station's coal-to-electricity ratio moves with
        rank, load factor and outages, so a factor of 1.6 against its own median is not a
        tight bound - it is the bound that separates "this plant ran differently" from "a
        tonnage is missing". KNOWN carries the one case already diagnosed; a new entry there
        needs the same arithmetic written down beside it.
        """
        KNOWN = {("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", "2021")}
        TOLERANCE = 1.6
        cv_rows = read_rows(os.path.join(ROOT, "outputs",
                                         "power_implied_coal_cv_fy2023_24.csv"))
        by_plant = {}
        for r in cv_rows:
            if r["plant"].startswith(("FLEET", "imported", "Thar lignite", "Table 3", "ALL")):
                continue
            if not (r["mass_kt"] and r["net_generation_GWh"]):
                continue
            mass, gen = float(r["mass_kt"]), float(r["net_generation_GWh"])
            if mass <= 0:
                continue
            by_plant.setdefault(r["plant"], []).append((r["fiscal_year"], gen / mass))
        flagged, checked = [], 0
        for plant, series in sorted(by_plant.items()):
            if len(series) < 3:
                continue
            for year, value in series:
                others = sorted(v for y, v in series if y != year)
                median = others[len(others) // 2]
                checked += 1
                ratio = value / median if median else 0.0
                if max(ratio, 1.0 / ratio if ratio else 0.0) > TOLERANCE:
                    if (plant, year) in KNOWN:
                        continue
                    flagged.append("%s FY%s: %.3f GWh/kt against a median of %.3f"
                                   % (plant, year, value, median))
        self.assertGreater(checked, 20,
                           "only %d station-years were screened" % checked)
        self.assertFalse(
            flagged,
            "a station's electricity per tonne departs from its own series by more than "
            "%.1fx, which is the shape of a missing tonnage in the source table. Work out "
            "the implied mass and what it does to hdip_over_table21 before adding it to "
            "KNOWN:\n  " % TOLERANCE + "\n  ".join(flagged))

    def test_the_shipped_file_matches_a_fresh_build(self):
        r = subprocess.run(
            [sys.executable, "-m", "pkinv.sectors.power.coal_energy_adjudication", "--check"],
            capture_output=True, text=True, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(r.returncode, 0,
                         "the adjudication is stale; rebuild it.\n%s%s" % (r.stdout, r.stderr))


if __name__ == "__main__":
    unittest.main()
