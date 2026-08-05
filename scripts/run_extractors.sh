#!/usr/bin/env bash
# In-job Utilities workaround: stage + run AI then Metadata on the host.
# Upload this file with the crash inputs. Job command:
#   export AUTOMATION_ANALYSIS=ls_dyna
#   bash run_extractors.sh
#
# Runs during the job (when ~/work is visible), not as post-job tiles.

set -euo pipefail

export AUTOMATION_ANALYSIS=ls_dyna

AI_IMG="631046354827.dkr.ecr.eu-central-1.amazonaws.com/deprod-rescale-automation-images-customer:automation-ai-extractor-0.1.12"
META_IMG="631046354827.dkr.ecr.eu-central-1.amazonaws.com/deprod-rescale-automation-images-customer:automation-metadata-extractor-0.2.14"
AI_STAGE="/enc/tmp/automation-ai-extractor"
META_STAGE="/enc/tmp/automation-metadata-extractor"
AI_PY="$AI_STAGE/python_venv/bin/python"
META_PY="$META_STAGE/python_venv/bin/python"
MAX_ATTEMPTS=5
SLEEP_SECONDS=10

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

resolve_work_root() {
  local root="$HOME/work/shared"
  if ! find "$root" -maxdepth 3 \( -name 'd3plot' -o -name 'd3plot*' -o -name 'binout*' \) 2>/dev/null | head -1 | grep -q .; then
    root="$HOME/work"
  fi
  cd "$root"
  pwd -P
}

wait_for_artifacts() {
  local root="$1"
  local i
  for i in $(seq 1 30); do
    if find "$root" -maxdepth 3 \( -name 'd3plot' -o -name 'd3plot[0-9]*' \) 2>/dev/null | head -1 | grep -q .; then
      log "found d3plot under $root"
      return 0
    fi
    log "waiting for d3plot under $root ($i/30)"
    sleep 2
  done
  log "FATAL: no d3plot under $root"
  return 1
}

stage_image() {
  local img="$1"
  local stage_dir="$2"
  local venv_py="$3"
  local i
  rm -rf "$stage_dir/python_venv"
  for i in $(seq 1 "$MAX_ATTEMPTS"); do
    log "stage $stage_dir attempt $i/$MAX_ATTEMPTS"
    if podman run --rm --userns=keep-id --env-host -v /enc/tmp:/enc/tmp "$img"; then
      if [ -x "$venv_py" ] && "$venv_py" -c 'import automation' >/dev/null 2>&1; then
        log "staged OK: $venv_py"
        return 0
      fi
      log "podman ok but venv incomplete"
    else
      log "podman stage failed"
    fi
    rm -rf "$stage_dir/python_venv"
    sleep "$SLEEP_SECONDS"
  done
  log "FATAL: could not stage $img"
  return 1
}

run_extractor() {
  local label="$1"
  local venv_py="$2"
  log "launching $label"
  "$venv_py" -m automation.main
  log "finished $label"
}

main() {
  log "HOME=$HOME PWD=$PWD RESCALE_WORK_PATH=${RESCALE_WORK_PATH-}"
  WORK_ROOT="$(resolve_work_root)"
  log "WORK_ROOT=$WORK_ROOT"
  export RESCALE_WORK_PATH="$WORK_ROOT"
  wait_for_artifacts "$WORK_ROOT"
  find "$WORK_ROOT" -maxdepth 3 \( -name 'd3plot' -o -name 'd3plot[0-9]*' -o -name 'binout*' \) 2>/dev/null | head -20 || true

  cd "$WORK_ROOT"

  stage_image "$AI_IMG" "$AI_STAGE" "$AI_PY"
  run_extractor "AI" "$AI_PY"

  stage_image "$META_IMG" "$META_STAGE" "$META_PY"
  run_extractor "Metadata" "$META_PY"

  for f in case_data.vtp rescale-ai.vtp job_metadata_fields.json; do
    if [ -f "$WORK_ROOT/$f" ]; then
      log "OK present: $f"
    else
      # also check shallow finds
      if find "$WORK_ROOT" -maxdepth 2 -name "$f" -print -quit | grep -q .; then
        log "OK present: $f"
      else
        log "FATAL: missing $f"
        exit 1
      fi
    fi
  done
  log "all extractors succeeded"
}

main "$@"
