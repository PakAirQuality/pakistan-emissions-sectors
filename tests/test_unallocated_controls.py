"""FY2015-16: the recovered year, and what the recovery must never quietly break.

For four releases two sector-years were NE while this ledger held their observed totals
and named the one missing field (product_split). At rc20 the split was recovered from the
public record - the Pakistan Oil Report 2015-2016's page-50 table, image-only, transcribed
under a quadruple identity gate - and the two controls became the transcription's
TWO-DOCUMENT gate. Everything here defends the closed state's honesty:

  * the controls survive with their provenance (they now anchor the recovered edition
    across two independent documents, so losing them would orphan the gate);
  * the gate has teeth - a corrupted transcription digit refuses to load;
  * the recovered year is a REAL ten-sector national year everywhere downstream, with
    no absent rows left anywhere;
  * the bridge that could have modelled the year stays declared-and-unpopulated forever
    (the observed split made every modelled alternative moot, which is the strongest
    possible argument for never populating it);
  * and the eight years that were already complete are NUMERICALLY unmoved, because the
    cheapest way to fake a recovery is to disturb the years that already worked.

Run:  python3 -m unittest discover tests -p "test_unallocated_controls.py"
"""
import collections
import csv
import os
import unittest

from pkinv.paths import DATA, OUTPUTS
from pkinv.report import atomic_annual, bridge_configurations, unallocated_controls
from pkinv.sectors.transport import ocac_image_edition
from pkinv.core.io import read_rows


def _rows(name, base=OUTPUTS):
    return read_rows(os.path.join(base, name), comments=False)


RECOVERED_SECTOR_YEARS = {("transport", "FY2015-16"), ("industry", "FY2015-16")}
COMPLETE_YEARS = ("FY2015-16", "FY2016-17", "FY2017-18", "FY2018-19", "FY2019-20",
                  "FY2020-21", "FY2021-22", "FY2022-23", "FY2023-24")
PRE_RECOVERY_YEARS = COMPLETE_YEARS[1:]


class TestTheControlsBecameTheGate(unittest.TestCase):
    def setUp(self):
        self.ledger = _rows("pakemis_unallocated_activity_controls.csv")

    def test_the_road_control_is_present_with_its_provenance(self):
        """The FY2015-16 Road total anchors the recovered edition across two
        independent documents. It must not disappear now that the year is E -
        without it the transcription's strongest gate has nothing to hold to."""
        road = [r for r in self.ledger
                if r["claimant_sector"] == "transport" and r["fiscal_year"] == "FY2015-16"]
        self.assertEqual(len(road), 1)
        row = road[0]
        self.assertAlmostEqual(float(row["value"]), 12440195.0, places=3)
        self.assertEqual(row["unit"], "tonnes")
        self.assertEqual(len(row["source_sha256"]), 64)
        self.assertTrue(row["source_document"])
        self.assertIn("TOTAL_PRIOR", row["source_column"])
        self.assertIn("prior-year", row["note"].lower())

    def test_every_control_records_the_closure(self):
        self.assertTrue(self.ledger)
        for row in self.ledger:
            self.assertEqual(row["allocation_state"], "split_recovered")
            self.assertEqual(row["emissions_state"], "E")
            self.assertEqual(row["missing_field"], "")
            self.assertEqual(row["reason_code"], unallocated_controls.CLOSED_CODE)
            self.assertIn("CLOSED at rc20", row["what_would_close_it"])

    def test_the_ledger_covers_exactly_the_recovered_sector_years(self):
        held = {(r["claimant_sector"], r["fiscal_year"]) for r in self.ledger}
        self.assertEqual(held, RECOVERED_SECTOR_YEARS)

    def test_the_transcription_gates_hold_on_the_committed_file(self):
        table = ocac_image_edition.load()
        self.assertEqual(
            table[("TRANSPORT", "Road")]["TOTAL"], 12440195.0)
        self.assertEqual(
            table[("INDUSTRY", "Total Industry")]["TOTAL"], 2023377.0)

    def test_the_gate_has_teeth(self):
        """The positive control: corrupt one digit of one cell and the load must
        refuse. An identity gate that cannot fail is a comment, not a gate."""
        real = ocac_image_edition._rows()
        corrupted = [dict(r) for r in real]
        for r in corrupted:
            if r["sector_row"] == "Road" and r["product"] == "MS":
                r["tonnes"] = str(float(r["tonnes"]) + 100)
        original = ocac_image_edition._rows
        ocac_image_edition._rows = lambda: corrupted
        try:
            with self.assertRaises(SystemExit):
                ocac_image_edition.load()
        finally:
            ocac_image_edition._rows = original

    def test_the_two_document_gate_reads_the_live_ledger(self):
        """The gate compares against the FY2016-17 edition's prior column as
        committed - so a silent change to either document breaks the load."""
        with open(ocac_image_edition.ANNUAL_CSV, newline="", encoding="utf-8") as f:
            prior = {r["sector_row"]: float(r["tonnes"])
                     for r in csv.DictReader(f)
                     if r["fiscal_year_start"] == "2016"
                     and r["product"] == "TOTAL_PRIOR"
                     and r["sector_row"] in ("Road", "Total Industry")}
        self.assertEqual(prior["Road"], 12440195.0)
        self.assertEqual(prior["Total Industry"], 2023377.0)


class TestTheRecoveredYearIsReal(unittest.TestCase):
    def test_no_absent_rows_remain_anywhere(self):
        atom = _rows("pakemis_atomic_annual.csv")
        absent = {(r["sector_id"], r["period_id"]) for r in atom
                  if r["estimate_status"] == "absent"}
        self.assertEqual(absent, set(),
                         "absent rows survived the recovery - either the flip "
                         "did not reach the atom or a NEW absence appeared and "
                         "must be declared in national_series.GAPS")
        for row in _rows("pakemis_national_series.csv"):
            self.assertNotEqual(row["activity_basis"], "absent", row["sector"])
        for row in _rows("pakemis_annual_fy2015_16_fy2023_24.csv"):
            self.assertNotEqual(row.get("grain"), "absent")

    def test_the_recovered_sector_years_carry_values(self):
        atom = _rows("pakemis_atomic_annual.csv")
        for sector, period in RECOVERED_SECTOR_YEARS:
            rows = [r for r in atom
                    if r["sector_id"] == sector and r["period_id"] == period
                    and r["co2e_Mt_AR5"]]
            self.assertTrue(rows, "%s %s has no atomic rows" % (sector, period))
            self.assertGreater(sum(float(r["co2e_Mt_AR5"]) for r in rows), 1.0)


class TestEveryYearIsANationalTotal(unittest.TestCase):
    def test_no_covered_total_rows_remain(self):
        levels = {r["period_id"]: r["aggregation_level"]
                  for r in _rows("pakemis_atomic_annual_aggregates.csv")
                  if r["aggregation_level"] in ("national", "covered_total")}
        for year in COMPLETE_YEARS:
            self.assertEqual(levels[year], "national", year)

    def test_every_year_is_additive(self):
        """Sector rows sum to the period's published total, in every year."""
        atom = collections.defaultdict(float)
        for row in _rows("pakemis_atomic_annual.csv"):
            if row["co2e_Mt_AR5"]:
                atom[row["period_id"]] += float(row["co2e_Mt_AR5"])
        published = {r["period_id"]: float(r["co2e_Mt_AR5"])
                     for r in _rows("pakemis_atomic_annual_aggregates.csv")
                     if r["aggregation_level"] == "national"}
        for year in COMPLETE_YEARS:
            self.assertAlmostEqual(atom[year], published[year], places=6, msg=year)


class TestTheBridgeIsDeclaredAndUnreachable(unittest.TestCase):
    """The bridge stays declared-not-populated FOREVER: the observed split made
    every modelled alternative moot, and populating it now would be modelling a
    year the record observes. The contract stays because the next partial year
    will want a working gate rather than a comment."""

    def setUp(self):
        self.registry = bridge_configurations.registry()

    def test_it_is_declared_and_not_populated(self):
        """Wave 6: both FY2015-16 bridges moved to HISTORICAL_MOOT - the rc20
        recovery made the question they answered moot, and a row saying "the
        strict answer remains NE" two releases after the panel reached zero NE
        sector-years was the register's most misleading state. Still declared,
        still never populated; the retained gate keeps working."""
        self.assertTrue(self.registry)
        for row in self.registry:
            self.assertEqual(row["activation_state"],
                             bridge_configurations.HISTORICAL_MOOT)
            self.assertEqual(row["derivation_state"], "proxy_backcast")
            self.assertTrue(row["permitted_alternatives"].strip())
            self.assertTrue(row["unit_precondition"].strip())
        bridge_configurations.validate(self.registry)

    def test_no_strict_output_can_select_a_bridge_row(self):
        """The reference configuration is not a bridge, and no published row carries one."""
        ids = set(bridge_configurations.declared_ids(self.registry))
        self.assertNotIn(atomic_annual.REFERENCE_CONFIGURATION, ids)
        for name in ("pakemis_atomic_annual.csv", "pakemis_monthly_fy2015_16_fy2023_24.csv",
                     "pakemis_atomic_annual_aggregates.csv"):
            for row in _rows(name):
                self.assertNotIn(row["configuration_id"], ids,
                                 "%s carries a bridge configuration" % name)
        for name in ("national_configurations.csv", "national_axis_register.csv"):
            for row in _rows(name):
                self.assertFalse(set(row.values()) & ids,
                                 "%s names a bridge; bridges are not axes" % name)

    def test_a_populated_alternative_must_conserve_the_control_exactly(self):
        """The contract ships before the first alternative does, so the alternative meets a
        working gate rather than a comment."""
        control = 12440195.0
        bridge_configurations.validate_allocation(
            control, {"MS": 0.4, "HSD": 0.55, "FO": 0.05})
        with self.assertRaises(bridge_configurations.BridgeContractError):
            bridge_configurations.validate_allocation(control, {"MS": 0.4, "HSD": 0.5})
        with self.assertRaises(bridge_configurations.BridgeContractError):
            bridge_configurations.validate_allocation(control, {"MS": 1.2, "HSD": -0.2})

    def test_alternatives_may_not_be_weighted_into_a_distribution(self):
        """Three answers to one unanswered question are not three draws. Averaging them
        would produce a central estimate that no evidence supports."""
        with self.assertRaises(bridge_configurations.BridgeContractError):
            bridge_configurations.validate_allocation(
                12440195.0, {"MS": 0.4, "HSD": 0.6}, weights={"nearest_year": 1.0})

    def test_a_bridged_row_is_never_marked_observed(self):
        with self.assertRaises(bridge_configurations.BridgeContractError):
            bridge_configurations.validate_allocation(
                12440195.0, {"MS": 0.4, "HSD": 0.6}, derivation_state="observed")

    def test_the_bridge_is_not_a_parametric_uncertainty(self):
        """Structural bridges and the Monte Carlo answer different questions and live in
        different files; a bridge id appearing in the uncertainty product would mean the
        interval had absorbed a structural choice."""
        ids = set(bridge_configurations.declared_ids(self.registry))
        for row in _rows("national_uncertainty_montecarlo.csv"):
            self.assertFalse(set(row.values()) & ids)


class TestThePreRecoveryYearsDidNotMove(unittest.TestCase):
    """The cheapest way to fake a recovery is to disturb the years that already
    worked. These are the numbers that must not move when FY2015-16 opens."""

    def test_all_nine_years_are_ten_sector_and_full_scope(self):
        coverage = {r["period_label"]: r
                    for r in _rows("pakemis_national_series_coverage.csv")}
        for year in COMPLETE_YEARS:
            self.assertEqual(int(coverage[year]["sectors_covered"]), 10, year)
            self.assertEqual(float(coverage[year]["coverage_share_pct_of_reference"]),
                             100.0, year)
            self.assertEqual(coverage[year]["sectors_absent"], "none", year)

    def test_the_reference_year_is_unmoved(self):
        national = next(float(r["co2e_Mt_AR5"]) for r in _rows("national_all_sectors.csv")
                        if r["row_kind"] == "national_total")
        # rc39 A1 re-base: the reference herd became the census's exact enumeration, so the pins moved for the first time since rc30 (L 452.14350 -> 452.33432, S 447.01683 -> 447.20153; agriculture +0.184699 and residential +0.006121 through the dung handoff)
        # rc39 A2: FracGASF is one global factor, so re-weighting it onto the fiscal year's own product mix lifts managed soils in EVERY year by ~0.0021-0.0023 Mt
        # 2026-10-07 THE POWER COAL RE-BASE: public-power coal energy is booked on the
        # stations' own metered coal at IPCC rank defaults instead of NEPRA Table 3's
        # published energy, and grid 1.A.1.a falls 57.82049 -> 40.04008. Previous pin,
        # rc52..this: 469.63822, which the retained legacy control reproduces to the
        # fifth decimal (national_configurations.csv, power_table3_legacy_control).
        self.assertAlmostEqual(national, 444.95542, places=5)   # rc67 reference re-base (was 451.85782)

    def test_the_eight_pre_recovery_years_are_unmoved(self):
        """Pinned totals - the recovery may only ADD FY2015-16.

        RE-BASED IN rc39 A1, and the shape of the move is the point. The census herd
        reaches the history through ONE channel only: the dung handoff, which derives the
        residential dung basis from the reference-year ledger and applies it across the
        panel. So every historical year rises by 0.0047-0.0059 Mt - a smooth ramp, all of
        it residential - while agriculture's own historical years do not move at all,
        because each reads its own year's activity. The reference year moves by 0.19082,
        which is agriculture's 0.18470 plus the same handoff's 0.00612.

        Pinned at 4 places rather than the old 2. These were rc19 values carried at two
        decimals, which is a tolerance of 5e-3 - wider than every historical movement the
        re-base actually caused. A guard whose whole purpose is to catch unintended
        movement should not be blind to a move of this size, and at 4 places it is not."""
        # The composed-vs-summed ulp split that separated these two pins at A2 (452.33663 here
        # against 452.33664 above) closed at A3: both files now print 452.34662. The split is a
        # property of where the digits fall, not of the arithmetic, so it can reopen - each pin
        # is still read from its own file rather than assumed equal to the other.
        # rc46 Wave 2: every year re-priced on its OWN brick and cement coal (the HDIP
        # series covers the whole window), so all eight moved together with the reference -
        # the per-year delta IS that year's activated coal, largest where the brick column
        # spikes (FY2020-21 +46.38, the year the reconciliation shows HDIP's brick residual
        # absorbing the power-lane disagreement).
        # rc50: THE CLINKER RE-BASE - the eight historical years ride the clinker balance at the
        # census-implied fraction (0.965, cement.census_implied_fraction) instead of the IPCC
        # blended default 0.75; 2.A.1 rises +3.96..+5.57 Mt a year (+37.13 in total) and closes
        # the +9,027 kt FY2022-23 -> FY2023-24 method break to +109 kt. FY2023-24 is the census
        # and did not move, so the L/S pins hold; the bridge is pakemis_industrial_coal_bridge.csv.
        # rc52: THREE CATEGORIES ENTER THE REFERENCE (the boundary program's Wave C) - ammonia
        # (Tier 1 calibrated on NFDC production), iron and steel (Tier 1 EAF on QIM billets) and
        # lubricant use (Tier 1 ODU on OCAC sales), each a full nine-year series BEFORE it
        # entered. Every year moves by exactly its activated atoms: +3.04 (FY2015-16), +3.23,
        # +2.97, +2.98, +3.09, +3.58, +3.80, +3.41, +3.72 (FY2023-24); the L/S pins move with
        # FY2023-24 in scripts/check_pins.py. Previous (rc50) pins: 423.84615, 447.77589,
        # 443.86472, 443.63919, 475.92647, 493.97688, 453.20894, 465.91851.
        # 2026-10-07 THE POWER COAL RE-BASE. Every year moves by its own coal account, and
        # the moves CHANGE SIGN twice: -0.49, +4.20, +4.20, +5.89, +11.07, -7.29, -11.38,
        # -17.78 (FY2016-17..FY2023-24). That is why no constant correction was admissible.
        # The per-year cause - the mass term and the calorific term whose product is the
        # ratio - is published in outputs/pakemis_power_coal_rebase_ledger.csv, and the
        # previous series is reachable through the legacy axis in
        # outputs/pakemis_structural_trajectories.csv. Previous (rc52) pins: 427.07446,
        # 450.74216, 446.84585, 446.73310, 479.51051, 497.77448, 456.62081, 469.63822.
        #
        # THE PEAK MOVED, which is the one qualitative consequence: it was FY2021-22 and is
        # now FY2020-21, by 0.095 Mt. A test asserting the peak's location would be asserting
        # a difference smaller than the structural fork it rides on, so there is none - the
        # manuscript says the position is not robust instead.
        #
        # rc67 REFERENCE RE-BASE, declared: fertiliser feedstock out of the gas leakage base,
        # household dung on the survey series, wastewater nitrous oxide on the 2019
        # Refinement with each year's own sanitation shares. Previous (rc66) pins:
        # 426.58053, 454.94353, 451.04843, 452.62773, 490.58301, 490.48805, 445.23595,
        # 451.85781. FY2020-21 and FY2021-22 are within 0.003 Mt of each other and FY2021-22
        # is now marginally the higher: the peak's position is not robust, as before.
        pinned = {"FY2016-17": 419.43996, "FY2017-18": 447.91008, "FY2018-19": 444.08059,
                  "FY2019-20": 445.51419, "FY2020-21": 483.44611, "FY2021-22": 483.44854,
                  "FY2022-23": 438.34095, "FY2023-24": 444.95542}
        totals = {r["period_label"]: float(r["co2e_Mt_AR5"])
                  for r in _rows("pakemis_national_series.csv")
                  if r["row_kind"] == "covered_total"}
        for year, want in pinned.items():
            self.assertAlmostEqual(totals[year], want, places=4, msg=year)


if __name__ == "__main__":
    unittest.main()
