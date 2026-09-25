#!/usr/bin/env bash
# Pull cached McLaren eval artifacts from a Rescale workstation for laptop demo mode.
# Usage: bash pull_demo_data.sh [user@host]
set -euo pipefail

HOST="${1:-udeprod_yJnke@18.201.17.179}"
PORT="${SCP_PORT:-22}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="$ROOT/demo_data"
EVAL_REMOTE="/enc/udeprod_yJnke/storage_wtaTdb/models/myCool_decimated_SidePoleCrash_GeoT/versions/0/evaluation"
CASES_REMOTE="/enc/udeprod_yJnke/storage_wtaTdb/datasets/mclaren-p35-side-pole-andy/versions/3/cases.csv"
MESH_CASES=(
  prediction_case0_chFXfb
  prediction_case3_dWNQX
  prediction_case9_KwXUX
)

mkdir -p "$DEST/evaluation"
echo "→ cases.csv"
scp -P "$PORT" "$HOST:$CASES_REMOTE" "$DEST/cases.csv"

echo "→ global_values JSON"
while IFS= read -r remote; do
  base="$(basename "$remote")"
  scp -P "$PORT" "$HOST:$remote" "$DEST/evaluation/$base"
done < <(ssh -p "$PORT" -o BatchMode=yes "$HOST" "find '$EVAL_REMOTE' -name '*_global_values.json' -print")

echo "→ sample VTPs (${#MESH_CASES[@]})"
for case in "${MESH_CASES[@]}"; do
  scp -P "$PORT" "$HOST:$EVAL_REMOTE/$case/$case.vtp" "$DEST/evaluation/$case.vtp"
done

echo "Done → $DEST"
du -sh "$DEST"
