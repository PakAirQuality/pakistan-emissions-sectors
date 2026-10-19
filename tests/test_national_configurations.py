"""The named-configuration product: the policy-facing single-axis readings.

The contract has four parts. Every configuration's axis must exist in the scenario
registry (a configuration naming a retired axis would silently price nothing); the
reference row must equal the deterministic baseline the tripwires pin; the
residential configuration must equal the S total those same tripwires pin (so the
product is welded to the two numbers the release promises never move); and every
priced row must agree with the structural bridge to 1e-3 (the two products resolve
through the same machinery, and this asserts nobody forks them). The no-probability
schema rule is the dung-variants contract: a fork in the evidence carries no
probability, and a column suggesting one is a build failure, not a modelling choice.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT

PATH = os.path.join(OUT, "national_configurations.csv")

# rc39 A1 re-base: the reference herd became the census's exact enumeration, so the pins moved for the first time since rc30 (L 452.14350 -> 452.33432, S 447.01683 -> 447.20153; agriculture +0.184699 and residential +0.006121 through the dung handoff)
# rc46 Wave 2 (THE RE-BASE): brick and cement coal activated through the
# industrial_solid_fuels_1a2 gate, +13.57189 on both configurations. Previous pins,
# rc39..rc46w1: L 452.34662 / S 447.21383.
# The NAME is historical: through rc66 the baseline was configuration L. Since rc67 it is
# the survey reading (S), and this constant is the reference total whatever its letter.
# 447.20152 is the PUBLISHED S vintage (national_all_sectors_ledger.csv, summed from components). national_configurations composes S as L + delta from already-rounded parts and prints 447.20153; the re-base put the number on a rounding boundary and split the last digit, the same composed-vs-summed effect rc19 recorded at 447.71689/447.71688. The summed vintage is authoritative.
# Likewise historical: this is the SECOND configuration's total, which since rc67 is L.

FORBIDDEN_COLUMN_WORDS = ("probability", "prob", "weight", "likelihood", "prior",
                          "confidence")


def _rows():
    return read_rows(PATH, comments=False)


def native_configuration_total(configuration):
    """Independent source-component sum, before the structural bridge composes cases."""
    from pkinv.core.io import seq_sum
    rows = read_rows(os.path.join(OUT, "pakemis_ghg_configuration_atoms.csv"), comments=False)
    selected = [row for row in rows if row["period_id"] == "FY2023-24"
                and row["configuration_id"] == configuration]
    if not selected:
        raise AssertionError("configuration native atoms missing: " + configuration)
    return seq_sum(float(row["co2e_Mt_AR5"]) for row in selected)


def _bridge():
    return read_rows(os.path.join(OUT, 'national_structural_bridge.csv'), comments=False)


def _scenario_axes():
    return {r["axis"] for r in read_rows(asset_path(ROOT, "data", "scenarios.csv"))}


class TestNationalConfigurations(unittest.TestCase):
    def test_no_probability_column_exists(self):
        """Forks in the evidence carry no probabilities - schema-enforced, as in
        national_dung_variants.csv."""
        with open(PATH, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        for col in header:
            for word in FORBIDDEN_COLUMN_WORDS:
                self.assertNotIn(word, col.lower(),
                                 "column %r suggests a probability; the "
                                 "configurations are forks, not draws" % col)

    def test_every_axis_exists_in_the_scenario_registry(self):
        """JOINT and READING rows are the declared exceptions: a joint
        configuration moves several registered axes at once (the fugitives
        factorial floor), and a READING row is a THIRD reading of one registered
        control that the one-alternative-per-axis schema cannot hold (the rc17
        central practice member). Both say so in their axis labels rather than
        posing as single axes."""
        axes = _scenario_axes()
        for r in _rows():
            if r["axis"] and not r["axis"].startswith(("JOINT", "READING")):
                self.assertIn(r["axis"], axes,
                              "%s names an unregistered axis" % r["configuration_id"])

    def test_the_joint_floor_reaches_national_products(self):
        """The seventh review's point: the 9.601 Mt factorial floor lived only inside
        the fugitives sector. It must now ship as a national configuration whose
        delta equals floor minus the conservative default-practice reference."""
        row = next(r for r in _rows()
                   if r["configuration_id"] == "fugitives_joint_minimum")
        self.assertTrue(row["axis"].startswith("JOINT"))
        self.assertAlmostEqual(float(row["alternative_value_Mt"]), 9.60149, places=4)
        self.assertAlmostEqual(float(row["national_delta_Mt"]),
                               9.601489 - 23.499371, places=4)
        self.assertIn("no probability", row["note"])

    def test_the_reference_row_is_the_deterministic_baseline(self):
        ref = next(r for r in _rows()
                   if r["configuration_id"] == "inventory_reference")
        self.assertAlmostEqual(float(ref["national_total_Mt"]), native_configuration_total("S_TAN"), places=4)
        self.assertEqual(float(ref["national_delta_Mt"]), 0.0)

    def test_the_residential_configuration_is_the_survey_total(self):
        """Ties the product to the second tripwire: all_diverted_dung_household_fuel IS
        configuration S's national total, to the rounding this file prints."""
        row = next(r for r in _rows()
                   if r["configuration_id"] == "all_diverted_dung_household_fuel")
        self.assertAlmostEqual(float(row["national_total_Mt"]), native_configuration_total("L_TAN"), places=3)

    def test_every_priced_row_agrees_with_the_structural_bridge(self):
        bridge = {r["axis"]: r for r in _bridge()}
        for r in _rows():
            if not r["axis"] or r["axis"].startswith(("JOINT", "READING")):
                continue        # the declared exceptions resolve against their own outputs
            b = bridge[r["axis"]]
            self.assertTrue(b["national_total_Mt_co2e"],
                            "%s: bridge row is unpriced" % r["configuration_id"])
            self.assertAlmostEqual(float(r["national_total_Mt"]),
                                   float(b["national_total_Mt_co2e"]), delta=1e-3,
                                   msg=r["configuration_id"])
            self.assertAlmostEqual(float(r["national_delta_Mt"]),
                                   float(b["national_delta_Mt_co2e"]), delta=1e-3,
                                   msg=r["configuration_id"])

    def test_the_named_configurations_all_ship(self):
        ids = {r["configuration_id"] for r in _rows()}
        for expected in ("inventory_reference", "all_diverted_dung_household_fuel",
                         "lower_fugitive_practice", "power_plant_physical_coal",
                         "power_with_kelectric", "waste_flowing_sewer",
                         "cement_tier1_model_low",
                         "military_government_in_scope",
                         "general_aviation_in_scope",
                         "unresolved_jp1_in_scope",
                         "rail_ie_summary"):
            self.assertIn(expected, ids)

    def test_the_fugitives_envelope_is_a_family(self):
        """The ninth review: the reference must not read as a neutral centre
        while sitting at the top of its own structural envelope. The power
        family precedent applies - the envelope members carry a family_id and
        roles that name where the reference sits."""
        rows = {r["configuration_id"]: r for r in _rows()}
        for member in ("lower_fugitive_practice", "fugitives_including_feedstock",
                       "fugitives_central_practice", "fugitives_joint_minimum"):
            self.assertEqual(rows[member]["family_id"],
                             "fugitives_structural_envelope", member)
        for member in ("lower_fugitive_practice", "fugitives_including_feedstock",
                       "fugitives_joint_minimum"):
            self.assertIn("envelope", rows[member]["family_role"].lower(), member)
        self.assertIn("not defended",
                      rows["fugitives_including_feedstock"]["family_role"].lower(),
                      "the old membership is retained for traceability, not preferred")
        self.assertNotIn("fugitives_excluding_feedstock", rows,
                         "retired at rc67: the reference now excludes the feedstock")
        self.assertIn("envelope's top",
                      rows["fugitives_joint_minimum"]["family_role"])
        self.assertIn("never selected",
                      rows["fugitives_central_practice"]["family_role"],
                      "the central member must say it is priced, not chosen")

    def test_both_clinker_range_ends_are_priced(self):
        """The ninth review caught the IPPU paper claiming "both ends of that
        range ... are priced against the national total as named configurations"
        while only the observed-floor row existed: the 0.95 all-Portland axis
        never reached the configurations file. Both cement axes must resolve to
        a configuration row."""
        axes = {r["axis"] for r in _rows() if r["axis"]}
        self.assertIn("cement clinker activity basis", axes)
        self.assertIn("cement clinker fraction", axes,
                      "the all-Portland (0.95) end of the published 17.389-"
                      "21.504 range has no national configuration row - the "
                      "paper says it does")

    def test_the_rail_recode_conserves_the_total(self):
        """Both bookings of the rail axis conserve the national total EXACTLY: since
        the rc11 re-base the ENGINE books the recode (the reference), and the
        rail_ie_summary configuration restates the pre-rc11 summary booking. The
        moved quantity must equal the claimant ledger's RESOLVED-RECODED rows."""
        row = next(r for r in _rows()
                   if r["configuration_id"] == "rail_ie_summary")
        self.assertAlmostEqual(float(row["national_total_Mt"]), native_configuration_total("S_TAN"), places=4)
        self.assertEqual(float(row["national_delta_Mt"]), 0.0)
        with open(os.path.join(OUT, "railways_fuel_claimants_2024.csv"), newline="",
                  encoding="utf-8") as f:
            ledger = list(csv.DictReader(f))
        non_traction = sum(float(r["co2e_Mt_AR5"]) for r in ledger
                           if r["status"] == "RESOLVED-RECODED")
        with open(os.path.join(OUT, "railways_uncertainty_scenarios_2024.csv"),
                  newline="", encoding="utf-8") as f:
            scen = next(r for r in csv.DictReader(f)
                        if r["structural_scenario"] == "ie_summary")
        self.assertAlmostEqual(float(scen["moved_Mt"]), non_traction, delta=1e-4)

    def test_the_claimant_ledger_regenerates_identically(self):
        from pkinv.sectors.railways import fuel_claimants
        fresh = fuel_claimants.build()
        with open(os.path.join(OUT, "railways_fuel_claimants_2024.csv"), newline="",
                  encoding="utf-8") as f:
            shipped = list(csv.DictReader(f))
        self.assertEqual(len(fresh), len(shipped))
        for f_row, s_row in zip(fresh, shipped):
            for col in fuel_claimants.FIELDS:
                self.assertEqual(str(f_row[col]), s_row[col],
                                 "%s/%s.%s" % (f_row["fuel"], f_row["claimant"], col))

    def test_every_machinery_pointer_resolves(self):
        """The machinery column is a checkable pointer, not prose: file#row must
        name an existing output and a row inside it."""
        for r in _rows():
            if not r["axis"]:
                continue
            fname, row_key = r["machinery"].split("#", 1)
            path = os.path.join(OUT, fname)
            self.assertTrue(os.path.exists(path), r["machinery"])
            with open(path, newline="", encoding="utf-8") as f:
                # comment-tolerant, matching the builder's own reader
                keys = {(row.get("category") or row.get("scenario")
                         or row.get("structural_scenario")
                         or row.get("configuration") or row.get("method") or "").strip()
                        for row in csv.DictReader(line for line in f
                                                  if not line.startswith("#"))}
            self.assertIn(row_key, keys, r["machinery"])

    def test_the_output_regenerates_identically(self):
        """The shipped CSV is what build() produces from the live engine - the same
        no-drift contract every generated artefact in this release carries."""
        from pkinv.report import national_configurations as nc
        fresh = nc.build()
        shipped = _rows()
        self.assertEqual(len(fresh), len(shipped))
        for f_row, s_row in zip(fresh, shipped):
            for col in nc.FIELDS:
                self.assertEqual(str(f_row[col]), s_row[col],
                                 "%s.%s" % (f_row["configuration_id"], col))


if __name__ == "__main__":
    unittest.main()


class TestAConfigurationCannotPriceMassTheReferenceContains(unittest.TestCase):
    """rc47 Wave 0, the twenty-first review's double count. For four releases the
    brick, cement and captive scope configurations added their full screening
    estimates to a reference that - since the rc46 activation - already booked the
    measured mass, so `cement_kiln_fuel_in_scope` printed the same coal twice and
    the priority rankings crowned the double count the #2 structural driver.
    2,712 tests passed with it in place, because nothing asserted disjointness.

    Three rules, mechanical where the defect was mechanical:
      * the two retired ids never ship again (a ratchet, like the orphans list);
      * a scope configuration for an IPCC code whose scope-registry status is
        `reference` must price LESS than the activated mass and say it is net
        ("excess" / "net of" in its note) - pricing more re-adds the activation;
      * the completeness-mass residual's unclaimed remainder is never negative,
        which is the arithmetic signature that claimants have leaked inside the
        reference (the shipped file said "-6.6 Mt by nothing" for a release).
    """

    RETIRED = ("brick_kiln_coal_in_scope", "captive_coal_in_scope")

    # A scope configuration over an activated code that prices mass DISJOINT from
    # the activation by construction, with the reasoning on the record. The rule
    # below must not force "net of" language onto a claimant that never overlapped.
    DISJOINT_BY_CONSTRUCTION = {
        ("1.A.2", "bagasse_ceiling_in_scope"):
            "CH4+N2O from biomass process heat; the activation was coal only and "
            "bagasse CO2 is biogenic, outside every total by construction",
    }

    def _registry_reference_mass(self):
        out = {}
        for r in read_rows(asset_path(ROOT, "data", "scope_registry.csv")):
            if r["current_status"] == "reference":
                out[r["ipcc_code"]] = float(r["current_mass_Mt"])
        return out

    def test_the_retired_configurations_stay_retired(self):
        ids = {r["configuration_id"] for r in _rows()}
        for retired in self.RETIRED:
            self.assertNotIn(retired, ids,
                             "%s was retired at rc47 Wave 0 as a double count of "
                             "the activated reference mass; it may not ship again "
                             "without a written de-activation of the gate" % retired)

    def test_a_scope_configuration_over_an_activated_code_prices_net(self):
        from pkinv.report.coverage_matrix import SCREEN_CONFIGURATIONS
        activated = self._registry_reference_mass()
        rows = {r["configuration_id"]: r for r in _rows()}
        checked = 0
        for code, config_ids in SCREEN_CONFIGURATIONS.items():
            if code not in activated:
                continue
            for cid in config_ids:
                if not cid.endswith("_in_scope") or cid not in rows:
                    continue
                if (code, cid) in self.DISJOINT_BY_CONSTRUCTION:
                    continue
                row = rows[cid]
                delta = abs(float(row["national_delta_Mt"]))
                self.assertLess(
                    delta, activated[code],
                    "%s prices %.3f Mt against %s whose activated reference mass "
                    "is %.3f - a delta at or above the activation re-adds mass "
                    "the reference contains" % (cid, delta, code, activated[code]))
                self.assertTrue(
                    ("excess" in row["note"].lower()) or ("net of" in row["note"].lower()),
                    "%s sits over the activated code %s but its note does not say "
                    "it is priced net of the reference's own copy" % (cid, code))
                checked += 1
        self.assertGreater(checked, 0,
                           "the net-pricing rule matched nothing; if every scope "
                           "configuration over an activated code is gone, retire "
                           "this assertion deliberately rather than letting it rot")

    def test_the_unclaimed_remainder_is_never_negative(self):
        for r in read_rows(os.path.join(OUT, "pakemis_completeness_mass.csv")):
            note = r.get("note", "") or ""
            if "by nothing" not in note and "left over" not in note:
                continue
            import re
            for m in re.finditer(r"(-?\d+\.\d+) Mt (?:by nothing|left over)", note):
                self.assertGreaterEqual(
                    float(m.group(1)), 0.0,
                    "a negative unclaimed remainder is the double-count signature: "
                    "claimants exceed the residual that supposedly contains them "
                    "(row %s)" % (r.get("stream") or r.get("category_id") or "?"))
