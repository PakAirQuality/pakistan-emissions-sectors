#!/usr/bin/env python3
"""Thin entry point for the species-resolved HFC bank (rc46 Wave 4).

The computation lives in pkinv.sectors.ippu.hfc_bank - see its docstring for why.

Usage:  python3 scripts/run_hfc_bank.py
Writes: outputs/ippu_hfc_species_bank.csv
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.sectors.ippu.hfc_bank import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
