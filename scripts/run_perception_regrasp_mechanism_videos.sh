#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
GPU_LIST="${GPU_LIST:-3,6}"
RUN_NAME="${RUN_NAME:-perception_regrasp_heatmap_orientationfix_20260904__mechanism_videos}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_NAME"
MANIFEST="$CAMPAIGN_DIR/selected_manifest.parquet"
MODEL="$PROJECT_ROOT/experiments/frozen_models/perception_regrasp_20260904/perception_regrasp_localizer.npz"
RUNS_DIR="$CAMPAIGN_DIR/runs"
LOGS_DIR="$CAMPAIGN_DIR/logs"
STATUS_PATH="$CAMPAIGN_DIR/status.json"

IFS=',' read -r -a gpus <<<"$GPU_LIST"
if ((${#gpus[@]} < 2)); then
  echo "At least two GPUs are required for the mechanism-video launcher." >&2
  exit 2
fi
test -s "$MANIFEST"
test -s "$MODEL"
mkdir -p "$RUNS_DIR" "$LOGS_DIR"
cd "$PROJECT_ROOT"

for position in x0.2 y0.1 y0.2; do
  "$SCRIPT_DIR/prepare_libero_pro_position_variant.sh" "$position" >/dev/null
done

write_status() {
  local status="$1"
  local exit_code="$2"
  local temporary="$STATUS_PATH.tmp"
  printf '{\n  "run_name": "%s",\n  "status": "%s",\n  "exit_code": %s,\n  "updated_at": "%s"\n}\n' \
    "$RUN_NAME" "$status" "$exit_code" "$(date --iso-8601=seconds)" >"$temporary"
  mv "$temporary" "$STATUS_PATH"
}

run_cell() {
  local gpu="$1"
  local position="$2"
  local task="$3"
  local cell="${position//./p}_task${task}"
  local variant_root="$PROJECT_ROOT/.runtime/libero_pro_position/$position"
  CUDA_VISIBLE_DEVICES="$gpu" \
    LIBERO_CONFIG_PATH="$CAMPAIGN_DIR/configs/$cell" \
    LIBERO_BDDL_FILES_PATH="$variant_root/bddl_files" \
    LIBERO_INIT_STATES_PATH="$variant_root/init_files" \
    LIBERO_PRO_POSITION_LEVEL="$position" \
    LIBERO_PRO_RECOVERY_MANIFEST="$MANIFEST" \
    LIBERO_PRO_RECOVERY_POSITION_LEVEL="$position" \
    LIBERO_PRO_RECOVERY_TASK_ID="$task" \
    LIBERO_PRO_RECOVERY_PROPOSALS="perception_regrasp_h8" \
    LIBERO_PRO_RECOVERY_PERCEPTION_MODEL="$MODEL" \
    LIBERO_PRO_RECOVERY_OUTPUT_DIR="$RUNS_DIR" \
    LIBERO_PRO_RECOVERY_RUN_NAME="mechanism__${cell}" \
    LIBERO_PRO_RECOVERY_SAVE_VIDEOS=1 \
    LIBERO_PRO_RECOVERY_RESUME=1 \
    "$SCRIPT_DIR/run_libero_pro_recovery_proposals.sh" \
    >"$LOGS_DIR/${cell}.log" 2>&1
}

write_status running 0
set +e
(
  set -e
  run_cell "${gpus[0]}" x0.2 5
  run_cell "${gpus[0]}" y0.1 8
) &
pid_a=$!
(
  set -e
  run_cell "${gpus[1]}" x0.2 9
  run_cell "${gpus[1]}" y0.2 4
) &
pid_b=$!

failure=0
wait "$pid_a" || failure=1
wait "$pid_b" || failure=1
set -e

if ((failure)); then
  write_status failed 1
  exit 1
fi
write_status completed 0
