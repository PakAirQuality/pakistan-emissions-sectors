"""Province allocation for residential fuel combustion - survey geographies where the
survey is credible, metered geography where a meter exists.

FIVE GEOGRAPHIES, NOT ONE, because these fuels are not distributed alike. Piped gas
follows the gas network, which is metered: OGRA publishes domestic connections by
province, and they are nothing like population - Balochistan has 5.5 percent of the
people and 2.8 percent of the connections. Firewood, dung cake, LPG and crop residues
follow the HIES 2024-25 design-weighted strata quantities - the August 2026 upgrade
from the population fallback these fuels rode before the survey was processed, and from
the herd proxy dung rode: a consumption sector should ride consumption geography, and
the survey measures where households actually burn the fuel rather than where the
animals excrete it (cake is traded across district lines; the herd proxy survives in
data/province_shares.csv as the structural alternative). Kerosene, charcoal, coal and
generators stay on the population fallback: their HIES items ride 42-116 observations
and a survey geography built on that would be noise wearing a stratification.

HIES's ICT, Gilgit-Baltistan and Azad Jammu & Kashmir strata fold into this
inventory's 'Other' province, matching the national grid's residual convention.

Collapsing all these onto one proxy would leave the national total unchanged and be
invisible in every output except the provincial file, so tests/test_residential.py
checks that the gas, dung and firewood geographies actually differ.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA
from pkinv.sectors.residential import hies
from pkinv.sectors.residential.combustion import CATEGORY

PROXY = "residential_pop"
GAS_PROXY = "residential_gas_conn"
HERD_PROXY = "residential_dungcake"    # the structural alternative, no longer reported

# stream first-word -> HIES fuel whose strata quantities set the geography
HIES_GEOGRAPHY = {"Firewood": "firewood", "Dung": "dung_cake", "LPG": "lpg"}
# Crop residues ride the two expenditure items' combined rupee geography.
RESIDUE_FUELS = ("agricultural_waste", "cotton_sticks")

_OTHER = {"Islamabad Capital Territory", "Gilgit-Baltistan", "Azad Jammu & Kashmir"}


def _fold(province):
    return "Other" if province in _OTHER else province


def hies_province_shares(fuel):
    """{province: share} from the survey's strata totals, ICT/GB/AJK folded to Other."""
    out = {p: 0.0 for p in PROVINCES}
    for (prov, _region), share in hies.strata_shares(fuel).items():
        out[_fold(prov)] += share
    return out


def residue_province_shares():
    """Rupee-weighted combination of the two residue expenditure items."""
    out = {p: 0.0 for p in PROVINCES}
    total = 0.0
    for fuel in RESIDUE_FUELS:
        v = hies.value_annual_rs(fuel)
        total += v
        for prov, share in hies_province_shares(fuel).items():
            out[prov] += v * share
    return {p: v / total for p, v in out.items()}


PROXY_MAP = {}
for _gas in ("CO2", "CH4", "N2O"):
    PROXY_MAP[(CATEGORY, "Natural gas %s" % _gas)] = GAS_PROXY
for _word, _fuel in HIES_GEOGRAPHY.items():
    _label = {"Firewood": "Firewood", "Dung": "Dung cake", "LPG": "LPG"}[_word]
    for _gas in ("CO2", "CH4", "N2O"):
        PROXY_MAP[(CATEGORY, "%s %s" % (_label, _gas))] = "residential_hies_" + _fuel
for _gas in ("CH4", "N2O"):
    PROXY_MAP[(CATEGORY, "Crop residues %s" % _gas)] = "residential_hies_residue"

PROXY_FALLBACK = {CATEGORY: PROXY}


def load_shares(period=None):   # rc44 A1: accepted, not yet used here
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    for fuel in set(HIES_GEOGRAPHY.values()):
        shares["residential_hies_" + fuel] = hies_province_shares(fuel)
    shares["residential_hies_residue"] = residue_province_shares()
    return shares


def proxy_for(c):
    # Indexed with [], not .get(): an unknown category must raise rather than silently
    # allocate onto the wrong geography at an unchanged national total.
    return PROXY_MAP.get((c["category"], c["subitem"]), PROXY_FALLBACK[c["category"]])


def strata_rows(data, comps):
    """The published strata table: fuel x province x urban/rural, HIES share and the
    allocated Mt CO2e where the stream rides a HIES geography.

    For non-HIES geographies (gas, population-fallback minors) the strata table still
    publishes the survey's distribution as a diagnostic, with the allocated column
    blank - the share describes the survey, not the engine's allocation.
    """
    by_stream = {}
    for c in comps:
        word = c["subitem"].split()[0]
        by_stream.setdefault(word, 0.0)
        by_stream[word] += c["co2e_Mt_AR5"]
    label_of = {"firewood": "Firewood", "dung_cake": "Dung", "lpg": "LPG",
                "natural_gas": "Natural", "kerosene": "Kerosene",
                "charcoal": "Charcoal", "coal": "Coal",
                "agricultural_waste": None, "cotton_sticks": None,
                "generator_fuel": "Generators", "electricity": None}
    rows = []
    for fuel in ("firewood", "dung_cake", "lpg", "natural_gas", "kerosene",
                 "agricultural_waste", "cotton_sticks", "charcoal", "coal",
                 "generator_fuel"):
        allocated = fuel in HIES_GEOGRAPHY.values()
        word = label_of[fuel]
        stream_mt = by_stream.get(word, 0.0) if word else 0.0
        for (prov, region), share in sorted(hies.strata_shares(fuel).items()):
            rows.append({
                "fuel": fuel, "province": prov, "region": region,
                "hies_share": round(share, 5),
                "allocated_Mt_co2e": (round(stream_mt * share, 5)
                                      if allocated else ""),
                "basis": ("engine geography (HIES strata)" if allocated else
                          "diagnostic only - engine rides %s" %
                          ("metered gas connections" if fuel == "natural_gas"
                           else "population fallback (thin survey n)"
                           if word else "the residue rupee geography")),
            })
    return rows
