#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_safety.sh"
cd "$COSMOS_REPO"

EXTRA_ARGS=(--collect-safety-signals)
if [[ "${LIBERO_SAFETY_TERMINATE_ON_VIOLATION:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--terminate-on-safety-violation)
fi
if [[ "${LIBERO_SAFETY_SAVE_VIDEOS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--save-videos)
fi
if [[ -n "${LIBERO_SAFETY_VIDEO_DIR:-}" ]]; then
  EXTRA_ARGS+=(--video-dir "${LIBERO_SAFETY_VIDEO_DIR}")
fi
if [[ "${LIBERO_SAFETY_RECORD_DENOISING_TRACE:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--record-denoising-trace)
fi
if [[ -n "${LIBERO_SAFETY_PLANNING_STRATEGY:-}" ]]; then
  EXTRA_ARGS+=(--planning-strategy "${LIBERO_SAFETY_PLANNING_STRATEGY}")
fi
if [[ -n "${LIBERO_SAFETY_PLANNING_RISK_LAMBDA:-}" ]]; then
  EXTRA_ARGS+=(--planning-risk-lambda "${LIBERO_SAFETY_PLANNING_RISK_LAMBDA}")
fi

python -m cosmos_policy.experiments.robot.libero.uncertainty_comparison collect-paired \
  --suites "${LIBERO_SAFETY_SUITES:-obstacle_avoidance}" \
  --task-ids "${LIBERO_SAFETY_TASK_IDS:-0,5,10}" \
  --init-state-ids "${LIBERO_SAFETY_INIT_STATE_IDS:-0}" \
  --max-rollouts-per-init "${LIBERO_SAFETY_MAX_ROLLOUTS_PER_INIT:-12}" \
  --min-success "${LIBERO_SAFETY_MIN_SUCCESS:-999}" \
  --min-failed "${LIBERO_SAFETY_MIN_FAILED:-999}" \
  --base-seed "${LIBERO_SAFETY_BASE_SEED:-195000}" \
  --uncertainty-seeds "${LIBERO_SAFETY_UNCERTAINTY_SEEDS:-0,1,2,3}" \
  --max-timesteps "${LIBERO_SAFETY_MAX_TIMESTEPS:-520}" \
  --output-dir "${LIBERO_SAFETY_OUTPUT_DIR:-../experiments/libero_safety}" \
  --run-name "${LIBERO_SAFETY_RUN_NAME:-}" \
  "${EXTRA_ARGS[@]}"
