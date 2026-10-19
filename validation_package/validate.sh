#!/bin/sh
# PakEmis national validation package - the validation command.
#
#   ./validate.sh --quick   integrity (SHA-256 of every packaged file), schemas and primary
#                           keys, the presentation-layer identity, and the arithmetic closure
#                           tests (annual, twelve-month, spatial, draw-wise, cross-sector)
#   ./validate.sh --full    the complete test suite of the release, unmodified, plus the
#                           package's own tests - SELF-CONTAINED: tests that need a source
#                           document the package registers and does not carry skip by name
#                           ("document vault not mounted: ...", counted in the summary)
#   ./validate.sh --documents DIR
#                           the documents gate (rc42): the same suite over an overlay of
#                           this package in which sources/, data/raw/ and data/cache/ are
#                           DIR's - a vault the maintainer holds and hands over privately,
#                           verified file by file against data/raw_manifest.csv. Without a
#                           DIR the gate reports itself not executed (exit 3), never green.
#
# Runs OFFLINE: an unroutable proxy is exported so any network attempt fails loudly instead
# of silently fetching. Runs against the packaged canonical outputs and never writes into
# them; writes are logs/ and deterministic canonical inputs under data/canonical/.
#
# ENVIRONMENT. The engine and most of the suite run on the Python 3 standard library. The
# gridded, parquet and common-draw tests need the packages in environment/requirements.lock;
# a test whose package is absent SKIPS and the skip is counted in logs/test_summary.json, so
# a run without them is a smaller witness, not a false green. environment/container/Dockerfile
# is the fully provisioned environment.
#
# Every step's exit code is recorded in logs/exit_codes.txt and logs/command_timings.csv.
# The script exits non-zero if ANY step failed, after running all of them.
set -u

ROOT=$(cd "$(dirname "$0")" && pwd)
MODE="${1:---quick}"
VAULT="${2:-}"
PYTHON="${PYTHON:-python3}"
export PKINV_ROOT="$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT/tests${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
export http_proxy="http://127.0.0.1:9" https_proxy="http://127.0.0.1:9"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy" no_proxy="" NO_PROXY=""
unset FIRMS_MAP_KEY

mkdir -p "$ROOT/logs"
case "$MODE" in
  --quick) LOG="$ROOT/logs/quick_validation.log" ;;
  --full)  LOG="$ROOT/logs/full_validation.log" ;;
  --documents) LOG="$ROOT/logs/documents_validation.log" ;;
  *) echo "usage: $0 --quick | --full | --documents DIR" >&2; exit 2 ;;
esac
if [ "$MODE" = "--documents" ]; then
  : > "$LOG"
  if [ -z "$VAULT" ] || [ ! -d "$VAULT" ]; then
    echo "DOCUMENTS GATE: not executed - no source vault mounted (usage: $0 --documents DIR)" | tee -a "$LOG"
    echo "--documents not-executed exit=3" >> "$ROOT/logs/exit_codes.txt"
    exit 3
  fi
  # the overlay: every package entry linked, the three document trees pointed at the vault
  OVERLAY=$(mktemp -d "${TMPDIR:-/tmp}/pakemis-documents.XXXXXX")
  for entry in "$ROOT"/* "$ROOT"/.[!.]*; do
    name=$(basename "$entry")
    case "$name" in data|sources|logs) ;; *) ln -s "$entry" "$OVERLAY/$name" ;; esac
  done
  mkdir -p "$OVERLAY/data" "$OVERLAY/logs"
  for entry in "$ROOT"/data/* "$ROOT"/data/.[!.]*; do
    [ -e "$entry" ] || continue
    name=$(basename "$entry")
    case "$name" in raw|cache) ;; *) ln -s "$entry" "$OVERLAY/data/$name" ;; esac
  done
  [ -d "$VAULT/sources" ] && ln -s "$VAULT/sources" "$OVERLAY/sources"
  [ -d "$VAULT/data/raw" ] && ln -s "$VAULT/data/raw" "$OVERLAY/data/raw"
  [ -d "$VAULT/data/cache" ] && ln -s "$VAULT/data/cache" "$OVERLAY/data/cache"
  export PKINV_ROOT="$OVERLAY"
  export PYTHONPATH="$OVERLAY/src:$OVERLAY/tests${PYTHONPATH:+:$PYTHONPATH}"
  echo "DOCUMENTS GATE over $OVERLAY (vault: $VAULT)" | tee -a "$LOG"
  $PYTHON "$OVERLAY/tests/validation/verify_vault.py" "$OVERLAY" >> "$LOG" 2>&1 || { echo "vault does not verify against data/raw_manifest.csv - see logs/documents_validation.log" | tee -a "$LOG"; exit 1; }
  $PYTHON -m pkinv.activity.build >> "$LOG" 2>&1 || { echo "canonical input bootstrap failed" | tee -a "$LOG"; exit 1; }
  $PYTHON "$OVERLAY/tests/validation/run_suite.py" "$OVERLAY" >> "$LOG" 2>&1
  code=$?
  cp "$OVERLAY/logs/test_summary.json" "$ROOT/logs/documents_test_summary.json" 2>/dev/null
  echo "--documents full-suite exit=$code" >> "$ROOT/logs/exit_codes.txt"
  echo "finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
  rm -rf "$OVERLAY"
  [ "$code" -eq 0 ] && echo "DOCUMENTS GATE: every step passed" | tee -a "$LOG" || echo "DOCUMENTS GATE: FAILED" | tee -a "$LOG"
  exit $code
fi
: > "$LOG"
TIMINGS="$ROOT/logs/command_timings.csv"
[ -f "$TIMINGS" ] || echo "mode,step,command,seconds,exit_code" > "$TIMINGS"
FAILED=0

step() {
  # step <name> <command...>: run, tee into the log, record the exit code and the time.
  name="$1"; shift
  echo "== $name" | tee -a "$LOG"
  echo "   $*" >> "$LOG"
  start=$(date +%s)
  "$@" >> "$LOG" 2>&1
  code=$?
  end=$(date +%s)
  printf '%s,%s,"%s",%d,%d\n' "$MODE" "$name" "$*" $((end - start)) "$code" >> "$TIMINGS"
  echo "$MODE $name exit=$code" >> "$ROOT/logs/exit_codes.txt"
  if [ "$code" -ne 0 ]; then
    FAILED=1
    echo "   FAILED (exit $code) - see logs/$(basename "$LOG")" | tee -a "$LOG"
  else
    echo "   ok ($((end - start)) s)" | tee -a "$LOG"
  fi
}

echo "PakEmis validation package: $MODE" | tee -a "$LOG"
echo "root:     $ROOT" | tee -a "$LOG"
echo "python:   $($PYTHON --version 2>&1)" | tee -a "$LOG"
echo "platform: $(uname -srm)" | tee -a "$LOG"
echo "started:  $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
echo | tee -a "$LOG"

$PYTHON -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || { echo "Python 3.10 or newer is required" | tee -a "$LOG"; exit 2; }

# 1. INTEGRITY: every packaged file against SHA256SUMS (stdlib, no sha256sum binary needed).
step "integrity"  $PYTHON "$ROOT/tests/validation/check_sha256sums.py" "$ROOT"

# Canonical CSVs are reproducible from the deposited extracts and field schemas.
# Prepare them before any test or semantic reader invokes a model adapter.
step "canonical-inputs"  $PYTHON -m pkinv.activity.build
[ "$FAILED" -eq 0 ] || exit 1

# 2. IDENTITY, SCHEMAS, KEYS, COUNTS: the package's own tests.
step "package-tests"  $PYTHON -m unittest discover -s "$ROOT/tests/validation" -t "$ROOT/tests" -p "test_*.py"

# 2b. THE SEMANTIC CONTRACT (v1.0.0): outputs/semantic/ re-derives byte for byte from the
# products it names, and its digests are the release manifest's.
step "semantic-contract"  $PYTHON -m pkinv.semantic.build --check

if [ "$MODE" = "--quick" ]; then
  # 3. ARITHMETIC: the closure tests of the release suite, module by module.
  for module in \
      test_atomic_annual test_annual_product test_national_rollup test_national_series \
      test_monthly test_monthly_all_years test_monthly_coverage \
      test_grid_cube test_adm2 test_adm2_fractions test_spatial_decomposition test_spatial_exceptions \
      test_common_ensemble test_mc_draws test_uncertainty_reconciliation test_joint_uncertainty_reconciles \
      test_configuration_keys test_national_configurations test_axis_register \
      test_category_ledger test_gas_closure test_n_ledger test_residue_ledger test_unallocated_controls \
      test_completeness_mass test_coverage_matrix test_ne_categories test_method_registry test_source_streams \
      test_transcription_checks test_deposit_licensing test_claims_registry \
      test_semantic_release test_golden; do
    step "arithmetic:$module"  $PYTHON -m unittest discover "$ROOT/tests" -p "$module.py"
  done
else
  # 3. THE WHOLE SUITE, as the release runs it (python3 -m unittest discover tests).
  step "full-suite"  $PYTHON "$ROOT/tests/validation/run_suite.py" "$ROOT"
fi

$PYTHON "$ROOT/tests/validation/summarise_logs.py" "$ROOT" "$MODE" >> "$LOG" 2>&1 || FAILED=1

echo | tee -a "$LOG"
echo "finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
if [ "$FAILED" -ne 0 ]; then
  echo "VALIDATION $MODE: ONE OR MORE STEPS FAILED - compare against KNOWN_EXCEPTIONS.json" | tee -a "$LOG"
  exit 1
fi
echo "VALIDATION $MODE: every step passed" | tee -a "$LOG"
exit 0
