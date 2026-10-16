"""FY2025-26 stays a separate provisional extension: checked on the FINAL exports.

Independent reads of the held primary documents (not the producer's parser) for the new
NFDC full-year nitrogen witness and the OCAC edition overlaps, and a sweep of every common-core
national product for any FY2025-26 period.
"""
import collections
import csv
import os
import re
import subprocess
import unittest

from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from pkinv.core import reporting_window as window
from pkinv.report import periods
from _support import ROOT

AVAILABILITY = "outputs/pakemis_extension_source_availability.csv"
PROVISIONAL = "outputs/pakemis_fy2025_26_provisional_activity.csv"
REVISIONS = "outputs/pakemis_ocac_extension_revisions.csv"
NFDC = "data/raw/nfdc/monthly_reviews_fy2026/nfdc_mfr_2026_07.pdf"
SURVEY_AG = "data/raw/finance_division/survey_2025_26/2_Agriculture.pdf"
CORE_PRODUCTS = (
    ("outputs/pakemis_annual_fy2015_16_fy2024_25.csv", "period_label"),
    ("outputs/pakemis_ghg_configuration_atoms.csv", "period_id"),
    ("outputs/pakemis_monthly_fy2015_16_fy2024_25.csv", "period_id"),
    ("outputs/pakemis_national_series.csv", "period_label"),
    ("outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv", "period_id"),
)


def pdf_text(path):
    return subprocess.check_output(["pdftotext", "-layout", asset_path(ROOT, path), "-"],
                                   stderr=subprocess.DEVNULL).decode("utf-8", "replace")


def table(path):
    return read_rows(asset_path(ROOT, path))


class Candidacy(unittest.TestCase):
    def test_no_common_core_national_product_carries_fy2025_26(self):
        for path, field in CORE_PRODUCTS:
            full = asset_path(ROOT, path)
            if not os.path.exists(full):
                continue
            with open(full, newline="", encoding="utf-8") as handle:
                lines = (l for l in handle if not l.startswith("#"))
                found = {r[field] for r in csv.DictReader(lines)}
            self.assertNotIn("FY2025-26", found, path)
            self.assertTrue(all(window.is_common_core(p) for p in found if p.startswith("FY")), path)
        for row in periods.rows():
            self.assertTrue(row["period_start"].endswith("-07-01") and row["period_end"].endswith("-06-30"))

    def test_provisional_emissions_have_no_aggregate_and_say_so(self):
        for row in table("outputs/pakemis_fy2025_26_provisional_emissions.csv"):
            self.assertEqual("FY2025-26", row["period"])
            self.assertNotRegex(row["source_process"].lower(), r"\b(national|total internal|all sectors)\b")
            self.assertIn("must not be called a common-scope national total", row["coverage"]) \
                if not row["source_process"].startswith("Billets") else None

    def test_nfdc_full_year_nitrogen_against_independent_reads(self):
        text = pdf_text(NFDC)
        block = text[text.index("FISCAL YEAR 2026-27 COMPARED"):]
        block = block[block.index("NITROGEN"):block.index("PHOSPHATE")]
        months = ("July", "August", "September", "October", "November", "December",
                  "January", "February", "March", "April", "May", "June")
        source = []
        for name in months:
            line = re.search(r"^%s\s+(.+)$" % name, block, re.M).group(1).split()
            source.append((float(line[2].replace(",", "")), float(line[3].replace(",", ""))))
        prior = [p for p, _ in source]
        current = [c for _, c in source]
        self.assertEqual(3387074, sum(prior))           # AFR2024-25 / Survey 3,387 kt
        final = sorted((r for r in table(PROVISIONAL) if r["activity"] == "nitrogen_N_offtake_t"),
                       key=lambda r: r["month"])
        self.assertEqual(12, len(final))
        self.assertEqual(current, [float(r["quantity"]) for r in final])
        self.assertEqual(3872787, sum(current))
        survey = re.search(r"^2025-26 P\s+([\d,]+)", pdf_text(SURVEY_AG).split("FERTILIZER OFFTAKE AND IMPORTS")[1], re.M)
        self.assertAlmostEqual(float(survey.group(1).replace(",", "")), sum(current[:9]) / 1000, delta=1)
        self.assertTrue(all("not field application" in r["boundary"] for r in final))

    def test_every_ocac_overlap_is_classified_and_the_fy2018_print_error_is_named(self):
        core = table("data/activity/transport/ocac_sectoral_annual.csv")
        editions = {int(r["fiscal_year_start"]) for r in core if r["product"] == "TOTAL_PRIOR"}
        rows = table(REVISIONS)
        periods_seen = {r["period"] for r in rows}
        for edition in editions:
            if edition - 1 in {int(r["fiscal_year_start"]) for r in core}:
                self.assertIn("FY%d-%02d" % (edition - 1, edition % 100), periods_seen)
        self.assertIn("FY2024-25", periods_seen)
        allowed = {"unchanged_printed_rounding", "correction_of_non_additive_first_print",
                   "reclassification_between_customer_classes", "level_revision"}
        self.assertTrue({r["classification"] for r in rows} <= allowed)
        road = next(r for r in rows if r["period"] == "FY2017-18" and r["customer_class"] == "Road")
        self.assertEqual("correction_of_non_additive_first_print", road["classification"])
        # The transport diagnostic independently finds the FY2017-18 edition's HSD classes
        # short of its own printed grand total by the same amount the next edition restores.
        flagged = [r for r in table("outputs/transport_ocac_control_diagnostic.csv")
                   if r["fiscal_year"] == "2017" and r["verdict"] == "NON-ADDITIVE"]
        self.assertEqual(["HSD"], [r["product"] for r in flagged])
        self.assertAlmostEqual(abs(float(flagged[0]["abs_diff"])), float(road["delta_tonnes"]), delta=2)

    def test_availability_register_is_exact_about_partial_and_absent_sources(self):
        rows = table(AVAILABILITY)
        for row in rows:
            self.assertTrue(os.path.exists(asset_path(ROOT, row["source_location"])), row["source_location"])
            if row["period"] == "FY2025-26":
                self.assertEqual("separate_provisional_extension", row["release_class"])
            if "2026-03 (9months)" in row["covered_months"] and "through2026-06" not in row["covered_months"]:
                self.assertRegex(row["actual_usability"].lower(), r"partial|july-march|jul-mar")
        livestock = next(r for r in rows if "AgriculturalCensus2024" in r["publication_edition"])
        self.assertIn("inter-census growth", livestock["actual_usability"])
        absent = [r for r in rows if r["actual_usability"].startswith("absent")]
        self.assertGreaterEqual(len(absent), 3)


if __name__ == "__main__":
    unittest.main()
