#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"
cd "$COSMOS_REPO"

EXTRA_ARGS=()
if [[ "${LIBERO_PRO_UNCERTAINTY_COLLECT_PREDICTION_ERRORS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--collect-prediction-errors)
fi
if [[ "${LIBERO_PRO_UNCERTAINTY_SAVE_VIDEOS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--save-videos)
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_VIDEO_DIR:-}" ]]; then
  EXTRA_ARGS+=(--video-dir "${LIBERO_PRO_UNCERTAINTY_VIDEO_DIR}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_VIDEO_FPS:-}" ]]; then
  EXTRA_ARGS+=(--video-fps "${LIBERO_PRO_UNCERTAINTY_VIDEO_FPS}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_MODE:-}" ]]; then
  EXTRA_ARGS+=(--intervention-mode "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_MODE}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_START_T:-}" ]]; then
  EXTRA_ARGS+=(--intervention-start-t "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_START_T}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_END_T:-}" ]]; then
  EXTRA_ARGS+=(--intervention-end-t "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_END_T}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_START_QUERY:-}" ]]; then
  EXTRA_ARGS+=(--intervention-start-query "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_START_QUERY}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_END_QUERY:-}" ]]; then
  EXTRA_ARGS+=(--intervention-end-query "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_END_QUERY}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_GRIPPER:-}" ]]; then
  EXTRA_ARGS+=(--intervention-gripper "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_GRIPPER}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_SCALE:-}" ]]; then
  EXTRA_ARGS+=(--intervention-scale "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_SCALE}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_BIAS:-}" ]]; then
  EXTRA_ARGS+=(--intervention-bias "${LIBERO_PRO_UNCERTAINTY_INTERVENTION_BIAS}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_PLANNING_STRATEGY:-}" ]]; then
  EXTRA_ARGS+=(--planning-strategy "${LIBERO_PRO_UNCERTAINTY_PLANNING_STRATEGY}")
fi
if [[ -n "${LIBERO_PRO_UNCERTAINTY_PLANNING_RISK_LAMBDA:-}" ]]; then
  EXTRA_ARGS+=(--planning-risk-lambda "${LIBERO_PRO_UNCERTAINTY_PLANNING_RISK_LAMBDA}")
fi
if [[ "${LIBERO_PRO_UNCERTAINTY_RECORD_DENOISING_TRACE:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--record-denoising-trace)
fi
if [[ "${LIBERO_PRO_UNCERTAINTY_COLLECT_SAFETY_SIGNALS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--collect-safety-signals)
fi
if [[ "${LIBERO_PRO_UNCERTAINTY_TERMINATE_ON_SAFETY_VIOLATION:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--terminate-on-safety-violation)
fi

python -m cosmos_policy.experiments.robot.libero.uncertainty_comparison collect \
  --suites "${LIBERO_PRO_UNCERTAINTY_SUITES:-libero_spatial_object}" \
  --task-ids "${LIBERO_PRO_UNCERTAINTY_TASK_IDS:-0}" \
  --episodes-per-task "${LIBERO_PRO_UNCERTAINTY_EPISODES_PER_TASK:-2}" \
  --init-state-offset "${LIBERO_PRO_UNCERTAINTY_INIT_STATE_OFFSET:-0}" \
  --base-seed "${LIBERO_PRO_UNCERTAINTY_BASE_SEED:-195}" \
  --uncertainty-seeds "${LIBERO_PRO_UNCERTAINTY_SEEDS:-0,1,2,3}" \
  --max-timesteps "${LIBERO_PRO_UNCERTAINTY_MAX_TIMESTEPS:-0}" \
  --output-dir "${LIBERO_PRO_UNCERTAINTY_OUTPUT_DIR:-../experiments/uncertainty}" \
  --run-name "${LIBERO_PRO_UNCERTAINTY_RUN_NAME:-}" \
  "${EXTRA_ARGS[@]}"
