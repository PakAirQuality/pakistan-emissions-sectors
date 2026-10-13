"""Like-for-like model-resolution ladder for domestic aviation."""
from pkinv.sectors.aviation import lto


def _factor(data, aircraft, distance_nm):
    lo = data.efv(lto.FF_EF, "%s_500" % aircraft)
    hi = data.efv(lto.FF_EF, "%s_750" % aircraft)
    return max(0.0, lo + (hi - lo) * (distance_nm - 500.0) / 250.0)


def compare(data, stages, reconciliation_factor=None, year=None):
    year = data.year if year is None else year
    domestic = [s for s in stages if s.boundary == "domestic"]
    aggregate = lto.fuel_tonnes(data, year)["domestic"]
    aggregate_stages = lto.lto_cycles(data, year)["domestic"]
    fleet = data.fleet_for("commercial", year)
    route = 0.0
    aircraft = 0.0
    route_n = aircraft_n = trajectory_n = 0
    for stage in domestic:
        if stage.great_circle_nm:
            route += (sum(share * _factor(data, ac, stage.great_circle_nm)
                          for ac, share in fleet.items()) * stage.activity_count / 1000.0)
            route_n += stage.activity_count
            if stage.aircraft_type:
                try:
                    aircraft += (_factor(data, data.inventory_aircraft(stage.aircraft_type),
                                         stage.great_circle_nm) * stage.activity_count / 1000.0)
                    aircraft_n += stage.activity_count
                except KeyError:
                    pass
        if stage.total_fuel_kg > 0:
            trajectory_n += stage.activity_count
    trajectory = sum(s.total_fuel_kg * s.activity_count for s in domestic) / 1000.0
    values = [("aggregate_movement", aggregate, aggregate_stages,
               "PCAA movements; representative distance and fleet"),
              ("route_resolved", route, route_n, "annual route activity; representative fleet"),
              ("route_aircraft", aircraft, aircraft_n, "stage distance and aircraft"),
              ("trajectory", trajectory, trajectory_n, "OpenAP observed/modelled trajectory")]
    if reconciliation_factor not in (None, ""):
        values.append(("fuel_constrained", trajectory * float(reconciliation_factor), trajectory_n,
                       "trajectory fuel reconciled to OCAC"))
    total_activity = float(aggregate_stages)
    return [{"fiscal_year": year, "model": name, "domestic_stages_total": total_activity,
             "domestic_stages_modelled": count, "coverage_share": count / total_activity if total_activity else 0,
             "fuel_t": fuel, "co2_kt": fuel * data.p("co2_per_t_fuel") / 1000.0,
             "method": method} for name, fuel, count, method in values]
