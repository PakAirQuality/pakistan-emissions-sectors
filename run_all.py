#!/usr/bin/env python3
"""Repo-root shim: `python3 run_all.py` still works after the move into the package.

The orchestrator itself lives in src/pkinv/run_all.py so that `pip install` ships it and
the pakistan-ghg console script resolves. This file only forwards, and adds src/ to the
path first so a checkout runs without needing `pip install -e .`.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from pkinv.run_all import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
