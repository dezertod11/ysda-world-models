#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${COSMOS_PYTHON:-$ROOT/.venv-cosmos/bin/python}"
OUTPUT="${OBJECT_CONTACT_VOF_OUTPUT:-$ROOT/experiments/campaigns/object_contact_vof_development_20260903/analysis}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

args=(
  "$PYTHON" "$ROOT/scripts/analyze_object_contact_vof_development.py"
  --campaign-dir "$ROOT/experiments/campaigns/signed_vof_new_task_holdout_20260903"
  --campaign-dir "$ROOT/experiments/campaigns/invariant_cate_reserve_holdout_20260903"
  --output-dir "$OUTPUT"
  --project-root "$ROOT"
  --device "${OBJECT_CONTACT_VOF_DEVICE:-cuda:0}"
  --row-batch-size "${OBJECT_CONTACT_VOF_BATCH_SIZE:-4}"
)

if [[ "${OBJECT_CONTACT_VOF_REUSE_FEATURES:-0}" == "1" ]]; then
  args+=(--reuse-object-features)
fi
if [[ "${OBJECT_CONTACT_VOF_ALLOW_DOWNLOAD:-0}" == "1" ]]; then
  args+=(--allow-model-download)
fi

exec "${args[@]}"
