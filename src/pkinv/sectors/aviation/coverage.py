"""Coverage measurement and controlled reconstruction against PCAA movements."""
from collections import Counter, defaultdict
import hashlib

from pkinv.sectors.aviation import ledger


def official_controls(data, year=None):
    """Airport domestic endpoint movements published by PCAA."""
    year = data.year if year is None else year
    return {row["icao"]: int(row["com_dom_mv"]) for row in data.movements_for(year)}


def endpoint_movements(stages, boundary_name="domestic"):
    counts = Counter()
    for stage in stages:
        if stage.boundary != boundary_name:
            continue
        if stage.origin_icao:
            counts[stage.origin_icao] += stage.activity_count
        if stage.destination_icao:
            counts[stage.destination_icao] += stage.activity_count
    return counts


def report(stages, controls):
    observed = endpoint_movements(stages)
    rows = []
    for airport in sorted(set(controls) | set(observed)):
        target, got = float(controls.get(airport, 0)), float(observed.get(airport, 0))
        rows.append({"airport_icao": airport, "pcaa_movements": target,
                     "allocated_movements": got, "missing_movements": max(0, target - got),
                     "excess_movements": max(0, got - target),
                     "coverage_ratio": got / target if target else "",
                     "coverage_flag": ("no_control" if not target else "excess" if got > target
                                       else "weak" if got / target < 0.8 else "partial"
                                       if got < target else "complete")})
    return rows


def route_weights(stages):
    weights = Counter()
    for stage in stages:
        if stage.boundary == "domestic" and stage.origin_icao and stage.destination_icao:
            weights[(stage.origin_icao, stage.destination_icao)] += stage.activity_count
    return weights


def _ipf(weights, row_targets, column_targets, iterations=500, tolerance=1e-8):
    """Fit a supported directed graph to marginals without creating new edges."""
    matrix = {pair: float(value) for pair, value in weights.items() if value > 0}
    for _ in range(iterations):
        previous = dict(matrix)
        for origin, target in row_targets.items():
            keys = [key for key in matrix if key[0] == origin]
            total = sum(matrix[key] for key in keys)
            if total:
                scale = target / total
                for key in keys:
                    matrix[key] *= scale
        for destination, target in column_targets.items():
            keys = [key for key in matrix if key[1] == destination]
            total = sum(matrix[key] for key in keys)
            if total:
                scale = target / total
                for key in keys:
                    matrix[key] *= scale
        if max((abs(matrix[key] - previous[key]) for key in matrix), default=0) < tolerance:
            break
    return matrix


def reconstruct(stages, controls, schedule_weights=None, year=2023):
    """Add weighted annual Tier-C route strata; never fabricate flight timestamps."""
    stages = list(stages)
    current = endpoint_movements(stages)
    endpoint_deficit = {a: max(0.0, float(target) - current[a])
                        for a, target in controls.items()}
    # PCAA publishes endpoint movements, not airport departures and arrivals.  Split
    # only the unresolved endpoint deficit equally; do not add traffic merely to make
    # already complete observed directions symmetric.
    row_targets = {a: value / 2.0 for a, value in endpoint_deficit.items()}
    col_targets = dict(row_targets)
    weights = route_weights(stages)
    for pair, value in (schedule_weights or {}).items():
        if pair[0] != pair[1] and value > 0:
            weights[pair] += float(value)
    # Timetables establish a route pair.  Permit its reciprocal direction, but no
    # connection between an otherwise unsupported airport pair.
    for (origin, destination), value in list(weights.items()):
        weights.setdefault((destination, origin), value)
    fitted = _ipf(weights, row_targets, col_targets)
    added = []
    for (origin, destination), count in sorted(fitted.items()):
        if count <= 1e-7:
            continue
        payload = "FY%d|%s|%s" % (year, origin, destination)
        fid = "recon-" + hashlib.sha256(payload.encode()).hexdigest()[:18]
        added.append(ledger.FlightStage(
            flight_id=fid, fiscal_year=year, origin_icao=origin,
            destination_icao=destination, boundary="domestic",
            period_start="%d-07-01" % year, period_end="%d-06-30" % (year + 1),
            record_granularity="annual_route", activity_count=count, source_tier="C",
            trajectory_quality="modelled", trajectory_available=False,
            source="PCAA movement-constrained route reconstruction",
            source_reference="route_evidence_%d_%02d.csv" % (year, (year + 1) % 100),
            imputation_method="IPF_supported_route_graph"))
    completed = ledger.validate_records(stages + added)
    got = endpoint_movements(completed)
    residual = {airport: max(0.0, float(target) - got.get(airport, 0.0))
                for airport, target in controls.items()
                if max(0.0, float(target) - got.get(airport, 0.0)) > 1e-6}
    return completed, residual


def residual_records(residual, year=2023):
    """Represent unresolved endpoint controls explicitly without assigning a route."""
    records = []
    for airport, movements in sorted(residual.items()):
        records.append(ledger.FlightStage(
            flight_id="residual-%d-%s" % (year, airport), fiscal_year=year,
            boundary="domestic", record_granularity="aggregate_residual",
            activity_count=float(movements), source_tier="D",
            source="PCAA airport control", source_reference=airport,
            imputation_method="UNALLOCATED_ENDPOINT_MOVEMENTS"))
    return records


def tier_summary(stages):
    counts, fuel = Counter(), defaultdict(float)
    for stage in stages:
        counts[stage.source_tier] += stage.activity_count
        fuel[stage.source_tier] += stage.total_fuel_kg * stage.activity_count
    total_n, total_fuel = sum(counts.values()), sum(fuel.values())
    return [{"source_tier": tier, "flight_stages": counts[tier],
             "stage_share": counts[tier] / total_n if total_n else 0.0,
             "fuel_t": fuel[tier] / 1000.0,
             "fuel_share": fuel[tier] / total_fuel if total_fuel else 0.0}
            for tier in ledger.DATA_TIERS]
