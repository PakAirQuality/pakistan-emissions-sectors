"""The agent's guardrail: a consumer prints only numbers the server inserted.

`render(template, result)` replaces {{result_cell_n}} with the n-th value's display string, and
{{result_cell_n.exact}} / {{result_cell_n.unit}} with the exact string or the unit. A template
that names a cell the result does not carry is an error; a template that carries a bare number
where a cell was expected is rejected by `reject_bare_numbers`, so an answer that invents a
figure never reaches a reader."""
import re

CELL = re.compile(r"\{\{result_cell_(\d+)(?:\.(exact|unit|value))?\}\}")
BARE_NUMBER = re.compile(r"(?<![\w.{])\d+(?:[.,]\d+)+(?![\w}])")


class PlaceholderError(ValueError):
    pass


def render(template, result):
    values = result["values"]

    def sub(match):
        index = int(match.group(1))
        if index >= len(values):
            raise PlaceholderError("template names result_cell_%d; the result has %d cells"
                                   % (index, len(values)))
        cell = values[index]
        attr = match.group(2) or "display"
        return str(cell[attr])
    return CELL.sub(sub, template)


def reject_bare_numbers(template):
    """A template may not carry a decimal number that is not a placeholder."""
    bare = BARE_NUMBER.findall(CELL.sub("", template))
    if bare:
        raise PlaceholderError("bare numbers in a template are rejected: %s" % bare)
    return True
