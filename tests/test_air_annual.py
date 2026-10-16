"""Current fiscal air panel closure, typed absences and source-layer consistency.

The rollup composes the four dung/nitrogen configurations from source atoms.
Coverage cells distinguish estimates from missing categories, and narrow power
SO2 admission does not admit the separate screening products.
"""

from pkinv.assets import asset_path
import os
import unittest
from collections import defaultdict

from pkinv.core.io import read_rows
from pkinv.core import configurations as conf
from pkinv.core.reporting_window import CORE_SUFFIX, CORE_FY_ENDS
from pkinv.report.air_annual import atom_configuration

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "outputs")
CORE7 = {"BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2"}
BASES = {"observed", "observed_fiscal", "reconstructed", "held", "calendar_projection",
         "calendar_blend",            # rc59: the satellite flare volumes, half of each calendar year
         "observed_population_held_parameters",
         "survey_anchored_interpolation", "survey_anchored_extrapolated_flat",
         "survey_observed_reference_round", "census_anchored_reconstruction"}
# rc58/rc59: the three register modules have no single-year layer - their reference slices
# are asserted against their own nine-year detail file in tests/test_industry_air.py
# rc60: power joins them with SO2 only - the oil and diesel grid classes. Its other pollutants
# are still screened, so the sector is in the panel without being fully in it, and the coverage
# matrix is where that distinction is carried.
PANEL_SECTORS = {"agriculture", "aviation", "fugitives", "industry", "ippu", "power", "railways",
                 "residential", "transport", "waste"}
REFERENCE_FILES = {
    "agriculture": "air_pollutants_2024.csv",
    "residential": "residential_air_pollutants_2024.csv",
    "waste": "waste_air_pollutants_2024.csv",
    "railways": "railways_air_pollutants_2024.csv",
    "transport": "transport_air_pollutants_2024.csv",
    "aviation": "aviation_air_pollutants_fy2023_24.csv",
}


def _o(name):
    return read_rows(os.path.join(OUT, name))


def _d(relpath):
    return read_rows(asset_path(ROOT, "data", relpath))


class TestThePanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atoms = _o("pakemis_air_atomic_annual.csv")
        cls.rollup = _o("pakemis_air_annual_%s.csv" % CORE_SUFFIX)
        cls.coverage = _o("pakemis_air_coverage_matrix.csv")

    def test_the_rollup_is_exactly_the_core_atoms(self):
        # per configuration since Wave A: each configuration's rollup is its own atoms
        # plus the configuration-invariant reference atoms for every other sector
        own = defaultdict(set)
        for a in self.atoms:
            own[a["configuration_id"]].add(a["sector_id"])
        configs = conf.AIR_ALL
        want = defaultdict(float)
        for cfg in configs:
            for a in self.atoms:
                if a["core7"] != "yes":
                    continue
                if a["configuration_id"] == atom_configuration(cfg, a["sector_id"]):
                    want[(a["period_id"], cfg, a["sector_id"], a["pollutant"])] += \
                        float(a["emissions_Gg"])
        got = defaultdict(float)
        for r in self.rollup:
            got[(r["period_id"], r["configuration_id"], r["sector_id"],
                 r["pollutant"])] += float(r["emissions_Gg"])
        self.assertEqual(set(want), set(got))
        for k, v in want.items():
            self.assertAlmostEqual(got[k], v, places=4, msg=str(k))

    def test_the_ledger_configuration_moves_residential_alone(self):
        """S/L changes household dung only, independently of the nitrogen axis."""
        by = defaultdict(float)
        for row in self.rollup:
            by[(row["period_id"], row["configuration_id"], row["sector_id"], row["pollutant"])]+=float(row["emissions_Gg"])
        for survey, ledger in ((conf.REFERENCE, conf.LEDGER), (conf.IPCC_REFERENCE, conf.IPCC_LEDGER)):
            for (period, cfg, sector, pol), value in by.items():
                if cfg == ledger and sector != "residential":
                    self.assertAlmostEqual(value, by[(period, survey, sector, pol)], places=9)
        # At source grain the only changed fuel is the dung stream; totals must
        # attribute the entire difference to those source records.
        source = defaultdict(float)
        for row in self.atoms:
            if row["sector_id"] == "residential":
                source[(row["period_id"],row["configuration_id"],row["fuel_or_material"],row["pollutant"])]+=float(row["emissions_Gg"])
        for (period,cfg,fuel,pol), value in source.items():
            if cfg == conf.LEDGER and fuel != "Dung cake":
                self.assertAlmostEqual(value, source[period,conf.REFERENCE,fuel,pol], places=8)

    def test_the_ledger_series_is_the_larger_in_every_year(self):
        """The ledger burns all the dung agriculture diverts and the survey series what
        households report, in every year of the panel, so residential PM2.5 under
        L_HERD1624 exceeds the reference in all nine years, not only the reference one.
        A year where it did not would mean a slice still carried the pre-rc67 roles."""
        pm = defaultdict(float)
        for r in self.rollup:
            if r["sector_id"] == "residential" and r["pollutant"] == "PM2.5":
                pm[(r["fiscal_end_year"], r["configuration_id"])] += float(r["emissions_Gg"])
        years = sorted({fy for fy, _cfg in pm})
        self.assertEqual(len(years), len(CORE_FY_ENDS))
        for fy in years:
            self.assertGreater(pm[(fy, "L_TAN")], 2 * pm[(fy, "S_TAN")], fy)

    def test_the_coverage_matrix_is_630_typed_cells(self):
        self.assertEqual(len(self.coverage), len(CORE_FY_ENDS)*10*7)
        estimated = {(a["period_id"], a["sector_id"], a["pollutant"])
                     for a in self.atoms if a["core7"] == "yes"}
        for c in self.coverage:
            self.assertIn(c["state"], ("E", "NE", "IE", "NO", "NA"))
            key = (c["period_id"], c["sector_id"], c["pollutant"])
            self.assertEqual(c["state"] == "E", key in estimated, key)
            if c["state"] != "E":
                self.assertTrue(c["note"], "an absence with no reason: %s" % (key,))

    def test_power_is_screening_except_for_the_so2_it_now_estimates(self):
        """rc60 NARROWED THIS, and the narrowing is the whole assertion.

        Power used to contribute no atom at all and every power cell read `NE`. The oil and
        diesel fleet's SO2 is now estimated per station on a reviewed register, so exactly one
        pollutant crosses: SO2 becomes `E` with basis `panel-atom`, and BC, CO, NH3, NMVOC, NOx
        and PM2.5 stay NE on those same stations, because admitting one pollutant establishes
        nothing about the others. Coal and gas SO2 stay in the screening too - the register
        admits neither.

        The predecessor of this test asserted `no power atoms exist`. That was true and is now
        false, and a test like it is worth writing carefully: it pinned a COVERAGE DECISION, so
        it had to move when the decision did, and the thing to preserve was not the absence but
        the discipline that every cell says which it is.
        """
        power_atoms = [a for a in self.atoms if a["sector_id"] == "power"]
        self.assertTrue(power_atoms, "power contributes no atom; the admission is not wired")
        self.assertEqual({a["pollutant"] for a in power_atoms}, {"SO2"},
                         "only SO2 is admitted for power; another pollutant has leaked in")
        self.assertEqual(len({a["period_id"] for a in power_atoms}), len(CORE_FY_ENDS),
                         "the admission must reach all nine periods or it adds a coverage slope "
                         "to the very series it exists to repair")

        screening = _o("power_air_screening_%s.csv" % CORE_SUFFIX)
        self.assertEqual(len({r["period_id"] for r in screening}), len(CORE_FY_ENDS))
        # rc58: captive self-generation left the screening for the industry atoms
        self.assertFalse([r for r in screening if r["category"].startswith("Captive")])
        self.assertTrue([a for a in self.atoms
                         if a["sector_id"] == "industry" and a["category"].startswith("Captive")])
        # ...and the screening is still whole for everything the admission did not take
        self.assertTrue([r for r in screening if r["fuel"] == "Coal" and r["pollutant"] == "SO2"])
        self.assertTrue([r for r in screening
                         if r["fuel"] == "Furnace Oil" and r["pollutant"] == "NOx"])

        for c in self.coverage:
            if c["sector_id"] != "power":
                continue
            if c["pollutant"] == "SO2":
                self.assertEqual(c["state"], "E", c["period_id"])
                self.assertIn("panel-atom", c["state_basis"])
            else:
                self.assertEqual(c["state"], "NE", (c["period_id"], c["pollutant"]))
                self.assertIn("screening", c["state_basis"] + c["note"])

    def test_the_narrowed_screening_and_the_admission_are_disjoint(self):
        """NO DOUBLE COUNTING, asserted rather than inferred.

        The screening runs on the national fuel table and the admission on stations, so the two
        cannot be compared row by row. What can be compared is the fuel: the screening's oil and
        diesel SO2 is scaled to the CPPA-side fuel the admission did NOT take, and that scaling
        is exact because the screening is linear in fuel mass. So the test is that the remainder
        fraction is a real fraction in every year - never negative, which would mean the
        admission claimed more fuel than the country supplied, and never 1.0 in a year where
        something was admitted, which would mean the narrowing silently did not happen.
        """
        from pkinv.report import air_annual
        admitted_years = {int(r["fiscal_start_year"]) + 1
                          for r in _d("activity/power/power_so2_admission.csv")
                          if r["disposition"] == "provisional_estimate" and r["fuel"] == "RFO"}
        self.assertEqual(len(admitted_years), len(CORE_FY_ENDS))
        for fy_end in sorted(admitted_years):
            fraction, why = air_annual.admitted_remainder_fraction(fy_end, "Furnace Oil")
            self.assertTrue(why, "FY%d admits furnace oil but the screening was not narrowed"
                            % fy_end)
            self.assertGreater(fraction, 0.0,
                               "FY%d: the admission consumed the whole national supply" % fy_end)
            self.assertLess(fraction, 1.0, "FY%d: nothing came out of the screening" % fy_end)

    def test_the_reference_slice_reproduces_the_shipped_layers(self):
        # the shipped single-year CSVs are rounded (3 dp kt); the panel's atoms are
        # full precision, so agreement is n x half-ulp ABSOLUTE per cell
        panel = defaultdict(float)
        n = defaultdict(int)
        for a in self.atoms:
            if (a["period_id"] == "FY2023-24"
                    and a["configuration_id"] == "S_TAN"):
                panel[(a["sector_id"], a["pollutant"])] += float(a["emissions_Gg"])
        for sector, fname in REFERENCE_FILES.items():
            for r in _o(fname):
                key = (sector, r["pollutant"])
                panel[key] -= float(r["emissions_kt"])
                n[key] += 1
        for key, resid in panel.items():
            if key[0] in REFERENCE_FILES:
                self.assertLessEqual(abs(resid), (n[key] + 1) * 0.0005 + 1e-9,
                                     "reference slice drifts at %s" % (key,))

    def test_every_atom_names_a_stream_and_a_declared_basis(self):
        streams = {r["source_stream_id"]
                   for r in _o("pakemis_source_streams.csv")}
        for a in self.atoms:
            self.assertIn(a["support_anchor_id"], streams, a["subitem"])
            self.assertIn(a["activity_basis"], BASES, a["subitem"])
            self.assertEqual(a["coverage_scope"], "covered_sources_only")

    def test_the_panel_is_nine_periods_and_nine_sectors(self):
        self.assertEqual(len({a["period_id"] for a in self.atoms}), len(CORE_FY_ENDS))
        self.assertEqual({a["sector_id"] for a in self.atoms}, PANEL_SECTORS)

    def test_industry_is_e_for_exactly_the_species_its_register_prices(self):
        """rc58: industry is a covered estimate for the core species at least one register
        class prices with a held factor row, in every period, and NE (typed, with a gap) for
        the rest - NH3, which EMEP lists as not estimated for every fuel."""
        from pkinv.sectors.industry import air_pollutants as ind
        covered = ind.covered_core_species() & CORE7
        self.assertEqual(covered, {"NOx", "CO", "SO2", "PM2.5", "NMVOC", "BC"})
        for c in self.coverage:
            if c["sector_id"] == "industry":
                self.assertEqual(c["state"], "E" if c["pollutant"] in covered else "NE", c)
                if c["state"] == "NE":
                    self.assertEqual(c["gap_id"], "air-industry-nh3")

    def test_the_sulfur_history_is_in_the_series(self):
        so2 = defaultdict(float)
        for r in self.rollup:
            if r["pollutant"] == "SO2":
                so2[r["fiscal_end_year"]] += float(r["emissions_Gg"])
        self.assertGreater(so2["2016"], 1.5 * so2["2024"],
                           "FY2015-16 lost its pre-Euro-II sulfur")

    def test_atoms_key_is_unique(self):
        keys = [(a["period_id"], a["configuration_id"], a["sector_id"],
                 a["category"], a["subitem"], a["process"], a["pollutant"])
                for a in self.atoms]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
