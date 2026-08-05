#!/usr/bin/env bash
# Post-job tile launcher — Metadata Extractor [DEV] (EU)
# Tile Command:  bash /enc/tmp/run_metadata.sh
# Job prep must copy this file to /enc/tmp (see run_job_prep.sh).
#
# Stage via tile Container ECR auth, then run host glibc venv
# with RESCALE_WORK_PATH set to the dir that actually has d3plot.

set -euo pipefail

export AUTOMATION_ANALYSIS=ls_dyna

IMG="631046354827.dkr.ecr.eu-central-1.amazonaws.com/deprod-rescale-automation-images-customer:automation-metadata-extractor-0.2.14"
STAGE="/enc/tmp/automation-metadata-extractor"
VENV_PY="$STAGE/python_venv/bin/python"
LOCK="/enc/tmp/mclaren-extractor.lock"
MAX_ATTEMPTS=5
SLEEP_SECONDS=10

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

while ! mkdir "$LOCK" 2>/dev/null; do
  log "waiting for lock $LOCK"
  sleep 5
done
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

resolve_work_root() {
  local candidate
  for candidate in "$HOME/work" "$HOME/work/shared" "${RESCALE_WORK_PATH-}"; do
    [ -n "$candidate" ] || continue
    [ -d "$candidate" ] || continue
    if find "$candidate" -maxdepth 3 \( -name 'd3plot' -o -name 'd3plot[0-9]*' \) 2>/dev/null | head -1 | grep -q .; then
      (cd "$candidate" && pwd -P)
      return 0
    fi
  done
  if [ -d "$HOME/work" ]; then
    (cd "$HOME/work" && pwd -P)
    return 0
  fi
  echo "$HOME/work/shared"
}

log "HOME=$HOME PWD=$PWD RESCALE_WORK_PATH=${RESCALE_WORK_PATH-}"
WORK_ROOT="$(resolve_work_root)"
export RESCALE_WORK_PATH="$WORK_ROOT"
log "WORK_ROOT=$WORK_ROOT"
find "$WORK_ROOT" -maxdepth 3 \( -name 'd3plot' -o -name 'd3plot[0-9]*' -o -name 'binout*' \) 2>/dev/null | head -20 || true

env | grep -E '^RESCALE.*|^USER|^HOME' > /enc/tmp/mclaren-meta.env.list

rm -rf "$STAGE/python_venv"
i=1
while [ "$i" -le "$MAX_ATTEMPTS" ]; do
  log "stage attempt $i/$MAX_ATTEMPTS"
  if podman run --rm --userns=keep-id --env-file /enc/tmp/mclaren-meta.env.list -v /enc/tmp:/enc/tmp "$IMG"; then
    if [ -x "$VENV_PY" ] && "$VENV_PY" -c 'import automation' >/dev/null 2>&1; then
      log "staged OK"
      break
    fi
    log "stage incomplete"
  else
    log "stage podman failed"
  fi
  rm -rf "$STAGE/python_venv"
  i=$((i + 1))
  sleep "$SLEEP_SECONDS"
done

if ! [ -x "$VENV_PY" ]; then
  log "FATAL: missing $VENV_PY"
  exit 1
fi

log "launching Metadata on host from $WORK_ROOT"
cd "$WORK_ROOT"
"$VENV_PY" -m automation.main
log "Metadata extractor finished"
