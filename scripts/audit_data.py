"""Every committed data product has a producer, a document, or a declared reason.

The command-line face of pkinv.report.data_provenance - the data/ counterpart of
scripts/audit_outputs.py. The classes, the overrides and the output are documented there;
the build runs the same module as a phase, so this script exists for the operator who wants
the orphan list printed.

Usage:  python3 scripts/audit_data.py [--verbose]
Writes: outputs/pakemis_data_provenance.csv
Exit:   1 if any product is unregistered
"""
import sys

from pkinv.report.data_provenance import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
