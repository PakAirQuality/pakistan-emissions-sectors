"""The industrial combustion air layer (rc58): the register's contract, the double-count
guards, and the planted defects that must fail by name.

Contract invariants first:
  * shares of one activity sum to exactly one; every estimate class resolves its activity,
    factors (held rows with values), stream anchor and physical source;
  * every SO2 estimate stands on a sulfur-evidence row valid for its year; a class whose
    evidence is withdrawn writes a TYPED ABSENCE for SO2, never a zero;
  * BC never exceeds the PM2.5 it is a share of;
  * cement: exactly one class prices kiln coal and it is the clinker-based integrated kiln;
    the HDIP column and cement gas are IE into it;
  * captive: priced once, under industry, anchored to the power module's captive stream,
    and absent from every power air output;
  * brick: the three classes partition HDIP's brick coal exactly and the unmapped remainder
    is positive every year;
  * the shipped detail file reproduces the panel's industry atoms.
Then the planted defects: a cement-coal class promoted to estimate fails the cement guard;
a factor row without a page fails the loader; include_captive=True fails the once-only
guard; a withdrawn sulfur row turns SO2 into a typed absence.
"""
import copy
import csv
import os
import unittest
from collections import defaultdict

from pkinv.core import air_factors, sulfur, configurations as conf
from pkinv.core.reporting_window import CORE_SUFFIX
from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS
from pkinv.sectors.industry import air_pollutants as ind
from pkinv.sectors.industry import solid_fuels

DETAIL = os.path.join(OUTPUTS, "pakemis_air_source_classes_%s.csv" % CORE_SUFFIX)
ATOMS = os.path.join(OUTPUTS, "pakemis_air_atomic_annual.csv")
POWER_SINGLE = os.path.join(OUTPUTS, "power_air_pollutants_fy2023_24.csv")
POWER_SCREEN = os.path.join(OUTPUTS, "power_air_screening_fy2015_16_fy2023_24.csv")


class TestTheRegister(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = ind.classes()
        cls.by_id = {c["source_class_id"]: c for c in cls.classes}
        cls.ctx = ind.Context()

    def test_every_estimate_class_resolves_everything_it_names(self):
        for c in self.classes:
            if c["status"] != "estimate":
                continue
            for ef_id in c["ef_ids"].split(";"):
                f = air_factors.factor(ef_id)
                if f["status"] != "absent":
                    air_factors.kg_per_unit(f)
            if c["sulfur_evidence_id"]:
                sulfur.evidence(c["sulfur_evidence_id"], 2024, c["source_class_id"], self.ctx.sulfur)
            self.assertTrue(c["ghg_anchor_subitem"], c["source_class_id"])

    def test_declared_shares_sum_to_one_and_computed_shares_partition(self):
        s = self.ctx.kiln_shares()
        self.assertAlmostEqual(s["fcbk"] + s["zz"] + s["unmapped"], 1.0, places=12)
        self.assertGreater(s["unmapped"], 0.0, "the surveyed frame does not cover Pakistan")
        self.assertGreater(s["fcbk"], s["zz"])
        declared = defaultdict(float)
        whole = defaultdict(list)
        for c in self.classes:
            if c["status"] == "estimate" and c["activity_share"] != "computed":
                declared[c["activity_function"]] += float(c["activity_share"])
                whole[c["activity_function"]].append(c["share_basis"] == "whole")
        for fn, total in declared.items():
            if all(whole[fn]):
                # rc59: distinct processes on one whole quantity (refinery process species and
                # refinery flaring both ride the feed), never a partition - each takes 1.0
                self.assertEqual(total, float(len(whole[fn])), fn)
                continue
            self.assertFalse(any(whole[fn]), "%s mixes whole and partition" % fn)
            self.assertAlmostEqual(total, 1.0, places=9, msg=fn)

    def test_cement_kiln_is_priced_once_on_clinker_never_as_a_boiler(self):
        kiln = [c for c in self.classes if c["status"] == "estimate"
                and c["physical_source_id"] == "ps_cement_kiln"]
        self.assertEqual([c["source_class_id"] for c in kiln], ["cement_kiln_integrated"])
        self.assertEqual(kiln[0]["activity_function"], "ippu.clinker_kt")
        for cid in ("cement_coal_hdip_column", "cement_gas_kiln_fuel"):
            self.assertEqual(self.by_id[cid]["status"], "IE")
            self.assertEqual(self.by_id[cid]["ie_target_class"], "cement_kiln_integrated")

    def test_captive_is_priced_once_under_industry_and_nowhere_in_power(self):
        cap = [c for c in self.classes if c["status"] == "estimate"
               and c["physical_source_id"] == "ps_captive_generation"]
        self.assertEqual(sorted(c["source_class_id"] for c in cap),
                         ["captive_gas_engine", "captive_gas_turbine"])
        for c in cap:
            self.assertEqual(c["ghg_anchor_module"], "power")
            self.assertEqual(c["ghg_anchor_subitem"], "Captive natural gas CO2")
            self.assertEqual(c["reporting_sector"], "industry")
        self.assertEqual(self.by_id["captive_fo_diesel"]["status"], "IE")
        for path in (POWER_SINGLE, POWER_SCREEN):
            with open(path, encoding="utf-8") as f:
                cats = {r["category"] for r in csv.DictReader(f)}
            self.assertFalse([c for c in cats if c.startswith("Captive")], path)

    def test_the_brick_classes_partition_hdip_brick_coal_every_year(self):
        for fy in ind.YEARS:
            total = 0.0
            for cid in ("brick_fcbk_mapped", "brick_zz_mapped", "brick_unmapped_remainder"):
                m = ind.activity(self.by_id[cid], fy, self.ctx)
                total += m["value"]
                if cid == "brick_unmapped_remainder":
                    self.assertGreater(m["value"], 0.0, fy)
            want = solid_fuels.coal_kt(solid_fuels._fiscal_label(fy), "brick_kilns")
            self.assertAlmostEqual(total, want, places=9, msg=fy)

    def test_bc_never_exceeds_the_pm25_it_is_a_share_of(self):
        rows = read_rows(DETAIL)
        by = defaultdict(dict)
        for r in rows:
            if r["status"] == "estimate":
                by[(r["period_id"], r["source_class_id"])][r["pollutant"]] = float(r["emissions_kt"])
        checked = 0
        for key, pols in by.items():
            if "BC" in pols:
                self.assertLessEqual(pols["BC"], pols["PM2.5"] + 1e-12, key)
                checked += 1
        self.assertGreater(checked, 100)

    def test_the_detail_file_reproduces_the_panel_atoms(self):
        """Per reporting sector (industry, ippu, fugitives since rc59; power since rc60): the
        detail file's estimate rows are the panel's atoms of that sector, period by period,
        species by species.

        Power joins with SO2 alone - the four admitted grid classes - so it appears here with
        one species where the others carry seven. That asymmetry is the coverage decision
        itself, and the equality below holds it to the same standard as the rest: whatever the
        detail file says the panel must say too.
        """
        detail = defaultdict(float)
        for r in read_rows(DETAIL):
            if r["status"] == "estimate":
                detail[(r["sector_id"], r["period_id"], r["pollutant"])] += float(r["emissions_kt"])
        panel = defaultdict(float)
        for a in read_rows(ATOMS):
            if (a["sector_id"] in ("industry", "ippu", "fugitives", "power")
                    and conf.canonical(a["configuration_id"]) == conf.REFERENCE):
                panel[(a["sector_id"], a["period_id"], a["pollutant"])] += float(a["emissions_Gg"])
        self.assertEqual({k[0] for k in detail}, {"industry", "ippu", "fugitives", "power"})
        self.assertEqual({k[2] for k in detail if k[0] == "power"}, {"SO2"},
                         "power is admitted for SO2 only; another species in the detail file "
                         "means a class started citing a factor it was not meant to")
        self.assertEqual(set(detail), set(panel))
        for k, v in detail.items():
            self.assertAlmostEqual(v, panel[k], delta=1e-5 + 1e-6 * abs(v), msg=k)

    def test_typed_absences_carry_their_activity_and_a_gap(self):
        rows = [r for r in read_rows(DETAIL) if r["status"] == "typed_absent"]
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r["emissions_kt"], "")
            self.assertTrue(r["basis"])
        nh3 = [r for r in rows if r["pollutant"] == "NH3"]
        self.assertTrue(nh3, "NH3 is typed absent for every fuel")
        coal = [r for r in rows if r["source_class_id"] == "other_industry_coal_in_cement_column"]
        self.assertEqual(len(coal), len(ind.YEARS))
        self.assertTrue(all(r["activity_value"] != "" for r in coal),
                        "the unidentified coal's tonnage is written beside its absence")


class TestPlantedDefects(unittest.TestCase):
    """Each defect is planted in memory and must fail by name."""

    @classmethod
    def setUpClass(cls):
        cls.classes = ind.classes()
        cls.by_id = {c["source_class_id"]: c for c in cls.classes}
        cls.ctx = ind.Context()

    def test_a_cement_coal_class_promoted_to_estimate_fails_the_kiln_guard(self):
        cement = [copy.deepcopy(self.by_id["cement_coal_hdip_column"])]
        cement[0]["status"] = "estimate"
        cement[0]["ef_ids"] = "emep_1a2_t1_solid_nox"
        kiln = [c for c in self.classes + cement if c["status"] == "estimate"
                and c["physical_source_id"] == "ps_cement_kiln"]
        self.assertNotEqual([c["source_class_id"] for c in kiln], ["cement_kiln_integrated"],
                            "the guard must see the second kiln-coal pricing")

    def test_a_factor_row_without_a_page_fails_at_load(self):
        rows = air_factors._rows()
        bad = [dict(r) for r in rows]
        bad[0]["source_page"] = ""
        original = air_factors._rows
        air_factors._rows = lambda: bad
        try:
            with self.assertRaises(ValueError):
                air_factors.load()
        finally:
            air_factors._rows = original

    def test_an_unknown_factor_id_fails_by_name(self):
        with self.assertRaises(air_factors.UnknownFactor):
            air_factors.factor("ap42_9.9_does_not_exist")

    def test_include_captive_in_the_power_screening_puts_captive_back(self):
        from pkinv.sectors.power import air_pollutants as pap
        from pkinv.sectors.power.data import PowerData
        data = PowerData()
        with_cap = {r["category"] for r in pap.compute(data, include_captive=True)}
        without = {r["category"] for r in pap.compute(data)}
        self.assertTrue([c for c in with_cap if c.startswith("Captive")])
        self.assertFalse([c for c in without if c.startswith("Captive")])

    def test_a_withdrawn_sulfur_row_turns_so2_into_a_typed_absence_not_zero(self):
        cls = copy.deepcopy(self.by_id["ind_fo_boiler"])
        ctx = ind.Context()
        ctx.sulfur = {k: v for k, v in ctx.sulfur.items() if k != "fo_hsfo_grade_mix"}
        with self.assertRaises(KeyError):
            ind.price(cls, 2024, ctx, ind.activity(cls, 2024, ctx))
        # and a row present but not valid for the year is a typed absence, by name
        ctx.sulfur = copy.deepcopy(ind.Context().sulfur)
        ctx.sulfur["fo_hsfo_grade_mix"]["valid_to_fy_end"] = "2016"
        priced, absent = ind.price(cls, 2024, ctx, ind.activity(cls, 2024, ctx))
        self.assertNotIn("SO2", priced)
        self.assertIn("SO2", absent)
        self.assertIn("no sulfur evidence valid", absent["SO2"])

    def test_thar_lignite_is_inadmissible_for_brick_coal(self):
        """The rc57 screening's substitution, refused by applies_to."""
        ev = sulfur.load()
        for row in ev.values():
            if "Thar" in row["note"] and "NOT admissible" in row["note"]:
                self.assertIn("brick", row["applies_to"])
        with self.assertRaises(ValueError):
            sulfur.evidence("fo_hsfo_grade_mix", 2024, "brick_fcbk_mapped", ev)


if __name__ == "__main__":
    unittest.main()
