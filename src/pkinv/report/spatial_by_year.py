"""The nine-year spatial products: where each year's mass sits, at ADM1 and ADM2.

WHAT THIS IS. Until now the inventory had a nine-year national ledger attached to a one-year
renderer: outputs/pakemis_monthly_fy2015_16_fy2023_24.csv carries all 108 months at national
grain, and everything below the nation existed for FY2023-24 alone. This publishes the other
eight years at ADM1 and ADM2, annually, under the identity the cube already holds per year:

    E(s, y, i) = A(s, y) x P(s, p, y) x W(s, i | p, y)

A is the national panel, evidenced per year. P and W are the cube's own dispatch. What is NOT
evidenced per year is most of W, and the point of this product is that it says so on every row
rather than in a footnote: `spatial_time_basis` names whether a year's within-province
geography was measured for that year or borrowed from the reference year and rescaled.

THE ADM2 VIEW GOES THROUGH THE SAME PARTITION THE MONTHLY VIEW USES, and not through the raw
district vector, which would be quicker and wrong. grid_cube.adm2_view_rows carries the nested
fractional weights (rc32, rc40 G2); binning on grid.districts instead would close every total
and disagree with the shipped ADM2 view at every shared boundary cell - a second vintage of the
same geography, which is the defect this whole pass exists to prevent.

WHAT CLOSES, PER YEAR AND PER GAS.
    national == ADM1
    ADM1     == ADM2 + outside + unallocated_below_adm1
Both are asserted in tests/test_spatial_by_year.py for all nine periods, not for a sample.

Usage:  python3 -m pkinv.report.spatial_by_year
Writes: outputs/pakemis_adm1_by_year.csv
        outputs/pakemis_adm2_by_year.csv
        outputs/pakemis_adm2_monthly_by_year.csv
        outputs/pakemis_adm2_sector_by_year.csv
        outputs/pakemis_grid_fallbacks_by_year.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.report import grid_cube

ADM1_OUT = asset_path(OUTPUTS, "pakemis_adm1_by_year.csv")
ADM2_OUT = asset_path(OUTPUTS, "pakemis_adm2_by_year.csv")
FALLBACK_OUT = asset_path(OUTPUTS, "pakemis_grid_fallbacks_by_year.csv")
MONTHLY_OUT = asset_path(OUTPUTS, "pakemis_adm2_monthly_by_year.csv")
SECTOR_OUT = asset_path(OUTPUTS, "pakemis_adm2_sector_by_year.csv")
UNALLOC_OUT = asset_path(OUTPUTS, "pakemis_spatial_unallocated_by_year.csv")
STREAM_DISTRICT_OUT = asset_path(OUTPUTS, "pakemis_adm2_stream_by_year.csv")
SURFACES_OUT = asset_path(OUTPUTS, "pakemis_grid_stream_surfaces_by_year.csv")

# NO `spatial_time_basis` COLUMN HERE, DELIBERATELY. The badge saying whether a year's
# geography was measured or borrowed belongs to ONE product - the per-stream-year weight
# registry - and it has to be DERIVED from the fallback events a build actually emitted, not
# from the surface a stream declares. Power is why: its plant ledger holds FY2019-20 onward,
# so an earlier year still declares `per_object_activity`, still runs, and places the whole
# sector on built-up through the allow-listed `grid station points -> builtup` substitution.
# A column filled in here would have read `direct_activity` for four years of the largest
# gridded sector. Consumers join the registry on (source_stream_id, period_id).
ADM1_FIELDS = ("period_id", "source_stream_id", "module", "reporting_sector", "sub_category",
               "gas", "spatial_view", "province", "emissions_Gg", "co2e_Mt_AR5")
ADM2_FIELDS = ("period_id", "shape_id", "adm2_ids", "allocation_status", "province",
               "gas", "spatial_view", "emissions_Gg", "absence_reason")
# THE SUBSTITUTION RECORD, PER YEAR, AND WHY IT IS A PRODUCT RATHER THAN A LOG. The cube has
# always priced its fallbacks, but it wrote them for the reference year alone - so a year that
# placed ONE province of one stream on built-up and a year that placed an entire sector that
# way were indistinguishable in everything published. They are not rare edge cases in the
# earlier years: grid power's plant fuel ledger begins in FY2019-20, so the four years before
# it have no per-plant fuel evidence at all and their grid coal is 100% substituted, against
# 0.8% from FY2019-20 on. A reader of the ADM2 table cannot see that; a reader of this file
# can, per stream and per province, with the mass it moved.
FALLBACK_FIELDS = ("period_id",) + tuple(grid_cube.FALLBACK_FIELDS)
# THE MASS NO GEOMETRY COULD PLACE, PER PERIOD. The cube computes this for every period and
# has published it for one: main() writes the reference year to
# pakemis_spatial_unallocated.csv and the other eight were built, used to derive a
# non-numeric marker row, and dropped. So the closure identity
# ADM1 == ADM2 + outside + unallocated could be ASSERTED for nine years and READ for one,
# and a consumer checking a historical year's arithmetic had to take the reference year's
# unallocated mass or nothing. Same rows, same fields, with the period they belong to.
UNALLOC_FIELDS = ("period_id", "source_stream_id", "module", "reporting_sector",
                  "ipcc_category", "gas", "month", "spatial_view", "level", "province",
                  "emissions_Gg", "co2e_Mt_AR5", "reason")
# THE SURFACE EACH STREAM WAS PLACED ON, PER PERIOD, AND THE HASH OF THE PATTERN IT GOT.
# pakemis_grid_stream_surfaces.csv records this for the reference year, and the weight registry
# has been reading THAT for all nine - so the surface, placement and district panel it reports
# against FY2015-16 have until now been FY2023-24's. For most streams they are genuinely the
# same, which is why it went unnoticed; for any stream where they are not, the registry was
# describing a build that did not happen. Same rows, same fields, with the period they belong
# to and the digest of the weight vector the period was actually placed on.
SURFACES_FIELDS = ("period_id",) + tuple(grid_cube.SURFACE_FIELDS)
# THE 108 MONTHS, AT ADM2 AND NOT ON THE GRID. The plan called for a monthly CUBE per period.
# The ANNUAL nine-period cube now ships - see annual_grid.py - so the half of this argument
# about per-cell history is settled and the half about MONTHS is not, which is why the two are
# separated here rather than left as one refusal. Nine MONTHLY 0.05-degree cubes are about
# 51 MB of NetCDF, and what the extra eleven twelfths would carry, for 65.9% of stream-years,
# is the reference year's within-province pattern repeated month by month: precision the
# evidence does not have, in the format most likely to be read as though it did. The annual
# cube is publishable because its provenance ships beside it, per stream and per period, in
# pakemis_spatial_weights_by_year.csv; a monthly one would additionally have to claim a
# historical SEASONAL geography, and nothing in the tree evidences one. The months ship at
# ADM2, the grain consumers query.
MONTHLY_FIELDS = ("period_id", "shape_id", "adm2_ids", "allocation_status", "province",
                  "gas", "month", "spatial_view", "emissions_Gg", "absence_reason")
# MODULE-RESOLVED AND ANNUAL, which is the grain a year slider with a sector filter needs and
# the grain the semantic layer can carry for nine years. The monthly module-resolved history
# would be about 36 MB - nine times the shipped sector file - and what those extra rows would
# store, for two thirds of stream-years, is the reference year's within-province pattern
# repeated a hundred and eight times per district instead of nine. More rows, no more evidence.
# THE PER-STREAM DISTRICT VECTOR, FOR EVERY PERIOD (rc54). pakemis_adm2_stream_reference.csv
# has published this for the reference year since rc47; the other eight periods were computed
# in the same loop and dropped. A district question about anything finer than a module - the
# reporting-sector partition first among them - could therefore only be answered for one year.
# Same generator, same closure: a stream's district rows sum, with its OUTSIDE row, to its
# ADM1 annual mass.
STREAM_DISTRICT_FIELDS = ("period_id", "configuration_id", "module", "reporting_sector",
                          "source_stream_id", "sub_category", "gas", "spatial_view",
                          "shape_id", "adm2_ids", "allocation_status", "province",
                          "emissions_Gg", "absence_reason")
SECTOR_FIELDS = ("period_id", "module", "reporting_sector", "shape_id", "adm2_ids",
                 "allocation_status", "province", "gas", "spatial_view", "emissions_Gg",
                 "co2e_Mt_AR5", "absence_reason")

# ONE FRAME FOR NINE YEARS, SAID OUT LOUD. data/adm2_canonical.csv is fixed at the 2019
# boundary set with the 2023 census names, and every period is published on it. Eleven of its
# units were carved out of larger ones during the window, so a district created in, say, 2017
# still has a FY2015-16 row - and that row means "the mass that would fall inside today's
# boundary", not a figure any administration reported at the time. It is the only choice that
# lets the nine years be compared with each other, and it is a CHOICE, so it is printed on the
# products rather than left to a reader who might reasonably assume the opposite. The frame's
# `effective_date` column cannot supply real creation dates - it holds source labels
# (census_2023, pre_subdivision, ag_census_2024) - and inventing them is not available to us,
# so the gap is carried as an acquisition request instead of guessed at.
GEOMETRY_VERSION = "geoBoundaries-gbOpen-PAK-ADM2-2019"


def periods():
    return [r["period_id"] for r in _activity_rows(asset_path(DATA, "periods.csv"), comments=False)]


def adm1_rows(result, period_id):
    """One row per (stream, province): the stream's own mass times its provincial share.

    The share vector is what the cube dispatched on - result["marginals"] - so this table and
    the grid cannot disagree about which province a stream's mass went to."""
    rows = []
    for stream in result["streams"]:
        sid = stream["source_stream_id"]
        marginals = result["marginals"][sid]
        gwp = grid_cube._gwp_for(stream)
        for province, share in sorted(marginals.items()):
            mass = stream["emissions_Gg"] * share
            if mass == 0.0:
                continue
            rows.append({
                "period_id": period_id,
                "source_stream_id": sid,
                "module": stream["module"],
                "reporting_sector": stream["reporting_sector"],
                "sub_category": stream["sub_category"],
                "gas": stream["gas"],
                "spatial_view": stream["spatial_view"],
                "province": province,
                "emissions_Gg": "%.12g" % mass,
                "co2e_Mt_AR5": "%.12g" % (mass * gwp / 1000.0),
            })
    return rows


def adm2_rows(view, period_id):
    """The monthly ADM2 view, summed to the year. The rows come from grid_cube's own generator
    so the annual, monthly and reference-year views all share one partition."""
    annual = collections.OrderedDict()
    for row in view:
        key = (row["shape_id"], row["adm2_ids"], row["allocation_status"], row["province"],
               row["gas"], row["spatial_view"], row["absence_reason"])
        if row["emissions_Gg"] == "":
            annual.setdefault(key, None)          # a declared absence stays non-numeric
            continue
        annual[key] = (annual.get(key) or 0.0) + float(row["emissions_Gg"])
    out = []
    for key, value in annual.items():
        shape_id, adm2_ids, status, province, gas, view, absence = key
        out.append({"period_id": period_id, "shape_id": shape_id, "adm2_ids": adm2_ids,
                    "allocation_status": status, "province": province, "gas": gas,
                    "spatial_view": view,
                    "emissions_Gg": "" if value is None else "%.12g" % value,
                    "absence_reason": absence})
    return out


def sector_rows(result, period_id):
    """The module-resolved ADM2 view, summed to the year, from grid_cube's own generator.
    The exact co2e column sums beside the mass: it was priced per stream at accumulation
    (each stream's own CH4 origin), so the annual value stays exact through this sum."""
    annual = collections.OrderedDict()
    for row in grid_cube.adm2_sector_rows(result):
        key = (row["module"], row["reporting_sector"], row["shape_id"], row["adm2_ids"],
               row["allocation_status"], row["province"], row["gas"], row["spatial_view"],
               row["absence_reason"])
        if row["emissions_Gg"] == "":
            annual.setdefault(key, None)
            continue
        mass, co2e = annual.get(key) or (0.0, 0.0)
        annual[key] = (mass + float(row["emissions_Gg"]),
                       co2e + float(row["co2e_Mt_AR5"]))
    out = []
    for key, value in annual.items():
        module, reporting, shape_id, adm2_ids, status, province, gas, view, absence = key
        out.append({"period_id": period_id, "module": module, "reporting_sector": reporting,
                    "shape_id": shape_id,
                    "adm2_ids": adm2_ids, "allocation_status": status, "province": province,
                    "gas": gas, "spatial_view": view,
                    "emissions_Gg": "" if value is None else "%.12g" % value[0],
                    "co2e_Mt_AR5": "" if value is None else "%.12g" % value[1],
                    "absence_reason": absence})
    return out


def build(period_sink=None, capture_cells=None):
    """`period_sink` receives each period as it is built and before it is dropped.

    The nine cubes have always been computed here; what was missing was somewhere for them to
    go. A sink keeps ONE period resident, which is what this loop already did - collecting nine
    would be about 1.3 GB of float64 accumulators and a different program.

    `capture_cells` names the streams whose placed cell vector the sink needs verbatim
    (the air spatial lane's anchors); grid_cube retains them under
    result["captured_cells"] for the sink and they drop with the period as before.
    """
    adm1, adm2, monthly, sector, fallbacks, unallocated, surfaces = [], [], [], [], [], [], []
    # THE PER-STREAM DISTRICT VECTOR, FOR EVERY PERIOD (rc54). grid_cube computes it for each
    # period at accumulation and the reference year's has been published since rc47; the other
    # eight were built here and dropped with the period. Collecting them costs one pass over
    # rows that already exist, and it is what lets the district layer answer a per-stream
    # question - the reporting-sector partition among them - for the whole window.
    stream_district = []
    for time_index, period_id in enumerate(periods()):
        result = grid_cube.build(period=grid_cube.period_keys(period_id), ledger=False,
                                 capture_cells=capture_cells)
        if period_sink is not None:
            period_sink.write(time_index, period_id, result)
        # Built ONCE per period and shared: the annual table is this view summed, and the
        # monthly table is this view itself. Deriving them separately is how two views of one
        # geography drift apart.
        view = grid_cube.adm2_view_rows(result)
        adm1.extend(adm1_rows(result, period_id))
        adm2.extend(adm2_rows(view, period_id))
        monthly.extend(dict({"period_id": period_id}, **row) for row in view)
        sector.extend(sector_rows(result, period_id))
        for row in grid_cube.adm2_stream_rows(result):
            stream_district.append(dict({"period_id": period_id}, **row))
        for row in grid_cube.fallback_rows(result["exceptions"]):
            fallbacks.append(dict({"period_id": period_id}, **row))
        for row in result["unallocated"]:
            unallocated.append(dict({"period_id": period_id}, **row))
        for row in result["surfaces"]:
            surfaces.append(dict({"period_id": period_id}, **row))
    return (adm1, adm2, monthly, sector, fallbacks, unallocated, surfaces,
            stream_district)


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    from pkinv.core.gis.grid import build_grid
    from pkinv.report.annual_grid import AnnualGridWriter, CORE, period_bounds
    from pkinv.report.air_annual_grid import (AirAnnualGridWriter,
                                              REF_PATH as AIR_REF,
                                              SURVEY_PATH as AIR_SURVEY)
    from pkinv.report.air_spatial_by_year import AirSink
    grid = build_grid()
    bounds = period_bounds()
    temporary = CORE + ".partial"
    air_ref_tmp, air_survey_tmp = AIR_REF + ".partial", AIR_SURVEY + ".partial"
    # The air lane is a SECOND sink on the same residency: the pollutant masses ride
    # the very vectors each period's cube placed their anchor streams on, so the two
    # families cannot disagree about where a stream's mass went.
    with AnnualGridWriter(temporary, grid, bounds) as writer, \
            AirAnnualGridWriter(air_ref_tmp, grid, bounds,
                                "REF_2023_24") as air_ref_writer, \
            AirAnnualGridWriter(air_survey_tmp, grid, bounds,
                                "L_HERD1624") as air_survey_writer:
        air = AirSink(grid, {"REF_2023_24": air_ref_writer,
                             "L_HERD1624": air_survey_writer})

        class _BothSinks:
            def write(self, time_index, period_id, result):
                writer.write(time_index, period_id, result)
                air.write(time_index, period_id, result)

        (adm1, adm2, monthly, sector, fallbacks, unallocated,
         surfaces, stream_district) = build(period_sink=_BothSinks(), capture_cells=air.anchors)
    air.close()
    # ATOMIC: a half-written cube must never be mistaken for a product. The reader that
    # opens this file next may be a release gate.
    os.replace(temporary, CORE)
    os.replace(air_ref_tmp, AIR_REF)
    os.replace(air_survey_tmp, AIR_SURVEY)
    for path, fields, rows in ((ADM1_OUT, ADM1_FIELDS, adm1), (ADM2_OUT, ADM2_FIELDS, adm2),
                               (MONTHLY_OUT, MONTHLY_FIELDS, monthly),
                               (SECTOR_OUT, SECTOR_FIELDS, sector),
                               (FALLBACK_OUT, FALLBACK_FIELDS, fallbacks),
                               (UNALLOC_OUT, UNALLOC_FIELDS, unallocated),
                               (SURFACES_OUT, SURFACES_FIELDS, surfaces),
                               (STREAM_DISTRICT_OUT, STREAM_DISTRICT_FIELDS, stream_district)):
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields))
            writer.writeheader()
            writer.writerows(rows)
    print("nine-year spatial products")
    print("  %-44s %6d rows" % (os.path.relpath(ADM1_OUT), len(adm1)))
    print("  %-44s %6d rows" % (os.path.relpath(ADM2_OUT), len(adm2)))
    print("  %-44s %6d rows" % (os.path.relpath(MONTHLY_OUT), len(monthly)))
    print("  %-44s %6d rows" % (os.path.relpath(SECTOR_OUT), len(sector)))
    print("  %-44s %6d rows" % (os.path.relpath(UNALLOC_OUT), len(unallocated)))
    print("  %-44s %6d rows" % (os.path.relpath(STREAM_DISTRICT_OUT), len(stream_district)))
    print("  %-44s %6d rows" % (os.path.relpath(SURFACES_OUT), len(surfaces)))
    print("  %-44s %6.1f MB" % (os.path.relpath(CORE),
                                os.path.getsize(CORE) / 1e6))
    print("  %-44s %6d rows" % (os.path.relpath(FALLBACK_OUT), len(fallbacks)))
    from pkinv.report import air_spatial_by_year as air_out
    print("  %-44s %6.1f MB" % (os.path.relpath(AIR_REF),
                                os.path.getsize(AIR_REF) / 1e6))
    print("  %-44s %6.1f MB" % (os.path.relpath(AIR_SURVEY),
                                os.path.getsize(AIR_SURVEY) / 1e6))
    for path in (air_out.ADM1_OUT, air_out.ADM2_OUT, air_out.UNALLOC_OUT):
        with open(path, encoding="utf-8") as handle:
            n = sum(1 for _ in handle) - 1
        print("  %-44s %6d rows" % (os.path.relpath(path), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
