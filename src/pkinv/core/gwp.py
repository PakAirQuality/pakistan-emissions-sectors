"""Global Warming Potential (GWP-100) conversion to CO2-equivalent.

AR5 is primary because UNFCCC Enhanced Transparency Framework / Common Reporting
Tables require AR5 GWP-100 values. AR6 is reported as a secondary column.
"""

# GWP-100 factors (mass basis, t CO2e per t gas).
# CH4 is split by origin: oxidising fossil CH4 adds a CO2 molecule that was not already
# in the fast carbon cycle, so it carries a higher factor than biogenic CH4. Agriculture
# is entirely biogenic (enteric, manure, rice, residue burning); the fossil entries exist
# for the energy and transport sectors.
GWP = {
    "AR5": {"CO2": 1.0, "CH4": 28.0, "CH4_fossil": 30.0, "N2O": 265.0,
            # AR5 Table 8.A.1; the ETF/CRT reporting basis.
            "HFC-23": 12400.0, "HFC-32": 677.0, "HFC-41": 116.0,
            "HFC-125": 3170.0, "HFC-134": 1120.0, "HFC-134a": 1300.0,
            "HFC-143": 328.0, "HFC-143a": 4800.0, "HFC-152a": 138.0,
            "HFC-227ea": 3350.0, "HFC-236fa": 8060.0, "HFC-245ca": 716.0,
            "HFC-245fa": 858.0, "HFC-365mfc": 804.0,
            "CF4": 6630.0, "C2F6": 11100.0, "C3F8": 8900.0,
            "C4F10": 9200.0, "c-C4F8": 9540.0, "C5F12": 8550.0,
            "C6F14": 7910.0, "SF6": 23500.0, "NF3": 16100.0},
    "AR6": {"CO2": 1.0, "CH4": 27.0, "CH4_fossil": 29.8, "N2O": 273.0,
            # AR6 WGI Chapter 7 Supplementary Material, Table 7.SM.7.
            "HFC-23": 14600.0, "HFC-32": 771.0, "HFC-41": 135.0,
            "HFC-125": 3740.0, "HFC-134": 1260.0, "HFC-134a": 1530.0,
            "HFC-143": 364.0, "HFC-143a": 5810.0, "HFC-152a": 164.0,
            "HFC-227ea": 3600.0, "HFC-236fa": 8690.0, "HFC-245ca": 787.0,
            "HFC-245fa": 962.0, "HFC-365mfc": 914.0,
            "CF4": 7380.0, "C2F6": 12400.0, "C3F8": 9290.0,
            "C4F10": 10000.0, "c-C4F8": 10200.0, "C5F12": 9220.0,
            "C6F14": 8620.0, "SF6": 25200.0, "NF3": 17400.0},
}


def to_co2e(gas, mass, ar="AR5", fossil=False):
    """Convert a mass of gas to CO2e in the same mass unit.

    `fossil` selects the fossil-origin CH4 factor and is ignored for every other gas, so
    a caller that does not know about it gets the biogenic answer -- which is the right
    default for agriculture and the reason no agriculture number moves.
    """
    key = "CH4_fossil" if (gas == "CH4" and fossil) else gas
    return mass * GWP[ar][key]
