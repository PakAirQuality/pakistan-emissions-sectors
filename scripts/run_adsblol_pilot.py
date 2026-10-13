#!/usr/bin/env python3
"""Run the cached ADSB.lol pilot and publish only aggregate diagnostics."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from pkinv.paths import OUTPUTS, ROOT
from pkinv.sectors.aviation.adsblol import (
    ADSBLOLSource, archive_positive_control, synthetic_positive_control,
)
from pkinv.sectors.aviation.reconstructed import PCAAReconstructedSource


def _write_csv(path, rows):
    if not rows:
        return
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run():
    source = ADSBLOLSource()
    stages, days, summary = source.pilot(parallel=True)
    _synthetic_stage, synthetic = synthetic_positive_control()
    _omdb_stages, archive_control = archive_positive_control(source.archives()[0])
    positive_controls = [synthetic, {
        "control": archive_control["control_name"],
        "canonical_stages": archive_control.get("canonical_stages", 0),
        "airport_linked_legs": archive_control.get("target_airport_linked_legs", 0),
        "callsign_identified": archive_control.get("callsign_identified", 0),
        "aircraft_type_identified": archive_control.get("aircraft_type_identified", 0),
        "status": archive_control["status"],
        "interpretation": archive_control["interpretation"],
    }]
    routes, _residual = PCAAReconstructedSource().route_ledger()
    reconstructed = {(stage.origin_icao, stage.destination_icao): stage.activity_count
                     for stage in routes}
    observed = {}
    for stage in stages:
        if stage.boundary == "domestic" and stage.origin_icao and stage.destination_icao:
            key = (stage.origin_icao, stage.destination_icao)
            observed[key] = observed.get(key, 0) + 1
    sample_days = len(summary["pilot_dates"])
    expected = 20300 / 366.0 * sample_days
    summary.update({
        "expected_pcaa_domestic_stages_for_sample_days": expected,
        "observed_domestic_over_pcaa_daily_rate": summary.get("domestic_stages", 0) / expected,
        "coverage_interpretation": "screening ratio; pilot dates need not equal annual mean",
        "synthetic_positive_control_status": synthetic["status"],
        "omdb_archive_positive_control_status": archive_control["status"],
        "omdb_archive_airport_linked_legs": archive_control.get("target_airport_linked_legs", 0),
    })
    route_rows = []
    for route in sorted(set(reconstructed) | set(observed)):
        route_rows.append({
            "origin_icao": route[0], "destination_icao": route[1],
            "adsblol_observed_stages_four_days": observed.get(route, 0),
            "pcaa_reconstructed_annual_stages": reconstructed.get(route, 0),
            "pcaa_expected_stages_four_average_days": reconstructed.get(route, 0) / 366.0 * sample_days,
            "source_role": "coverage pilot; not annual expansion factor",
        })
    output = Path(OUTPUTS)
    _write_csv(output / "aviation_adsblol_pilot_days.csv", days)
    _write_csv(output / "aviation_adsblol_route_pilot.csv", route_rows)
    _write_csv(output / "aviation_adsblol_positive_controls.csv", positive_controls)
    (output / "aviation_adsblol_pilot_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_snapshot = Path(ROOT) / "sources" / "Aviation" / "ADSBLOL_pilot_FY2023_24.json"
    source_snapshot.write_text(json.dumps(
        {"summary": summary, "days": days, "positive_controls": positive_controls,
         "provenance": "aggregates only; raw ODbL archives are not redistributed"},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    run()
