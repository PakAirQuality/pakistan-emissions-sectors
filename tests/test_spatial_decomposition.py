"""The spatial class, measured: coarse by geometry or coarse by ignorance, and never both.

`spatial_method` is a hand-assigned literal on every component, S1 to S4 written into each
sector's evidence triple and checked against nothing. That is the third appearance in this
release of one construction: `flatness_class` carried its own observed/unobserved answer, so
the temporal gap could not move when PBS's monthly series arrived; the per-sector `source_id`
constant labelled every power profile OCAC including the ones built from PBS. The cost here was
concrete and recent - two registry notes went false the week the grid coordinates landed, and
a person noticed rather than a test.

These tests are that person, made mechanical:

  * a stream may not declare a class stronger than the measurement supports, and the count of
    streams that do may only fall;
  * a geometry set's note may not quote a geocoded fraction the facility registry does not
    hold. This is the one that would have caught the grid notes by itself;
  * nothing is unclassified, and the gap is recomputed from the registers rather than read
    back out of the table that reports it.

Run:  python3 -m unittest discover tests -p "test_spatial_decomposition.py"
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import re
import unittest

from pkinv.paths import DATA, OUTPUTS
from pkinv.report import spatial_decomposition as spatial
from _support import cached_build
from pkinv.core.io import read_rows


def _rows(name, base=OUTPUTS):
    return read_rows(os.path.join(base, name))


class TestTheGeometryNotesAgreeWithTheRegistry(unittest.TestCase):
    """`geometry_sets.csv` said the grid fleet was wholly coordinate-unresolved for as long as
    it was true and for exactly as long after. A prose count is a number like any other."""

    def test_every_quoted_fraction_is_the_one_the_registry_holds(self):
        measured = spatial.geocoding()
        checked = 0
        for row in _rows("geometry_sets.csv", base=DATA):
            found = re.findall(r"(\d[\d,]*)\s+of\s+(\d[\d,]*)", row["note"])
            if not found:
                continue
            _members, _located, emitting, emitting_located = measured[row["geometry_id"]]
            if emitting_located is None:
                continue
            # The FIRST fraction in a note is the one that decides the placement, and that is
            # over the members that can emit. A note may then explain itself with the whole
            # register's numbers, as the grid fleet's does, and those are not re-checked here.
            quoted_geocoded, quoted_members = found[0]
            checked += 1
            self.assertEqual(
                (int(quoted_geocoded.replace(",", "")),
                 int(quoted_members.replace(",", ""))),
                (emitting_located, emitting),
                "%s says %r and the registry holds %d of %d that can emit"
                % (row["geometry_id"], row["note"][:70], emitting_located, emitting))
        self.assertGreater(checked, 0, "no geometry note quotes a fraction any more, so this "
                                       "guard is watching nothing")

    def test_no_note_still_says_it_is_waiting_for_the_first_coordinate(self):
        for row in _rows("geometry_sets.csv", base=DATA):
            self.assertNotIn("every member currently coordinate_unresolved", row["note"],
                             "%s: coordinates have landed for some set; this note has not "
                             "been re-read" % row["geometry_id"])


class TestThePlacementIsMeasuredNotDeclared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_spatial_decomposition.csv")

    def test_every_stream_is_placed(self):
        for row in self.rows:
            self.assertIn(row["placement_class"], spatial.CLASSES, row["sub_category"])
            self.assertTrue(row["basis"].strip())

    def test_a_diffuse_source_is_never_counted_as_a_gap(self):
        """Enteric fermentation has no point to find. Counting it as unresolved would make
        the gap a measure of the inventory's size rather than of its ignorance."""
        for row in self.rows:
            if row["placement_class"] == spatial.DIFFUSE:
                self.assertEqual(float(row["unresolved_Mt_AR5"]), 0.0, row["sub_category"])

    def test_the_gap_is_recomputed_from_the_registers(self):
        """Independently of the table that reports it - the same shape as the
        temporal one. Since Wave 5 the discriminator is whether the placement
        register records a point mechanism (the cube's dispatch consumes the
        points, partial coverage riding declared fallbacks), so a consumed fleet
        is outside the gap whatever its fraction; the fraction still decides the
        S-class."""
        register = {r["geometry_id"]: r for r in _rows("geometry_sets.csv",
                                                       base=DATA)}
        consumed = ("per_object_activity", "object_partial_activity",
                    "object_uniform")
        measured = spatial.geocoding()
        fallbacks = spatial.fallback_mass_by_stream()
        expected = 0.0
        for row in _rows("pakemis_source_streams.csv"):
            geometry = row["geometry_id"]
            reg = register.get(geometry, {})
            if geometry == spatial.NO_GEOMETRY or reg.get("kind") in ("adm_diffuse",
                                                                     "network"):
                continue
            if reg.get("within_province_placement") in consumed:
                # rc42 (S-1b): a consumed fleet's unresolved mass is the mass the cube's
                # own fallback ledger says rode a province surface - 0.318 Mt for coal
                # today, 34.7 Mt in rc41 when this test still added nothing here
                expected += fallbacks.get(row["source_stream_id"], (0.0, 0.0))[1]
                continue
            _members, _located, emitting, emitting_located = measured.get(
                geometry, (0, None, 0, None))
            fraction = ((emitting_located / emitting)
                        if (emitting_located is not None and emitting) else None)
            if fraction is None or fraction < spatial.GEOCODED_ENOUGH:
                expected += float(row["emissions_ar5"] or 0.0)
        published = sum(float(r["unresolved_Mt_AR5"]) for r in self.rows)
        self.assertAlmostEqual(expected, published, places=5)

    def test_no_stream_declares_a_class_the_measurement_cannot_carry(self):
        """It found thirty when it was first run, and all thirty are resolved, so this can be
        asserted at zero rather than ratcheted.

        Six were the report's own fault: it failed S1 wherever a raster was registered, and
        the railways rows register one only so that every stream resolves - the register says
        "unused: allocation is the network surface". The other twenty-four were real. The
        fugitive segments declared S2 on the reasoning that "the allocation rides
        infrastructure geography"; the objects are real but the allocation does not ride them,
        because stream_geometry.csv gives those segments the provincial diffuse set and
        stream_grid_proxy.csv spreads them uniformly inside it. They are S3 now, by the same
        correction the sector's own LNG row had already made for itself.
        """
        unsupported = [r for r in self.rows
                       if r["class_supported_by_measurement"] == "no"]
        self.assertFalse(unsupported,
                         "these declare a spatial class the geometry registry does not "
                         "support: %s" % sorted({(r["module"], r["sub_category"],
                                                  r["declared_spatial_class"],
                                                  r["geometry_kind"])
                                                 for r in unsupported}))

    def test_a_member_that_cannot_emit_never_moves_a_coverage_fraction(self):
        """The guard the metric never had, and the reason it read the wrong fleet.

        The grid register holds 157 stations and 79 of them are wind, solar or hydel. They
        belong in the register - they are real assets - and they cannot appear in a coverage
        fraction for an EMISSIONS allocation. Planting another one must move nothing.
        """
        before = spatial.geocoding()["facilities:power_grid"]
        original = spatial._rows

        def fake(path):
            rows = original(path)
            if path.endswith("facility_registry.csv"):
                wind = dict(rows[0], facility_id="grid_planted_wind_farm", module="power",
                            emits="no", geocode_status="exact_coordinate_unresolved")
                rows = rows + [wind]
            return rows

        spatial._rows = fake
        try:
            after = spatial.geocoding()["facilities:power_grid"]
        finally:
            spatial._rows = original
        self.assertEqual(after[0], before[0] + 1, "the register should have grown")
        self.assertEqual(after[2:], before[2:],
                         "a non-emitting station changed the fraction that decides where "
                         "this fleet's emissions are placed")

    def test_only_the_fleet_that_mixes_has_a_smaller_emitting_denominator(self):
        """Every other set is wholly emitting, so its two denominators agree. If a second set
        starts to mix, this says so rather than letting it pass unnoticed."""
        mixed = {geometry_id for geometry_id, (members, _l, emitting, _el)
                 in spatial.geocoding().items() if emitting != members}
        self.assertEqual(mixed, {"facilities:power_grid"})

    def test_a_stream_citing_an_unregistered_geometry_raises(self):
        """Fails closed: an unknown geometry would otherwise be placed by a `.get` default."""
        original = spatial._rows

        def fake(path):
            rows = original(path)
            if path.endswith("pakemis_source_streams.csv"):
                rows = [dict(rows[0], geometry_id="facilities:not-a-real-set")] + rows[1:]
            return rows

        spatial._rows = fake
        try:
            with self.assertRaises(KeyError):
                spatial.build()
        finally:
            spatial._rows = original


CACHES = all(os.path.exists(asset_path(DATA, "gis", "proxy_%s_267x340.npy" % n))
             for n in ("cropland", "builtup", "population", "glw_livestock",
                       "manure_applied"))
try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


@unittest.skipUnless(HAVE_NUMPY and CACHES,
                     "gis extra or committed proxy caches absent from this checkout")
class TestTheRegisterDescribesTheAllocationItClaimsTo(unittest.TestCase):
    """The derived spatial class rests on ONE declared fact per geometry set - what the cube
    distributes mass by inside it - and a register that describes an allocation it cannot see
    is the shape of every stale note this release has had to repair. So the cube records what
    each branch of its own dispatch actually did, and this compares the two.

    Without it, `within_province_placement` would be exactly the construction the derived
    class exists to retire: a value someone typed, checked against nothing.
    """

    def test_every_branch_the_cube_took_matches_the_register(self):
        from pkinv.report import grid_cube
        took = cached_build()["within_province_placement"]
        declared = {r["geometry_id"]: r["within_province_placement"]
                    for r in _rows("geometry_sets.csv", base=DATA)}
        declared[spatial.NO_GEOMETRY] = "raster_or_administrative"
        self.assertTrue(took, "the cube recorded no placements at all")
        for geometry, basis in sorted(took.items()):
            self.assertEqual(
                basis, declared[geometry],
                "%s: the cube distributes mass by %r and data/geometry_sets.csv says %r"
                % (geometry, basis, declared[geometry]))

    def test_a_set_the_cube_never_places_is_declared_not_used(self):
        """The other direction. A set the allocation does not touch may not claim a
        placement, because a placement it never performs cannot be checked and would earn
        the set a spatial class on paper."""
        from pkinv.report import grid_cube
        took = cached_build()["within_province_placement"]
        for row in _rows("geometry_sets.csv", base=DATA):
            if row["geometry_id"] in took:
                continue
            self.assertEqual(row["within_province_placement"], "not_used",
                             "%s is placed by nothing and declares %r"
                             % (row["geometry_id"], row["within_province_placement"]))


class TestTheClassIsDerivedNotDeclared(unittest.TestCase):
    def test_the_rule_answers_each_case_the_way_the_vocabulary_reads(self):
        """The derivation as a truth table, so a future edit to it has to disagree with
        something written down rather than merely with an intention."""
        for placement, fraction, expected in (
                ("per_object_activity", 0.973, "S1"),   # aviation: 36 of 37 airports
                ("per_object_activity", 0.38, "S2"),    # located too sparsely to carry it
                # rc47 Wave 2: None used to answer S1 here ("coordinate-native by
                # construction") - and that reading is exactly how 187 Mt of panel-year
                # power shipped the best grade on a measurement nobody had computed.
                # No measurement, no S1; a genuinely coordinate-native stream can and
                # must show a located fraction.
                ("per_object_activity", None, "S2"),
                ("object_partial_activity", 0.967, "S2"),  # captive: 864 of 1,068 have gas
                ("object_uniform", 1.0, "S2"),          # rail yards
                ("declared_judgement", None, "S2"),     # rail corridors
                ("raster_or_administrative", 1.0, "S3"),   # a located fleet, never opened
                ("not_used", None, "S3")):
            self.assertEqual(spatial.spatial_class(placement, fraction), expected,
                             "%s at %r" % (placement, fraction))

    def test_the_grid_fleet_is_consumed_and_earns_exactly_s2(self):
        """The 58 Mt case, in its Wave-5 state. The version of this test that pinned
        the fleet to raster-and-S3 was the derivation doing its job - a located
        fleet the allocation ignored was NOT a facility proxy - and its docstring
        invited exactly this rewrite. The cube now consumes the points: located
        stations carry their OWN plant-ledger fuel, the builtup fallback is a
        declared event per province, so the placement is per_object_activity. The
        class is S2 and MUST NOT be S1 while the emitting-geocoded fraction sits
        below 95 percent - upgrading on partial coverage would put the whole
        fleet's mass on the located share, the exact objection the old pin
        recorded."""
        rows = {r["geometry_id"]: r for r in _rows("geometry_sets.csv", base=DATA)}
        self.assertEqual(rows["facilities:power_grid"]["within_province_placement"],
                         "per_object_activity")
        grid = [r for r in _rows("pakemis_spatial_decomposition.csv")
                if r["geometry_id"] == "facilities:power_grid"]
        self.assertTrue(grid)
        # rc42 (S-1b): the class is decided by the MASS the located stations carry, read
        # from the cube's own fallback ledger. The coal stream, 44 percent located by
        # count and 99 percent by activity, earns S1 and point_resolved; the gas, RFO and
        # HSD streams keep fallback mass and are point_partial, S2, with that mass priced
        # as unresolved - the row a reader sorts on says what the map does.
        for row in grid:
            self.assertIn(row["placement_class"], ("point_resolved", "point_partial"),
                          row["sub_category"])
            if row["placement_class"] == "point_resolved":
                self.assertEqual(float(row["unresolved_Mt_AR5"]), 0.0, row["sub_category"])
            else:
                self.assertGreater(float(row["unresolved_Mt_AR5"]), 0.0, row["sub_category"])
                located = float(row["located_mass_fraction"])
                self.assertEqual(row["measured_spatial_class"],
                                 "S1" if located >= spatial.GEOCODED_ENOUGH else "S2",
                                 (row["sub_category"], located))
        coal = [r for r in grid if "coal" in r["sub_category"].lower()]
        self.assertTrue(coal)
        for row in coal:
            self.assertEqual(row["measured_spatial_class"], "S1", row["sub_category"])
            self.assertGreaterEqual(float(row["located_mass_fraction"]), 0.95)

    def test_the_ledger_publishes_both_and_they_agree(self):
        """`build()` raises where they do not, so this asserts the shipped file rather than
        the code path - a reader downloads the CSV, not the exception."""
        rows = _rows("pakemis_source_streams.csv")
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["spatial_class"], row["spatial_class_measured"],
                             row["source_stream_id"])
            self.assertIn(row["geometry_available"], ("yes", "no"))
        unavailable = {r["geometry_id"] for r in rows if r["geometry_available"] == "no"}
        self.assertEqual(unavailable, {spatial.NO_GEOMETRY},
                         "geometry_available is the S4 axis and nothing else")

    def test_a_planted_declaration_stops_the_build(self):
        """Positive control on the fail-closed guard. Without it the two columns would be
        published side by side and a reader left to notice the disagreement."""
        from pkinv.report import source_streams
        original = source_streams._measured_class

        def fake():
            table = original()
            return {k: ("S1" if v != "S1" else "S3") for k, v in table.items()}

        source_streams._measured_class = fake
        try:
            with self.assertRaises(ValueError) as caught:
                source_streams.build()
        finally:
            source_streams._measured_class = original
        self.assertIn("does not earn", str(caught.exception))



class TheClassAxisAgreesWithTheUnallocatedLedger(unittest.TestCase):
    """WHAT THE REVIEWER FOUND, and the narrower thing it turned out to be.

    Twenty-four industrial-combustion streams read `spatial_class = S3` while carrying no
    native geometry and appearing whole in the unallocated ledger. S3 asserts that "a raster
    or an administrative share does the placing" BELOW THE PROVINCE, and for those streams
    nothing places them below the province at all - so the letter claimed a product that does
    not exist.

    They are not unplaced, which is why the class is NA rather than the stream being dropped:
    every one has a province. What is absent is a level beneath it. The class axis grades
    below-province placement, so where there is none there is nothing to grade, and two
    separate columns now carry what IS true.
    """

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_spatial_decomposition.csv")

    def test_no_stream_claims_a_class_for_a_placement_it_does_not_have(self):
        for row in self.rows:
            if row["placement_status"] == "unallocated_below_adm1":
                self.assertEqual("NA", row["measured_spatial_class"],
                                 "%s/%s is unallocated below ADM1 and still graded %s"
                                 % (row["module"], row["sub_category"],
                                    row["measured_spatial_class"]))
            else:
                self.assertNotEqual("NA", row["measured_spatial_class"],
                                    "%s/%s is allocated below ADM1 and graded NA"
                                    % (row["module"], row["sub_category"]))

    def test_the_two_products_name_the_same_streams(self):
        """The class axis and the unallocated ledger are two views of one decision. rc41: the
        class axis no longer READS the cube's ledger to learn which streams are retained at
        ADM1 (a product of a later phase that itself reads the class axis - every build had
        compared against the previous release's file); it derives the set from the geometry
        column by the cube's own rule, and this test holds the cube's ledger to it, stream
        by stream, not module by module."""
        derived = spatial.unallocated_streams()
        ledger = spatial.unallocated_ledger_streams()
        self.assertTrue(ledger, "outputs/pakemis_spatial_unallocated.csv names no stream")
        self.assertEqual(ledger, derived)
        graded = {r["module"] for r in self.rows
                  if r["measured_spatial_class"] == "NA"}
        self.assertEqual({m for m, _s in ledger}, graded)

    def test_the_finest_level_is_stated_for_every_stream(self):
        levels = {r["finest_placement_level"] for r in self.rows}
        self.assertEqual({"adm1", "below_adm1"}, levels)

if __name__ == "__main__":
    unittest.main()


class TestAStreamRidesItsOwnProfileNotItsNeighbours(unittest.TestCase):
    """rc46 Wave 5 regression: the flare-weight cache key originally omitted the stream's
    spatial profile, so every flare-pointed segment inherited whichever provincial vector
    was built first - gas production shipped on OIL's split (Balochistan 20.9% -> 0.1%)
    while the stream totals held, which is exactly the failure a national closure test
    cannot see. The check is at the shipped-product level: streams that share a declared
    profile must agree on their ADM1 vector, and the oil and gas profiles - genuinely
    different splits in OGRA's data - must not collapse into one."""

    def _adm1_vectors(self):
        streams = {r["source_stream_id"]: r for r in read_rows(
            os.path.join(OUTPUTS, "pakemis_source_streams.csv"))}
        flare = {sid for sid, r in streams.items()
                 if r.get("geometry_id") == "points:wb_flares"}
        self.assertGreater(len(flare), 0, "no flare-pointed streams shipped")
        vec = collections.defaultdict(dict)
        for r in read_rows(os.path.join(OUTPUTS, "pakemis_adm1_by_year.csv")):
            if r["source_stream_id"] in flare and r["spatial_view"] == "physical":
                vec[(r["period_id"], r["source_stream_id"])][r["province"]] = \
                    float(r["emissions_Gg"])
        out = {}
        for key, by_prov in vec.items():
            total = sum(by_prov.values())
            if total > 0:
                out[key] = {p: v / total for p, v in by_prov.items()}
        return streams, out

    def test_streams_sharing_a_profile_share_a_vector_and_profiles_differ(self):
        streams, vectors = self._adm1_vectors()
        by_profile = collections.defaultdict(dict)
        for (period, sid), v in vectors.items():
            by_profile[(period, streams[sid]["spatial_profile_id"])][sid] = v
        # within a profile: identical vectors (same shares, same sites)
        for (period, profile), members in by_profile.items():
            first_sid, first = next(iter(members.items()))
            for sid, v in members.items():
                for prov in set(first) | set(v):
                    self.assertAlmostEqual(
                        first.get(prov, 0.0), v.get(prov, 0.0), places=6,
                        msg=f"{period}: {sid} disagrees with {first_sid} on {prov} "
                            f"despite sharing profile {profile}")
        # across profiles: at least two distinct vectors per period (oil vs gas)
        for period in {p for p, _ in by_profile}:
            profs = [(prof, next(iter(m.values())))
                     for (p, prof), m in by_profile.items() if p == period]
            if len(profs) < 2:
                continue
            max_gap = max(abs(a.get(prov, 0) - b.get(prov, 0))
                          for i, (_, a) in enumerate(profs)
                          for _, b in profs[i + 1:]
                          for prov in set(a) | set(b))
            self.assertGreater(
                max_gap, 0.01,
                msg=f"{period}: every flare profile shipped the same provincial vector - "
                    "the cache-key regression this test exists for")
