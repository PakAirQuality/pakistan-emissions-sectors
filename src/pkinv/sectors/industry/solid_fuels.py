"""Industrial solid-fuel combustion: brick-kiln and cement-sector coal (rc46 Wave 2).

THE SERIES THE TYPED REFUSAL NAMED. The industry fuel ledger carried a refusal -
refused_no_series_held - for industrial coal since the screening decomposition, and the
sector's own docstring called itself "a floor on 1A2, not an estimate of it". The HDIP
coal-by-consumer series (Finance Division Statistical Supplement, Table 14.1 section 4,
transcribed to data/activity/industry/coal_by_consumer.csv) now supplies national coal to
brick kilns and to the cement sector for every year of the inventory window, so those two
streams enter the reference estimate through the industrial_solid_fuels_1a2 activation gate.

WHAT THE SOURCE IS, SAID PLAINLY. The table is marked "** Estimated" by its own footer, and
its consumption categories EXHAUST supply: Table 14.3's imports-plus-production reproduces
Table 14.1's total to about half a kilotonne in eight of nine years. THAT CLOSURE IS FORCED,
NOT INDEPENDENT (2026-09-10): the two tables balance by construction - the FY2023-24
inter-edition revision moved production and consumption by an identical -434 kt - so it
verifies the transcription, not the sectoral split. Sectoral coal is a constructed
allocation of a measured total, not a set of meters; HDIP states its own allocation rule
(Economic Survey 2025-26 ch.14, held): Thar coal to the Thar power plants, other coalfields'
coal to brick kilns, imported coal to power plants and the industrial sector. TWO FACTS the
split rests on, both under reconciliation (outputs/pakemis_coal_source_reconciliation.csv):
(1) the BRICK column behaves as a residual-style bucket - HDIP's power column and NEPRA's
independently metered named-station coal disagree with opposite signs in exactly the
brick-spike years (outputs/industry_coal_reconciliation.csv) - a HYPOTHESIS under test, not
a demonstrated mechanism; (2) the column the Supplement prints as "Cement" is printed
"Cement/Others" by the Economic Survey (2025-26 Table 14.10) and "Cement/Other Industry" by
the PEY (Table 4.4, witnessed in sources/Papers/Punjab Industry.pdf s3.1) - so
"Cement-sector coal" here may carry steel, textile and chemical coal UNSPLIT. "Other
industrial coal" is therefore not zero but unseparated inside this column; the engine does
not yet split it. Petcoke is not in the table at all - the petcoke trade screening remains
its own lane.

THE ONE YEAR THAT DOES NOT CLOSE IS A VINTAGE DIAGNOSIS. FY2015-16's printed consumption
exceeds supply by 203.8 kt - almost exactly the 204.0 kt by which the supplement's revised
brick figure (3,541.1) exceeds the PEY 2018 edition's (3,337.1). The older vintage closes
the balance; the revision breaks it. This module adopts the balance-consistent 3,337.102 kt
for FY2015-16 (the exact tonnes held in brick_kiln_coal.csv) and types the supplement print
as a balance-breaking revision. Every other year is the supplement's final vintage.

FACTORS come from the registry (Other Bituminous Coal: 94,600/10/1.5 kg per TJ on 25.8 TJ/Gg
+/-21% - the same figures and bucket the rc13 screening declared). The screening module
stays: it is the air-pollutant lane and the historical comparator, and its clinker-derived
cement KILN FUEL model (13.59 Mt, band 11.99-15.65 at the 16-company census; the earlier
13.38 / 11.8-15.4 was the 14-company vintage) is a REPLACEMENT comparator priced NET of this
stream (cement_kiln_fuel_in_scope, +2.80 Mt) - never added to it, never a candidate for the
total on its own.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import functools
import os

from pkinv.paths import DATA

ITEM = "Other Bituminous Coal"
SERIES = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
VINTAGES = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")
POLICY = asset_path(DATA, "coal_booking_policy.csv")
CONSUMER_SECTOR = {"brick_kilns": "brick_kilns", "cement": "cement_other"}

STREAMS = (
    # (consumer column, subitem label)
    ("brick_kilns", "Brick-kiln coal"),
    ("cement", "Cement-sector coal"),
)


def _rows(path):
    return list(_activity_rows(path, comments=True))


@functools.lru_cache(maxsize=1)
def _booked():
    """(fiscal_label, consumer) -> (kt, estimate_id, rule): the print data/coal_booking_policy.csv
    names, resolved in the vintages table. The policy is the only place an edition is chosen."""
    prints = {r["estimate_id"]: r for r in _rows(VINTAGES)}
    out = {}
    for r in _rows(POLICY):
        est = prints.get(r["booked_estimate_id"])
        if est is None:
            raise KeyError("coal_booking_policy.csv books %s, which coal_by_sector_vintages.csv "
                           "does not print" % r["booked_estimate_id"])
        if est["period_coverage"] != "full_year":
            raise ValueError("%s is a %s print: only full years may be booked"
                             % (est["estimate_id"], est["period_coverage"]))
        if (est["reference_fiscal_year"] != r["reference_fiscal_year"]
                or est["sector_mapped"] != CONSUMER_SECTOR[r["consumer"]]):
            raise ValueError("%s books %s %s but the print is %s %s" % (
                r["booked_estimate_id"], r["reference_fiscal_year"], r["consumer"],
                est["reference_fiscal_year"], est["sector_mapped"]))
        out[(r["reference_fiscal_year"], r["consumer"])] = (float(est["value"]), est["estimate_id"], r["rule"])
    return out


def coal_kt(fiscal_label, consumer):
    """The year's coal to `consumer` in kt, as the DECLARED booking policy chooses it.

    HDIP publishes this allocation more than once per reference year and the prints differ - two
    reallocations, one level revision and one provisional-to-final sit in the held record
    (outputs/pakemis_coal_vintage_ledger.csv). Which print is booked is therefore data, not a rule
    in this function: data/coal_booking_policy.csv names an estimate_id per (year, consumer) with
    its reason, and the estimate is resolved in data/activity/industry/coal_by_sector_vintages.csv.
    July-March prints cannot be booked (the resolver refuses them). rc53 reproduces rc52's values
    exactly; changing a booked_estimate_id is a re-base."""
    booked = _booked().get((fiscal_label, consumer))
    if booked is None:
        raise KeyError("coal_booking_policy.csv books no %s for %s" % (consumer, fiscal_label))
    return booked[0]


def booking(fiscal_label, consumer):
    """(kt, estimate_id, rule) - the booked value with the print it came from."""
    return _booked()[(fiscal_label, consumer)]


def _fiscal_label(end_year):
    return "%d-%02d" % (end_year - 1, end_year % 100)


def compute(data, year=None):
    """Component rows for the two solid-fuel streams, priced on the year's own coal.

    `year` is the sector's fiscal-END convention (2024 = FY2023-24), like the gas and
    liquid streams beside it.
    """
    from pkinv.core.uncertainty import product
    end_year = year if year is not None else data.year
    label = _fiscal_label(end_year)
    ncv = data.efv("industry_ncv", ITEM)
    ncv_u = data.efu("industry_ncv", ITEM)
    # The activity uncertainty is the series' own character: an official ESTIMATE whose
    # brick column is a residual-style allocation. The parameter row declares the basis.
    ad_u = data.p("industry_coal_activity_uncert")
    out = []
    for consumer, label_text in STREAMS:
        kt = coal_kt(label, consumer)
        if not kt:
            continue
        tj = kt * ncv  # kt * TJ/Gg == Gg * TJ/Gg
        for gas, cat in (("CO2", "industry_combustion_co2"),
                         ("CH4", "industry_combustion_ch4"),
                         ("N2O", "industry_combustion_n2o")):
            row = {"category": "Industrial fuel combustion (1A2)",
                   "subitem": "%s %s" % (label_text, gas), "gas": gas,
                   "emissions_Gg": tj * data.efv(cat, ITEM) / 1e6,
                   "uncert_pct": product(ad_u, ncv_u, data.efu(cat, ITEM)),
                   "activity_year": end_year,
                   "activity_period_kind": "span",
                   # E2: a published official statistic, marked estimated by its own
                   # footer. Cement coal's months ride the QIM production proxy (T3,
                   # output not fuel); brick's are declared flat (T4, the unmodelled
                   # kiln season). The declared letter is the one the layer USES - the
                   # mismatch guard caught this line declaring T4 for both.
                   # Spatial S2 since rc47 Wave 4 - "the next commit's work" the rc46
                   # comment promised: brick rides the 11,272 surveyed kiln points
                   # (object-uniform, the density that produced the WAPE-benchmarked
                   # allocation), cement the geocoded clinker register at its
                   # company-census weights (object-partial). Both are facility sets
                   # without per-object fuel, which is exactly S2.
                   "evidence_class": "E2",
                   "temporal_method": "T3" if consumer == "cement" else "T4",
                   "spatial_method": "S2",
                   "source_id": "finance_division_supplement_coal"}
            if gas == "CH4":
                row["fossil"] = True
            out.append(row)
    return out, []
