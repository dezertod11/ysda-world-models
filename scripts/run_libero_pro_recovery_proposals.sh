#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

OUTPUT_DIR="${LIBERO_PRO_RECOVERY_OUTPUT_DIR:-$PROJECT_ROOT/experiments/recovery_proposals}"
MANIFEST="${LIBERO_PRO_RECOVERY_MANIFEST:?LIBERO_PRO_RECOVERY_MANIFEST is required}"
if [[ "$OUTPUT_DIR" != /* ]]; then
  OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
fi
if [[ "$MANIFEST" != /* ]]; then
  MANIFEST="$PROJECT_ROOT/$MANIFEST"
fi

EXTRA_ARGS=()
if [[ "${LIBERO_PRO_RECOVERY_RESUME:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--resume)
fi
if [[ "${LIBERO_PRO_RECOVERY_ALLOW_INTEGRITY_FAILURES:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--allow-integrity-failures)
fi
if [[ "${LIBERO_PRO_RECOVERY_SAVE_VIDEOS:-1}" != "1" ]]; then
  EXTRA_ARGS+=(--no-save-videos)
fi
if [[ -n "${LIBERO_PRO_RECOVERY_PERCEPTION_MODEL:-}" ]]; then
  EXTRA_ARGS+=(--perception-model "$LIBERO_PRO_RECOVERY_PERCEPTION_MODEL")
fi

exec "$COSMOS_VENV/bin/python" "$SCRIPT_DIR/collect_recovery_proposals.py" \
  --manifest "$MANIFEST" \
  --position-level "${LIBERO_PRO_RECOVERY_POSITION_LEVEL:?position level is required}" \
  --task-id "${LIBERO_PRO_RECOVERY_TASK_ID:?task id is required}" \
  --proposals "${LIBERO_PRO_RECOVERY_PROPOSALS:-frequent_requery_h4,lift_hold_h8,privileged_regrasp_h8}" \
  --uncertainty-seeds "${LIBERO_PRO_RECOVERY_UNCERTAINTY_SEEDS:-0,1,2,3}" \
  --base-seed "${LIBERO_PRO_RECOVERY_BASE_SEED:-20260904}" \
  --max-timesteps "${LIBERO_PRO_RECOVERY_MAX_TIMESTEPS:-280}" \
  --num-denoising-steps-action "${LIBERO_PRO_RECOVERY_NUM_DENOISING_STEPS_ACTION:-5}" \
  --prediction-mode "${LIBERO_PRO_RECOVERY_PREDICTION_MODE:-parallel}" \
  --num-denoising-steps-future-state "${LIBERO_PRO_RECOVERY_NUM_DENOISING_STEPS_FUTURE_STATE:-1}" \
  --num-denoising-steps-value "${LIBERO_PRO_RECOVERY_NUM_DENOISING_STEPS_VALUE:-1}" \
  --num-future-state-samples "${LIBERO_PRO_RECOVERY_NUM_FUTURE_STATE_SAMPLES:-1}" \
  --num-value-samples "${LIBERO_PRO_RECOVERY_NUM_VALUE_SAMPLES:-1}" \
  --primitive-steps "${LIBERO_PRO_RECOVERY_PRIMITIVE_STEPS:-4}" \
  --lift-dz "${LIBERO_PRO_RECOVERY_LIFT_DZ:-0.35}" \
  --replay-threshold "${LIBERO_PRO_RECOVERY_REPLAY_THRESHOLD:-1e-9}" \
  --video-fps "${LIBERO_PRO_RECOVERY_VIDEO_FPS:-20}" \
  --perception-device "${LIBERO_PRO_RECOVERY_PERCEPTION_DEVICE:-cuda}" \
  --perception-min-confidence "${LIBERO_PRO_RECOVERY_PERCEPTION_MIN_CONFIDENCE:-0.0}" \
  --max-states "${LIBERO_PRO_RECOVERY_MAX_STATES:-0}" \
  --output-dir "$OUTPUT_DIR" \
  --run-name "${LIBERO_PRO_RECOVERY_RUN_NAME:-recovery_proposals_$(date +%Y%m%d_%H%M%S)}" \
  "${EXTRA_ARGS[@]}"
