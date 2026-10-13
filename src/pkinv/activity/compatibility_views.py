"""Materialize stable source views from maintained observations and annotations.

Only this upstream task writes the eight compatibility tables.  It reads source
assets directly, before canonical publication, so there is no canonical/input
bootstrap cycle.  Numeric strings, source row order and legacy CSV formatting
are preserved; the formatting registry contains no observation values.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from pkinv.assets import resolve
from pkinv.paths import ROOT

FORMATS = "data/compatibility_view_formats.json"
INPUTS = (
    "aviation/fuel_sales", "fugitives/anchor_activity",
    "residential/fuel_supply_observations", "residential/fuel_supply_annotations",
    "ippu/company_production", "ippu/company_production_evidence", "ippu/company_roster",
)


def _path(name, root):
    return Path(resolve(os.path.join(root, "data/activity", name + ".csv"), root=root))


def _read(name, root):
    with _path(name, root).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def aviation_fuel_rows(root=ROOT):
    return [{"fiscal_year": row["fiscal_year"], "fiscal_year_label": "2023-24",
             "customer_category": row["customer_category"], "fuel_type": row["fuel_type"],
             "tonnes": row["tonnes"], "preliminary_ipcc_assignment": "UNRESOLVED",
             "source": row["source"], "source_url": row["source_url"],
             "source_note": row["source_note"]}
            for row in _read("aviation/fuel_sales", root) if row["fiscal_year"] == "2023"]


def _unique(rows, fields):
    result = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in result:
            raise ValueError("duplicate maintained observation: %r" % (key,))
        result[key] = row
    return result


def view_rows(root=ROOT):
    """Return legacy rows without consulting any generated compatibility view."""
    views = {"aviation/fuel_controls_2023_24": aviation_fuel_rows(root)}
    anchors = _read("fugitives/anchor_activity", root)
    _unique(anchors, ("fiscal_year", "activity_id"))
    unknown = {row["fiscal_year"] for row in anchors} - {"2022", "2023", "2024"}
    if unknown:
        raise ValueError("anchor compatibility views require an explicit mapping for " + str(unknown))
    views["fugitives/anchor_activity_2021_23"] = [r for r in anchors if r["fiscal_year"] != "2024"]
    views["fugitives/anchor_activity_2023_24"] = [
        {k: v for k, v in r.items() if k != "fiscal_year"}
        for r in anchors if r["fiscal_year"] == "2024"]

    supply = _unique(_read("residential/fuel_supply_observations", root), ("fiscal_year", "fuel"))
    annotations = _read("residential/fuel_supply_annotations", root)
    _unique(annotations, ("view_id", "source_row"))
    for name in ("residential/fuel_supply", "residential/fuel_supply_history"):
        selected = sorted((r for r in annotations if r["view_id"] == name), key=lambda r: int(r["source_row"]))
        views[name] = [{**r, **supply[(r["fiscal_year"], r["fuel"])]} for r in selected]

    production = _unique(_read("ippu/company_production", root), ("observation_id", "measure"))
    by_observation = {}
    for (observation, measure), fact in production.items():
        if fact["unit"] != "tonne" or fact["period_basis"] != "fiscal":
            raise ValueError("company production views require fiscal observations in tonnes")
        row = by_observation.setdefault(observation, {})
        row[measure + "_t"] = fact["value"]
    evidence = _read("ippu/company_production_evidence", root) + _read("ippu/company_roster", root)
    _unique(evidence, ("view_id", "source_row"))
    for name in ("ippu/company_clinker_2023_24", "ippu/company_clinker_series", "ippu/cement_producer_census_2023_24"):
        selected = sorted((r for r in evidence if r["view_id"] == name), key=lambda r: int(r["source_row"]))
        output = []
        for annotation in selected:
            observation = annotation["observation_id"]
            facts = [r for (key, _), r in production.items() if key == observation]
            reported = set(filter(None, annotation["reported_measures"].split(";")))
            if any((r["company"], r["period_end_year"]) !=
                                (annotation["company"], annotation["period_end_year"]) for r in facts):
                raise ValueError("company evidence does not match observation " + observation)
            values = by_observation.get(observation, {})
            if any(measure + "_t" not in values for measure in reported):
                raise ValueError("reported company measure has no maintained fact: " + observation)
            output.append({**annotation, **{measure + "_t": values[measure + "_t"] for measure in reported}})
        views[name] = output
    return views


def _record(values, style):
    quoted = set(style.get("quoted", ()))
    def cell(value, index):
        value = str(value)
        if index in quoted or any(c in value for c in ',"\r\n'):
            return '"' + value.replace('"', '""') + '"'
        return value
    return style.get("before", "") + ",".join(cell(value, i) for i, value in enumerate(values)) + style.get("newline", "\r\n")


def render(root=ROOT):
    with open(resolve(os.path.join(root, FORMATS), root=root), encoding="utf-8") as handle:
        formats = json.load(handle)["views"]
    views = view_rows(root)
    if set(views) != set(formats):
        raise ValueError("compatibility view/format registry mismatch")
    result = {}
    for name, rows in views.items():
        spec = formats[name]
        fields, styles = spec["fields"], spec["records"]
        text = _record(fields, styles[0])
        for i, row in enumerate(rows, 1):
            style = styles[i] if i < len(styles) else {"newline": styles[0]["newline"]}
            text += _record([row.get(field, "") for field in fields], style)
        result[name] = (text + spec.get("after", "")).encode("utf-8")
    return result


def build(root=ROOT, *, check=False):
    changed = []
    for name, payload in render(root).items():
        path = _path(name, root)
        if path.exists() and path.read_bytes() == payload:
            continue
        changed.append(name)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(payload)
            temporary.replace(path)
    if check and changed:
        raise ValueError("stale compatibility views: " + ", ".join(changed))
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = build(check=args.check)
    print("Compatibility input views: %d changed" % len(changed))


if __name__ == "__main__":
    main()
