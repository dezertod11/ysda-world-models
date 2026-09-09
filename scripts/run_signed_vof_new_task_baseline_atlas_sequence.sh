#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${SIGNED_VOF_ATLAS_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${SIGNED_VOF_ATLAS_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_signed_vof_new_task_baseline_atlas_20260903.json}"
PROFILE="${SIGNED_VOF_ATLAS_PROFILE:-signed_vof_new_task_baseline_atlas}"
RUN_PREFIX="${SIGNED_VOF_ATLAS_RUN_PREFIX:-signed_vof_new_task_baseline_atlas_20260903}"
GPUS="${SIGNED_VOF_ATLAS_GPUS:-2,3,4,5,6,7}"
MANIFEST="${SIGNED_VOF_ATLAS_MANIFEST:-$PROJECT_ROOT/experiments/SIGNED_VOF_NEW_TASK_BASELINE_ATLAS_FREEZE_MANIFEST_20260903.json}"
PROTOCOL="$PROJECT_ROOT/experiments/SIGNED_VOF_NEW_TASK_BASELINE_ATLAS_PROTOCOL_20260903.md"
ROUTER="$PROJECT_ROOT/experiments/frozen_models/signed_vof_pre_state_action_a10_v1.json"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" - "$CONFIG" "$PROTOCOL" "$ROUTER" "$MANIFEST" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

config, protocol, router, manifest_path = map(Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
for path, key in (
    (config, "campaign_config_sha256"),
    (protocol, "protocol_sha256"),
    (router, "frozen_router_sha256"),
):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != manifest[key]:
        raise SystemExit(f"Frozen hash mismatch for {path}: {actual} != {manifest[key]}")
print("[signed-vof-atlas] frozen hashes verified")
PY

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --max-parallel 6 \
  --execute

"$PYTHON" scripts/analyze_signed_vof_new_task_atlas.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-dir "$CAMPAIGN_DIR/analysis/baseline_atlas" \
  --expected-states 180

echo "[signed-vof-atlas] complete: $CAMPAIGN_DIR"
