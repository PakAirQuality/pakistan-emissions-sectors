"""The source-stream ledger: conserved, complete, and honest about what it cannot resolve.

The ledger is the first object in this project that a data user is meant to read INSTEAD of
the manuscript, so the properties it has to hold are different from the ones the manuscript
tests enforce. Three matter most:

  CONSERVATION  it is a re-expression of the inventory, not a second calculation of it, so it
                must equal the national rollup exactly - per gas, per IPCC category, and in
                total. A ledger that is 0.1 Mt off is a second vintage.
  COMPLETENESS  every component appears exactly once. A join that drops rows produces a
                smaller, entirely plausible ledger.
  NO SILENT NULL  a field that cannot be resolved says so. This is the one that decides
                whether the gaps get closed: 182 of 184 streams cite documents whose licence
                is undetermined, and that number is only actionable because it is written
                down rather than left blank.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest


from pkinv.core import evidence, registry                  # noqa: E402
from pkinv.report import source_streams                    # noqa: E402
from pkinv.core.io import read_rows
from _support import DATA, OUT, ROOT



def _rows(path):
    return read_rows(path)


class TestTheLedgerConserves(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ledger = _rows(os.path.join(OUT, "pakemis_source_streams.csv"))
        cls.national = _rows(os.path.join(OUT, "national_all_sectors.csv"))

    def test_the_ledger_is_not_empty(self):
        """Every assertion below is a comparison, and a comparison over nothing passes."""
        self.assertGreater(len(self.ledger), 150,
                           "the ledger has %d rows; the join has collapsed" % len(self.ledger))
        self.assertEqual(len(source_streams.FIELDS), len(self.ledger[0]))

    def test_it_equals_the_national_total(self):
        total = sum(float(r["emissions_ar5"]) for r in self.ledger)
        published = next(float(r["co2e_Mt_AR5"]) for r in self.national
                         if r["sector"] == "TOTAL")
        self.assertAlmostEqual(total, published, places=3,
                               msg="the ledger is a re-expression of the inventory, not a "
                                   "second calculation of it")

    def test_it_equals_the_rollup_module_by_module(self):
        by_module = {}
        for r in self.ledger:
            by_module[r["module"]] = by_module.get(r["module"], 0.0) + float(r["emissions_ar5"])
        for row in self.national:
            if row["sector"] == "TOTAL":
                continue
            self.assertAlmostEqual(by_module.get(row["sector"], 0.0),
                                   float(row["co2e_Mt_AR5"]), places=3,
                                   msg="%s disagrees with the rollup" % row["sector"])

    def test_every_component_appears_exactly_once(self):
        comps, _cats, _sectors = registry.build_all()
        expected = {source_streams.stream_id(c["_sector"], c["category"],
                                             c["subitem"], c["gas"]) for c in comps}
        got = [r["source_stream_id"] for r in self.ledger]
        self.assertEqual(len(got), len(set(got)), "duplicate source_stream_id")
        self.assertEqual(expected, set(got))
        self.assertEqual(len(comps), len(self.ledger))

    def test_the_stream_id_is_stable_across_a_rebuild(self):
        """Built from the stream's identity, not from a counter, so a reordered build does
        not silently renumber every row of a published dataset."""
        first, _ = source_streams.build()
        second, _ = source_streams.build()
        self.assertEqual([r["source_stream_id"] for r in first],
                         [r["source_stream_id"] for r in second])
        self.assertEqual(first, second)


class TestTheLedgerDeclaresItsGaps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ledger = _rows(os.path.join(OUT, "pakemis_source_streams.csv"))

    def test_no_field_is_ever_blank(self):
        """The failure this prevents: a ledger that reads as complete because its gaps are
        empty strings. An unresolved field must SAY unresolved."""
        blanks = []
        for row in self.ledger:
            for field, value in row.items():
                if not str(value).strip():
                    blanks.append("%s.%s" % (row["source_stream_id"], field))
        self.assertFalse(blanks, "%d blank cells; declare them instead:\n  %s"
                         % (len(blanks), "\n  ".join(blanks[:12])))

    def test_the_release_height_class_is_in_the_vocabulary(self):
        for row in self.ledger:
            self.assertIn(row["release_height_class"], evidence.RELEASE_HEIGHT,
                          "%s carries a release height outside core.evidence.RELEASE_HEIGHT"
                          % row["source_stream_id"])

    def test_every_category_has_a_declared_release_height(self):
        """A category missing from data/release_heights.csv silently becomes 'unknown', which
        is a real class and therefore an easy place to hide. Assert coverage instead."""
        declared = {(r["module"], r["category"])
                    for r in _rows(asset_path(DATA, "release_heights.csv"))}
        comps, _c, _s = registry.build_all()
        needed = {(c["_sector"], c["category"]) for c in comps}
        self.assertEqual(needed - declared, set(),
                         "categories with no declared release height")
        self.assertEqual(declared - needed, set(),
                         "release heights declared for categories that no longer exist")


class TestTheTemporalProfileRegistry(unittest.TestCase):

    def setUp(self):
        self.profiles = _rows(asset_path(DATA, "temporal_profiles.csv"))
        self.monthly = _rows(os.path.join(OUT, "national_monthly_2024.csv"))

    def test_the_registry_is_not_empty(self):
        self.assertGreater(len(self.profiles), 20)

    def test_it_agrees_with_the_engine_in_both_directions(self):
        """An unused registry row and an unregistered profile are equally a defect.

        Profiles are built inline in each sector's monthly.py and identified only by a
        free-text basis string, so this registry is keyed on that string. That makes it
        brittle by construction - and the brittleness is the point: if a sector rewords its
        basis, this fails and the new wording gets registered, rather than the ledger quietly
        losing a profile id.
        """
        used = {(r["sector"], r["temporal_method"], r["basis"]) for r in self.monthly}
        registered = {(r["sector"], r["temporal_class"], r["basis"]) for r in self.profiles}
        self.assertEqual(used - registered, set(), "profiles the engine applies but the "
                                                   "registry does not name")
        self.assertEqual(registered - used, set(), "registry rows nothing applies")

    def test_every_profile_id_is_unique(self):
        ids = [r["profile_id"] for r in self.profiles]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_flat_profile_is_declared_as_one(self):
        """T4 is the class that most needs to be visible, so the registry states shape
        independently of class and the two must agree."""
        for row in self.profiles:
            if row["shape"] == "flat":
                self.assertEqual(row["temporal_class"], "T4",
                                 "%s is flat but not T4" % row["profile_id"])


class TestSpatialClaimsMatchTheEvidence(unittest.TestCase):
    """S1 means native source geometry. Claiming it without geometry is the spatial version
    of the defect this project keeps finding in prose.

    IPPU declared S1 for three releases on the strength of a facility registry with 34 rows
    and ZERO populated latitudes, while its allocation actually rode a provincial share whose
    own note says "PROVISIONAL GEOGRAPHY ... must not be interpreted as measured FY2023-24
    provincial production". It is S3 now.
    """

    def setUp(self):
        self.ledger = _rows(os.path.join(OUT, "pakemis_source_streams.csv"))

    def test_the_spatial_class_is_in_the_vocabulary(self):
        for row in self.ledger:
            self.assertIn(row["spatial_class"], evidence.SPATIAL)

    def test_ippu_no_longer_claims_native_geometry_it_does_not_have(self):
        facilities = _rows(asset_path(DATA, "activity", "ippu", "facilities.csv"))
        geocoded = [f for f in facilities if (f.get("latitude") or "").strip()]
        ippu = [r for r in self.ledger if r["module"] == "ippu"]
        self.assertTrue(ippu, "no ippu streams in the ledger")
        if not geocoded:
            for row in ippu:
                self.assertNotEqual(row["spatial_class"], "S1",
                                    "ippu claims native geometry with %d of %d facilities "
                                    "geocoded" % (len(geocoded), len(facilities)))

    def test_geometry_is_resolved_or_explicitly_residual_everywhere(self):
        """Stage 5's gate, as a property: no stream says "unresolved" any more.

        Round 10 shipped the ledger with geometry_id=unresolved on 184 of 184 streams -
        the honest starting line. Stage 5 replaced it: every stream names a registered
        geometry set or carries the explicit S4 residual, and "unresolved" stopped being a
        legal value in this column.
        """
        legal = {r["geometry_id"]
                 for r in _rows(asset_path(DATA, "geometry_sets.csv"))}
        legal.add("S4:no-native-geometry")
        for row in self.ledger:
            self.assertNotEqual(row["geometry_id"], "unresolved",
                                "%s regressed to unresolved" % row["source_stream_id"])
            self.assertIn(row["geometry_id"], legal,
                          "%s names an unregistered geometry" % row["source_stream_id"])

    def test_s1_requires_geometry_the_allocation_actually_opens(self):
        """The property, with the count pin removed because the pin was the bug.

        This test used to assert exactly six S1 streams AND that no facility set could ever
        be one - "railways' network is the only earned S1 geometry". Both halves went false
        together the moment the class was derived rather than declared: the network is S2,
        because Pakistan Railways publishes no per-corridor fuel and the corridor service
        tiers are declared judgement, and a facility set IS the only earned S1 - aviation,
        thirty-six of thirty-seven airports located and weighted by PCAA movements. A test
        that names the answer cannot survive the answer changing, which is the whole reason
        the class stopped being a literal.

        So: no count, and no named geometry. An S1 stream must name a set whose placement
        the allocation performs on per-object activity, over members that are located.
        """
        from pkinv.report import spatial_decomposition as spatial
        sets = {r["geometry_id"]: r
                for r in _rows(asset_path(DATA, "geometry_sets.csv"))}
        measured = spatial.geocoding()
        s1 = [r for r in self.ledger if r["spatial_class"] == "S1"]
        self.assertTrue(s1, "no stream is S1 at all; the class has stopped discriminating")
        for row in s1:
            geometry = sets.get(row["geometry_id"])
            self.assertIsNotNone(geometry, row["source_stream_id"])
            self.assertIn(geometry["kind"], ("network", "facility_set", "observation"),
                          "%s claims S1 over diffuse geometry" % row["source_stream_id"])
            self.assertEqual(geometry["within_province_placement"], "per_object_activity",
                             "%s claims S1 while the allocation places it by %r"
                             % (row["source_stream_id"],
                                geometry["within_province_placement"]))
            _members, _located, emitting, emitting_located = measured[row["geometry_id"]]
            # rc42 (S-1b): where the stream's own fuel can be located per station, the
            # located share of that ACTIVITY is the measure - the grid fleet is one geometry
            # of 82 emitting members carrying five fuel streams, and the coal stream is S1
            # with all eight of its stations located while the geometry counts 38 of 82.
            from pkinv.report import grid_cube
            share = grid_cube.located_activity_share(row["spatial_profile_id"])
            if share is not None:
                self.assertGreaterEqual(
                    share, spatial.GEOCODED_ENOUGH,
                    "%s claims S1 with %.1f%% of its own fuel on a located station"
                    % (row["source_stream_id"], 100 * share))
            elif emitting_located is not None and emitting:
                self.assertGreaterEqual(
                    emitting_located / emitting, spatial.GEOCODED_ENOUGH,
                    "%s claims S1 with %d of %d emitting members located"
                    % (row["source_stream_id"], emitting_located, emitting))

    def test_a_view_that_is_not_physical_names_the_geography_it_lacks(self):
        """THE BURDEN OF PROOF, made mechanical.

        The spatial view is the one axis of the three that cannot be derived: it is a
        property of what an activity statistic MEANS, and no register here holds that. So it
        is declared - and a declared value with nothing to contradict it is exactly what this
        release has spent itself repairing. What can be enforced instead is the burden: a row
        that places mass somewhere other than where it is emitted has to say what would place
        it correctly and why that is not held.

        Waste's rows already carried that sentence in prose before this column existed
        (landfills, drains, treatment works, burn sites), and transport's proxy rationale
        already carried its own admission about inter-city highway fuel. This test is the
        difference between a project that noticed and a project that cannot stop noticing.
        """
        from pkinv.report.grid_cube import VIEWS
        rows = _rows(asset_path(DATA, "stream_geometry.csv"))
        checked = 0
        for row in rows:
            self.assertIn(row["spatial_view"], VIEWS,
                          "%s/%s declares a view outside the vocabulary"
                          % (row["module"], row["category"]))
            if row["spatial_view"] == "physical":
                self.assertFalse(row["view_reason"].strip(),
                                 "%s/%s is physical and still argues for itself; the reason "
                                 "column is for what is NOT held"
                                 % (row["module"], row["category"]))
                continue
            checked += 1
            reason = row["view_reason"]
            self.assertGreater(len(reason), 80,
                               "%s/%s places mass away from the emission and says almost "
                               "nothing about it" % (row["module"], row["category"]))
            self.assertTrue(
                any(word in reason.lower() for word in ("not held", "no ", "not")),
                "%s/%s must name the release geography it does not hold"
                % (row["module"], row["category"]))
        self.assertGreater(checked, 0,
                           "every stream is physical, so this guard watches nothing - which "
                           "would be excellent news and should be checked before believed")

    def test_the_view_covers_every_stream_and_nothing_is_blank(self):
        for row in self.ledger:
            self.assertIn(row["spatial_view"], ("physical", "origin", "accounting"),
                          row["source_stream_id"])

    def test_the_geometry_assignment_is_used_in_both_directions(self):
        """Every stream resolves exactly once, and every declared mapping row matches at
        least one stream - the release_heights discipline, one level finer."""
        mapping = _rows(asset_path(DATA, "stream_geometry.csv"))
        self.assertGreater(len(mapping), 15)
        matched = set()
        for row in self.ledger:
            for i, m in enumerate(mapping):
                if m["module"] == row["module"]                         and m["category"] == row["sub_category"]:
                    matched.add(i)
        # sub_category on the ledger is the SUBITEM; the mapping keys on the engine
        # category, so match through module+category via the builder instead: rebuild the
        # index and assert it raises on nothing (completeness) and that no mapping row is
        # dead (both directions).
        from pkinv.report import source_streams as ss
        rows = ss._geometry_index()
        from pkinv.core import registry as reg
        comps, _c, _s = reg.build_all()
        used = set()
        for c in comps:
            gid = ss._geometry_for(rows, c["_sector"], c["category"], c["subitem"])
            for i, m in enumerate(rows):
                if m["module"] == c["_sector"] and m["category"] == c["category"]                         and m["geometry_id"] == gid                         and (not m["subitem_prefix"]
                             or c["subitem"].startswith(m["subitem_prefix"])):
                    used.add(i)
        dead = [rows[i]["geometry_id"] for i in range(len(rows)) if i not in used]
        self.assertFalse(dead, "stream_geometry rows matching no stream: %s" % dead)

if __name__ == "__main__":
    unittest.main()
