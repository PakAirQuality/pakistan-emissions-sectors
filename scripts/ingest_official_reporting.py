"""Materialize the six sectors' CRT workbook extracts; --check writes nothing."""
import argparse
import importlib

from pkinv.core.source_extracts import build_extract

PARSERS = {
    "power": ("extract",),
    "residential": ("extract",),
    "railways": ("extract",),
    "aviation": ("extract_crt", "extract_crt_audit"),
    "fugitives": ("extract_crt", "audit_cells"),
    "ippu": ("extract_summary", "extract_background", "extract_fgas_species", "audit_cells"),
}


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--check", action="store_true")
    options = args.parse_args()
    differences = []
    for sector, functions in PARSERS.items():
        module = importlib.import_module("pkinv.sectors.%s.official_reporting" % sector)
        for function in functions:
            parser = getattr(module, function)
            changed = build_extract(parser, check=options.check)
            differences.extend(changed)
            print("%s: %s" % (parser.extract_name, "differs" if changed and options.check
                               else "updated" if changed else "current"), flush=True)
    return int(options.check and bool(differences))


if __name__ == "__main__":
    raise SystemExit(main())
