#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

RUN_NAME="${FROZEN_H16_HOLDOUT_RUN_NAME:-frozen_h16_ranker_holdout_20260828}"
GPUS="${FROZEN_H16_HOLDOUT_GPUS:-7}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_NAME"
RELABEL_DIR="$PROJECT_ROOT/experiments/campaigns/${RUN_NAME}__dense_relabel"
MODEL="$PROJECT_ROOT/experiments/frozen_models/factor_h16_dense_ridge_v1.json"
CONFIG="$PROJECT_ROOT/experiments/configs/libero_campaign_frozen_h16_ranker_holdout.json"

if [[ ! -f "$MODEL" ]]; then
  echo "Missing frozen ranker: $MODEL" >&2
  exit 2
fi

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$CONFIG" \
  --profile frozen_h16_ranker_holdout \
  --run-prefix "$RUN_NAME" \
  --gpus "$GPUS" \
  --execute

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/relabel_counterfactual_dense_campaign.py" \
  --source-campaign "$CAMPAIGN_DIR" \
  --output-campaign "$RELABEL_DIR" \
  --workers "${FROZEN_H16_HOLDOUT_RELABEL_WORKERS:-3}"

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/analyze_counterfactual_feedback.py" \
  --campaign-dir "$RELABEL_DIR" \
  --output-dir "$RELABEL_DIR/analysis/counterfactual_feedback"

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/frozen_candidate_ranker.py" evaluate \
  --model "$MODEL" \
  --holdout-candidates "$RELABEL_DIR/analysis/counterfactual_feedback/candidate_outcomes_all.parquet" \
  --output-dir "$RELABEL_DIR/analysis/frozen_ranker_all" \
  --bootstrap-draws 5000 \
  --required-groups 20

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/frozen_candidate_ranker.py" evaluate \
  --model "$MODEL" \
  --holdout-candidates "$RELABEL_DIR/analysis/counterfactual_feedback/strict_candidate_outcomes_all.parquet" \
  --output-dir "$RELABEL_DIR/analysis/frozen_ranker_strict" \
  --bootstrap-draws 5000 \
  --required-groups 20

printf '%s\n' "$RELABEL_DIR/analysis/frozen_ranker_strict/RESULTS.md"
