"""CO2 from carbon-containing soil amendments - urea application + liming.

IPCC 2006 V4 Ch11:
  Urea  (Eq 11.13): CO2-C = M_urea * EF_urea (0.20 t C/t);  CO2 = C * 44/12
  Liming (Eq 11.12): CO2-C = M_limestone*0.12 + M_dolomite*0.13; CO2 = C * 44/12

UREA MASS HAS TWO BASES, and rc39 A3 made the difference explicit instead of uniform.

  direct_product_offtake               the REFERENCE year. NFDC Annex-5 prints the national urea
                                       offtake for Jul-2023..Jun-2024: 6,578,838 t. Eq. 11.13 is
                                       applied to that mass directly.
  reconstructed_from_total_N_and_share every HISTORICAL year, which carries only a FAOSTAT
                                       total-N figure: M_urea = N_total * urea_N_share /
                                       urea_N_content.

This docstring used to say the reconstruction "reproduces the actual NFDC 2024 urea offtake".
It nearly does - 6,565,217 t against 6,578,838, low by 13,621 t or 0.207%, worth 0.009989 Mt
CO2 - and "nearly" was doing unmarked work: a derived quantity stood in for a measurement that
is held, printed and product-resolved. The reconstruction remains the only possible basis for
the backcast, so it stays, named.

LIMING (3.G) IS NOT ESTIMATED and this module emits no row for it. Pakistan's cropland is
alkaline/calcareous so agricultural liming is believed minimal, but "believed minimal" is not a
measurement: a national lime-use statistic has not been acquired for this inventory, so the
honest status is NE, not a zero.
Eq 11.12 and its factors stay documented here for when that activity data exists.
"""
from pkinv.core.uncertainty import product

# rc39 A4: 3.H only. Liming is 3.G and is NOT ESTIMATED - see the module docstring and
# the 3.G row in report/completeness.py. The category is named for what it contains.
CATEGORY = "Urea application"
C_TO_CO2 = 44.0 / 12.0


def urea_mass_t(data):
    """(t urea, basis) for whichever year this InventoryData describes.

    A backcast year is stamped with faostat_basis_year by timeseries._apply_year; the anchor is
    a fresh InventoryData and carries no stamp. The basis is READ, never inferred: the two
    masses differ by 0.207%, so a wrong choice would not be visible in the output."""
    if getattr(data, "urea_offtake_product_t", None) is not None:
        return data.urea_offtake_product_t, "direct_product_offtake"
    if getattr(data, "faostat_basis_year", None) is not None:
        n_total = data.fertilizer["nitrogen_N_offtake"]["value_t"]
        return (n_total * data.p("urea_N_share") / data.p("urea_N_content"),
                "reconstructed_from_total_N_and_share")
    from pkinv.sectors.agriculture import fertiliser_mix
    _, tonnes = fertiliser_mix.national_product_nitrogen(data)
    if "Urea" not in tonnes:
        raise KeyError("the Annex-5 window carries no urea row")
    return tonnes["Urea"], "direct_product_offtake"


def compute(data):
    # ---- Urea application CO2 (Eq 11.13) ----
    n_u = data.fertilizer["nitrogen_N_offtake"]["uncert_pct"]
    m_urea, urea_basis = urea_mass_t(data)
    urea_co2_t = m_urea * data.efv("liming_urea", "EF_urea") * C_TO_CO2
    urea_gg = urea_co2_t / 1000.0

    # ---- Liming CO2 (Eq 11.12): NOT ESTIMATED, and therefore NOT EMITTED AS A ROW ----
    # This used to compute lime_c from liming_limestone_t and liming_dolomite_t, both of which
    # are 0 with the note "~0 pending data", and publish the resulting 0.000000 Gg as an
    # estimate. completeness.py declared the same category NE at the same time. A published
    # zero is the stronger claim - it says a measurement was made and came to nothing - so the
    # row is gone and the NE declaration stands alone. EF_limestone and EF_dolomite remain in
    # the factor store: when national lime-use activity data exists, only the activity is
    # missing. tests/test_ne_categories.py fails if an NE category regains a numeric row.

    return [
        {"category": CATEGORY, "subitem": "Urea application CO2", "gas": "CO2",
         "emissions_Gg": urea_gg,
         # The basis is NOT carried on the row. core.components v3 is a closed schema, and its
         # own comment records why: provenance keys that only some sectors set describe "the
         # rows that bothered". An agriculture-only flag here would be that mistake again. The
         # basis is published for every year in outputs/agriculture_urea_basis.csv instead,
         # where the historical rows can state their own basis rather than being inferred from
         # a field the reference year happens to fill in.
         "uncert_pct": product(n_u, data.efu("liming_urea", "EF_urea"))},
    ]
