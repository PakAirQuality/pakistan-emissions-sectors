"""One authoritative answer per fact a document might state about the products.

WHY THIS EXISTS. An external reviewer graded the 108-month product D - "it still does not
exist; only the reference year has twelve allocated months" - and made building it the
highest-leverage next task. It exists: outputs/pakemis_monthly_fy2015_16_fy2024_25.csv holds
16,824 rows over 108 distinct months, 201507 to 202406. The reviewer had read the published
description, and it said in as many words that the product did not exist.

That sentence was written to keep an allocated month from being read as an observed one, which
is the distinction this whole programme insists on. It was true about the EVIDENCE and false
about the PRODUCT, and nothing could tell it so. A release can be under-graded by its own
scrupulousness exactly as easily as it can be over-sold, and both failures have the same
shape: a claim about the products that no product can contradict.

WHAT THIS IS. Every count a manuscript, README or caption makes about the shape of the
release, derived once from the products themselves, with the file each answer came from on the
row. The claims registry then reads THIS, so a sentence that disagrees with the release fails
the build rather than being noticed by a reviewer.

RECOMPUTES NOTHING. Every fact is read from an output that already exists - the
release_manifest discipline, and for the same reason: a second arithmetic path is a second
vintage waiting to disagree with the first.

WHAT THIS IS NOT. It carries no grades. A maturity grade is an opinion, and an opinion
published in a machine-readable register is an opinion that stops being re-argued - which is
the defect this file exists to catch, wearing a schema.

Usage:  python3 -m pkinv.report.product_facts
Writes: outputs/pakemis_product_facts.csv
"""

from pkinv.assets import asset_path
import csv
import json
import os

from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

ANNUAL = "pakemis_annual_fy2015_16_fy2024_25.csv"
MONTHLY = "pakemis_monthly_fy2015_16_fy2024_25.csv"
STREAMS = "pakemis_source_streams.csv"
UNALLOCATED = "pakemis_spatial_unallocated.csv"
AGRI_FISCAL = "pakemis_agriculture_fiscal_series.csv"
AGRI_BASIS = "pakemis_agriculture_basis_change.csv"
AGRI_CALENDAR = "pakemis_agriculture_crop_calendar.csv"
LONGITUDINAL_LEVELS = "pakemis_longitudinal_uncertainty.csv"
LONGITUDINAL_TREND = "pakemis_trend_uncertainty.csv"
DEPOSIT = "pakemis_deposit_manifest.csv"
SOURCE_REGISTER = "pakemis_source_register.csv"
TEMPORAL_DECOMPOSITION = "pakemis_temporal_decomposition.csv"


def _rows(name):
    return read_rows(asset_path(OUTPUTS, name))


def _fact(out, fact_id, value, source, basis):
    out.append({"fact_id": fact_id, "value": value, "source_output": source,
                "basis": basis})


def build():
    out = []

    # rc34: these two rows read release_manifest.json - which the Release
    # manifest phase writes AFTER this one, so they saw the previous fixpoint's
    # file - and looked up keys it does not carry, so both shipped "unresolved"
    # for releases. The version is the package's own; the content commit is
    # unknowable before this file is committed, and the manifest holds it.
    import pkinv
    _fact(out, "release_id", pkinv.__version__, "src/pkinv/__init__.py",
          "the release this file describes")
    _fact(out, "commit", "see release_manifest.json describes_commit",
          "release_manifest.json", "the content commit is cut by the fixpoint after "
          "this file is committed, so the manifest holds it and this row points there")

    annual = _rows(ANNUAL)
    years = sorted({r["period_label"] for r in annual})
    _fact(out, "annual_fy_count", len(years), ANNUAL,
          "distinct fiscal years in the nine-year annual product")
    _fact(out, "annual_first_fy", years[0], ANNUAL, "earliest period in the annual product")
    _fact(out, "annual_last_fy", years[-1], ANNUAL, "latest period in the annual product")

    # THE COMMON SCOPE IS DERIVED AND HAS MOVED. annual_product.harmonized_sectors() drops any
    # sector absent in any year of the window; a hand-written tuple used to say eight and was
    # stale, which is the finding that made it derived. The abstract still says eight.
    scope = sorted({r["sector"] for r in annual if r["harmonized_common_scope"] == "yes"})
    _fact(out, "common_scope_sector_count", len(scope), ANNUAL,
          "sectors with no absent year in the harmonized window, derived from the rows")
    _fact(out, "common_scope_sector_ids", ";".join(scope), ANNUAL,
          "the membership itself, sorted so it is diffable")

    ne = [r for r in annual if r["completeness_state"] == "NE"]
    _fact(out, "annual_ne_sector_years", len(ne), ANNUAL,
          "sector-years carrying a notation key rather than an estimate")
    _fact(out, "annual_ne_detail",
          ";".join(sorted("%s/%s" % (r["period_label"], r["sector"]) for r in ne)),
          ANNUAL, "which sector-years those are")
    first = years[0]
    present = {r["sector"] for r in annual
               if r["period_label"] == first and r["completeness_state"] != "NE"}
    _fact(out, "first_fy_estimated_sector_count", len(present), ANNUAL,
          "sectors carrying an estimate in the earliest year; the rest are declared NE")

    # Per sector, the years actually estimated. This is what settles a manuscript claiming a
    # sector is absent for years the atom estimates - the IPPU paper says four of nine are NE.
    by_sector = {}
    for row in annual:
        if row["completeness_state"] != "NE":
            by_sector.setdefault(row["sector"], set()).add(row["period_label"])
    for sector in sorted(by_sector):
        _fact(out, "%s_years_estimated" % sector, len(by_sector[sector]), ANNUAL,
              "fiscal years in which %s carries an estimate rather than a notation key"
              % sector)

    monthly = _rows(MONTHLY)
    months = sorted({r["month"] for r in monthly})
    _fact(out, "monthly_months_published", len(months), MONTHLY,
          "distinct months in the published monthly product - the answer to whether a "
          "108-month product exists")
    _fact(out, "monthly_first_month", months[0], MONTHLY, "earliest month published")
    _fact(out, "monthly_last_month", months[-1], MONTHLY, "latest month published")
    _fact(out, "monthly_rows", len(monthly), MONTHLY, "component-months published")

    # TWO VOCABULARIES FOR ONE CONCEPT, and the register says so rather than picking one.
    # The reference-year layer grades timing T1-T4 (outputs/temporal_profile.csv); the
    # nine-year product grades it TE1-TE4. They mean the same four things. Reading one file
    # with the other's letters silently returns zero, which is how this fact first published
    # a flat share of 0.0 per cent.
    graded = [r for r in monthly if r["temporal_evidence_class"]]
    classes = sorted({r["temporal_evidence_class"] for r in graded})
    _fact(out, "monthly_evidence_vocabulary", ";".join(classes), MONTHLY,
          "the timing-evidence letters the nine-year product uses; the reference-year "
          "layer uses T1-T4 for the same four classes")
    weakest = classes[-1] if classes else ""
    mass = sum(abs(float(r["co2e_Mt_AR5"] or 0.0)) for r in graded)
    weak_mass = sum(abs(float(r["co2e_Mt_AR5"] or 0.0)) for r in graded
                    if r["temporal_evidence_class"] == weakest)
    _fact(out, "monthly_flat_share_pct",
          round(100.0 * weak_mass / mass, 1) if mass else "unresolved", MONTHLY,
          "share of published monthly mass on a declared-flat profile (%s) - the months "
          "exist; this is how much of them is allocation rather than record. SUPERSEDED AS A "
          "HEADLINE by monthly_observed_share_pct / monthly_physical_share_pct / "
          "monthly_weakly_timed_share_pct: this figure is true but says nothing about how "
          "much of that flatness is the physical answer, and most of it is" % weakest)
    _fact(out, "monthly_flat_rows", len([r for r in graded
                                         if r["temporal_evidence_class"] == weakest]),
          MONTHLY, "component-months carrying the weakest timing class")

    # THE ARTEFACT COUNTS, published as facts because I reported them wrong from prose. A
    # summary quoted 405 files against a role table summing to 403, and 13 uncited canonical
    # products where 43 minus 31 is 12 - two runs' figures mixed in one paragraph. The
    # register was right both times. A number a person can retype is a number that will be
    # retyped wrong.
    inventory = _rows("pakemis_artifact_inventory.csv")
    _fact(out, "artifact_count", len(inventory), "pakemis_artifact_inventory.csv",
          "physical files this release ships")
    canonical = [r for r in inventory if r["role"] == "canonical"]
    _fact(out, "canonical_count", len(canonical), "pakemis_artifact_inventory.csv",
          "artefacts declared canonical - a product the release is for")
    _fact(out, "canonical_uncited",
          sum(1 for r in canonical if r["cited_in"] == "none"),
          "pakemis_artifact_inventory.csv",
          "canonical artefacts no manuscript names; ratcheted in "
          "tests/test_artifact_inventory.py with the list in the failure message")
    for tier in sorted({r["release_tier"] for r in inventory}):
        _fact(out, "artifacts_tier_%s" % tier,
              sum(1 for r in inventory if r["release_tier"] == tier),
              "pakemis_artifact_inventory.csv",
              "artefacts in the %s release tier" % tier)

    # AGRICULTURE'S BASIS, in the register rather than in a sentence. Half the inventory,
    # and every number here was measured in a pass that found the seam was an off-by-one
    # rather than a philosophy - so these are exactly the figures a manuscript would be
    # tempted to retype, and exactly the ones a reader would be unable to check.
    fiscal = _rows(AGRI_FISCAL)
    reference = [r for r in fiscal if r["fiscal_end_year"] == "2024"]
    calendar_mass = sum(float(r["co2e_Mt_AR5"]) for r in reference
                        if r["activity_basis"] == "calendar_projection")
    total_mass = sum(float(r["co2e_Mt_AR5"]) for r in reference)
    bases = {r["category"]: r["activity_basis"] for r in fiscal}
    _fact(out, "agriculture_fiscal_basis_categories",
          sum(1 for b in bases.values() if b != "calendar_projection"), AGRI_FISCAL,
          "agriculture categories reconstructed on observed Pakistani fiscal activity")
    _fact(out, "agriculture_calendar_basis_share_pct",
          round(100.0 * calendar_mass / total_mass, 2), AGRI_FISCAL,
          "share of agriculture's reference-year mass whose driver is the FAOSTAT livestock "
          "projection, for which no fiscal enumeration exists")

    change = _rows(AGRI_BASIS)
    # Compare only the eight historical years for which both calendar and
    # fiscal bases exist.  The FY2024-25 extension has no matched archived
    # calendar comparator and must never contribute a fabricated zero delta.
    backcast = [r for r in change if 2016 <= int(r["fiscal_end_year"]) <= 2023]
    _fact(out, "agriculture_basis_change_Mt",
          round(sum(float(r["basis_term_Mt"]) for r in backcast), 4), AGRI_BASIS,
          "what moving eight backcast years from the FAOSTAT-calendar basis to the fiscal "
          "basis was worth, cumulative, excluding the cotton scope term")
    _fact(out, "agriculture_cotton_scope_Mt",
          round(sum(float(r["scope_term_Mt"]) for r in backcast), 4), AGRI_BASIS,
          "cotton, absent from the calendar history and present at the reference year; a "
          "scope break, kept apart from the basis change because they are different claims")

    calendar = _rows(AGRI_CALENDAR)
    misaligned = [r for r in calendar if str(r["best_offset"]) == "-1"]
    _fact(out, "agriculture_crops_misaligned_by_one_year",
          len({r["crop"] for r in misaligned}), AGRI_CALENDAR,
          "crops the former history read a full calendar year late: kharif crops are "
          "harvested in the year before the fiscal year they belong to")

    # THE NINE-YEAR ENSEMBLE. Published as facts because the honest headline here is a
    # negative one - the panel cannot resolve a year-on-year change - and a negative result
    # is exactly the kind a manuscript drifts away from. The count and the diagnostic that
    # explains it are read by claims rather than retyped.
    trend = _rows(LONGITUDINAL_TREND)
    consecutive = [r for r in trend if r["pair_kind"] == "consecutive"]
    typed = [r for r in consecutive if r["scenario"] == "parameter_typed"]
    _fact(out, "trend_consecutive_changes_tested", len(typed), LONGITUDINAL_TREND,
          "consecutive year-on-year changes in the nine-year panel")
    _fact(out, "trend_consecutive_changes_resolved",
          sum(1 for r in typed if r["significant_at_95"] == "yes"), LONGITUDINAL_TREND,
          "consecutive changes whose 95 percent interval excludes zero under the "
          "parameter-typed correlation scenario")
    # TWO WINDOWS, both full-scope since rc20. Until the FY2015-16 product splits were
    # recovered, the longer window straddled an eight-to-ten-sector step and was published
    # as a coverage transition rather than a trend. The recovery made the first year a
    # complete ten-sector national total, so the full-panel window is now a like-for-like
    # emissions change; the FY2016-17 window is retained beside it for continuity with the
    # previously published common-scope result.
    window = next(r for r in trend if r["pair_kind"] == "window_full_panel"
                  and r["scenario"] == "parameter_typed")
    _fact(out, "trend_window_change_Mt", float(window["difference_Mt"]), LONGITUDINAL_TREND,
          "FY2015-16 to FY2023-24 change over the full ten-sector panel - like-for-like "
          "since rc20's recovery of the FY2015-16 product splits")
    _fact(out, "trend_window_significant", window["significant_at_95"], LONGITUDINAL_TREND,
          "whether the full-panel window is resolved at 95 percent under the typed "
          "scenario")
    # The common-scope window MERGED into the full panel at rc20: common_start is
    # derived as the first year whose sector set equals the reference's, and since the
    # FY2015-16 recovery that is the panel's first year, so the differences product
    # publishes ONE window and these facts point at it. The fact ids stay, because the
    # quantity they name - the change over the years every sector reports - is the same
    # quantity; only its span grew.
    _fact(out, "trend_common_window_change_Mt", float(window["difference_Mt"]),
          LONGITUDINAL_TREND,
          "FY2015-16 to FY2023-24 change, the window in which every sector reports "
          "throughout (the full panel, since rc20); the primary trend result")
    _fact(out, "trend_common_window_significant", window["significant_at_95"],
          LONGITUDINAL_TREND,
          "whether the primary trend is resolved at 95 percent under the typed scenario")

    levels = _rows(LONGITUDINAL_LEVELS)
    reference = next(r for r in levels if r["fiscal_end_year"] == "2024"
                     and r["scenario"] == "parameter_typed")
    _fact(out, "uncertainty_variance_share_residual_pct",
          float(reference["variance_share_residual_pct"]), LONGITUDINAL_LEVELS,
          "share of national variance the parameter graph attributes to no named quantity; "
          "correlation cannot cancel what it cannot name, so this is what keeps the trend "
          "band wide")
    _fact(out, "uncertainty_variance_share_persists_pct",
          float(reference["variance_share_persists_pct"]), LONGITUDINAL_LEVELS,
          "share of national variance in parameters that persist across fiscal years")

    # THE MONTHLY PRODUCT'S EVIDENCE, AS THREE FIGURES INSTEAD OF ONE.
    #
    # `monthly_flat_share_pct` above is true and, alone, misleading: it says 80 per cent of
    # the monthly mass carries a flat profile without saying that most of that flatness is
    # the physical answer rather than a gap. A rumen emits every day; a coal plant's flat
    # month is nobody having read the generation records. An external reviewer asked for the
    # claim to be made as three numbers generated from the released rows, and
    # pakemis_temporal_decomposition.csv has computed exactly that split since the monthly
    # layer was built - it was simply never published as a fact or quoted in a manuscript.
    #
    # These are the numbers the release should be judged on. They are read from the
    # decomposition rather than recomputed, because a second arithmetic path to a headline
    # is a second vintage of it.
    from pkinv.report import temporal_decomposition as decomposition
    buckets = decomposition.summary()
    _fact(out, "monthly_observed_share_pct",
          round(buckets[decomposition.OBSERVED][1], 1), TEMPORAL_DECOMPOSITION,
          "X: monthly mass whose within-year variation is carried by an observed monthly "
          "series")
    _fact(out, "monthly_physical_share_pct",
          round(buckets[decomposition.CONTINUOUS][1]
                + buckets[decomposition.STOCK][1], 1), TEMPORAL_DECOMPOSITION,
          "Y: monthly mass whose flat profile is the PHYSICAL answer - continuous or "
          "stock-driven processes, where obtaining a monthly series would not change the "
          "shape")
    _fact(out, "monthly_weakly_timed_share_pct",
          round(buckets[decomposition.UNOBSERVED][1], 1), TEMPORAL_DECOMPOSITION,
          "Z: monthly mass that genuinely varies within the year and is carried flat "
          "because no monthly evidence was obtained. THIS is the gap, and the only one of "
          "the three that acquiring data would close")

    # THE DEPOSIT. What a reader receives, and what they do not - the second of which is the
    # more surprising fact about this release and therefore the one most worth pinning.
    deposit = _rows(DEPOSIT)
    register = _rows(SOURCE_REGISTER)
    _fact(out, "deposit_files", len(deposit), DEPOSIT,
          "files in the archive deposit, assembled from an explicit allowlist")
    _fact(out, "deposit_megabytes",
          round(sum(int(r["bytes"]) for r in deposit if r["bytes"]) / 1e6, 1), DEPOSIT,
          "size of the archive deposit, EXCLUDING the context-stamped artefacts whose size "
          "this manifest cannot record without describing itself - the PDFs, the manifest "
          "and the sidecars. The deposit is larger than this number by those files")
    _fact(out, "deposit_source_documents", 0, DEPOSIT,
          "third-party source documents in the deposit; the register names them and says "
          "where to obtain them instead, because their redistribution terms are mostly not "
          "established and this project cannot license what it does not own")
    _fact(out, "source_documents_archived",
          sum(1 for r in register if r["archival_state"] == "archived"), SOURCE_REGISTER,
          "third-party publications archived in the repository and excluded from the deposit; "
          "the register hashes each and says where to obtain it")
    _fact(out, "source_register_entries", len(register), SOURCE_REGISTER,
          "registered sources, each with its inbound-use and redistribution answers")
    _fact(out, "source_documents_not_redistributable",
          sum(1 for r in register if r["outbound_redistribution"] == "not-established"),
          SOURCE_REGISTER,
          "sources whose publisher states no redistribution terms; the correct answer for a "
          "government publication, and the deposit is built so it costs nothing")

    streams = _rows(STREAMS)
    unplaced = {r["source_stream_id"] for r in _rows(UNALLOCATED)}
    _fact(out, "grid_streams", len(streams), STREAMS, "source streams in the release")
    _fact(out, "grid_streams_allocated", len(streams) - len(unplaced), STREAMS,
          "streams the cube places in cells")
    _fact(out, "grid_streams_unallocated", len(unplaced), UNALLOCATED,
          "streams held at ADM1 because no geometry exists below the provincial control; "
          "they are NOT spread over the grid")

    # --- configuration counts (rc18, the thirteenth review: counted, never
    # remembered - a supplement carried 168 for a release after the factorial
    # grew to 224) -----------------------------------------------------------
    _fact(out, "structural_axes",
          len(_rows("national_axis_register.csv")),
          "national_axis_register.csv", "registered structural axes")
    _fact(out, "named_configurations",
          len(_rows("national_configurations.csv")),
          "national_configurations.csv",
          "named national configurations, families and joint rows included")
    _fact(out, "fugitives_structural_configurations",
          len(_rows("fugitives_structural_factorial_2024.csv")),
          "fugitives_structural_factorial_2024.csv",
          "the fugitives factorial's joint configurations")
    _fact(out, "fugitives_conditional_configurations",
          len(_rows("fugitives_conditional_intervals_2024.csv")),
          "fugitives_conditional_intervals_2024.csv",
          "configurations carrying their own conditional Monte Carlo interval")

    # The nine-fiscal-year air panel (air program Wave 3): the shape claims a reader
    # or a manuscript sentence would otherwise have to count by hand.
    air_atoms = _rows("pakemis_air_atomic_annual.csv")
    _fact(out, "air_atomic_rows", len(air_atoms), "pakemis_air_atomic_annual.csv",
          "one atom per period x sector x category x process x species, covered "
          "sources only")
    cov = _rows("pakemis_air_coverage_matrix.csv")
    _fact(out, "air_coverage_cells", len(cov), "pakemis_air_coverage_matrix.csv",
          "9 periods x 10 modules x 7 core species, every cell typed E/NE/IE/NO/NA")
    _fact(out, "air_coverage_estimated_cells",
          sum(1 for r in cov if r["state"] == "E"), "pakemis_air_coverage_matrix.csv",
          "cells the covered panel estimates; the rest are typed absences, never zeros")
    _fact(out, "air_panel_rollup_rows",
          len(_rows("pakemis_air_annual_fy2015_16_fy2024_25.csv")),
          "pakemis_air_annual_fy2015_16_fy2024_25.csv",
          "the covered-sources rollup at period x sector x category x species")
    # the nine-year air spatial family (air spatial Wave B): the shape facts a reader
    # would otherwise count by hand, from the products themselves
    from netCDF4 import Dataset
    with Dataset(asset_path(OUTPUTS,
                              "pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc")) as ds:
        _fact(out, "air_grid_periods", len(ds.dimensions["time"]),
              "pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc",
              "fiscal periods in the air cube's time axis; the survey-anchored file "
              "carries the same nine")
        _fact(out, "air_grid_species",
              sum(1 for v in ds.variables.values()
                  if getattr(v, "units", "") == "Gg"),
              "pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc",
              "pollutant layers per period, native mass, never summable across species")
    unalloc = _rows("pakemis_air_unallocated_by_year.csv")
    _fact(out, "air_unallocated_rows", len(unalloc),
          "pakemis_air_unallocated_by_year.csv",
          "typed air mass placed at ADM1 and nowhere finer (the aviation cruise "
          "class), per period and configuration - the closure identity's third term")
    return out


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    path = asset_path(OUTPUTS, "pakemis_product_facts.csv")
    write_table(path, list(rows[0]), rows, banner=('# One authoritative answer per fact a manuscript states about the shape of this release.', '# Derived from the products; the claims registry reads this, so a sentence that disagrees fails the build.', '# No grades here: a maturity grade is an opinion, and an opinion in a register stops being re-argued.',))
    print("product facts -> %s" % path)
    print("  %d facts" % len(rows))
    for key in ("common_scope_sector_count", "monthly_months_published",
                "monthly_flat_share_pct", "annual_ne_sector_years",
                "grid_streams_allocated", "grid_streams_unallocated"):
        value = next(r["value"] for r in rows if r["fact_id"] == key)
        print("    %-32s %s" % (key, value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
