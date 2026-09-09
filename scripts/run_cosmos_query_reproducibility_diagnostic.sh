#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

OUTPUT_DIR="${COSMOS_QUERY_REPRO_OUTPUT_DIR:-$PROJECT_ROOT/experiments/campaigns/cosmos_query_reproducibility_20260902}"
MODES="${COSMOS_QUERY_REPRO_MODES:-default strict}"
REPLICAS="${COSMOS_QUERY_REPRO_REPLICAS:-a b}"
INIT_STATE_IDS="${COSMOS_QUERY_REPRO_INIT_STATE_IDS:-0,16,41}"
REPEATS="${COSMOS_QUERY_REPRO_REPEATS:-2}"
BASE_SEED="${COSMOS_QUERY_REPRO_BASE_SEED:-15000000}"
MAX_PREFLIGHT_MEMORY_MIB="${COSMOS_QUERY_REPRO_MAX_PREFLIGHT_MEMORY_MIB:-128}"

mkdir -p "$OUTPUT_DIR/raw" "$OUTPUT_DIR/analysis"

physical_gpu="${CUDA_VISIBLE_DEVICES%%,*}"
used_mib="$(nvidia-smi --id="$physical_gpu" --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')"
if (( used_mib > MAX_PREFLIGHT_MEMORY_MIB )); then
  echo "GPU $physical_gpu uses $used_mib MiB; diagnostic preflight limit is $MAX_PREFLIGHT_MEMORY_MIB MiB." >&2
  exit 1
fi

for mode in $MODES; do
  for replica in $REPLICAS; do
    output="$OUTPUT_DIR/raw/${mode}_${replica}.npz"
    if [[ -s "$output" && "${COSMOS_QUERY_REPRO_FORCE:-0}" != "1" ]]; then
      echo "[query-repro] skip existing $output"
      continue
    fi
    "$COSMOS_VENV/bin/python" "$SCRIPT_DIR/diagnose_cosmos_query_reproducibility.py" \
      --init-state-ids "$INIT_STATE_IDS" \
      --base-seed "$BASE_SEED" \
      --repeats "$REPEATS" \
      --deterministic-mode "$mode" \
      --replica-id "$replica" \
      --output "$output"
  done
done

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/analyze_cosmos_query_reproducibility.py" \
  --input-dir "$OUTPUT_DIR/raw" \
  --output-dir "$OUTPUT_DIR/analysis"

echo "[query-repro] complete: $OUTPUT_DIR"
