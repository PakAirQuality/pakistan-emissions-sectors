"""The scenario product's SHAPE and its refusals - never its numbers as conclusions.

This product exists because an external reconstruction computed a set of conditional alternatives
for FY2023-24 industry, and the arithmetic was worth keeping. The hazard it carries is that a
scenario which makes the trend look more plausible gets quietly promoted to an estimate. rc40's
validation package compared 83 products, called 82 identical, and 59 of 107 phases had never run;
the same shape here would be a table of alternatives that a later reader mistakes for a range.

So what is guarded is that the record cannot LIE about what it is:
  - every row is typed, and no row claims to be a central estimate or a confidence bound;
  - the power-coal discrepancy is never booked into industry;
  - the coal factor is the engine's own chain, not a ratio of rounded published totals;
  - the external figures are carried beside ours, and the unverified ones are labelled.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import OUTPUTS, ROOT

OUT = os.path.join(OUTPUTS, "pakemis_industrial_coal_scenarios.csv")
KINDS = ("reported", "scenario", "sensitivity", "break_even")


def rows():
    with open(OUT, encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


class TheRecordsShape(unittest.TestCase):
    def test_every_row_is_typed_and_says_what_it_rests_on(self):
        for r in rows():
            self.assertIn(r["kind"], KINDS, r["scenario_id"])
            self.assertTrue(r["conditions"].strip(), r["scenario_id"])
            self.assertTrue(r["note"].strip(), r["scenario_id"])

    def test_exactly_one_row_is_the_reported_series(self):
        """A table of alternatives with no anchor is a menu. Exactly one row is the shipped
        estimate and it is typed differently from every alternative."""
        reported = [r for r in rows() if r["kind"] == "reported"]
        self.assertEqual(len(reported), 1)
        self.assertEqual(reported[0]["scenario_id"], "reported")

    def test_no_row_claims_to_be_an_estimate_a_central_or_an_interval(self):
        """The words that would promote a scenario. `conditions` and `note` are prose a human
        writes, so the ban is on the phrasing, not on a flag someone could forget to set."""
        banned = ("central estimate", "best estimate", "confidence interval", "95%",
                  "should be adopted", "corrected estimate", "replaces the reported")
        for r in rows():
            text = (r["conditions"] + " " + r["note"]).lower()
            for phrase in banned:
                self.assertNotIn(phrase, text, "%s: %r" % (r["scenario_id"], phrase))

    def test_the_discrepancy_is_never_booked_into_industry(self):
        """The one thing this product must refuse. Every reallocation row has to say, in its own
        text, that the coal is NOT established as industrial."""
        gross = [r for r in rows() if "gross" in r["scenario_id"]]
        self.assertTrue(gross)
        for r in gross:
            self.assertIn("IF", r["conditions"], r["scenario_id"])
        text = " ".join(r["note"] + r["conditions"] for r in rows()).lower()
        self.assertIn("thar", text, "the origin constraint is not stated anywhere")
        self.assertIn("delivery", text)

    def test_the_sensitivity_rows_are_not_offered_as_measurements(self):
        for r in rows():
            if r["kind"] != "sensitivity":
                continue
            self.assertIn("test", r["note"].lower(), r["scenario_id"])


class TheFactorIsTheEnginesOwn(unittest.TestCase):
    def test_the_scenarios_use_the_registry_chain_not_a_back_derived_ratio(self):
        """The external analysis divided rounded emissions by rounded tonnage and got 2.460145.
        That is within 0.06 percent of the truth, which is a compliment to its arithmetic and still
        not the number this release burns coal at. Rebuilt here from the registry, with coal CH4 as
        FOSSIL - AR5 gives fossil methane 30, not 28, and the atom table types it that way."""
        import csv as _csv
        from pkinv.core.gwp import GWP
        factors = {}
        with open(asset_path(ROOT, "data", "emission_factors.csv"), encoding="utf-8") as handle:
            for r in _csv.DictReader(l for l in handle if not l.startswith("#")):
                if r.get("value"):
                    factors[r["ef_id"]] = float(r["value"])
        expected = factors["res_ncv_coal"] * (
            factors["ind_coal_co2"]
            + factors["ind_coal_ch4"] * GWP["AR5"]["CH4_fossil"]
            + factors["ind_coal_n2o"] * GWP["AR5"]["N2O"]) / 1e6

        reported = [r for r in rows() if r["kind"] == "reported"][0]
        mass = float(reported["industrial_coal_Mt"])
        # the reported row's coal mass, times the chain, must reproduce the shipped coal emissions
        atoms = os.path.join(OUTPUTS, "pakemis_atomic_annual.csv")
        shipped = 0.0
        with open(atoms, encoding="utf-8") as handle:
            for r in _csv.DictReader(l for l in handle if not l.startswith("#")):
                if (r["configuration_id"] == "REF_2023_24" and r["period_id"] == "FY2023-24"
                        and r["subitem"].startswith(("Brick-kiln coal", "Cement-sector coal"))):
                    shipped += float(r["co2e_Mt_AR5"] or 0.0)
        self.assertAlmostEqual(mass * expected, shipped, places=6)
        self.assertAlmostEqual(mass, 5.520, places=3,
                               msg="the booked coal mass is 1,129 + 4,391 kt; a sum over "
                                   "coal_by_consumer.csv without the booking policy adds superseded "
                                   "editions and gives 11.475")

    def test_the_external_figures_are_carried_beside_ours_not_instead(self):
        for r in rows():
            if r["kind"] in ("reported", "scenario", "sensitivity"):
                self.assertTrue(r["external_value_MtCO2e"].strip(), r["scenario_id"])

    def test_the_reported_row_reproduces_the_shipped_totals(self):
        """If this drifts, every scenario measured against it drifts silently."""
        reported = [r for r in rows() if r["kind"] == "reported"][0]
        self.assertAlmostEqual(float(reported["direct_1a2_MtCO2e"]), 28.131, places=2)
        self.assertAlmostEqual(float(reported["broader_industry_MtCO2e"]), 53.666, places=2)


class TheBreakEvenRows(unittest.TestCase):
    def test_both_thresholds_are_published_and_neither_is_a_fuel_property(self):
        be = {r["scenario_id"]: r for r in rows() if r["kind"] == "break_even"}
        self.assertEqual(set(be), {"break_even_broader", "break_even_direct"})
        for r in be.values():
            self.assertIn("threshold", r["note"].lower())
            self.assertEqual(r["direct_1a2_MtCO2e"], "",
                             "a break-even row states a FACTOR, not an emissions total")

    def test_the_direct_threshold_is_the_harder_one(self):
        """The finding the two rows exist to carry, asserted so it cannot quietly reverse: even on
        the gross coal mass, direct combustion needs a far higher factor than the broader boundary,
        which is why 'broader industry may have been flat' survives testing and 'industrial
        combustion must have risen' does not."""
        be = {r["scenario_id"]: r["note"] for r in rows() if r["kind"] == "break_even"}
        broader = float(be["break_even_broader"].split()[0])
        direct = float(be["break_even_direct"].split()[0])
        self.assertGreater(direct, broader)
        self.assertGreater(direct / broader, 1.15)


if __name__ == "__main__":
    unittest.main()
