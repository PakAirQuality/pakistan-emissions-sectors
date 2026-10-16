"""The reporting-sector axis: where IPCC 2006 files each stream, beside the module that computes it.

The one stream that moves is captive gas self-generation - 1.A.2 autoproducer generation, computed
in the power module. Every claim here is a conservation claim: the axis REGROUPS and never invents,
so the power bar must lose exactly what the industry bar gains, in every period and at every grain
that carries the column. The consequence it exposes is not comfortable and is asserted on purpose:
filing captive generation where the Guidelines file it makes the industrial decline LARGER, because
captive generation fell too.

Since rc54 the district tables answer the axis too: the cube keys its accumulator on the pair
(module, reporting_sector), so the same question has the same answer at national, provincial and
district grain. rc53 refused it at district grain instead, which was the honest move while the
district mass really was module-resolved - and the wrong one to leave standing, because it left the
product saying "industry" twice with two different meanings.
"""
import csv
import os
import unittest
from collections import defaultdict
from decimal import Decimal

import pakemis_query.errors as E
from pakemis_query.models import QueryEmissions
from pkinv.paths import DATA, OUTPUTS
from pkinv.core import configurations as conf
from pkinv.report import reporting_sectors

from semantic._golden import open_engine

CAPTIVE_CATEGORY = "Captive gas self-generation (1A2)"
ATOMS = os.path.join(OUTPUTS, "pakemis_atomic_annual.csv")


def atom_rows():
    with open(ATOMS, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class Registry(unittest.TestCase):
    def test_the_vocabulary_is_the_module_vocabulary_and_nothing_else(self):
        modules = set(reporting_sectors.vocabulary())
        for r in reporting_sectors.rows():
            self.assertIn(r["module"], modules)
            self.assertIn(r["reporting_sector"], modules)

    def test_a_rationale_is_required_exactly_where_the_axis_differs(self):
        differ = [r for r in reporting_sectors.rows() if r["reporting_sector"] != r["module"]]
        self.assertEqual([(r["module"], r["category"]) for r in differ], [("power", CAPTIVE_CATEGORY)])
        for r in reporting_sectors.rows():
            self.assertEqual(bool(r["rationale"].strip()), r["reporting_sector"] != r["module"],
                             "%s / %s" % (r["module"], r["category"]))
        self.assertIn("1.A.2", differ[0]["rationale"])

    def test_every_stream_resolves_and_every_row_matches_a_stream(self):
        """Both directions: a stream the registry does not declare RAISES at build time, and a row
        that matches nothing is a dead row nobody would notice going stale."""
        rows = reporting_sectors.rows()
        streams = {(r["sector_id"], r["category"], r["subitem"]) for r in atom_rows()}
        used = set()
        for module, category, subitem in streams:
            value = reporting_sectors.resolve(rows, module, category, subitem)
            self.assertIn(value, set(reporting_sectors.vocabulary()))
            used.add((module, category))
        for r in rows:
            self.assertIn((r["module"], r["category"]), used,
                          "dead registry row: %s / %s" % (r["module"], r["category"]))

    def test_an_unresolved_ipcc_code_keeps_its_module(self):
        """Railways' '1.A.2/1.A.4.c' and transport's mixed off-road are declared splits that the
        source does not publish. An unresolved allocation is not re-keyed on a guess."""
        by_cat = {(r["sector_id"], r["category"]): r["ipcc_code"] for r in atom_rows()}
        rows = reporting_sectors.rows()
        for (module, category), code in by_cat.items():
            if "/" in code or code == "1.A.4.c":
                self.assertEqual(reporting_sectors.resolve(rows, module, category, ""), module,
                                 "%s (%s) was re-keyed off an unresolved code" % (category, code))


class Conservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()
        cls.periods = tuple(p["period_id"] for p in cls.engine.release.dim("dim_period") if p["basis"] == "fiscal")

    def _cells(self, key, **kw):
        out = self.engine.query_emissions(QueryEmissions(periods=self.periods, group_by=("period_id", key), **kw))
        return {(c["group"]["period_id"], c["group"][key]): Decimal(c["exact"]) for c in out["values"]}, out

    def _captive(self):
        captive = defaultdict(Decimal)
        for r in atom_rows():
            if r["category"] == CAPTIVE_CATEGORY and conf.canonical(r["configuration_id"]) == conf.REFERENCE:
                captive[r["period_id"]] += Decimal(r["co2e_Mt_AR5"] or "0")
        return captive

    def test_the_two_partitions_sum_to_the_same_national_total_every_period(self):
        mods, _ = self._cells("sector_id")
        reps, out = self._cells("reporting_sector")
        for period in self.periods:
            m = sum(v for (p, _), v in mods.items() if p == period)
            r = sum(v for (p, _), v in reps.items() if p == period)
            self.assertEqual(m, r, period)
        self.assertIn("reporting_sector_view", [l["id"] for l in out["limitations_hit"]])

    def test_power_loses_exactly_what_industry_gains(self):
        mods, _ = self._cells("sector_id")
        reps, _ = self._cells("reporting_sector")
        captive = self._captive()
        for period in self.periods:
            self.assertGreater(captive[period], 0, period)
            self.assertEqual(reps[(period, "industry")] - mods[(period, "industry")], captive[period], period)
            self.assertEqual(mods[(period, "power")] - reps[(period, "power")], captive[period], period)
            for sector in {s for (_, s) in mods} - {"industry", "power"}:
                self.assertEqual(mods[(period, sector)], reps[(period, sector)], "%s %s" % (period, sector))

    def test_reference_start_and_latest_levels_match_current_source_atoms(self):
        reps, _ = self._cells("reporting_sector")
        controls = defaultdict(Decimal)
        for row in atom_rows():
            if conf.canonical(row["configuration_id"]) != conf.REFERENCE:
                continue
            module = row["sector_id"]
            if module not in ("industry", "power"):
                continue
            reported = "industry" if row["category"] == CAPTIVE_CATEGORY else module
            controls[row["period_id"], reported] += Decimal(row["co2e_Mt_AR5"] or "0")
        for period in ("FY2015-16", "FY2023-24", "FY2024-25"):
            for sector in ("industry", "power"):
                self.assertEqual(reps[period, sector], controls[period, sector])

    def test_filing_captive_where_the_guidelines_file_it_makes_the_decline_larger(self):
        """The finding the axis exists to expose, asserted so it cannot quietly reverse: the narrow
        module bar UNDERSTATES the fall it is accused of overstating."""
        mods, _ = self._cells("sector_id")
        reps, _ = self._cells("reporting_sector")
        module_change = mods[("FY2023-24", "industry")] - mods[("FY2015-16", "industry")]
        reporting_change = reps[("FY2023-24", "industry")] - reps[("FY2015-16", "industry")]
        self.assertLess(reporting_change, module_change)
        captive = self._captive()
        self.assertEqual(reporting_change - module_change,
                         captive["FY2023-24"] - captive["FY2015-16"])

    def test_the_economic_view_is_built_on_the_axis_not_a_second_rule(self):
        reps, _ = self._cells("reporting_sector")
        econ, _ = self._cells("economic_sector")
        for period in self.periods:
            self.assertEqual(econ[(period, "industrial")],
                             reps[(period, "industry")] + reps[(period, "ippu")], period)

    def test_the_filter_equals_the_group_cell(self):
        reps, _ = self._cells("reporting_sector")
        out = self.engine.query_emissions(QueryEmissions(periods=("FY2023-24",), reporting_sectors=("industry",)))
        self.assertEqual(Decimal(out["values"][0]["exact"]), reps[("FY2023-24", "industry")])

    def test_the_axis_holds_at_provincial_grain(self):
        out = self.engine.query_emissions(QueryEmissions(
            periods=("FY2023-24",), geography_level="adm1", group_by=("reporting_sector",)))
        cells = {c["group"]["reporting_sector"]: Decimal(c["exact"]) for c in out["values"]}
        mod = self.engine.query_emissions(QueryEmissions(
            periods=("FY2023-24",), geography_level="adm1", group_by=("module",)))
        by_module = {c["group"]["module"]: Decimal(c["exact"]) for c in mod["values"]}
        self.assertEqual(sum(cells.values()), sum(by_module.values()))
        self.assertGreater(cells["industry"], by_module["industry"])
        self.assertLess(cells["power"], by_module["power"])

    def test_the_district_tables_answer_the_axis_now(self):
        """rc53 REFUSED this, on the ground that the district tables were module-resolved and
        answering would return the industry module alone. rc54 removes the ground rather than the
        refusal: the cube keys its district accumulator on (module, reporting_sector), so the
        district mass is partitioned exactly and the same question has the same answer at every
        grain. That last clause is the point - it is the inconsistency the axis was meant to end."""
        national, _ = self._cells("reporting_sector")
        # to the spatial layer's own precision: the district products print at "%.12g", which is
        # why every closure test in the spatial family compares ratios at places=6 rather than
        # bit-equality. The claim is that the grains agree, not that they are byte-identical.
        for level in ("adm1", "adm2"):
            out = self.engine.query_emissions(QueryEmissions(
                periods=("FY2023-24",), geography_level=level, group_by=("reporting_sector",)))
            cells = {c["group"]["reporting_sector"]: Decimal(c["exact"]) for c in out["values"]}
            for sector in ("industry", "power"):
                self.assertAlmostEqual(float(cells[sector] / national[("FY2023-24", sector)]), 1.0,
                                       places=7, msg="%s %s" % (level, sector))

    def test_the_district_partition_moves_exactly_the_captive_mass(self):
        """And it moves the MEASURED district vector - a point allocation over the geocoded captive
        plants - not a proportional share of the power module's districts."""
        out = self.engine.query_emissions(QueryEmissions(
            periods=("FY2023-24",), geography_level="adm2", group_by=("module", "reporting_sector")))
        by = {(c["group"]["module"], c["group"]["reporting_sector"]): Decimal(c["exact"])
              for c in out["values"]}
        self.assertIn(("power", "industry"), by)
        self.assertAlmostEqual(float(by[("power", "industry")] / self._captive()["FY2023-24"]), 1.0,
                               places=7)
        self.assertGreater(by[("power", "power")], by[("power", "industry")])


if __name__ == "__main__":
    unittest.main()
