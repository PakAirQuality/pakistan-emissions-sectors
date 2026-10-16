"""Read-only queries over verified emissions facts and dimensions.

The fiscal core comprises ten years and four named configurations. Unsupported
periods, mixed species sums and unavailable uncertainty grains receive typed
refusals. Native air mass is distinct from GWP-weighted greenhouse-gas quantities.
"""
import dataclasses
import os
from pakemis_query import configurations

from pakemis_query import errors as E
from pakemis_query.envelope import envelope, value
from pakemis_query.models import (GEOGRAPHY_LEVELS, VIEWS, QueryAir, QueryEmissions, canonical_json)

DECIMAL = "DECIMAL(38,18)"
REFERENCE_PERIOD = "FY2023-24"
# THE REPORTING-SECTOR AXIS (2026-09-12): a real column on every emissions fact, declared per
# stream in data/stream_reporting_sector.csv - the sector IPCC 2006 files a stream under, in the
# module vocabulary, beside sector_id (the module that computed it). The one row that differs is
# captive gas self-generation (1.A.2, computed by the power module, reported under industry).
# `group_by: ["reporting_sector"]` and the `reporting_sectors` filter are answerable at EVERY
# grain since rc54: the cube keys its district accumulator on (module, reporting_sector), so a
# module's district mass is partitioned by where the Guidelines report it rather than summed
# away. Until rc54 the district tables were module-resolved and the request was REFUSED there
# rather than answered with the module - a right-shaped answer to the wrong question.
REPORTING_SECTOR_KEY = "reporting_sector"
# The ECONOMIC-SECTOR regrouping (2026-09-11), a derived group key at national grain: the same
# atoms, grouped by what the activity IS rather than by the module that computed it.
# 'industrial' = the industry and ippu REPORTING sectors - 1.A.2 manufacturing combustion
# including the captive generation the power module computes (through the reporting axis, not a
# code match) plus every 2.x process category; every other sector keeps its module. Railways'
# unresolved '1.A.2/1.A.4.c' reports under railways and is not industry. Additive by
# construction - both views sum to the same national total - and the industrial aggregate is
# the release's own "covered direct industrial sources" boundary
# (outputs/pakemis_industry_boundary_ledger.csv), nothing screened or absent inside it.
ECONOMIC_SECTOR_KEY = "economic_sector"
ECONOMIC_SECTOR_SQL = ("CASE WHEN reporting_sector IN ('industry', 'ippu') "
                       "THEN 'industrial' ELSE reporting_sector END")


class Engine:
    def __init__(self, release, threads=1):
        import duckdb
        self.release = release
        self.con = duckdb.connect(database=":memory:")
        self.con.execute("SET threads TO %d" % threads)
        self.con.execute("SET preserve_insertion_order = true")
        for name in release.tables:
            path, kind = release.table_path(name)
            reader = "read_parquet" if kind == "parquet" else "read_csv"
            args = "'%s'" % path if kind == "parquet" else "'%s', header=true, all_varchar=true" % path
            self.con.execute("CREATE VIEW %s AS SELECT * FROM %s(%s)" % (name, reader, args))
        self.decimals = release.contract["rounding"]

    # --- defaults and validation --------------------------------------------------------

    def _fill(self, q):
        d = self.release.defaults
        applied = []
        fields = dataclasses.asdict(q)
        for key, default in (("basis", d["basis"]), ("configuration_id", d["configuration_id"]),
                             ("gwp_basis", d["gwp_basis"]), ("geography_level", "national"),
                             ("spatial_view", d["spatial_view"])):
            if not fields[key]:
                fields[key] = default
                applied.append(key)
        if not fields["periods"]:
            fields["periods"] = (d["period_id"],)
            applied.append("periods")
        fields["configuration_id"] = configurations.canonical(fields["configuration_id"])
        fields["defaults_applied"] = tuple(applied)
        return QueryEmissions(**fields)

    def _validate(self, q):
        r = self.release
        periods = {p["period_id"]: p for p in r.dim("dim_period")}
        for p in q.periods:
            if p not in periods:
                fiscal = [x for x in periods if x.startswith("FY")]
                raise E.UnknownDimensionValue(
                    "%r is not a period of this release; name a fiscal year (%s..%s) or a "
                    "calendar year CY1990..CY2024 (agriculture only)" % (p, fiscal[0], fiscal[-1]),
                    dimension="period_id", value=p)
            if periods[p]["basis"] != q.basis:
                raise E.MixedBasisError("period %s is on the %s basis; the request names %s"
                                        % (p, periods[p]["basis"], q.basis), period=p)
        if q.basis == "calendar" and (not q.sectors or set(q.sectors) != {"agriculture"}):
            raise E.NotEstimated("calendar-year values exist for agriculture only",
                                 "calendar_basis_ne")
        configurations = {c["configuration_id"]: c for c in r.dim("dim_configuration")}
        if q.configuration_id not in configurations or configurations[q.configuration_id]["queryable"] != "yes":
            raise E.UnknownDimensionValue("%r is not a queryable configuration (S_TAN, L_TAN, S_IPCC, L_IPCC)"
                                          % q.configuration_id, dimension="configuration_id")
        if q.gwp_basis not in ("AR5", "AR6"):
            raise E.UnknownDimensionValue("%r is not a GWP basis" % q.gwp_basis, dimension="gwp_basis")
        if q.geography_level not in GEOGRAPHY_LEVELS:
            raise E.UnknownDimensionValue("%r is not a geography level" % q.geography_level, dimension="geography_level")
        if q.geography_level == "adm2" and q.gwp_basis == "AR6":
            raise E.NotEstimated("AR6 CO2e is not carried at ADM2", "ar6_adm2_ne")
        if q.spatial_view not in VIEWS:
            raise E.UnknownDimensionValue("%r is not a spatial view" % q.spatial_view, dimension="spatial_view")
        return q

    # --- SQL helpers ----------------------------------------------------------------------

    @staticmethod
    def _in(column, values):
        return "%s IN (%s)" % (column, ", ".join("'%s'" % v.replace("'", "''") for v in values))

    def _filters(self, q, table_alias=""):
        where = []
        if q.gases:
            where.append(self._in("gas", q.gases))
        if q.sectors:
            where.append(self._in("sector_id" if q.geography_level == "national" else "module", q.sectors))
        if q.reporting_sectors:
            # every grain: the national facts, the ADM1 stream tables and the district tables
            # all carry the column since rc54
            where.append(self._in(REPORTING_SECTOR_KEY, q.reporting_sectors))
        if q.ipcc_codes and q.geography_level == "national":
            where.append("(" + " OR ".join("ipcc_code = '%s' OR ipcc_code LIKE '%s.%%'" % (c, c) for c in q.ipcc_codes) + ")")
        if q.categories and q.geography_level == "national":
            where.append(self._in("category", q.categories))
        if q.streams:
            where.append(self._in("component_id" if q.geography_level == "national" else "source_stream_id", q.streams))
        return where

    def _fetch(self, sql):
        cur = self.con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # --- query_emissions ------------------------------------------------------------------

    def query_emissions(self, request):
        q = self._validate(self._fill(request))
        if q.geography_level == "national":
            return self._national(q)
        return self._spatial(q)

    def _national(self, q):
        col = "co2e_Mt_%s" % q.gwp_basis
        if q.basis == "calendar":
            # the FAOSTAT-comparable calendar reconstruction; the reference year's own-basis
            # anchor rows (year_basis fiscal_census_anchor) are a comparison, not a series
            table, where = "fact_annual_calendar", [self._in("period_id", q.periods),
                                                   "year_basis = 'calendar_faostat'"]
            col = "co2e_Mt_AR5"
            if q.gwp_basis == "AR6":
                raise E.NotEstimated("the calendar reconstruction carries AR5 only", "calendar_basis_ne")
            if q.categories:
                where.append(self._in("category", q.categories))
            groups = [g for g in q.group_by if g in ("period_id", "category")]
        else:
            table = "fact_monthly" if q.months else "fact_annual"
            where = [self._in("period_id", q.periods), "geography_id = 'PK'"]
            if q.months:
                where.append(self._in("month", q.months))
            groups = list(q.group_by)
            where += self._filters(q)
        group_sql = ", ".join(groups) if groups else "'all'"
        # a derived key is SELECTed as its expression under the key's own alias and GROUPed by
        # that alias; a real column passes through unchanged
        select_cols = [ECONOMIC_SECTOR_SQL + " AS " + ECONOMIC_SECTOR_KEY if g == ECONOMIC_SECTOR_KEY else g for g in groups]
        group_cols = ", ".join(select_cols) + ", " if groups else ""
        formula = ""
        if table != "fact_annual_calendar":
            where.append("configuration_id = '%s'" % q.configuration_id)
        sql = ("SELECT %s SUM(CAST(%s AS %s)) AS exact, string_agg(result_row_id, ';' ORDER BY result_row_id) AS ids, COUNT(*) AS n "
               "FROM %s WHERE %s GROUP BY %s" % (group_cols, col, DECIMAL, table, " AND ".join(where), group_sql))
        formula = "SUM(%s) over native component rows for %s" % (col, q.configuration_id)
        rows = self._fetch(sql + self._order(q))
        decimals = self._decimals_for(q, groups)
        values = []
        for r in rows:
            label = {g: r[g] for g in groups}
            values.append(value(str(r["exact"]), "Mt CO2e %s" % q.gwp_basis, decimals,
                               row_ids=(r["ids"] or "").split(";") if r["ids"] else [],
                               formula=formula.replace("%d", str(r["n"])) if "%d" in formula else formula,
                               group=label, n_rows=r["n"]))
        if not values and not groups:
            values.append(value("0", "Mt CO2e %s" % q.gwp_basis, decimals, formula="no rows in scope"))
        prov = self._provenance([table])
        return envelope(self.release, "query_emissions", canonical_json(q), dataclasses.asdict(q),
                        values, {"kind": "sum", "sql": sql, "table": table, "column": col},
                        prov, uncertainty=self._uncertainty_for(q), completeness=self._completeness_for(q),
                        limitations_hit=self._limitations_for(q), defaults_applied=q.defaults_applied)

    def _spatial(self, q):
        if q.geography_level == "adm1":
            # Monthly provincial rows also supply AR6 annual sums.
            table, col, geo_col = "fact_adm1_month", "co2e_Mt_%s" % q.gwp_basis, "province"
        else:
            table = "fact_adm2_month" if q.months else "fact_adm2_year"
            col, geo_col = "co2e_Mt_AR5", "shape_id"
        where = ["configuration_id = '%s'" % q.configuration_id,
                 self._in("period_id", q.periods)]
        if q.months:
            where.append(self._in("month", q.months))
        if q.geography_ids:
            where.append(self._in(geo_col, q.geography_ids))
        if q.spatial_view != "all":
            where.append("spatial_view = '%s'" % q.spatial_view)
        where += self._filters(q)
        groups = list(q.group_by) or [geo_col]
        group_cols = ", ".join(groups)
        if table in ("fact_adm2_month", "fact_adm2_year"):
            sql = ("SELECT %s, SUM(CAST(co2e_Mt_AR5 AS %s)) AS exact_low, "
                   "SUM(CAST(emissions_Gg AS %s)) AS gg, string_agg(DISTINCT co2e_exactness, ';') AS exactness, COUNT(*) AS n, "
                   "string_agg(result_row_id, ';' ORDER BY result_row_id) AS ids FROM %s WHERE %s AND emissions_Gg <> '' GROUP BY %s"
                   % (group_cols, DECIMAL, DECIMAL, table, " AND ".join(where), group_cols))
        else:
            sql = ("SELECT %s, SUM(CAST(%s AS %s)) AS exact_low, SUM(CAST(emissions_Gg AS %s)) AS gg, "
                   "'exact' AS exactness, COUNT(*) AS n, string_agg(result_row_id, ';' ORDER BY result_row_id) AS ids "
                   "FROM %s WHERE %s AND %s <> '' GROUP BY %s"
                   % (group_cols, col, DECIMAL, DECIMAL, table, " AND ".join(where), col, group_cols))
        rows = self._fetch(sql + self._order(q, "exact_low"))
        decimals = self.decimals["co2e_Mt"].get(q.geography_level, 4)
        values = []
        for r in rows:
            label = {g: r[g] for g in groups}
            values.append(value(str(r["exact_low"]), "Mt CO2e %s" % q.gwp_basis, decimals,
                                row_ids=(r["ids"] or "").split(";"), formula="SUM(%s) over %d rows" % (col, r["n"]),
                                group=label, n_rows=r["n"], exactness=r["exactness"], gg=str(r["gg"])))
        unallocated, read_from = self._unallocated_for(q, table, col)
        tables = [table] + [t for t in ("fact_unallocated", read_from) if t != table]
        return envelope(self.release, "query_emissions", canonical_json(q), dataclasses.asdict(q),
                        values, {"kind": "sum", "sql": sql, "table": table, "column": col},
                        self._provenance(list(dict.fromkeys(tables))), unallocated=unallocated,
                        uncertainty=self._uncertainty_for(q), limitations_hit=self._limitations_for(q),
                        defaults_applied=q.defaults_applied)

    @staticmethod
    def _disp(exact, decimals):
        from pakemis_query.envelope import display
        return display(exact, decimals)

    # --- query_air (native pollutant masses) ---------------------------------------------------------

    AIR_GROUPS = ("pollutant", "sector_id", "category", "subitem", "province", "shape_id", "year", "period_id")
    AIR_SECTORS = ("agriculture", "aviation", "fugitives", "industry", "ippu", "power", "railways", "residential", "transport", "waste")

    def query_air(self, request):
        """Native kt of a named species from the PakEmis-Air tables; never CO2e, and never a
        sum across pollutants (the particulate strata contain one another).

        ONE PRODUCT, TWO TIME BASES. `periods` (fiscal, FY2015-16..FY2024-25) answers from the
        covered-sources family - the national panel and its province and district marginals -
        in which a source that is only SCREENED travels beside the values in `completeness`,
        never inside them. `years` (calendar, 1990..2024) answers from the agriculture series,
        national. A request that names neither is answered for the release's reference period,
        and says so in `defaults_applied`, exactly as query_emissions does.

        It did not always. Until this default the function ROUTED on whether `periods` was
        present: without it the answer came from the pre-rc48 single-year layers
        (fact_air_annual, fact_air_adm1, fact_air_adm2), in which grid power's UNCONTROLLED
        SCREENING BOUND is an ordinary row - 85 % of a "national SO2 total" that this module's
        own completeness rule forbids summing. Nothing in the envelope said which product had
        answered (`context.periods` was simply empty), so one omitted field changed the
        inventory a caller was reading, silently. A public explorer served that as a sector
        breakdown for a month. The single-year layers are still tables of the release; they
        are no longer something a query can fall into."""
        q = request
        applied = []
        if not q.geography_level:
            q = dataclasses.replace(q, geography_level="national"); applied.append("geography_level")
        if not q.periods and not q.years:
            if "year" in q.group_by:
                # a trend is not defaulted to one year: the caller is asked which years
                raise E.GrainUnavailable("a year grouping needs the calendar series: name the "
                                         "years (1990..2024)", "air_history_national_only")
            if "period_id" not in q.group_by:          # that one is refused below, by name
                q = dataclasses.replace(q, periods=(self.release.defaults["period_id"],)); applied.append("periods")
        q = dataclasses.replace(q, defaults_applied=tuple(applied))
        pollutants = {r["pollutant"] for r in self.release.dim("dim_pollutant")}
        for pl in q.pollutants:
            if pl not in pollutants:
                raise E.UnknownDimensionValue("%r is not a pollutant of the integrated air panel (%s)"
                                              % (pl, ", ".join(sorted(pollutants))), dimension="pollutant", value=pl)
        for sec in q.sectors:
            if sec not in self.AIR_SECTORS:
                raise E.NotEstimated("the air tables carry no %s layer (%s)"
                                     % (sec, ", ".join(self.AIR_SECTORS)), "air_sector_ne")
        if q.geography_level not in GEOGRAPHY_LEVELS:
            raise E.UnknownDimensionValue("%r is not a geography level" % q.geography_level, dimension="geography_level")
        bad = [g for g in q.group_by if g not in self.AIR_GROUPS]
        if bad:
            raise E.GrainUnavailable("%r is not a grouping of the air tables (%s)"
                                     % (bad[0], ", ".join(self.AIR_GROUPS)), "grain_unavailable")
        if "pollutant" not in q.group_by and len(q.pollutants) != 1:
            raise E.GrainUnavailable(
                "a sum across pollutants is meaningless (BC is inside PM2.5, PM2.5 inside "
                "PM10); name exactly one pollutant or group by pollutant", "pollutants_not_additive")
        if q.geography_level != "national":
            if q.years:
                raise E.GrainUnavailable("the calendar-year air series (1990..2024, agriculture) "
                                         "is national only; provinces and districts carry the "
                                         "fiscal periods", "air_history_national_only")
            # derived, never declared: the sectors the table the request will hit actually
            # holds, read from it. The refusal names them the same way, so it cannot go on
            # listing as absent a sector that has since arrived - which the hand-written
            # list here did for industry, IPPU and fugitives after all three had.
            table_probe = "fact_air_adm1_year" if q.geography_level == "adm1" else "fact_air_adm2_year"
            have = {r["sector_id"] for r in self._fetch("SELECT DISTINCT sector_id FROM %s" % table_probe)}
            missing = [sec for sec in q.sectors if sec not in have]
            if missing:
                raise E.GrainUnavailable(
                    "%r has no %s air layer in this release (the layer holds %s)"
                    % (missing[0], "provincial" if q.geography_level == "adm1" else "district",
                       ", ".join(sorted(have))),
                    "air_spatial_not_in_layer")
        if q.years and q.periods:
            raise E.GrainUnavailable("years (the calendar agriculture series) and periods "
                                     "(the fiscal covered panel) are two time bases; ask "
                                     "for one", "air_two_time_bases")
        if "period_id" in q.group_by and not q.periods:
            raise E.GrainUnavailable("a period_id grouping needs the covered panel: name "
                                     "the fiscal periods (FY2015-16..FY2024-25)",
                                     "air_panel_national_only")
        # table choice
        if q.years:
            table, geo_col = "fact_air_timeseries", ""
            base = [self._in("year", q.years)]
            allowed = ("year", "pollutant", "category")
            bad = [g for g in q.group_by if g not in allowed]
            if bad:
                raise E.GrainUnavailable("%r is not a grouping of the air timeseries (%s); the "
                                         "series is agriculture, national" % (bad[0], ", ".join(allowed)),
                                         "air_history_national_only")
            # the source's own TOTAL rows are its sums; a category grouping must not add them in
            base.append("category <> 'TOTAL'" if ("category" in q.group_by or q.categories) else "category = 'TOTAL'")
        elif q.periods and q.geography_level in ("adm1", "adm2"):
            # the ten-year spatial family (rc49): the same one allocation the panel,
            # the grid and both ADM tables are marginals of. Two configurations, like
            # the panel and for the same reason - an unfiltered sum adds them.
            cfg = configurations.canonical(q.configuration_id or configurations.REFERENCE)
            if cfg not in configurations.AIR_ALL:
                raise E.UnknownDimensionValue(
                    "%r is not a configuration of the air panel (S_TAN, "
                    "L_TAN, S_IPCC, L_IPCC)" % cfg, dimension="configuration_id", value=cfg)
            if not q.configuration_id:
                applied.append("configuration_id")
            q = dataclasses.replace(q, configuration_id=cfg,
                                    defaults_applied=tuple(applied))
            if q.geography_level == "adm1":
                table, geo_col = "fact_air_adm1_year", "province"
                allowed = ("period_id", "pollutant", "sector_id", "province")
            else:
                table, geo_col = "fact_air_adm2_year", "shape_id"
                allowed = ("period_id", "pollutant", "sector_id", "province", "shape_id")
            bad = [g for g in q.group_by if g not in allowed]
            if bad:
                raise E.GrainUnavailable(
                    "%r is not a grouping of the ten-year spatial air family (%s); "
                    "category and subitem live at the national grains"
                    % (bad[0], ", ".join(allowed)), "grain_unavailable")
            if q.categories:
                raise E.GrainUnavailable(
                    "the ten-year spatial air family carries sector grain, not "
                    "categories; filter by sector or ask the national panel",
                    "grain_unavailable")
            base = [self._in("period_id", q.periods),
                    "configuration_id = '%s'" % cfg]
            if q.sectors:
                base.append(self._in("sector_id", q.sectors))
        else:
            # every request that reaches here names periods: its own, or the default above
            table, geo_col = "fact_air_panel", ""
            # The panel carries four structural configurations; an unfiltered sum
            # would add incompatible alternatives.
            cfg = configurations.canonical(q.configuration_id or configurations.REFERENCE)
            if cfg not in configurations.AIR_ALL:
                raise E.UnknownDimensionValue(
                    "%r is not a configuration of the air panel (S_TAN, "
                    "L_TAN, S_IPCC, L_IPCC)" % cfg, dimension="configuration_id", value=cfg)
            if not q.configuration_id:
                applied.append("configuration_id")
            q = dataclasses.replace(q, configuration_id=cfg,
                                    defaults_applied=tuple(applied))
            base = [self._in("period_id", q.periods),
                    "configuration_id = '%s'" % cfg]
            allowed = ("period_id", "pollutant", "sector_id", "category")
            bad = [g for g in q.group_by if g not in allowed]
            if bad:
                raise E.GrainUnavailable("%r is not a grouping of the covered panel (%s); "
                                         "the panel's grain is period x sector x category "
                                         "x species" % (bad[0], ", ".join(allowed)),
                                         "grain_unavailable")
            if q.sectors:
                base.append(self._in("sector_id", q.sectors))
        if q.pollutants:
            base.append(self._in("pollutant", q.pollutants))
        if q.periods:
            available = {row["period_id"] for row in self._fetch(
                "SELECT DISTINCT period_id FROM %s" % table)}
            unknown = set(q.periods) - available
            if unknown:
                raise E.UnknownDimensionValue(
                    "Air period %r is outside this product's supported fiscal core; "
                    "provisional source extensions do not form a national total" % sorted(unknown)[0],
                    dimension="period_id", value=sorted(unknown)[0])
        if q.categories:
            base.append(self._in("category", q.categories))
        if q.geography_ids and geo_col:
            base.append(self._in(geo_col, q.geography_ids))
        groups = list(q.group_by) or ([geo_col] if geo_col else ["pollutant"])
        if geo_col and geo_col not in groups and "pollutant" not in groups and len(q.pollutants) != 1:
            groups.append("pollutant")
        group_cols = ", ".join(groups) + ", " if groups else ""
        where = " AND ".join(base) if base else "1=1"
        sql = ("SELECT %sSUM(CAST(emissions_kt AS %s)) AS exact, string_agg(result_row_id, ';' ORDER BY result_row_id) AS ids, "
               "COUNT(*) AS n FROM %s WHERE %s GROUP BY %s"
               % (group_cols, DECIMAL, table, where, ", ".join(groups) if groups else "'all'"))
        rows = self._fetch(sql + self._order(q))
        values = []
        for r in rows:
            label = {g: r[g] for g in groups}
            species = label.get("pollutant") or (q.pollutants[0] if len(q.pollutants) == 1 else "")
            values.append(value(str(r["exact"]), ("kt %s" % species).strip(), 3,
                               row_ids=(r["ids"] or "").split(";") if r["ids"] else [],
                               formula="SUM(emissions_kt) over %d %s rows" % (r["n"], table),
                               group=label, n_rows=r["n"]))
        prov = self._provenance([table])
        limitations = ["air_beta", "lulucf_excluded"]
        if table in ("fact_air_panel", "fact_air_adm1_year", "fact_air_adm2_year"):
            limitations.append("air_covered_sources")
        if q.geography_level != "national" or not q.sectors:
            limitations.append("air_sector_ne")
        # THE ABSENCE-SCREENING BLOCK (the completeness-mass rule applied to air):
        # a fiscal-period answer carries what the panel's typed absences plausibly
        # hold - power's controlled..uncontrolled scenario pair and industry's
        # uncontrolled end - BESIDE the values, never inside them. The headline sum
        # is byte-unchanged by these rows; summing a covered total with a scenario
        # end would produce a number that is neither an estimate nor a bound.
        completeness = []
        if q.periods and table in ("fact_air_panel", "fact_air_adm1_year",
                                   "fact_air_adm2_year"):
            where_abs = [self._in("period_id", q.periods)]
            if q.pollutants:
                where_abs.append(self._in("pollutant", q.pollutants))
            completeness = self._fetch(
                "SELECT period_id, sector_id, pollutant, scenario_controlled_kt, "
                "scenario_uncontrolled_kt, controlled_absence_reason, factor_basis, "
                "gap_id FROM fact_air_absence_screening WHERE %s "
                "ORDER BY period_id, sector_id, pollutant"
                % " AND ".join(where_abs))
        return envelope(self.release, "query_air", canonical_json(q), dataclasses.asdict(q),
                        values, {"kind": "sum", "sql": sql, "table": table, "column": "emissions_kt"},
                        prov, completeness=completeness, limitations_hit=limitations,
                        defaults_applied=q.defaults_applied)

    def _order(self, q, column="exact"):
        sql = ""
        if q.order_by:
            direction = "DESC" if q.order_by.lower().endswith("desc") else "ASC"
            sql += " ORDER BY %s %s" % (column, direction)
        if q.limit:
            sql += " LIMIT %d" % q.limit
        return sql

    def _decimals_for(self, q, groups):
        d = self.decimals["co2e_Mt"]
        if not groups:
            return d["national_total"] if not (q.sectors or q.ipcc_codes or q.categories or q.streams) else d["sector"]
        if "component_id" in groups or "source_stream_id" in groups:
            return d["stream"]
        if "category" in groups or "ipcc_code" in groups:
            return d["category"]
        return d["sector"]

    # --- the blocks every answer carries ----------------------------------------------------

    def _provenance(self, tables):
        r = self.release
        products = [{"table": t, "path": r.tables[t]["path"], "sha256": r.tables[t]["sha256_csv"]} for t in tables]
        return {"tables": products, "release_manifest": r.contract["release"]["release_manifest"],
                "derived_from": r.tables[tables[0]]["derived_from"][:6]}

    # fact_uncertainty is keyed on (category, module, resolution) and NOTHING ELSE. It carries the
    # reference period and the reference configuration only, and it has no gas column. Every axis a
    # caller can filter on that this table does not carry is therefore a REFUSAL: returning the
    # category envelope for a request about one gas, one other year, one other configuration or one
    # stream would answer a question the release has not answered, in a block that looks the same
    # as a real one. Each refusal names the axis that is missing, because an empty block with no
    # reason reads as a lookup miss - which is exactly how the resolution defect below survived.
    RESOLUTIONS = {("national", False): "annual_national", ("national", True): "monthly_national",
                   ("adm2", False): "annual_adm2", ("adm2", True): "monthly_adm2"}

    def _uncertainty_for(self, q):
        def none(reason):
            return {"rows": [], "resolution": None, "interpretation": reason}

        if q.spatial_view != "all":
            return none("uncertainty is published for the complete source boundary only; "
                        "no interval is available for the %s spatial view" % q.spatial_view)

        # THE RESOLUTION DEFECT. This selected `resolution = 'annual'` for a national request and
        # the bare geography level otherwise, producing 'annual', 'adm1' or 'adm2'. The vocabulary
        # is annual_national / monthly_national / annual_adm2 / monthly_adm2, so NONE of the three
        # ever matched and every envelope this engine has ever produced carried an empty block.
        # Nothing failed, because nothing asserted that a row ever came back.
        if (q.geography_level == "national" and not q.months and not q.categories
                and not q.streams and not q.ipcc_codes and not q.gases and not q.reporting_sectors
                and "fact_ghg_conditional" in self.release.tables):
            sector = q.sectors[0] if len(q.sectors) == 1 else "national_covered"
            if len(q.sectors) <= 1:
                where = [self._in("period_id", q.periods),
                         "configuration_id = '%s'" % q.configuration_id,
                         "sector_id = '%s'" % sector,
                         "species_or_metric = 'CO2e_%s'" % q.gwp_basis]
                rows = self._fetch("SELECT * FROM fact_ghg_conditional WHERE " + " AND ".join(where))
                return {"available": bool(rows), "kind": "conditional_parameter_percentiles",
                        "table": "fact_ghg_conditional", "rows": rows,
                        "note": "Separate temporal dependence cases; missing sources and structural alternatives excluded; intervals are not additive."}
        resolution = self.RESOLUTIONS.get((q.geography_level, bool(q.months)))
        if q.geography_level == "adm1":
            return none("the release publishes no provincial uncertainty: fact_uncertainty carries "
                        "annual_adm2 and monthly_adm2, and no adm1 resolution at any grain")
        if resolution is None:
            return none("no uncertainty resolution exists for geography level %r" % q.geography_level)
        if q.gases:
            return none("this GWP-contribution query has no matched per-gas uncertainty: "
                        "fact_uncertainty has no gas column and covers all gases in each category; "
                        "native-gas conditional intervals are published separately")
        if q.configuration_id and q.configuration_id != self.release.defaults.get("configuration_id"):
            return none("these category/allocation envelopes are published for the reference "
                        "configuration only; no matched envelope is available for %s; its "
                        "annual conditional intervals are published separately" % q.configuration_id)
        reference = self.release.defaults.get("period_id")
        if reference and set(q.periods or ()) - {reference}:
            return none("per-category uncertainty is published for %s only; for another period the "
                        "release carries an interval on the national covered total alone, in "
                        "fact_uncertainty_series" % reference)
        if q.streams:
            return none("the finest grain the release publishes an interval at is the category; "
                        "there is no per-stream uncertainty")

        # narrow to what was asked for. A category-scoped request that came back with all 23
        # categories would make the reader find their own row, and the Explorer's sidecar used to
        # do this filtering for itself precisely because this block was empty - so leaving it out
        # here would have made the fixed block LESS useful than the workaround it replaced.
        where = ["resolution = '%s'" % resolution]
        if q.categories:
            where.append(self._in("category", q.categories))
        if q.sectors:
            where.append(self._in("module", q.sectors))
        rows = self._fetch("SELECT category, module, resolution, envelope_low_pct, envelope_high_pct, envelope_kind, aggregation_rule "
                           "FROM fact_uncertainty WHERE " + " AND ".join(where))
        return {"rows": rows[:40], "resolution": resolution,
                "interpretation": "per-category envelopes (structural, no probability) at resolution "
                "%s; they are NEVER combined in quadrature across categories - see aggregation_rule"
                % resolution}

    def _completeness_for(self, q):
        where = []
        if q.ipcc_codes:
            where.append("(" + " OR ".join("code = '%s' OR code LIKE '%s.%%'" % (c, c) for c in q.ipcc_codes) + ")")
        sql = "SELECT code, category, gas, notation_key, gap_id FROM fact_completeness WHERE notation_key <> 'E'"
        if where:
            sql += " AND " + " AND ".join(where)
        return self._fetch(sql)

    def _unallocated_for(self, q, table, column):
        """Return ADM1 mass placed no finer for the requested period, configuration,
        gas, spatial view and source scope. The all-year, all-configuration
        ``fact_unallocated`` table supplies AR5. For AR6, the same retained stream
        identities select the corresponding ``fact_adm1_month`` masses. These rows
        are part of the province total and close the ADM1-to-ADM2 allocation.
        Return both the scoped block and the table from which it was read."""
        cfg = "configuration_id = '%s'" % q.configuration_id
        source, col = "fact_unallocated", "co2e_Mt_AR5"
        where = [cfg, self._in("period_id", q.periods)]
        if q.months:
            where.append(self._in("month", q.months))
        if q.gwp_basis == "AR6":
            # Preserve the requested GWP basis using the same retained streams.
            source, col = "fact_adm1_month", "co2e_Mt_AR6"
            where.append("source_stream_id IN (SELECT DISTINCT source_stream_id FROM fact_unallocated WHERE " +
                         cfg + " AND " + self._in("period_id", q.periods) + ")")
        if q.geography_level == "adm1" and q.geography_ids:
            where.append(self._in("province", q.geography_ids))
        if q.spatial_view != "all":
            where.append("spatial_view = '%s'" % q.spatial_view)
        where += self._filters(q)
        rows = self._fetch("SELECT province, SUM(CAST(%s AS %s)) AS exact, COUNT(*) AS n FROM %s WHERE %s AND %s <> '' "
                           "GROUP BY province ORDER BY province" % (col, DECIMAL, source, " AND ".join(where), col))
        block = {"level": "adm1", "by_province": [{"province": r["province"], "exact": str(r["exact"]), "n_rows": r["n"]} for r in rows],
                 "periods": list(q.periods), "table": source,
                 "note": "mass retained at ADM1 and placed no finer; part of every closure below it"}
        return block, source

    def _limitations_for(self, q):
        hit = ["lulucf_excluded"]
        if ECONOMIC_SECTOR_KEY in q.group_by:
            hit.append("economic_sector_view")
        if REPORTING_SECTOR_KEY in q.group_by or q.reporting_sectors or ECONOMIC_SECTOR_KEY in q.group_by:
            # the economic view is an expression over the reporting axis, so it inherits
            # the axis's limitation beside its own
            hit.append("reporting_sector_view")
        if q.geography_level == "adm2":
            hit += ["ar6_adm2_ne", "no_polygon_units"]
        if q.basis == "calendar":
            hit.append("calendar_basis_ne")
        return hit
