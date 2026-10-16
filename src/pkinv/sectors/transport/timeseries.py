"""A fuel-based national road-transport series, FY2015-16 to FY2024-25.

THE SERIES THE SECTOR'S OWN PHILOSOPHY DEMANDS. This paper's central claim is that
the national total does not require a reliable fleet model - fuel controls set the
magnitude. It follows that an incomplete historical fleet cannot excuse the absence
of a national series: OCAC's Road customer-class rows cover ten fiscal years,
and the same NCVs and IPCC factors that build the reference year build every other
year. This module does exactly that and nothing more.

DECLARED BASIS - WHOLE-ROAD-CLASS, PER YEAR:
  - petrol = Road MS + HOBC, diesel = Road HSD (OCAC annual editions);
  - NO household-generator back-cast (the HIES survey exists for 2024-25 only);
  - NO off-road partition (the fleet model is reference-year);
  - class composition NOT reconstructed;
  - CNG from the same OGRA series the reference year uses, through FY2024-25;
    that latest row retains the sector-partition control and its documented
    difference from the chapter narrative as separate source evidence.
The reference-year (FY2023-24) row of this series therefore differs from the sector's
reported figure by exactly those refinements - the generator carve-out and the
off-road category split - and a test asserts that identity, so the series and the
inventory cannot quietly diverge.

Writes: outputs/transport_fuel_series.csv, including road_share_of_national_hsd -
the panel that bounds the diesel-boundary scenarios and the ledger's unresolved rows.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.components import enrich_co2e
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.transport import cng
from pkinv.sectors.transport.data import TransportData
from pkinv.core.io import write_table

PROVINCIAL_CSV = asset_path(DATA, "activity", "transport",
                              "ocac_sectoral_provincial.csv")


def calendar_year_road_t(cy=2022, path=PROVINCIAL_CSV):
    """Calendar-year national Road sales, tonnes per product, from the monthly panel.

    Construction: sum of the direct monthly PAKISTAN Road rows for January-June of
    the calendar year, plus the December cumulative row (which is July-December
    fiscal-year-to-date by the panel's own convention - the identity is tested
    against the annual editions). Only the PAKISTAN rows exist for the cumulative
    months, so this construction is national-only; provincial detail is
    structurally unavailable for the second half of the calendar year. The two
    halves carry monthly-edition and cumulative-edition vintages respectively
    (~0.2 percent apart on the FY2021-22 panel), declared rather than adjusted.
    """
    jan_jun = ["%d-%02d" % (cy, m) for m in range(1, 7)]
    december = "%d-12" % cy
    out, found = {}, set()
    for r in _activity_rows(path, comments=False):
        if r["area"] != "PAKISTAN" or r["sector_row"] != "Road":
            continue
        # SELECT the kind each half needs rather than raising on the other kind's
        # presence. The panel used to hold one PAKISTAN row per month, and these
        # branches raised if it was the wrong kind - a guard against a silently wrong
        # vintage. Since the direct editions' national pages joined the panel as its
        # area-page controls, a month can carry BOTH kinds, and "the row is the wrong
        # kind" stopped implying "the right kind is missing". The guard moves below:
        # each half must actually have been found.
        if r["month"] in jan_jun and r["report_kind"] == "monthly":
            out[r["product"]] = out.get(r["product"], 0.0) + float(r["tonnes"])
            found.add(r["month"])
        elif r["month"] == december and r["report_kind"] == "cumulative":
            out[r["product"]] = out.get(r["product"], 0.0) + float(r["tonnes"])
            found.add(december)
    missing = (set(jan_jun) | {december}) - found
    if missing:
        raise ValueError("CY%d is missing the required editions for %s - six direct "
                         "monthly months and the cumulative December are the construction"
                         % (cy, sorted(missing)))
    return out

GASES = (("co2", "transport_fuel_co2"), ("ch4", "transport_fuel_ch4"),
         ("n2o", "transport_fuel_n2o"))
BASIS = ("whole-Road-class: no generator carve-out back-cast, no off-road "
         "partition, composition not reconstructed")


def build(data=None):
    """Per OCAC year: fuel kt, TJ, gases in Gg, CO2e Mt (petroleum and incl-CNG)."""
    data = TransportData() if data is None else data
    rows = []
    for year in data.ocac_years():
        petrol_kt = (data.ocac_t("Road", "MS", year)
                     + data.ocac_t("Road", "HOBC", year)) / 1000.0
        diesel_kt = data.ocac_t("Road", "HSD", year) / 1000.0
        comps = []
        for fuel_kt, item in ((petrol_kt, "Motor Gasoline"),
                              (diesel_kt, "Gas/Diesel Oil")):
            tj = fuel_kt * data.efv("transport_ncv", item)
            for gas, cat in GASES:
                comps.append({"category": "series", "subitem": item,
                              "gas": gas.upper(),
                              "fossil": gas == "ch4",
                              "emissions_Gg": tj * data.efv(cat, item) / 1e6,
                              "uncert_pct": 0.0})
        petroleum_mt = sum(c["co2e_Mt_AR5"] for c in enrich_co2e(comps))
        cng_mt = None
        if year in data.cng:
            cng_mt = sum(c["co2e_Mt_AR5"]
                         for c in enrich_co2e(cng.compute(data, year)))
        rows.append({
            "inventory_year": year,
            "fy_label": "FY%d-%s" % (year - 1, str(year)[2:]),
            "petrol_kt": round(petrol_kt, 3),
            "diesel_kt": round(diesel_kt, 3),
            "road_share_of_national_hsd": round(
                data.ocac_t("Road", "HSD", year)
                / data.ocac_t("TOTAL_INTERNAL", "HSD", year), 4),
            "co2e_Mt_AR5_petroleum": round(petroleum_mt, 4),
            "cng_co2e_Mt_AR5": "" if cng_mt is None else round(cng_mt, 4),
            "co2e_Mt_AR5_incl_cng": "" if cng_mt is None
            else round(petroleum_mt + cng_mt, 4),
            "basis": BASIS if year == min(data.ocac_years())
            else "as first row",
        })
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "transport_fuel_series.csv")
    write_table(path, list(rows[0].keys()), rows)
    print("Transport fuel series, %d OCAC years:" % len(rows))
    for r in rows:
        cng_s = (" + CNG %s = %s" % (r["cng_co2e_Mt_AR5"],
                                     r["co2e_Mt_AR5_incl_cng"])
                 if r["cng_co2e_Mt_AR5"] != "" else "  (no CNG series year)")
        print("  %s  petroleum %7.3f Mt%s  road-share %.3f"
              % (r["fy_label"], r["co2e_Mt_AR5_petroleum"], cng_s,
                 r["road_share_of_national_hsd"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
