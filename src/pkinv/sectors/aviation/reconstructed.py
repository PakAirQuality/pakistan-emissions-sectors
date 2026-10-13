"""Officially constrained annual-route fallback for FY2023-24.

The adapter emits weighted annual strata, never synthetic dated flights.  Route and
airline controls are solved jointly so that adding evidence cannot allocate the same
route capacity to several operators.  Unsupported activity remains Tier D.
"""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import input_exists as _input_exists
from collections import defaultdict
from dataclasses import replace
from datetime import date
import csv
import hashlib
import math
import os

import numpy as np
from scipy.optimize import linprog

from pkinv.paths import DATA
from pkinv.sectors.aviation import coverage, ledger
from pkinv.activity.store import read_rows

ACTIVITY = asset_path(DATA, "activity", "aviation")
RESIDENT = {"PIA", "ABQ", "FJL", "SEP", "SIF"}


def _rows(name):
    return read_rows(asset_path(ACTIVITY, name), comments=False)


def _distance_km(a, b):
    lat1, lat2 = math.radians(float(a["latitude_deg"])), math.radians(float(b["latitude_deg"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(b["longitude_deg"]) - float(a["longitude_deg"]))
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(value)))


def _active_weight(row):
    start, end = date.fromisoformat(row["active_from"]), date.fromisoformat(row["active_to"])
    frequency = float(row.get("weekly_frequency_central") or row.get("weekly_frequency") or 1)
    return frequency * ((end - start).days + 1) / 7.0


def _boundary(row):
    return row.get("boundary") or ledger.boundary(row["origin_icao"], row["destination_icao"])


def _joint_allocate(routes, airline_targets, supported, priors):
    """Maximum-coverage transportation LP over supported airline-route cells.

    Route and airline controls are upper bounds.  Tiny inverse-prior costs make the
    result deterministic and prefer better-supported cells without compromising the
    primary objective of maximum documented coverage.
    """
    route_map = {(s.origin_icao, s.destination_icao): s for s in routes}
    cells = sorted((airline, pair) for airline in airline_targets for pair in route_map
                   if pair in supported.get(airline, set()))
    if not cells:
        return {}, dict(airline_targets), {p: s.activity_count for p, s in route_map.items()}
    # Entropy-like balancing first spreads each airline over its documented network.
    # This avoids the arbitrary corner solutions of a bare transportation LP.
    values = {}
    for airline, target in airline_targets.items():
        eligible = [p for a, p in cells if a == airline]
        total_prior = sum(max(priors.get((airline, p), 0.0), 1e-9) for p in eligible)
        for pair in eligible:
            values[(airline, pair)] = (float(target) *
                max(priors.get((airline, pair), 0.0), 1e-9) / total_prior)
    for _ in range(1000):
        previous = dict(values)
        for pair, stage in route_map.items():
            keys = [(a, p) for a, p in cells if p == pair]
            total = sum(values[k] for k in keys)
            if total > stage.activity_count and total:
                factor = stage.activity_count / total
                for key in keys:
                    values[key] *= factor
        for airline, target in airline_targets.items():
            keys = [(a, p) for a, p in cells if a == airline]
            total = sum(values[k] for k in keys)
            capacities = sum(route_map[p].activity_count for _, p in keys)
            desired = min(float(target), capacities)
            if total and total < desired:
                factor = desired / total
                for key in keys:
                    values[key] *= factor
        if max((abs(values[k] - previous[k]) for k in values), default=0) < 1e-8:
            break
    # A residual LP fills any remaining feasible capacity without altering the
    # evidence-balanced base allocation.
    airline_used0 = {a: sum(v for (aa, _), v in values.items() if aa == a)
                     for a in airline_targets}
    route_used0 = {p: sum(v for (_, pp), v in values.items() if pp == p)
                   for p in route_map}
    constraints, bounds = [], []
    for airline, target in sorted(airline_targets.items()):
        constraints.append([1.0 if a == airline else 0.0 for a, _ in cells])
        bounds.append(max(0.0, float(target) - airline_used0[airline]))
    for pair, stage in sorted(route_map.items()):
        constraints.append([1.0 if p == pair else 0.0 for _, p in cells])
        bounds.append(max(0.0, stage.activity_count - route_used0[pair]))
    result = linprog(-np.ones(len(cells)), A_ub=np.asarray(constraints),
                     b_ub=np.asarray(bounds), bounds=(0, None), method="highs")
    if not result.success:
        raise RuntimeError("joint route-airline residual allocation failed: %s" % result.message)
    allocated = {cell: values.get(cell, 0.0) + float(value)
                 for cell, value in zip(cells, result.x)
                 if values.get(cell, 0.0) + float(value) > 1e-7}
    airline_used = defaultdict(float)
    route_used = defaultdict(float)
    for (airline, pair), value in allocated.items():
        airline_used[airline] += value
        route_used[pair] += value
    airline_residual = {a: max(0.0, float(v) - airline_used[a])
                        for a, v in airline_targets.items()}
    route_residual = {p: max(0.0, s.activity_count - route_used[p])
                      for p, s in route_map.items()}
    return allocated, airline_residual, route_residual


class PCAAReconstructedSource:
    name = "PCAAReconstructedSource"

    def __init__(self, fiscal_year=2023):
        self.fiscal_year = fiscal_year
        if fiscal_year != 2023:
            raise ValueError("the documented fallback currently covers FY2023-24 only")

    def controls(self):
        return _rows("airport_controls_2023_24.csv"), _rows("airline_controls_2023_24.csv")

    def evidence(self, boundary_name=None):
        rows = _rows("route_evidence_2023_24.csv")
        return [r for r in rows if boundary_name is None or _boundary(r) == boundary_name]

    def route_weights(self):
        weights = defaultdict(float)
        for row in self.evidence("domestic"):
            pair = (row["origin_icao"], row["destination_icao"])
            weights[pair] += _active_weight(row)
            direction = row.get("directionality", "bidirectional")
            if direction == "bidirectional":
                weights[(pair[1], pair[0])] += _active_weight(row)
        return dict(weights)

    def _airports(self):
        rows = _rows("airports.csv")
        foreign_path = asset_path(ACTIVITY, "international_airports.csv")
        if _input_exists(foreign_path):
            rows.extend(_rows("international_airports.csv"))
        return {row["airport_icao"]: row for row in rows}

    def _enrich(self, stages):
        airports, enriched = self._airports(), []
        for stage in stages:
            origin, destination = airports.get(stage.origin_icao), airports.get(stage.destination_icao)
            if origin and destination and origin["latitude_deg"] and destination["latitude_deg"]:
                stage = replace(stage, great_circle_nm=_distance_km(origin, destination) / 1.852)
            enriched.append(stage.validate())
        return enriched

    def route_ledger(self):
        airport_rows, _ = self.controls()
        controls = {r["airport_icao"]: float(r["domestic_commercial_movements"])
                    for r in airport_rows}
        routes, residual = coverage.reconstruct([], controls, self.route_weights(), self.fiscal_year)
        return self._enrich(routes), coverage.residual_records(residual, self.fiscal_year)

    def _shares(self, airline, pair, boundary_name):
        rows = _rows("aircraft_family_shares_2023_24.csv")
        exact = [r for r in rows if r["airline_icao"] == airline and
                 (r["origin_icao"], r["destination_icao"]) == pair]
        generic = [r for r in rows if r["airline_icao"] == airline and
                   r["origin_icao"] in ("*", boundary_name) and
                   r["destination_icao"] in ("*", boundary_name)]
        selected = exact or generic
        if not selected:
            return [("unknown", 1.0, "UNRESOLVED")]
        total = sum(float(r["share"]) for r in selected)
        if total > 1.000001:
            raise ValueError("aircraft shares exceed one for %s %s" % (airline, pair))
        result = [(r["aircraft_type"], float(r["share"]), r["source_reference"])
                  for r in selected]
        if total < 0.999999:
            result.append(("unknown", 1.0 - total, "UNRESOLVED"))
        return result

    def _supported(self, boundary_name):
        supported, priors = defaultdict(set), defaultdict(float)
        for row in self.evidence(boundary_name):
            airline = row["airline_icao"]
            pair = (row["origin_icao"], row["destination_icao"])
            supported[airline].add(pair)
            priors[(airline, pair)] += _active_weight(row)
            if boundary_name == "domestic" and row.get("directionality", "bidirectional") == "bidirectional":
                reverse = pair[::-1]
                supported[airline].add(reverse)
                priors[(airline, reverse)] += _active_weight(row)
        return supported, priors

    def _assign(self, route_stages, boundary_name, targets):
        supported, priors = self._supported(boundary_name)
        allocation, airline_gap, route_gap = _joint_allocate(
            route_stages, targets, supported, priors)
        route_map = {(s.origin_icao, s.destination_icao): s for s in route_stages}
        assigned = []
        for (airline, pair), count in sorted(allocation.items()):
            stage = route_map[pair]
            for aircraft, share, reference in self._shares(airline, pair, boundary_name):
                if count * share <= 1e-7:
                    continue
                payload = "%d|%s|%s|%s|%s" % (self.fiscal_year, boundary_name, airline, pair, aircraft)
                assigned.append(replace(
                    stage, flight_id="alloc-" + hashlib.sha256(payload.encode()).hexdigest()[:18],
                    operator=airline, operator_residence="Pakistan",
                    aircraft_type="" if aircraft == "unknown" else aircraft,
                    activity_count=count * share, source_reference=reference,
                    imputation_method="joint_control_supported_route_allocation").validate())
        residual = []
        for airline, missing in sorted(airline_gap.items()):
            if missing > 1e-7:
                residual.append(ledger.FlightStage(
                    flight_id="operator-residual-%d-%s-%s" % (self.fiscal_year, boundary_name, airline),
                    fiscal_year=self.fiscal_year, boundary=boundary_name, operator=airline,
                    operator_residence="Pakistan", record_granularity="aggregate_residual",
                    activity_count=missing, source_tier="D", source="PCAA airline control",
                    source_reference="airline_controls_2023_24.csv",
                    imputation_method="UNALLOCATED_OPERATOR_DEPARTURES").validate())
        return assigned, residual, route_gap

    def aircraft_ledger(self, route_stages):
        _, airlines = self.controls()
        targets = {r["airline_icao"]: float(r["departures"]) for r in airlines
                   if r["traffic_scope"] == "domestic" and r["airline_icao"] in RESIDENT}
        assigned, residual, _ = self._assign(route_stages, "domestic", targets)
        return assigned, residual

    def international_route_ledger(self):
        """Outbound Pakistan stages for resident carriers, constrained by departures."""
        _, airlines = self.controls()
        targets = {r["airline_icao"]: float(r["departures"]) for r in airlines
                   if r["traffic_scope"] == "international" and r["airline_icao"] in RESIDENT}
        rows = self.evidence("international")
        priors = defaultdict(float)
        for row in rows:
            priors[(row["origin_icao"], row["destination_icao"])] += _active_weight(row)
        stages = []
        for pair, count in sorted(priors.items()):
            payload = "%d|international|%s|%s" % (self.fiscal_year, *pair)
            stages.append(ledger.FlightStage(
                flight_id="intl-recon-" + hashlib.sha256(payload.encode()).hexdigest()[:18],
                fiscal_year=self.fiscal_year, origin_icao=pair[0], destination_icao=pair[1],
                boundary="international", period_start="2023-07-01", period_end="2024-06-30",
                record_granularity="annual_route", activity_count=count, source_tier="C",
                trajectory_quality="modelled", source="documented resident international network",
                source_reference="route_evidence_2023_24.csv",
                imputation_method="schedule_frequency_prior").validate())
        stages = self._enrich(stages)
        assigned, residual, _ = self._assign(stages, "international", targets)
        return assigned, residual
