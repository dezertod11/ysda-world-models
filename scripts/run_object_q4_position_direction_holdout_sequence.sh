#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${OBJECT_Q4_DIRECTION_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${OBJECT_Q4_DIRECTION_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_object_q4_position_direction_holdout_20260902.json}"
PROFILE="${OBJECT_Q4_DIRECTION_PROFILE:-object_q4_position_direction_holdout}"
RUN_PREFIX="${OBJECT_Q4_DIRECTION_RUN_PREFIX:-object_q4_position_direction_holdout_20260902}"
GPUS="${OBJECT_Q4_DIRECTION_GPUS:-2,3,4,5,6,7}"
MANIFEST="${OBJECT_Q4_DIRECTION_MANIFEST:-$PROJECT_ROOT/experiments/OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_FREEZE_MANIFEST_20260902.json}"
PROTOCOL="$PROJECT_ROOT/experiments/OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_PROTOCOL_20260902.md"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

cd "$PROJECT_ROOT"

"$PYTHON" - "$CONFIG" "$PROTOCOL" "$MANIFEST" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

config, protocol, manifest_path = map(Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
for path, key in ((config, "campaign_config_sha256"), (protocol, "protocol_sha256")):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != manifest[key]:
        raise SystemExit(f"Frozen hash mismatch for {path}: {actual} != {manifest[key]}")
print("[object-q4-position-direction] frozen hashes verified")
PY

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --max-parallel 6 \
  --execute

"$PYTHON" scripts/analyze_object_q4_position_direction_holdout.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --freeze-manifest "$MANIFEST" \
  --output-dir "$CAMPAIGN_DIR/analysis/position_direction_holdout"

"$PYTHON" scripts/plot_object_q4_position_direction_holdout.py \
  --analysis-dir "$CAMPAIGN_DIR/analysis/position_direction_holdout"

echo "[object-q4-position-direction] complete: $CAMPAIGN_DIR"
