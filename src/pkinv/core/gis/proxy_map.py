"""Province-share proxy -> gridding raster.

The provincial layer allocates on a proxy vocabulary (livestock_cattle, fertilizer_N,
rice_area, ...) while the grid layer holds rasters under different names (glw_livestock,
cropland, spam_rice, ...). This is the translation between them, plus the fallback rules.

It lives in core because BOTH the greenhouse-gas and the air-pollutant grid layers need
it and must not drift apart. It previously lived in gis/air_spatial.py, which meant
run_gis.py imported it from the air layer -- so the GHG gridding was downstream of the
air layer's vocabulary, and moving the air modules would silently have dropped
manure_applied from the raster set, sending applied manure to the cropland fallback.
That redistributes emissions between provinces at an unchanged national total, so it
would not have shown up in national_totals_2024.csv at all.

The mapping itself is agriculture's today. When a second sector grids, it should pass
its own mapping rather than extend this one in place.
"""

GIS_PROXY_FOR = {
    "livestock_total": "glw_livestock", "livestock_cattle": "glw_livestock",
    "livestock_buffalo": "glw_livestock", "livestock_sheep": "glw_livestock",
    "livestock_goats": "glw_livestock", "livestock_smallrum": "glw_livestock",
    "fertilizer_N": "cropland", "crop_total": "cropland", "rice_area": "spam_rice",
    "manure_applied": "manure_applied",
}


def gis_proxy(row_proxy, category, proxies):
    """Translate a province-share proxy to a raster, honouring the manual-drop overrides."""
    if category == "Field burning of residues" and "firms_fire" in proxies:
        return "firms_fire"
    name = GIS_PROXY_FOR.get(row_proxy, "cropland")
    return name if name in proxies else "cropland"
