#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG="${REAL_OBSERVATION_REQUERY_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_real_observation_requery.json}"
PROFILE="${REAL_OBSERVATION_REQUERY_PROFILE:-real_observation_requery_holdout}"
RUN_PREFIX="${REAL_OBSERVATION_REQUERY_RUN_PREFIX:-real_observation_requery_20260830}"
GPUS="${REAL_OBSERVATION_REQUERY_GPUS:-2,3,7}"
PYTHON="${REAL_OBSERVATION_REQUERY_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --execute

"$PYTHON" scripts/analyze_real_observation_requery.py \
  --campaign-dir "$CAMPAIGN_DIR"

printf '%s\n' "[real-observation-requery] complete: $CAMPAIGN_DIR"
