#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${COSMOS_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${TEMPORAL_OVERLAP_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_temporal_overlap_passive.json}"
PROFILE="${TEMPORAL_OVERLAP_PROFILE:-temporal_overlap_passive}"
RUN_PREFIX="${TEMPORAL_OVERLAP_RUN_PREFIX:-temporal_overlap_passive_20260821}"
GPUS="${TEMPORAL_OVERLAP_GPUS:-2,3,4,5,6,7}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

"$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --execute

"$PYTHON" "$SCRIPT_DIR/validate_temporal_overlap_artifacts.py" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-json "$CAMPAIGN_DIR/analysis/temporal_overlap/integrity_summary.json"

if [[ "$PROFILE" == "temporal_overlap_passive" ]]; then
  "$PYTHON" "$SCRIPT_DIR/analyze_temporal_overlap_campaign.py" \
    --campaign-dir "$CAMPAIGN_DIR" \
    --output-dir "$CAMPAIGN_DIR/analysis/temporal_overlap"
fi
