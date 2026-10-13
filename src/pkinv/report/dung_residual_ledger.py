"""The unresolved dung residual, by species, in the three quantities a destination would
need: nitrogen, volatile solids and air-dry cake.

WHY. Under configuration S, 46.77 Mt of air-dry cake that agriculture's ledger diverts
to fuel has no observed destination (residential_dung_ledger_2024.csv, the UNRESOLVED
row). The scenario variants price that residual one destination at a time
(national_dung_variants.csv), and each destination is priced on a DIFFERENT quantity:
non-household combustion burns the cake's dry solids, a return to manure management
needs the nitrogen, field application needs both. The residual was published as one
air-dry mass; this table publishes the nitrogen and volatile solids that sit inside it,
per species, through the same chain the engine uses (combustion.dung_vs_kg:
N x vs_rate / nex_rate per animal category; VS / (1 - ash) is dry solids; dry solids /
(1 - moisture) is air-dry cake), so a reader pricing a destination has the quantity it
needs beside the one the ledger states.

THE RESIDUAL SHARE IS APPLIED UNIFORMLY ACROSS SPECIES. The household observation (HIES)
is a cake mass with no species, so the residual's species composition is assumed to be
the diversion's: every species keeps the diversion's 0.7963 unresolved fraction. That is
an assumption the table declares in its own column, not a measurement.

Nitrogen does NOT convert to cake: the chain goes N -> VS (via the rate ratio for the
same animal category, where the typical animal mass cancels) -> dry solids -> air-dry
cake. The label on each column names its basis.

Usage:  python3 -m pkinv.report.dung_residual_ledger
Writes: outputs/pakemis_dung_residual_ledger.csv
"""
import csv
import io
import os

from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS

LEDGER = os.path.join(OUTPUTS, "residential_dung_ledger_2024.csv")
OUT = os.path.join(OUTPUTS, "pakemis_dung_residual_ledger.csv")
FIELDS = ("species", "diverted_N_kt", "diverted_VS_kt", "diverted_dry_solids_kt",
          "diverted_air_dry_Mt", "unresolved_share", "unresolved_N_kt",
          "unresolved_VS_kt", "unresolved_dry_solids_kt", "unresolved_air_dry_Mt",
          "chain", "note")
TOLERANCE_MT = 0.001


def _unresolved_share():
    with io.open(LEDGER, encoding="utf-8") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    diverted = unresolved = None
    for r in rows:
        if r["configuration"] == "S" and r["claimant"].startswith("UNRESOLVED"):
            unresolved = float(r["Mt_air_dry"])
        if r["configuration"] == "both" and r["claimant"].startswith("Diverted"):
            diverted = float(r["Mt_air_dry"])
    if diverted is None or unresolved is None:
        raise KeyError("residential_dung_ledger_2024.csv lacks the Diverted or UNRESOLVED row")
    # the share from the two printed masses, not the ledger's 4-dp share column: 0.7963 x
    # 58.7414 is 46.7757, which misses the printed 46.7741 by more than the tolerance
    return unresolved / diverted, unresolved


def build():
    from pkinv.sectors.agriculture.ef_library import InventoryData
    from pkinv.sectors.residential import combustion
    from pkinv.sectors.residential.data import ResidentialData
    agri = InventoryData()
    data = ResidentialData()
    share, unresolved_mt = _unresolved_share()
    ash = data.p("dung_ash_frac_dry")
    moisture = data.p("dung_cake_moisture_ar")
    rows = []
    total = {k: 0.0 for k in ("n", "vs", "ts", "ad")}
    for species, n_kg in sorted(combustion.diverted_n_by_species(agri).items()):
        tam = agri.p("tam_" + species)
        nex_per_head = agri.p("nex_rate_" + species) * tam * 365.0 / 1000.0
        vs_per_head = data.p("vs_rate_" + species) * tam * 365.0 / 1000.0
        vs_kg = (n_kg / nex_per_head) * vs_per_head
        ts_kg = vs_kg / (1.0 - ash)
        ad_kg = ts_kg / (1.0 - moisture)
        for k, v in zip(("n", "vs", "ts", "ad"), (n_kg, vs_kg, ts_kg, ad_kg)):
            total[k] += v
        rows.append({
            "species": species,
            "diverted_N_kt": "%.3f" % (n_kg / 1e6), "diverted_VS_kt": "%.3f" % (vs_kg / 1e6),
            "diverted_dry_solids_kt": "%.3f" % (ts_kg / 1e6),
            "diverted_air_dry_Mt": "%.5f" % (ad_kg / 1e9),
            "unresolved_share": "%.4f" % share,
            "unresolved_N_kt": "%.3f" % (share * n_kg / 1e6),
            "unresolved_VS_kt": "%.3f" % (share * vs_kg / 1e6),
            "unresolved_dry_solids_kt": "%.3f" % (share * ts_kg / 1e6),
            "unresolved_air_dry_Mt": "%.5f" % (share * ad_kg / 1e9),
            "chain": ("N x (vs_rate_%s / nex_rate_%s) = VS; VS / (1 - %.3f ash) = dry solids; "
                      "/ (1 - %.3f moisture) = air-dry" % (species, species, ash, moisture)),
            "note": "species share of the residual assumed equal to its share of the diversion"})
    closure = abs(total["ad"] / 1e9 * share - unresolved_mt)
    if closure > TOLERANCE_MT:
        raise SystemExit("dung residual ledger does not close: %.5f Mt vs the ledger's %.5f"
                         % (total["ad"] / 1e9 * share, unresolved_mt))
    rows.append({
        "species": "ALL", "diverted_N_kt": "%.3f" % (total["n"] / 1e6),
        "diverted_VS_kt": "%.3f" % (total["vs"] / 1e6),
        "diverted_dry_solids_kt": "%.3f" % (total["ts"] / 1e6),
        "diverted_air_dry_Mt": "%.5f" % (total["ad"] / 1e9),
        "unresolved_share": "%.4f" % share,
        "unresolved_N_kt": "%.3f" % (share * total["n"] / 1e6),
        "unresolved_VS_kt": "%.3f" % (share * total["vs"] / 1e6),
        "unresolved_dry_solids_kt": "%.3f" % (share * total["ts"] / 1e6),
        "unresolved_air_dry_Mt": "%.5f" % (share * total["ad"] / 1e9),
        "chain": "sum over species",
        "note": "closes on residential_dung_ledger_2024.csv's UNRESOLVED row to %.3f Mt" % TOLERANCE_MT})
    return rows


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "# The unresolved dung residual (configuration S) by species: nitrogen, volatile solids,",
        "# dry solids and air-dry cake through the engine's own chain. pkinv.report.dung_residual_ledger.",
        "# The species split of the residual is an ASSUMPTION (equal to the diversion's); see the note column.",))
    last = rows[-1]
    print("dung_residual_ledger: unresolved %s Mt air-dry = %s kt N, %s kt VS"
          % (last["unresolved_air_dry_Mt"], last["unresolved_N_kt"], last["unresolved_VS_kt"]))


if __name__ == "__main__":
    main()
