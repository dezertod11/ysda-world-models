#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COSMOS_VENV="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}"
BASE="${TERMINAL_PROPOSAL_RUN_PREFIX:-proposal_opportunity_k16_20260830}"
GPUS="${TERMINAL_PROPOSAL_GPUS:-2,2,3,3,4,4,6,6}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$BASE"
OUTPUT_DIR="$CAMPAIGN_DIR/analysis/terminal_opportunity_atlas"
RESULT_DIR="$CAMPAIGN_DIR/analysis/k16_screen"

shopt -s nullglob

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$PROJECT_ROOT/experiments/configs/libero_campaign_proposal_opportunity_k16.json" \
  --profile proposal_opportunity_k16 \
  --run-prefix "$BASE" \
  --gpus "$GPUS" \
  --execute

NEW_FILES=("$CAMPAIGN_DIR/runs"/*__candidate_outcomes.parquet)
if [[ ${#NEW_FILES[@]} -ne 10 ]]; then
  echo "[proposal-k16] expected 10 candidate outcome tables, found ${#NEW_FILES[@]}" >&2
  exit 2
fi

HISTORICAL_FILES=(
  "$PROJECT_ROOT/experiments/campaigns/counterfactual_feedback_dense_relabel_20260827/runs"/*__candidate_outcomes.parquet
  "$PROJECT_ROOT/experiments/campaigns/counterfactual_feedback_h32_dense_relabel_20260827/runs"/*__candidate_outcomes.parquet
  "$PROJECT_ROOT/experiments/campaigns/terminal_grounded_critic_20260829__development/runs"/*__candidate_outcomes.parquet
  "$PROJECT_ROOT/experiments/campaigns/terminal_grounded_critic_20260829__holdout/runs"/*__candidate_outcomes.parquet
)

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/build_terminal_opportunity_atlas.py" \
  --candidate-files "${HISTORICAL_FILES[@]}" "${NEW_FILES[@]}" \
  --output-dir "$OUTPUT_DIR"

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/analyze_proposal_opportunity_k16.py" \
  --atlas-dir "$OUTPUT_DIR" \
  --campaign "$BASE" \
  --output-dir "$RESULT_DIR" \
  --candidate-files "${NEW_FILES[@]}"

echo "[proposal-k16] sequence complete: $RESULT_DIR"
