#!/usr/bin/env python3
"""The technical supplement's list of canonical products, generated, never typed.

Every file the release ships as a canonical product (data/catalog/artifact_roles.csv,
role=canonical, resolved against outputs/ by pkinv.report.artifact_inventory) is named once,
grouped by family, with one line on what it holds. The line comes from the product
catalogue where the file is a catalogued primary artifact, otherwise from the file's own
leading comment, otherwise from its role description, otherwise from its name. Internal
release labels and emphasis capitals are removed from those sources; nothing else is
reworded.

The output is written beside the manuscript sources (paper_national/versions/v3/), not under
generated/, because the artifact inventory's citation scan reads the manuscript directory
and its sections only.

    python3 scripts/make_v3_product_list.py            # write
    python3 scripts/make_v3_product_list.py --check    # compare bytes, write nothing
"""
import argparse
import csv
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(ROOT, "paper_national", "versions", "v3", "products_appendix.tex")
OUTPUTS = os.path.join(ROOT, "outputs")

# Ordered: the first rule a name satisfies decides its family.
FAMILIES = (
    ("Semantic query layer", lambda n: n.startswith("semantic/")),
    ("Figure data", lambda n: n.startswith("paper_figure_data/")),
    ("Gridded products (NetCDF)", lambda n: n.endswith(".nc")),
    ("Uncertainty and structural cases", lambda n: any(k in n for k in (
        "uncertainty", "ensemble", "longitudinal", "structural", "bridge_configurations",
        "absence_screening", "power_air_screening"))),
    ("Evaluation and comparison", lambda n: any(k in n for k in (
        "edgar", "htap", "btr", "benchmark", "validation", "comparison", "unsd_", "lahore"))),
    ("Administrative and spatial records", lambda n: any(k in n for k in (
        "adm1", "adm2", "spatial", "road_", "kiln_allocation", "builtup", "stream_support",
        "grid_", "unallocated", "frame"))),
    ("Monthly records", lambda n: any(k in n for k in ("monthly", "temporal", "crop_calendar"))),
    ("Coverage and evidence registers", lambda n: any(k in n for k in (
        "coverage", "product_", "artifact_", "evidence", "requests", "exceptions", "nesting",
        "completeness", "source_support"))),
    ("Activity accounts, source controls and extension", lambda n: any(k in n for k in (
        "coal", "brick", "cement", "sulfur", "industr", "ogra", "ammonia", "hfc", "minerals",
        "ocac", "extension", "fy2025_26", "agriculture", "splice", "basis_change"))),
    ("Annual records", lambda n: True),
)

# Files a canonical pattern still matches but which describe a retired nine-year panel or a
# dated re-base measurement; they are reported to the register owner for re-typing instead of
# being presented here as current products.
SUPERSEDED = re.compile(r"fy2015_16_fy2023_24|_rc\d+\.csv$")
OVERRIDES = {
    "pakemis_adm2_monthly.csv": "District monthly greenhouse-gas records for the reference year, without intervals",
    "pakemis_adm2_monthly_sector.csv": "District monthly greenhouse-gas records by sector for the reference year, without intervals",
    "pakemis_adm2_nesting_check.csv": "Check that district agricultural allocations sum to their provincial controls",
    "pakemis_power_grid_basis_change.csv": "Comparison of the power geography under the alternative allocation bases",
    "pakemis_spatial_exceptions.csv": "Allocations where the grid could not follow the declared spatial basis",
}

ACRONYMS = {"ADM1", "ADM2", "GHG", "OGRA", "OCAC", "NEPRA", "HDIP", "UNSD", "EDGAR", "HTAP",
            "FAOSTAT", "NFDC", "PBS", "QIM", "IPCC", "BTR", "CRT", "HFC", "NMVOC", "LPG", "CNG",
            "RLNG", "OSM", "TAN", "IPPU", "MMCFD", "HIES", "CPPA", "GENCO", "SIR", "ODBL", "UFG",
            "COD", "CSV", "CC", "IGO", "OCHA", "GEM", "KE", "GCD", "AR5", "AR6", "GWP", "EMEP", "NCV", "FGD", "VIIRS", "FIRMS", "NO2",
            "SO2", "NH3", "CO2", "CH4", "N2O", "NOX", "PM10", "PM2.5", "HFCS", "SNGPL", "SSGC"}


def clean(text):
    """One line, without release-history labels or emphasis capitals."""
    text = " ".join(text.replace("#", " ").split())
    text = re.sub(r"\(?\brc\d+[a-z]?\b(?:\s+(?:Wave|W)\s*\d+[a-z]?)?(?:\s*[A-Z]\d+)?(?:\s*/\s*rc\d+\s*[A-Z]?\d*)?\)?[:;,]?\s*",
                  "", text)
    text = re.sub(r"\(?\bWave [A-Za-z]?\d*[a-z]?(?:, Output \d+)?\)?[:;,]?\s*", "", text)
    text = re.sub(r"\bsince\s*(?=[,.;)]|$)", "", text)
    words = []
    for word in text.split(" "):
        core = re.sub(r"[^A-Za-z0-9.]", "", word)
        parts = [p for p in re.split(r"[^A-Za-z0-9.]+", word) if p]
        keep = (len(core) < 2 or core.upper() in ACRONYMS or any(c.isdigit() for c in core)
                or "_" in word or any(p.upper() in ACRONYMS for p in parts))
        if core.isupper() and not keep:
            word = word.lower()
        words.append(word)
    text = " ".join(words).strip(" -:;,")
    # The first clause carries what the file holds; the rest is method detail.
    for stop in (". ", "; ", " - ", " — ", ": "):
        cut = text.find(stop, 25)
        if cut > 0:
            text = text[:cut]
    if len(text) > 150:
        text = text[:150].rsplit(" ", 1)[0]
    # A cut inside a parenthesis drops the unfinished parenthesis.
    if text.count("(") > text.count(")"):
        text = text[:text.rfind("(")]
    text = re.sub(r"\s+(and|or|the|with|of|to|a|in|for|by|at|whose)$", "", text.strip(" -:;,.(")).strip(" -:;,.(")
    return text[:1].upper() + text[1:]


def from_name(name):
    stem = os.path.basename(name).rsplit(".", 1)[0]
    stem = re.sub(r"^(pakemis|fact|dim)_", "", stem)
    stem = re.sub(r"fy(\d{4})_(\d{2})_fy(\d{4})_(\d{2})", r"FY\1-\2 to FY\3-\4", stem)
    words = stem.replace("_", " ")
    for a, b in (("adm1", "provincial (ADM1)"), ("adm2", "district (ADM2)"), ("ghg", "greenhouse-gas"),
                 ("air", "air-pollutant"), ("0p05", "0.05-degree"), ("0p1", "0.1-degree")):
        words = re.sub(r"\b%s\b" % a, b, words)
    kind = ("Semantic dimension table" if os.path.basename(name).startswith("dim_")
            else "Semantic fact table" if name.startswith("semantic/") else "Records")
    return "%s: %s" % (kind, words)


def leading_comment(path):
    if not path.endswith(".csv"):
        return ""
    try:
        with io.open(path, encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
    except OSError:
        return ""
    return first[1:].strip() if first.startswith("#") else ""


def tex(text):
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}"), ("×", r"$\times$"), ("≥", r"$\geq$"), ("≤", r"$\leq$"),
                 ("→", r"$\rightarrow$"), ("–", "--"), ("—", "---"), ("₂", "$_2$"), ("₄", "$_4$"),
                 ("₃", "$_3$"), ("±", r"$\pm$"), ("·", r"$\cdot$"), ("≈", r"$\approx$")):
        text = text.replace(a, b)
    return "".join(ch if ord(ch) < 128 or ch in "$" else "?" for ch in text)


def filename(name):
    # \_ followed by a break hint: the citation scanner normalises both (one shared function).
    return r"\texttt{%s}" % name.replace("_", r"\_\allowbreak ").replace("/", r"/\allowbreak ")


def render():
    from pkinv.report import artifact_inventory as inventory
    from pkinv.core.io import read_rows
    catalogue = {}
    for row in read_rows(os.path.join(OUTPUTS, "pakemis_product_catalog.csv")):
        catalogue[row["primary_artifact"]] = row["what_it_is_and_is_not"]
    canonical = [r for r in inventory.build() if r["role"] == "canonical"]
    names = sorted(r["artifact"] for r in canonical if not SUPERSEDED.search(r["artifact"]))
    generic = {"pakemis_*.csv", "pakemis_*.nc", "semantic/*.csv", "paper_figure_data/*.csv",
               "national_all_sectors*.csv", "*"}
    patterns = {r["artifact"]: (r["matched_pattern"], r["description"]) for r in canonical}
    grouped = {label: [] for label, _rule in FAMILIES}
    for name in names:
        pattern, description = patterns[name]
        line = (OVERRIDES.get(name) or catalogue.get(name) or leading_comment(os.path.join(OUTPUTS, name))
                or ("" if pattern in generic else description))
        line = clean(line) if line else from_name(name)
        if not line:
            line = from_name(name)
        family = next(label for label, rule in FAMILIES if rule(name))
        grouped[family].append((name, line))
    out = ["%% GENERATED by scripts/make_v3_product_list.py from data/catalog/artifact_roles.csv",
           "%% (role=canonical), outputs/pakemis_product_catalog.csv and each file's leading comment.",
           "%% Do not edit: run the script. --check compares bytes.",
           r"\section{Canonical data products}",
           r"\label{app:products}",
           ("The release ships %d canonical products. Each is listed once below, by family, with "
            "the file name under \\texttt{outputs/} and one line on what it holds. Descriptions "
            "are taken from the product catalogue, the file's own header or its declared role." % len(names)),
           ""]
    for label, _rule in FAMILIES:
        items = grouped[label]
        if not items:
            continue
        out.append(r"\subsection*{%s}" % label)
        out.append(r"\begin{itemize}\setlength{\itemsep}{1pt}\footnotesize")
        for name, line in items:
            out.append(r"\item %s: %s." % (filename(name), tex(line)))
        out.append(r"\end{itemize}")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = io.open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != text:
            print("products_appendix.tex differs from a fresh render")
            return 1
        print("products_appendix.tex is current")
        return 0
    with io.open(OUT, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
