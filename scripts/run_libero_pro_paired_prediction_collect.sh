#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"
cd "$COSMOS_REPO"

EXTRA_ARGS=()
if [[ "${LIBERO_PRO_PAIRED_SAVE_VIDEOS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--save-videos)
fi
if [[ -n "${LIBERO_PRO_PAIRED_VIDEO_DIR:-}" ]]; then
  EXTRA_ARGS+=(--video-dir "${LIBERO_PRO_PAIRED_VIDEO_DIR}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_VIDEO_FPS:-}" ]]; then
  EXTRA_ARGS+=(--video-fps "${LIBERO_PRO_PAIRED_VIDEO_FPS}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PAIR_ID_START:-}" ]]; then
  EXTRA_ARGS+=(--pair-id-start "${LIBERO_PRO_PAIRED_PAIR_ID_START}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_MODE:-}" ]]; then
  EXTRA_ARGS+=(--intervention-mode "${LIBERO_PRO_PAIRED_INTERVENTION_MODE}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_START_T:-}" ]]; then
  EXTRA_ARGS+=(--intervention-start-t "${LIBERO_PRO_PAIRED_INTERVENTION_START_T}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_END_T:-}" ]]; then
  EXTRA_ARGS+=(--intervention-end-t "${LIBERO_PRO_PAIRED_INTERVENTION_END_T}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_START_QUERY:-}" ]]; then
  EXTRA_ARGS+=(--intervention-start-query "${LIBERO_PRO_PAIRED_INTERVENTION_START_QUERY}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_END_QUERY:-}" ]]; then
  EXTRA_ARGS+=(--intervention-end-query "${LIBERO_PRO_PAIRED_INTERVENTION_END_QUERY}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_GRIPPER:-}" ]]; then
  EXTRA_ARGS+=(--intervention-gripper "${LIBERO_PRO_PAIRED_INTERVENTION_GRIPPER}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_SCALE:-}" ]]; then
  EXTRA_ARGS+=(--intervention-scale "${LIBERO_PRO_PAIRED_INTERVENTION_SCALE}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_BIAS:-}" ]]; then
  EXTRA_ARGS+=(--intervention-bias "${LIBERO_PRO_PAIRED_INTERVENTION_BIAS}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_INTERVENTION_ROLLOUTS:-}" ]]; then
  EXTRA_ARGS+=(--intervention-rollouts "${LIBERO_PRO_PAIRED_INTERVENTION_ROLLOUTS}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_ROLLOUT_SEED_STEP:-}" ]]; then
  EXTRA_ARGS+=(--rollout-seed-step "${LIBERO_PRO_PAIRED_ROLLOUT_SEED_STEP}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_STRATEGY:-}" ]]; then
  EXTRA_ARGS+=(--planning-strategy "${LIBERO_PRO_PAIRED_PLANNING_STRATEGY}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_RISK_LAMBDA:-}" ]]; then
  EXTRA_ARGS+=(--planning-risk-lambda "${LIBERO_PRO_PAIRED_PLANNING_RISK_LAMBDA}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_ACTION_WEIGHT:-}" ]]; then
  EXTRA_ARGS+=(--planning-action-weight "${LIBERO_PRO_PAIRED_PLANNING_ACTION_WEIGHT}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_DIFFICULTY_THRESHOLD:-}" ]]; then
  EXTRA_ARGS+=(--planning-difficulty-threshold "${LIBERO_PRO_PAIRED_PLANNING_DIFFICULTY_THRESHOLD}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_VALUE_MARGIN:-}" ]]; then
  EXTRA_ARGS+=(--planning-value-margin "${LIBERO_PRO_PAIRED_PLANNING_VALUE_MARGIN}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_UNCERTAINTY_MARGIN:-}" ]]; then
  EXTRA_ARGS+=(--planning-uncertainty-margin "${LIBERO_PRO_PAIRED_PLANNING_UNCERTAINTY_MARGIN}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_PHASE_FRACTION:-}" ]]; then
  EXTRA_ARGS+=(--planning-phase-fraction "${LIBERO_PRO_PAIRED_PLANNING_PHASE_FRACTION}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_SHORT_OPEN_LOOP_STEPS:-}" ]]; then
  EXTRA_ARGS+=(--planning-short-open-loop-steps "${LIBERO_PRO_PAIRED_PLANNING_SHORT_OPEN_LOOP_STEPS}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PLANNING_SURROGATE_ERROR_THRESHOLD:-}" ]]; then
  EXTRA_ARGS+=(--planning-surrogate-error-threshold "${LIBERO_PRO_PAIRED_PLANNING_SURROGATE_ERROR_THRESHOLD}")
fi
if [[ "${LIBERO_PRO_PAIRED_RECORD_DENOISING_TRACE:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--record-denoising-trace)
fi
if [[ "${LIBERO_PRO_PAIRED_COLLECT_SAFETY_SIGNALS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--collect-safety-signals)
fi
if [[ "${LIBERO_PRO_PAIRED_TERMINATE_ON_SAFETY_VIOLATION:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--terminate-on-safety-violation)
fi
if [[ "${LIBERO_PRO_PAIRED_RESUME:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--resume)
fi
if [[ -n "${LIBERO_PRO_PAIRED_NUM_OPEN_LOOP_STEPS:-}" ]]; then
  EXTRA_ARGS+=(--num-open-loop-steps "${LIBERO_PRO_PAIRED_NUM_OPEN_LOOP_STEPS}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_NUM_DENOISING_STEPS_ACTION:-}" ]]; then
  EXTRA_ARGS+=(--num-denoising-steps-action "${LIBERO_PRO_PAIRED_NUM_DENOISING_STEPS_ACTION}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_PREDICTION_MODE:-}" ]]; then
  EXTRA_ARGS+=(--prediction-mode "${LIBERO_PRO_PAIRED_PREDICTION_MODE}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_NUM_DENOISING_STEPS_FUTURE_STATE:-}" ]]; then
  EXTRA_ARGS+=(--num-denoising-steps-future-state "${LIBERO_PRO_PAIRED_NUM_DENOISING_STEPS_FUTURE_STATE}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_NUM_DENOISING_STEPS_VALUE:-}" ]]; then
  EXTRA_ARGS+=(--num-denoising-steps-value "${LIBERO_PRO_PAIRED_NUM_DENOISING_STEPS_VALUE}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_NUM_FUTURE_STATE_SAMPLES:-}" ]]; then
  EXTRA_ARGS+=(--num-future-state-samples "${LIBERO_PRO_PAIRED_NUM_FUTURE_STATE_SAMPLES}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_NUM_VALUE_SAMPLES:-}" ]]; then
  EXTRA_ARGS+=(--num-value-samples "${LIBERO_PRO_PAIRED_NUM_VALUE_SAMPLES}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_VALUE_ENSEMBLE_AGGREGATION:-}" ]]; then
  EXTRA_ARGS+=(--value-ensemble-aggregation "${LIBERO_PRO_PAIRED_VALUE_ENSEMBLE_AGGREGATION}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_EXPERIMENT_SPLIT:-}" ]]; then
  EXTRA_ARGS+=(--experiment-split "${LIBERO_PRO_PAIRED_EXPERIMENT_SPLIT}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_CASE_ID:-}" ]]; then
  EXTRA_ARGS+=(--case-id "${LIBERO_PRO_PAIRED_CASE_ID}")
fi
if [[ "${LIBERO_PRO_PAIRED_RECORD_TEMPORAL_OVERLAP:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--record-temporal-overlap)
fi
if [[ -n "${LIBERO_PRO_PAIRED_TEMPORAL_OVERLAP_DIR:-}" ]]; then
  EXTRA_ARGS+=(--temporal-overlap-dir "${LIBERO_PRO_PAIRED_TEMPORAL_OVERLAP_DIR}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_TEMPORAL_OVERLAP_SEED_MODE:-}" ]]; then
  EXTRA_ARGS+=(--temporal-overlap-seed-mode "${LIBERO_PRO_PAIRED_TEMPORAL_OVERLAP_SEED_MODE}")
fi
if [[ -n "${LIBERO_PRO_PAIRED_TEMPORAL_OVERLAP_MAX_WINDOW:-}" ]]; then
  EXTRA_ARGS+=(--temporal-overlap-max-window "${LIBERO_PRO_PAIRED_TEMPORAL_OVERLAP_MAX_WINDOW}")
fi

python -m cosmos_policy.experiments.robot.libero.uncertainty_comparison collect-paired \
  --suites "${LIBERO_PRO_PAIRED_SUITES:-libero_spatial_object}" \
  --task-ids "${LIBERO_PRO_PAIRED_TASK_IDS:-0}" \
  --init-state-ids "${LIBERO_PRO_PAIRED_INIT_STATE_IDS:-0}" \
  --max-rollouts-per-init "${LIBERO_PRO_PAIRED_MAX_ROLLOUTS_PER_INIT:-8}" \
  --min-success "${LIBERO_PRO_PAIRED_MIN_SUCCESS:-1}" \
  --min-failed "${LIBERO_PRO_PAIRED_MIN_FAILED:-1}" \
  --base-seed "${LIBERO_PRO_PAIRED_BASE_SEED:-195}" \
  --uncertainty-seeds "${LIBERO_PRO_PAIRED_UNCERTAINTY_SEEDS:-0,1}" \
  --max-timesteps "${LIBERO_PRO_PAIRED_MAX_TIMESTEPS:-0}" \
  --output-dir "${LIBERO_PRO_PAIRED_OUTPUT_DIR:-../experiments/uncertainty}" \
  --run-name "${LIBERO_PRO_PAIRED_RUN_NAME:-}" \
  "${EXTRA_ARGS[@]}"
