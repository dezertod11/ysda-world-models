#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG="${FACTOR_ROUTED_REQUERY_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_factor_routed_requery_transfer.json}"
PROFILE="${FACTOR_ROUTED_REQUERY_PROFILE:-factor_routed_requery_transfer}"
RUN_PREFIX="${FACTOR_ROUTED_REQUERY_RUN_PREFIX:-factor_routed_requery_transfer_20260830}"
GPUS="${FACTOR_ROUTED_REQUERY_GPUS:-2,3,7}"
PYTHON="${FACTOR_ROUTED_REQUERY_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --execute

"$PYTHON" scripts/analyze_factor_routed_requery_transfer.py \
  --campaign-dir "$CAMPAIGN_DIR"

printf '%s\n' "[factor-routed-requery] complete: $CAMPAIGN_DIR"
