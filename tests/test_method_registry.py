"""rc39 A7: every estimated agriculture atom names the equation that produced it.

Every row of the annual product carried method_id=unresolved and
uncertainty_model_id=unresolved - 1,672 of 1,672, repo-wide. The equations were never
unknown: each module's docstring names the one it implements. They simply never reached the
published atom, so a reader could not tell Eq 10.19 from Eq 11.13 without opening the source.

Agriculture is now fully resolved, 306 of 306 atoms. The other nine sectors remain unresolved
and are COUNTED rather than quietly left: report_coverage() publishes the share, because a
registry that silently defaulted would turn an unanswered question into a plausible answer.
"""
import collections
import csv
import os
import unittest

from _support import OUTPUTS, read_rows

from pkinv.report import method_registry

UNRESOLVED = "unresolved"


def _atoms():
    return read_rows(os.path.join(OUTPUTS, "pakemis_atomic_annual.csv"))


class TestAgricultureIsFullyResolved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _atoms()
        cls.ag = [r for r in cls.rows
                  if r["sector_id"] == "agriculture" and r["co2e_Mt_AR5"] not in ("", None)]

    def test_the_sweep_found_atoms(self):
        self.assertGreater(len(self.ag), 100)

    def test_every_agriculture_atom_names_a_method(self):
        stray = sorted({(r["category"], r["subitem"]) for r in self.ag
                        if r["method_id"] == UNRESOLVED})
        self.assertFalse(stray, "agriculture atoms with no method: %s" % stray)

    def test_every_agriculture_atom_names_an_uncertainty_model(self):
        stray = sorted({(r["category"], r["subitem"]) for r in self.ag
                        if r["uncertainty_model_id"] == UNRESOLVED})
        self.assertFalse(stray, "agriculture atoms with no uncertainty model: %s" % stray)

    def test_the_coverage_is_published_and_complete_for_agriculture(self):
        resolved, total = method_registry.report_coverage(self.rows)["agriculture"]
        self.assertEqual(resolved, total)

    def test_manures_three_methods_are_three_equations(self):
        """The reason the registry keys on subitem and not on category alone: 3.A.2's CH4,
        direct N2O and indirect N2O are different equations on the same animals, so a
        category-level key would have had to pick one and mislabel the other two."""
        methods = {r["subitem"]: r["method_id"] for r in self.ag
                   if r["category"] == "Manure management"}
        self.assertEqual(methods["Direct N2O"],
                         "ipcc2006_v4_ch10_eq10.25_manure_direct_n2o")
        self.assertEqual(methods["Indirect N2O (volatilisation)"],
                         "ipcc2006_v4_ch10_eq10.26_manure_indirect_n2o")
        self.assertEqual(methods["buffalo (CH4)"],
                         "ipcc2006_v4_ch10_eq10.23_manure_ch4")

    def test_soils_direct_and_indirect_are_not_one_method(self):
        methods = {r["subitem"]: r["method_id"] for r in self.ag
                   if r["category"] == "Managed soils"}
        self.assertIn("eq11.1", methods["Direct N2O - organic manure"])
        self.assertIn("eq11.9", methods["Indirect N2O - volatilisation (organic manure)"])
        self.assertIn("eq11.10", methods["Indirect N2O - leaching/runoff (organic manure)"])


class TestEverySectorIsResolved(unittest.TestCase):
    def test_every_estimated_atom_names_its_method_and_model(self):
        """rc39 resolved agriculture and counted the other nine as unresolved (1,366 of
        1,672 atoms); rc41 (the nineteenth review's P-1) scopes the registry by sector and
        gas and names every engine's equation, so the count is zero everywhere and stays
        zero - an atom whose method the registry cannot name fails the build here."""
        coverage = method_registry.report_coverage(_atoms())
        self.assertGreaterEqual(len(coverage), 10)
        for sector, (resolved, total) in sorted(coverage.items()):
            self.assertEqual(resolved, total, "%s: %d of %d atoms resolved" % (sector, resolved, total))
        stray = sorted({(r["sector_id"], r["category"], r["subitem"], r["gas"]) for r in _atoms()
                        if r["co2e_Mt_AR5"] not in ("", None)
                        and (r["method_id"] == UNRESOLVED or r["uncertainty_model_id"] == UNRESOLVED)})
        self.assertEqual(stray, [])


class TestFieldBurningIsE3(unittest.TestCase):
    """The module's own comment block said E3 - "production times a residue ratio times a
    burned fraction, three assumptions deep" - and no override existed, so both rows fell to
    the module default of E2. E2 claims "a published statistic for this source and period";
    nobody publishes Pakistan's burned residue mass."""

    def test_both_burning_rows_are_e3(self):
        rows = [r for r in _atoms()
                if r["sector_id"] == "agriculture" and r["ipcc_code"] == "3.C.1.b"
                and r["co2e_Mt_AR5"] not in ("", None)]
        self.assertTrue(rows)
        self.assertEqual({r["evidence_class"] for r in rows}, {"E3"})


class TestLivestockNitrogenIsNotSourcedToAFertiliserAnnexe(unittest.TestCase):
    """Seven streams attributed livestock nitrogen to NFDC's synthetic-fertiliser annexe:
    manure management's indirect N2O, and in managed soils the volatilisation and leaching
    streams of organic manure and of pasture deposition. Their DIRECT counterparts were
    sourced to the census, so the same nitrogen carried two provenances depending on which
    side of the volatilisation step it sat on."""

    @classmethod
    def setUpClass(cls):
        cls.streams = [r for r in read_rows(os.path.join(OUTPUTS,
                                                         "pakemis_source_streams.csv"))
                       if r["module"] == "agriculture"]

    def test_only_synthetic_fertiliser_streams_carry_the_annexe(self):
        wrong = sorted(r["sub_category"] for r in self.streams
                       if "nfdc_fertilizer_review_annex7" in r["source_id"]
                       and "synthetic" not in r["sub_category"])
        self.assertFalse(wrong, "livestock nitrogen sourced to the fertiliser annexe: %s"
                                % wrong)

    def test_manure_indirect_rides_the_census(self):
        row = next(r for r in self.streams
                   if r["ipcc_code"] == "3.C.6")
        self.assertEqual(row["source_id"], "pbs_agricultural_census_and_economic_survey")

    def test_urea_names_the_document_its_mass_comes_from(self):
        """3.C.3 (urea) claimed the agricultural census and listed crops and livestock files -
        neither of which contains a tonne of urea."""
        row = next(r for r in self.streams if r["ipcc_code"] == "3.C.3")
        self.assertEqual(row["source_id"], "nfdc_annex5_national_offtake")
        self.assertIn("annex5", row["source_document_ids"])


if __name__ == "__main__":
    unittest.main()
