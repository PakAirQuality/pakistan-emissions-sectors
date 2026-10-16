"""The spatial products contract (docs/spatial_products_contract.md), enforced.

Three directions. The canonical tiers EXIST and the shipped-file nesting chain closes
(what a downstream user actually downloads, not the in-memory build the cube suite
tests). No canonical writer reads a research-tier file - the guard that would have
caught rc7's inversion, where the cube silently depended on a hand-run district panel.
And every research family the contract lists is real, so the doc cannot drift into
describing files that no longer exist.
"""

from pkinv.assets import asset_path
import csv
import os
import re
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT

CONTRACT = os.path.join(ROOT, "docs", "spatial_products_contract.md")

CANONICAL_NESTED = ("pakemis_grid_0p05_monthly.nc", "pakemis_adm2_monthly.csv",
                    "pakemis_adm2_monthly_sector.csv",
                    "pakemis_grid_provincial_check.csv", "pakemis_grid_fallbacks.csv",
                    "pakemis_spatial_unallocated.csv")
CANONICAL_INPUTS = ("district_totals_2024.csv", "residential_district_2024.csv",
                    "waste_district_2024.csv")
# Research-tier path fragments no canonical writer may read.
RESEARCH_FRAGMENTS = ("outputs/gis/", "outputs/districts/",
                      "railways_gis_", "residential_gis_provincial",
                      "air_pollutants_district")
CANONICAL_WRITERS = ("src/pkinv/report/grid_cube.py",
                     "src/pkinv/core/gis/cube.py",
                     "src/pkinv/sectors/agriculture/gis/district_downscale.py",
                     "src/pkinv/sectors/residential/gis/district_downscale.py",
                     "src/pkinv/sectors/waste/gis/district_downscale.py")


def _rows(name):
    # The `#` filter is not decoration: the ADM2 views carry a header comment explaining why
    # they hold no per-cell uncertainty, and reading it as data broke this file the day it
    # was added. Every other reader in the repository already skips comments.
    return read_rows(os.path.join(OUT, name))


def _numeric(rows):
    """The ADM2 views carry two declared, non-numeric absences. The vocabulary is the
    writer's, imported rather than re-spelled, so a third one cannot appear without every
    reader learning about it."""
    from pkinv.report.grid_cube import DECLARED_ABSENCES
    # rc41: an absence row leaves emissions_Gg EMPTY and names itself in absence_reason
    out = []
    for row in rows:
        if row["emissions_Gg"] in DECLARED_ABSENCES:
            continue        # the pre-rc41 form (a HEAD-baseline read of the last release)
        if row.get("absence_reason", ""):
            assert row["absence_reason"] in DECLARED_ABSENCES, row["absence_reason"]
            continue
        out.append(row)
    return out


class TestSpatialContract(unittest.TestCase):
    def test_the_canonical_set_exists(self):
        for name in CANONICAL_NESTED + CANONICAL_INPUTS:
            self.assertTrue(os.path.exists(os.path.join(OUT, name)), name)
        self.assertTrue(os.path.exists(CONTRACT))

    def test_the_shipped_nesting_chain_closes(self):
        """From the shipped CSVs alone: module x ADM2 partitions ADM2 (1e-5 Gg), and
        the canonical inputs reconcile per province against their own totals - the
        chain a downstream user can verify without running the engine."""
        agg = {}
        for row in _numeric(_rows("pakemis_adm2_monthly.csv")):
            key = (row["shape_id"], row["gas"], row["month"], row["spatial_view"])
            agg[key] = agg.get(key, 0.0) + float(row["emissions_Gg"])
        summed = {}
        for row in _numeric(_rows("pakemis_adm2_monthly_sector.csv")):
            key = (row["shape_id"], row["gas"], row["month"], row["spatial_view"])
            summed[key] = summed.get(key, 0.0) + float(row["emissions_Gg"])
        worst = max(abs(summed[k] - v) for k, v in agg.items())
        self.assertLess(worst, 1e-5)

        waste_prov = {r["province"]: float(r["co2e_Mt_AR5"])
                      for r in _rows("waste_provincial_2024.csv")}
        got = {}
        for r in _rows("waste_district_2024.csv"):
            got[r["province"]] = got.get(r["province"], 0.0) + float(r["co2e_Mt_AR5"])
        for province, total in waste_prov.items():
            self.assertAlmostEqual(got[province], total, delta=5e-4, msg=province)

    def test_the_shipped_files_carry_the_second_term(self):
        """The closure identity gained a term this release - ADM1 == ADM2 + unallocated -
        and a downstream user has to be able to see that from the download alone.

        This test exists because the one above CANNOT see the change: it compares the two
        ADM2 views against each other, and both lost the same 9.01 Mt on the same day, so
        it passed throughout. A test that cannot detect a two per cent mass removal is not
        holding the identity it claims to hold.
        """
        unallocated = _rows("pakemis_spatial_unallocated.csv")
        self.assertTrue(unallocated)
        by_gas = {}
        for row in unallocated:
            by_gas[row["gas"]] = by_gas.get(row["gas"], 0.0) + float(row["emissions_Gg"])

        # 1. It reconciles against the shipped ledger, which names the streams it covers.
        ledger = {}
        for row in _rows("pakemis_source_streams.csv"):
            if row["geometry_id"] == "S4:no-native-geometry":
                ledger[row["gas"]] = (ledger.get(row["gas"], 0.0)
                                      + float(row["emissions_native"]))
        self.assertEqual(set(by_gas), set(ledger))
        for gas, total in ledger.items():
            self.assertLess(abs(by_gas[gas] - total), max(1e-6 * total, 1e-6), gas)

        # 2. The ADM2 views point at it, per province and gas, rather than leaving a reader
        #    to discover the shortfall by subtraction.
        from pkinv.report.grid_cube import UNALLOCATED_BELOW_ADM1
        expected = {(row["province"], row["gas"]) for row in unallocated}
        for name in ("pakemis_adm2_monthly.csv", "pakemis_adm2_monthly_sector.csv"):
            marked = {(row["province"], row["gas"]) for row in _rows(name)
                      if row["absence_reason"] == UNALLOCATED_BELOW_ADM1}
            self.assertEqual(marked, expected,
                             "%s does not declare the mass it is missing" % name)

        # 3. And the ADM2 total is STRICTLY below the national total by at least that mass -
        #    the inequality that fails if the unplaced streams are placed again.
        national = {}
        for row in _rows("national_monthly_2024.csv"):
            national[row["gas"]] = (national.get(row["gas"], 0.0)
                                    + float(row["emissions_Gg"]))
        adm2 = {}
        for row in _numeric(_rows("pakemis_adm2_monthly.csv")):
            adm2[row["gas"]] = adm2.get(row["gas"], 0.0) + float(row["emissions_Gg"])
        for gas, total in national.items():
            self.assertLessEqual(adm2[gas], total - 0.98 * by_gas[gas],
                                 "%s: the ADM2 view carries mass that has no geometry "
                                 "below its province" % gas)

    def test_no_canonical_writer_reads_a_research_product(self):
        """The inversion guard: a canonical writer referencing a research-tier path
        makes the canonical family depend on a hand-run artefact again."""
        problems = []
        for relative in CANONICAL_WRITERS:
            text = open(asset_path(ROOT, relative), encoding="utf-8").read()
            code = "\n".join(line for line in text.splitlines()
                             if not line.lstrip().startswith("#"))
            for fragment in RESEARCH_FRAGMENTS:
                if fragment in code:
                    problems.append("%s references %r" % (relative, fragment))
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))

    def test_the_inversion_guard_has_teeth(self):
        """Positive control: a planted research reference is caught."""
        planted = "value = read('outputs/gis/total_co2e_2024.tif')"
        caught = any(fragment in planted for fragment in RESEARCH_FRAGMENTS)
        self.assertTrue(caught)

    def test_the_promoted_input_regenerates_in_tree(self):
        """The promoted producer is present in every shared-registry build group."""
        from pkinv.build import phases_for_group
        for group in ("dev", "ci", "full"):
            self.assertIn("pkinv.sectors.agriculture.gis.district_downscale",
                          {p.target for p in phases_for_group(group)}, group)
        for path in (".github/workflows/public-checks.yml", ".github/workflows/reproduce.yml",
                     "Makefile"):
            with open(asset_path(ROOT, path), encoding="utf-8") as handle:
                self.assertIn("python3 -m pkinv.build", handle.read(), path)

    def test_every_research_family_in_the_contract_exists(self):
        text = open(CONTRACT, encoding="utf-8").read()
        for probe in ("outputs/gis/", "outputs/districts/",
                      "railways_gis_", "air_pollutants_district"):
            self.assertIn(probe, text)
        self.assertTrue(os.path.isdir(os.path.join(OUT, "gis")))
        self.assertTrue(os.path.isdir(os.path.join(OUT, "districts")))


if __name__ == "__main__":
    unittest.main()
