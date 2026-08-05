#!/usr/bin/env bash
# Utilities JOB command helper (not a tile).
# Upload this + run_ai.sh + run_metadata.sh + lsdyna-doe.json
# + export_catalog_from_parent.py (auto-pulls Inputs from clonedFrom).
# Optional: mclaren_catalog.json override; else API uses clonedFrom parent.
# Job Command:
#   bash run_job_prep.sh
#
# Copies extractor launchers (and catalog if present) to /enc/tmp while
# work/shared is still visible, so post-job tiles can bash /enc/tmp/run_*.sh.

set -euo pipefail

export AUTOMATION_ANALYSIS=ls_dyna

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

# cp that no-ops when src and dst are the same inode (set -e safe).
safe_cp() {
  local src=$1 dst=$2
  if [ ! -f "$src" ]; then
    return 0
  fi
  if [ -e "$dst" ] && [ "$src" -ef "$dst" ]; then
    return 0
  fi
  cp -f "$src" "$dst"
}

SRC="."
if [ ! -f "$SRC/run_ai.sh" ] && [ -f "$HOME/work/shared/run_ai.sh" ]; then
  SRC="$HOME/work/shared"
fi

log "PWD=$PWD SRC=$SRC"
ls -la "$SRC/run_ai.sh" "$SRC/run_metadata.sh"

safe_cp "$SRC/run_ai.sh" /enc/tmp/run_ai.sh
safe_cp "$SRC/run_metadata.sh" /enc/tmp/run_metadata.sh
chmod +x /enc/tmp/run_ai.sh /enc/tmp/run_metadata.sh

# DOE catalog: prefer uploaded file; else pull Inputs from clonedFrom parent via API
# (Utilities clones keep clonedFrom=HFuKPb but drop Inputs — no per-job YAML needed)
if [ -f "$SRC/export_catalog_from_parent.py" ]; then
  safe_cp "$SRC/export_catalog_from_parent.py" /enc/tmp/export_catalog_from_parent.py
fi
if [ ! -f "$SRC/mclaren_catalog.json" ] && [ ! -f ./mclaren_catalog.json ]; then
  log "no uploaded mclaren_catalog.json — exporting from clonedFrom / SOURCE_JOB_ID"
  export RESCALE_API_BASE_URL="${RESCALE_API_BASE_URL:-https://eu.rescale.com}"
  py=""
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then py=$c; break; fi
  done
  if [ -n "$py" ] && [ -f /enc/tmp/export_catalog_from_parent.py ]; then
    "$py" /enc/tmp/export_catalog_from_parent.py || log "WARNING: catalog export failed"
  elif [ -n "$py" ] && [ -f "$SRC/export_catalog_from_parent.py" ]; then
    "$py" "$SRC/export_catalog_from_parent.py" || log "WARNING: catalog export failed"
  else
    log "WARNING: python / export_catalog_from_parent.py missing — DOE Inputs will not resolve"
  fi
fi

if [ -f ./mclaren_catalog.json ]; then
  SRC_CAT=./mclaren_catalog.json
elif [ -f "$SRC/mclaren_catalog.json" ]; then
  SRC_CAT="$SRC/mclaren_catalog.json"
else
  SRC_CAT=""
fi

if [ -n "$SRC_CAT" ]; then
  safe_cp "$SRC_CAT" ./mclaren_catalog.json
  safe_cp "$SRC_CAT" "$HOME/work/mclaren_catalog.json" || true
  safe_cp "$SRC_CAT" "$HOME/work/shared/mclaren_catalog.json" || true
  log "mclaren_catalog.json present for DOE knobs"
else
  log "WARNING: no mclaren_catalog.json — DOE Inputs will not resolve"
fi

if [ -f "$SRC/lsdyna-doe.json" ]; then
  safe_cp "$SRC/lsdyna-doe.json" ./lsdyna-doe.json
  safe_cp "$SRC/lsdyna-doe.json" "$HOME/work/lsdyna-doe.json" || true
fi

log "copied launchers to /enc/tmp:"
ls -la /enc/tmp/run_ai.sh /enc/tmp/run_metadata.sh

sleep 5
log "job prep done"
