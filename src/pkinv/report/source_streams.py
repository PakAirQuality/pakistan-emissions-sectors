"""The canonical source-stream ledger: one conserved record per emitting stream.

WHY THIS EXISTS. Everything this inventory publishes today is an aggregate of something -
a module total, an IPCC category, a province, a month. Each is derived correctly, and none of
them is the object a user of the data product actually needs, which is one row that answers:

    what was emitted, by which process and gas, in which year and month, at which physical
    location, under which scenario, from which source document, and with which parametric,
    structural, temporal and spatial limitations?

That question has always been answerable here, but only by joining six files by hand. This
module does the join once and writes it down.

WHY IT IS DERIVED RATHER THAN EMITTED. The obvious alternative is to widen the component row
until it carries all of this. That would be a mistake. The component schema is a CLOSED set of
fifteen keys (core.components.ALL_KEYS, asserted by the sector contract), and its closedness is
what makes the contract checkable at all - a sector cannot smuggle a field past it. Widening it
by ten mostly-join-derivable columns would push provenance bookkeeping into ten sector modules
and buy nothing that a join does not already give.

So the component row stays the atom, and this is the published product. It RECOMPUTES NOTHING:
every quantity is read from an output that already exists, for the same reason
report/release_manifest.py recomputes nothing - a second arithmetic path is a second vintage
waiting to disagree with the first.

WHAT "unresolved" MEANS HERE. A field that cannot be resolved carries an explicit declared
value, never a blank. A ledger whose gaps are empty strings reads as complete; a ledger whose
gaps say "unresolved" can be counted, and counting them is how the gap gets closed.

Usage:  python3 -m pkinv.report.source_streams
Writes: outputs/pakemis_source_streams.csv
"""

from pkinv.assets import asset_path
import csv
import os

import pkinv
from pkinv import release
from pkinv.core import components as components_core
from pkinv.core import evidence, parameters, registry
from pkinv.paths import DATA, OUTPUTS
from pkinv.report import category_ledger, national_rollup
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

UNRESOLVED = "unresolved"
NOT_APPLICABLE = "not-applicable"

FIELDS = (
    "release_version", "source_stream_id", "module", "reporting_sector",
    "ipcc_code", "ipcc_category", "sub_category", "process", "gas", "methane_origin",
    "notation_key",
    "inventory_period_start", "inventory_period_end", "activity_year",
    "activity_period_kind",
    "emissions_native", "native_unit", "emissions_ar5", "emissions_ar6",
    "evidence_class",
    "activity_parameter_ids", "conversion_parameter_ids", "factor_parameter_ids",
    "factor_identity_ids",
    "scenario_id", "module_structural_axes",
    "temporal_class", "temporal_profile_id", "temporal_profile_source",
    "spatial_class", "spatial_class_measured", "geometry_available", "spatial_view",
    "spatial_profile_id", "geometry_id", "release_height_class",
    "source_id", "source_document_ids", "archival_state", "licence_status",
)


def _rows(path, root=OUTPUTS):
    full = path if os.path.isabs(path) else asset_path(root, path)
    return read_rows(full)


def stream_id(module, category, subitem, gas):
    """A stable, readable key for a stream - now core's identity, not this file's.

    The construction moved to core.components.component_id in schema v3 and this is a
    thin alias so the public name and every caller keep working. It moved because an
    identity synthesised by one report is an identity that report owns: the atomic annual
    table, the monthly layer and this ledger must name a stream the same way, and the only
    way to guarantee that is for all three to read one field rather than each rebuild it.

    (category, subitem) is already unique within a sector by contract
    (tests/test_sector_contract.py::test_category_subitem_is_unique) and category names are
    globally unique, so this cannot collide. It is built from the identity rather than from a
    counter so that it survives a reordering of the build, which a positional id would not.
    """
    return components_core.component_id(module, category, subitem, gas)


def _split_parameters(groups):
    """Sort a row's dependency groups into the roles the reviewer's schema asks for.

    The rule is by group name and it is declared rather than inferred, because two of the
    buckets are not what a reader would guess:

      factor:ncv:<fuel>   a calorific value - a CONVERSION, not an emission factor. It turns
                          a mass or a volume into energy and is shared by every gas of a
                          stream, which is exactly why it is separated here.
      factor:<gas>:<fuel> an IPCC emission factor, per gas.
      ef:<name>           an emission factor from a sector's own factor table (rc40 G3).
                          Agriculture names its factors this way - ef:enteric_buffalo,
                          ef:liming_EF_urea - and until rc40 they fell through to the
                          activity bucket, so every agriculture stream published its factor
                          as an activity and its factor field as unresolved.
      everything else     a named quantity from a sector's own input tables.

    That last bucket is called ACTIVITY and is not purely activity: waste's first-order-decay
    constant and its maximum methane capacity are physically factors, and they sit here
    because that is where their evidence lives - the sector's own uncertainty inputs rather
    than the shared IPCC factor table. Saying so is better than a taxonomy that quietly
    misfiles them.
    """
    activity, conversion, factor, identity = [], [], [], []
    for group in groups:
        # rc41: a role the scope register DECLARES outranks the name (a module-local
        # factor such as "power:CH4 and N2O factors" or a physical factor that lives in a
        # sector's own input table, waste's MCF and F, is a factor and is filed as one)
        role = parameters.SCOPE_ROLES.get(group)
        if role == "conversion" or (role is None and group.startswith("factor:ncv:")):
            conversion.append(group)
            identity.append(group)
        elif role == "factor" or (role is None and (group.startswith("factor:")
                                                     or group.startswith("ef:"))):
            factor.append(group)
            identity.append(group)
        else:
            activity.append(group)
    return activity, conversion, factor, identity


def _factor_table_ids(groups, by_group, gas=None, bindings=None):
    """The emission-factor TABLE rows behind a stream, as distinct from their physical identity.

    Two ids exist for one number and the ledger must not blur them. `ef_id` is per consumer -
    `pow_co2_hsd` and `tr_co2_diesel` are two rows of data/emission_factors.csv for the same
    carbon content - while `factor:<gas>:<fuel>` is the physical quantity, which is what the
    cross-sector correlation model shares. A user reconciling against the factor table needs
    the former; a user reasoning about correlated error needs the latter. Both are published.
    """
    out = []
    for group in groups:
        # rc40 G3: a group that IS an ef id names its own table row. ef:liming_EF_urea has no
        # ef:-prefixed member in the registry (its member is agriculture:liming_EF_urea), so
        # without this it resolved to nothing while its sibling ef:enteric_buffalo resolved.
        if group.startswith("ef:"):
            out.append(group[len("ef:"):])
        for parameter in by_group.get(group, ()):
            # rc41: a group with a select rule binds ONE member per gas (aviation's jet-fuel
            # group holds the CO2 conversion beside the CH4 and N2O factors); the identity
            # of a CH4 row is its CH4 member, not all three
            if bindings and gas and parameter in bindings and bindings[parameter][2]:
                import re as _re
                if not _re.search(bindings[parameter][2], gas):
                    continue
            if parameter.startswith("ef:"):
                out.append(parameter[len("ef:"):])
            elif parameters.SCOPE_ROLES.get(group) in ("factor", "conversion") \
                    or group.startswith("factor:"):
                # rc41: a module-local factor (fugitives' 2019 Refinement families, ippu's
                # clinker factor, waste's MCF and Bo, aviation's jet-fuel conversion) has no
                # table row behind it - its registered parameter id IS the identity
                out.append(parameter)
    return sorted(set(out))


def _temporal_index():
    """(module, category, subitem, gas) -> the profile the monthly layer actually applied."""
    registry_rows = _rows(asset_path(DATA, "temporal_profiles.csv"), root=DATA)
    by_key = {(r["sector"], r["temporal_class"], r["basis"]): r for r in registry_rows}
    index = {}
    for row in _rows("national_monthly_2024.csv"):
        key = (row["sector"], row["category"], row["subitem"], row["gas"])
        profile = by_key.get((row["sector"], row["temporal_method"], row["basis"]))
        if profile is None:
            index[key] = (UNRESOLVED, UNRESOLVED)
        else:
            index[key] = (profile["profile_id"], profile["profile_source"])
    return index, registry_rows


def _geometry_index():
    """(module, category, subitem_prefix) -> geometry_id, most specific prefix first.

    The assignment is DECLARED in data/stream_geometry.csv - the release_heights.csv
    pattern one level finer - and every id must exist in data/geometry_sets.csv or be the
    explicit residual. Stage 5 replaced the wall-to-wall "unresolved" this column carried
    with either a registered geometry or S4:no-native-geometry; "unresolved" is no longer a
    legal value here, and the tests enforce the vocabulary.
    """
    sets = {r["geometry_id"] for r in _rows(asset_path(DATA, "geometry_sets.csv"),
                                            root=DATA)}
    rows = _rows(asset_path(DATA, "stream_geometry.csv"), root=DATA)
    for row in rows:
        gid = row["geometry_id"]
        if gid != "S4:no-native-geometry" and gid not in sets:
            raise ValueError("stream_geometry names %r, which data/geometry_sets.csv does "
                             "not register" % gid)
    return rows


def _geometry_for(rows, module, category, subitem):
    from pkinv.core.declared import match_prefix
    return match_prefix(rows, module, category, subitem, "geometry_id", "geometry")


def _view_for(rows, module, category, subitem):
    """What the placement CLAIMS TO BE - physical, origin or accounting.

    The third spatial axis and the only one of the three that cannot be derived: it is a
    property of what an activity statistic means, and no register in this repository holds
    that. Declared on data/stream_geometry.csv beside the geometry, through the same prefix
    resolution, with the burden of proof on the row - a view that is not physical must name
    the release geography the allocation does not have.
    """
    from pkinv.core.declared import match_prefix
    return match_prefix(rows, module, category, subitem, "spatial_view", "spatial view")


def _measured_class():
    """geometry_id -> the spatial class the ALLOCATION earns, derived rather than declared.

    Two registers and no judgement: what the cube distributes mass by inside each geometry
    (`within_province_placement` on data/geometry_sets.csv, one row per set and proved
    against the cube's own dispatch by test) and how much of each set that can emit is
    located (the facility registry). pkinv.report.spatial_decomposition owns both, and this
    is a lookup rather than a second copy of the rule - a second arithmetic path is a second
    vintage waiting to disagree.

    The declared class is still written to its own column and the two are compared by test.
    A declared value that nothing can contradict is how this project has now lost five
    numbers, and the point of a derived one is that new evidence moves it without anyone
    remembering to.
    """
    from pkinv.report import spatial_decomposition as spatial
    measured = spatial.geocoding()
    # A stream with no native geometry is not administratively placed: the cube retains it
    # whole at ADM1 (grid_cube, `geometry_id == NO_NATIVE_GEOMETRY` -> the unallocated
    # ledger), so there is no sub-provincial placement to grade, and S3 - "an administrative
    # statistic does the placing" - asserted one that does not exist. rc41: this used to
    # read the cube's unallocated ledger to decide between NA and S3 - a product of a LATER
    # phase that itself reads this ledger - so every build compared against the previous
    # release's file, and an empty outputs/ graded the twenty-four industry streams S3. The
    # rule is the cube's and is stated here; spatial_decomposition derives the set from the
    # geometry column and the test holds the cube's ledger to it.
    out = {spatial.NO_GEOMETRY: spatial.NOT_PLACED}
    for row in _rows(asset_path(DATA, "geometry_sets.csv"), root=DATA):
        _members, _located, emitting, emitting_located = measured.get(
            row["geometry_id"], (0, None, 0, None))
        fraction = ((emitting_located / emitting)
                    if (emitting_located is not None and emitting) else None)
        out[row["geometry_id"]] = spatial.spatial_class(
            row["within_province_placement"], fraction)
    return out


def _placements():
    return {r["geometry_id"]: r["within_province_placement"]
            for r in _rows(asset_path(DATA, "geometry_sets.csv"), root=DATA)}


def _refined_measured(letter, geometry, proxy, placements):
    """rc42 (the twentieth review's S-1b): a per-object-activity geometry is graded PER
    STREAM by the share of the stream's own fuel that sits on a located station, not by
    the geometry's member count. The grid fleet is one geometry carrying five fuel
    streams: the coal stations are all located (the S1 case), half the gas fleet is
    not (S2), and one letter for the geometry mis-states one of them whichever way it
    reads. The share is grid_cube.located_activity_share - ledger and coordinate tables
    only - because this phase runs before the cube and must not read its ledger."""
    if placements.get(geometry) != "per_object_activity":
        return letter
    from pkinv.report import grid_cube
    from pkinv.report import spatial_decomposition as spatial
    # The stream ledger is the reference year's, so this grade is too - named, because the
    # function takes a period and a bare call is indistinguishable from an oversight.
    share = grid_cube.located_activity_share(proxy, grid_cube.period_keys())
    if share is None:
        return letter
    return spatial.spatial_class("per_object_activity", None, located_mass=share)


def _release_heights():
    """(module, category[, subitem_prefix]) -> class; longest matching prefix wins.

    The prefix column arrived with the rc47 Wave 3 aviation split: LTO and cruise are
    one category with two release heights, which the (module, category) grain could
    not say. An empty prefix is the category default, exactly as in stream_geometry."""
    rows = _rows(asset_path(DATA, "release_heights.csv"), root=DATA)

    def lookup(module, category, subitem):
        best, best_len = "unknown", -1
        for r in rows:
            if r["module"] != module or r["category"] != category:
                continue
            prefix = r.get("subitem_prefix", "") or ""
            if subitem.startswith(prefix) and len(prefix) > best_len:
                best, best_len = r["release_height_class"], len(prefix)
        return best
    return lookup


def _provenance():
    """source_id -> (document paths, archival states, licence statuses).

    A source_id may read several activity files and each file has its own archival state, so
    the ledger publishes the SET rather than a single value. Where a stream's documents
    disagree - one archived, one not - the weaker state is what the stream can honestly claim.
    """
    documents = {r["data_file"]: r for r in _rows(asset_path(DATA, "source_documents.csv"),
                                                  root=DATA)}
    keys = {}
    for row in _rows(asset_path(DATA, "source_keys.csv"), root=DATA):
        keys.setdefault(row["source_id"], []).append(row["data_file"])
    WEAKEST = ("not-archived", "derived", "archived")
    out = {}
    for source_id, files in keys.items():
        states = {documents[f]["archival_state"] for f in files if f in documents}
        licences = {documents[f].get("licence_status", UNRESOLVED)
                    for f in files if f in documents}
        state = next((s for s in WEAKEST if s in states), UNRESOLVED)
        licence = "undetermined" if "undetermined" in licences else \
            (sorted(licences)[0] if licences else UNRESOLVED)
        out[source_id] = (sorted(files), state, licence)
    return out


def build():
    comps, _categories, _sector_of = registry.build_all()
    component_code = category_ledger.component_code
    scopes = parameters.scope_map()
    bindings = parameters.load_member_bindings()
    by_group = {}
    for parameter in parameters.registry():
        group = (parameter.get("dependency_group") or "").strip()
        if group:
            by_group.setdefault(group, []).append(parameter["parameter_id"])
    temporal, profile_registry = _temporal_index()
    heights = _release_heights()
    geometry_rows = _geometry_index()
    from pkinv.report import reporting_sectors
    reporting_rows = reporting_sectors.rows()
    measured_class = _measured_class()
    placements = _placements()
    provenance = _provenance()
    periods = {s.NAME: (s.PERIOD_START.isoformat(), s.PERIOD_END.isoformat())
               for s in registry.all_sectors()}
    proxies = {s.NAME: s for s in registry.all_sectors()}
    axes_by_module = {}
    for axis in national_rollup.scenario_registry():
        axes_by_module.setdefault(axis["module"], []).append(axis["axis"])

    out = []
    for c in comps:
        module = c["_sector"]
        # PER COMPONENT, and with no default. This line used to read
        # `codes.get(c["category"], UNRESOLVED)`; when the IPCC 2006 migration split manure
        # management and managed soils, the dict stopped carrying those two categories and 24
        # stream rows quietly shipped the literal string "unresolved" in their code column -
        # the whole file still built, and nothing failed. A half-done rename that reaches
        # writers and not readers fails silently, so this raises instead.
        code = component_code(c["category"], c["subitem"], c["gas"])
        groups = parameters.groups_for(c, scopes)
        activity, conversion, factor, identity = _split_parameters(groups)
        key = (module, c["category"], c["subitem"], c["gas"])
        profile_id, profile_source = temporal.get(key, (UNRESOLVED, UNRESOLVED))
        start, end = periods[module]
        try:
            proxy = proxies[module].proxy_for(c)
        except Exception:                                   # noqa: BLE001 - declare, not crash
            proxy = UNRESOLVED
        files, archival, licence = provenance.get(
            c["source_id"], ([], UNRESOLVED, UNRESOLVED))
        geometry = _geometry_for(geometry_rows, module, c["category"], c["subitem"])
        from pkinv.core.primary_geography import RAIL_GEOMETRIES
        compatible_rail = geometry in RAIL_GEOMETRIES
        if compatible_rail:
            geometry = "S4:no-native-geometry"
            proxy = "railways_freight_div"
        out.append({
            "release_version": pkinv.__version__,
            # Read from the row, not recomputed: the component already carries its
            # identity under schema v3.
            "source_stream_id": c.get("component_id") or stream_id(
                module, c["category"], c["subitem"], c["gas"]),
            "module": module,
            # The sector IPCC 2006 REPORTS the stream under, declared per stream in
            # data/stream_reporting_sector.csv beside the module that computes it; the
            # module vocabulary, additive with `module` at every grain. Captive gas
            # self-generation is the one row that differs (power computes, industry reports).
            "reporting_sector": reporting_sectors.resolve(
                reporting_rows, module, c["category"], c["subitem"]),
            "ipcc_code": code,
            "ipcc_category": category_ledger.IPCC_CATEGORY_NAMES.get(code, UNRESOLVED),
            "sub_category": c["subitem"],
            # The engine has no process concept distinct from the sub-item. Declared rather
            # than faked: a process taxonomy invented here would be a fourth category
            # hierarchy, and this project already paid for having two.
            "process": NOT_APPLICABLE,
            "gas": c["gas"],
            "methane_origin": ("fossil" if c.get("fossil") else "biogenic")
                              if c["gas"] == "CH4" else NOT_APPLICABLE,
            # Every stream in this ledger is estimated by construction; the 42 non-E rows of
            # completeness.csv are its complement, not its members.
            "notation_key": "E",
            "inventory_period_start": start,
            "inventory_period_end": end,
            "activity_year": c["activity_year"],
            "activity_period_kind": c["activity_period_kind"],
            "emissions_native": round(c["emissions_Gg"], 6),
            "native_unit": "Gg",
            "emissions_ar5": round(c["co2e_Mt_AR5"], 8),
            "emissions_ar6": round(c["co2e_Mt_AR6"], 8),
            "evidence_class": c["evidence_class"],
            "activity_parameter_ids": ";".join(activity) or UNRESOLVED,
            # rc40 G3: a stream whose factor is resolved and which has no conversion step
            # has a definite answer - none - not an unresolved one. Kept unresolved where
            # the factor is too, so the two states stay distinguishable.
            "conversion_parameter_ids": ";".join(conversion) or (
                "none" if factor else UNRESOLVED),
            "factor_parameter_ids": ";".join(factor) or UNRESOLVED,
            "factor_identity_ids": ";".join(
                _factor_table_ids(identity, by_group, c["gas"], bindings)) or UNRESOLVED,
            "scenario_id": national_rollup.SCENARIO_ID,
                        # MODULE-scoped, and named so. data/scenarios.csv registers an axis against a
            # module, not against a stream, so the power gas row lists the coal-energy fork
            # even though no gas row depends on it. Calling the field structural_axes would
            # read as "the axes this stream depends on", which is a stronger claim than the
            # registry supports; per-stream scoping needs the axis to declare the categories
            # it moves, which is a scenario-registry change and not this round's.
            "module_structural_axes": ";".join(axes_by_module.get(module, [])) or "none",
            "temporal_class": c["temporal_method"],
            "temporal_profile_id": profile_id,
            "temporal_profile_source": profile_source,
            "spatial_class": "NA" if compatible_rail else c["spatial_method"],
            "spatial_class_measured": _refined_measured(measured_class[geometry], geometry,
                                                        proxy, placements),
            "geometry_available": "no" if geometry == "S4:no-native-geometry" else "yes",
            "spatial_view": ("accounting" if compatible_rail else
                             _view_for(geometry_rows, module, c["category"], c["subitem"])),
            "spatial_profile_id": proxy,
            "geometry_id": geometry,
            "release_height_class": heights(module, c["category"], c["subitem"]),
            "source_id": c["source_id"],
            "source_document_ids": ";".join(files) or UNRESOLVED,
            "archival_state": archival,
            "licence_status": licence,
        })
    out.sort(key=lambda r: (r["module"], r["ipcc_code"], r["sub_category"], r["gas"]))
    # FAIL CLOSED ON A LETTER NOBODY MEASURED. The declared class is a sector engine's
    # constant; the measured one is read from what the allocation does. Where they disagree
    # the release does not build, because publishing both and letting a reader choose is how
    # this project shipped a spatial profile that said S2 for 58 Mt allocated on a raster.
    # The fix for a failure here is a sector engine's SPATIAL_METHOD or an allocation that
    # earns the letter - never a widened comparison.
    disagree = sorted((r["module"], r["sub_category"], r["spatial_class"],
                       r["spatial_class_measured"], r["geometry_id"])
                      for r in out if r["spatial_class"] != r["spatial_class_measured"])
    if disagree:
        raise ValueError(
            "%d streams declare a spatial class the allocation does not earn. The declared "
            "letter lives on the sector engine; the measured one is derived from "
            "data/geometry_sets.csv within_province_placement and the facility registry:\n  "
            % len(disagree)
            + "\n  ".join("%s / %s declares %s, allocation earns %s (%s)" % row
                          for row in disagree))
    return out, profile_registry


VIEW_MEANING = {
    "physical": "placed where the emission happens",
    "origin": "placed where the generating activity originates; the release is elsewhere "
              "and its geography is not held",
    "accounting": "placed where the statistic is booked; the emission occurs wherever the "
                  "vehicle, boiler or process is",
}


def write_view_profile(rows, path=None):
    """The spatial-VIEW distribution, nationally and per module.

    The third axis, beside spatial_profile.csv's S1-S3 and the release-height profile. The
    other two say how finely mass is placed and how high it leaves; this one says whether the
    place is where the emission happens at all, and it is the only one of the three a reader
    can get wrong while doing everything else right. About a fifth of this inventory is not
    physical - waste at the people who generate it rather than at the landfill, road and
    industrial fuel at the province of sale rather than at the road - and before this file
    existed every product added the three together and returned one number.
    """
    path = path or asset_path(OUTPUTS, "spatial_view_profile.csv")
    national, per_module = {}, {}
    for r in rows:
        view, module, mt = r["spatial_view"], r["module"], r["emissions_ar5"]
        national[view] = national.get(view, 0.0) + mt
        per_module.setdefault(module, {})
        per_module[module][view] = per_module[module].get(view, 0.0) + mt
    grand = sum(national.values())
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["scope", "spatial_view", "meaning", "co2e_Mt_AR5",
                    "share_of_scope_pct"])
        for view in sorted(national):
            w.writerow(["NATIONAL", view, VIEW_MEANING[view], round(national[view], 4),
                        round(100 * national[view] / grand, 2)])
        for module in sorted(per_module):
            total = sum(per_module[module].values())
            for view in sorted(per_module[module]):
                w.writerow([module, view, VIEW_MEANING[view],
                            round(per_module[module][view], 4),
                            round(100 * per_module[module][view] / total, 2)])
    return path


def write_spatial_profile(rows, path=None):
    """The spatial-class distribution, nationally and per module.

    The exact analogue of outputs/temporal_profile.csv, and overdue: S1-S4 has been REQUIRED
    on every component row since the schema freeze, validated on every build, and published
    nowhere. Appendix B of the manuscript reports the national share by temporal class and
    there was no spatial counterpart to put beside it, so "where does this inventory actually
    know its geography" had no answer a reader could look up.
    """
    path = path or asset_path(OUTPUTS, "spatial_profile.csv")
    national, per_module = {}, {}
    for r in rows:
        cls, module, mt = r["spatial_class"], r["module"], r["emissions_ar5"]
        national[cls] = national.get(cls, 0.0) + mt
        per_module.setdefault(module, {})
        per_module[module][cls] = per_module[module].get(cls, 0.0) + mt
    grand = sum(national.values())
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["scope", "spatial_method", "meaning", "co2e_Mt_AR5",
                    "share_of_scope_pct"])
        for cls in sorted(national):
            w.writerow(["NATIONAL", cls, evidence.SPATIAL[cls], round(national[cls], 4),
                        round(100 * national[cls] / grand, 2)])
        for module in sorted(per_module):
            total = sum(per_module[module].values())
            for cls in sorted(per_module[module]):
                w.writerow([module, cls, evidence.SPATIAL[cls],
                            round(per_module[module][cls], 4),
                            round(100 * per_module[module][cls] / total, 2)])
    return path


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows, _profiles = build()
    path = asset_path(OUTPUTS, "pakemis_source_streams.csv")
    write_table(path, list(FIELDS), rows)

    spatial = write_spatial_profile(rows)
    views = write_view_profile(rows)
    total = sum(r["emissions_ar5"] for r in rows)
    print("source-stream ledger -> %s" % path)
    print("spatial class profile -> %s" % spatial)
    print("spatial view profile  -> %s" % views)
    print("  %d streams, %d fields, schema %s, release %s"
          % (len(rows), len(FIELDS), components_core.SCHEMA_VERSION, pkinv.__version__))
    print("  %.2f Mt CO2e (AR5) under %s" % (total, national_rollup.SCENARIO_ID))
    for field in ("factor_identity_ids", "temporal_profile_id", "licence_status"):
        gaps = sum(1 for r in rows if r[field] in (UNRESOLVED, "undetermined"))
        print("  %-24s %d of %d unresolved" % (field, gaps, len(rows)))
    by_geo = {}
    for r in rows:
        by_geo[r["geometry_id"]] = by_geo.get(r["geometry_id"], 0) + 1
    print("  geometry: %d ids over %d streams; %d streams explicit S4 residual"
          % (len(by_geo), len(rows), by_geo.get("S4:no-native-geometry", 0)))
    by_view = {}
    for r in rows:
        by_view[r["spatial_view"]] = by_view.get(r["spatial_view"], 0.0) + r["emissions_ar5"]
    print("  spatial view, share of national total:")
    for view in sorted(by_view, key=lambda v: -by_view[v]):
        print("    %-12s %9.2f Mt %6.2f%%"
              % (view, by_view[view], 100 * by_view[view] / total))
    print("    %-12s %9.2f Mt %6.2f%%  <- placed somewhere other than where it is emitted"
          % ("NOT physical", total - by_view.get("physical", 0.0),
             100 * (total - by_view.get("physical", 0.0)) / total))
    by_height = {}
    for r in rows:
        by_height[r["release_height_class"]] = \
            by_height.get(r["release_height_class"], 0.0) + r["emissions_ar5"]
    print("  release height, share of national total:")
    for name, value in sorted(by_height.items(), key=lambda kv: -kv[1]):
        print("    %-24s %6.2f Mt  %5.1f%%" % (name, value, 100 * value / total))
    assert set(evidence.RELEASE_HEIGHT) >= set(by_height), "height outside the vocabulary"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
