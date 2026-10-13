"""How a filename may appear in source code: literally, or with its digits generalised.

Shared by scripts/audit_outputs.py (every file in outputs/ has a writer) and
pkinv.report.data_provenance (every product under data/ has a producer, a document or a
declared reason). Output and data names are routinely built at run time -
"industry_monthly_%d.csv" % year, "%s_totals_%d.csv" % (name, year),
"power_totals_%s.csv" % period.file_suffix(...) - so a search for the literal name alone
would call a written file an orphan. The generalised forms keep the stem so that a
pattern cannot degenerate into one that matches everything.
"""
import os
import re


def name_patterns(name):
    """Regexes, most literal first, that match how `name` may be written in code."""
    yield re.escape(name)
    # fy-suffixed names (rc15): "power_totals_fy2023_24.csv" is written as
    # "power_totals_%s.csv" % period.file_suffix(...) - the whole fy...-token
    # generalises as one unit, or digit-run generalisation below would split it.
    fy_generalised = re.sub(r"fy\d{4}_\d{2}|cy\d{4}", r"(?:%s|\\{[^}]*\\})",
                            re.escape(name))
    if fy_generalised != re.escape(name):
        yield fy_generalised
    generalised = re.sub(r"\d+", r"(?:\\d+|%d|%s|\\{[^}]*\\})", re.escape(name))
    if generalised != re.escape(name):
        yield generalised
    stem, ext = os.path.splitext(name)
    parts = stem.split("_")
    if len(parts) > 1:
        # "<something>_monthly_2024.csv" written as "%s_monthly_%d.csv"
        tail = "_".join(parts[1:])
        yield r"(?:%[sd]|\{[^}]*\})_" + re.sub(r"\d+", r"(?:\\d+|%d|%s)",
                                               re.escape(tail + ext))
