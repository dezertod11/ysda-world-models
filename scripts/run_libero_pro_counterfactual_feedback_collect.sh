#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

OUTPUT_DIR="${LIBERO_PRO_VOF_OUTPUT_DIR:-$PROJECT_ROOT/experiments/counterfactual_feedback}"
if [[ "$OUTPUT_DIR" != /* ]]; then
  OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
fi

EXTRA_ARGS=()
if [[ "${LIBERO_PRO_VOF_RESUME:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--resume)
fi
if [[ "${LIBERO_PRO_VOF_SKIP_FEEDBACK_BRANCH:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--skip-feedback-branch)
fi
if [[ "${LIBERO_PRO_VOF_TERMINAL_SELECTED_FEEDBACK_ONLY:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--terminal-selected-feedback-only)
fi

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/collect_counterfactual_feedback.py" \
  --suites "${LIBERO_PRO_VOF_SUITES:-libero_object_object}" \
  --task-ids "${LIBERO_PRO_VOF_TASK_IDS:-all}" \
  --init-state-ids "${LIBERO_PRO_VOF_INIT_STATE_IDS:-all}" \
  --rollouts-per-init "${LIBERO_PRO_VOF_ROLLOUTS_PER_INIT:-2}" \
  --base-seed "${LIBERO_PRO_VOF_BASE_SEED:-2600000}" \
  --rollout-seed-step "${LIBERO_PRO_VOF_ROLLOUT_SEED_STEP:-97}" \
  --uncertainty-seeds "${LIBERO_PRO_VOF_UNCERTAINTY_SEEDS:-0,1,2,3}" \
  --max-timesteps "${LIBERO_PRO_VOF_MAX_TIMESTEPS:-280}" \
  --target-decision-states "${LIBERO_PRO_VOF_TARGET_DECISION_STATES:-100}" \
  --sampling-mode "${LIBERO_PRO_VOF_SAMPLING_MODE:-phase_balanced}" \
  --snapshot-query-indices "${LIBERO_PRO_VOF_SNAPSHOT_QUERY_INDICES:-0,3,6,9}" \
  --phase-cap-fraction "${LIBERO_PRO_VOF_PHASE_CAP_FRACTION:-0.4}" \
  --open-loop-steps "${LIBERO_PRO_VOF_OPEN_LOOP_STEPS:-16}" \
  --feedback-steps 8 \
  --consequence-horizon-steps "${LIBERO_PRO_VOF_CONSEQUENCE_HORIZON_STEPS:-16}" \
  --terminal-continuation-fraction "${LIBERO_PRO_VOF_TERMINAL_CONTINUATION_FRACTION:-0.2}" \
  --continuation-num-candidates "${LIBERO_PRO_VOF_CONTINUATION_NUM_CANDIDATES:-0}" \
  --query-cost "${LIBERO_PRO_VOF_QUERY_COST:-0.0}" \
  --num-denoising-steps-action "${LIBERO_PRO_VOF_NUM_DENOISING_STEPS_ACTION:-5}" \
  --prediction-mode "${LIBERO_PRO_VOF_PREDICTION_MODE:-parallel}" \
  --continuation-prediction-mode "${LIBERO_PRO_VOF_CONTINUATION_PREDICTION_MODE:-inherit}" \
  --num-denoising-steps-future-state "${LIBERO_PRO_VOF_NUM_DENOISING_STEPS_FUTURE_STATE:-1}" \
  --num-denoising-steps-value "${LIBERO_PRO_VOF_NUM_DENOISING_STEPS_VALUE:-1}" \
  --num-future-state-samples "${LIBERO_PRO_VOF_NUM_FUTURE_STATE_SAMPLES:-1}" \
  --num-value-samples "${LIBERO_PRO_VOF_NUM_VALUE_SAMPLES:-1}" \
  --value-ensemble-aggregation "${LIBERO_PRO_VOF_VALUE_ENSEMBLE_AGGREGATION:-average}" \
  --experiment-split "${LIBERO_PRO_VOF_EXPERIMENT_SPLIT:-screen}" \
  --case-id "${LIBERO_PRO_VOF_CASE_ID:-}" \
  --output-dir "$OUTPUT_DIR" \
  --run-name "${LIBERO_PRO_VOF_RUN_NAME:-counterfactual_feedback_$(date +%Y%m%d_%H%M%S)}" \
  "${EXTRA_ARGS[@]}"
