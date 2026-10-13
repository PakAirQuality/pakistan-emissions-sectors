"""The two power-plant workbooks, read at last, and the Lahore register built on them.

Three things are guarded here, and each one is a way this ingest could go quietly wrong.

THE YEAR CONVENTION. The workbooks label a fiscal year by its END year. That was established
against this repository's own monthly sums rather than assumed, and if it is ever read the other
way every plant's history shifts by twelve months without anything failing. So it is asserted.

THE FACTOR BOUNDARY. The workbooks carry their own emission numbers, computed as activity times a
literature kg/MWh factor. This release computes SO2 from a sulfur balance on a dated evidence
register. The workbook's numbers may be COMPARED and must never become the estimate, so no
register may be written by the ingest and the crosscheck file must say what it is on every row.

WHAT IS NOT MEASURED MUST SAY SO. A heat rate carried outside the years it was published, a
regulatory-maximum sulfur, an assumed control state: each is an assumption, and a row that
presents one as a measurement is the defect these columns exist to prevent.

AND TWO CEILINGS ARE NOT A CORROBORATION. The workbook's literature kg/MWh factor implies a ~3 %
fuel, which is Pakistan's regulatory MAXIMUM rather than any assay. While the register borrowed
industry's 3.0 % the two agreed closely - and that agreement carried no information, because both
sides were the same ceiling. The comparison below is therefore written against the quantity the
two methods really share, the activity, with the sulfur difference measured rather than tolerated.
"""

from pkinv.assets import asset_path
import hashlib
import os
import subprocess
import sys
import unittest
from collections import defaultdict

from pkinv.core import air_factors
from pkinv.core.io import read_rows
from pkinv.paths import DATA, OUTPUTS

ROOT = os.path.join(os.path.dirname(__file__), "..")
DISTRICT = asset_path(DATA, "activity", "power", "grid_plant_district.csv")
MONTHLY = asset_path(DATA, "activity", "power", "grid_monthly_workbook.csv")
CROSSCHECK = asset_path(DATA, "activity", "power", "workbook_emissions_crosscheck.csv")
REGISTER = os.path.join(OUTPUTS, "pakemis_air_lahore_power_register.csv")
SULFUR = asset_path(DATA, "activity", "industry", "fuel_sulfur_evidence.csv")
REGISTERS = (
    asset_path(DATA, "air_emission_factors.csv"),
    asset_path(DATA, "air_source_classes.csv"),
    asset_path(DATA, "activity", "industry", "fuel_sulfur_evidence.csv"),
    asset_path(DATA, "power_params.csv"),
    asset_path(DATA, "physical_sources.csv"),
)


def _digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class TestTheIngestIsDeterministic(unittest.TestCase):
    def test_check_mode_says_the_files_are_current(self):
        done = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "ingest_power_plant_workbooks.py"),
             "--check"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_no_register_is_written_by_reading_a_workbook(self):
        before = {p: _digest(p) for p in REGISTERS}
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "build_lahore_power_register.py")],
                       check=True, capture_output=True)
        self.assertEqual({p: _digest(p) for p in REGISTERS}, before)


class TestTheYearConventionIsTheFiscalEndYear(unittest.TestCase):
    """Read the other way, every plant's history shifts a year and nothing else complains."""

    def test_the_workbook_year_matches_this_repositorys_own_monthly_sums(self):
        names = {r["panel_name"]: (r["canonical_plant"] or r["panel_name"])
                 for r in read_rows(asset_path(DATA, "activity", "power", "plant_name_crosswalk.csv"))}
        monthly, months = defaultdict(float), defaultdict(int)
        for r in read_rows(asset_path(DATA, "activity", "power", "generation_monthly.csv")):
            key = (names.get(r["plant"], r["plant"]), r["fiscal_year"])
            monthly[key] += float(r["gwh"] or 0)
            months[key] += 1
        agreed = 0
        for r in read_rows(DISTRICT):
            if not r["generation_gwh"]:
                continue
            key = (names.get(r["plant"], r["plant"]), r["fiscal_year"])
            if months.get(key) != 12:
                continue
            ours, theirs = monthly[key], float(r["generation_gwh"])
            if abs(ours - theirs) <= max(0.05, 0.001 * max(ours, 1.0)):
                agreed += 1
        self.assertGreaterEqual(agreed, 40,
                                "the fiscal-end-year reading should reproduce this repository's "
                                "own twelve-month sums on many plant-years; it reproduced %d"
                                % agreed)

    def test_every_fiscal_year_is_well_formed(self):
        for r in read_rows(DISTRICT):
            self.assertRegex(r["fiscal_year"], r"^FY\d{4}-\d{2}$", r)
            self.assertEqual(int(r["fiscal_end_year"]) - 1, int(r["fiscal_year"][2:6]), r)


class TestGeographyIsResolvedNotAssumed(unittest.TestCase):
    def test_every_placed_plant_carries_a_canonical_adm2_id(self):
        canonical = {r["adm2_id"] for r in read_rows(asset_path(DATA, "adm2_canonical.csv"))}
        rows = read_rows(DISTRICT)
        self.assertTrue(rows)
        for r in rows:
            self.assertTrue(r["district_printed"], r)
            self.assertIn(r["adm2_id"], canonical,
                          "a district spelling that resolves nowhere is a plant about to be "
                          "dropped from a spatial product without a trace: %s" % r)

    def test_the_placement_is_compared_against_what_this_repository_already_holds(self):
        rows = read_rows(DISTRICT)
        for r in rows:
            self.assertTrue(r["geography_agreement"].strip(), r)
        conflicts = [r for r in rows if r["geography_agreement"].startswith("CONFLICT")]
        self.assertFalse(conflicts,
                         "a workbook placement that contradicts plant_coordinates.csv must be "
                         "resolved, not shipped: %s" % conflicts[:3])

    def test_lahore_gains_the_stations_the_coordinate_ladder_left_unresolved(self):
        placed = {r["plant"] for r in read_rows(DISTRICT) if r["adm2_id"] == "punjab_lahore"}
        self.assertIn("Kohinoor Energy", placed)


class TestTheMonthlySheetsDefectIsTypedNotAbsorbed(unittest.TestCase):
    """One month cell holding the annual total, and short plant-years. Both are named."""

    def test_the_annual_in_a_month_defect_is_found_and_named(self):
        hit = [r for r in read_rows(MONTHLY) if "repeats the ANNUAL total" in r["reading"]]
        self.assertTrue(hit, "the defect exists in the sheet; the ingest must still see it")
        self.assertEqual({r["fiscal_year"] for r in hit}, {"FY2018-19"},
                         "the defect is systematic to one year; if that changes, look again")

    def test_every_row_carries_its_closure_against_the_annual_sheet(self):
        for r in read_rows(MONTHLY):
            self.assertTrue(r["months_present"], r)
            self.assertTrue(r["reading"].strip(), r)
            if r["annual_sheet_gwh"]:
                self.assertTrue(r["closure_residual_gwh"], r)


class TestTheWorkbookFactorsAreComparedNeverAdopted(unittest.TestCase):
    def test_every_crosscheck_row_says_it_is_not_the_estimate(self):
        rows = read_rows(CROSSCHECK)
        self.assertTrue(rows)
        for r in rows:
            self.assertTrue(r["reading"].strip(), r)
            self.assertTrue("never adopted" in r["reading"] or "NOT USABLE" in r["reading"], r)

    def test_the_unsourced_bagasse_placeholder_is_typed(self):
        bagasse = [r for r in read_rows(CROSSCHECK) if r["fuel"].upper() == "BAGASSE"]
        self.assertTrue(bagasse)
        for r in bagasse:
            self.assertIn("UNSOURCED PLACEHOLDER", r["reading"])


class TestTheNepraTablesKeyTheFiscalSTARTYear(unittest.TestCase):
    """The opposite convention to the workbooks', in the same sector, one directory apart.

    `grid_monthly_workbook.csv` labels a fiscal year by its END year - that is the class above.
    `plant_heat_rates.csv` and `plant_fuel_ledger.csv`, both transcribed from NEPRA's State of
    Industry Report, label it by its START year: `fiscal_year` 2019 is FY2019-20. Two files that
    disagree about what "2019" means, joined by a script that must pick one, is precisely the
    defect that shipped: `build_lahore_power_register.py` computed the end year and read every
    plant's heat rate twelve months early. It survived review because Kohinoor's published rate is
    identical in all five years, so Lahore never moved - and 31 of the 42 plants with a published
    rate DO vary, so a national build on that key would have mis-dated all of them silently.

    The convention is not asserted from a document's prose; it is measured. The ledger prints its
    own `net_generation_GWh`, and this repository independently holds twelve monthly rows per
    plant-year, so the two candidate readings can simply be raced against each other.
    """

    @classmethod
    def setUpClass(cls):
        names = {r["panel_name"]: (r["canonical_plant"] or r["panel_name"])
                 for r in read_rows(asset_path(DATA, "activity", "power", "plant_name_crosswalk.csv"))}
        cls.monthly, cls.months = defaultdict(float), defaultdict(int)
        for r in read_rows(asset_path(DATA, "activity", "power", "generation_monthly.csv")):
            key = (names.get(r["plant"], r["plant"]), r["fiscal_year"])
            cls.monthly[key] += float(r["gwh"] or 0)
            cls.months[key] += 1
        cls.ledger = defaultdict(float)
        for r in read_rows(asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")):
            if r["net_generation_GWh"]:
                cls.ledger[(names.get(r["plant"], r["plant"]), r["fiscal_year"])] += float(r["net_generation_GWh"])

    def _complete_year(self, plant, start):
        """The monthly sum for FY<start>-<start+1>, but only where all twelve months are held."""
        key = (plant, "FY%d-%02d" % (start, (start + 1) % 100))
        if key in self.monthly and self.months[key] == 12 and self.monthly[key] > 0:
            return self.monthly[key]
        return None

    def test_the_start_year_reading_is_closer_on_every_comparable_plant_year(self):
        """The head-to-head, which needs no tolerance to be decisive."""
        start_closer = end_closer = 0
        losers = []
        for (plant, year), gwh in self.ledger.items():
            start = int(year)
            as_start, as_end = self._complete_year(plant, start), self._complete_year(plant, start - 1)
            if as_start is None or as_end is None:
                continue
            if abs(gwh - as_start) < abs(gwh - as_end):
                start_closer += 1
            else:
                end_closer += 1
                losers.append((plant, year, gwh, as_start, as_end))
        self.assertGreaterEqual(start_closer + end_closer, 60,
                                "too few plant-years hold twelve months in BOTH candidate periods "
                                "for this comparison to decide anything")
        self.assertEqual(end_closer, 0,
                         "the fiscal END reading won on %d plant-years; the convention this "
                         "repository joins on is no longer one-sided: %s" % (end_closer, losers[:5]))

    def test_the_start_year_reading_reproduces_the_ledgers_own_generation(self):
        """And it does not merely win - it agrees, on 71 of the 78 years it can be checked against.

        The seven that do not are gross-versus-net residuals and first-year commissionings
        (Sapphire Electric 2020, Thar Coal Block-I 2022 and ThalNova 2022 among them), none of
        them a twelve-month displacement. Under the END reading the agreement count is ZERO of 72,
        which is what makes this evidence rather than a preference.
        """
        agreed = comparable = 0
        for (plant, year), gwh in self.ledger.items():
            as_start = self._complete_year(plant, int(year))
            if as_start is None:
                continue
            comparable += 1
            if abs(gwh - as_start) / as_start < 0.005:
                agreed += 1
        self.assertEqual((agreed, comparable), (71, 78),
                         "the ledger/monthly agreement moved; re-derive the convention before "
                         "changing this number, because the join depends on it")

    def test_the_register_reads_the_heat_rate_at_the_start_year(self):
        """The defect itself, pinned at the function that had it.

        A build would not fail if this regressed - it would price a plant on the following year's
        efficiency - so the key is asserted directly against a plant whose rate is known to vary.
        """
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        try:
            import build_lahore_power_register as reg
        finally:
            sys.path.pop(0)
        self.assertEqual(reg._start_year("FY2019-20"), 2019)
        self.assertEqual(reg._start_year("FY2023-24"), 2023)

        rates = reg.heat_rates()
        varying = defaultdict(set)
        for (plant, year), (rate, _basis) in rates.items():
            varying[plant].add(round(rate, 6))
        moves = sorted(p for p, v in varying.items() if len(v) > 1)
        self.assertGreaterEqual(len(moves), 25,
                                "the premise of this guard is that most plants' heat rates vary "
                                "between years; if they no longer do, the off-by-one stops being "
                                "silent and this test should be re-argued, not relaxed")


class TestTheRegisterSeparatesMeasurementFromAssumption(unittest.TestCase):
    def setUp(self):
        self.rows = read_rows(REGISTER)

    def test_an_absence_is_never_a_zero(self):
        for r in self.rows:
            if r["operating_status"] == "no generation record":
                self.assertEqual(r["generation_gwh"], "", r)
                self.assertEqual(r["so2_Gg"], "", r)

    def test_a_carried_heat_rate_says_it_was_not_published_for_that_year(self):
        for r in self.rows:
            if not r["heat_rate_basis"]:
                continue
            if "published for this year" not in r["heat_rate_basis"]:
                self.assertIn("DECLARED CONSTANT", r["heat_rate_basis"], r)

    def test_the_control_assumption_is_stated_on_every_priced_row(self):
        priced = [r for r in self.rows if r["so2_Gg"]]
        self.assertTrue(priced)
        for r in priced:
            self.assertEqual(r["control_type"], "none assumed")
            self.assertIn("ASSUMPTION", r["control_basis"])

    def test_the_sulfur_band_travels_with_the_central(self):
        for r in self.rows:
            if not r["so2_Gg"]:
                continue
            lo, mid, hi = float(r["so2_Gg_lo"]), float(r["so2_Gg"]), float(r["so2_Gg_hi"])
            self.assertLess(lo, mid)
            self.assertLess(mid, hi)

    def test_the_two_methods_agree_on_activity_and_part_on_the_factor(self):
        """The two methods run on the same activity; what separates them is measurable.

        This guard asserted agreement within a quarter while the register borrowed INDUSTRY's
        3.0 % regulatory maximum, and it passed for the wrong reason: the workbook's 12 kg/MWh
        literature factor was itself built on a ~3 % fuel, so two copies of one ceiling agreed
        with each other. The register now prices the power sector's own specification centre
        (1.3229 %), the ratio moved to ~0.44, and the old tolerance would have failed a change
        that improved the evidence.

        So the comparison is restated as what it can actually prove. Divide the workbook's
        emission by the register's fuel mass and by AP-42's per-%S factor, and what comes back
        is the sulfur content the workbook ASSUMED. If the two methods disagreed about activity
        - a different generation, a different heat rate, a unit slip - that number would be
        physically absurd. It is not: it lands at ~3.03 % on every year, inside the held
        specification band, and the ratio equals the sulfur ratio to four decimals. The methods
        agree on the plant and disagree, by a stated amount, about its fuel.
        """
        compared = [r for r in self.rows if r["ratio_engine_over_workbook"]]
        self.assertGreaterEqual(len(compared), 8)

        # What each method says per TONNE of the same fuel. The workbook publishes an emission
        # and this register publishes one; dividing both by the register's own fuel mass puts
        # them in the same unit without needing to unpick which sulfur or which retention each
        # of them assumed - a product this comparison cannot separate and should not pretend to.
        workbook, engine = [], []
        for r in compared:
            mass_t = float(r["fuel_mass_kt"]) * 1000.0
            workbook.append(float(r["workbook_so2_Gg"]) * 1e6 / mass_t)
            engine.append(float(r["so2_Gg"]) * 1e6 / mass_t)
            self.assertAlmostEqual(float(r["ratio_engine_over_workbook"]),
                                   engine[-1] / workbook[-1], places=4, msg=str(r))

        # THE ACTIVITY CHECK, and it found something. Both methods describe one station burning
        # one fuel under one fixed set of assumptions, so each per-tonne figure ought to be the
        # SAME NUMBER in every year, and this register's is - 26.5 kg/t to five decimals in all
        # nine. The workbook's is 57.53 in seven years and misses in exactly two, FY2016-17 high
        # at 59.06 and FY2017-18 low at 55.90.
        #
        # Those two are not noise and they are not a factor difference. The workbook's ANNUAL
        # sheet disagrees with this repository's twelve monthly rows about how much Kohinoor
        # generated: 816.83 GWh against 795.678 in FY2016-17 (+2.66 percent) and 644.56 against
        # 663.382 in FY2017-18 (-2.84 percent). Carry those through and 57.53 becomes 59.06 and
        # 55.90 precisely. So the cross-check is doing its job: it located a two-year activity
        # disagreement between two lanes of the same source, and the register uses the monthly
        # rows, which are the twelve observations rather than one printed total.
        engine_per_t = sorted(engine)
        # places=2 is the published precision, not a loose tolerance: so2_Gg is stored to four
        # decimals and fuel_mass_kt to three, so their quotient carries rounding noise in the
        # fifth figure. Anything a changed factor or sulfur could do is orders larger.
        self.assertAlmostEqual(engine_per_t[-1], engine_per_t[0], places=2,
                               msg="this register's own kg SO2 per tonne moves between years, "
                                   "which would mean its factor or its sulfur is not constant")
        agreed = [x for x in workbook if abs(x - 57.53) < 0.1]
        self.assertEqual(len(agreed), 7,
                         "seven of the nine years agree on the workbook's implied kg/t; a change "
                         "here means a third year's activity has diverged, or one of the two "
                         "known ones has been reconciled: %s"
                         % sorted(round(x, 2) for x in workbook))
        for value, expected_ratio in ((max(workbook), 816.83 / 795.678),
                                      (min(workbook), 644.56 / 663.382)):
            self.assertAlmostEqual(value / 57.53, expected_ratio, places=3,
                                   msg="the outlier no longer equals the generation ratio "
                                       "between the workbook's annual sheet and the monthly "
                                       "rows, so its explanation has stopped being true")

        # And the two constants themselves, so a silent change of factor or sulfur is visible.
        # 57.5 kg/t is the workbook's 12 kg/MWh carried through the heat rate. 60.0 kg/t is a
        # complete balance at 3.0 percent sulfur.
        #
        # THIS GUARD FIRED AT rc63 AND THE NUMBER IT CAUGHT IS A CORROBORATION, which is worth
        # recording because the guard was written expecting the opposite. It pinned 26.5 kg/t,
        # "a complete balance at the power sector's own 1.3229 percent specification centre" -
        # the unweighted geometric middle of a 0.5-3.5 span. Against that, the workbook's
        # independent 57.53 was 2.17 TIMES higher, a 117 percent disagreement nobody had
        # explained. rc63 retired the 1.3229 row: one national fuel cannot carry two centrals,
        # and the held import grade split (85.3-100 percent high-sulphur) put the pool near the
        # top of the span rather than its middle, so the power classes joined the industry row
        # at 3.0 percent.
        #
        # The workbook was never used to choose that value. Invert its 57.53 kg/t through the
        # same balance and it implies 2.877 percent sulfur - 4.1 percent below the adopted 3.0,
        # against 117 percent above the retired 1.3229. An independent method that disagreed by
        # a factor of two now agrees to within a twentieth. That is the strongest evidence in
        # the round that the merge chose the right row, and it arrived by a guard failing.
        self.assertAlmostEqual(sum(agreed) / len(agreed), 57.53, delta=0.05)
        self.assertAlmostEqual(sum(engine) / len(engine), 60.0, delta=0.5)
        # the agreement itself, pinned: if these two ever diverge again it is a finding
        implied_by_workbook = (sum(agreed) / len(agreed)) / 20.0
        self.assertAlmostEqual(implied_by_workbook, 2.877, places=3)
        self.assertLess(abs(implied_by_workbook / 3.0 - 1.0), 0.05,
                        "the workbook's independent factor has stopped corroborating the booked "
                        "furnace-oil sulfur; that is a finding about one of the two, not a "
                        "tolerance to widen")

    def test_this_table_is_a_diagnostic_and_the_panel_is_fed_from_elsewhere(self):
        """rc60 UNDID THE ABSENCE THIS GUARD PINNED, and the guard has to say what replaced it.

        It used to assert that power SO2 is typed NE in every period - true while this register
        was the only thing that had ever priced Lahore's power, and false now. What it was
        actually protecting is still worth protecting: THIS FILE is a diagnostic and does not
        feed the panel. The panel is fed by data/activity/power/power_so2_admission.csv, a
        reviewed national register that prices Lahore's plants on metered fuel where it exists,
        and this table remains the generation-route view beside it.

        So the assertion becomes: power SO2 is admitted, and this file is not how.
        """
        power = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_air_coverage_matrix.csv"))
                 if r.get("sector_id") == "power" and r.get("pollutant") == "SO2"]
        self.assertEqual(len(power), 9)
        for r in power:
            self.assertEqual(r["state"], "E", r)
            self.assertEqual(r["state_basis"], "panel-atom", r)
        classes = read_rows(asset_path(DATA, "air_source_classes.csv"))
        feeding = [c for c in classes if c["physical_source_id"] == "ps_grid_generation"]
        self.assertEqual(len(feeding), 4)
        for c in feeding:
            self.assertIn("power.admitted_fuel_kt:", c["activity_function"])
            self.assertNotIn("lahore", c["activity_function"].lower(),
                             "the panel must not be fed from a district diagnostic")


if __name__ == "__main__":
    unittest.main()
