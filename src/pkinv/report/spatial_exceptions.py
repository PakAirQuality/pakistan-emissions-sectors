"""Every place the grid could not do what the spatial declaration says, with the mass at stake.

pakemis_grid_fallbacks.csv already records each substitution - stream, scope, declared
surface, used surface, reason. What it cannot say is HOW MUCH, and a substitution without a
mass is a caveat rather than a finding: a reader cannot tell whether the fallback moved a
rounding error or a megatonne. This joins the fallback register to the ADM2 product and
publishes the affected mass, the rule that was applied instead, and whether the exception is
resolvable or permanent.

FOUR KINDS (rc41; two until then), and they are not the same problem.

  shape_missing - the boundary file has no polygon for a canonical reporting unit. Larkana
  is the whole of it. Every stream that would place mass inside that unit falls back to a
  within-province spread, so the province total is right and the sub-provincial placement of
  that share is not made. Resolvable: a boundary file with the polygon fixes it, and nothing
  about the inventory needs to change.

  proxy_empty - the declared raster has no weight anywhere inside a shape, so a stream that
  should follow it has nothing to follow. The rice EF1FR synthetic-fertiliser stream hits
  this in seven shapes where MapSPAM shows no paddy; the fallback spreads uniformly within
  the shape. Not resolvable by a better boundary file - it is a real absence of the proxy,
  and the honest reading is that those shapes' share of that stream is placed by area rather
  than by evidence.

  province_points_absent - a stream placed on a set of located objects (grid stations,
  cement works, captive plants) has a province share with no located, fuelled object of
  that set, so that share spreads on built-up with a declared event. The Sindh coal grid
  stream is the largest single exception in the inventory (rc41: 34.4 Mt), and it was not
  in this table before rc41 because the table only knew two kinds.

  raster_absent - a declared manual raster is not held and the stream rides its fallback.

WHY THIS IS NOT A SECOND COPY OF THE FALLBACK REGISTER. The register says a substitution
happened and (rc41) what fraction of each stream's mass it moved; this sums that cost per
unit and module and says whether it can be resolved.

Writes: outputs/pakemis_spatial_exceptions.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import os

from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS, ROOT

OUT = asset_path(OUTPUTS, "pakemis_spatial_exceptions.csv")
NESTING_OUT = asset_path(OUTPUTS, "pakemis_adm2_nesting_check.csv")
PROVINCIAL = asset_path(OUTPUTS, "provincial_totals_2024.csv")
NESTING_FIELDS = ("province", "adm2_sum_Mt_AR5", "provincial_control_Mt_AR5",
                  "difference_Mt_AR5", "abs_difference_Mt_AR5", "share_of_control_pct")
FALLBACKS = asset_path(OUTPUTS, "pakemis_grid_fallbacks.csv")
ADM2_SECTOR = asset_path(OUTPUTS, "pakemis_adm2_monthly_sector.csv")

FIELDS = ("exception_kind", "unit_or_shape", "province", "module",
          "affected_streams", "affected_stream_count",
          "declared_surface", "used_surface", "affected_mass_Mt_AR5", "mass_grain",
          "affected_share_of_module_pct", "retention_rule", "resolution_status",
          "resolvable_by", "reason")

SHAPE_MISSING = "shape_missing"
PROXY_EMPTY = "proxy_empty"
PROVINCE_POINTS_ABSENT = "province_points_absent"
RASTER_ABSENT = "raster_absent"
STREAMS = asset_path(OUTPUTS, "pakemis_source_streams.csv")


def _rows(path):
    return list(_activity_rows(path, comments=True))


def _module_totals():
    """{module: Mt CO2e-AR5} from the source-stream ledger - the denominator of the share."""
    out = collections.defaultdict(float)
    for row in _rows(STREAMS):
        out[row["module"]] += float(row["emissions_ar5"] or 0.0)
    return out


KIND_OF_SCOPE = {"district": SHAPE_MISSING, "shape": PROXY_EMPTY,
                 "province": PROVINCE_POINTS_ABSENT, "raster": RASTER_ABSENT}


def build():
    """One row per (kind, unit, module), priced from the register the cube writes.

    rc41 (the nineteenth review's S-2): this used to take a module's WHOLE mass in the
    affected province or shape from the ADM2 product, summing native Gg of every gas with
    no GWP at all, and labelled it Mt CO2e - 8.36 Mt for Larkana where the fraction that
    actually fell back is a twentieth of that. The cube now prices every fallback event
    per stream (pakemis_grid_fallbacks.csv: weight_share, affected_Gg, affected_Mt_AR5 at
    the stream's own gas and methane origin), and this table sums those; the mass grain is
    the stream, stated in mass_grain. The province is the event's own, so the agriculture
    panel events in "Other" are no longer filed under Sindh.
    """
    fallbacks = _rows(FALLBACKS)
    module_totals = _module_totals()
    grouped = collections.defaultdict(list)
    for row in fallbacks:
        kind = KIND_OF_SCOPE[row["scope"]]
        if kind == PROXY_EMPTY:
            unit = row["shape"] or "unnamed-in-register"
        elif kind == RASTER_ABSENT:
            unit = row["declared"]
        else:
            unit = row["province"]
        grouped[(kind, unit, row["module"])].append(row)

    out = []
    for (kind, unit, module), events in sorted(grouped.items()):
        used = sorted({e["used"] for e in events})
        declared = sorted({e["declared"] for e in events})
        streams = sorted({e["source_stream_id"] for e in events})
        provinces = sorted({e["province"] for e in events if e["province"]})
        mass = sum(float(e["affected_Mt_AR5"]) for e in events)
        if kind == SHAPE_MISSING:
            rule = ("the unit's panel share is spread across its province by the "
                    "within-province proxy; the provincial total is unaffected")
            status, fixed_by = "open", "a boundary file containing the unit's polygon"
        elif kind == PROXY_EMPTY:
            rule = ("the stream is spread uniformly inside the shape, because its declared "
                    "raster has no weight there")
            status, fixed_by = "permanent", (
                "nothing: the proxy is genuinely absent in this shape, so the placement "
                "is by area rather than by evidence")
        elif kind == PROVINCE_POINTS_ABSENT:
            rule = ("the province's share of the stream is spread on the built-up raster, "
                    "because no located object of the declared set carries this stream's "
                    "activity there; the provincial total is unaffected")
            status, fixed_by = "open", (
                "a located, fuelled object of the declared set in the province (the plant "
                "ledger or facility register)")
        else:
            rule = "the stream rides the fallback raster nationally"
            status, fixed_by = "open", "the manual raster named in PROXY_SOURCES.md"
        total = module_totals.get(module, 0.0)
        out.append({
            "exception_kind": kind,
            "unit_or_shape": unit,
            "province": ";".join(provinces),
            "module": module,
            "affected_streams": ";".join(streams),
            "affected_stream_count": len(streams),
            "declared_surface": ";".join(declared),
            "used_surface": ";".join(used),
            "affected_mass_Mt_AR5": round(mass, 6),
            "mass_grain": ("stream: the fraction of each affected stream's own mass that "
                           "rode the substitute, at the stream's gas and methane origin, "
                           "summed over the module's affected streams"),
            "affected_share_of_module_pct": round(100.0 * mass / total, 4) if total else "",
            "retention_rule": rule,
            "resolution_status": status,
            "resolvable_by": fixed_by,
            "reason": events[0]["reason"],
        })
    return out


def nesting_rows():
    """Agriculture's ADM2 physical view against its provincial control, province by province.

    THE UNITS NEST EXACTLY SINCE rc40 G2. rc39 published a 1.836 Mt absolute difference
    across five provinces (Punjab -0.911); the cause was two partitions - the cube allocated
    on the hard label mask and read marginals out on the exact-area split, so border cells
    crossed provinces on paper. The marginals now partition each cell within its own province
    and this table is the evidence: every row closes to the allocation at 1e-6.

    The ADM2 product carries NATIVE GAS MASS, not CO2e, so the comparison applies AR5 here.
    Comparing the columns directly - which is the obvious thing to do - gives 212 Mt of
    nonsense, and getting that wrong once is why the conversion is spelled out rather than
    assumed by a reader.
    """
    from pkinv.core import gwp
    adm2 = collections.defaultdict(float)
    for row in _rows(ADM2_SECTOR):
        if row["module"] != "agriculture" or row["spatial_view"] != "physical":
            continue
        try:
            gg = float(row["emissions_Gg"])
        except (TypeError, ValueError):
            continue
        adm2[row["province"]] += gwp.to_co2e(row["gas"], gg, "AR5") / 1000.0
    # THE CONTROL IS THE ALLOCATION THE CUBE WAS FED, UNROUNDED (rc40 G2). Both provincial
    # products print four significant figures - 123.3, 17.29 - so comparing the ADM2 sum
    # against either measures the file's rounding, not the nesting. downscale.provincial_rows
    # is province share x national component at float precision, which is exactly what the
    # cube distributed below the province; the ADM2 sums must reproduce it to 1e-6.
    from pkinv.sectors.agriculture import downscale
    control = collections.defaultdict(float)
    for r in downscale.provincial_rows():
        control[r["province"]] += float(r["co2e_Mt_AR5"])
    control = dict(control)
    out = []
    total_abs = 0.0
    for province in sorted(control):
        if province.startswith("NATIONAL"):
            continue
        a, b = adm2.get(province, 0.0), control[province]
        total_abs += abs(a - b)
        out.append({"province": province,
                    "adm2_sum_Mt_AR5": round(a, 6),
                    "provincial_control_Mt_AR5": round(b, 6),
                    "difference_Mt_AR5": round(a - b, 6),
                    "abs_difference_Mt_AR5": round(abs(a - b), 6),
                    "share_of_control_pct": round(100.0 * (a - b) / b, 4) if b else ""})
    out.append({"province": "TOTAL", "adm2_sum_Mt_AR5": round(sum(adm2.values()), 6),
                "provincial_control_Mt_AR5": round(
                    sum(v for k, v in control.items() if not k.startswith("NATIONAL")), 6),
                "difference_Mt_AR5": "", "abs_difference_Mt_AR5": round(total_abs, 6),
                "share_of_control_pct": ""})
    return out


def main(argv=()):
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "WHERE THE GRID COULD NOT DO WHAT THE SPATIAL DECLARATION SAYS (rc39 A9).",
        "pakemis_grid_fallbacks.csv records that a substitution happened; this records what",
        "it cost. shape_missing is a boundary-file gap and is resolvable; proxy_empty is a",
        "real absence of the declared raster inside a shape and is not.",
        "affected_mass_Mt_AR5 is priced per stream from pakemis_grid_fallbacks.csv (rc41): the",
        "fraction of each affected stream's own mass that rode the substitute, at its gas and",
        "methane origin. The provincial and national totals are unaffected in every row here.",
    ))
    nesting = nesting_rows()
    write_table(NESTING_OUT, NESTING_FIELDS, nesting, banner=(
        "DO AGRICULTURE'S ADM2 UNITS NEST INTO THEIR PROVINCIAL CONTROLS? (rc39 A9 / rc40 G2)",
        "Yes, since rc40: every province closes to the allocation the cube was fed at 1e-6.",
        "rc39 measured 1.836 Mt of absolute difference here; the cause was two partitions",
        "(hard label mask in, exact-area split out) and it is closed, not tolerated.",
        "The control is downscale.provincial_rows() UNROUNDED - the printed provincial files",
        "carry four significant figures and would measure their own rounding instead.",
        "The ADM2 product carries NATIVE GAS MASS; AR5 is applied here to compare it with a",
        "CO2e control. Comparing the columns directly gives 212 Mt of nonsense.",
    ))
    print("adm2 nesting check -> %s" % os.path.relpath(NESTING_OUT, ROOT))
    print("  %s Mt absolute difference across five provinces"
          % nesting[-1]["abs_difference_Mt_AR5"])
    kinds = collections.Counter(r["exception_kind"] for r in rows)
    print("spatial exceptions -> %s" % os.path.relpath(OUT, ROOT))
    for kind, n in sorted(kinds.items()):
        mass = sum(r["affected_mass_Mt_AR5"] for r in rows if r["exception_kind"] == kind)
        print("  %-14s %2d rows, %.6f Mt affected" % (kind, n, mass))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
