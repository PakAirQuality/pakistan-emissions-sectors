"""A limitation sentence may not say what the release's own tables contradict.

The limitations are hand-written sentences served with every answer. A review of the public
explorer in 2026-10 found eight of them describing an earlier release than the one they
shipped in:

    air_history_national_only   "provinces and districts carry CY2024 alone"  - nine fiscal years
    air_spatial_not_in_layer    industry, IPPU, fugitives "have no air layer" - all three do
    air_beta                    "ten sectors"                                - nine, then ten
    air_sector_ne               "power has no covered air estimate"          - SO2 was admitted
    grid_not_tabular            "the two NetCDF products"                    - six
    ar6_adm2_ne                 AR6 "at ADM1 stream grain"                   - the year table is AR5
    adm2_history_annual_only    "1,102 of 1,672 live stream-years"           - the count moved twice
    reporting_sector_view       district tables "do not carry the column"    - they do

None was a number in a table, so no closure test could see it. Each claim is now either made
from the table (the NetCDF file's sector list) or stated without the detail that drifts, and
this module holds every one to the table it is about. A sentence may not quote a count that
a table could contradict; it points at the table.
"""
import csv
import json
import os
import re
import unittest

from pkinv.core.io import read_rows

ROOT = os.path.join(os.path.dirname(__file__), "..")
SEMANTIC = os.path.join(ROOT, "outputs", "semantic")
COUNT_WORDS = r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)"


def _header(name):
    with open(os.path.join(SEMANTIC, name + ".csv"), newline="", encoding="utf-8") as handle:
        return next(csv.reader(l for l in handle if not l.startswith("#")))


def _distinct(name, column):
    return {r[column] for r in read_rows(os.path.join(SEMANTIC, name + ".csv"))}


class TestLimitationsAgreeWithTheTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.semantic import release_json
        cls.text = {l["id"]: l["message"] for l in release_json.BASE_LIMITATIONS}
        cls.air = [m for i, m in cls.text.items() if i.startswith("air_")]

    def test_the_shipped_contract_carries_these_sentences(self):
        with open(os.path.join(SEMANTIC, "semantic_release.json"), encoding="utf-8") as handle:
            shipped = {l["id"]: l["message"] for l in json.load(handle)["known_limitations"]}
        for limitation, message in self.text.items():
            self.assertEqual(shipped.get(limitation), message, "%s: the built contract is stale" % limitation)

    def test_provinces_and_districts_carry_the_fiscal_periods(self):
        from pkinv.core.reporting_window import CORE_PERIOD_IDS
        for table in ("fact_air_adm1_year", "fact_air_adm2_year"):
            periods = _distinct(table, "period_id")
            self.assertEqual(periods, set(CORE_PERIOD_IDS), table)
        self.assertNotIn("CY2024", self.text["air_history_national_only"])
        self.assertIn("fiscal", self.text["air_history_national_only"])

    def test_no_sector_with_a_spatial_air_layer_is_called_absent(self):
        have = _distinct("fact_air_adm1_year", "sector_id") & _distinct("fact_air_adm2_year", "sector_id")
        for sector in ("industry", "ippu", "fugitives"):
            self.assertIn(sector, have)
        message = self.text["air_spatial_not_in_layer"]
        self.assertNotRegex(message, r"no air layer\s*\(")
        self.assertNotRegex(message, r"(?i)\(industry, IPPU, fugitives\)")

    def test_no_air_sentence_counts_the_sectors(self):
        """How many sectors a grain holds is a property of its table and has changed in three
        releases out of four; a sentence that states it is a sentence that will be wrong."""
        for message in self.air:
            self.assertNotRegex(message, r"(?i)\b%s sectors\b" % COUNT_WORDS, message)
        from pakemis_query.models import QueryAir
        from pakemis_query.engine import Engine
        self.assertNotRegex(QueryAir.__doc__, r"(?i)\b%s sectors\b" % COUNT_WORDS)
        self.assertNotRegex(Engine.query_air.__doc__, r"(?i)\b%s sectors (carry|with)\b" % COUNT_WORDS)

    def test_what_is_said_of_grid_power_is_what_the_panel_holds(self):
        species = {r["pollutant"] for r in read_rows(os.path.join(SEMANTIC, "fact_air_panel.csv")) if r["sector_id"] == "power"}
        for limitation in ("air_sector_ne", "air_covered_sources"):
            message = self.text[limitation]
            if species:
                self.assertNotRegex(message, r"(?i)power has no covered air estimate \(")
                for pollutant in species:
                    self.assertIn(pollutant, message, "%s does not name %s, which the panel prices for power" % (limitation, pollutant))
            else:
                self.assertNotIn("admission register", message)
        screened = {r["pollutant"] for r in read_rows(os.path.join(SEMANTIC, "fact_air_absence_screening.csv")) if r["sector_id"] == "power"}
        self.assertTrue(screened, "the screening pair the sentences point at is gone")

    def test_the_grid_sentence_counts_no_files(self):
        with open(os.path.join(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as handle:
            cubes = [p["path"] for p in json.load(handle)["products"] if p["path"].endswith(".nc")]
        self.assertGreater(len(cubes), 2)
        self.assertNotRegex(self.text["grid_not_tabular"], r"(?i)\b%s NetCDF\b" % COUNT_WORDS)
        with open(os.path.join(ROOT, "docs", "semantic_contract.md"), encoding="utf-8") as handle:
            self.assertNotRegex(handle.read(), r"(?i)\bthe two NetCDF products\b")

    def test_ar6_is_claimed_only_where_a_column_holds_it(self):
        self.assertIn("co2e_Mt_AR6", _header("fact_adm1_month"))
        self.assertNotIn("co2e_Mt_AR6", _header("fact_adm1_year"))
        self.assertNotIn("co2e_Mt_AR6", _header("fact_adm2_year"))
        message = self.text["ar6_adm2_ne"]
        self.assertIn("fact_adm1_month", message)
        self.assertIn("fact_adm1_year", message)
        self.assertNotIn("ADM1 stream grain only", message)

    def test_the_district_tables_carry_the_reporting_sector(self):
        for table in ("fact_adm2_year", "fact_adm2_month"):
            self.assertIn("reporting_sector", _header(table), table)
        self.assertNotIn("REFUSED", self.text["reporting_sector_view"])
        self.assertNotIn("do not carry the column", self.text["reporting_sector_view"])

    def test_no_sentence_quotes_a_count_of_stream_years(self):
        for limitation, message in self.text.items():
            self.assertNotRegex(message, r"[\d,]+ of [\d,]+ live stream-years", limitation)
        # adm2_history_annual_only was retired at rc68: district months exist for every core
        # period, so there is no annual-only district history left to describe
        self.assertNotIn("adm2_history_annual_only", self.text)
        from pkinv.semantic import facts
        self.assertNotRegex(facts.fact_adm2_year.__doc__, r"For [\d,]+ of [\d,]+\s+live stream-years")


class TestTheAirGridSaysWhatItHolds(unittest.TestCase):
    def test_the_coverage_attribute_is_the_atoms_own_sector_list(self):
        from pkinv.report import air_annual_grid
        sectors = air_annual_grid.covered_sectors()
        text = air_annual_grid.coverage_scope_text(sectors)
        self.assertIn("the %d sectors" % len(sectors), text)
        for sector, species in sectors.items():
            self.assertIn(sector, text)
            if len(species) != len(air_annual_grid.POLLUTANTS):
                self.assertIn("%s (%s only)" % (sector, ", ".join(species)), text)
        try:
            from netCDF4 import Dataset
        except ImportError:
            raise unittest.SkipTest("netCDF4 not installed")
        from pkinv.core import configurations as conf
        from pkinv.core.reporting_window import CORE_PERIOD_IDS
        for cfg in conf.AIR_ALL:
            path = air_annual_grid.path_for(cfg)
            with Dataset(path) as ds:
                self.assertEqual(ds.coverage_scope, text, path)
                self.assertEqual(ds.configuration_id, cfg)
                self.assertEqual(set(map(str, ds["period_id"][:])), set(CORE_PERIOD_IDS))


if __name__ == "__main__":
    unittest.main()
