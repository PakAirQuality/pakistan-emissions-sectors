"""The facility registry: one id per physical facility, honest about what it cannot locate.

Three properties carry the weight. IDENTITY: unique ids, grandfathered where they were
already published (IPPU's 34 must never renumber). CORRESPONDENCE: both directions against
every source file, so a plant cannot fall out of the registry silently and the registry
cannot invent one. HONESTY: a coordinate is present and inside Pakistan, or the row says
coordinate_unresolved - the power grid's 157 town-located plants and the two counted LNG
terminals enter that way, because the alternative (geocoding towns by guess) is the
fabricated-provenance failure this project refuses everywhere.
"""

from pkinv.assets import asset_path
import csv
import os
import subprocess
import sys
import unittest


from pkinv.report import facility_registry                 # noqa: E402
from pkinv.core.io import read_rows
from _support import DATA, ROOT



def _rows(relative):
    return read_rows(asset_path(ROOT, relative))


class TestIdentity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = facility_registry.registry()

    def test_ids_unique_and_registry_non_empty_per_module(self):
        ids = [r["facility_id"] for r in self.registry]
        self.assertEqual(len(ids), len(set(ids)))
        by_module = {}
        for row in self.registry:
            by_module.setdefault(row["module"], []).append(row)
        for module in ("power", "ippu", "aviation", "railways", "fugitives", "industry"):
            self.assertIn(module, by_module, "no %s facilities" % module)

    def test_ippu_ids_are_grandfathered_verbatim(self):
        """Published ids never renumber. cement_lucky_pezu was in outputs before this
        registry existed; a rename would orphan every reference to it."""
        published = {r["facility_id"] for r in _rows("data/activity/ippu/facilities.csv")}
        held = {r["facility_id"] for r in self.registry if r["module"] == "ippu"}
        self.assertEqual(published, held)

    def test_the_registry_regenerates_identically(self):
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "build_facility_registry.py"),
             "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TestCorrespondence(unittest.TestCase):
    """Both directions against every source. A registry that lists what someone remembered
    is the failure audit_outputs.py exists to prevent, one layer up."""

    @classmethod
    def setUpClass(cls):
        cls.registry = facility_registry.registry()
        cls.by_module = {}
        for row in cls.registry:
            cls.by_module.setdefault(row["module"], []).append(row)

    def _both_directions(self, module, source_relative, source_key_column, expected):
        source_keys = {r[source_key_column] for r in _rows(source_relative)}
        registry_keys = {r["source_key"] for r in self.by_module[module]
                         if r["source_file"] == source_relative}
        self.assertEqual(len(source_keys), expected)
        self.assertEqual(source_keys - registry_keys, set(),
                         "%s rows missing from the registry" % source_relative)
        self.assertEqual(registry_keys - source_keys, set(),
                         "registry rows citing vanished %s entries" % source_relative)

    def test_captive_register(self):
        # 1,105 register rows over 1,043 distinct plant names: 54 groups run multiple
        # sites, which is why the facility_id disambiguates by district. The key
        # correspondence is over the NAMES.
        self._both_directions("power", "data/activity/power/captive_register.csv",
                              "physical_plant", 1043)

    def test_grid_plants(self):
        self._both_directions("power", "data/activity/power/plant_locations.csv",
                              "plant", 157)

    def test_ippu_facilities(self):
        self._both_directions("ippu", "data/activity/ippu/facilities.csv",
                              "facility_id", 34)

    def test_airports(self):
        self._both_directions("aviation", "data/activity/aviation/airports.csv",
                              "airport_icao", 37)

    def test_rail_yards(self):
        self._both_directions("railways", "data/gis/rail/yards.csv", "yard", 7)

    def test_every_located_point_source_is_registered(self):
        """The name-repair layer, pinned one level up: every plant the point-source
        product locates through point_sources.ALIAS + Table 5 must have a registry row.
        UNMATCHED rows are point_sources' own declared state and stay out; a LOCATED
        plant missing from the registry would mean the registry and the point product
        disagree about which facilities exist."""
        from pkinv.sectors.power import point_sources
        from pkinv.sectors.power.data import PowerData
        registered = {r["source_key"] for r in self.by_module["power"]
                      if r["source_file"] == "data/activity/power/plant_locations.csv"}
        rows = point_sources.rows(PowerData(), 2023)
        located = [r for r in rows if r["located_by"] != "UNMATCHED"]
        self.assertGreater(len(located), 40, "the point product located almost nothing")
        missing = sorted({point_sources.ALIAS.get(r["plant"], r["plant"])
                          for r in located}
                         - registered - set(point_sources.MINE_MOUTH))
        self.assertFalse(missing,
                         "located plants with no registry row: %s" % missing[:8])


class TestHonesty(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = facility_registry.registry()

    def test_coordinates_present_and_in_pakistan_or_declared_unresolved(self):
        for row in self.registry:
            if row["latitude"].strip():
                lon, lat = float(row["longitude"]), float(row["latitude"])
                if row["adm2_id"] != "not-applicable":
                    self.assertTrue(60.5 <= lon <= 77.5 and 23.5 <= lat <= 37.5,
                                    "%s outside Pakistan" % row["facility_id"])
            else:
                self.assertIn(row["status"], ("coordinate_unresolved",),
                              "%s has no coordinates and does not say so"
                              % row["facility_id"])

    def test_every_adm2_reference_resolves(self):
        from pkinv.core import adm2
        canonical = adm2.load_canonical()
        for row in self.registry:
            if row["adm2_id"] not in ("unresolved", "not-applicable"):
                for part in row["adm2_id"].split(";"):
                    self.assertIn(part, canonical, row["facility_id"])

    def test_the_confidence_vocabulary_is_closed(self):
        """The fifth review counted eleven ad-hoc confidence strings. The vocabulary
        is closed now; a new grade means editing CONFIDENCE_VOCAB deliberately, not
        leaking a source's private wording into the registry."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bfr", os.path.join(ROOT, "scripts", "build_facility_registry.py"))
        bfr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bfr)
        for row in self.registry:
            self.assertIn(row["coord_confidence"], bfr.CONFIDENCE_VOCAB,
                          row["facility_id"])

    def test_every_row_carries_the_verification_columns(self):
        """IPPU's five-column geocoding vocabulary, registry-wide: every row states
        HOW its coordinate is known (or that it is not), not just how confident a
        single adjective feels."""
        for row in self.registry:
            self.assertIn(row["geocode_status"],
                          ("exact_coordinate_resolved", "exact_coordinate_unresolved"),
                          row["facility_id"])
            if row["geocode_status"] == "exact_coordinate_resolved":
                self.assertTrue(row["coordinate_source"].strip(),
                                "%s resolved with no coordinate_source"
                                % row["facility_id"])
                self.assertTrue(row["coordinate_source_reference"].strip(),
                                "%s resolved with no coordinate_source_reference"
                                % row["facility_id"])

    def test_no_osm_derived_row_ships_unlicensed(self):
        """The seventh review's ODbL item: 71 OSM-derived facility rows shipped with
        no licence at all, inside a repository whose blanket grant is CC-BY - a
        licence OpenStreetMap extractions cannot carry, because an extracted
        coordinate table is a DERIVATIVE DATABASE under ODbL 1.0, share-alike and
        all. Every row now states the licence its geometry travels under, the
        vocabulary is closed, and any row whose coordinate source names OSM must
        say odbl."""
        allowed = {"odbl-1.0 (OpenStreetMap contributors; derivative database)",
                   "cc-by-4.0 (Hamdani et al. 2025, Zenodo)",
                   "source-document-register"}
        osm = 0
        for row in self.registry:
            self.assertIn(row["licence"], allowed, row["facility_id"])
            src = row["coordinate_source"].lower()
            if src.startswith(("openstreetmap", "osm")):
                osm += 1
                self.assertTrue(row["licence"].startswith("odbl"),
                                "%s has OSM geometry under %r"
                                % (row["facility_id"], row["licence"]))
        self.assertEqual(osm, 71,
                         "the OSM-derived row count moved (%d) - re-audit the "
                         "licence derivation in build_facility_registry.py" % osm)

    def test_the_kilns_are_district_resolved(self):
        """The asset-table join: at most the five declared outside-boundary points
        may stay unresolved; the count may move down, never up."""
        kilns = [r for r in self.registry if r["module"] == "industry"]
        unresolved = [r for r in kilns if r["adm2_id"] == "unresolved"]
        self.assertLessEqual(len(unresolved), 5)
        self.assertTrue(all(r["facility_id"].startswith("kiln_") for r in kilns))

    def test_the_grid_coordinate_gap_only_ever_shrinks(self):
        """It was 157 of 157, and the version of this test that said so predicted its own
        replacement: "if any gain a coordinate, this count moves DOWN and the sector's class
        conversation reopens; it may never drift up".

        It has, twice. Two coordinate databases already tracked here placed 42 of the
        stations at rc18, and the Wave-5 rung - province contains the point AND the
        source's own name confirms the declared town - carried it to 56, so the gap
        is 101. The ratchet is what is asserted, not the number: a coordinate once
        corroborated cannot be quietly lost, and the fleet's size cannot change
        without someone saying so.

        101 -> 105 at rc60, and this is the direction the ratchet was written to question,
        so the reason is here rather than in a commit message. The ladder matched on name
        tokens and geography with NO gate on technology, and four stations were therefore
        carrying a point that belongs to a different plant: the run-of-canal hydel Nandipur
        held the adjacent gas CCPP's coordinate, and the wind farms Gul Ahmed Electric,
        Liberty Wind Power-I and Liberty Wind Power-II held the coordinates of thermal
        plants their owners also run - the two Liberty rows landing about 370 km away in
        Ghotki. Those four points are now refused by a technology gate, so four stations
        return to unresolved. The gap grew because four wrong answers were withdrawn, which
        is the one movement upward this test should ever accept, and it must not be raised
        again without the same kind of account.

        And then DOWN to 88 in the same release, which is why the ceiling is the live count and
        not the raised one: this builder had never read data/activity/power/gas_plant_coordinates.csv,
        though grid_cube.py has consumed it since rc42, so seventeen stations were recorded as
        having no corroborated point while a GEM-exact one sat in the repository. A ratchet left
        at the loosened value would have permitted those seventeen to be lost again in silence.
        """
        grid = [r for r in self.registry
                if r["source_file"] == "data/activity/power/plant_locations.csv"]
        unresolved = [r for r in grid if r["status"] == "coordinate_unresolved"]
        self.assertEqual(len(grid), 157)
        self.assertLessEqual(len(unresolved), 88,
                             "the grid coordinate gap has grown, which means a corroborated "
                             "station lost its point")

    def test_the_time_validity_columns_are_well_formed(self):
        """rc60. `valid_from` and `valid_to` were declared at the sixteenth review for exactly
        this purpose - "a plant cannot receive emissions before it operated" - and then carried
        two values in the whole registry, with NO validator of any kind. They now carry the
        captive fleet's licence years and disconnection dates, so the validator lands with the
        data rather than after it."""
        import datetime

        def parsed(value):
            for fmt in ("%Y-%m-%d", "%Y"):
                try:
                    return datetime.datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            return None

        dated = [r for r in self.registry if r["valid_from"] or r["valid_to"]]
        self.assertGreater(len(dated), 100,
                           "the captive licence years and disconnection dates should be here")
        for row in dated:
            for column in ("valid_from", "valid_to"):
                if row[column]:
                    self.assertIsNotNone(parsed(row[column]),
                                         "%s=%r is neither a year nor an ISO date: %s"
                                         % (column, row[column], row["facility_id"]))
            if row["valid_from"] and row["valid_to"]:
                self.assertLessEqual(parsed(row["valid_from"]), parsed(row["valid_to"]),
                                     "a facility cannot stop before it started: %s" % row)

    def test_a_captive_disconnection_never_removes_its_metered_gas(self):
        """The register reconciles to OGRA's 288 MMCFD only with every connection record in it.
        A date is a column, never a filter, and this is the guard that says so."""
        captive = [r for r in self.registry if r["facility_id"].startswith("captive_")]
        self.assertEqual(len(captive), 1105)
        ended = [r for r in captive if r["valid_to"]]
        self.assertTrue(ended, "the disconnection dates should have landed")

    def test_a_district_is_never_claimed_more_firmly_than_its_evidence(self):
        """rc60. The placement ladder is point, then the gas table's point, then the town, then
        an administrative assignment from the source workbook. The weakest rung must say so:
        a row placed only by the workbook carries boundary_scope 'district' and a note that
        names it an assignment rather than an observation."""
        grid = [r for r in self.registry
                if r["source_file"] == "data/activity/power/plant_locations.csv"]
        stated = [r for r in grid if r["boundary_scope"] == "district"]
        self.assertTrue(stated, "the workbook fallback should place someone")
        for row in stated:
            # a point may exist and still place no district - the carved-from shapes cannot
            # separate their members - but the note must name the workbook, not the coordinate
            self.assertNotEqual(row["adm2_id"], "unresolved", row)
            self.assertIn("administrative assignment, not an observation", row["note"], row)
        for row in grid:
            if row["boundary_scope"] == "plant site":
                self.assertTrue(row["latitude"].strip(),
                                "a plant-site scope claims a point: %s" % row)

    def test_the_grid_S_class_is_justified_by_the_allocation_not_the_registry(self):
        """The registry improving does not upgrade the streams, and saying otherwise would be
        the same defect the temporal side carried twice: a class that answers from a
        declaration rather than from what the build actually did.

        The grid streams stay S2 while the cube's surface is built-up area, because putting
        the whole fleet's emissions on the located quarter would misplace the rest. When the
        allocation does use the points, this test is what makes the note change with it.
        """
        proxy = [r for r in _rows("data/stream_grid_proxy.csv")
                 if r["module"] == "power"
                 and r["category"] == "Electricity and heat production"]
        self.assertEqual(len(proxy), 1)
        self.assertTrue(proxy[0]["raster_proxy"],
                        "the grid stream claims no surface at all")
        note = proxy[0][[k for k in proxy[0] if "note" in k or "rationale" in k][0]]
        self.assertNotIn("until coordinates land", note,
                         "coordinates have landed; the note still says it is waiting for the "
                         "first one rather than for coverage")

    def test_prospective_rows_touch_no_stream(self):
        """Prospective assets are registered and citable, and NOTHING allocates to
        them - enforced for EVERY prospective geometry set, not a hard-coded one
        (rc7's version covered only the kilns, so the landfill set would have been
        born unguarded)."""
        mapped = {r["geometry_id"] for r in _rows("data/stream_geometry.csv")}
        prospective = [r["geometry_id"] for r in _rows("data/geometry_sets.csv")
                       if "prospective" in r["geometry_id"]
                       or "status=prospective" in r["member_rule"]]
        self.assertGreaterEqual(len(prospective), 2)
        for geometry_id in prospective:
            self.assertNotIn(geometry_id, mapped, geometry_id)

    def test_expected_members_counts_are_real(self):
        """geometry_sets.expected_members was validated by nothing - a wrong count
        failed silently. For facility sets resolved from the registry, the count must
        equal the member_rule's actual selection."""
        registry = facility_registry.registry()
        for row in _rows("data/geometry_sets.csv"):
            if row["kind"] != "facility_set" \
                    or row["member_source"] != "data/facility_registry.csv":
                continue
            parts = [part.strip().split("=", 1)
                     for part in row["member_rule"].split(" AND ")]
            if not all(len(part) == 2 for part in parts):
                continue        # prose rule; not registry-resolvable
            rule = dict(parts)
            got = sum(1 for r in registry
                      if all(r.get(k) == v for k, v in rule.items()))
            self.assertEqual(got, int(row["expected_members"]), row["geometry_id"])

    def test_a_power_station_is_filed_in_the_district_its_coordinate_is_in(self):
        """For the stations the province audit says are placed correctly, this registry's
        district must be the one the audit computed from the coordinate.

        WHY. On 2026-10-05 this registry shipped ThalNova and Thar Energy under
        sindh_thatta from coordinates about 24.81 N, 70.39 E - the Thar coalfield, roughly
        250 km from Thatta. The build read the district STRING Global Energy Monitor supplies
        beside the coordinates, and GEM gives "Thatta" for all three Thar stations. Engro
        Powergen Thar escaped only because NEPRA's location table lists it separately and it
        leaves through a different branch, so three stations about a kilometre apart were
        filed in two districts - and Thar Coal Block-I, 11 km away, sat under Tharparkar in
        the same column of the same source file. The province audit had already computed
        Tharparkar for every one of them.

        Nothing in the inventory moved: the allocation places a plant by its COORDINATE, and
        sindh_tharparkar duly carried 30,140 Gg of FY2023-24 CO2 against 490 Gg for the
        Thatta/Sujawal shape. That is what makes this worth a guard rather than a correction
        alone - the emissions were right and the published label was wrong, so a reader
        joining this registry to the ADM2 product met two shipped files contradicting each
        other with no test on either side of the join.

        WHY ONLY POWER STATIONS, AND ONLY THE AGREEING ONES. The same comparison over the
        whole registry reports about two hundred disagreements and almost none is this defect.
        Most captive rows share a city or district centroid - dozens at one coordinate - and
        there the district is the primary datum and the coordinate the approximation, so the
        comparison runs backwards. A further group is a frame-vintage artefact: facilities
        filed under Karachi's modern districts cannot be contained by a 2019 polygon named
        Malir or Keamari, because the canonical frame carries one legacy Karachi shape. And
        seven stations fall in no polygon or in a conflicting one, which is a BOUNDARY
        problem that pakemis_power_province_boundary_audit.csv owns and reports; duplicating
        it here would make two tests fail for one cause. The audit's agreeing stations are
        the set where the coordinate is an observation, the frame resolves it, and the
        district is therefore derivable - which is exactly the set the defect was in.
        """
        import csv as _csv
        import io as _io
        from pkinv.assets import asset_path as _asset_path
        from pkinv.core import adm2 as adm2_names
        from pkinv.paths import OUTPUTS as _OUTPUTS
        audit_path = _asset_path(_OUTPUTS, "pakemis_power_province_boundary_audit.csv")
        if not os.path.exists(audit_path):
            self.skipTest("the province boundary audit has not been generated here")
        text = _io.open(audit_path, encoding="utf-8").read()
        body = "\n".join(l for l in text.split("\n") if not l.startswith("#"))
        audit = {r["plant"]: r for r in _csv.DictReader(_io.StringIO(body))
                 if r.get("row_kind") == "station" and r.get("verdict") == "agree"
                 and r.get("adm2_containing")}
        self.assertGreater(len(audit), 50,
                           "only %d agreeing audited stations; this guard is checking an "
                           "almost empty set" % len(audit))
        registry = {r["name"]: r for r in facility_registry.registry()}
        wrong, checked = [], 0
        # ONE DECLARED EXCEPTION, with its reason and not as a loosened rule.
        #
        # Chiniot Power is filed punjab_chiniot and its coordinate (31.6116, 72.7607) falls in
        # the 2019 frame's Jhang polygon, about 20 km south-west of Chiniot city. Both claims
        # have a source: data/sectors/power/evidence/workbook_emissions_crosscheck.csv states
        # district "Chiniot" for this plant in every one of its years, and the frame states
        # Jhang for that point. Chiniot district was carved out of Jhang in 2009, so a
        # boundary-adjacent bagasse plant is exactly where the two would disagree, and the
        # coordinate's own precision is not established to the kilometre.
        #
        # Nothing in the inventory turns on it: the province is Punjab either way, which is
        # what the audit checks, and the allocation places the plant from the coordinate. It
        # is listed here because resolving it needs a Pakistani source on the plant's district
        # - not a choice between two of this repository's own columns - and because an
        # exception a reader can see beats a guard quietly scoped to avoid it. Opened as a
        # data_gaps lead in the same pass.
        UNRESOLVED_SOURCE_VS_FRAME = {"Chiniot Power"}
        for plant, arow in sorted(audit.items()):
            row = registry.get(plant)
            if row is None or row["adm2_id"] in ("unresolved", "not-applicable"):
                continue
            if plant in UNRESOLVED_SOURCE_VS_FRAME:
                continue
            try:
                expected = adm2_names.resolve(arow["adm2_containing"])
            except KeyError:
                continue
            checked += 1
            if expected != row["adm2_id"]:
                wrong.append("%s: filed under %s, but its coordinate (%s, %s) is in %s"
                             % (plant, row["adm2_id"], row["latitude"], row["longitude"],
                                expected))
        self.assertGreater(checked, 20,
                           "only %d stations joined the audit to the registry; the join key "
                           "has drifted and this guard is passing on nothing" % checked)
        self.assertFalse(wrong, "a power station is filed under a district its own "
                                "coordinate is not in, and the province audit says that "
                                "coordinate is placed correctly:\n  " + "\n  ".join(wrong))

    def test_a_planted_out_of_bbox_coordinate_is_caught(self):
        """The stored positive control for the build-time validation."""
        rows = facility_registry.registry()
        rows[0] = dict(rows[0], latitude="51.5", longitude="-0.1",
                       adm2_id="punjab_lahore")
        import unittest.mock as mock
        with mock.patch.object(facility_registry, "registry", return_value=rows):
            with self.assertRaises(ValueError):
                facility_registry.build()


if __name__ == "__main__":
    unittest.main()
