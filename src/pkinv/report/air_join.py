"""The air-to-GHG join: which source stream anchors each sector's pollutant row.

The air layers are computed from the same activity the greenhouse-gas streams burn, count
and collect; the spatial lane inherits each pollutant row's stream's own allocation, so the
join must be exact and fail-closed. Residential, transport, waste and aviation carry a
`ghg_subitem` column (a real `sub_category` of the module's streams - Wave A of the air
spatial lane repaired transport's constant anchor and re-emitted waste's and aviation's
dropped columns). Power keys on (category, fuel) and railways on (fuel, traction-or-not), declared here.

An unknown key RAISES - the agriculture `proxy_for` discipline: a pollutant row that
cannot name its stream does not get a geography.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

ROOT = asset_path(os.path.dirname(__file__), "..", "..", "..")
STREAMS = asset_path(ROOT, "outputs", "pakemis_source_streams.csv")

# power: (category, fuel) -> a representative stream's sub_category (all gas variants of a
# fuel share one spatial profile, so the representative's vector is the family's). The two
# coal fuel_detail strata are one family. Railways: traction only (the air layer's scope).
POWER_ANCHOR = {
    ("Electricity and heat production", "Coal"): "Coal CO2",
    ("Electricity and heat production", "Gas"): "Gas CO2",
    ("Electricity and heat production", "Furnace Oil"): "Furnace Oil CO2",
    ("Electricity and heat production", "Diesel Oil"): "Diesel Oil CO2",
    ("Electricity and heat production", "Bagasse"): "Bagasse CH4",
    ("Captive gas self-generation (1A2)", "Natural Gas"): "Captive natural gas CO2",
}
# (fuel, traction?) -> sub_category: the traction rows ride the rail network, the
# non-traction rows the yard points - present in every period, unlike traction furnace
# oil, which the detail table reports NIL through FY2020-21 (air spatial Wave A)
RAILWAYS_ANCHOR = {
    ("Diesel", True): "Diesel CO2",
    ("Furnace oil", True): "Furnace oil CO2",
    ("Diesel", False): "Non-traction diesel CO2",
    ("Furnace oil", False): "Non-traction furnace oil CO2",
}


def stream_index():
    """{module: {sub_category: source_stream_id}} over the shipped stream register."""
    out = {}
    for r in _activity_rows(STREAMS, comments=False):
        out.setdefault(r["module"], {})[r["sub_category"]] = r["source_stream_id"]
    return out


def anchor_subitem(sector, row):
    """The `sub_category` of the stream a pollutant row inherits its geography from."""
    if sector in ("residential", "transport", "waste", "aviation", "agriculture"):
        key = row.get("ghg_subitem", "")
        if not key:
            raise KeyError("%s air row %r carries no ghg_subitem" % (sector, row.get("subitem")))
        return key
    if sector == "power":
        # rc60: a source-class row NAMES its anchor, so take the declaration when there is one.
        # POWER_ANCHOR remains for the screening rows, which are built from the power module's
        # own fuel table and carry no register entry - and it must not be consulted first, since
        # its (category, fuel) key would answer for a class whose category it never described.
        declared = row.get("ghg_subitem", "")
        if declared:
            return declared
        return POWER_ANCHOR[(row["category"], row["fuel"])]
    if sector == "railways":
        from pkinv.sectors.railways import traction
        return RAILWAYS_ANCHOR[(row["fuel"],
                                row.get("category", traction.CATEGORY)
                                == traction.CATEGORY)]
    if sector in ("industry", "ippu", "fugitives"):
        # rc58/rc59: the source-class register names each class's anchor stream explicitly
        # (ghg_subitem) and, where the stream lives in another module, the MODULE that
        # computes it (ghg_anchor_module: power for captive generation, industry for soda
        # ash, transport for petrol distribution) - the cases where an air atom's sector is
        # not the anchoring stream's module
        key = row.get("ghg_subitem", "")
        if not key:
            raise KeyError("%s air row %r carries no ghg_subitem" % (sector, row.get("subitem")))
        return key
    raise KeyError("no air join declared for sector %r" % sector)


def anchor_module(sector, row):
    """The module whose stream register the anchor is looked up in - the sector itself except
    where the row declares ghg_anchor_module (industry's captive classes anchor power's
    captive stream; soda ash and petrol distribution name declared proxies)."""
    return row.get("ghg_anchor_module") or sector


def stream_for(sector, row, index=None):
    """The anchoring source_stream_id; raises on any row the join cannot name."""
    index = index or stream_index()
    sub = anchor_subitem(sector, row)
    module = anchor_module(sector, row)
    try:
        return index[module][sub]
    except KeyError:
        raise KeyError("%s air row %r anchors %r, which is no stream of module %s"
                       % (sector, row.get("subitem") or row.get("fuel"), sub, module))
