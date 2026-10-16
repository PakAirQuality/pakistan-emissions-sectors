"""The spatial weight registry: it must describe the build, not the intention.

WHY THESE TESTS ARE SHAPED THIS WAY. The registry exists because a spatial product that carries
nine years cannot be read honestly without knowing, per row, which year's evidence placed it.
The failure it guards against is not a wrong number - every closure identity holds either way -
but a FLATTERING BADGE: a stream-year credited with the year's own evidence when the build
borrowed a pattern or substituted a raster. So most of what follows compares the registry
against the record of what the build did, never against what a stream declares.
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import unittest

from pkinv.paths import DATA, OUTPUTS

# The vocabulary answers one question - does the evidence behind this surface have a time axis
# the engine reads for this period? - and the three values it replaced answered a different one.
# `direct_activity`, `administrative_activity` and `dynamic_proxy` were a pure function of
# `within_province_placement`, a column already in the same row, and the last of them was
# applied to streams riding a 2021 raster snapshot in FY2023-24. `interpolated_between_anchors`
# and `nearest_vintage` are deliberately absent: no code path emits them, and an unemittable
# value in a closed enum makes this test pass vacuously.
BASES = ("annual_observed_activity", "modelled_population_proxy", "calendar_activity_proxy", "reference_shape_forward", "static_structural",
         "reference_shape_backcast", "substituted_surface", "unallocated",
         "not_present")


def rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


class TestTheRegistryIsComplete(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.reg = rows(os.path.join(OUTPUTS, "pakemis_spatial_weights_by_year.csv"))
        cls.periods = [r["period_id"] for r in rows(asset_path(DATA, "periods.csv"))]
        cls.ledger = rows(os.path.join(OUTPUTS, "pakemis_source_streams.csv"))

    def test_every_stream_period_appears_exactly_once(self):
        keys = collections.Counter((r["source_stream_id"], r["period_id"]) for r in self.reg)
        self.assertEqual(len(self.reg), len(self.ledger) * len(self.periods))
        self.assertEqual(max(keys.values()), 1, "a stream-period is described twice")
        self.assertEqual(
            {r["source_stream_id"] for r in self.reg},
            {r["source_stream_id"] for r in self.ledger},
            "the registry and the stream ledger disagree about what exists")

    def test_the_basis_vocabulary_is_closed(self):
        for row in self.reg:
            self.assertIn(row["spatial_time_basis"], BASES, row["source_stream_id"])

    def test_a_borrowed_row_names_the_period_it_borrowed_from_and_no_other_row_does(self):
        for row in self.reg:
            if row["spatial_time_basis"] in ("reference_shape_backcast", "reference_shape_forward"):
                self.assertTrue(row["borrowed_from_period"], row["source_stream_id"])
                self.assertNotEqual(row["borrowed_from_period"], row["period_id"],
                                    row["source_stream_id"])
            else:
                self.assertEqual(row["borrowed_from_period"], "",
                                 "%s claims a borrow it did not make" % row["source_stream_id"])

    def test_unallocated_is_exactly_the_streams_with_no_native_geometry_in_every_year(self):
        s4 = {r["source_stream_id"] for r in self.ledger
              if r["geometry_id"] == "S4:no-native-geometry"}
        self.assertTrue(s4)
        for period in self.periods:
            got = {r["source_stream_id"] for r in self.reg
                   if r["period_id"] == period
                   and r["spatial_time_basis"] in ("unallocated", "not_present")}
            self.assertEqual(got & s4, s4, period)

    def test_allowed_geographies_matches_the_membership_it_names(self):
        from pkinv.core.geography import members_of
        for row in self.reg:
            want = "|".join(members_of(row["other_membership"]))
            self.assertEqual(row["allowed_geographies"], want, row["source_stream_id"])


class TestTheRegistryDescribesTheBuild(unittest.TestCase):
    """The half that matters: every judgement traced to the record, not the declaration."""

    @classmethod
    def setUpClass(cls):
        cls.reg = rows(os.path.join(OUTPUTS, "pakemis_spatial_weights_by_year.csv"))
        cls.fallbacks = rows(os.path.join(OUTPUTS,
                                          "pakemis_grid_fallbacks_by_year.csv"))

    def test_the_substituted_share_is_the_emitted_record_and_not_an_estimate(self):
        want = collections.defaultdict(float)
        for row in self.fallbacks:
            want[(row["source_stream_id"], row["period_id"])] += float(row["weight_share"])
        for row in self.reg:
            key = (row["source_stream_id"], row["period_id"])
            self.assertAlmostEqual(float(row["substituted_share"]),
                                   min(1.0, want.get(key, 0.0)), places=6, msg=str(key))

    def test_a_mostly_substituted_stream_year_cannot_claim_the_year_s_own_evidence(self):
        """The flattering badge this registry exists to prevent."""
        for row in self.reg:
            if float(row["substituted_share"]) > 0.5:
                self.assertEqual(row["spatial_time_basis"], "substituted_surface",
                                 "%s %s" % (row["source_stream_id"], row["period_id"]))

    def test_grid_power_before_the_ledger_rides_its_own_panel_pool(self):
        """Rewritten at rc46 Wave 1 - the case that produced the rule got a better answer.

        The plant fuel ledger holds FY2019-20 onward. Until Wave 1 the four years before it
        had no per-plant evidence at all and were graded substituted_surface wholesale; they
        now draw a per-station pool from the generation panel through the name crosswalk, so
        the grading is NON-UNIFORM and honestly so: fuels the panel labels (coal, gas, RFO)
        are annual_observed_activity on their own year's pool, and fuels it leaves blank in
        those years (diesel) stay substituted_surface at share 1.0 - an empty pool is still
        an absence, and it is still declared.
        """
        # The panel's fuel labelling differs by layout year: HSD rows exist from FY2018-19,
        # so diesel is panel-evidenced there and empty-pool substituted in the three years
        # before. The set of fully substituted rows is asserted EXACTLY - anything joining
        # it means a pool went empty, anything leaving it means evidence appeared and the
        # grading should say so.
        fully_substituted = set()
        for period in ("FY2015-16", "FY2016-17", "FY2017-18", "FY2018-19"):
            graded = [r for r in self.reg
                      if r["period_id"] == period
                      and r["surface"] == "grid_station_points+builtup_fallback"
                      and r["spatial_time_basis"] != "not_present"]
            self.assertTrue(graded, period)
            for row in graded:
                if row["spatial_time_basis"] == "substituted_surface":
                    self.assertEqual(float(row["substituted_share"]), 1.0,
                                     row["source_stream_id"])
                    fully_substituted.add((period, row["source_stream_id"]))
                else:
                    self.assertEqual(row["spatial_time_basis"], "annual_observed_activity",
                                     "%s %s: the panel pool stopped resolving this fuel"
                                     % (row["source_stream_id"], period))
        expected = {(p, "power|electricity-and-heat-production|diesel-oil-%s|%s" % (g, g))
                    for p in ("FY2015-16", "FY2016-17", "FY2017-18")
                    for g in ("ch4", "co2", "n2o")}
        self.assertEqual(fully_substituted, expected,
                         "the empty-pool set moved: the panel's fuel labelling changed")
        # FROM FY2019-20 THE LEDGER EXISTS, and after Wave 1's seventeen coordinates the
        # substituted share is small everywhere: coal under 0.05 as before, gas now 0.03-0.13
        # where it ran 0.43-0.51. The floor is asserted alongside the ceiling because a zero
        # would mean the fallback pricing stopped, not that Nooriabad found a coordinate.
        for period in ("FY2019-20", "FY2020-21", "FY2021-22", "FY2022-23", "FY2023-24"):
            graded = {r["source_stream_id"]: r for r in self.reg
                      if r["period_id"] == period
                      and r["surface"] == "grid_station_points+builtup_fallback"
                      and r["spatial_time_basis"] != "not_present"
                      and "bagasse" not in r["source_stream_id"]}
            self.assertTrue(graded, period)
            coal = [r for k, r in graded.items() if "coal" in k]
            gas = [r for k, r in graded.items() if "|gas-" in k]
            self.assertTrue(coal and gas, period)
            for row in coal:
                self.assertEqual(row["spatial_time_basis"], "annual_observed_activity",
                                 "%s %s: every coal station is located"
                                 % (row["source_stream_id"], period))
                self.assertLess(float(row["substituted_share"]), 0.05, row["source_stream_id"])
            for row in gas:
                self.assertEqual(row["spatial_time_basis"], "annual_observed_activity",
                                 row["source_stream_id"])
                self.assertLess(float(row["substituted_share"]), 0.15,
                                "%s %s: an rc46 gas coordinate was lost"
                                % (row["source_stream_id"], period))
                self.assertGreater(float(row["substituted_share"]), 0.0,
                                   row["source_stream_id"])

    def test_every_row_publishes_the_share_the_badge_summarises(self):
        """Because the badge is a threshold on a continuum, the continuum must be on the row.
        Gas crosses SUBSTITUTION_MAJORITY in one of five ledger years and sits just under it in
        the other four; a consumer reading only `spatial_time_basis` would see a categorical
        change where the underlying coverage moved three points."""
        for row in self.reg:
            self.assertNotEqual(row["substituted_share"], "", row["source_stream_id"])
            value = float(row["substituted_share"])
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_bagasse_is_substituted_in_every_year_including_the_reference(self):
        """Not a nine-year problem but a permanent one, and worth a row of its own: the
        bagasse profile has no fuel class in the plant ledger, so its geography is the
        built-up raster in the reference year too."""
        bagasse = [r for r in self.reg if "bagasse" in r["source_stream_id"]
                   and r["spatial_time_basis"] != "not_present"]
        self.assertTrue(bagasse)
        for row in bagasse:
            self.assertEqual(row["spatial_time_basis"], "substituted_surface",
                             "%s %s" % (row["source_stream_id"], row["period_id"]))

    # NON-CLAIMS. The four values this guard skips are the ones that assert no year-specific
    # evidence; static_structural joined them on 2026-10-05. The docstring below used to read
    # "everything else is a backcast", which was a true description of the build and not of
    # the vocabulary: a surface with no time axis in any period is static_structural in every
    # period, and that is a WEAKER claim than annual_observed_activity, not a stronger one.
    # What this guard exists to catch - annual_observed_activity on a period the engine does
    # not key - is still caught exactly, because that value is in neither list.
    NOT_A_YEAR_EVIDENCE_CLAIM = ("reference_shape_backcast", "reference_shape_forward", "modelled_population_proxy", "calendar_activity_proxy", "static_structural",
                                 "unallocated", "substituted_surface", "not_present")

    def test_no_year_but_the_reference_claims_evidence_the_engine_does_not_read(self):
        """A surface may be graded with the year's own evidence only where the engine actually
        keys that surface to the period. Claiming otherwise would credit evidence that was
        never opened."""
        from pkinv.report.spatial_weights import YEAR_KEYED
        for row in self.reg:
            if row["period_id"] == "FY2023-24":
                continue
            if row["spatial_time_basis"] in self.NOT_A_YEAR_EVIDENCE_CLAIM:
                continue
            allowed = YEAR_KEYED.get((row["surface"], row["district_panel"]), ())
            self.assertTrue(allowed is None or row["period_id"] in allowed,
                            "%s in %s claims %s on (%r, %r), which the engine does not key "
                            "to the period" % (row["source_stream_id"], row["period_id"],
                                               row["spatial_time_basis"], row["surface"],
                                               row["district_panel"]))

    def test_a_surface_with_no_time_axis_is_timeless_in_every_period(self):
        """The repair of 2026-10-05, held so it cannot quietly revert.

        A surface absent from YEAR_KEYED is keyed for no period at all. It is therefore a
        timeless surface in every period, which is what this module's vocabulary note says
        static_structural means - "in any period including the reference". The build applied
        that only to the reference year, so 62 streams read static_structural in FY2023-24 and
        reference_shape_backcast in the eight others while their pattern_hash was IDENTICAL
        across all nine: nothing was backcast, because there was no time-specific pattern to
        backcast from. 499 stream-years carried the wrong label, and anyone counting "rests on
        a borrowed shape" by period counted every one of them in every year but the reference.
        """
        from pkinv.report.spatial_weights import YEAR_KEYED
        wrong, checked = [], 0
        for row in self.reg:
            if row["spatial_time_basis"] in ("not_present", "unallocated",
                                             "substituted_surface"):
                continue
            allowed = YEAR_KEYED.get((row["surface"], row["district_panel"]), ())
            if allowed is None or allowed:          # has a time axis in some period
                continue
            checked += 1
            if row["spatial_time_basis"] != "static_structural":
                wrong.append("%s %s: %s" % (row["source_stream_id"], row["period_id"],
                                            row["spatial_time_basis"]))
        self.assertTrue(checked, "no never-keyed surface rows: this guard checked nothing")
        self.assertFalse(wrong, "a surface with no time axis in ANY period is not timeless "
                                "in these periods:\n  " + "\n  ".join(wrong[:12]))

    def test_the_backcast_label_is_still_emitted_by_some_path(self):
        """The companion to the test above, and the reason the repair stopped where it did.

        Relabelling every stream whose pattern equals the reference year's would have been
        defensible too - and it would have left reference_shape_backcast emitted by no code
        path, which this module's header rules out as making the vocabulary test pass
        vacuously. The value survives on road_density and builtup+ocac_area_shares, whose axis
        exists in FY2021-22 and FY2022-23 only, so earlier periods genuinely carry a pattern
        from elsewhere. If this ever reaches zero the vocabulary has a dead value and the
        honest move is to retire it, not to leave it listed.
        """
        emitted = [r for r in self.reg
                   if r["spatial_time_basis"] == "reference_shape_backcast"]
        self.assertTrue(emitted,
                        "reference_shape_backcast is declared in the vocabulary and produced "
                        "by nothing; retire the value or restore the path that emits it")

    def test_the_year_axis_is_keyed_on_the_PANEL_and_not_on_the_surface(self):
        """A surface is a raster and a panel is what factors it, and only the panel can carry
        a time axis. Keying YEAR_KEYED on the surface name would credit every stream that
        happens to ride the same raster.

        This test used to make that point with residential, which rode `population` on the
        reference year's district split while waste rode the same raster on each period's own.
        rc44 gave residential the period's population too, so the two now agree - and the
        point survives with a sharper example, because THREE surfaces carry both a keyed and
        an unkeyed panel: cropland and glw_livestock each carry residential panels that are
        keyed and agriculture panels that are not, and builtup carries residential panels
        against forty-seven streams with no panel at all. Keying on the surface would credit
        all of them.
        """
        from pkinv.report.spatial_weights import YEAR_KEYED
        surfaces = rows(os.path.join(OUTPUTS, "pakemis_grid_stream_surfaces.csv"))
        by_surface = {}
        for row in surfaces:
            by_surface.setdefault(row["surface"], set()).add(
                (row["surface"], row["district_panel"]) in YEAR_KEYED)
        split = sorted(name for name, flags in by_surface.items() if len(flags) > 1)
        self.assertGreaterEqual(len(split), 3, "the pair key is no longer load-bearing: %s"
                                % sorted(by_surface))
        self.assertIn("cropland", split)
        self.assertIn("glw_livestock", split)

    def test_the_crop_panels_are_year_keyed_and_the_livestock_panels_are_not(self):
        """Rewritten at rc46 Wave 3, which retired its predecessor's premise by name.

        The old guard ("the agriculture panels still carry the reference year's shape") held
        the honest state of rc44: every agriculture district panel was built for the
        reference year. The PBS district crop panel changed half of that, and only half -
        so the guard now holds the SPLIT: pairs whose panel is Rice cultivation, Managed
        soils or Urea application are annual_observed_activity in every historical year
        (the panel carries the time axis, the waste:population construction), and the
        LIVESTOCK panels (Enteric fermentation, Manure management) stay
        reference_shape_backcast, because one census anchor is held and interpolating
        district herds between nothing and it would be invention. A livestock row reading
        annual_observed means someone year-keyed a panel no evidence supports; a crop row
        reading backcast means the panel stopped being read. Field burning left this
        tuple at rc47 Wave 1: it carries NO district panel any more (its factor was a
        reference borrow, and crop area is a weaker stand-in for where fires burn than
        the fires themselves), so its rows have an empty panel half and are asserted
        separately below - year-keyed by the FIRMS surface alone."""
        YEAR_KEYED_PANELS = ("agri:Rice cultivation", "agri:Managed soils",
                             "agri:Urea application")
        burning = [r for r in self.reg
                   if r["module"] == "agriculture"
                   and "field-burning" in r["source_stream_id"]
                   and r["period_id"] != "FY2023-24"
                   and r["spatial_time_basis"] != "not_present"]
        self.assertTrue(burning, "no field-burning rows to hold the raster claim on")
        held_years = {r["acq_date"][:4] if int(r["acq_date"][5:7]) >= 7
                      else str(int(r["acq_date"][:4]) - 1)
                      for r in rows(asset_path(DATA, "gis", "manual", "firms_fire.csv"))}
        for row in burning:
            self.assertEqual(row["district_panel"], "",
                             "%s carries a district panel the category declined"
                             % row["source_stream_id"])
            if row["period_id"][2:6] in held_years:
                self.assertEqual(row["spatial_time_basis"], "annual_observed_activity")
            else:
                self.assertEqual(row["spatial_time_basis"], "substituted_surface")
                self.assertEqual(float(row["substituted_share"]), 1.0)
        for row in self.reg:
            if row["period_id"] == "FY2023-24" or not row["district_panel"].startswith("agri:"):
                continue
            if row["spatial_time_basis"] == "not_present":
                continue
            if row["district_panel"] in YEAR_KEYED_PANELS:
                source_periods = {r["period_id"] for r in rows(asset_path(
                    DATA, "activity", "agriculture", "crop_district_panel.csv"))
                    if r["qa_flag"] != "excluded_corrupt" and r["adm2_id"]}
                expected = ("annual_observed_activity" if row["period_id"] in source_periods
                            else "reference_shape_forward")
                self.assertEqual(row["spatial_time_basis"], expected,
                                 "%s %s: class differs from usable crop-panel coverage"
                                 % (row["source_stream_id"], row["period_id"]))
            else:
                # static_structural is admissible here for the same reason it is a
                # non-claim above: GLW is one undated raster, so a livestock panel placed on
                # it is timeless in every period. The assertion still rejects
                # annual_observed_activity, which is the claim this test is named for.
                self.assertIn(row["spatial_time_basis"],
                              ("reference_shape_backcast", "static_structural",
                               "substituted_surface", "unallocated"),
                              "%s %s: a livestock panel was year-keyed without evidence"
                              % (row["source_stream_id"], row["period_id"]))


class TestAbsencesAreTypedNotGraded(unittest.TestCase):
    """The trap this closes: a stream-year with no mass emits no fallback events, so it scores
    a perfect substituted_share of zero and reads as a well-placed backcast. Bagasse power in
    FY2015-16 is how it was found - the stream does not exist that year, and the registry was
    describing where its mass went."""

    @classmethod
    def setUpClass(cls):
        cls.reg = rows(os.path.join(OUTPUTS, "pakemis_spatial_weights_by_year.csv"))

    def test_the_structural_absences_are_typed_not_present(self):
        absent = {(r["source_stream_id"], r["period_id"]) for r in self.reg
                  if r["spatial_time_basis"] == "not_present"}
        self.assertEqual(len(absent), 29,
                         "the panel's structural absences are 3 cement-gas streams in "
                         "FY2020-21, 2 bagasse in four years and 3 railway furnace oil in six")
        for stream_id, period in absent:
            self.assertTrue(
                ("bagasse" in stream_id and period < "FY2019-20")
                or ("cement-gas" in stream_id and period == "FY2020-21")
                or ("furnace-oil" in stream_id and period < "FY2021-22"),
                "%s %s is typed absent but is not one of the known absences"
                % (stream_id, period))

    def test_an_absent_stream_year_grades_nothing(self):
        for row in self.reg:
            if row["spatial_time_basis"] == "not_present":
                self.assertEqual(row["weight_period"], "", row["source_stream_id"])
                self.assertEqual(row["borrowed_from_period"], "", row["source_stream_id"])
                self.assertEqual(float(row["substituted_share"]), 0.0, row["source_stream_id"])


if __name__ == "__main__":
    unittest.main()
