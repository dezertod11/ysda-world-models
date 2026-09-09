#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COSMOS_VENV="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}"
BASE="${AUTOREGRESSIVE_VALUE_RUN_PREFIX:-autoregressive_value_ranking_dual_20260830}"
GPUS="${AUTOREGRESSIVE_VALUE_GPUS:-2,2,3,3,4,4,6,6}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$BASE"
OUTPUT_DIR="$CAMPAIGN_DIR/analysis/value_ranking_comparison"

shopt -s nullglob

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$PROJECT_ROOT/experiments/configs/libero_campaign_autoregressive_value_ranking.json" \
  --profile autoregressive_value_ranking \
  --run-prefix "$BASE" \
  --gpus "$GPUS" \
  --execute

DUAL_FILES=("$CAMPAIGN_DIR/runs"/*__candidate_outcomes.parquet)

if [[ ${#DUAL_FILES[@]} -ne 10 ]]; then
  echo "[ar-value] expected 10 dual candidate tables, found ${#DUAL_FILES[@]}" >&2
  exit 2
fi

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/analyze_autoregressive_value_ranking.py" \
  --candidate-files "${DUAL_FILES[@]}" \
  --output-dir "$OUTPUT_DIR"

echo "[ar-value] sequence complete: $OUTPUT_DIR"
