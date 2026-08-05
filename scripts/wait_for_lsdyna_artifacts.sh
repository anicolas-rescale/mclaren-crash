#!/usr/bin/env bash
# Wait until LS-DYNA / PSA inputs are visible in the job work dir, then copy
# them into extract_inputs/ so post-process tiles still see artifacts after
# Utilities may clear staged input files from the work root.
#
# Upload this script with the job inputs, then set the Rescale command to:
#   bash wait_for_lsdyna_artifacts.sh
#
# Optional env:
#   WAIT_TIMEOUT_SEC   max wait (default 3600)
#   WAIT_POLL_SEC      poll interval (default 10)
#   WAIT_SETTLE_SEC    sleep after ready (default 30)
#   EXTRACT_KEEP_DIR   materialize dir (default extract_inputs)
#   AUTOMATION_ANALYSIS  forced to ls_dyna if unset

set -euo pipefail

export AUTOMATION_ANALYSIS="${AUTOMATION_ANALYSIS:-ls_dyna}"

TIMEOUT_SEC="${WAIT_TIMEOUT_SEC:-3600}"
POLL_SEC="${WAIT_POLL_SEC:-10}"
SETTLE_SEC="${WAIT_SETTLE_SEC:-30}"
KEEP_DIR="${EXTRACT_KEEP_DIR:-extract_inputs}"

echo "cwd=$(pwd)"
echo "AUTOMATION_ANALYSIS=${AUTOMATION_ANALYSIS}"
echo "Waiting up to ${TIMEOUT_SEC}s for d3plot, binout*, results.json, lsdyna-doe.json ..."

start_ts=$(date +%s)
while true; do
  now_ts=$(date +%s)
  elapsed=$((now_ts - start_ts))

  d3plot_ok=0
  binout_ok=0
  results_ok=0
  doe_ok=0
  [ -f d3plot ] && d3plot_ok=1
  if ls binout* >/dev/null 2>&1; then
    binout_ok=1
  fi
  [ -f results.json ] && results_ok=1
  [ -f lsdyna-doe.json ] && doe_ok=1

  if [ "${d3plot_ok}" -eq 1 ] && [ "${binout_ok}" -eq 1 ] \
    && [ "${results_ok}" -eq 1 ] && [ "${doe_ok}" -eq 1 ]; then
    echo "Artifacts ready after ${elapsed}s:"
    ls -lh d3plot results.json lsdyna-doe.json 2>/dev/null || true
    ls -lh binout* 2>/dev/null | head -40 || true
    break
  fi

  if [ "${elapsed}" -ge "${TIMEOUT_SEC}" ]; then
    echo "ERROR: timed out after ${elapsed}s waiting for artifacts" >&2
    echo "  d3plot=${d3plot_ok} binout=${binout_ok} results=${results_ok} doe=${doe_ok}" >&2
    echo "--- ls -la (head) ---" >&2
    ls -la | head -80 >&2 || true
    exit 1
  fi

  echo "$(date -u +%H:%M:%S) waiting ${elapsed}s ... d3plot=${d3plot_ok} binout=${binout_ok} results=${results_ok} doe=${doe_ok}"
  sleep "${POLL_SEC}"
done

echo "Settling ${SETTLE_SEC}s for sibling files ..."
sleep "${SETTLE_SEC}"

# Materialize copies as command-written outputs. Extractors rglob for d3plot /
# binout / DOE / results.json, so a subdirectory is enough if the work root
# input staging is cleared before post-job tiles run.
echo "Materializing artifacts into ${KEEP_DIR}/ ..."
rm -rf "${KEEP_DIR}"
mkdir -p "${KEEP_DIR}"

copy_glob() {
  local pattern="$1"
  # shellcheck disable=SC2086
  if ls ${pattern} >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    cp -a ${pattern} "${KEEP_DIR}/"
  fi
}

copy_glob "d3plot"
copy_glob "d3plot[0-9]*"
copy_glob "binout*"
copy_glob "results.json"
copy_glob "lsdyna-doe.json"
copy_glob "*.csv"
copy_glob "probe_map.json"
copy_glob "scorecard_field_map.json"
copy_glob "mclaren_catalog.json"

echo "Materialized $(find "${KEEP_DIR}" -type f | wc -l | tr -d ' ') files:"
ls -lh "${KEEP_DIR}" | head -60

# Sanity: extractors must be able to see a d3plot under KEEP_DIR
if [ ! -f "${KEEP_DIR}/d3plot" ]; then
  echo "ERROR: ${KEEP_DIR}/d3plot missing after materialize" >&2
  exit 1
fi

echo "Handing off to post-process automations."
