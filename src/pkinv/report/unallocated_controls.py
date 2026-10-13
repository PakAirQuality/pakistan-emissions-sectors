"""The FY2015-16 activity controls: held as absence evidence for four releases, now the gate.

THE LEDGER'S FIRST LIFE (rc17-rc19). Transport and industrial combustion were NE in
FY2015-16 while this ledger held their OBSERVED totals - Road 12,440,195 tonnes and Total
Industry 2,023,377 tonnes, from the FY2016-17 OCAC edition's prior-year column - because
the split by PRODUCT existed in no held document and a 16-source search was logged
negative. The design principle was that an absence must not swallow its own evidence: the
ledger named the one missing field (product_split) so the next person knew the year was
one column from estimable, not unknown.

THE LEDGER'S SECOND LIFE (rc20, the fifteenth review). The product split turned out to be
public - the Pakistan Oil Report 2015-2016 on ocac.org.pk, page 50, served as a 602-pixel
image flipbook the earlier search had crawled past. The recovered table is transcribed and
quadruple-identity-gated in sectors/transport/ocac_image_edition.py, and THESE TWO CONTROLS
BECAME ITS TWO-DOCUMENT GATE: the new edition's Road and Total Industry TOTALs must equal
the prior-year column this ledger has carried all along, exactly, or the transcription
refuses to load. Both sector-years are now E; the rows here record the closure and keep
serving as the cross-edition anchor. `missing_field` is empty because nothing is missing.

THE PERIOD TAG IS NOT THE EDITION TAG. The rows this reads carry `fy_label FY2016-17` because
that label names the EDITION they were transcribed from, while the datum belongs to the year
before it. The re-tagging happens once, here, explicitly - the same period-tagging trap that
put 48,011 kt of FY2021-22 cement into a FY2023-24 slot for three releases.

Usage:  python3 -m pkinv.report.unallocated_controls
Writes: outputs/pakemis_unallocated_activity_controls.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import csv
import os

from pkinv.core import period
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_unallocated_activity_controls.csv")
OCAC = asset_path(DATA, "activity", "transport", "ocac_sectoral_annual.csv")

FIELDS = ("control_id", "fiscal_year", "claimant_sector", "source_document",
          "source_table", "source_column", "value", "unit", "source_sha256",
          "allocation_state", "emissions_state", "missing_field", "reason_code",
          "what_would_close_it", "note")

# The reason code the two absences carried while they were absences (rc17-rc19), kept as
# the closed-state code's stem so the history reads continuously in the coverage products.
REASON_CODE = "known_activity_total_missing_product_split"
CLOSED_CODE = "closed_rc20_product_split_recovered"

# The prior-year column of the FY2016-17 edition, per claimant sector. `sector_row` is the
# OCAC row; the fiscal year is the edition's year MINUS ONE, which is the whole point of the
# column and the thing most easily got wrong.
PRIOR_COLUMN = "TOTAL_PRIOR"
PRIOR_EDITION_YEAR = 2017
CLAIMANTS = {
    "Road": ("transport",
             "The Road row covers petrol, HOBC, diesel, kerosene and LDO together, and its "
             "recovered FY2015-16 split (MS 5,687,337 / HOBC 38,449 / HSD 6,713,723 / LDO "
             "686) sums to this control exactly. The FY2015_16_FULL_SCOPE_BRIDGE stays "
             "declared-not-populated forever: the observed split made every modelled "
             "alternative moot."),
    "Total Industry": ("industry",
                       "Industry's FY2015-16 GAS was held all along (OGRA 2015-16, in "
                       "gas_consumption.csv); the recovered liquid split (FO 1,463,955 / "
                       "HSD 461,563 / MS 60,563 / KERO 31,976 / LDO 4,568 / HOBC 752) sums "
                       "to this control exactly, so the sector-year is whole."),
}
SOURCE_TABLE = "Sectoral Sales of Energy Products (annual edition), prior-year total column"
CLOSED_BY = ("CLOSED at rc20: the Pakistan Oil Report 2015-2016 page-50 sectoral table "
             "(data/raw/ocac/oil_report_2015_16/, identity-gated transcription in "
             "sectors/transport/ocac_image_edition.py) supplies the product split; this "
             "control is now the two-document gate the transcription must equal exactly")


def _ocac_rows():
    return read_rows(OCAC, comments=False)


def build():
    """One row per observed-but-unsplit control. Raises if the source row has vanished."""
    rows = []
    by_sector = {r["sector_row"]: r for r in _ocac_rows()
                 if r["product"] == PRIOR_COLUMN
                 and int(r["inventory_year"]) == PRIOR_EDITION_YEAR}
    for sector_row in sorted(CLAIMANTS):
        source = by_sector.get(sector_row)
        if source is None:
            raise SystemExit(
                "the %s prior-year control has vanished from %s. It is the only evidence "
                "this inventory holds for that sector-year and the NE row beside it means "
                "'unsplit', not 'unknown' - if the ingest dropped it, the NE row is now "
                "unsupported." % (sector_row, os.path.relpath(OCAC, DATA)))
        claimant, note = CLAIMANTS[sector_row]
        # The edition names the year AFTER the datum's, which is what a prior-year column is.
        end_year = int(source["inventory_year"]) - 1
        start, end = period.fiscal(end_year - 1)
        rows.append({
            "control_id": "ocac_prior_%s_%s" % (end_year, claimant),
            "fiscal_year": period.label(start, end),
            "claimant_sector": claimant,
            "source_document": source["source_file"],
            "source_table": SOURCE_TABLE,
            "source_column": "%s (%s row, %s section)" % (PRIOR_COLUMN, sector_row,
                                                          source["section"]),
            "value": float(source["tonnes"]),
            "unit": "tonnes",
            "source_sha256": source["source_sha256"],
            "allocation_state": "split_recovered",
            "emissions_state": "E",
            "missing_field": "",
            "reason_code": CLOSED_CODE,
            "what_would_close_it": CLOSED_BY,
            "note": ("Read from the PRIOR-YEAR column of the %s edition, so the datum is "
                     "FY%d-%02d though the source row is labelled with the edition's own "
                     "fiscal year. %s" % (source["fy_label"], end_year - 1, end_year % 100,
                                          note)),
        })
    return rows


def controls_for(claimant_sector, rows=None):
    rows = rows if rows is not None else build()
    return [r for r in rows if r["claimant_sector"] == claimant_sector]


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    print("unallocated activity controls -> %s" % OUT)
    for row in rows:
        print("  %-10s %-12s %12.0f %s  %s (%s)"
              % (row["fiscal_year"], row["claimant_sector"], row["value"], row["unit"],
                 row["emissions_state"], row["missing_field"]))
    print("  every row is a held control whose product split was recovered at rc20; the "
          "rows now gate the recovered edition instead of excusing an absence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
