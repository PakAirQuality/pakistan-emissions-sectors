"""Air-pollutant co-emissions from open waste burning.

Reported in mass (kt), never converted to CO2e and never part of the greenhouse-gas
control-total reconciliation. The row schema deliberately matches the agriculture air
layer (category, subitem, ghg_subitem, pollutant, emissions_kt, uncert_pct) so the two
can be concatenated; `ghg_subitem` is the join key that lets a pollutant row inherit its
greenhouse-gas stream's province proxy instead of carrying its own.

Emission factors are Andreae (2019) "garbage burning", which is also the family the
crop-residue module uses, so the two open-burning streams in this inventory rest on the
same measurement convention. That matters: municipal waste burning and crop-residue
burning are separate IPCC categories (4C2 and 3F) but are compared constantly.

Not EMEP/EEA 5.C.2. Despite being titled "open burning of waste", that chapter covers
small-scale agricultural waste - its activity basis is hectares of orchard and farmland
and its factors are measured from Douglas fir slash and almond prunings in California.
Its own overview says non-agricultural burning "is not discussed in this chapter".

Usage:  python3 -m pkinv.sectors.waste.air_pollutants
"""
from pkinv.core.uncertainty import product
from pkinv.sectors.waste import open_burning
from pkinv.sectors.waste.data import WasteData

EF = "waste_burning"
CATEGORY = open_burning.CATEGORY

# Andreae 2019 garbage burning. HCl has no crop-residue analogue and is the signature of
# burning chlorinated plastics; it is reported for completeness and enters no total.
POLLUTANTS = [("PM2.5", "Gef_PM25"), ("CO", "Gef_CO"), ("NOx", "Gef_NOx"),
              ("NMVOC", "Gef_NMVOC"), ("BC", "Gef_BC"), ("SO2", "Gef_SO2"),
              ("NH3", "Gef_NH3"), ("HCl", "Gef_HCl")]


def compute(data, year=None):
    """Rows of kt per pollutant. Factors are per kg DRY matter, so the wet burned mass
    is converted with the same dry-matter fraction the N2O term uses."""
    mb_dry = open_burning.waste_burnt(data, year) * data.p("dry_matter")
    ad_u = product(open_burning.activity_uncert(data), data.pu("dry_matter"))
    rows = []
    for poll, key in POLLUTANTS:
        rows.append({
            "category": CATEGORY,
            "subitem": "Open waste burning " + poll,
            # All streams share one burned mass, so they share one greenhouse-gas anchor.
            "ghg_subitem": "Open waste burning CH4",
            "pollutant": poll,
            "emissions_kt": mb_dry * data.efv(EF, key) / 1e6,
            "uncert_pct": product(ad_u, data.efu(EF, key)),
        })
    return rows


def main():
    data = WasteData()
    rows = compute(data)
    print("Open waste burning air pollutants (%d, %.2f Mt wet waste burned):"
          % (data.year, open_burning.waste_burnt(data) / 1e6))
    for r in rows:
        print("  %-8s %8.1f kt  +/-%3.0f%%" % (r["pollutant"], r["emissions_kt"], r["uncert_pct"]))


if __name__ == "__main__":
    main()
