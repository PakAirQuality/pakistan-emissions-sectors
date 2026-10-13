"""The national manuscript's generated tables: LaTeX bodies built from query envelopes.

v1.0.0 Wave 4. A renderer here takes the envelopes a registry row's stored query returned
(paper_national/queries/paper_artefacts.csv) and returns the LaTeX lines the manuscript
inputs. It prints ONLY `display` strings the query core inserted - it never re-rounds, sums,
divides or counts a mass; the rounding rule is the contract's (semantic_release.json
`rounding`, half-even on the exact decimal string) and the receipt on every envelope is what
makes a printed cell reproducible. Text labels (an IPCC name, a footnote marker, a column
header) are the renderer's; every number is the release's.

Each renderer has the signature `render(envelopes, release) -> [lines]`, where `envelopes`
is the list of envelopes the registry row's query_params produced (one per params object,
in order) and `release` is the open pakemis_query.Release (used for dimension lookups and
nothing else).
"""
import json

from pkinv.report.category_ledger import IPCC_CATEGORY_NAMES

# The manuscript's short forms of the Guidelines' names, with the footnote markers the
# category table carries. tests/paper_numbers/test_tables.py maps the printed short form
# back to IPCC_CATEGORY_NAMES, so a short form here is a label the test already accepts.
CATEGORY_PRINTED = {
    "1.B.2": "Fugitive emissions, oil and natural gas$^{e}$",
    "4.D.1": "Domestic wastewater",
    "1.A.4.c": "Agriculture/forestry/fishing (off-road)$^{\\dagger}$",
    "3.F": "Field burning of residues",
    "1.A.2/1.A.4.c": "Railway stationary/off-road (unresolved)$^{\\ddagger}$",
}
GASES = ("CO2", "CH4", "N2O")


def _cells_by_group(env, *keys):
    """{(group values...): value dict} over an envelope's cells."""
    return {tuple(v["group"][k] for k in keys): v for v in env["values"]}


def category_gas(envelopes, release):
    """tab:categorygas. Envelopes, in registry order: [0] ipcc_code x gas, [1] ipcc_code
    (ordered largest first, the row order), [2] gas totals, [3] the national total, [4]
    ipcc_code x sector_id (the "Computed in" column). A dash is a gas with no component in
    the category - the cell is absent from the grouped result, not a value below a
    threshold."""
    by_code_gas = _cells_by_group(envelopes[0], "ipcc_code", "gas")
    by_gas = _cells_by_group(envelopes[2], "gas")
    modules = {}
    for v in envelopes[4]["values"]:
        modules.setdefault(v["group"]["ipcc_code"], []).append(v["group"]["sector_id"])
    lines = ["\\begin{tabular}{@{}llrrrrl@{}}", "\\toprule",
             "\\textbf{IPCC} & \\textbf{Category} & \\textbf{\\COtwo{}} & \\textbf{\\CHfour{}} & "
             "\\textbf{\\NtwoO{}}",
             "& \\textbf{Total} & \\textbf{Computed in} \\\\", "\\midrule"]
    for row in envelopes[1]["values"]:
        code = row["group"]["ipcc_code"]
        name = CATEGORY_PRINTED.get(code, IPCC_CATEGORY_NAMES[code])
        cells = [by_code_gas[(code, g)]["display"] if (code, g) in by_code_gas else "---"
                 for g in GASES]
        lines.append("%s & %s & %s & %s & %s \\\\"
                     % (code, name, " & ".join(cells), row["display"],
                        " + ".join(sorted(modules[code]))))
    lines.append("\\midrule")
    lines.append("\\textbf{Total} & & %s & \\textbf{%s} & \\\\"
                 % (" & ".join("\\textbf{%s}" % by_gas[(g,)]["display"] for g in GASES),
                    envelopes[3]["values"][0]["display"]))
    lines += ["\\bottomrule", "\\end{tabular}"]
    return lines


def completeness_counts(envelopes, release):
    """tab:completeness. The notation-key tally as VALUE MACROS the inline table prints
    (\\genCompletenessCountE ...), because the table's third column is prose that belongs
    in the section, not in a renderer. Each count is the number of cells get_completeness
    returned for that key - the cardinality of a result set, not an arithmetic on values -
    and each macro names the receipt of the envelope it came from."""
    lines = []
    for env in envelopes:
        key = json.loads(env["request"])["notation_keys"][0]
        macro = "\\genCompletenessCount%s" % key
        lines.append("\\providecommand{%s}{}\\renewcommand{%s}{%d}%% receipt %s"
                     % (macro, macro, len(env["values"]), env["receipt"]))
    return lines


RENDERERS = {"pkinv.report.paper_tables.category_gas": category_gas,
             "pkinv.report.paper_tables.completeness_counts": completeness_counts}
