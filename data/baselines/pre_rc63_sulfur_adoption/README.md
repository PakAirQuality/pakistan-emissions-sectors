# Baseline: the air panel immediately before the rc63 sulfur adoption

WHAT THIS IS. Four shipped products, copied byte-for-byte out of `outputs/` at the moment before
two sulfur centrals moved, so that the effect of that change can be measured against something
rather than described. `SHA256SUMS` pins all four.

WHY IT EXISTS AS A DIRECTORY AND NOT AS A COMMIT. The established tool,
`scripts/measure_spatial_rebase.py`, measured the working tree against `git show HEAD:...`. That
works when the change to be measured is the only uncommitted change. It does not work here: HEAD
predates this whole session, so a HEAD comparison would report every change since rc59 and not the
sulfur adoption. A reviewer put it correctly - waiting for a commit is a limitation of the tool,
not a property of the measurement, and two preserved states can be compared without either being a
commit. The measuring script now takes explicit `--baseline` and `--candidate` paths.

WHAT THE STATE IS. Booked at the time these were written:
  coal_punjab_fields    4.5 %  basis field_range     (two Punjab coalfields' RESOURCE ranges)
  power_rfo_spec_range  1.3229 % applied to the three power RFO classes
After the adoption:
  coal_punjab_fields    4.643 % basis measured_avg   (mean of three as-fired analyses)
  power_rfo_spec_range  retired; the power RFO classes cite fo_hsfo_grade_mix at 3.0 %

WHAT IT IS NOT. Not an independent regeneration. These files were produced by the engine as it
stood, and preserved; nobody has re-derived them from inputs since. Any comparison built on them is
a REPORTED SESSION RESULT with its inputs named, and should say so until the pre-adoption state can
be rebuilt from the register and re-checked against these digests.
