#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${OBJECT_Q4_SHARED_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${OBJECT_Q4_SHARED_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_object_q4_shared_prefix_replication_20260902.json}"
PROFILE="${OBJECT_Q4_SHARED_PROFILE:-object_q4_shared_prefix_replication}"
RUN_PREFIX="${OBJECT_Q4_SHARED_RUN_PREFIX:-object_q4_shared_prefix_replication_20260902}"
GPUS="${OBJECT_Q4_SHARED_GPUS:-3,4,5,6,7}"
MANIFEST="${OBJECT_Q4_SHARED_MANIFEST:-$PROJECT_ROOT/experiments/OBJECT_Q4_SHARED_PREFIX_REPLICATION_FREEZE_MANIFEST_20260902.json}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --max-parallel 5 \
  --execute

"$PYTHON" scripts/analyze_object_q4_shared_prefix_replication.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --freeze-manifest "$MANIFEST" \
  --output-dir "$CAMPAIGN_DIR/analysis/object_q4_shared_prefix"

echo "[object-q4-shared-prefix] complete: $CAMPAIGN_DIR"
