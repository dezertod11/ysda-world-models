#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG="${PHASE_VOF_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_phase_vof_terminal_transfer.json}"
PROFILE="${PHASE_VOF_PROFILE:-phase_vof_terminal_transfer}"
RUN_PREFIX="${PHASE_VOF_RUN_PREFIX:-phase_vof_terminal_transfer_20260831}"
GPUS="${PHASE_VOF_GPUS:-2,3,4,5,7}"
PYTHON="${PHASE_VOF_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"
DENSE_DIR="$PROJECT_ROOT/experiments/campaigns/${RUN_PREFIX}__dense_relabel"

cd "$PROJECT_ROOT"

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --execute

"$PYTHON" scripts/relabel_counterfactual_dense_campaign.py \
  --source-campaign "$CAMPAIGN_DIR" \
  --output-campaign "$DENSE_DIR" \
  --workers 5

"$PYTHON" scripts/analyze_phase_vof_terminal_transfer.py \
  --dense-campaign-dir "$DENSE_DIR"

printf '%s\n' "[phase-vof-terminal] complete: $DENSE_DIR"
