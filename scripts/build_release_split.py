#!/usr/bin/env python3
"""Split the full validation package for upload: dist/rc<NN>_split/ for the current mint.

Six-ish parts under 90 MB, SHA256SUMS.parts covering every part AND the whole archive,
REASSEMBLE.md with the release/commit/test-run identity read from the tree, not typed.
Run from the repo root AFTER the record commit; reads dist/pakemis_<v>_full_validation.zip.
"""
import hashlib
import io
import json
import os
import subprocess
import sys

R = os.getcwd()
sys.path.insert(0, os.path.join(R, "src"))

from pkinv.assets import asset_path
import pkinv  # noqa: E402

V = pkinv.__version__
ZIP = asset_path(R, "dist", "pakemis_%s_full_validation.zip" % V)
OUT = asset_path(R, "dist", "rc%s_split" % V.split("rc")[1])
PART = 90 * 1024 * 1024


# Per-release notes for REASSEMBLE.md, keyed by the minted version. A release
# without notes fails here on purpose: the split is the artefact a reviewer
# downloads first, and it must say what changed.
RELEASE_NOTES = {
    "1.0.0rc48": """## New in rc48 — the air-pollutant panel release

The seven air species (BC, CO, NH3, NMVOC, NOx as NO2, PM2.5, SO2) leave their single
reference year: a nine-fiscal-year covered-sources panel (FY2015-16..FY2023-24), built the
way the greenhouse-gas national series is built — each sector's own air engine per year
under its own fiscal convention. National greenhouse-gas pins are untouched.

- **`pakemis_air_atomic_annual.csv`** — 2,790 atoms (period × sector × category × process
  × species, Gg), each carrying its activity basis, factor source and its own source-stream
  anchor, fail-closed. The rollup declares `coverage_scope=covered_sources_only` on every
  row: this is not a complete national seven-species inventory and does not claim to be.
- **`pakemis_air_coverage_matrix.csv`** — all 630 period × module × species cells typed
  E/NE/IE/NO/NA (360 estimated, 270 typed absences, each with its reason and gap row).
  A missing estimate is its key, never a zero. Power runs the same nine years as the
  UNCONTROLLED screening scenario it declares itself to be, beside the panel
  (`power_air_screening_fy2015_16_fy2023_24.csv`), never inside it.
- **Road transport re-based on cited factors**: the EMEP/EEA guidebook 2023 Tier 1
  chapters (held, transcribed, every cell re-checked) replace the uncited per-km
  diagnostic; fuel reconciles to the OCAC control by construction; four processes as
  separate atoms; BC for the first time; SO2 stoichiometric under the cited Euro-II
  (Jan 2017) / Euro-V (Jan 2021) sulfur regime. FY2023-24 totals move as a declared
  re-base and the old-vs-new comparison is printed in the transport paper.
- **The panel is servable**: `fact_air_panel` + a period-aware `query_air`, the
  covered-sources limitation verbatim on every envelope, three typed refusals, and
  goldens freezing the SO2 series' Euro-II step.
- Beside this lane, the external verification bundle became the whole package
  (per-sector archives, `_common.zip`, a derivation chain per sector, and a
  withheld-files register).""",
    "1.0.0rc49": """## New in rc49 — the nine-year air spatial family

The covered-sources air panel leaves the national grain: nine fiscal years x seven
species on the frozen 0.05-degree lattice, through the greenhouse-gas cube's own
dispatch — every pollutant mass rides the cell vector its anchor stream was placed on
for that period, so the grid, the ADM2 table and the ADM1 table are three marginals of
ONE allocation and the identity panel = grid = ADM1 = ADM2 + outside + unallocated
closes for all 126 (pollutant, period, configuration) cells.

- **Two physical-only NetCDFs** (`pakemis_air_grid_0p05_annual_fy2015_16_fy2023_24.nc`
  and `..._survey_...nc`): REF_2023_24 and the new survey-anchored L_HERD1624
  configuration (HIES 2018-19/2024-25 dung series, per-household interpolation, every
  year's basis labelled) as separate files, never summed.
- **Anchor-grain ADM tables + typed unallocated** — the by-year tables carry the
  (period, stream) join key and no evidence badge of their own; the weight registry's
  verdict per mass is published in `pakemis_air_spatial_support_by_year.csv`, with the
  activity/factor and spatial uncertainty halves side by side, never combined, in
  `pakemis_air_uncertainty_split_by_year.csv`.
- **Corrected supports before anything was gridded**: the railway air layer now splits
  per traction stream (54 furnace-oil atoms had anchored a stream absent for six
  periods); agriculture's 14 rows became 76 on the surfaces each mass actually leaves
  from (fertiliser per product, livestock per stage, soil NOx per N pool, burning per
  crop) — byte-stable at every national total, and the Monte-Carlo now draws per POOL
  so the regrouping leaves the declared uncertainty intervals invariant.

National greenhouse-gas pins are untouched.""",
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    assert os.path.exists(ZIP), ZIP
    codes = io.open(asset_path(R, "dist", "pakemis_%s_validation" % V,
                                 "logs", "exit_codes.txt")).read()
    import re as _re
    bad = [l for l in codes.splitlines() if _re.search(r"exit=[1-9]", l)]
    assert not bad, ("refusing to split a package whose own checks failed:\n"
                     + "\n".join(bad))
    os.makedirs(OUT, exist_ok=True)
    whole = sha(ZIP)
    size = os.path.getsize(ZIP)
    base = os.path.basename(ZIP)
    parts = []
    with open(ZIP, "rb") as f:
        i = 0
        while True:
            chunk = f.read(PART)
            if not chunk:
                break
            suffix = "%s%s" % (chr(ord("a") + i // 26), chr(ord("a") + i % 26))
            name = "%s.part-%s" % (base, suffix)
            with open(asset_path(OUT, name), "wb") as p:
                p.write(chunk)
            parts.append(name)
            i += 1
    with open(asset_path(OUT, "SHA256SUMS.parts"), "w") as f:
        for name in parts:
            f.write("%s  %s\n" % (sha(asset_path(OUT, name)), name))
        f.write("%s  %s\n" % (whole, base))

    head = subprocess.run(["git", "rev-parse", "--short=8", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    run = json.load(open(asset_path(R, "outputs", "pakemis_test_run.json")))
    log = subprocess.run(["git", "log", "--oneline", "-4"],
                         capture_output=True, text=True).stdout.splitlines()
    art = next((l.split()[0] for l in log if "Release manifest" in l), "?")
    rel = next((l.split()[0] for l in log if "Mint" in l or "mint" in l), "?")
    counts = run.get("counts", run)
    with open(asset_path(OUT, "REASSEMBLE.md"), "w") as f:
        f.write("""# PakEmis %s — full validation package, split for upload

The archive is %s bytes, over most single-file upload limits, so it ships as %d
parts. Reassembly is a concatenation in name order; nothing is compressed twice and no tool
beyond `cat` is needed.

## Reassemble

```sh
cat %s.part-* > %s
shasum -a 256 -c SHA256SUMS.parts        # verifies the %d parts AND the whole archive
unzip %s
```

The parts must be concatenated in lexical order (`part-aa` … `part-%s`); `part-*` expands
that way in every POSIX shell. If `shasum` is unavailable, `sha256sum -c SHA256SUMS.parts`
is equivalent.

## What you should get

| | |
|---|---|
| whole archive sha256 | `%s` |
| bytes | %s |
| release | %s |
| release commit | `%s` (artifacts `%s`, record `%s`) |
| test run | %s executed, %s passed, %s skipped, %s failed |

## Verify the package itself

Inside the unpacked directory:

```sh
./reproduce.sh              # rebuilds the products from source and diffs them
./validate.sh --quick       # the fast gate
./validate.sh --full        # the whole suite over the finished tree
```

Their exit codes on this build are recorded in `logs/exit_codes.txt` inside the
package; the split is cut only when reproduce, --quick and --full all exited 0.

%s
""" % (V, "{:,}".format(size), len(parts), base, base, len(parts), base,
       parts[-1].split("-")[-1], whole, "{:,}".format(size), V, rel, art, head,
       counts.get("executed", "?"), counts.get("passed", "?"),
       counts.get("skipped", "?"), counts.get("failed", "?"),
       RELEASE_NOTES[V]))
    print("split -> %s: %d parts + SHA256SUMS.parts + REASSEMBLE.md" % (OUT, len(parts)))
    print("whole sha256 %s (%s bytes)" % (whole, "{:,}".format(size)))


if __name__ == "__main__":
    main()
