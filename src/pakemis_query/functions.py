"""The public functions of the contract, beyond query_emissions (which lives on the Engine).

Each returns an envelope. They read the dimension and fact tables through the engine's DuckDB
views; none computes a number the release does not carry, except compare (a difference of two
exact sums, stated as such) and the grid cell lookup (a value read from the NetCDF)."""
import dataclasses
import os

from pakemis_query import errors as E
from pakemis_query.engine import DECIMAL, REFERENCE_PERIOD
from pakemis_query.envelope import envelope, value
from pakemis_query.receipt import receipt_id
from pakemis_query.models import (CompareRequest, EvidenceRequest, GridCellRequest, MethodRequest,
                                  QueryActivity, QueryEmissions, SpatialLineageRequest, TimeseriesRequest,
                                  TransferRequest, UncertaintyRequest, CompletenessRequest,
                                  canonical_json)


def compare_emissions(engine, req):
    left, right = engine.query_emissions(req.left), engine.query_emissions(req.right)
    ql, qr = engine._fill(req.left), engine._fill(req.right)
    if ql.basis != qr.basis:
        raise E.MixedBasisError("a comparison never crosses bases (%s vs %s)" % (ql.basis, qr.basis))
    if ql.gwp_basis != qr.gwp_basis:
        raise E.MixedGwpError("a comparison never crosses GWP bases")
    from decimal import Decimal
    values = []
    for lv, rv in zip(left["values"], right["values"]):
        a, b = Decimal(lv["exact"]), Decimal(rv["exact"])
        delta = b - a
        if req.mode == "relative":
            exact = str((delta / a * 100).quantize(Decimal("0.000001"))) if a else ""
            values.append(value(exact, "percent", 1, formula="(right - left) / left x 100", left=lv, right=rv))
        else:
            values.append(value(str(delta), lv["unit"], engine.decimals["co2e_Mt"]["sector"],
                                formula="right - left (two exact sums)", left=lv, right=rv))
    fields = dataclasses.asdict(ql)
    fields["periods"] = tuple(sorted(set(ql.periods) | set(qr.periods)))
    fields["configuration_id"] = "%s vs %s" % (ql.configuration_id, qr.configuration_id) if ql.configuration_id != qr.configuration_id else ql.configuration_id
    return envelope(engine.release, "compare_emissions", canonical_json(req), fields, values,
                    {"kind": "difference", "mode": req.mode, "left": left["calculation"], "right": right["calculation"]},
                    left["provenance"], uncertainty=left["uncertainty"],
                    limitations_hit=[l["id"] for l in left["limitations_hit"]] + [l["id"] for l in right["limitations_hit"] if l not in left["limitations_hit"]])


def get_timeseries(engine, req):
    q = engine._fill(req.query)
    periods = tuple(p["period_id"] for p in engine.release.dim("dim_period") if p["basis"] == q.basis)
    if q.basis == "fiscal" and q.configuration_id == "L_2023_24":
        raise E.GrainUnavailable("configuration L exists for FY2023-24 only; a series is the reference's", "config_L_residential_only")
    group = ("month",) if req.step == "monthly" else ("period_id",)
    series = dataclasses.replace(q, periods=periods, group_by=group + tuple(g for g in q.group_by if g not in group),
                                 months=q.months, defaults_applied=q.defaults_applied)
    if req.step == "monthly":
        months = tuple(m["month"] for m in engine.release.dim("dim_month"))
        series = dataclasses.replace(series, months=months)
    out = engine.query_emissions(series)
    # RE-MINT THE RECEIPT OVER THE REQUEST WE ACTUALLY STORE. query_emissions hashed it over the
    # EXPANDED QueryEmissions above; overwriting `request` here without re-minting left an envelope
    # whose stored request does not reproduce its stored receipt, so a replay of a timeseries
    # download link failed `receipt_not_reproduced` while every other request type replayed. The
    # citation carries the receipt too, and moved with it. compare_emissions never had this
    # because it passes its own canonical request into envelope() - see the call below.
    out["request_type"] = "get_timeseries"
    out["request"] = canonical_json(req)
    minted = receipt_id(out["request"], engine.release.release_id, out["result_sha256"])
    out["citation"] = out["citation"].replace(out["receipt"], minted)
    out["receipt"] = minted
    return out


def get_uncertainty(engine, req):
    r = engine.release
    if req.scope == "series":
        rows = engine._fetch("SELECT * FROM fact_uncertainty_series WHERE kind IN ('annual_level','trend_pair')"
                             + (" AND period_or_pair = '%s'" % req.period_id if req.period_id else ""))
        table = "fact_uncertainty_series"
    elif req.scope == "national":
        rows = engine._fetch("SELECT * FROM fact_uncertainty_series WHERE kind = 'parametric_reference' AND scope = 'national'")
        table = "fact_uncertainty_series"
    else:
        where = []
        if req.category:
            where.append("category = '%s'" % req.category.replace("'", "''"))
        if req.module:
            where.append("module = '%s'" % req.module)
        if req.resolution:
            where.append("resolution = '%s'" % req.resolution)
        rows = engine._fetch("SELECT * FROM fact_uncertainty" + (" WHERE " + " AND ".join(where) if where else ""))
        table = "fact_uncertainty"
    values = []
    for row in rows:
        if table == "fact_uncertainty_series":
            values.append(value(row["P50_Mt"], "Mt CO2e AR5", 3, row_ids=[row["result_row_id"]],
                                formula="P50 of the draws", quantiles={"P2.5": row["P2.5_Mt"], "P97.5": row["P97.5_Mt"]},
                                kind=row["kind"], key=row["key"], scenario=row["scenario"]))
        else:
            values.append(value(row["estimate_Mt"], "Mt CO2e AR5", 3, row_ids=[row["result_row_id"]],
                                formula="the category's published estimate with its envelope",
                                envelope={"low_pct": row["envelope_low_pct"], "high_pct": row["envelope_high_pct"],
                                          "kind": row["envelope_kind"]},
                                category=row["category"], module=row["module"], resolution=row["resolution"],
                                aggregation_rule=row["aggregation_rule"]))
    fields = {"basis": "fiscal", "periods": (req.period_id or REFERENCE_PERIOD,),
              "configuration_id": req.configuration_id or r.defaults["configuration_id"], "gwp_basis": "AR5"}
    return envelope(r, "get_uncertainty", canonical_json(req), fields, values,
                    {"kind": "lookup", "table": table}, engine._provenance([table]),
                    uncertainty={"interpretation": "quantiles of draws for the series; per-category envelopes "
                                                   "(structural, no probability) for the joint table - never quadrature"})


def get_completeness(engine, req):
    where = []
    if req.notation_keys:
        where.append(engine._in("notation_key", req.notation_keys))
    if req.ipcc_codes:
        where.append("(" + " OR ".join("code = '%s' OR code LIKE '%s.%%'" % (c, c) for c in req.ipcc_codes) + ")")
    rows = engine._fetch("SELECT * FROM fact_completeness" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY code, gas")
    values = [value("", "notation_key", 0, row_ids=[r["result_row_id"]], formula="completeness.csv row",
                    code=r["code"], category=r["category"], gas=r["gas"], notation_key=r["notation_key"],
                    justification=r["justification"], gap_id=r["gap_id"]) for r in rows]
    for v in values:
        v["display"] = v["notation_key"]
    return envelope(engine.release, "get_completeness", canonical_json(req), {"basis": "fiscal", "periods": (REFERENCE_PERIOD,)},
                    values, {"kind": "lookup", "table": "fact_completeness"}, engine._provenance(["fact_completeness"]))


def get_evidence(engine, req):
    where = []
    if req.source_stream_id:
        where.append("e.source_stream_id = '%s'" % req.source_stream_id.replace("'", "''"))
    if req.module:
        where.append("e.module = '%s'" % req.module)
    if req.category:
        where.append("s.ipcc_category = '%s'" % req.category.replace("'", "''"))
    rows = engine._fetch("SELECT e.*, s.ipcc_code, s.ipcc_category, s.sub_category, s.methane_origin, s.source_id, s.source_document_ids "
                         "FROM fact_evidence e JOIN dim_stream s USING (source_stream_id)"
                         + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY e.source_stream_id")
    values = [value("", "evidence", 0, row_ids=[r["result_row_id"]], formula="stream lineage row", **{k: r[k] for k in r if k != "result_row_id"}) for r in rows]
    for v in values:
        v["display"] = "%s / %s / %s" % (v["evidence_class"], v["temporal_class"], v["spatial_class_measured"])
    return envelope(engine.release, "get_evidence", canonical_json(req), {"basis": "fiscal", "periods": (REFERENCE_PERIOD,)},
                    values, {"kind": "lookup", "table": "fact_evidence"}, engine._provenance(["fact_evidence", "dim_stream"]),
                    evidence={"grades": "E (activity evidence), TE (timing), S (placement); see dim_evidence_class"})


def get_method(engine, req, method_rows):
    """method_rows: data/method_registry.csv rows handed in by the service (the registry is a
    data file the semantic release lists among its products)."""
    rows = [r for r in method_rows if (not req.method_id or r["method_id"] == req.method_id)
            and (not req.category or r["category"] == req.category)]
    values = [value("", "method", 0, formula=r.get("equation", ""), **r) for r in rows]
    for v in values:
        v["display"] = v.get("method_id", "")
    path = "data/method_registry.csv"
    digest = engine.release.product_digest(path)
    catalog = engine.release.contract.get("asset_catalog")
    if catalog:
        asset_id = catalog["bindings"]["method_registry"]
        asset = next((asset for asset in catalog["assets"] if asset["asset_id"] == asset_id), None)
        if asset is None:
            raise E.IdentityError("method registry asset binding is absent: %s" % asset_id)
        path, digest = asset["path"], asset["sha256"]
    return envelope(engine.release, "get_method", canonical_json(req), {"basis": "fiscal", "periods": (REFERENCE_PERIOD,)},
                    values, {"kind": "lookup", "table": path},
                    {"tables": [{"path": path, "sha256": digest}]})


def get_spatial_lineage(engine, req):
    conf = req.configuration_id or engine.release.defaults["configuration_id"]
    where = ["configuration_id = '%s'" % conf]
    if req.shape_id:
        where.append("shape_id = '%s'" % req.shape_id)
    if req.province:
        where.append("province = '%s'" % req.province.replace("'", "''"))
    if req.month:
        where.append("month = '%s'" % req.month)
    if req.gas:
        where.append("gas = '%s'" % req.gas)
    rows = engine._fetch("SELECT * FROM fact_adm2_month WHERE %s ORDER BY module, gas, month, spatial_view" % " AND ".join(where))
    geo = [g for g in engine.release.dim("dim_geography") if g["shape_id"] == req.shape_id] if req.shape_id else []
    values = [value(r["co2e_Mt_AR5"], "Mt CO2e AR5", 4, row_ids=[r["result_row_id"]],
                    formula="ADM2 module x gas x month row", module=r["module"], gas=r["gas"], month=r["month"],
                    spatial_view=r["spatial_view"], allocation_status=r["allocation_status"],
                    absence_reason=r["absence_reason"], emissions_Gg=r["emissions_Gg"],
                    exactness=r["co2e_exactness"]) for r in rows]
    unalloc = engine._fetch("SELECT module, gas, SUM(CAST(co2e_Mt_AR5 AS %s)) AS exact FROM fact_unallocated WHERE configuration_id = '%s'%s GROUP BY module, gas"
                            % (DECIMAL, conf, (" AND province = '%s'" % (req.province or (geo[0]["parent_id"].split(":")[1] if geo else "")).replace("'", "''")) if (req.province or geo) else ""))
    fields = {"basis": "fiscal", "periods": (REFERENCE_PERIOD,), "configuration_id": conf, "gwp_basis": "AR5",
              "geography_level": "adm2" if req.shape_id else "adm1", "geography_ids": (req.shape_id or req.province,), "spatial_view": "all"}
    return envelope(engine.release, "get_spatial_lineage", canonical_json(req), fields, values,
                    {"kind": "lookup", "table": "fact_adm2_month"}, engine._provenance(["fact_adm2_month", "fact_unallocated"]),
                    evidence={"geography": geo}, unallocated={"by_module_gas": [{"module": r["module"], "gas": r["gas"], "exact": str(r["exact"])} for r in unalloc]},
                    limitations_hit=["no_polygon_units", "ar6_adm2_ne"])


def get_cross_sector_transfer(engine, req):
    where = []
    if req.ledger_id:
        where.append("ledger_id = '%s'" % req.ledger_id)
    if req.configuration_id:
        where.append("configuration_id = '%s'" % req.configuration_id)
    rows = engine._fetch("SELECT * FROM fact_transfer" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY ledger_id, configuration_id, row_id")
    values = [value(r["value"], r["units"], 4, row_ids=[r["result_row_id"]], formula="%s#%s#%s" % (r["source_file"], r["row_key"], r["value_column"]),
                    ledger_id=r["ledger_id"], row_id=r["row_id"], kind=r["kind"], status=r["status"],
                    origin=r["origin_sector"], destination=r["destination_sector"], configuration_id=r["configuration_id"]) for r in rows]
    return envelope(engine.release, "get_cross_sector_transfer", canonical_json(req), {"basis": "fiscal", "periods": (REFERENCE_PERIOD,), "configuration_id": req.configuration_id or "all"},
                    values, {"kind": "ledger", "closure": "control == transfers + unresolved, per ledger and configuration"}, engine._provenance(["fact_transfer"]))


def _time_origin(variable):
    """The epoch a cube's time axis is counted from, READ from the file.

    This used to be the literal date(2023, 7, 1). That was correct for the monthly cube and
    only for it - the annual cube counts days since 1970-01-01 - so the constant would have
    returned a confidently wrong month the first time the lookup was pointed at history. A CF
    time variable states its own origin; there is no reason to guess it.
    """
    from datetime import date
    units = getattr(variable, "units", "")
    if "since" not in units:
        raise E.GrainUnavailable(
            "the cube's time axis declares no origin (units=%r), so a month cannot be "
            "resolved against it" % units, "grid_not_tabular")
    stamp = units.split("since", 1)[1].strip().split()[0]
    return date.fromisoformat(stamp)


def get_grid_cell(engine, req, cube_paths):
    """cube_paths: {"REF_2023_24": path, "L_2023_24": path, "ANNUAL": path} to the products.

    Three refusals live here rather than in a caller, because a lookup that answers anyway is
    worse than one that declines: a point outside the grid, the period-named alternative
    configuration outside its period, and a historical MONTH. The last is the honest shape of the products -
    eight of the nine years have annual cells and no monthly ones, because a historical month's
    seasonal geography is not evidenced and will not be invented to satisfy a query.
    """
    try:
        from netCDF4 import Dataset
    except ImportError as exc:
        raise E.GrainUnavailable("the grid needs netCDF4: %s" % exc, "grid_not_tabular")
    conf = req.configuration_id or engine.release.defaults["configuration_id"]
    period = req.period_id or REFERENCE_PERIOD
    historical = period != REFERENCE_PERIOD

    if historical and conf != "REF_2023_24":
        raise E.NotEstimated(
            "configuration %s is built on the grid for %s alone; %s is published under "
            "the reference configuration only"
            % (conf, REFERENCE_PERIOD, period), "configuration_l_reference_year_only")
    if historical and req.month and req.month != "annual":
        raise E.GrainUnavailable(
            "the monthly grain is the reference year's alone; %s is published annually on the "
            "grid (a historical month's seasonal geography is not evidenced)" % period,
            "grid_monthly_reference_year_only")

    path = cube_paths["ANNUAL"] if historical else cube_paths[conf]
    ds = Dataset(path)
    try:
        lats, lons = ds["lat"][:], ds["lon"][:]
        # A DOMAIN CHECK, BECAUSE argmin ALWAYS SUCCEEDS. Without this, a query for Delhi or
        # for the middle of the Arabian Sea snaps to the nearest edge cell and is returned with
        # a receipt, a digest and four decimal places. Half a cell is the tolerance: outside it
        # the point is not in this grid and the honest answer is that there is no cell.
        half = float(abs(lats[1] - lats[0])) / 2.0
        if (req.lat > float(lats.max()) + half or req.lat < float(lats.min()) - half
                or req.lon > float(lons.max()) + half or req.lon < float(lons.min()) - half):
            raise E.UnknownDimensionValue(
                "(%.4f, %.4f) is outside the Pakistan grid domain (lat %.2f..%.2f, lon "
                "%.2f..%.2f)" % (req.lat, req.lon, float(lats.min()), float(lats.max()),
                                 float(lons.min()), float(lons.max())), "grid_domain")
        i = int(abs(lats - req.lat).argmin()); j = int(abs(lons - req.lon).argmin())

        if historical:
            var = ds["%s_emissions" % req.gas.lower()]
            periods = [str(p) for p in ds["period_id"][:]]
            if period not in periods:
                raise E.UnknownDimensionValue(
                    "%s is not one of the nine gridded periods %s" % (period, periods),
                    "grid_period")
            k = periods.index(period)
            views = [str(v) for v in ds["spatial_view"][:]]
            if req.spatial_view:
                if req.spatial_view not in views:
                    raise E.UnknownDimensionValue(
                        "%s is not a spatial view %s" % (req.spatial_view, views), "grid_view")
                cell = var[k, views.index(req.spatial_view), i, j]
            else:
                cell = var[k, :, i, j].sum()
            # A masked cell is OUTSIDE PAKISTAN, which is a different claim from zero.
            import numpy as _np
            if _np.ma.is_masked(cell):
                raise E.NotEstimated(
                    "(%.4f, %.4f) is inside the grid but outside Pakistan: the cube masks "
                    "non-national cells rather than calling them zero" % (req.lat, req.lon),
                    "grid_outside_country")
            val = float(cell)
        else:
            var = ds["%s_Gg" % req.gas.lower()]
            if req.spatial_view:
                raise E.GrainUnavailable(
                    "the monthly cube carries no spatial_view dimension; views are published "
                    "on the annual grid", "grid_not_tabular")
            if req.month and req.month != "annual":
                from datetime import date
                origin = _time_origin(ds["time"])
                t = int((date(int(req.month[:4]), int(req.month[4:]), 1) - origin).days)
                axis = [int(x) for x in ds["time"][:]]
                if t not in axis:
                    raise E.UnknownDimensionValue(
                        "%s is not a month of %s" % (req.month, REFERENCE_PERIOD), "grid_month")
                val = float(var[axis.index(t), i, j])
            else:
                val = float(var[:, i, j].sum())
        conservation = getattr(ds, "conservation", "")
    finally:
        ds.close()
    v = value(repr(val), "Gg", engine.decimals["emissions_Gg"], formula="cell value read from %s" % os.path.basename(path),
              lat=float(lats[i]), lon=float(lons[j]), row=i, col=j, month=req.month or "annual",
              period_id=period, spatial_view=req.spatial_view or "all (the three views sum)")
    return envelope(engine.release, "get_grid_cell", canonical_json(req),
                    {"basis": "fiscal", "periods": (period,), "configuration_id": conf, "gwp_basis": "native", "geography_level": "grid"},
                    [v], {"kind": "lookup", "table": os.path.basename(path), "conservation": conservation},
                    {"tables": [{"path": "outputs/" + os.path.basename(path), "sha256": engine.release.product_digest("outputs/" + os.path.basename(path))}]},
                    limitations_hit=["grid_not_tabular"])


# --- query_activity ---------------------------------------------------------------------------
# The columns every activity table shares, in the order the release writes them. A table's
# CLASS columns are the ones between Measure and Value (vehicles: "Vehicle class", "Fuel";
# livestock: "Animal type"), read from the table's own header rather than listed here, so a
# table added later is queryable without a second copy of its schema.
ACTIVITY_STANDARD = ("Period", "Location", "Province", "Locality", "Measure", "Value", "Unit",
                     "Period type", "Reporting interval", "Location level", "Evidence",
                     "Source status", "Source series", "Use note", "Source reference", "Record ID")
ACTIVITY_ROW_CAP = 400
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")


def activity_tables(release):
    """The queryable activity tables of the release: the fact_activity_* facts except the
    source-detail join table, which is not a record table."""
    return sorted(t for t in release.tables
                  if t.startswith("fact_activity_") and t != "fact_activity_source_details")


def _activity_columns(engine, table):
    cols = [d[0] for d in engine.con.execute("SELECT * FROM %s LIMIT 0" % table).description]
    i, j = cols.index("Measure"), cols.index("Value")
    return cols, cols[i + 1:j]


def _period_label(period, period_type):
    """'2023-06-30' -> '30 June 2023' when the period is a date; otherwise as printed."""
    parts = str(period).split("-")
    if len(parts) == 3 and all(x.isdigit() for x in parts) and len(parts[0]) == 4:
        y, m, d = (int(x) for x in parts)
        if 1 <= m <= 12:
            return "%d %s %d" % (d, _MONTHS[m - 1], y)
    return str(period)


def _display_grouped(exact):
    """The source's figure with thousands separators and its own decimals: 1561386 -> '1,561,386',
    0.275 -> '0.275'. No rounding: what is printed is what the source printed."""
    from decimal import Decimal
    try:
        x = Decimal(exact)
    except Exception:
        return str(exact)
    if x == x.to_integral_value():
        return "{:,}".format(int(x))
    return "{:,f}".format(x)


def _display_words(exact):
    """A count as a reader would say it: 4,822,762 -> '4.82 million'; below a million, the grouped figure."""
    from decimal import Decimal
    try:
        x = Decimal(exact)
    except Exception:
        return str(exact)
    ax = abs(x)
    if ax >= 1_000_000_000:
        return "%s billion" % (x / 1_000_000_000).quantize(Decimal("0.01"))
    if ax >= 1_000_000:
        return "%s million" % (x / 1_000_000).quantize(Decimal("0.01"))
    return _display_grouped(exact)


def _activity_held(engine, table, where, params, column):
    """The distinct values of one column under a filter, for a refusal that says what IS held."""
    sql = 'SELECT DISTINCT t."%s" AS v FROM %s t' % (column, table)
    if where:
        sql += " WHERE " + " AND ".join(where)
    return sorted(r[0] for r in engine.con.execute(sql, params).fetchall() if r[0] not in (None, ""))


def query_activity(engine, req):
    """Rows of one activity table, filtered, each carrying its definitions. The value is the
    source's figure in the source's unit; `total` adds one computed sum and says it is one."""
    release = engine.release
    tables = activity_tables(release)
    if not req.table:
        raise E.UnknownDimensionValue("name the activity table: one of %s" % ", ".join(tables))
    if req.table not in tables:
        raise E.UnknownDimensionValue("%r is not an activity table of this release; the tables are %s"
                               % (req.table, ", ".join(tables)))
    cols, classes = _activity_columns(engine, req.table)
    if req.location_level:
        # matched without case, as a location is: the tables print "District", a caller types "district"
        levels = sorted(r["Location level"] for r in
                        engine._fetch('SELECT DISTINCT "Location level" FROM %s' % req.table))
        if req.location_level.lower() not in {level.lower() for level in levels}:
            raise E.UnknownDimensionValue("%r is not a location level of %s (it has: %s)"
                                          % (req.location_level, req.table, ", ".join(levels)))
    if req.order_by not in ("", "value desc", "value asc"):
        raise E.UnknownDimensionValue("order_by is 'value desc', 'value asc' or empty")
    # the filter in three parts, so a refusal can say what the release holds once one part is dropped
    base, base_params = [], []
    if req.measure:
        base.append('t."Measure" = ?'); base_params.append(req.measure)
    if req.location_level:
        base.append('lower(t."Location level") = ?'); base_params.append(req.location_level.lower())
    if req.categories:
        if not classes:
            raise E.UnknownDimensionValue("%s has no class column to filter on" % req.table)
        base.append('lower(t."%s") IN (%s)' % (classes[0], ",".join("?" * len(req.categories))))
        base_params += [c.lower() for c in req.categories]
    place, place_params = [], []
    if req.locations:
        place.append('lower(t."Location") IN (%s)' % ",".join("?" * len(req.locations)))
        place_params += [l.lower() for l in req.locations]
    when, when_params = [], []
    if req.periods:
        # a period as printed, or the year of a printed date: "2023" finds the register of 2023-06-30
        when.append("(" + " OR ".join(['t."Period" = ? OR t."Period" LIKE ?'] * len(req.periods)) + ")")
        for period in req.periods:
            when_params += [period, period + "-__-__"]
    where, params = base + place + when, base_params + place_params + when_params
    detailed = "fact_activity_source_details" in release.tables
    sql = "SELECT t.*%s FROM %s t" % (
        ', d.combinable AS "_combinable", d.source_id AS "_source_table", d.source_row AS "_source_row"' if detailed else "",
        req.table)
    if detailed:
        sql += ' LEFT JOIN fact_activity_source_details d ON d."Record ID" = t."Record ID"'
    if where:
        sql += " WHERE " + " AND ".join(where)
    applied = []
    if not req.periods:
        # the latest period of each (place, measure, classes): a register's newest stock, a
        # series' last year - never a sum across periods
        keys = ", ".join('t."%s"' % c for c in ["Location", "Measure"] + classes)
        sql += ' QUALIFY t."Period" = MAX(t."Period") OVER (PARTITION BY %s)' % keys
        applied.append("periods")
    if req.order_by:
        sql += ' ORDER BY TRY_CAST(t."Value" AS DOUBLE) %s NULLS LAST, t."Location", t."Period"' % req.order_by.split()[1].upper()
    else:
        sql += ' ORDER BY t."Location", t."Period"' + "".join(', t."%s"' % c for c in classes)
    cap = req.limit if req.limit and req.limit > 0 else ACTIVITY_ROW_CAP
    sql += " LIMIT %d" % (cap + 1)
    cur = engine.con.execute(sql, params)
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    if not rows:
        # an empty answer would read as "there is none"; say what the release holds instead
        # worded for a reader: the refusal is shown as written, so it names the subject and never a table id
        target = " ".join(x for x in (req.measure or "anything", "/".join(req.categories),
                                      "in " + ", ".join(req.locations) if req.locations else "") if x)
        if req.periods:
            held = _activity_held(engine, req.table, base + place, base_params + place_params, "Period")
            if held:
                span = ("%s to %s (%d periods)" % (_period_label(held[0], ""), _period_label(held[-1], ""), len(held))
                        if len(held) > 1 else _period_label(held[0], ""))
                raise E.UnknownDimensionValue(
                    "no record of %s is held for %s; the records held run %s, and nothing later is held"
                    % (target, ", ".join(req.periods), span),
                    dimension="periods", first_period=held[0], last_period=held[-1])
        if req.locations:
            known = _activity_held(engine, req.table, base, base_params, "Location")
            near = [k for k in known if any(k.lower().startswith(l.lower()[:3]) for l in req.locations)][:12]
            raise E.UnknownDimensionValue(
                "no record of %s is held; these records name %d places%s"
                % (target, len(known), (", among them " + ", ".join(near)) if near else ""),
                dimension="locations")
        raise E.UnknownDimensionValue("no record of %s is held" % target)
    truncated = len(rows) > cap
    rows = rows[:cap]
    values = []
    for r in rows:
        exact = str(r["Value"] if r["Value"] not in (None, "") else "")
        decimals = 0 if exact and exact.lstrip("-").replace(".", "", 1).isdigit() and float(exact) == int(float(exact)) else 3
        extra = _activity_extra(r, classes)
        if exact:
            extra["display"] = _display_grouped(exact)
            extra["display_words"] = _display_words(exact)
        values.append(value(exact, r["Unit"], decimals, row_ids=[r["Record ID"]],
                            formula="as printed by the source; no arithmetic", **extra))
    if req.total:
        values.append(_activity_total(req, rows, classes, truncated, detailed))
    cur = engine.con.execute('SELECT "column", meaning FROM dim_activity_columns WHERE file = ?',
                             [req.table.replace("fact_", "") + ".csv"])
    definitions = {column: meaning for column, meaning in cur.fetchall()}
    fields = dataclasses.asdict(req)
    fields.update({"periods": tuple(sorted({r["Period"] for r in rows})), "basis": "as printed",
                   "configuration_id": "", "gwp_basis": "", "geography_level": req.location_level or "",
                   "geography_ids": tuple(req.locations), "spatial_view": ""})
    limitation = "activity:registered_stock" if req.table == "fact_activity_vehicles" else ""
    return envelope(release, "query_activity", canonical_json(req), fields, values,
                    {"kind": "records", "table": req.table, "class_columns": classes,
                     "definitions": definitions, "rows": len(rows), "truncated": truncated,
                     "total": bool(req.total),
                     "note": "each row's value is the source's own figure in the source's unit, never converted "
                             "or inferred, and its use note states what the figure is not; a `total` value is "
                             "the one sum this function computes, over one place, one period and one measure"},
                    engine._provenance([req.table]),
                    limitations_hit=[limitation] if limitation in release.limitations else [],
                    defaults_applied=applied)


def _activity_extra(r, classes):
    """The definitions one activity row carries: what is counted, where, when, on what evidence,
    from which source, and what the figure may not be read as."""
    extra = {"measure": r["Measure"], "location": r["Location"], "province": r.get("Province") or "",
             "locality": r.get("Locality") or "", "location_level": r["Location level"],
             "period": r["Period"], "period_type": r["Period type"],
             "period_label": _period_label(r["Period"], r["Period type"]),
             "classes": {c: r[c] for c in classes}, "category": r[classes[0]] if classes else "",
             "evidence": r["Evidence"], "source_status": r.get("Source status") or "",
             "source_series": r["Source series"], "use_note": r["Use note"],
             "source_reference": r["Source reference"], "record_id": r["Record ID"]}
    if r.get("_combinable"):
        extra["combinable"] = r["_combinable"]
    if r.get("_source_table"):
        # where the figure sits in the deposit: the ingested table and its row
        extra["source_table"] = r["_source_table"]
        extra["source_row"] = str(r.get("_source_row") or "")
    return extra


def _activity_total(req, rows, classes, truncated, detailed):
    """The sum of the rows returned, as ONE more value, under the release's own additivity rules:
    one measure, one unit, one place and one period, every row marked combinable. A register
    summed across years would count each vehicle once per year, and a projection summed with a
    count is neither, so anything wider is refused rather than added."""
    from decimal import Decimal, InvalidOperation
    if truncated:
        raise E.GrainUnavailable("a total needs every row and this result was cut at its row cap; narrow the request")
    if not detailed:
        raise E.GrainUnavailable("this release ships no combinable column, so no activity total is computed")
    for column, word in (("Measure", "measure"), ("Unit", "unit"), ("Location", "place"), ("Period", "period")):
        found = sorted({r[column] for r in rows})
        if len(found) != 1:
            raise E.GrainUnavailable(
                "a total is over the classes of one measure, one place and one period; this request returned %d %ss "
                "(%s). Name one." % (len(found), word, ", ".join(found[:8])), dimension=word)
    barred = sorted({r.get("_combinable") or "(not stated)" for r in rows
                     if not str(r.get("_combinable") or "").lower().startswith("yes")})
    if barred:
        raise E.GrainUnavailable("the release marks these rows as not to be combined: %s" % "; ".join(barred),
                                 dimension="combinable")
    if len({r["Evidence"] for r in rows}) != 1:
        raise E.GrainUnavailable("these rows mix evidence classes (%s) and are not summed"
                                 % ", ".join(sorted({r["Evidence"] for r in rows})), dimension="evidence")
    try:
        total = sum((Decimal(str(r["Value"])) for r in rows), Decimal(0))
    except (InvalidOperation, TypeError):
        raise E.GrainUnavailable("a row of this result has no numeric value, so no total is computed")
    exact = str(total.quantize(Decimal(1)) if total == total.to_integral_value() else total)
    first = rows[0]
    summed = [r[classes[0]] for r in rows] if classes else []
    extra = _activity_extra(first, classes)
    extra.update({"classes": {c: "" for c in classes}, "category": "Every class held, summed",
                  "classes_summed": "; ".join(summed), "derived": "sum",
                  "interpretation": "Computed here as the sum of the %s rows this release holds for this place and "
                                    "period. It is not a figure the source printed: the release withholds printed "
                                    "total rows, so a class the source lists and this release does not hold is not in it."
                                    % (classes[0].lower() if classes else "class"),
                  "record_id": "", "display": _display_grouped(exact), "display_words": _display_words(exact)})
    extra.pop("source_row", None)
    return value(exact, first["Unit"], 0 if "." not in exact else 3, row_ids=[r["Record ID"] for r in rows],
                 formula="sum of the %d rows above, as printed" % len(rows), **extra)


