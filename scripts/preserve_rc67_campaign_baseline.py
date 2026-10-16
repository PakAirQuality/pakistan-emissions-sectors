"""Preserve released inputs/products before the rc68 integrated scientific rebase."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/baselines/rc67_integrated_campaign"
INPUTS = (
    "data/shared/activity/monthly/pbs_minerals_month_province.csv",
    "data/sectors/power/activity/coal_energy_booking.csv",
    "data/sectors/industry/activity/coal_by_consumer.csv",
    "data/shared/metadata/air_source_classes.csv",
)
PRODUCTS = (
    "release_manifest.json", "national_totals_2024.csv",
    "national_all_sectors.csv", "national_configurations.csv",
    "national_uncertainty_montecarlo.csv", "national_uncertainty_parameters.csv",
    "pakemis_atomic_annual.csv", "pakemis_national_series.csv",
    "pakemis_annual_fy2015_16_fy2023_24.csv",
    "pakemis_monthly_fy2015_16_fy2023_24.csv",
    "pakemis_air_atomic_annual.csv", "pakemis_air_annual_fy2015_16_fy2023_24.csv",
    "pakemis_air_coverage_matrix.csv", "pakemis_air_uncertainty_split_by_year.csv",
    "pakemis_monthly_coverage.csv", "pakemis_monthly_coverage_summary.csv",
    "pakemis_spatial_weights_by_year.csv", "pakemis_spatial_unallocated_by_year.csv",
    "pakemis_adm1_by_year.csv", "pakemis_adm2_by_year.csv",
    "pakemis_trend_uncertainty.csv", "pakemis_longitudinal_uncertainty.csv",
    "pakemis_minerals_panel_screening.csv", "pbs_minerals_parse_summary.csv",
    "pakemis_power_fuel_reconciliation.csv", "pakemis_power_coal_configurations.csv",
    "pakemis_coal_balance.csv", "pakemis_coal_sector_reallocation.csv",
    "n_ledger_2024.csv", "agriculture_air_pollutants_2024.csv",
)


def main():
    receipt = BASE / "baseline.json"
    if receipt.exists():
        manifest = json.loads(receipt.read_text())
        for row in manifest["files"]:
            path = BASE / row["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                raise RuntimeError("preserved baseline changed: " + row["path"])
        print("Existing immutable baseline verified; no files replaced.")
        return
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if commit != "3db0d658294dae1e6c760844df167daf7938fd65":
        raise RuntimeError("baseline must be preserved from the inspected rc67 content tree")
    paths = list(INPUTS) + ["outputs/" + name for name in PRODUCTS]
    paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "outputs").glob("pakemis*grid*.nc"))]
    paths += ["paper_national/versions/v3/" + name for name in
              ("paper.tex", "paper.pdf", "submission.tex", "submission.pdf", "technical_supplement.tex", "technical_supplement.pdf")]
    paths += ["papers/pdf/national_paper.pdf", "papers/pdf/national_supplement.pdf"]
    files, absent = [], []
    for relative in paths:
        source = ROOT / relative
        if not source.is_file():
            absent.append(relative)
            continue
        target = BASE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append({"path": relative, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "bytes": source.stat().st_size})
    manifest = {"version": "1.0.0rc67", "commit": commit, "files": files,
                "not_present": absent,
                "scope": "baseline only; ODbL-derived spatial databases retain upstream terms"}
    receipt.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (BASE / "SHA256SUMS").write_text("".join(f'{r["sha256"]}  {r["path"]}\n' for r in files))
    print(f"Preserved {len(files)} baseline files ({sum(r['bytes'] for r in files):,} bytes).")
    if absent:
        print("Explicitly absent optional products:", ", ".join(absent))


if __name__ == "__main__":
    main()
