#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${OBJECT_Q4_CONTROLLER_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${OBJECT_Q4_CONTROLLER_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_object_q4_scheduled_controller_20260901.json}"
PROFILE="${OBJECT_Q4_CONTROLLER_PROFILE:-object_q4_scheduled_controller}"
RUN_PREFIX="${OBJECT_Q4_CONTROLLER_RUN_PREFIX:-object_q4_scheduled_controller_20260901}"
GPUS="${OBJECT_Q4_CONTROLLER_GPUS:-2,3,4,5,6}"
MANIFEST="${OBJECT_Q4_CONTROLLER_MANIFEST:-$PROJECT_ROOT/experiments/OBJECT_Q4_SCHEDULED_CONTROLLER_FREEZE_MANIFEST_20260901.json}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --max-parallel 5 \
  --execute

"$PYTHON" scripts/analyze_object_q4_scheduled_controller.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --freeze-manifest "$MANIFEST" \
  --output-dir "$CAMPAIGN_DIR/analysis/object_q4_scheduled_controller"

printf '%s\n' "[object-q4-controller] complete: $CAMPAIGN_DIR"

