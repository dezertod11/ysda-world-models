#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
RUN_PREFIX="${FACTORIAL_RUN_PREFIX:-factorial_selection_horizon_20260820}"
GPU_IDS="${FACTORIAL_GPU_IDS:-2,3,4,5,6,7}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"
PYTHON="$PROJECT_ROOT/.venv-cosmos/bin/python"

mkdir -p "$CAMPAIGN_DIR"

"$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$PROJECT_ROOT/experiments/configs/libero_campaign_factorial_selection_horizon.json" \
  --profile factorial_selection_horizon \
  --execute \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPU_IDS"

"$PYTHON" "$SCRIPT_DIR/analyze_adaptive_planning_campaign.py" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-dir "$CAMPAIGN_DIR/analysis/adaptive_summary"

"$PYTHON" "$SCRIPT_DIR/analyze_selection_horizon_factorial.py" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-dir "$CAMPAIGN_DIR/analysis/selection_horizon_factorial"

echo "[factorial] complete: $CAMPAIGN_DIR"
