#!/usr/bin/env bash
# Staged 200-epoch GeoT train on cXBNn, eval at 10/50/100/200.
set -euo pipefail
source /program/rescale-ai-2.1.6/venv/bin/activate
export PYTHONPATH=/enc/udeprod_cXBNn/work/rescale-ai:${PYTHONPATH:-}
export HYDRA_FULL_ERROR=1
export RESCALE_AI_DISABLE_POST_TRAINING=1

ROOT=/enc/udeprod_cXBNn/mclaren_holdout_c9_c3
SCRIPTS=/enc/udeprod_cXBNn/work/mclaren_p35_probes/scripts
LOGDIR=/enc/udeprod_cXBNn/work/mclaren_p35_probes/logs
CONFDIR=/enc/udeprod_cXBNn/work/rescale-ai/rescale_ai/solver/transient/conf
TRAIN_PY=/enc/udeprod_cXBNn/work/rescale-ai/rescale_ai/solver/transient/train.py

mkdir -p "$LOGDIR" "$ROOT/eval"

# Free A10G VRAM (ollama sits on ~15 GB at boot).
pkill -f '/program/ollama/bin/ollama runner' || true
sleep 2
nvidia-smi --query-gpu=memory.used,memory.free --format=csv || true

cd /enc/udeprod_cXBNn/work/rescale-ai/rescale_ai/solver/transient

run_train() {
  local epochs="$1"
  echo "=== train through epoch ${epochs} $(date -u +%H:%M:%SZ) ==="
  set +e
  python -u "$TRAIN_PY" --config-path="$CONFDIR" --config-name=mclaren_holdout_p35 \
    training.epochs="$epochs" \
    | tee -a "$LOGDIR/train.log"
  local rc=${PIPESTATUS[0]}
  set -e
  local ckpt="$ROOT/models/geo-global-ts/versions/0/models/checkpoints/checkpoint.0.${epochs}.pt"
  if [[ -f "$ckpt" ]]; then
    echo "checkpoint present ${ckpt} (train_exit=${rc})"
    return 0
  fi
  echo "ERROR missing ${ckpt} train_exit=${rc}"
  return "${rc:-1}"
}

eval_epoch() {
  local ep="$1"
  local out="$ROOT/eval/epoch_$(printf '%03d' "$ep")"
  mkdir -p "$out"
  cp "$ROOT/all_cases.csv" "$out/all_cases.csv"
  echo "=== eval epoch ${ep} $(date -u +%H:%M:%SZ) ==="
  python -u "$SCRIPTS/predict_and_eval.py" \
    --config-dir "$CONFDIR" \
    --config-name mclaren_holdout_p35 \
    --epoch "$ep" \
    --out "$out" \
    --holdouts KwXUX dWNQX \
    | tee -a "$LOGDIR/eval.log"
}

run_train 10
eval_epoch 10
run_train 50
eval_epoch 50
run_train 100
eval_epoch 100
run_train 200
eval_epoch 200
echo "ALL_DONE $(date -u +%H:%M:%SZ)"
