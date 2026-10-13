"""The air panel's numbers and the air panel's absences must be joinable.

WHY THIS TEST EXISTS. The semantic layer publishes the nine-year provincial air panel
(fact_air_adm1_year) keyed on sector_id, and it publishes the completeness matrix
(fact_completeness) keyed on a prose category. Every one of the thirty (air) completeness
rows carried a BLANK engine_category, so there was no key between them at all: a reader
asking the layer for power SO2 in Sindh in FY2021-22 got 4.47 kt, while the NE for "Air
pollutants - power generation, as actually emitted" - the row saying that power SO2 as
actually emitted is not estimated, pending a control-device inventory - sat in another table
with nothing linking the two. An assistant serving that layer could only connect them by
parsing English, and would answer the most contested cell in the panel with a bare number.

The fix is a declared sector_id on every (air) row. This holds it: the map must cover every
air row, and it must name only sectors the air panel actually publishes, so a new air
category cannot arrive unkeyed and a typo cannot point at a sector that does not exist.

WHAT THIS DOES NOT DO. It does not make the assistant consult completeness - that is a
question about the assistant's prompt and tool use, which lives in the explorer repository
and cannot be tested from here. What it does is remove the excuse: the join is now
mechanical, so a caveat that fails to reach a reader is a choice about how the layer is
queried rather than a missing column.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

COMPLETENESS = os.path.join(ROOT, "outputs", "completeness.csv")
AIR_PANEL = os.path.join(ROOT, "outputs", "semantic", "fact_air_adm1_year.csv")
SEMANTIC_COMPLETENESS = os.path.join(ROOT, "outputs", "semantic", "fact_completeness.csv")


class TestEveryAirAbsenceCanBeJoinedToTheAirPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(COMPLETENESS):
            raise unittest.SkipTest("completeness.csv has not been built in this checkout")
        cls.rows = read_rows(COMPLETENESS)
        cls.air = [r for r in cls.rows if r["code"] == "(air)"]

    def test_every_air_row_carries_a_sector_key(self):
        unkeyed = sorted(r["category"] for r in self.air if not r.get("sector_id"))
        self.assertFalse(
            unkeyed,
            "these (air) completeness rows have no sector_id, so nothing in the semantic "
            "layer can join them to the air panel: %s" % unkeyed)

    def test_the_air_sectors_are_sectors_the_panel_publishes(self):
        if not os.path.exists(AIR_PANEL):
            self.skipTest("the air panel has not been built in this checkout")
        published = {r["sector_id"] for r in read_rows(AIR_PANEL)}
        named = {r["sector_id"] for r in self.air if r.get("sector_id")}
        unknown = sorted(named - published)
        self.assertFalse(
            unknown,
            "the completeness map names sectors the air panel does not publish: %s. Either "
            "the key is a typo or the panel lost a sector." % unknown)

    def test_the_power_so2_absence_is_reachable_from_the_panels_own_key(self):
        """The case that motivated this: the panel's most contested cell.

        Asserted specifically, not just structurally, because the general test would pass a
        layer in which this particular row had quietly lost its NE.
        """
        hits = [r for r in self.air
                if r.get("sector_id") == "power" and r["notation_key"] == "NE"
                and "SO2" in r["gas"]]
        self.assertTrue(
            hits,
            "no power-sector air row is both NE and about SO2. The release declares power "
            "SO2 as actually emitted unestimated pending a control-device inventory; if "
            "that has changed, the provincial comparison in Section 10 needs restating.")
        self.assertTrue(
            any(h["gap_id"] for h in hits),
            "the power SO2 absence carries no gap_id, so a reader cannot find what would "
            "close it: %s" % [h["category"] for h in hits])

    def test_the_semantic_layer_carries_the_key_through(self):
        """A column added to completeness.csv is useless if the fact table drops it."""
        if not os.path.exists(SEMANTIC_COMPLETENESS):
            self.skipTest("the semantic layer has not been built in this checkout")
        rows = read_rows(SEMANTIC_COMPLETENESS)
        self.assertIn("sector_id", rows[0],
                      "fact_completeness does not carry sector_id, so the join is not "
                      "available to anything reading the semantic layer")
        air = [r for r in rows if r["code"] == "(air)"]
        self.assertTrue(air, "the semantic completeness fact has no (air) rows")
        self.assertFalse(
            [r["category"] for r in air if not r["sector_id"]],
            "(air) rows reach the semantic layer without a sector_id")

    def test_every_air_sector_in_the_panel_has_at_least_one_completeness_row(self):
        """The other direction: a sector reporting air numbers with nothing said about it."""
        if not os.path.exists(AIR_PANEL):
            self.skipTest("the air panel has not been built in this checkout")
        published = {r["sector_id"] for r in read_rows(AIR_PANEL)}
        named = {r["sector_id"] for r in self.air if r.get("sector_id")}
        silent = sorted(published - named)
        self.assertFalse(
            silent,
            "these sectors publish air numbers and have no (air) completeness row at all, "
            "so nothing in the layer says what they do and do not cover: %s" % silent)


if __name__ == "__main__":
    unittest.main()
