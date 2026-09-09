#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${OBJECT_Q4_TRANSFER_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${OBJECT_Q4_TRANSFER_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_object_q4_requery_task_transfer_20260901.json}"
PROFILE="${OBJECT_Q4_TRANSFER_PROFILE:-object_q4_requery_task_transfer}"
RUN_PREFIX="${OBJECT_Q4_TRANSFER_RUN_PREFIX:-object_q4_requery_task_transfer_20260901}"
GPUS="${OBJECT_Q4_TRANSFER_GPUS:-2,3,4,5,6,7}"
MANIFEST="${OBJECT_Q4_TRANSFER_MANIFEST:-$PROJECT_ROOT/experiments/OBJECT_Q4_REQUERY_TASK_TRANSFER_FREEZE_MANIFEST_20260901.json}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --max-parallel 6 \
  --execute

"$PYTHON" scripts/analyze_object_q4_requery_task_transfer.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --freeze-manifest "$MANIFEST" \
  --output-dir "$CAMPAIGN_DIR/analysis/object_q4_task_transfer"

printf '%s\n' "[object-q4-transfer] complete: $CAMPAIGN_DIR"

