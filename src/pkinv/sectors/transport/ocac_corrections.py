"""Declared corrections to OCAC first prints, read by the ingest and by the diagnostics.

OCAC's FY2017-18 edition prints an HSD grand total of 9,038,298 t while its customer classes
sum to 8,516,476 t; the FY2018-19 edition restores exactly the 521,822 t difference to Road
and leaves the grand total unchanged. scripts/ingest_ocac_sectoral.py applies the correction
under a fail-closed rule and refuses to write if what it finds differs from what is declared
here; ocac_diagnostics.py reports the first print as the non-additive page it was. One
declaration, so the two cannot disagree about the amount.

Keyed (fiscal_year_start, section, sector_row, product). Each value is the first print's own
number; the corrected value is first_print_tonnes + gap_tonnes.
"""
DECLARED_PUBLISHER_CORRECTIONS = {
    (2017, "TRANSPORT", "Road", "HSD"): {
        "first_print_tonnes": 7466423.0, "gap_tonnes": 521822.0,
        "first_print": "OCAC_FY2017_18.pdf (HSD total 9,038,298 t; classes sum 8,516,476 t)",
        "restated_in": "OCAC_FY2018_19.pdf (FY2017-18 Road 15,454,576 t; grand total unchanged)"},
}
