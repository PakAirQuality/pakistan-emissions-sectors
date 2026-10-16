"""Tests for the OCAC sectoral-sales ingest - the transport controls' provenance.

Fast tests read the committed CSVs only; the one test that re-parses a PDF is
skipped when pdftotext is absent. The pinned cells were read independently from the
FY2021-22 PDF during the August 2026 re-anchor and verified against the printed
page; if the ingest ever drifts from them, the control totals drift with it.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import os
import shutil
import subprocess
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)
from pkinv.core.io import read_rows
from _support import ROOT

ANNUAL = asset_path(ROOT, "data", "activity", "transport", "ocac_sectoral_annual.csv")
PROV = asset_path(ROOT, "data", "activity", "transport", "ocac_sectoral_provincial.csv")


def _annual():
    return read_rows(ANNUAL, comments=False)


def _prov():
    return read_rows(PROV, comments=False)


def _cell(rows, **match):
    got = [float(r["tonnes"]) for r in rows
           if all(r[k] == str(v) for k, v in match.items())]
    if len(got) != 1:
        raise AssertionError("expected exactly one row for %s, got %d"
                             % (match, len(got)))
    return got[0]


class TestPinnedCells(unittest.TestCase):
    """Independently verified cells from the printed pages."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _annual()

    def test_the_reference_year_road_row(self):
        """FY2021-22 = inventory year 2022, the sector's reference year."""
        self.assertEqual(_cell(self.rows, inventory_year=2022, sector_row="Road",
                               product="HSD"), 7886579.0)
        self.assertEqual(_cell(self.rows, inventory_year=2022, sector_row="Road",
                               product="MS"), 8976577.0)
        self.assertEqual(_cell(self.rows, inventory_year=2022, sector_row="Road",
                               product="HOBC"), 150986.0)

    def test_the_reference_year_boundary_rows(self):
        self.assertEqual(_cell(self.rows, inventory_year=2022,
                               sector_row="Railways", product="HSD"), 118179.0)
        self.assertEqual(_cell(self.rows, inventory_year=2022,
                               sector_row="TOTAL_INTERNAL", product="HSD"),
                         8915873.0)
        self.assertEqual(_cell(self.rows, inventory_year=2022,
                               sector_row="TOTAL_INTERNAL", product="MS"),
                         9006833.0)
        # OCAC books ZERO HSD to Agriculture in every year - the customer-class
        # fact the whole diesel-boundary story rests on.
        self.assertEqual(_cell(self.rows, inventory_year=2022,
                               sector_row="AGRICULTURE", product="HSD"), 0.0)
        self.assertEqual(_cell(self.rows, inventory_year=2022,
                               sector_row="AGRICULTURE", product="LDO"), 11822.0)

    def test_other_editions_spot_cells(self):
        """The 13,232 kt figure the old note misattributed to the Economic Survey
        is the OCAC FY2023-24 Total Transport row; the first edition anchors the
        other end of the panel."""
        self.assertEqual(_cell(self.rows, inventory_year=2024,
                               sector_row="Total Transport", product="TOTAL"),
                         13232027.0)
        self.assertEqual(_cell(self.rows, inventory_year=2017, sector_row="Road",
                               product="HSD"), 7331277.0)

    def test_agriculture_hsd_is_zero_in_every_year(self):
        for r in self.rows:
            if r["sector_row"] == "AGRICULTURE" and r["product"] == "HSD":
                self.assertEqual(float(r["tonnes"]), 0.0, r["fy_label"])


class TestClosureIdentities(unittest.TestCase):
    """The structural facts the ledger and the boundary argument rest on."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _annual()

    # The FY2017-18 edition's printed national HSD total exceeds the sum of its
    # own printed class rows by exactly this amount - a source-side inconsistency
    # in that edition alone. Since rc68 the ingest books the publisher's own fix
    # (the FY2018-19 edition restores it to Road), so the identity now holds in
    # every year; the amount is pinned in the ingest's declared correction.
    FY2017_18_HSD_DISCREPANCY_T = 521822.0

    def test_customer_classes_sum_to_the_national_total(self):
        """Per year, HSD across the customer classes equals TOTAL_INTERNAL exactly
        - the identity that makes OCAC's sector rows an exhaustive partition of
        national sales, which is the claimant-exhaustiveness demonstration. The
        FY2017-18 first print failed it by 521,822 t until the correction was
        booked at rc68; the declared correction must carry exactly that amount."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ingest_ocac_sectoral", os.path.join(ROOT, "scripts", "ingest_ocac_sectoral.py"))
        ingest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ingest)
        declared = ingest.DECLARED_PUBLISHER_CORRECTIONS[(2017, "TRANSPORT", "Road", "HSD")]
        self.assertEqual(declared["gap_tonnes"], self.FY2017_18_HSD_DISCREPANCY_T)
        for year in sorted({r["inventory_year"] for r in self.rows}):
            classes = sum(_cell(self.rows, inventory_year=year, sector_row=s,
                                product="HSD")
                          for s in ("DOMESTIC", "AGRICULTURE", "Total Industry",
                                    "Total Transport", "Total Power",
                                    "Total Government"))
            total = _cell(self.rows, inventory_year=year,
                          sector_row="TOTAL_INTERNAL", product="HSD")
            self.assertAlmostEqual(total - classes, 0.0, delta=2.0, msg=year)

    def test_road_share_of_national_hsd_stays_in_the_declared_band(self):
        """The 9-year panel that bounds the unresolved retail claimants: the
        Road-share envelope quoted in the ledger and the boundary scenarios."""
        shares = []
        for year in sorted({r["inventory_year"] for r in self.rows}):
            road = _cell(self.rows, inventory_year=year, sector_row="Road",
                         product="HSD")
            total = _cell(self.rows, inventory_year=year,
                          sector_row="TOTAL_INTERNAL", product="HSD")
            shares.append(road / total)
        self.assertGreater(min(shares), 0.82)   # FY2017-18, on its printed total
        self.assertLess(max(shares), 0.92)
        # and the reference year specifically (index 6 since the recovered
        # FY2015-16 image edition prepended a year to the panel)
        self.assertAlmostEqual(shares[6], 7886579.0 / 8915873.0, places=9)


class TestProvincialPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _prov()

    def test_additive_areas_sum_to_pakistan(self):
        """Per month x product, the additive areas reproduce the PAKISTAN page
        exactly; KARACHI is a subset of SINDH and never adds."""
        # WITHIN ONE REPORT KIND. The panel now holds months whose area pages come from
        # the direct monthly editions while a cumulative national row also exists for the
        # same month; comparing monthly provinces against a period-to-date national row is
        # comparing two different quantities, which is how this test failed by exactly the
        # prior months' mass when the direct area pages arrived.
        monthly = [r for r in self.rows if r["report_kind"] == "monthly"]
        months = sorted({r["month"] for r in monthly if r["area"] != "PAKISTAN"})
        self.assertGreaterEqual(len(months), 46)
        for month in months:
            for product in ("MS", "HSD"):
                pak = _cell(monthly, month=month, area="PAKISTAN",
                            sector_row="Road", product=product)
                add = sum(float(r["tonnes"]) for r in monthly
                          if r["month"] == month and r["additive"] == "1"
                          and r["sector_row"] == "Road"
                          and r["product"] == product)
                self.assertAlmostEqual(add, pak, delta=2.0,
                                       msg="%s %s" % (month, product))

    def test_karachi_is_inside_sindh(self):
        for month in ("2021-07", "2022-03"):
            k = _cell(self.rows, month=month, area="KARACHI", sector_row="Road",
                      product="HSD")
            s = _cell(self.rows, month=month, area="SINDH", sector_row="Road",
                      product="HSD")
            self.assertLess(k, s)
            self.assertGreater(k, 0.0)

    def test_reference_year_months_are_all_direct(self):
        """All twelve FY2021-22 months are direct monthly reports - the provincial
        proxy needs no cumulative differencing."""
        fy_months = ["2021-%02d" % m for m in range(7, 13)] + \
                    ["2022-%02d" % m for m in range(1, 7)]
        for month in fy_months:
            kinds = {r["report_kind"] for r in self.rows if r["month"] == month}
            self.assertEqual(kinds, {"monthly"}, month)

    def test_monthly_sums_close_to_the_annual_road_row(self):
        """FY2021-22: twelve monthly PAKISTAN Road values close to the annual
        edition's Road row within 0.5 percent (monthly vintage vs revised annual
        - the observed gap is about 0.2 percent)."""
        annual = _annual()
        fy_months = ["2021-%02d" % m for m in range(7, 13)] + \
                    ["2022-%02d" % m for m in range(1, 7)]
        for product, expected in (("HSD", 7886579.0), ("MS", 8976577.0)):
            monthly_sum = sum(_cell(self.rows, month=m, area="PAKISTAN",
                                    sector_row="Road", product=product)
                              for m in fy_months)
            self.assertLess(abs(monthly_sum - expected) / expected, 0.005,
                            product)
            self.assertEqual(_cell(annual, inventory_year=2022,
                                   sector_row="Road", product=product), expected)


class TestParserAgainstSource(unittest.TestCase):
    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext not installed")
    def test_reference_year_pdf_reparses_to_the_committed_values(self):
        require_documents("sources/Aviation/ocac_annual/OCAC_FY2021_22.pdf")
        from pkinv.sectors.transport import ocac
        parsed = ocac.parse_annual(os.path.join(ocac.ANNUAL_DIR,
                                                "OCAC_FY2021_22.pdf"))
        road = next(v for _s, r, v in parsed["rows"] if r == "Road")
        self.assertEqual(road["HSD"], 7886579.0)
        self.assertEqual(road["MS"], 8976577.0)
        self.assertEqual(road["HOBC"], 150986.0)


if __name__ == "__main__":
    unittest.main()
