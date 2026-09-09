#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG="${INITIAL_REQUERY_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_initial_requery_holdout.json}"
PROFILE="${INITIAL_REQUERY_PROFILE:-initial_requery_holdout}"
RUN_PREFIX="${INITIAL_REQUERY_RUN_PREFIX:-initial_requery_holdout_20260831}"
GPUS="${INITIAL_REQUERY_GPUS:-2,3,4,5,7}"
PYTHON="${INITIAL_REQUERY_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --execute

"$PYTHON" scripts/analyze_initial_requery_holdout.py \
  --campaign-dir "$CAMPAIGN_DIR"

printf '%s\n' "[initial-requery] complete: $CAMPAIGN_DIR"

