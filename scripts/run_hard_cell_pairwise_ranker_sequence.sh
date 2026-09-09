#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COSMOS_VENV="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}"
CONFIG="$PROJECT_ROOT/experiments/configs/libero_campaign_hard_cell_pairwise_ranker.json"
BASE="${HARD_CELL_PAIRWISE_RUN_PREFIX:-hard_cell_pairwise_ranker_20260830}"
GPUS="${HARD_CELL_PAIRWISE_GPUS:-2,3,4,5,6,7,2,3,4,5,6,7}"
DEVCAL="${BASE}__development_calibration"
HOLDOUT="${BASE}__holdout"
ROOT="$PROJECT_ROOT/experiments/campaigns/$BASE"
MODEL="$ROOT/frozen_model.json"
FIT_DIR="$ROOT/analysis/development_calibration"
HOLDOUT_DIR="$ROOT/analysis/holdout"

shopt -s nullglob

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$CONFIG" \
  --profile hard_cell_pairwise_development_calibration \
  --run-prefix "$DEVCAL" \
  --gpus "$GPUS" \
  --execute

DEVCAL_FILES=("$PROJECT_ROOT/experiments/campaigns/$DEVCAL/runs"/*__candidate_outcomes.parquet)
if [[ ${#DEVCAL_FILES[@]} -ne 8 ]]; then
  echo "[pairwise] expected 8 development/calibration tables, found ${#DEVCAL_FILES[@]}" >&2
  exit 2
fi

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/hard_cell_pairwise_ranker.py" fit \
  --candidate-files "${DEVCAL_FILES[@]}" \
  --model-output "$MODEL" \
  --output-dir "$FIT_DIR"

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$CONFIG" \
  --profile hard_cell_pairwise_holdout \
  --run-prefix "$HOLDOUT" \
  --gpus "$GPUS" \
  --execute

HOLDOUT_FILES=("$PROJECT_ROOT/experiments/campaigns/$HOLDOUT/runs"/*__candidate_outcomes.parquet)
if [[ ${#HOLDOUT_FILES[@]} -ne 20 ]]; then
  echo "[pairwise] expected 20 holdout tables, found ${#HOLDOUT_FILES[@]}" >&2
  exit 2
fi

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/hard_cell_pairwise_ranker.py" evaluate \
  --candidate-files "${HOLDOUT_FILES[@]}" \
  --model "$MODEL" \
  --output-dir "$HOLDOUT_DIR"

echo "[pairwise] sequence complete: $HOLDOUT_DIR"
