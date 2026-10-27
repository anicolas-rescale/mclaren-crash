#!/usr/bin/env bash
# McLaren Side-Pole — workstation mesh-inference hotfix (LATEST / 2.1.12)
#
# Lives on shared HPS wtaTdb:
#   ~/storage_wtaTdb/shared/mclaren-ws-patches/mclaren_ws_mesh_inference_hotfix.sh
#   ~/storage_wtaTdb/shared/mclaren-ws-patches/inference_runner_transient.py.patched-2.1.12
#
# Roberto / Andy one-liner (Training WS with wtaTdb attached):
#   bash ~/storage_wtaTdb/shared/mclaren-ws-patches/mclaren_ws_mesh_inference_hotfix.sh
# Then hard-refresh AI Physics UI → P35_OS_Side_Pole_Model02 → Inference.
#
# Prod 2.1.12 is often a protected/sourceless wheel (no .py to sed). This script:
#   - If inference_runner_transient.py exists: patch in place (outvar_ts_keys=[] + tuple unpack)
#   - If missing: drop the bundled patched 2.1.12 .py into site-packages (overrides .pyc)
#
# Mesh/knobs only — not probe curves in Inference UI.
# Flags: --dry-run | --no-restart | -h

set -euo pipefail

log()  { printf '[mclaren-mesh-hotfix] %s\n' "$*"; }
warn() { printf '[mclaren-mesh-hotfix] WARN: %s\n' "$*" >&2; }
die()  { printf '[mclaren-mesh-hotfix] ERROR: %s\n' "$*" >&2; exit 1; }

DRY_RUN=0
RESTART=1
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --no-restart) RESTART=0 ;;
    -h|--help)
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *) die "Unknown arg: $arg (use --dry-run | --no-restart)" ;;
  esac
done

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PATCHED_NAME="inference_runner_transient.py.patched-2.1.12"
MARKER="mclaren-mesh-hotfix"

# --- locate package ----------------------------------------------------------
resolve_program_path() {
  local cand
  if [[ -n "${PROGRAM_PATH:-}" && -d "$PROGRAM_PATH" ]]; then
    echo "$PROGRAM_PATH"
    return 0
  fi
  for cand in /program/rescale-ai-2.1.12 /program/rescale-ai-2.1.13; do
    [[ -d "$cand" ]] && { echo "$cand"; return 0; }
  done
  cand=$(ls -d /program/rescale-ai-* 2>/dev/null | sort -V | tail -1 || true)
  [[ -n "$cand" && -d "$cand" ]] || return 1
  echo "$cand"
}

PROGRAM_PATH="$(resolve_program_path)" || die "No /program/rescale-ai-* found. Is this an AI Physics Training workstation?"
log "Package: $PROGRAM_PATH"

# --- locate site-packages core dir + optional existing .py -------------------
find_core_dir() {
  local hit
  shopt -s nullglob
  for hit in "$PROGRAM_PATH"/venv/lib/python*/site-packages/rescale_ai/inference/core; do
    if [[ -d "$hit" ]]; then
      echo "$hit"
      shopt -u nullglob
      return 0
    fi
  done
  shopt -u nullglob
  hit=$(find "$PROGRAM_PATH" -type d -path '*/site-packages/rescale_ai/inference/core' 2>/dev/null | head -1 || true)
  [[ -n "$hit" && -d "$hit" ]] || return 1
  echo "$hit"
}

CORE_DIR="$(find_core_dir)" || die "rescale_ai/inference/core not found under $PROGRAM_PATH"
RUNNER="$CORE_DIR/inference_runner_transient.py"
log "Core dir: $CORE_DIR"

find_patched_payload() {
  local hit
  for hit in \
    "$SCRIPT_DIR/$PATCHED_NAME" \
    "$HOME/storage_wtaTdb/shared/mclaren-ws-patches/$PATCHED_NAME" \
    /enc/*/storage_wtaTdb/shared/mclaren-ws-patches/"$PATCHED_NAME" \
    "$HOME/work/shared/mclaren-ws-patches/$PATCHED_NAME"
  do
    # shellcheck disable=SC2086
    for path in $hit; do
      if [[ -f "$path" ]]; then
        echo "$path"
        return 0
      fi
    done
  done
  return 1
}

PY_BIN=""
for cand in "$PROGRAM_PATH/venv/bin/python3" "$PROGRAM_PATH/venv/bin/python" "$(command -v python3 || true)"; do
  [[ -n "$cand" && -x "$cand" ]] && { PY_BIN="$cand"; break; }
done
[[ -n "$PY_BIN" ]] || die "No python interpreter found"

install_patched_file() {
  local payload="$1"
  log "Sourceless/protected install — installing patched runner from:"
  log "  $payload"
  if [[ ! -w "$CORE_DIR" ]]; then
    die "Cannot write $CORE_DIR (need write access to site-packages)."
  fi
  if grep -q 'mclaren-mesh-hotfix:skip-gt-probes' "$RUNNER" 2>/dev/null; then
    log "OK: patched runner already installed at $RUNNER"
    return 0
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY: would copy $payload → $RUNNER and clear pyc"
    return 0
  fi
  if [[ -f "$RUNNER" ]]; then
    cp -a "$RUNNER" "${RUNNER}.bak-${MARKER}-$(date -u +%Y%m%d%H%M%S)"
  fi
  cp -a "$payload" "$RUNNER"
  rm -f "$CORE_DIR"/__pycache__/inference_runner_transient*.pyc 2>/dev/null || true
  # Prove import picks up the patch
  if ! "$PY_BIN" -c "import rescale_ai.inference.core.inference_runner_transient as m; import inspect; t=inspect.getsource(m); assert 'mclaren-mesh-hotfix:skip-gt-probes' in t; print('import OK:', m.__file__)"; then
    die "Patched file written but import check failed"
  fi
  log "Installed patched runner → $RUNNER"
}

patch_existing_py() {
  export RUNNER DRY_RUN MARKER
  log "Editable .py present — patching in place with $PY_BIN"
  "$PY_BIN" <<'PY'
from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(os.environ["RUNNER"])
dry = os.environ.get("DRY_RUN", "0") == "1"
marker = os.environ["MARKER"]
text = path.read_text(encoding="utf-8")

if "mclaren-mesh-hotfix:skip-gt-probes" in text and f"{marker}:unpack" in text:
    print("OK: already hotfixed")
    sys.exit(0)

instantiate_pat = re.compile(
    r"(dataset\s*=\s*instantiate\(\s*\n"
    r"(?:.*\n)*?"
    r"[ \t]*dynamic_targets=\[\],\s*\n)"
    r"([ \t]*)\)",
    re.MULTILINE,
)
model_call_pat = re.compile(
    r"(?P<indent>[ \t]*)pred\s*=\s*model\(sample=sample,\s*data_stats=data_stats\)\s*\n"
    r"(?P=indent)pred_pos\s*=\s*pred\[:,\s*:,\s*:3\]\.transpose\(0,\s*1\)",
)

new = text
changed = False
m = instantiate_pat.search(new)
if m is None:
    if "outvar_ts_keys=[]" in new:
        print("OK: outvar_ts_keys=[] already present")
    else:
        print("ERROR: instantiate block not found", file=sys.stderr)
        sys.exit(2)
else:
    block, indent = m.group(1), m.group(2)
    if "outvar_ts_keys=[]" not in block and "outvar_ts_keys = []" not in block:
        insertion = f"{block}{indent}    outvar_ts_keys=[],  # {marker}:skip-gt-probes\n{indent})"
        new = new[: m.start()] + insertion + new[m.end() :]
        changed = True
        print("PATCH: add outvar_ts_keys=[]")

m2 = model_call_pat.search(new)
if m2 is None:
    if f"{marker}:unpack" in new or "ProbePredictions" in new:
        print("OK: unpack / post-1423 already present")
    else:
        print("WARN: model call pattern not found", file=sys.stderr)
else:
    indent = m2.group("indent")
    replacement = (
        f"{indent}pred = model(sample=sample, data_stats=data_stats)\n"
        f"{indent}if isinstance(pred, tuple):  # {marker}:unpack\n"
        f"{indent}    pred, _global_pred = pred\n"
        f"{indent}pred_pos = pred[:, :, :3].transpose(0, 1)"
    )
    new = new[: m2.start()] + replacement + new[m2.end() :]
    changed = True
    print("PATCH: unpack tuple before nodal frames")

if not changed:
    print("OK: nothing to change")
    sys.exit(0)
if dry:
    print("DRY: would write patch")
    sys.exit(0)

stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
bak = path.with_suffix(path.suffix + f".bak-{marker}-{stamp}")
shutil.copy2(path, bak)
path.write_text(new, encoding="utf-8")
print(f"Wrote {path}")
print(f"Backup {bak}")
cache = path.parent / "__pycache__"
if cache.is_dir():
    n = 0
    for pyc in cache.glob("inference_runner_transient*.pyc"):
        pyc.unlink(missing_ok=True)
        n += 1
    print(f"Cleared {n} pyc")
PY
}

# Decide strategy
if [[ -f "$RUNNER" ]] && grep -q 'def run_inference_on_demand' "$RUNNER" 2>/dev/null; then
  if [[ ! -w "$RUNNER" ]]; then
    die "Cannot write $RUNNER"
  fi
  patch_existing_py
else
  log "No editable inference_runner_transient.py (protected/sourceless tile)"
  PAYLOAD="$(find_patched_payload)" || die "Missing $PATCHED_NAME next to this script / on HPS patches dir. Re-stage both files onto wtaTdb."
  install_patched_file "$PAYLOAD"
fi

# --- restart app -------------------------------------------------------------
if [[ "$RESTART" -eq 1 ]]; then
  SVC=$(systemctl list-units --type=service --all --no-legend 'rescaleapp-*' 2>/dev/null \
    | awk '{print $1}' \
    | grep -iE 'aiphysics|ai-physics|rescaleAiPhysics|rescale-ai-physics' \
    | head -1 || true)
  if [[ -z "$SVC" ]]; then
    for cand in \
      rescaleapp-rescaleAiPhysicsE2eDesktop.service \
      rescaleapp-rescaleAiPhysicsE2eDesktopLatest.service \
      rescaleapp-rescaleAiPhysicsE2eDesktopPreRelease.service
    do
      if [[ -f "/etc/systemd/system/$cand" ]]; then
        SVC="$cand"
        break
      fi
    done
  fi
  if [[ -n "$SVC" ]]; then
    log "Restarting $SVC"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      if sudo -n systemctl restart "$SVC" 2>/dev/null; then
        sleep 3
        systemctl is-active "$SVC" >/dev/null 2>&1 && log "Service active: $SVC" \
          || warn "Restart issued but not active yet — check: systemctl status $SVC"
      else
        warn "Could not restart $SVC. Restart AI Physics from the job page, then hard-refresh."
      fi
    else
      log "DRY: would restart $SVC"
    fi
  else
    warn "No rescaleapp-* unit found — restart AI Physics from the job page, then hard-refresh."
  fi
else
  log "Skipping restart (--no-restart)"
fi

cat <<EOF

[mclaren-mesh-hotfix] Done.

Next:
  1. Hard-refresh the AI Physics UI
  2. Open P35_OS_Side_Pole_Model02 → Inference
  3. Change knobs → Run Inference (GPU)
  4. Expect mesh deformation; not probe curves on this tile

EOF
