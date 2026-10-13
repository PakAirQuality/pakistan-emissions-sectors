"""The canonical ADM2 package: complete over every district string this repository holds.

The property that matters is TOTAL RESOLUTION: every district spelling in every live data
file resolves to a canonical unit, in both directions, with the geometry's holes declared
rather than discovered. The package was built by finding, among other things, that the
boundary file has no Larkana polygon at all - a district of two million people absent from
every district product ever generated here, silently, because the rasteriser fills unknown
territory with -1 and nothing ever asked where Larkana went.
"""

from pkinv.assets import asset_path
import csv
import json
import os
import sys
import unittest


from pkinv.core import adm2                                # noqa: E402
from pkinv.core.io import read_rows
from _support import DATA, ROOT


LIVE_DISTRICT_FILES = (
    ("data/activity/waste/population_district.csv", "district"),
    ("data/activity/livestock_district_2024.csv", "district"),
    ("data/activity/transport/vehicles_district.csv", "district"),
)


def _rows(relative):
    return read_rows(asset_path(ROOT, relative))


class TestTheCanonicalTable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.canonical = adm2.load_canonical()

    def test_it_is_not_empty_and_ids_are_unique(self):
        self.assertGreater(len(self.canonical), 140)
        names = [r["canonical_name"] for r in self.canonical.values()]
        self.assertEqual(len(names), len(set(names)), "duplicate canonical names")

    def test_the_package_regenerates_identically(self):
        """The builder is the review surface; a hand edit to the CSVs would silently
        diverge from it."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "build_adm2_package.py"),
             "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_shape_in_the_boundary_file_is_claimed(self):
        """Both directions, geometry side: a polygon no canonical unit claims is territory
        that would rasterise into the grid and then vanish from every district product."""
        with open(asset_path(DATA, "gis", "PAK_ADM2.geojson"), encoding="utf-8") as handle:
            shapes = {f["properties"]["shapeID"] for f in json.load(handle)["features"]}
        claimed = set(adm2.shape_to_adm2())
        self.assertEqual(shapes - claimed, set(), "unclaimed polygons")
        self.assertEqual(claimed - shapes, set(), "canonical rows citing unknown shapeIDs")

    def test_the_larkana_defect_is_declared_not_papered_over(self):
        """The boundary file has no Larkana polygon - verified against its shapeName list;
        Qambar Shahdadkot, carved OUT of Larkana in 2004, is present, so this is a
        distributor defect rather than a vintage question. The table must say so."""
        larkana = next(r for r in adm2.load_canonical().values()
                       if r["canonical_name"] == "Larkana District")
        self.assertEqual(larkana["geometry_relation"], "shape_missing")
        self.assertEqual(larkana["shape_id"], "")
        self.assertIn("defect", larkana["note"])

    def test_geometry_relations_are_from_the_vocabulary_and_consistent(self):
        for row in self.canonical.values():
            relation = row["geometry_relation"]
            self.assertIn(relation, ("one_to_one", "part_of", "carved_from",
                                     "shape_missing", "no_geometry", "legacy_aggregate"))
            if relation in ("one_to_one", "part_of", "carved_from", "legacy_aggregate"):
                self.assertTrue(row["shape_id"], "%s claims geometry it does not name"
                                % row["adm2_id"])
            else:
                self.assertFalse(row["shape_id"], "%s declares no geometry but names a "
                                                  "shape" % row["adm2_id"])

    def test_a_shared_shape_is_shared_by_declared_subdivisions(self):
        """Karachi's one polygon carries seven census districts; that many-to-one is the
        design, and it must be visible as part_of rows rather than as duplicates."""
        karachi_members = [r for r in self.canonical.values()
                          if r["shape_name"] == "Karachi"]
        # Seven census subdivisions plus the pre-subdivision legacy district itself, which
        # historical BoS panels still name.
        self.assertEqual(len(karachi_members), 8)
        self.assertEqual(sorted(r["geometry_relation"] for r in karachi_members),
                         ["legacy_aggregate"] + ["part_of"] * 7)


class TestTotalResolution(unittest.TestCase):
    """The point of the package: no district string in the repository resolves nowhere."""

    def test_every_live_district_string_resolves(self):
        failures = []
        seen = 0
        for relative, column in LIVE_DISTRICT_FILES:
            names = {r[column] for r in _rows(relative) if r.get(column)}
            seen += len(names)
            for name in sorted(names):
                try:
                    adm2.resolve(name)
                except KeyError:
                    failures.append("%s: %r" % (relative, name))
        self.assertGreater(seen, 300, "the sweep read almost nothing")
        self.assertFalse(failures, "district names resolving nowhere:\n  "
                         + "\n  ".join(failures))

    def test_every_geojson_name_resolves(self):
        with open(asset_path(DATA, "gis", "PAK_ADM2.geojson"), encoding="utf-8") as handle:
            names = [f["properties"]["shapeName"] for f in json.load(handle)["features"]]
        for name in names:
            adm2.resolve(name)      # raises on failure

    def test_the_engine_residual_row_resolves(self):
        self.assertEqual(adm2.resolve("Other (GB/AJK/ICT residual)"), "other_residual")

    def test_resolution_lands_in_the_right_province(self):
        """A crosswalk row pointing at the wrong province would misallocate silently."""
        canonical = adm2.load_canonical()
        problems = []
        for relative, column in LIVE_DISTRICT_FILES:
            for row in _rows(relative):
                if not row.get(column) or not row.get("province"):
                    continue
                unit = canonical[adm2.resolve(row[column])]
                if unit["province_id"] != row["province"]:
                    problems.append("%s: %s is %s here, %s canonically"
                                    % (relative, row[column], row["province"],
                                       unit["province_id"]))
                    break               # one per file is enough to fail on
        self.assertFalse(problems, "\n".join(problems))

    def test_an_unknown_name_raises_with_the_remedy(self):
        with self.assertRaises(KeyError) as ctx:
            adm2.resolve("Atlantis District")
        self.assertIn("adm2_crosswalk", str(ctx.exception))

    def test_the_old_alias_file_is_subsumed(self):
        """The 20-row waste alias file predates this package; every mapping it makes must
        agree with the crosswalk, or two bridges disagree about one district."""
        aliases = _rows("data/activity/waste/district_aliases.csv")
        self.assertGreater(len(aliases), 10)
        for row in aliases:
            self.assertEqual(adm2.resolve(row["source_name"]),
                             adm2.resolve(row["engine_district"]),
                             "alias %r disagrees with the crosswalk" % row["source_name"])


if __name__ == "__main__":
    unittest.main()
