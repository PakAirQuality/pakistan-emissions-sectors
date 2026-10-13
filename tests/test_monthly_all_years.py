"""The 108-month layer: does it close, does it cover, and does it overclaim?

Three properties matter, and only the first is arithmetic. The months must sum to the annual
row they came from, or the monthly product is a second inventory wearing the same name. They
must cover exactly the sector-years the annual product supports - no more, because a month
invented for an absent sector-year reads as an observation that something was emitted; no
fewer, because a silently dropped stream is mass that vanished between two published files.
And every row must declare what its timing is evidence OF, because the strong classes here
come from fuel sales and depot offtakes, not from watching anything emit.

Run:  python3 -m unittest discover tests -p "test_monthly_all_years.py"
"""
import collections
import csv
import os
import unittest

from pkinv.core import evidence, monthly as core_monthly
from pkinv.paths import DATA, OUTPUTS
from pkinv.report import monthly_all_years, months, temporal_profiles
from pkinv.core.io import read_rows


def _rows(name, base=OUTPUTS):
    return read_rows(os.path.join(base, name), comments=False)


class TestTheMonthRegistry(unittest.TestCase):
    def test_it_equals_what_core_monthly_computes(self):
        """The table materialises core/monthly.py, exactly as data/periods.csv does for
        core/period.py. If the two drift, every profile row's month key stops meaning what
        the code says it means."""
        table = _rows("months.csv", base=DATA)
        self.assertEqual(len(table), 108)
        from pkinv.report import periods
        expected = []
        for start_year in range(periods.FIRST_START_YEAR, periods.LAST_START_YEAR + 1):
            expected.extend(core_monthly.months_for(start_year))
        self.assertEqual([r["month_id"] for r in table], expected)

    def test_the_leap_februaries_are_a_day_longer(self):
        days = {r["month_id"]: int(r["days_in_month"]) for r in _rows("months.csv", base=DATA)}
        self.assertEqual(days["201602"], 29)
        self.assertEqual(days["202002"], 29)
        self.assertEqual(days["202402"], 29)
        self.assertEqual(days["201702"], 28)

    def test_the_disturbances_are_flagged_and_closed(self):
        table = _rows("months.csv", base=DATA)
        flags = {r["month_id"]: r["special_period_flag"] for r in table}
        self.assertEqual(flags["202004"], "covid_restrictions")
        self.assertEqual(flags["202208"], "floods_2022")
        self.assertEqual(flags["201907"], "")
        vocabulary = {f for _f, _l, f, _n in months.SPECIAL_PERIODS} | {""}
        self.assertEqual(set(flags.values()) - vocabulary, set())
        for row in table:
            self.assertEqual(bool(row["special_period_flag"]),
                             bool(row["special_period_note"]), row["month_id"])


class TestTheProfileRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_temporal_profiles.csv")

    def test_every_component_year_sums_to_one(self):
        """The only thing a profile may do. A registry whose weights summed to 1.02 would
        move 2 percent of a stream's annual mass into existence."""
        summed = collections.defaultdict(float)
        counted = collections.Counter()
        for row in self.rows:
            key = (row["component_id"], row["fiscal_year"])
            summed[key] += float(row["weight"])
            counted[key] += 1
        for key, total in summed.items():
            self.assertAlmostEqual(total, 1.0, places=9, msg=str(key))
            self.assertEqual(counted[key], 12, key)

    def test_the_vocabularies_are_closed(self):
        for row in self.rows:
            self.assertIn(row["temporal_evidence_class"], evidence.TEMPORAL_EVIDENCE)
            self.assertIn(row["timing_target"], evidence.TIMING_TARGET)
            self.assertIn(row["temporal_status"], evidence.TEMPORAL_STATUS)

    def test_a_strong_class_never_claims_the_emitting_process_it_does_not_watch(self):
        """The anti-conflation rule. OCAC times fuel SALES and NFDC times urea leaving a
        depot; a TE1 or TE2 row claiming `emitting_process` would be asserting that the
        inventory watched combustion or soil chemistry, which it did not."""
        for row in self.rows:
            if row["temporal_evidence_class"] in ("TE1", "TE2"):
                self.assertIn(row["timing_target"],
                              ("fuel_sale", "commodity_offtake", "production"),
                              "%s claims %s from %s" % (row["component_id"],
                                                        row["timing_target"],
                                                        row["source_id"]))

    def test_nothing_is_borrowed_except_what_declares_it(self):
        """The pass's standing decision: no year wears another year's shape unless the row
        says whose - and as of the QIM ingest, NO year wears another's at all.

        Cement was the one borrowing, held at TE4 for exactly that reason. All nine fiscal
        editions of PBS Table 2 are now parsed, so every year takes its own months and the
        borrowing is gone rather than merely relabelled.

        The CONDITIONAL is what this test protects and it is kept live: whatever borrows in
        future must still declare its year and grade itself TE4. The unconditional half is
        inverted rather than deleted - an empty set is the claim now, and a row appearing
        without a declared year would fail here just as loudly.
        """
        for row in self.rows:
            if row["borrowed_from_year"]:
                self.assertEqual(row["temporal_evidence_class"], "TE4",
                                 "%s borrows from %s and is graded above TE4"
                                 % (row["component_id"], row["borrowed_from_year"]))
        borrowed = {r["sector"] for r in self.rows if r["borrowed_from_year"]}
        self.assertEqual(borrowed, set(),
                         "a sector is borrowing a shape from another year again: %s"
                         % sorted(borrowed))

    def test_the_years_without_a_petroleum_panel_carry_no_OCAC_months(self):
        """The OCAC panel begins in July 2021, and the six years before it must not have
        acquired months FROM IT.

        This used to assert those years carried no observed months from anywhere, which was
        a stronger claim than the evidence supported and one that only held while OCAC was
        the sole monthly source: PBS's plant-month generation reaches FY2015-16 to FY2020-21
        and the assertion made it a test failure rather than a finding. The panel's own
        boundary is still checked, by name.
        """
        for row in self.rows:
            if row["fiscal_year"] >= "FY2021-22":
                continue
            if "ocac" in row["source_id"].lower():
                self.fail("%s %s carries an OCAC profile before the panel opens"
                          % (row["fiscal_year"], row["component_id"]))
            if row["temporal_evidence_class"] != "TE4":
                self.assertTrue(row["source_id"].strip(),
                                "%s %s is graded above TE4 and names no source"
                                % (row["fiscal_year"], row["component_id"]))


class TestEveryLayerServesEveryYearItself(unittest.TestCase):
    """One absent source must never take a sector's other sources down with it.

    The profile builder used to wrap each layer in a bare `except Exception`, on the
    reasoning that a missing panel, an absent annex and an unreadable edition all mean the
    same thing - no monthly evidence for this sector-year. They do not, and the cost was
    measurable twice. Power's PBS plant-month generation was discarded for the years OCAC
    cannot serve, until the OCAC call was asked rather than allowed to raise. Agriculture's
    rice profile is a CROP CALENDAR that reads no fertiliser data at all, and it was thrown
    away with the fertiliser annex for eight of the nine years - three percent of the national
    inventory left flat by an exception handler.

    Every layer now declares its own absences, so the handler is gone. These tests are what
    keeps it gone.
    """

    SECTORS = ("agriculture", "ippu", "industry", "transport", "railways", "aviation",
               "residential", "waste", "fugitives", "power")

    def test_no_layer_raises_for_any_year_in_the_window(self):
        from pkinv.core import registry
        from pkinv.report import periods
        for sector in self.SECTORS:
            for fy_start in range(periods.FIRST_START_YEAR, periods.LAST_START_YEAR + 1):
                try:
                    _components, rows = registry.monthly_layer(sector).rows(fy_start=fy_start)
                except Exception as error:                        # noqa: BLE001 - reported
                    self.fail("%s raised for FY%d: %s: %s"
                              % (sector, fy_start, type(error).__name__, error))
                self.assertTrue(rows, "%s returned no months for FY%d" % (sector, fy_start))

    def test_the_sector_a_calendar_serves_is_shaped_in_every_year(self):
        """Rice methane is produced while the paddy is flooded and essentially not otherwise.
        The flooded window comes from a provincial crop calendar, which carries no year - so
        there is no year it cannot shape, and no year it should be missing from."""
        rows = _rows("pakemis_temporal_profiles.csv")
        years = {r["fiscal_year"] for r in rows
                 if r["sector"] == "agriculture" and r["category"].startswith("Rice")
                 and r["temporal_evidence_class"] != "TE4"}
        self.assertEqual(len(years), 9, "rice carries a flooded window in only %d years"
                                        % len(years))

    def test_no_year_borrows_a_fertiliser_shape_it_has_no_edition_for(self):
        """The other half of the same decision. A crop calendar has no year and travels; one
        year's offtake is that year's, and carrying it would be what the borrowing cement's
        QIM profile was graded TE4 for.

        THE INVARIANT, NOT THE YEAR LIST. This used to assert the observed shape appeared in
        FY2023-24 alone, which was true when Annex-7 was the only edition held. NFDC Table 3.4
        now supplies FY2015-16..FY2022-23, so eight more years carry an observed shape and
        none of them borrows it. Pinning the literal year set would have failed on a year
        acquiring its OWN edition - the opposite of what this guards - so the test asks the
        readers directly whether an edition exists for each year that claims one.
        """
        from pkinv.sectors.agriculture import monthly as agri_monthly, nfdc_monthly
        rows = _rows("pakemis_temporal_profiles.csv")
        soils = [r for r in rows
                 if r["sector"] == "agriculture" and r["category"].startswith("Managed soils")
                 and r["temporal_evidence_class"] in ("TE1", "TE2")]
        self.assertTrue(soils)
        for year in sorted({r["fiscal_year"] for r in soils}):
            fy_start = int(year[2:6])
            self.assertTrue(
                nfdc_monthly.covers(fy_start) or agri_monthly.annex7_covers(fy_start),
                "%s carries an observed fertiliser shape with no edition behind it" % year)


class TestTheMonthlyProductCloses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_monthly_fy2015_16_fy2023_24.csv")
        cls.atom = [r for r in _rows("pakemis_atomic_annual.csv") if r["co2e_Mt_AR5"]]

    def test_it_closes_on_native_mass_and_on_co2e(self):
        native = collections.defaultdict(float)
        co2e = collections.defaultdict(float)
        for row in self.rows:
            key = (row["component_id"], row["period_id"])
            if row["emission_native_mass"]:
                native[key] += float(row["emission_native_mass"])
            co2e[key] += float(row["co2e_Mt_AR5"])
        for component in self.atom:
            key = (component["component_id"], component["period_id"])
            self.assertAlmostEqual(co2e[key], float(component["co2e_Mt_AR5"]),
                                   places=9, msg=str(key))
            if component["emission_native_mass"]:
                self.assertAlmostEqual(native[key],
                                       float(component["emission_native_mass"]),
                                       places=6, msg=str(key))

    def test_it_covers_exactly_the_live_annual_rows(self):
        """No month for an absent sector-year, and no annual row without months. Twelve
        zeros for a year the inventory does not estimate would read as an observation that
        nothing was emitted."""
        monthly = {(r["component_id"], r["period_id"]) for r in self.rows}
        annual = {(r["component_id"], r["period_id"]) for r in self.atom}
        self.assertEqual(monthly, annual)

    def test_all_108_months_are_present(self):
        self.assertEqual(len({r["month"] for r in self.rows}), 108)
        by_year = collections.defaultdict(set)
        for row in self.rows:
            by_year[row["period_id"]].add(row["month"])
        for year, seen in by_year.items():
            self.assertEqual(len(seen), 12, year)

    def test_the_absent_sector_years_have_no_months(self):
        """Vacuously true since rc20 closed the last absence; kept armed for the
        next partial year (the invariant, not today's count, is the contract)."""
        absent = {(r["sector_id"], r["period_id"]) for r in _rows("pakemis_atomic_annual.csv")
                  if r["estimate_status"] == "absent"}
        present = {(r["sector_id"], r["period_id"]) for r in self.rows}
        self.assertEqual(absent & present, set())

    def test_the_closure_basis_is_declared_per_row(self):
        for row in self.rows:
            self.assertIn(row["closure_basis"], ("native_mass", "co2e_AR5"))
            self.assertEqual(row["closure_basis"] == "co2e_AR5",
                             row["emission_native_mass"] == "")
        # The co2e_AR5 closure existed for ONE reason: agriculture's coarse history carried no
        # native mass to close on. Those rows now carry their components' own gas masses, so
        # every row in the product closes on native mass and nothing needs the fallback. The
        # rule above - co2e_AR5 if and only if native mass is absent - is what still holds it.
        coarse = {r["sector_id"] for r in self.rows if r["closure_basis"] == "co2e_AR5"}
        self.assertEqual(coarse, set(),
                         "a sector is closing on CO2e again because it has no native mass: %s"
                         % sorted(coarse))


class TestDaysWeightingIsRealAndDeclared(unittest.TestCase):
    def test_an_unshaped_month_is_its_own_length(self):
        """The change this pass made to every flat profile. February must be shorter than
        July, in the data and not only in the docstring."""
        rows = [r for r in _rows("pakemis_monthly_fy2015_16_fy2023_24.csv")
                if r["profile_id"] == "days_weighted" and r["period_id"] == "FY2023-24"]
        self.assertTrue(rows)
        shares = {r["month"]: float(r["share"]) for r in rows}
        self.assertGreater(shares["202307"], shares["202402"])
        expected = core_monthly.days_weighted_profile(2023)
        for month, share in shares.items():
            self.assertAlmostEqual(share, expected[month], places=12, msg=month)

    def test_the_leap_day_reaches_the_product(self):
        """FY2015-16 and FY2019-20 contain a 29-day February, and it must be worth more
        than the 28-day ones."""
        rows = [r for r in _rows("pakemis_monthly_fy2015_16_fy2023_24.csv")
                if r["profile_id"] == "days_weighted"]
        by_month = {r["month"]: float(r["share"]) for r in rows}
        self.assertGreater(by_month["201602"], by_month["201702"])


class TestAWeakProfileIsAlwaysGradedAsOne(unittest.TestCase):
    """The rule that keeps the class column meaningful: a shape carrying no information
    about the source must SAY so, and a shape carrying some must not be filed as if it
    carried none."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_monthly_fy2015_16_fy2023_24.csv")

    def test_every_calendar_only_profile_is_graded_TE4(self):
        days = [r for r in self.rows if r["profile_id"] == "days_weighted"]
        self.assertTrue(days)
        self.assertEqual({r["temporal_evidence_class"] for r in days}, {"TE4"})
        # and it must say what it is timing, even when the answer is "nothing in particular"
        self.assertTrue({r["timing_target"] for r in days}
                        <= {"proxy_only", "stock_exposure"})

    def test_every_borrowed_profile_is_graded_TE4_and_names_its_year(self):
        """Nothing borrows now - so the live check is on the DERIVATION, not the column.

        This used to assert that borrowed rows existed, which kept the rule exercised. With
        cement on its own nine years the column is empty, and an empty column has two very
        different causes: nothing borrows, or the thing that fills the column broke. Only the
        second is a defect, and they are indistinguishable from the output alone.

        So the mechanism is tested directly, in both directions, against the basis strings the
        layers actually write. If that derivation ever stops recognising a borrowed shape, this
        fails here rather than shipping TE2 over a shape lifted from another year.
        """
        from pkinv.report import temporal_profiles
        from pkinv.sectors.ippu import monthly as ippu_monthly

        self.assertEqual("2022", temporal_profiles.borrowed_year(
            {ippu_monthly.BORROWED_BASIS}),
            "the borrowed-shape basis is no longer recognised as borrowed")
        self.assertEqual("", temporal_profiles.borrowed_year(
            {ippu_monthly.OWN_YEAR_BASIS}),
            "an own-year basis is being read as borrowed")

        borrowed = [r for r in self.rows if r["borrowed_from_year"]]
        self.assertEqual([], borrowed,
                         "%d rows borrow a shape from another year" % len(borrowed))

    def test_a_graded_profile_is_never_the_calendar_in_disguise(self):
        """A TE1/TE2/TE3 row must differ from the days-weighted shape for its year -
        otherwise the grade claims evidence that left no trace in the numbers."""
        from pkinv.core import monthly as core_monthly
        from pkinv.report import periods
        starts = {r["period_id"]: int(r["fiscal_start_year"]) for r in periods.rows()}
        graded = collections.defaultdict(dict)
        for row in self.rows:
            if row["temporal_evidence_class"] != "TE4":
                graded[(row["component_id"], row["period_id"])][row["month"]] = \
                    float(row["share"])
        self.assertTrue(graded)
        for (component, period_id), shares in graded.items():
            days = core_monthly.days_weighted_profile(starts[period_id])
            identical = all(abs(shares[m] - days[m]) < 1e-12 for m in shares)
            self.assertFalse(identical,
                             "%s in %s is graded above TE4 and is exactly the calendar"
                             % (component, period_id))

    def test_no_evidence_graded_row_is_suppressed_by_a_missing_observation(self):
        """A year with no monthly series still publishes twelve graded rows per component.
        Absence of observation reduces the CLASS; it never removes the row."""
        atom = [r for r in _rows("pakemis_atomic_annual.csv") if r["co2e_Mt_AR5"]]
        live = {(r["component_id"], r["period_id"]) for r in atom}
        published = {(r["component_id"], r["period_id"]) for r in self.rows}
        self.assertEqual(live - published, set())
        earliest = [r for r in self.rows if r["period_id"] == "FY2015-16"]
        self.assertTrue(earliest)
        self.assertEqual(len({r["month"] for r in earliest}), 12)


class TestItAgreesWithTheShippedReferenceYear(unittest.TestCase):
    """The compatibility bargain: a second product may not be a second vintage."""

    def test_the_reference_year_shares_reproduce_the_shipped_layer(self):
        shipped = collections.defaultdict(dict)
        for row in _rows("national_monthly_2024.csv"):
            key = (row["sector"], row["category"], row["subitem"], row["gas"])
            shipped[key][row["month"]] = float(row["share"])
        fresh = collections.defaultdict(dict)
        for row in _rows("pakemis_monthly_fy2015_16_fy2023_24.csv"):
            if row["period_id"] != "FY2023-24":
                continue
            key = (row["sector_id"], row["category"], row["subitem"], row["gas"])
            fresh[key][row["month"]] = float(row["share"])
        self.assertEqual(set(shipped), set(fresh))
        for key, months_ in shipped.items():
            for month, share in months_.items():
                # places=8: the shipped layer rounds its share column, and this is a
                # test of agreement rather than of float formatting.
                self.assertAlmostEqual(fresh[key][month], share, places=8,
                                       msg="%s %s" % (key, month))

    def test_the_nine_year_product_agrees_with_the_shipped_reference_year(self):
        """No stream may disagree with the reference year the release already shipped.

        This previously allowed exactly one exception - cement moving T3 to T4 - because the
        nine-year product graded a borrowed shape more honestly than the reference layer did.
        Both now read the same nine fiscal QIM editions, cement is T2 in both, and the
        exception is gone. The set is empty, which is a stronger statement than the one it
        replaces: the two products describe the same months the same way, everywhere.
        """
        shipped = {}
        for row in _rows("national_monthly_2024.csv"):
            shipped[(row["sector"], row["category"], row["subitem"], row["gas"],
                     row["month"])] = row["temporal_method"]
        moved = collections.Counter()
        for row in _rows("pakemis_monthly_fy2015_16_fy2023_24.csv"):
            if row["period_id"] != "FY2023-24":
                continue
            key = (row["sector_id"], row["category"], row["subitem"], row["gas"],
                   row["month"])
            was = shipped[key]
            now = evidence.TEMPORAL_FROM_EVIDENCE[row["temporal_evidence_class"]]
            if was != now:
                moved[(row["sector_id"], was, now)] += 1
        self.assertEqual(set(moved), set(), dict(moved))


class TestTheDecompositionSeparatesPhysicsFromIgnorance(unittest.TestCase):
    """An eighty-five percent TE4 share is uninformative. This is the number that is not."""

    @classmethod
    def setUpClass(cls):
        from pkinv.report import temporal_decomposition
        cls.module = temporal_decomposition
        cls.rows = _rows("pakemis_temporal_decomposition.csv")

    def test_every_component_carries_a_physical_verdict(self):
        for row in self.rows:
            self.assertIn(row["flatness_class"], self.module.PHYSICS_CLASSES, row["component"])
            self.assertIn(row["flatness_physically_appropriate"], ("yes", "no"))
            self.assertTrue(row["expected_temporal_driver"].strip())
            self.assertTrue(row["basis"].strip())

    def test_a_component_is_never_declared_observed_or_unobserved(self):
        """The two coverage classes are MEASURED, and this is the guard on that.

        They used to be written into the physics table, which meant the headline could not
        move when a monthly series arrived: PBS's plant-month generation carried three of
        power's nine years and the published gap did not change by a thousandth, because it
        was quoting a declaration. Physics is declared; coverage is read off the product.
        """
        for row in self.rows:
            self.assertNotIn(row["flatness_class"],
                             (self.module.OBSERVED, self.module.UNOBSERVED),
                             "%s carries a coverage verdict in its PHYSICS column"
                             % row["component"])

    def test_nothing_is_unassigned(self):
        """An unclassified component cannot be defended as correctly flat, so leaving one
        unassigned is itself the finding the table reports."""
        stray = [r["component"] for r in self.rows
                 if r["expected_temporal_driver"] == "unassigned"]
        self.assertFalse(stray, "no physical basis recorded for: %s" % stray)

    def test_the_two_flat_classes_disagree_about_what_flat_means(self):
        """The whole point: `continuous_by_process` says flat is right, and `time_variable`
        says flat is a gap. If every row answered the same way the axis would carry no
        information."""
        verdicts = {r["flatness_class"]: r["flatness_physically_appropriate"]
                    for r in self.rows}
        self.assertEqual(verdicts.get(self.module.CONTINUOUS), "yes")
        self.assertEqual(verdicts.get(self.module.TIME_VARIABLE), "no")
        self.assertGreaterEqual(len({r["flatness_class"] for r in self.rows}), 3)

    def test_the_shares_are_computed_and_sum(self):
        total = sum(float(r["share_of_national_pct"]) for r in self.rows)
        self.assertAlmostEqual(total, 100.0, places=1)

    def test_the_split_of_every_time_variable_component_is_exhaustive(self):
        """Observed plus unobserved is the component's whole mass, and a physically flat
        component has neither - it is aseasonal, not unmeasured."""
        for row in self.rows:
            observed = float(row["observed_Mt_AR5"])
            unobserved = float(row["unobserved_Mt_AR5"])
            if row["flatness_class"] == self.module.TIME_VARIABLE:
                self.assertAlmostEqual(observed + unobserved, float(row["co2e_Mt_AR5"]),
                                       places=3, msg=row["component"])
            else:
                self.assertEqual((observed, unobserved), (0.0, 0.0), row["component"])

    def test_the_gap_is_the_TE4_mass_of_the_time_variable_components(self):
        """Recomputed from the monthly product itself rather than from this table, because
        the whole value of the split is that it is a measurement."""
        rows = _rows("pakemis_monthly_fy2015_16_fy2023_24.csv")
        physical = {(r["sector_id"], r["component"]) for r in self.rows
                    if r["flatness_class"] != self.module.TIME_VARIABLE}
        expected = sum(
            float(r["co2e_Mt_AR5"]) for r in rows
            if r["temporal_evidence_class"] == "TE4"
            and (r["sector_id"], self.module.grain_of(r)) not in physical)
        published = sum(float(r["unobserved_Mt_AR5"]) for r in self.rows)
        self.assertAlmostEqual(expected, published, places=2)

    def test_the_gap_is_smaller_than_the_TE4_share_and_says_so(self):
        """The decomposition must not be a way of making TE4 look smaller - but it should
        show that most flat mass is correctly flat. Both halves are asserted."""
        total = sum(float(r["co2e_Mt_AR5"]) for r in self.rows)
        gap = 100.0 * sum(float(r["unobserved_Mt_AR5"]) for r in self.rows) / total
        physical = sum(float(r["share_of_national_pct"]) for r in self.rows
                       if r["flatness_physically_appropriate"] == "yes")
        self.assertLess(gap, 84.3, "the gap cannot exceed the TE4 share it decomposes")
        self.assertGreater(physical, gap,
                           "most flat mass should be flat for a physical reason; if not, "
                           "the monthly product is weaker than the class shares suggest")


if __name__ == "__main__":
    unittest.main()
