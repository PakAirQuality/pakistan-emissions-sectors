"""Every FY2023-24 coal grid station is located, and none rides the built-up fallback (rc42, S-1).

rc41 placed 34.71 of the 38.46 Mt coal grid stream (90 percent) on the Sindh and Balochistan
built-up rasters while GEM and Climate TRACE held exact points for all eight stations in
tables this repository already carried. The coal coordinate table is keyed by the ledger's
own station names through an explicit alias map; the dispatch reads it for the ledger keys
plant_coordinates.csv does not locate.
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import DATA, data_rows, rows, scripts_on_path

COAL = os.path.join("activity", "power", "coal_plant_coordinates.csv")
LEDGER = os.path.join("activity", "power", "plant_fuel_ledger.csv")


class TestTheCoalFleetIsLocated(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.table = data_rows(COAL)
        cls.ledger = sorted({r["plant"] for r in data_rows(LEDGER, comments=False)
                             if r["fiscal_year"] == "2023" and r["fuel"] == "Coal"})

    def test_all_eight_ledger_stations_have_a_row(self):
        self.assertEqual(len(self.ledger), 8)
        self.assertEqual(sorted(r["plant"] for r in self.table), self.ledger)

    def test_every_row_is_exact_and_corroborated(self):
        for r in self.table:
            self.assertEqual(r["gem_accuracy"], "exact", r["plant"])
            self.assertLessEqual(float(r["agreement_km"]), 5.0, r["plant"])
            # raster_province, not province: the column is RASTER-DERIVED and was renamed
            # so no reader can mistake it for a curated record. China Power Hub's raster
            # cell reads Sindh while its record and GEM say Balochistan, which is the
            # twenty-second review's item 7 and why the name had to change.
            self.assertIn(r["raster_province"],
                          ("Punjab", "Sindh", "Balochistan", "Khyber Pakhtunkhwa"),
                          r["plant"])

    def test_the_dispatch_locates_every_coal_station(self):
        from pkinv.report import grid_cube
        points = grid_cube.grid_plant_points(("Coal",))
        self.assertEqual(sum(len(v) for v in points.values()), 8)
        # a station pools under the province its POINT lands in on the inventory grid
        # (Hub's cell reads Sindh on the 0.05-degree province raster although the site is
        # Lasbela's), so the pool set is a subset of the three coal provinces
        self.assertTrue(set(points) <= {"Punjab", "Sindh", "Balochistan"}, set(points))

    def test_the_coal_fallback_is_gone_but_for_balochistans_share(self):
        """34.71 Mt of coal mass rode built-up in rc41; with the eight stations located
        only Balochistan's 0.83 percent ledger share (0.32 Mt) can remain, because no
        located station carries its own coal fuel there - the Hub point lands in the grid's
        Sindh cell - and that remainder is a declared event, not a silence."""
        coal = [r for r in rows("pakemis_grid_fallbacks.csv")
                if r["scope"] == "province" and r["source_stream_id"].startswith("power|")
                and "coal" in r["source_stream_id"].lower()]
        self.assertTrue({r["province"] for r in coal} <= {"Balochistan"},
                        [(r["province"], r["affected_Mt_AR5"]) for r in coal])
        self.assertLess(sum(float(r["affected_Mt_AR5"]) for r in coal), 0.35)

    def test_a_point_outside_every_province_is_refused(self):
        scripts_on_path()
        import ingest_coal_plant_coordinates as script
        original = script.ALIASES.copy()
        try:
            script.ALIASES["China Power Hub"] = "Thar Block I power station"   # a wrong alias
            script.AGREEMENT_KM = 0.0                                          # forces the agreement gate
            with self.assertRaises(SystemExit):
                script.build()
        finally:
            script.ALIASES.clear()
            script.ALIASES.update(original)
            script.AGREEMENT_KM = 5.0


class TestTheClassIsGradedPerStreamOnLocatedActivity(unittest.TestCase):
    """rc42 (S-1b). The grid fleet is one geometry carrying five fuel streams; the letter
    is graded per stream on the share of the stream's OWN FY2023-24 fuel that sits on a
    located station (ledger + coordinate tables, no grid). Until rc44 the cube pooled unlocated
    stations onto their located siblings with no fallback event, so the fallback ledger alone
    read the gas fleet as 1.0 located with half of it unlocated and this share had to be
    applied on top of it. rc44 prices that fuel as an event, so the two are now INDEPENDENT
    MEASURES OF ONE QUANTITY from different inputs, and test_the_two_located_measures_agree
    holds them together."""

    @classmethod
    def setUpClass(cls):
        from pkinv.report import grid_cube
        cls.share = {p: grid_cube.located_activity_share(p)
                     for p in ("power_coal", "power_gas", "power_rfo", "power_hsd", "bagasse_grid")}
        cls.ledger = [r for r in rows("pakemis_source_streams.csv")
                      if r["geometry_id"] == "facilities:power_grid"]
        cls.decomposition = [r for r in rows("pakemis_spatial_decomposition.csv")
                             if r["geometry_id"] == "facilities:power_grid"]

    def test_coal_diesel_gas_and_now_rfo_are_located(self):
        """Coal was fully located in rc42; diesel joined in rc44 by K-Electric leaving the
        denominator. GAS crossed at rc46 Wave 1 the ordinary way - seventeen stations
        acquired GEM-exact, TRACE-corroborated coordinates - and reads 0.966 located.

        RFO CROSSED AT rc60, and not by acquiring anything. This test used to assert
        `share < 0.95` with the instruction "retire this bound and promote the grade
        deliberately", and its own docstring explained the 0.8299 by naming the typed skip
        list in scripts/ingest_gas_plant_coordinates.py - the GOGPT defect on Halmore, the
        JDW-III identity conflict, Nooriabad approximate-only. THAT EXPLANATION WAS WRONG,
        and the wrongness is worth keeping on the record: none of those three burns furnace
        oil. The whole 0.1701 was Lal Pir, 86.4 of the reference year's 508.1 thousand
        tonnes, which has held a GEM-exact coordinate since rc46. It went unmatched because
        scripts/ingest_nepra_plants.py had joined the column heading "(000 M. Tons)" onto
        its name, giving a join key of ('000', 'lal', 'm', 'pir', 'tons').

        So the lesson this test now carries is about a missing-data story that was never
        checked against the data it claimed to describe. A floor with a plausible reason
        attached is not evidence; the reason has to name the actual rows.
        """
        self.assertAlmostEqual(self.share["power_coal"], 1.0, places=9)
        self.assertAlmostEqual(self.share["power_hsd"], 1.0, places=9)
        self.assertGreater(self.share["power_gas"], 0.95, "gas fell back below the rc46 line")
        self.assertAlmostEqual(self.share["power_rfo"], 1.0, places=9,
                               msg="every RFO station in the reference year held a coordinate "
                                   "at rc60; a drop means a coordinate or a name join was lost")
        self.assertIsNone(self.share["bagasse_grid"])

    def test_the_rfo_fleet_is_located_station_by_station(self):
        """The share is one number and could be right for the wrong reason, so the twelve
        stations behind it are named. This is also the guard that would have caught the
        original defect: Lal Pir carried 17 percent of the fuel and matched nothing, while
        the aggregate still read a comfortable 0.83."""
        from pkinv.report import grid_cube
        ledger = grid_cube._grid_fuel_ledger(grid_cube.GRID_PROFILE_FUELS["power_rfo"], None)
        located = set()
        for name in grid_cube.GRID_COORDINATE_TABLES:
            path = asset_path(DATA, "activity", "power", name)
            if not os.path.exists(path):
                continue
            for row in grid_cube._rows(path, root="/"):
                key = grid_cube._grid_plant_name_key(row["plant"])
                if key in ledger:
                    located.add(key)
        unlocated = sorted(" ".join(k) for k in set(ledger) - located)
        self.assertEqual(unlocated, [], "RFO stations carrying ledger fuel and no coordinate")
        self.assertEqual(len(ledger), 12,
                         "the reference-year RFO fleet changed size; re-derive the list before "
                         "moving this number: %s" % sorted(" ".join(k) for k in ledger))

    def test_the_ledger_grades_the_four_fossil_streams_s1_and_bagasse_s2(self):
        """HSD crossed 0.95 at rc44 (K-Electric left the ledger); gas at rc46 Wave 1
        (seventeen GEM/TRACE coordinates); RFO at rc60, by a plant-name fix rather than by an
        acquisition - Lal Pir had held a GEM-exact coordinate since rc46 and could not be
        matched to it because the ledger carried a column heading in its name.

        Bagasse keeps S2: it has no plant-ledger fuel at all, so `located_activity_share`
        returns None for it and there is nothing to measure a letter against."""
        for r in self.ledger:
            expected = ("S1" if r["spatial_profile_id"] in ("power_coal", "power_hsd",
                                                            "power_gas", "power_rfo") else "S2")
            self.assertEqual(r["spatial_class_measured"], expected, r["sub_category"])
            self.assertEqual(r["spatial_class"], expected, r["sub_category"])

    def test_the_decomposition_prints_the_activity_share_less_the_fallback(self):
        fallback = {}
        for r in rows("pakemis_grid_fallbacks.csv"):
            if r["scope"] == "province":
                fallback[r["source_stream_id"]] = fallback.get(r["source_stream_id"], 0.0) \
                    + float(r["weight_share"] or 0.0)
        for r in self.decomposition:
            stream_id = "power|electricity-and-heat-production|%s|%s" % (
                r["sub_category"].lower().replace(" ", "-"), r["gas"].lower())
            profile = {"Coal": "power_coal", "Gas": "power_gas", "Furnace Oil": "power_rfo",
                       "Diesel Oil": "power_hsd", "Bagasse": "bagasse_grid"}[r["sub_category"].rsplit(" ", 1)[0]]
            # ONE MEASURE, ONE PLACE (rc44). This used to be
            #     expected = located_activity_share(profile) * (1 - fallback_fraction)
            # which was right while the cube pooled a province's share across its located
            # stations without emitting an event: the ledger could not see the unlocated fuel,
            # so the located share had to be applied on top of it. The cube now prices that
            # fuel as a fallback, so the fallback fraction already carries it and multiplying
            # again squares it - for gas, 0.4874 became 0.2376. The product prints
            # 1 - fallback_fraction and so does this test.
            expected = 1.0 - fallback.get(stream_id, 0.0)
            self.assertAlmostEqual(float(r["located_mass_fraction"]), expected, places=4,
                                   msg=(r["sub_category"], stream_id))
            self.assertEqual(r["measured_spatial_class"], "S1" if expected >= 0.95 else "S2",
                             r["sub_category"])

    def test_the_two_located_measures_agree(self):
        """THE INVARIANT (rc44). The input-side measure reads ledger fuel on located
        stations; the cube-side measure is one minus what its fallback ledger booked. They
        are computed from different inputs and must land on the same number, because
        point_sources builds each province's share from the same ledger energy: the cube's
        total fallback is the sum over provinces of share_p x (1 - located fuel_p / fuel_p),
        and with share_p = fuel_p / total fuel that telescopes to 1 - located / total, which
        is the input-side measure exactly.

        This is the check that catches a squared fraction on its own - the rc42 correction
        left in place after rc44 made it redundant multiplied these two together, and the
        product printed 0.2376 for a gas fleet that is 0.4874 located. Nothing else failed.
        """
        fallback, absent = {}, {}
        for r in rows("pakemis_grid_fallbacks.csv"):
            if r["scope"] != "province":
                continue
            key, w = r["source_stream_id"], float(r["weight_share"] or 0.0)
            fallback[key] = fallback.get(key, 0.0) + w
            # TWO KINDS OF FALLBACK, and only one of them is what the input-side measure can
            # see. "no corroborated station ... in <province>" fires when the SHARE vector
            # gives a province mass and no point of that fuel lands in it - which is a
            # disagreement between the share vector's provinces (NEPRA Table 5 labels) and
            # the cube's (the province raster the point falls in), not a statement about
            # located fuel. Coal is the standing case: every one of the eight stations is
            # located, so the ledger share is 1.0, while Balochistan holds 0.83 percent of
            # the coal share and its station's point lands in the grid's Sindh cell.
            if r["reason"].startswith("no corroborated station"):
                absent[key] = absent.get(key, 0.0) + w
        seen = 0
        for r in self.decomposition:
            profile = {"Coal": "power_coal", "Gas": "power_gas", "Furnace Oil": "power_rfo",
                       "Diesel Oil": "power_hsd", "Bagasse": "bagasse_grid"}[
                           r["sub_category"].rsplit(" ", 1)[0]]
            if self.share[profile] is None:
                continue
            stream_id = "power|electricity-and-heat-production|%s|%s" % (
                r["sub_category"].lower().replace(" ", "-"), r["gas"].lower())
            expected = self.share[profile] - absent.get(stream_id, 0.0)
            self.assertAlmostEqual(1.0 - fallback.get(stream_id, 0.0), expected, places=5,
                                   msg=(r["sub_category"], stream_id))
            seen += 1
        self.assertGreater(seen, 0)
        # The equality is EXACT where the two vectors agree on provinces: gas and furnace oil
        # carry no province-absent row at all and match to five decimal places.
        for stream_id in fallback:
            if "gas-" in stream_id or "furnace-oil-" in stream_id:
                self.assertNotIn(stream_id, absent, stream_id)


class TestThePowerBoundaryIsHonouredWhereverTheLedgerIsRead(unittest.TestCase):
    """SoIR Table 3 is CPPA-only - ke_boundary_audit tests it per year and per fuel - so the
    mass the cube places contains no K-Electric generation. Until rc44 the cube read the
    plant ledger without the boundary filter the rest of the sector applies, and pooled
    Sindh's grid gas onto K-Electric's Karachi points: 15.6 percent of the whole located gas
    pool, and the majority of Sindh's. The boundary is now one predicate, and this test says
    the consumer furthest from it obeys."""

    @classmethod
    def setUpClass(cls):
        cls.ke = set()
        for r in data_rows(LEDGER, comments=False):
            if r["system"] == "K-Electric":
                cls.ke.add(r["plant"])

    def test_the_predicate_is_the_only_definition(self):
        from pkinv.sectors.power import plant_ledger
        self.assertTrue(self.ke)
        for plant in sorted(self.ke):
            self.assertFalse(plant_ledger.in_boundary({"system": "K-Electric"}), plant)
        self.assertTrue(plant_ledger.in_boundary({"system": "CPPA"}))

    def test_no_k_electric_station_is_in_the_cube_point_pool(self):
        """By COORDINATE, not by name: a K-E station reaching the pool under any spelling
        would still put its point in it."""
        import os as _os
        from pkinv.report import grid_cube
        keys = {grid_cube._grid_plant_name_key(p) for p in self.ke}
        banned = set()
        for r in data_rows(_os.path.join("activity", "power", "plant_coordinates.csv")):
            if grid_cube._grid_plant_name_key(r["plant"]) in keys:
                banned.add((round(float(r["longitude"]), 5), round(float(r["latitude"]), 5)))
        self.assertTrue(banned, "no K-Electric station has coordinates - test is vacuous")
        for fuels in (("Gas", "RLNG"), ("RFO",), ("Coal",), ("HSD",)):
            pool = grid_cube.grid_plant_points(fuels)
            for province, points in pool.items():
                for lon, lat, _qty in points:
                    self.assertNotIn((round(lon, 5), round(lat, 5)), banned,
                                     (fuels, province))

    def test_the_heating_value_is_the_sectors_parameter(self):
        """Not a second copy of it. Equal today, so this commit moves nothing."""
        from pkinv.report import grid_cube
        params = {r["param"]: r["value"] for r in data_rows("power_params.csv")}
        self.assertEqual(grid_cube._grid_gas_hhv(),
                         float(params["captive_hhv_btu_per_scf"]))
        self.assertEqual(grid_cube._grid_gas_hhv(), 1000.0)


if __name__ == "__main__":
    unittest.main()
