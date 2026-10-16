"""Compatible primary geography; ODbL alternatives remain in the preserved release.

Removing an ODbL file from an archive does not remove its effect on a database.
Primary allocation must avoid its geometry and derived weights at calculation time.
"""

PRIMARY_COMPATIBLE = True
RAIL_GEOMETRIES = frozenset({"network:pak_rail", "points:pak_rail_yards"})


def compatible_facilities(rows):
    """Select independently sourced rows; never relabel ODbL coordinates as CC BY."""
    return [dict(row) for row in rows if "odbl" not in row.get("licence", "").lower()
            and not row.get("coordinate_source", "").lower().startswith(("osm", "openstreetmap"))]


def primary_stream(stream):
    result = dict(stream)
    if result.get("geometry_id") in RAIL_GEOMETRIES:
        result["geometry_id"] = "S4:no-native-geometry"
        result["spatial_profile_id"] = "railways_freight_div"
        result["spatial_view"] = "accounting"
    return result
