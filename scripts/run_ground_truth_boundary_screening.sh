#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${COSMOS_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${GROUND_TRUTH_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_ground_truth_boundary_screening.json}"
PROFILE="${GROUND_TRUTH_PROFILE:-ground_truth_boundary_screening}"
RUN_PREFIX="${GROUND_TRUTH_RUN_PREFIX:-ground_truth_boundary_screening_20260824}"
GPUS="${GROUND_TRUTH_GPUS:-5,6}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"
ANALYSIS_DIR="$CAMPAIGN_DIR/analysis/boundary_screening"

"$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --execute

"$PYTHON" "$SCRIPT_DIR/validate_temporal_overlap_artifacts.py" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-json "$ANALYSIS_DIR/integrity_summary.json"

"$PYTHON" "$SCRIPT_DIR/analyze_boundary_case_screening.py" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-dir "$ANALYSIS_DIR"
