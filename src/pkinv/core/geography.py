"""Pakistan's inventory geography — provinces and the shapefile name maps.

Geography, not agriculture: every sector allocates to the same five provinces, so this
is the one definition. It previously existed twice, verbatim, in inventory/downscale.py
and gis/grid.py, with different modules importing different copies.

ORDER IS LOAD-BEARING. PROV_ID indexes the int8 province raster and fixes the row order
of every provincial CSV, so reordering this list silently rewrites published outputs.
"Other" = Gilgit-Baltistan + Azad Kashmir + Islamabad Capital Territory.
"""

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
PROVINCES = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Other"]
PROV_ID = {p: i for i, p in enumerate(PROVINCES)}  # 0..4; outside the country = -1

# geoBoundaries ADM1 shapeName -> inventory province
ADM1_TO_PROVINCE = {
    "Punjab": "Punjab", "Sindh": "Sindh", "Khyber Pakhtunkhwa": "Khyber Pakhtunkhwa",
    "Balochistan": "Balochistan", "Gilgit-Baltistan": "Other", "Azad Kashmir": "Other",
    "Islamabad Capital Territory": "Other",
}

# The CURATED station record's own province vocabulary -> inventory province
# (data/activity/power/plant_locations.csv). It is a third vocabulary, not a typo: the record
# spells the territory "Azad Jammu & Kashmir" where geoBoundaries spells it "Azad Kashmir",
# and ADM1_TO_PROVINCE above covers only the latter. Kept as its own map rather than widened
# into that one, because a boundary distributor's vocabulary and a hand-curated record's are
# different things and conflating them is how a distributor change would silently re-point a
# curated row.
#
# curated_province() RAISES on a string neither map knows. That matters more than it looks: a
# caller that fell back to the raster on an unrecognised value would turn a typo in the
# curated record into a silent restoration of the raster placement this map exists to replace,
# and the only symptom would be a station quietly back in the wrong province.
CURATED_TO_PROVINCE = {
    "Azad Jammu & Kashmir": "Other",
}


def curated_province(name):
    """The inventory province for a curated station record's province string."""
    if name in PROV_ID:
        return name
    for table in (CURATED_TO_PROVINCE, ADM1_TO_PROVINCE):
        if name in table:
            return table[name]
    raise KeyError(
        "curated province %r is in no province vocabulary. Add it to "
        "CURATED_TO_PROVINCE with the territory it belongs to rather than letting the "
        "caller fall back to the raster, which would silently undo the curated placement"
        % (name,))


# FAO GAUL L2 ADM1_NAME -> inventory province (FATA/NWFP -> KP; Islamabad -> Other)
GAUL_ADM1_TO_PROVINCE = {
    "Punjab": "Punjab", "Sindh": "Sindh", "Balochistan": "Balochistan",
    "North-West Frontier": "Khyber Pakhtunkhwa",
    "Federally Administered Tribal Areas": "Khyber Pakhtunkhwa",
    "Islamabad": "Other",
}

# --- the residual unit's membership -------------------------------------------------
# "Other" is a reporting group, not a place, and it does not mean the same geography in
# every sector: the census frame's Other is Islamabad District alone, OCAC's is AJK + GB
# (Islamabad is folded into Punjab on its area pages), the airport panel's is all three.
# Placing an OCAC "Other" share inside Islamabad - which is what a mask over the whole
# residual unit does - books mass to a territory the source explicitly excludes. Each row
# of data/province_shares.csv therefore declares its own membership, and the allocation
# reads it rather than the prose beside it.
OTHER_TERRITORIES = ("Islamabad Capital Territory", "Azad Kashmir", "Gilgit-Baltistan")
MEMBERSHIPS = {
    "ict_only": ("Islamabad Capital Territory",),
    "ajk_gb": ("Azad Kashmir", "Gilgit-Baltistan"),
    "ict_ajk_gb": OTHER_TERRITORIES,
    "unresolved_group": OTHER_TERRITORIES,   # membership not established: the whole unit, declared
    "none": (),                              # the row places no mass in Other
}

_MEMBERSHIP_BY_PROXY = None


def other_membership(proxy):
    """The ADM1 units a proxy's `Other` share may be placed in, from its own declared row.

    Returns the membership key; `members_of()` turns it into the territory names. An
    unknown proxy is `unresolved_group` - today's behaviour, and visible as unresolved.
    """
    global _MEMBERSHIP_BY_PROXY
    if _MEMBERSHIP_BY_PROXY is None:
        import csv
        import os
        from pkinv.paths import ROOT
        path = asset_path(ROOT, "data", "province_shares.csv")
        _MEMBERSHIP_BY_PROXY = {
            r["proxy"]: (r.get("other_membership") or "unresolved_group")
            for r in _activity_rows(path, comments=False)}
    key = _MEMBERSHIP_BY_PROXY.get(proxy, "unresolved_group")
    if key not in MEMBERSHIPS:
        raise ValueError("province_shares.csv: unknown other_membership %r for proxy %r"
                         % (key, proxy))
    return key


def members_of(membership):
    """The territory names a membership key admits."""
    return MEMBERSHIPS[membership]
