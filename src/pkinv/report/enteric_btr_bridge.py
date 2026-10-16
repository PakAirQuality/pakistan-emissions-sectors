"""The enteric-fermentation bridge to Pakistan's First BTR, by species.

WHY. The article reports enteric fermentation at 1.19 times the submitted FY2020-21 value
and manure management at 0.99, and the clause explaining the gap was deleted in v3 because
nothing held supported it. The BTR does not print livestock populations, but its Figure 1
(page 15 of the PDF) prints enteric CH4 BY SPECIES in Mt CO2e, and the inventory's
FY2020-21 estimate is available at the same grain (fact_annual, category enteric
fermentation, subitem = species). Species by species the two accounts can be compared, and
the comparison locates the gap without a hypothesis: four species agree to the printed
precision, the whole difference sits in buffalo and other cattle, and two species the BTR
carries (mules and asses, horses) this inventory does not estimate.

THE BTR VALUES ARE A TRANSCRIPTION, declared here with their source, the way gem_audit
declares its correspondence: pakistan_btr1_2024.pdf, Figure 1 "Animal population (%) and
enteric CH4 emissions (MtCO2e)", the right-hand panel; the text layer is
sources/UNFCCC/btr1_2024.txt. They sum to 112.83, the BTR's enteric total that
pakemis_btr_comparison.csv already carries.

COMPARATOR ONLY: nothing reads this file.

Usage:  python3 -m pkinv.report.enteric_btr_bridge
Writes: outputs/pakemis_enteric_btr_bridge.csv
"""
import csv
import io
import os

from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS

ANNUAL = os.path.join(OUTPUTS, "semantic", "fact_annual.csv")
OUT = os.path.join(OUTPUTS, "pakemis_enteric_btr_bridge.csv")
PERIOD = "FY2020-21"
CONFIG = "S_TAN"
SOURCE = ("Pakistan First BTR (2024), Figure 1 'Animal population (%) and enteric CH4 "
          "emissions (MtCO2e)', PDF page 15; sources/UNFCCC/pakistan_btr1_2024.pdf")

# species key in this inventory -> (BTR label, BTR Mt CO2e as printed)
BTR_BY_SPECIES = {
    "buffalo": ("Buffalo", 48.43),
    "dairy_cattle": ("Dairy Cows", 24.67),
    "other_cattle": ("Other Cattle", 20.80),
    "goats": ("Goats", 11.25),
    "sheep": ("Sheep", 4.42),
    "camels": ("Camels", 1.44),
}
BTR_ONLY = {"mules_and_asses": ("Mules & Asses", 1.63), "horses": ("Horses", 0.19)}
BTR_TOTAL_PRINTED = 112.83
AGREE_MT = 0.01  # the BTR prints two decimals

FIELDS = ("species", "btr_label", "pakemis_Mt_co2e_AR5", "btr_Mt_co2e", "difference_Mt",
          "ratio_pakemis_over_btr", "verdict", "note")


def _pakemis_by_species():
    out = {}
    with io.open(ANNUAL, encoding="utf-8") as handle:
        for r in csv.DictReader(line for line in handle if not line.startswith("#")):
            if (r["configuration_id"] == CONFIG and r["period_id"] == PERIOD
                    and r["gas"] == "CH4" and r["category"].lower().startswith("enteric")):
                out[r["subitem"]] = out.get(r["subitem"], 0.0) + float(r["co2e_Mt_AR5"])
    if not out:
        raise SystemExit("fact_annual carries no enteric CH4 for %s" % PERIOD)
    return out

def build():
    ours = _pakemis_by_species()
    unknown = sorted(set(ours) - set(BTR_BY_SPECIES))
    if unknown:
        raise SystemExit("inventory species without a BTR correspondence: %s" % unknown)
    rows = []
    for key, (label, btr) in BTR_BY_SPECIES.items():
        p = ours.get(key, 0.0)
        d = p - btr
        verdict = "agree to the printed precision" if abs(d) <= AGREE_MT else (
            "inventory higher" if d > 0 else "inventory lower")
        rows.append({"species": key, "btr_label": label, "pakemis_Mt_co2e_AR5": "%.3f" % p,
                     "btr_Mt_co2e": "%.2f" % btr, "difference_Mt": "%.3f" % d,
                     "ratio_pakemis_over_btr": "%.3f" % (p / btr), "verdict": verdict,
                     "note": ""})
    for key, (label, btr) in BTR_ONLY.items():
        rows.append({"species": key, "btr_label": label, "pakemis_Mt_co2e_AR5": "NE",
                     "btr_Mt_co2e": "%.2f" % btr, "difference_Mt": "%.3f" % (-btr),
                     "ratio_pakemis_over_btr": "", "verdict": "not estimated here",
                     "note": "the BTR carries this species; this inventory does not estimate it"})
    p_total = sum(ours.values())
    b_total = sum(v for _, v in BTR_BY_SPECIES.values()) + sum(v for _, v in BTR_ONLY.values())
    if abs(b_total - BTR_TOTAL_PRINTED) > 0.02:
        raise SystemExit("the transcribed BTR species do not sum to the printed total: %.2f vs %.2f"
                         % (b_total, BTR_TOTAL_PRINTED))
    rows.append({"species": "TOTAL", "btr_label": "Enteric fermentation",
                 "pakemis_Mt_co2e_AR5": "%.3f" % p_total, "btr_Mt_co2e": "%.2f" % b_total,
                 "difference_Mt": "%.3f" % (p_total - b_total),
                 "ratio_pakemis_over_btr": "%.3f" % (p_total / b_total),
                 "verdict": "sum of the rows above",
                 "note": "the BTR total as printed is %.2f; pakemis_btr_comparison.csv carries the same pair"
                         % BTR_TOTAL_PRINTED})
    return rows


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "# Enteric CH4 by species, this inventory (FY2020-21, REF_2023_24, AR5) against Pakistan's",
        "# First BTR as printed in its Figure 1 (PDF p.15). Transcription declared in",
        "# pkinv/report/enteric_btr_bridge.py. COMPARATOR ONLY; nothing reads this file.",))
    agree = [r["species"] for r in rows if r["verdict"].startswith("agree")]
    gap = [(r["species"], r["difference_Mt"]) for r in rows if r["verdict"] == "inventory higher"]
    print("enteric_btr_bridge: agree %s; inventory higher %s" % (agree, gap))


if __name__ == "__main__":
    main()
