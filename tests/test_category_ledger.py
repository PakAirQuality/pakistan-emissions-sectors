"""The category x gas ledger must reconcile with the module rollup, exactly.

WHY THIS FILE EXISTS AT ALL. The manuscript printed a gas decomposition - CO2, CH4 and N2O as
CO2e, and methane's share of the total - that nothing generated and nothing checked. It stayed
in the paper across three releases while every headline number around it was re-anchored, and
by the end its three parts summed to 455.14 Mt against a printed national total of 448.00, with
CO2 wrong by 9.5 Mt and the methane share wrong by 1.2 points.

The reason it survived is worth stating plainly: it was in the coverage test's declared-debt
list. That list records printed quantities not yet anchored, and two tests bound it - nothing
may be added, and an entry must be deleted once registered. Both passed the whole time, because
neither compares a debt entry against anything. A declared debt reads as "tracked" and behaves
as "unchecked".

So the decomposition is generated now, and this file asserts it adds up.
"""

from pkinv.assets import asset_path
import os
import sys
import unittest


from pkinv.report import category_ledger, national_rollup   # noqa: E402
from _support import ROOT


class TestTheLedgerReconciles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = {basis: category_ledger.build(basis) for basis in ("ledger", "survey")}
        cls.roll = {basis: national_rollup.rollup(basis) for basis in ("ledger", "survey")}

    def _total(self, basis, col):
        return next(r[col] for r in self.roll[basis] if r["sector"] == "TOTAL")

    def test_the_ledger_sums_to_the_national_total_under_both_configurations(self):
        """Both metrics, both configurations. The two paths share build_components() and
        nothing else, so an aggregation defect in either shows up here."""
        for basis in ("ledger", "survey"):
            for col, metric in (("co2e_Mt_AR5", "AR5"), ("co2e_Mt_AR6", "AR6")):
                ledger = sum(r[col] for r in self.rows[basis])
                self.assertAlmostEqual(
                    ledger, self._total(basis, col), places=6,
                    msg="%s %s: ledger %.6f vs rollup %.6f"
                        % (basis, metric, ledger, self._total(basis, col)))

    def test_every_module_total_survives_the_regrouping(self):
        """A category-first view must not move a module's magnitude - it only relabels which
        IPCC code the same components belong to."""
        for basis in ("ledger", "survey"):
            by_module = {}
            for r in self.rows[basis]:
                by_module[r["module"]] = by_module.get(r["module"], 0.0) + r["co2e_Mt_AR5"]
            for row in self.roll[basis]:
                if row["sector"] == "TOTAL":
                    continue
                self.assertAlmostEqual(
                    by_module.get(row["sector"], 0.0), row["co2e_Mt_AR5"], places=6,
                    msg="%s: module %s" % (basis, row["sector"]))

    def test_the_gas_decomposition_is_closed(self):
        """The specific defect: the three gas totals must sum to the national total and the
        shares must sum to 100, computed rather than typed."""
        stats = category_ledger.by_gas(self.rows["ledger"])
        gases = {g: v for g, v in stats.items() if g != "TOTAL"}
        self.assertEqual(sorted(gases), ["CH4", "CO2", "N2O"])
        self.assertAlmostEqual(sum(v[0] for v in gases.values()),
                               stats["TOTAL"][0], places=6)
        self.assertAlmostEqual(sum(v[2] for v in gases.values()), 100.0, places=6)
        self.assertAlmostEqual(stats["TOTAL"][0], self._total("ledger", "co2e_Mt_AR5"),
                               places=6)

    def test_methane_is_the_majority_and_the_share_is_derived(self):
        """Guards the direction of the corrected statement as well as its arithmetic: the
        stale paragraph said 54.3 percent when the engine said 55.5, and a reader cannot tell
        a rounding difference from a superseded release without a check like this one."""
        stats = category_ledger.by_gas(self.rows["ledger"])
        share = stats["CH4"][2]
        self.assertAlmostEqual(share, 100.0 * stats["CH4"][0] / stats["TOTAL"][0], places=9)
        self.assertGreater(share, 50.0, "methane is no longer the majority - the paper's "
                                        "metric-sensitivity argument needs rewriting, not "
                                        "re-anchoring")


class TestTheCodeTableCannotDrift(unittest.TestCase):
    """The mapping is read from the completeness matrix; only the Guidelines' NAMES are
    declared. Both directions are asserted, because a declared table that is merely a superset
    is how a retired code goes on being printed."""

    def test_every_code_the_ledger_produces_has_a_declared_name(self):
        used = set(category_ledger.by_code())
        missing = sorted(used - set(category_ledger.IPCC_CATEGORY_NAMES))
        self.assertFalse(missing, "codes with no IPCC name: %s" % ", ".join(missing))

    def test_no_declared_name_is_orphaned(self):
        used = set(category_ledger.by_code())
        orphans = sorted(set(category_ledger.IPCC_CATEGORY_NAMES) - used)
        self.assertFalse(orphans,
                         "IPCC_CATEGORY_NAMES carries codes this inventory does not report, "
                         "which is how a retired category keeps a name: %s"
                         % ", ".join(orphans))

    def test_the_mapping_comes_from_the_completeness_matrix(self):
        """Not a tautology: it asserts the ledger's codes are the completeness matrix's codes
        for the same categories, so the two cannot describe different inventories.

        Since the IPCC 2006 migration a code is a property of the COMPONENT, not of the engine
        category: manure management carries 3.A.2 and 3.C.6, managed soils 3.C.4 and 3.C.5. So
        the assertion is that every (code, engine category) pair the ledger prints is one the
        matrix or the crosswalk declares - which is the same claim, at the grain the data now
        has. Keying on the category alone would simply KeyError on the split ones, and keying
        on the code alone would stop noticing if a category acquired a code nobody declared.
        """
        import sys, os as _os
        sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__))), "src"))
        from pkinv.report import category_crosswalk
        declared = {(r["ipcc2006_code"], r["engine_category"])
                    for r in category_crosswalk.rules()
                    if r["applies_to"] == "component"}
        codes = category_ledger.category_codes()
        declared |= {(code, engine) for engine, code in codes.items()}
        for row in category_ledger.build():
            self.assertIn(
                (row["ipcc_code"], row["engine_category"]), declared,
                "the ledger prints %s for engine category %r, which neither the completeness "
                "matrix nor the crosswalk declares"
                % (row["ipcc_code"], row["engine_category"]))

    def test_no_declared_name_absorbs_an_unestimated_category(self):
        """The Round 6 defect, generalised.

        IPCC_CATEGORY_NAMES["3.C.3"] read "Urea application and liming". Liming is 3.C.2, and the
        completeness matrix in the same release carries 3.G as NE pending national lime-use
        data - so the printed name asserted coverage of a category the release declares
        unestimated. A display label is not a neutral thing: it is where a completeness claim
        can be made with nothing checking it.

        The check is textual, because what a reader takes from a label is textual: if the name
        of an ESTIMATED category contains the distinguishing word of an UNESTIMATED one, the
        label is claiming something the matrix denies.
        """
        import csv as _csv
        import os as _os
        from pkinv.paths import OUTPUTS
        ne_labels = {}
        with open(_os.path.join(OUTPUTS, "completeness.csv"),
                  newline="", encoding="utf-8") as handle:
            for row in _csv.DictReader(handle):
                if row["notation_key"] == "NE":
                    # The WHOLE label, not a fragment of it. Splitting on the dash and taking
                    # the tail turns "Water-borne navigation - domestic" into "domestic",
                    # which then matches "Domestic wastewater" and flags a correct name.
                    label = (row["category"] or "").strip().lower()
                    if len(label) > 4:
                        ne_labels.setdefault(label, set()).add(row["code"])
        offenders = []
        for code, name in sorted(category_ledger.IPCC_CATEGORY_NAMES.items()):
            for label, ne_codes in sorted(ne_labels.items()):
                if code in ne_codes:
                    continue          # a code may of course name its own unestimated parts
                if label in name.lower():
                    offenders.append("%s is named %r, which contains %r - the label of %s, "
                                     "an unestimated category"
                                     % (code, name, label, "/".join(sorted(ne_codes))))
        self.assertFalse(offenders, "a category name claims coverage the completeness matrix "
                                    "denies:\n  " + "\n  ".join(offenders))

    def test_an_unresolved_allocation_is_declared_on_the_row(self):
        """Mixed off-road machinery is placed at 1.A.4.c because the larger part belongs
        there, but the source's residual class carries construction and industrial plant that
        the Guidelines book under 1.A.2. The ledger must say the placement is unsettled rather
        than print a clean category."""
        rows = category_ledger.build()
        flagged = {r["ipcc_code"] for r in rows if r["ipcc_allocation"] == "unresolved"}
        self.assertEqual(flagged, set(category_ledger.UNRESOLVED_ALLOCATION),
                         "the flagged rows and the declared table disagree")
        for code in category_ledger.UNRESOLVED_ALLOCATION:
            self.assertIn(code, {r["ipcc_code"] for r in rows},
                          "%s is declared unresolved but reports nothing" % code)

    def test_a_category_split_across_modules_keeps_its_rows(self):
        """1.A.2 is computed in two modules - captive self-generation in power, process heat
        and boilers in industry. The ledger must show both, because collapsing them hides the
        split that makes the EDGAR 1.A.2 comparison legible."""
        rows = [r for r in category_ledger.build() if r["ipcc_code"] == "1.A.2"]
        self.assertGreater(len({r["module"] for r in rows}), 1,
                           "1.A.2 is reported from one module only - either the industry "
                           "module moved or the ledger collapsed the split")



class TestTheBenchmarkScopeIsDerived(unittest.TestCase):
    """The reviewer's finding, pinned: a scope classification must come from the completeness
    matrix, not from someone's recollection of which sectors exist.

    The first version of benchmark_scope_coverage() declared five EDGAR domains estimated
    "whole". Three of them carried NE categories in outputs/completeness.csv at the time -
    domestic navigation and mobile air-conditioning in transport, transmission, distribution
    and solid fuels in fugitives, industrial wastewater, incineration and biological treatment
    in waste. The metric had been introduced one round earlier precisely to stop a magnitude
    ratio from being read as completeness, and it was itself an unchecked completeness claim.
    """

    @classmethod
    def setUpClass(cls):
        from pkinv.report import national_rollup as nr
        cls.nr = nr
        cls.rows, cls.summary = nr.benchmark_scope_coverage()

    def test_the_bands_sum_to_the_whole_comparator(self):
        total = (self.summary["fully_represented_pct"]
                 + self.summary["partially_represented_pct"]
                 + self.summary["absent_pct"])
        self.assertAlmostEqual(total, 100.0, places=6)

    def test_no_domain_is_called_represented_while_carrying_an_NE(self):
        """The defect itself. A domain may only be 'represented' when the completeness matrix
        has no NE row for any code mapped to it."""
        keys = self.nr._completeness_keys()
        mapped = self.nr._edgar_domain_codes()
        for domain, _mt, _share, klass, _counts, named in self.rows:
            has_ne = [c for c in mapped[domain] if "NE" in keys[c]]
            if klass == "represented":
                self.assertFalse(has_ne, "%s is called represented but %s are NE"
                                 % (domain, ", ".join(has_ne)))
            else:
                self.assertTrue(has_ne, "%s is not called represented but nothing is NE"
                                        % domain)
                for code in has_ne:
                    self.assertIn(code, named,
                                  "%s hides its unestimated category %s" % (domain, code))

    def test_every_mapped_code_exists_in_the_completeness_matrix(self):
        """A code mapped to a domain but absent from the matrix would score as complete."""
        keys = self.nr._completeness_keys()
        for domain, codes in self.nr._edgar_domain_codes().items():
            for code in codes:
                self.assertIn(code, keys, "%s maps %s, which the matrix does not carry"
                              % (domain, code))

    def test_the_domain_magnitudes_decompose_the_comparator(self):
        self.assertAlmostEqual(sum(mt for _d, mt in self.nr.EDGAR_DOMAINS),
                               self.nr.EDGAR_NATIONAL, places=2)


class TestBenchmarkBoundaries(unittest.TestCase):
    """Every benchmark row must declare what it is comparing, and a ratio must be permitted
    before it is printed.

    The row labelled "Road transport" carried the transport MODULE - road plus mixed off-road,
    41.93 Mt - against an EDGAR row covering a different set of modes in a different calendar
    year, and printed a ratio of 0.71 as though the two were the same thing. Cement calcination
    against the whole of IPPU printed 0.64 the same way. Arithmetic divisibility is not
    comparability, and only the register knows the difference.
    """

    @classmethod
    def setUpClass(cls):
        import csv as _csv
        import os as _os
        from pkinv.paths import DATA
        with open(asset_path(DATA, "benchmarks.csv"),
                  newline="", encoding="utf-8") as handle:
            cls.register = list(_csv.DictReader(handle))

    def test_every_row_declares_both_boundaries_and_a_role(self):
        for r in self.register:
            key = "%s/%s/%s" % (r["source"], r["engine_category"], r["year"])
            for field in ("benchmark_period", "engine_boundary", "benchmark_boundary",
                          "boundary_match", "comparison_role", "ratio_permitted",
                          "engine_period", "gas_scope", "bunker_treatment",
                          "biogenic_treatment"):
                self.assertTrue((r.get(field) or "").strip(),
                                "%s has no %s" % (key, field))
            self.assertIn(r["boundary_match"], ("exact", "partial", "screening"), key)
            self.assertIn(r["comparison_role"],
                          ("matched", "diagnostic", "coverage", "superseded"), key)
            self.assertIn(r["ratio_permitted"], ("yes", "no"), key)
            # the AR6 defect's vocabulary guard: the GWP basis is closed, and a row
            # published in neither AR basis must be the never-comparable native kind
            self.assertIn(r["gwp"], ("AR5", "AR6", "native CO2"), key)

    def test_no_ratio_is_printed_where_the_register_forbids_it(self):
        from pkinv.report import national_rollup
        header = ["source", "engine_category", "scope_detail", "year", "gwp",
                  "engine_period", "benchmark_period",
                  "engine_boundary", "benchmark_boundary", "boundary_match",
                  "gas_scope", "bunker_treatment", "biogenic_treatment",
                  "comparison_role", "benchmark_Mt_co2e", "engine_Mt_co2e",
                  "ratio_engine_over_benchmark", "within_0.5_2.0x", "note"]
        permitted = {(r["source"], r["engine_category"], r["year"]): r["ratio_permitted"]
                     for r in self.register}
        withheld = 0
        for raw in national_rollup.benchmark_comparison():
            row = dict(zip(header, raw))
            flag = permitted[(row["source"], row["engine_category"], str(row["year"]))]
            if flag == "no":
                withheld += 1
                self.assertEqual(row["ratio_engine_over_benchmark"], "",
                                 "%s/%s prints a ratio its boundaries do not support"
                                 % (row["source"], row["engine_category"]))
        self.assertGreater(withheld, 0,
                           "no row withholds a ratio - either the register lost its flags or "
                           "every boundary became exact, and one of those is unlikely")

    def test_a_module_boundary_says_so(self):
        """The specific defect: a row whose engine side is a module must say MODULE in its
        boundary, so nobody labels it with a category name again."""
        for r in self.register:
            if r["engine_category"] in ("transport", "waste"):
                self.assertIn("MODULE", r["engine_boundary"],
                              "%s is a module on the engine side and does not say so"
                              % r["engine_category"])

    def test_every_edgar_row_is_pinned_to_a_hashed_source_file(self):
        """The seventh review's provenance item: data/source_documents.csv said the
        EDGAR booklet was 'archived, sources/EDGAR' while the file sat GITIGNORED at
        the repo root - the register claimed an archive that did not exist in the
        tree, and every EDGAR benchmark row hung off it. Since rc11 the booklet is
        tracked and every EDGAR row either pins the exact file by sha256 or declares
        in benchmark_release that the source file is not held (the 2024 prior-vintage
        row). A benchmark whose source cannot be re-opened is a rumour with digits."""
        import hashlib as _hashlib
        import os as _os
        from pkinv.paths import ROOT
        hashes = {}
        edgar_rows = [r for r in self.register if r["source"] == "EDGAR"]
        self.assertTrue(edgar_rows, "the register lost its EDGAR rows")
        for r in edgar_rows:
            key = "%s/%s/%s" % (r["source"], r["engine_category"], r["year"])
            file_ = (r.get("benchmark_source_file") or "").strip()
            if not file_:
                self.assertIn("source file not held",
                              r.get("benchmark_release", ""),
                              "%s names no source file and does not declare why" % key)
                continue
            path = asset_path(ROOT, file_)
            self.assertTrue(_os.path.exists(path),
                            "%s pins %s, which is not in the tree" % (key, file_))
            if path not in hashes:
                with open(path, "rb") as fh:
                    hashes[path] = _hashlib.sha256(fh.read()).hexdigest()
            self.assertEqual(hashes[path], r["benchmark_source_sha256"],
                             "%s: the held %s does not match the pinned sha256"
                             % (key, file_))

class TestTheScenarioRegistryAndBridge(unittest.TestCase):
    """The release's structural configuration is nine choices, not one letter.

    The manifest recorded "configuration L", which names only the dung axis. The 448.00 Mt
    total also embeds the sewer methane correction factor, the fugitive practice and activity
    bases, three power axes, the clinker fraction, the industrial gas heating value and the
    transport retail residual - and the parametric interval contains none of them. Several
    single axes move the total further than the whole interval does.
    """

    @classmethod
    def setUpClass(cls):
        from pkinv.report import national_rollup as nr
        cls.nr = nr
        cls.registry = nr.scenario_registry()
        cls.baseline, cls.bridge = nr.structural_bridge()

    def test_every_axis_names_a_module_that_exists(self):
        from pkinv.core import registry as core_registry
        modules = {s.NAME for s in core_registry.all_sectors()}
        for entry in self.registry:
            self.assertIn(entry["module"], modules,
                          "%s names a module that is not registered" % entry["axis"])
            for field in ("setting", "alternative", "note"):
                self.assertTrue(entry[field].strip(), "%s has no %s" % (entry["axis"], field))

    def test_the_dung_axis_still_carries_the_configuration_letter(self):
        """L survives as one axis's ALTERNATIVE rather than as the whole scenario. If the
        letter stops appearing here, either the axis was renamed or the baseline changed.

        The baseline did change, at rc67: through rc66 the axis's setting was the ledger
        and the survey was its alternative. The setting is the survey now, the ledger is
        the alternative, and the row it points at is the configuration-L sensitivity."""
        dung = [e for e in self.registry if e["module"] == "residential"]
        self.assertEqual(len(dung), 1)
        self.assertIn("survey", dung[0]["setting"])
        self.assertNotIn("ledger", dung[0]["setting"])
        self.assertIn("ledger", dung[0]["alternative"])
        self.assertIn("configuration L", dung[0]["alternative_row"])

    def test_the_dung_axis_raises_the_total(self):
        """The direction of the swap, in the bridge. Stepping from the survey to the
        ledger ADDS the dung households are not observed burning, so the axis's delta is
        positive and equal to the residential difference between the two engine runs
        (+5.24626 Mt; through rc66 the same axis read -5.13, the step down to the 2024-25
        round as measured)."""
        from pkinv.sectors.residential import engine
        from pkinv.sectors.residential.data import ResidentialData
        data = ResidentialData()
        ref = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data))
        led = sum(c["co2e_Mt_AR5"]
                  for c in engine.build_components(data, dung_basis="ledger"))
        row = next(r for r in self.bridge if r["module"] == "residential")
        self.assertGreater(row["national_delta_Mt"], 0.0)
        self.assertAlmostEqual(row["national_delta_Mt"], led - ref, places=4)
        self.assertAlmostEqual(row["national_delta_Mt"], 5.24626, places=4)

    def test_each_priced_axis_moves_the_total(self):
        """Recode axes are the declared exception: a reporting recode conserves the
        national total BY CONSTRUCTION (the same fuel at a different code), and its
        zero delta is the claim, not a failure to price."""
        priced = [r for r in self.bridge if r["national_delta_Mt"] is not None]
        self.assertGreaterEqual(len(priced), 8)
        for r in priced:
            if "recode" in r["note"].lower():
                self.assertEqual(r["national_delta_Mt"], 0.0,
                                 "%s declares a recode but moves the total" % r["axis"])
                continue
            self.assertNotAlmostEqual(
                r["national_delta_Mt"], 0.0, places=3,
                msg="%s is declared a structural alternative and changes nothing" % r["axis"])

    def test_a_single_axis_exceeds_the_parametric_interval(self):
        """The reason the bridge exists. If no structural choice were larger than the interval
        the paper reports, the conditional qualification would be a technicality rather than
        the headline caveat it is."""
        half_width = 0.112 * self.baseline
        largest = max(abs(r["national_delta_Mt"]) for r in self.bridge
                      if r["national_delta_Mt"] is not None)
        self.assertGreater(largest, 0.3 * half_width,
                           "no structural axis is material against the parametric interval")

    def test_the_manifest_carries_the_whole_scenario(self):
        import json
        import os as _os
        from pkinv.paths import OUTPUTS
        with open(_os.path.join(OUTPUTS, "release_manifest.json"), encoding="utf-8") as h:
            manifest = json.load(h)
        self.assertEqual(manifest["scenario"]["scenario_id"], "REF_2023_24")
        self.assertEqual(len(manifest["scenario"]["axes"]), len(self.registry),
                         "the manifest records fewer axes than the registry declares")


if __name__ == "__main__":
    unittest.main()
