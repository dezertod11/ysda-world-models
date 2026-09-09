#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

POSITION_LEVEL="${P3C_POSITION_LEVEL:?P3C_POSITION_LEVEL is required}"
bash "$SCRIPT_DIR/prepare_libero_pro_position_variant.sh" "$POSITION_LEVEL"
VARIANT_ROOT="$PROJECT_ROOT/.runtime/libero_pro_position/$POSITION_LEVEL"
export LIBERO_BDDL_FILES_PATH="$VARIANT_ROOT/bddl_files"
export LIBERO_INIT_STATES_PATH="$VARIANT_ROOT/init_files"
export LIBERO_CONFIG_PATH="${P3C_CONFIG_PATH:-$PROJECT_ROOT/.runtime/p3c_config/$POSITION_LEVEL}"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

EXTRA=()
if [[ "${P3C_RESUME:-1}" == "1" ]]; then
  EXTRA+=(--resume)
fi
if [[ "${P3C_SAVE_VIDEOS:-0}" == "1" ]]; then
  EXTRA+=(--save-videos)
else
  EXTRA+=(--no-save-videos)
fi

exec "$COSMOS_VENV/bin/python" "$SCRIPT_DIR/collect_online_perception_regrasp.py" \
  --manifest "${P3C_MANIFEST:?P3C_MANIFEST is required}" \
  --position-level "$POSITION_LEVEL" \
  --task-ids "${P3C_TASK_IDS:-}" \
  --trigger-artifact "${P3C_TRIGGER_ARTIFACT:?P3C_TRIGGER_ARTIFACT is required}" \
  --trigger-modes "${P3C_TRIGGER_MODES:-workspace_calibrated,global_conservative}" \
  --perception-model "${P3C_PERCEPTION_MODEL:?P3C_PERCEPTION_MODEL is required}" \
  --uncertainty-seeds "${P3C_UNCERTAINTY_SEEDS:-0,1,2,3}" \
  --base-seed "${P3C_BASE_SEED:-20260904}" \
  --max-timesteps "${P3C_MAX_TIMESTEPS:-280}" \
  --trigger-query-idx "${P3C_TRIGGER_QUERY_IDX:-4}" \
  --prefix-horizon "${P3C_PREFIX_HORIZON:-16}" \
  --trigger-prefix-steps "${P3C_TRIGGER_PREFIX_STEPS:-8}" \
  --continuation-horizon "${P3C_CONTINUATION_HORIZON:-8}" \
  --num-denoising-steps-action "${P3C_NUM_DENOISING_STEPS_ACTION:-5}" \
  --prediction-mode "${P3C_PREDICTION_MODE:-parallel}" \
  --num-denoising-steps-future-state "${P3C_NUM_DENOISING_STEPS_FUTURE_STATE:-1}" \
  --num-denoising-steps-value "${P3C_NUM_DENOISING_STEPS_VALUE:-1}" \
  --num-future-state-samples "${P3C_NUM_FUTURE_STATE_SAMPLES:-1}" \
  --num-value-samples "${P3C_NUM_VALUE_SAMPLES:-1}" \
  --replay-threshold "${P3C_REPLAY_THRESHOLD:-1e-9}" \
  --video-fps "${P3C_VIDEO_FPS:-20}" \
  --max-cases "${P3C_MAX_CASES:-0}" \
  --output-dir "${P3C_OUTPUT_DIR:?P3C_OUTPUT_DIR is required}" \
  --run-name "${P3C_RUN_NAME:?P3C_RUN_NAME is required}" \
  "${EXTRA[@]}"
