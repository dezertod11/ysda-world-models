#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${INVARIANT_CATE_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CONFIG="${INVARIANT_CATE_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_invariant_cate_reserve_holdout_20260903.json}"
PROFILE="invariant_cate_reserve_holdout"
RUN_PREFIX="${INVARIANT_CATE_RUN_PREFIX:-invariant_cate_reserve_holdout_20260903}"
GPUS="${INVARIANT_CATE_GPUS:-2,4,5,6,7}"
MANIFEST="${INVARIANT_CATE_MANIFEST:-$PROJECT_ROOT/experiments/INVARIANT_CATE_RESERVE_HOLDOUT_FREEZE_MANIFEST_20260903.json}"
PROTOCOL="$PROJECT_ROOT/experiments/INVARIANT_CATE_RESERVE_HOLDOUT_PROTOCOL_20260903.md"
ROUTER="$PROJECT_ROOT/experiments/frozen_models/invariant_cate_relative_a01_v1.json"
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
    (router, "frozen_router_file_sha256"),
):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != manifest[key]:
        raise SystemExit(f"Frozen hash mismatch for {path}: {actual} != {manifest[key]}")
print("[invariant-cate] frozen hashes verified")
PY

"$PYTHON" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" --profile "$PROFILE" --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" --max-parallel 5 --execute

"$PYTHON" scripts/analyze_invariant_cate_reserve_holdout.py \
  --campaign-dir "$CAMPAIGN_DIR" --manifest "$MANIFEST" \
  --output-dir "$CAMPAIGN_DIR/analysis/frozen_invariant_cate"

echo "[invariant-cate] complete: $CAMPAIGN_DIR"
