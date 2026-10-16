"""The validation catalog: complete over the comparisons that exist, honest about absences.

(rc35: the catalog replaced the older validation registry, whose lane this file
used to test; the sweep and the well-formedness checks now read the catalog.)

Two failure modes this file closes. A registry that lists only what someone remembered to
list reads as exhaustive when it is not - so the completeness sweep applies the
audit_outputs closure argument to validations: every comparison-shaped file in outputs/
must be registered or declared out of scope, and the out-of-scope list must justify itself.
And a registry entry is a citation, so an entry whose product has vanished or emptied must
fail the build rather than go on being cited (the report module enforces that; the tests
here prove it fires).
"""
import csv
import glob
import os
import sys
import unittest


from pkinv.report import validation_catalog                # noqa: E402
from pkinv.core.io import read_rows
from _support import OUT, ROOT

PROPERTIES = ("magnitude", "timing", "geography")
# The registry's twelve columns; the catalog's five newer ones (benchmark_task_id,
# producer, wired, verdict_adapter, result_metric) are legitimately blank on rows
# they do not apply to, so the no-blank rule is scoped to the legacy twelve.
LEGACY_COLUMNS = ("validation_id", "property_tested", "module", "source", "period",
                  "boundary", "shared_inputs", "independence_class",
                  "calibration_or_validation", "result_output", "interpretation_limit")


# Files that LOOK like comparisons and are deliberately not registry rows, each with the
# reason. An entry here without a reason is a debt list, which this repo retired.
OUT_OF_SCOPE = {
    "pakemis_primary_geography_licence_audit.csv": "a provenance and licensing audit of the primary spatial geometry, not an independent emissions comparison",
    "pakemis_wastewater_method_comparison.csv": "a METHOD comparison inside the inventory, not a validation against an outside estimate: it sets the wastewater nitrous-oxide reference (2019 Refinement) beside the method it replaced (2006 Guidelines) on the same draws, and neither side is evidence about the other (rc67)",
    "pakemis_minerals_panel_screening.csv": "a COMPLETENESS screening of an activity panel, not a comparison of two estimates: it reports which province-years the panel holds and what a missing one costs the served monthly shape. Its guards are tests/test_minerals_panel_screening.py",
    "pakemis_citation_pointer_audit.csv": "a CITATION audit, not a validation: it scores whether each registered source names the table its figures were read from, and says nothing about whether any estimate is right. Its ratchets are tests/test_citation_pointer_audit.py",
    "pakemis_citation_deposit_audit.csv": "a PACKAGING audit, not a validation: it compares the paths the manuscripts cite against the deposit manifest and says nothing about whether any estimate is right. Its ratchet is tests/test_citation_deposit.py",
    "benchmark_air_comparison.csv": "air-pollutant beta, outside the GHG product's registry",
    "aviation_benchmark_summary_fy2023_24.csv": "sector-internal summary of rows the matrix "
                                           "already registers",
    "fugitives_benchmark_crosswalk.csv": "a crosswalk table, not a comparison result",
    "ippu_cement_uncertainty_inputs_2024.csv": "inputs to a comparison, not one",
    "aviation_climatetrace_periods.csv": "period bookkeeping behind the registered "
                                         "airport comparison",
    "aviation_climatetrace_spatial_diagnostics.csv": "diagnostics behind the registered "
                                                     "airport comparison",
    "aviation_climatetrace_airport_monthly.csv": "monthly detail behind the registered "
                                                 "airport comparison",
    "power_tropomi_extraction_manifest.json": "manifest of the registered TROPOMI check",
    "aviation_annual_component_comparison.csv": "internal partition consistency between "
                                                "the sector's own accounts, not external",
    "aviation_unfccc_official_comparison.csv": "prose-level summary of the registered "
                                               "hash-pinned CRT cell audit",
    "ippu_cement_crt_bridge_2022.csv": "year-bridge arithmetic behind the registered "
                                       "official comparison, not a comparison itself",
    "ippu_cement_tier_comparison_2024.csv": "detail of the registered method ladder",
    "n_ledger_stage_comparison.csv": "internal nitrogen-ledger stage consistency, "
                                     "enforced by its own closure test",
    "national_benchmark_comparison.csv": "registered by the catalog rows mag-benchmarks-matrix, mag-waste-edgar and mag-agriculture-benchmarks "
                                         "kept for the transition; the matrix row is "
                                         "the registered one",
    "transport_cng_crosscheck_2024.csv": "internal consistency of the CNG stream against "
                                         "its own OGRA source, not external validation",

    # --- the rc33 sweep extension's classifications: every name family the old
    # --- glob was blind to, each excluded for a stated reason or cataloged ----
    "aviation_era5_openap_audit.csv": "input-audit of the ERA5/OpenAP route weather extraction, not a comparison of the inventory against an instrument",
    "aviation_monthly_reconciliation.csv": "the aviation fuel reconciliation STUDY's internal ledger (its own runner); an accounting identity, not an external instrument",
    "aviation_reconciliation_fy2023_24.csv": "same study, annual ledger; internal accounting identity",
    "aviation_reconciliation_manifest.json": "the study's run manifest, provenance not comparison",
    "aviation_reconciliation_qa.csv": "the study's QA gate rows; runner self-checks, unified in Wave B",
    "commercial_institutional_audit_2024.csv": "the 1.A.4.a scope audit: builds the floor configuration, does not compare against an instrument",
    "fugitives_assumption_audit_2024.csv": "the assumption register audit: internal declaration hygiene, no instrument",
    "fugitives_official_matched_2022.csv": "the matched-support input extraction behind the CRT reproduction, which is the registered row",
    "ippu_ammonia_activity_reconciliation.csv": "reconciliation between the sector's own activity sources; no external instrument",
    "ippu_cement_activity_reconciliation.csv": "same class: own-source reconciliation",
    "ippu_cement_matched_calendar_2022.csv": "input to the registered official comparison (ippu_official_comparison.csv)",
    "ippu_company_boundary_audit_2024.csv": "the census boundary audit: provenance hygiene per company, not a comparison",
    "ippu_company_clinker_flow_audit_2024.csv": "per-company flow-completeness audit; provenance, not an instrument",
    "national_uncertainty_reconciliation.csv": "the MC parameter-sigma disposition register: an internal contract, not a validation",
    "pakemis_validation_catalog.csv": "the rc33 lane's own per-row status product (self-referential)",
    "pakemis_validation_scorecard.csv": "the validation lane's own scorecard (self-referential)",
    "pakemis_validation_sector_scorecard.csv":
        "the (module x property) projection of the catalog (rc37; self-referential)",
    "railways_fuel_reconciliation_2024.csv": "own-source fuel reconciliation feeding the registered official comparison",
    "railways_network_audit_2024.csv": "network-geometry provenance audit, not a comparison",
    "residential_district_map_audit_2024.csv": "district-name mapping audit; join hygiene, not an instrument",
    "spatial_nh3_validation.json": "stale artifact of the retained-but-unstaged NH3 module; catalog row geo-nh3-cell-2015 declares the absence until the benchmark grid lands",
    "pakemis_comparison_crosswalk.csv": "a declaration of the TERMS of every comparison (source, metric, year basis, boundary, independence) built from the catalog and the BTR table; it carries no result of its own and registering it would register the catalog twice",
    "pakemis_validation_five_classes.csv": "a REGROUPING of the catalogue itself by what each entry can establish (one row per catalogue entry, derived from role and independence_class); it adds no comparison and registering it would register every entry twice",
    "pakemis_validation_five_classes_summary.csv": "the per-class counts of pakemis_validation_five_classes.csv; a summary of the catalogue, not a comparison",
}


def _registry():
    return read_rows(validation_catalog.CATALOG)


class TestTheRegistryIsWellFormed(unittest.TestCase):

    def test_it_is_not_empty_and_ids_are_unique(self):
        rows = _registry()
        self.assertGreaterEqual(len(rows), 20)
        ids = [r["validation_id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_legacy_cell_is_blank(self):
        for row in _registry():
            for field in LEGACY_COLUMNS:
                if field in ("period", "boundary", "shared_inputs") and \
                        row["calibration_or_validation"] == "declared-absence":
                    continue   # an absence has no period or boundary to name
                self.assertTrue(str(row[field]).strip(),
                                "blank %s on %s" % (field, row["validation_id"]))

    def test_every_property_has_live_comparisons_and_absences_are_first_class(self):
        """Magnitude, timing and geography each validated SEPARATELY - the reviewer's
        core Stage 8 requirement - and a property with no check for some module says so
        in a declared-absence row rather than by omission."""
        rows = _registry()
        for prop in PROPERTIES:
            live = [r for r in rows if r["property_tested"] == prop
                    and r["calibration_or_validation"] != "declared-absence"]
            self.assertGreaterEqual(
                len(live), 3, "property %r has %d live comparisons" % (prop, len(live)))
        absences = [r for r in rows
                    if r["calibration_or_validation"] == "declared-absence"]
        self.assertGreaterEqual(len(absences), 4)
        for row in absences:
            self.assertIn(row["result_output"], ("none", ""))
            self.assertGreater(len(row["interpretation_limit"]), 25,
                               "%s: an absence must name what would fill it"
                               % row["validation_id"])

    def test_independence_is_never_overclaimed_for_shared_input_rows(self):
        """A comparison whose shared_inputs names a common upstream may not claim large
        independence - the exact overclaim the registry exists to prevent."""
        for row in _registry():
            shared = row["shared_inputs"].lower()
            if any(word in shared for word in ("likely common", "directly used",
                                               "same national statistic",
                                               "plausibly common", "likely shared")):
                self.assertNotEqual(row["independence_class"], "large",
                                    "%s claims large independence over shared inputs"
                                    % row["validation_id"])

    def test_the_published_catalog_carries_live_row_counts(self):
        published = {row["validation_id"]: row
                     for row in read_rows(os.path.join(OUT, "pakemis_validation_catalog.csv"))}
        self.assertEqual(set(published), {r["validation_id"] for r in _registry()})
        for vid, row in published.items():
            if row["exists"] == "yes":
                self.assertTrue(row["rows_live"].strip(), vid)

    def test_a_vanished_product_fails_the_build(self):
        """The positive control: point one entry at a missing file and build() must raise."""
        import tempfile
        import unittest.mock as mock
        rows = _registry()
        target = next(r for r in rows if r["result_output"] not in ("none", ""))
        target["result_output"] = "does_not_exist_9f2.csv"
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                         newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            path = handle.name
        try:
            with mock.patch.object(validation_catalog, "CATALOG", path):
                with self.assertRaises(SystemExit) as caught:
                    validation_catalog.build()
            self.assertIn("does_not_exist_9f2.csv missing", str(caught.exception))
        finally:
            os.unlink(path)


class TestTheRegistryIsComplete(unittest.TestCase):

    def test_every_comparison_shaped_output_is_registered_or_declared(self):
        """The audit_outputs closure argument, applied to validations: it is not enough to
        check the files someone remembered to list."""
        # a result_output may carry an eval/ prefix; the sweep compares basenames
        registered = {os.path.basename(r["result_output"]) for r in _registry()}
        from _support import presentation_layer
        index = presentation_layer()        # a validation package's reading index; empty here
        shaped = set()
        # rc33: the sweep grew the name families it had been blind to
        # (*validation*, *audit*, *agreement*, *reconciliation*, *match*,
        # *evaluation*) and became RECURSIVE so outputs/eval/ is visible -
        # the holes the modularity map named
        for pattern in ("*crt*", "*benchmark*", "*comparison*", "*crosscheck*",
                        "*climatetrace*", "*tropomi*", "*edgar*",
                        "*validation*", "*audit*", "*agreement*",
                        "*reconciliation*", "*match*", "*evaluation*"):
            for path in glob.glob(os.path.join(OUT, "**", pattern),
                                  recursive=True):
                name = os.path.basename(path)
                if os.path.normpath(os.path.relpath(path, ROOT)) in index:
                    continue          # a validation package's reading index, not a product
                if name.endswith((".csv", ".json")):
                    shaped.add(name)
        unaccounted = sorted(shaped - registered - set(OUT_OF_SCOPE)
                             - {n for n in shaped if n.startswith("crt_")}
                             - {n for n in shaped
                                if "unfccc_crt" in n and n not in registered})
        self.assertFalse(unaccounted,
                         "comparison-shaped outputs neither registered nor declared out of "
                         "scope:\n  " + "\n  ".join(unaccounted))

    def test_the_out_of_scope_list_does_not_shadow_a_registrable_comparison(self):
        for name, why in OUT_OF_SCOPE.items():
            self.assertGreater(len(why), 15, "%s is excluded without a real reason" % name)

    def test_the_sweep_sees_files(self):
        """A closure test over an empty glob passes; this is what stops that."""
        count = sum(len(glob.glob(os.path.join(OUT, p)))
                    for p in ("*benchmark*", "*crosscheck*", "*crt*"))
        self.assertGreater(count, 10, "the comparison glob has stopped matching")


if __name__ == "__main__":
    unittest.main()
