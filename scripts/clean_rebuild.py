#!/usr/bin/env python3
"""Reproduce from deposit-listed compiled inputs in a fresh directory and environment.

Primary-document extraction is a separate level: the explicitly named source
phases are seeded with verified bytes and recorded, never reported regenerated.
The production outputs directory starts empty apart from these and held inputs.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pkinv.core.io import read_rows
from pkinv.build import DEPOSIT_SOURCE_PHASES, phases_for_group
from pkinv.run_all import PHASES


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--venv", type=Path, help="preinstalled isolated requirements.lock environment")
    args = parser.parse_args()
    work = args.work or Path(tempfile.mkdtemp(prefix="pakemis-clean-"))
    tree = work / "tree"
    tree.mkdir(parents=True, exist_ok=False)
    (tree / "logs").mkdir()
    manifest = read_rows(str(ROOT / "outputs/pakemis_deposit_manifest.csv"))
    copied = []
    for row in manifest:
        if row["kind"] not in {"code", "build", "input", "documentation", "manuscript", "manuscript_source"}:
            continue
        source = ROOT / row["path"]
        if row["sha256"] and sha(source) != row["sha256"]:
            raise ValueError("stale deposit input: " + row["path"])
        target = tree / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(dict(path=row["path"], sha256=sha(source)))
    environment = os.environ.copy()
    environment.update(PKINV_ROOT=str(tree), PYTHONPATH=str(tree / "src"),
                       PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=str(work / "mpl"))
    environment.pop("FIRMS_MAP_KEY", None)
    venv = args.venv or work / "venv"
    if args.venv is None:
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        subprocess.run([str(venv / "bin/python"), "-m", "pip", "install", "-r",
                        str(tree / "requirements.lock")], check=True)
    python = str(venv / "bin/python")
    subprocess.run([python, str(tree / "tests/validation/seed_held_products.py"),
                    str(ROOT), str(tree)], env=environment, check=True)
    receipt = tree / "logs/seeded_products.json"
    seeded = json.loads(receipt.read_text())
    known = {row["path"] for row in seeded}
    for phase in PHASES:
        if phase.label not in DEPOSIT_SOURCE_PHASES:
            continue
        for relative in phase.writes:
            if not relative.startswith("outputs/") or relative in known:
                continue
            source, target = ROOT / relative, tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            seeded.append(dict(path=relative, sha256=sha(source), producer=phase.label,
                reason_held="compiled-source level: " + DEPOSIT_SOURCE_PHASES[phase.label],
                reproducible_in_package="source_extraction_not_repeated"))
            known.add(relative)
    # A `prior:` read is a declared cycle: the phase consumes the PREVIOUS build's copy of a
    # file a later phase rewrites (the semantic contract hashes the source register the
    # deposit manifest writes afterwards). A fresh tree has no previous build, so the first
    # rc68 clean rebuild stopped at "Semantic release". The released bytes are that previous
    # build; they are seeded and recorded, and the later phase still regenerates and compares.
    for phase in phases_for_group("deposit"):
        for read in phase.reads or ():
            if not read.startswith("prior:"):
                continue
            relative = read[len("prior:"):]
            source, target = ROOT / relative, tree / relative
            if relative in known or target.exists() or not source.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            seeded.append(dict(path=relative, sha256=sha(source), producer=phase.label,
                reason_held="prior-build read: the released copy stands in for the previous build",
                reproducible_in_package="rewritten"))
            known.add(relative)
    receipt.write_text(json.dumps(seeded, indent=2) + "\n")
    (work / "input_snapshot.json").write_text(json.dumps(copied, indent=2) + "\n")
    with (work / "rebuild.log").open("w") as log:
        process = subprocess.run([python, "-m", "pkinv.build", "--group", "deposit",
            "--strict", "--quick", "--ledger", "logs/pakemis_run_ledger.json",
            "--seeded", "logs/seeded_products.json"], cwd=tree, env=environment,
            stdout=log, stderr=subprocess.STDOUT)
    result = subprocess.run([python, str(tree / "tests/validation/compare_outputs.py"),
        str(ROOT), str(tree), str(work / "comparison.csv"), "skipped"], env=environment)
    summary = dict(level="compiled_inputs", source_extraction_repeated=False,
        build_exit=process.returncode, comparison_exit=result.returncode,
        seeded_source_phases=DEPOSIT_SOURCE_PHASES, work=str(work))
    (work / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return int(bool(process.returncode or result.returncode))


if __name__ == "__main__":
    raise SystemExit(main())
