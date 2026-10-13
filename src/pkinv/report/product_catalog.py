"""The product catalogue: one row per logical scientific product, and the table it generates.

WHY THIS EXISTS NOW. The supplement's product table was maintained by hand, and it drifted:
its uncertainty row read "reference year only ... There is no time-correlated ensemble ... and
none is published" while `pakemis_longitudinal_uncertainty.csv` and
`pakemis_trend_uncertainty.csv` had been shipping for releases and the main paper described
their three scenarios. A reviewer reading both could not tell which document was authoritative,
and no test could see the contradiction because the sentence was prose and the products were
files.

Patching that sentence would have fixed the instance. Generating the table fixes the class:
a product cannot be in the release and absent from the table, and cannot be described by a
status the catalogue does not hold.

WHAT A ROW IS. A LOGICAL product, not a file. `pakemis_annual_fy2015_16_fy2023_24.csv` and its
`.parquet` twin are one product in two representations, which is why counting citation coverage
over file extensions has always been slightly wrong.

THE SCHEMA IS NOT INVENTED HERE. docs/product_catalog_design.md specified these fields and
their vocabularies, and said in its own first paragraph that it existed "so the next pass
implements a decided design rather than re-deriving one". This is that pass, for the slice the
supplement's table needs.

WHAT THIS IS NOT, and the design document keeps the rest as declared-not-built: there is no
artifact_manifest.csv, no packaging allowlist, and the `*` catch-all in data/artifact_roles.csv
still stands. Exit criteria 4, 5 and 6 of that document are met here - every core product has
exactly one family, a documentation anchor and an existing artifact - and the others are not.

Usage:  python3 -m pkinv.report.product_catalog
Writes: outputs/pakemis_product_catalog.csv
        paper_national/sections/generated_products.tex
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS, ROOT
from pkinv.paths import PAPER_NATIONAL_SECTIONS  # noqa: E402
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_product_catalog.csv")
TEX = asset_path(PAPER_NATIONAL_SECTIONS, "generated_products.tex")

FIELDS = ("product_id", "product_family", "release_tier", "artifact_kind", "ship",
          "primary_artifact", "representations", "documentation_anchor", "generated_by",
          "status", "what_it_is_and_is_not")

FAMILY_ORDER = ("annual", "monthly", "spatial", "uncertainty", "semantic")
FAMILY_LABEL = {"annual": "Annual", "monthly": "Monthly", "spatial": "Spatial",
                "uncertainty": "Uncertainty", "semantic": "Semantic layer"}

# One row per logical product. `status` is the word the supplement prints, and it is a property
# of the product rather than a sentence about it: a product whose status and description live
# here cannot be described differently in the manuscript, because the manuscript no longer
# contains the description.
# WHAT A documentation_anchor HAS TO DO, since for several releases it did not have to do
# anything. The design in docs/product_catalog_design.md replaced "every shipped filename must
# be cited" with "every core logical product must have one documentation_anchor", and the only
# guard on it asserted the field was non-empty. On 2026-10-05, 8 of the 23 anchors resolved to
# nothing: four said supp:products, and the supplement has no product table - the table is
# tab:products in sections/50_data_records.tex, in the MAIN document - and four said
# main:spatial, where no label ending :spatial is reachable from paper_national.tex, because
# the only sec:spatial in the tree belongs to the technical supplement. A pointer nobody
# dereferences is the same defect as a citation nobody checks, one level out, and it replaced
# a mechanism that WAS checked.
#
# The form is <doc>:<label-suffix>, where doc is main (paper_national.tex) or supp
# (supplement.tex) and the suffix is what follows the colon in a \label{} reachable through
# that document's \input tree. tests/test_product_catalog_anchors.py resolves every one.
CATALOG = (
    dict(product_id="annual.reference_year", product_family="annual", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="national_all_sectors.csv", representations="csv",
         documentation_anchor="main:results", generated_by="pkinv.report.national_rollup",
         status="mature",
         what_it_is_and_is_not="Ten sectors on one reporting period, exact mass closure and "
                               "executable cross-boundary ledgers."),
    dict(product_id="annual.panel", product_family="annual", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_annual_fy2015_16_fy2023_24.csv",
         representations="csv;parquet",
         documentation_anchor="main:results", generated_by="pkinv.report.annual_product",
         # "partial by declaration" survived here for two releases after the FY2015-16
         # recovery made it false - the sixteenth review read it beside the main paper's
         # "complete 90-sector-year rectangle" and correctly called the pair a
         # contradiction. Sector-year coverage is complete; what remains partial is
         # CATEGORY SCOPE (the NE categories), which is the completeness matrix's
         # statement to make, not this status word's.
         status="mature",
         what_it_is_and_is_not="Sector, category and gas for all 90 sector-years - the "
                               "rectangle is complete since the FY2015-16 recovery; "
                               "category scope stays partial and the completeness matrix "
                               "says where. TWO views; only the harmonized common scope "
                               "may be differenced."),
    dict(product_id="annual.pass2_scorecard", product_family="annual",
         release_tier="core", artifact_kind="register", ship="yes",
         primary_artifact="pakemis_pass2_scorecard.csv", representations="csv",
         documentation_anchor="main:limitations",
         generated_by="pkinv.report.pass2_scorecard", status="new",
         what_it_is_and_is_not="The Pass-2 exit gate scored from shipped products: "
                               "two outcomes met, one met with named exclusions, "
                               "and the monthly outcome refused by type with its "
                               "arithmetic printed. A verdict register, never an "
                               "estimate."),
    dict(product_id="annual.completeness_mass", product_family="annual",
         release_tier="core", artifact_kind="register", ship="yes",
         primary_artifact="pakemis_completeness_mass.csv", representations="csv",
         documentation_anchor="main:limitations",
         generated_by="pkinv.report.completeness_mass", status="new",
         what_it_is_and_is_not="Every absent stream joined to the bound the shipped "
                               "arithmetic supports - a measured completeness band "
                               "with contained claimants excluded from its sums. A "
                               "register of what is missing and what it would "
                               "weigh, never a distribution and never part of any "
                               "total."),
    dict(product_id="spatial.rice_geography_crosscheck", product_family="spatial",
         release_tier="core", artifact_kind="crosscheck", ship="yes",
         primary_artifact="pakemis_rice_geography_crosscheck.csv",
         representations="csv", documentation_anchor="main:results",
         generated_by="pkinv.report.rice_geography_crosscheck", status="new",
         what_it_is_and_is_not="The declared MapSPAM rice surface measured against "
                               "the own-year GCD-Rice 2023 30 m classification, as "
                               "within-province ADM2 shares with per-unit verdicts. "
                               "A measurement of a disagreement, never a surface "
                               "switch - the fork is priced as the "
                               "agriculture_rice_gcd2023_adm2 bracket."),
    dict(product_id="spatial.stream_support_ledger", product_family="spatial",
         release_tier="core", artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_stream_support_ledger.csv",
         representations="csv", documentation_anchor="main:results",
         generated_by="scripts.build_stream_support_ledger", status="new",
         what_it_is_and_is_not="One row per (period, stream): the mass beside the "
                               "support that placed it - geometry, surface, panel, "
                               "measured located share, priced fallback and "
                               "ADM1-retained masses, grade, pattern hash and the "
                               "monthly-support refusal stated per row. Rectangular "
                               "with typed absence. The audit's three-file hand-join, "
                               "done once and pinned; never a second allocation."),
    dict(product_id="spatial.adm2_frame_2022", product_family="spatial",
         release_tier="core", artifact_kind="crosswalk", ship="yes",
         primary_artifact="pakemis_adm2_frame_2022.csv",
         representations="csv", documentation_anchor="main:results",
         generated_by="scripts.build_adm2_frame_2022", status="new",
         what_it_is_and_is_not="The OCHA COD-AB 2022 ADM2 frame (160 units, CC BY-IGO) "
                               "crosswalked to the canonical 152-unit set: twelve of the "
                               "fourteen collision groups plus Larkana and Tor Ghar "
                               "RESOLVE, Keamari and Surab stay part_of. The complete, "
                               "tested preparation for the v1.1 re-rasterisation - and "
                               "deliberately NOT that re-rasterisation: every shipped "
                               "shape_id stays on the frozen 2019 frame this release."),
    dict(product_id="spatial.grid_0p1_edgar_aligned", product_family="spatial",
         release_tier="core", artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_grid_0p1_edgar_aligned.nc",
         representations="netcdf", documentation_anchor="main:results",
         generated_by="scripts.build_grid_01deg", status="new",
         what_it_is_and_is_not="The annual 0.05-degree cube aggregated 2x2 at the ODD "
                               "parity that tiles EDGAR's 0.1-degree lattice exactly "
                               "(interior 133x169; three half-covered boundary strips "
                               "declared in coverage_fraction), conservation asserted "
                               "per layer. A derived benchmark-comparison surface - "
                               "the frozen 0.05 lattice remains the product of record."),
    dict(product_id="spatial.agri_reference_panel_divergence", product_family="spatial",
         release_tier="core", artifact_kind="crosscheck", ship="yes",
         primary_artifact="agri_reference_panel_divergence.csv",
         representations="csv", documentation_anchor="main:results",
         generated_by="scripts.build_agri_panel_divergence", status="new",
         what_it_is_and_is_not="The reference-year crop split measured proxy-vs-panel "
                               "(rc47 Wave 1): within-province shares per (category, "
                               "shape) under the MapSPAM/cropland proxy product and "
                               "the PBS district crop panel the allocation reads. "
                               "The record of what putting FY2023-24 on the panel "
                               "changed, and of why field burning declined both "
                               "panels for its own-year FIRMS raster - a measured "
                               "disagreement, never a second allocation."),
    dict(product_id="annual.atomic", product_family="annual", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_atomic_annual.csv", representations="csv",
         documentation_anchor="main:products", generated_by="pkinv.report.atomic_annual",
         status="mature",
         what_it_is_and_is_not="The component grain beneath the panel: every priced stream, "
                               "with its evidence class, for all nine periods."),
    dict(product_id="monthly.panel", product_family="monthly", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_monthly_fy2015_16_fy2023_24.csv",
         representations="csv;parquet",
         documentation_anchor="main:monthly", generated_by="pkinv.report.monthly_all_years",
         status="allocation, not observation",
         what_it_is_and_is_not="{months} months, July 2015 to June 2024, every non-absent "
                               "component resolved into twelve months closing exactly to its "
                               "annual figure. {flat_share} per cent of the published monthly "
                               "mass sits on a flat profile, against {reference_flat_share} "
                               "per cent in the reference year alone. Read a flat month as an "
                               "allocation, never as an observation."),
    dict(product_id="monthly.coverage", product_family="monthly", release_tier="core",
         artifact_kind="diagnostic", ship="yes",
         primary_artifact="pakemis_monthly_coverage_summary.csv", representations="csv",
         documentation_anchor="main:monthly", generated_by="pkinv.report.monthly_coverage",
         status="complete",
         what_it_is_and_is_not="Exactly 108 rows: what each month's timing rests on, and which "
                               "sectors a month does not have at all."),
    dict(product_id="spatial.cube", product_family="spatial", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_grid_0p05_monthly.nc", representations="netcdf",
         documentation_anchor="main:cube", generated_by="pkinv.report.grid_cube",
         status="allocation, partly observed",
         what_it_is_and_is_not="The 0.05 degree MONTHLY cube in native gas mass, with district "
                               "and provincial views, for the reference year. The monthly grain "
                               "is the reference year's alone; the nine fiscal years are "
                               "gridded ANNUALLY in "
                               "pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc and "
                               "tabulated at ADM1 and ADM2 in pakemis_adm1_by_year.csv and "
                               "pakemis_adm2_by_year.csv."),
    dict(product_id="spatial.cube_annual", product_family="spatial", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc",
         representations="netcdf",
         documentation_anchor="main:cube", generated_by="pkinv.report.spatial_by_year",
         status="allocation, evidence-graded per stream and period",
         what_it_is_and_is_not="Nine fiscal periods at 0.05 degrees, three spatial views, three "
                               "gases, in native mass. Each period is generated from its own "
                               "atomic streams, NOT by rescaling the reference year's map. "
                               "Cells plus pakemis_spatial_unallocated_by_year.csv reproduce "
                               "each period's national control. The views PARTITION the placed "
                               "mass and must not be added to one another's totals. Whether a "
                               "period's within-province pattern is its own or borrowed is "
                               "stated per stream in pakemis_spatial_weights_by_year.csv. "
                               "There is no historical configuration S and no historical "
                               "monthly grain."),
    dict(product_id="spatial.by_year", product_family="spatial", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_adm1_by_year.csv", representations="csv",
         documentation_anchor="main:cube", generated_by="pkinv.report.spatial_by_year",
         status="allocation, geography borrowed outside the reference year",
         what_it_is_and_is_not="Nine fiscal years at ADM1 and ADM2, annually. Each year's "
                               "national mass is evidenced for that year; the within-province "
                               "geography is the reference year's, rescaled - so this is a "
                               "reconstruction of where past emissions most likely sat, not "
                               "nine years of observed district data. It is also the only "
                               "ADM1 table configuration L has: "
                               "pakemis_grid_provincial_check.csv is a share check."),
    dict(product_id="spatial.unallocated", product_family="spatial", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_spatial_unallocated.csv", representations="csv",
         documentation_anchor="main:cube", generated_by="pkinv.report.spatial_unallocated",
         status="declared, not gridded",
         what_it_is_and_is_not="The mass with no defensible placement below ADM1, retained "
                               "rather than spread. National closure is raster plus this."),
    dict(product_id="uncertainty.reference_year", product_family="uncertainty",
         release_tier="core", artifact_kind="estimate", ship="yes",
         primary_artifact="national_uncertainty_montecarlo.csv", representations="csv",
         documentation_anchor="main:uncertainty", generated_by="pkinv.eval.uncertainty",
         status="mature",
         what_it_is_and_is_not="A 100,000-draw national Monte Carlo consuming two sectors' own "
                               "engines, plus twenty structural axes priced as named "
                               "configurations."),
    dict(product_id="uncertainty.common_ensemble", product_family="uncertainty",
         release_tier="core", artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_ensemble_summary.csv",
         representations="csv;parquet",
         documentation_anchor="main:uncertainty",
         generated_by="pkinv.report.common_ensemble",
         status="joinable, reference year",
         what_it_is_and_is_not="A 10,000-draw prefix of the national Monte Carlo "
                               "carried to months and provinces on one draw_id, "
                               "with both closure identities holding inside every "
                               "draw. Profile weights are drawn only where a "
                               "measured dispersion exists; allocation is "
                               "conditional, never mixed."),
    dict(product_id="uncertainty.longitudinal", product_family="uncertainty",
         release_tier="core", artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_longitudinal_uncertainty.csv", representations="csv",
         documentation_anchor="main:uncertainty",
         generated_by="pkinv.report.longitudinal_uncertainty",
         status="published, and negative",
         what_it_is_and_is_not="Nine annual bands under three temporal-correlation "
                               "assumptions, typed persistent against redrawn. It exists; an "
                               "earlier edition of this table said it did not."),
    dict(product_id="uncertainty.trend", product_family="uncertainty", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="pakemis_trend_uncertainty.csv", representations="csv",
         documentation_anchor="main:uncertainty",
         generated_by="pkinv.report.longitudinal_uncertainty",
         status="published, and negative",
         what_it_is_and_is_not="Draw-wise year-on-year and window differences, each pair "
                               "restricted to the sectors both years report. No "
                               "year-on-year change is resolved at 95 per cent; the "
                               "multi-year windows now are, under the typed scenario."),
    # v1.0.0: the semantic layer - the four families above re-expressed as typed fact and
    # dimension tables under one contract, the layer every consumer reads by hash
    dict(product_id="semantic.release", product_family="semantic", release_tier="core",
         artifact_kind="contract", ship="yes",
         primary_artifact="semantic/semantic_release.json", representations="json",
         documentation_anchor="main:products", generated_by="pkinv.semantic.build",
         status="mature",
         what_it_is_and_is_not="The semantic contract: release identity, the dimensions and "
                               "their values, the defaults, the rounding and aggregation rules, "
                               "the source digests and the known limitations. Byte-stable and "
                               "hashed by the release manifest; it stamps no commit."),
    dict(product_id="semantic.facts", product_family="semantic", release_tier="core",
         artifact_kind="estimate", ship="yes",
         primary_artifact="semantic/fact_annual.csv", representations="csv;parquet",
         documentation_anchor="main:products", generated_by="pkinv.semantic.build",
         status="mature",
         what_it_is_and_is_not="Twelve fact tables (annual, calendar, monthly, ADM1, ADM2, "
                               "unallocated, uncertainty, completeness, transfers, evidence) "
                               "whose values are the products' own strings; the only arithmetic "
                               "is exact decimal products of two shipped numbers, closure-tested."),
    dict(product_id="semantic.dimensions", product_family="semantic", release_tier="core",
         artifact_kind="registry", ship="yes",
         primary_artifact="semantic/dim_period.csv", representations="csv;parquet",
         documentation_anchor="main:products", generated_by="pkinv.semantic.build",
         status="mature",
         what_it_is_and_is_not="Ten dimension tables: the closed vocabularies every fact row "
                               "keys into (periods on both bases, months, configurations, GWP "
                               "factors, gases, IPCC categories, geographies, streams, evidence "
                               "grades, notation keys)."),
)


def _facts():
    """The live numbers the table prints, computed from the products themselves.

    The descriptions carry figures - how many months, what share is flat, what resolution -
    and a generated table whose NUMBERS were typed by hand would only have moved the drift
    one file along. These are read from the products on every render.
    """
    summary = _rows(asset_path(OUTPUTS, "pakemis_monthly_coverage_summary.csv"))
    total = sum(float(r["co2e_Mt_AR5"]) for r in summary)
    flat = sum(float(r["TE4_Mt"]) for r in summary)
    reference = [r for r in summary if r["period_id"] == "FY2023-24"]
    ref_total = sum(float(r["co2e_Mt_AR5"]) for r in reference)
    ref_flat = sum(float(r["TE4_Mt"]) for r in reference)
    return {
        "months": len(summary),
        "flat_share": round(100.0 * flat / total, 1),
        "reference_flat_share": round(100.0 * ref_flat / ref_total, 1),
    }


def _rows(path):
    return read_rows(path)


def catalog():
    facts = _facts()
    return [dict(row, what_it_is_and_is_not=row["what_it_is_and_is_not"].format(**facts))
            for row in CATALOG]


def _escape(text):
    return text.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")


def render(rows):
    """The supplement's product table, generated. One row per catalogued core product."""
    lines = [
        "% GENERATED by pkinv.report.product_catalog -- do not edit.",
        "% The supplement's product table was hand-maintained and drifted: it described the",
        "% uncertainty family as reference-year only while two longitudinal products shipped.",
        "% It is generated now so a product cannot be in the release and absent from the table.",
        r"\begin{tabular}{@{}p{0.20\linewidth}p{0.16\linewidth}p{0.56\linewidth}@{}}",
        r"\toprule",
        r"\textbf{Product} & \textbf{Status} & \textbf{What it is, and what it is not} \\",
        r"\midrule",
    ]
    for family in FAMILY_ORDER:
        for row in [r for r in rows if r["product_family"] == family
                    and r["release_tier"] == "core"]:
            lines.append("%s &\n%s &\n%s \\texttt{%s}. \\\\" % (
                _escape("%s: %s" % (FAMILY_LABEL[family],
                                    row["product_id"].split(".", 1)[1].replace("_", " "))),
                _escape(row["status"]),
                _escape(row["what_it_is_and_is_not"]),
                _escape(row["primary_artifact"])))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def missing_artifacts(rows=None):
    """Catalogued products whose primary artifact is not on disk - exit criterion 6."""
    return [row["product_id"] for row in (rows or catalog())
            if not os.path.exists(asset_path(OUTPUTS, row["primary_artifact"]))]


def main():
    rows = catalog()
    absent = missing_artifacts(rows)
    if absent:
        raise SystemExit("catalogued products with no artifact on disk: %s" % absent)

    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows, banner=('# ONE ROW PER LOGICAL PRODUCT, not per file: a CSV and its Parquet twin are one product in two representations.', "# The supplement's product table is GENERATED from this, so a product cannot ship and be absent from the table, and", '# cannot be described there by a status this file does not hold.',))

    with open(TEX, "w", encoding="utf-8") as handle:
        handle.write(render(rows))

    import collections
    print("product catalog -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d logical products across %d families"
          % (len(rows), len({r["product_family"] for r in rows})))
    for family, count in sorted(collections.Counter(r["product_family"]
                                                    for r in rows).items()):
        print("    %-12s %d" % (family, count))
    print("  every primary artifact resolves on disk")
    print("  table -> %s" % os.path.relpath(TEX, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
