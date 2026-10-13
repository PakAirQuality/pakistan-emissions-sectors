"""The unified validation layer (rc33).

One verdict vocabulary (verdicts.py), one catalog joining the registries
(data/validation_catalog.csv, built by pkinv.report.validation_catalog), one
scorecard over the (property x grain) space. Everything here READS the
existing validation products through adapters; producers migrate to the shared
vocabulary opportunistically, each migration a declared diff.
"""
