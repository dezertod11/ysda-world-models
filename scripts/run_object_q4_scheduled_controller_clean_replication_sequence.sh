#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${OBJECT_Q4_CLEAN_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${OBJECT_Q4_CLEAN_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_object_q4_scheduled_controller_clean_replication_20260901.json}"
PROFILE="${OBJECT_Q4_CLEAN_PROFILE:-object_q4_scheduled_controller_clean_replication}"
RUN_PREFIX="${OBJECT_Q4_CLEAN_RUN_PREFIX:-object_q4_scheduled_controller_clean_replication_20260901}"
GPUS="${OBJECT_Q4_CLEAN_GPUS:-5,6,7}"
MAX_PREFLIGHT_MEMORY_MIB="${OBJECT_Q4_CLEAN_MAX_PREFLIGHT_MEMORY_MIB:-128}"
MANIFEST="${OBJECT_Q4_CLEAN_MANIFEST:-$PROJECT_ROOT/experiments/OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_FREEZE_MANIFEST_20260901.json}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

IFS=',' read -r -a gpu_ids <<< "$GPUS"
for gpu in "${gpu_ids[@]}"; do
  used_mib="$(nvidia-smi --id="${gpu// /}" --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')"
  if (( used_mib > MAX_PREFLIGHT_MEMORY_MIB )); then
    printf '%s\n' "GPU ${gpu// /} uses ${used_mib} MiB; clean-replication preflight limit is ${MAX_PREFLIGHT_MEMORY_MIB} MiB." >&2
    exit 1
  fi
done

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --max-parallel 3 \
  --execute

"$PYTHON" scripts/analyze_object_q4_scheduled_controller.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --freeze-manifest "$MANIFEST" \
  --output-dir "$CAMPAIGN_DIR/analysis/object_q4_scheduled_controller"

printf '%s\n' "[object-q4-clean-replication] complete: $CAMPAIGN_DIR"
