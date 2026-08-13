#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}/bin/python"

CONFIRM_PREFIX="${ADAPTIVE_CONFIRM_PREFIX:-adaptive_confirmatory_20260813}"
VIDEO_PREFIX="${ADAPTIVE_VIDEO_PREFIX:-adaptive_confirmatory_video_replays_20260813}"
GPU_IDS="${ADAPTIVE_GPU_IDS:-2,3,4,5,6,7}"
POLL_SECONDS="${ADAPTIVE_POLL_SECONDS:-120}"
GPU_MAX_USED_MIB="${ADAPTIVE_GPU_MAX_USED_MIB:-12000}"
GPU_STABLE_POLLS="${ADAPTIVE_GPU_STABLE_POLLS:-3}"

BASE_CONFIG="${ADAPTIVE_BASE_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_planning.json}"
CONFIRM_CONFIG="${ADAPTIVE_CONFIRM_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_confirmatory_frozen.json}"
SCREEN_DIR="$PROJECT_ROOT/experiments/campaigns/adaptive_screening_20260813"
SELECTION_CSV="${ADAPTIVE_SELECTION_CSV:-$SCREEN_DIR/analysis/adaptive_summary/selected_for_confirmatory.csv}"
CONFIRM_DIR="$PROJECT_ROOT/experiments/campaigns/$CONFIRM_PREFIX"
CONFIRM_ANALYSIS="$CONFIRM_DIR/analysis/adaptive_summary"

VIDEO_CONFIG="${ADAPTIVE_VIDEO_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_video_replays_frozen.json}"
VIDEO_SELECTION="${ADAPTIVE_VIDEO_SELECTION:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_video_replays_frozen.csv}"
VIDEO_DIR="$PROJECT_ROOT/experiments/campaigns/$VIDEO_PREFIX"
VIDEO_OUTPUT="${ADAPTIVE_VIDEO_OUTPUT:-$PROJECT_ROOT/experiments/final_results_media/adaptive_confirmatory_20260813}"

manifest_status() {
  "$PYTHON" - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("missing")
else:
    try:
        print(json.loads(path.read_text(encoding="utf-8")).get("status", "missing"))
    except (OSError, json.JSONDecodeError):
        print("unreadable")
PY
}

expected_strategy_runs() {
  "$PYTHON" - "$1" "$2" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
jobs = data["profiles"][sys.argv[2]]["jobs"]
print(sum(len(job["strategy_lambdas"].split()) for job in jobs))
PY
}

completed_strategy_runs() {
  local run_dir="$1"
  if [[ ! -d "$run_dir/runs" ]]; then
    echo 0
    return
  fi
  find "$run_dir/runs" -maxdepth 1 -type f -name '*__completed.json' 2>/dev/null | wc -l
}

campaign_process_active() {
  local run_dir="$1"
  local prefix="$2"
  [[ -s "$run_dir/supervisor.pid" ]] || return 1
  local pid
  pid="$(<"$run_dir/supervisor.pid")"
  local command
  command="$(ps -o args= -p "$pid" 2>/dev/null || true)"
  [[ "$command" == *"run_libero_experiment_campaign.py"*"$prefix"* ]]
}

wait_for_existing_campaign() {
  local run_dir="$1"
  local prefix="$2"
  while campaign_process_active "$run_dir" "$prefix"; do
    echo "[recovery] existing campaign is active: $prefix"
    sleep "$POLL_SECONDS"
  done
}

gpu_snapshot() {
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu \
    --format=csv,noheader,nounits
}

gpus_have_capacity() {
  local snapshot="$1"
  local gpu
  IFS=',' read -r -a requested <<< "$GPU_IDS"
  for gpu in "${requested[@]}"; do
    gpu="${gpu//[[:space:]]/}"
    local used
    used="$(awk -F',' -v target="$gpu" '
      {gsub(/ /, "", $1); gsub(/ /, "", $2); if ($1 == target) print $2}
    ' <<< "$snapshot")"
    if [[ -z "$used" || "$used" -gt "$GPU_MAX_USED_MIB" ]]; then
      return 1
    fi
  done
}

wait_for_gpus() {
  local stable=0
  while (( stable < GPU_STABLE_POLLS )); do
    local snapshot
    snapshot="$(gpu_snapshot)"
    if gpus_have_capacity "$snapshot"; then
      stable=$((stable + 1))
      echo "[recovery] GPU capacity check $stable/$GPU_STABLE_POLLS passed"
    else
      stable=0
      echo "[recovery] waiting for GPUs $GPU_IDS (used-memory limit ${GPU_MAX_USED_MIB} MiB)"
      echo "$snapshot"
    fi
    if (( stable < GPU_STABLE_POLLS )); then
      sleep "$POLL_SECONDS"
    fi
  done
}

run_until_complete() {
  local config="$1"
  local profile="$2"
  local prefix="$3"
  local run_dir="$PROJECT_ROOT/experiments/campaigns/$prefix"
  local expected
  expected="$(expected_strategy_runs "$config" "$profile")"

  wait_for_existing_campaign "$run_dir" "$prefix"
  while true; do
    local completed
    completed="$(completed_strategy_runs "$run_dir")"
    local status
    status="$(manifest_status "$run_dir/manifest.json")"
    echo "[recovery] $prefix: status=$status strategy-runs=$completed/$expected"
    if [[ "$status" == "completed" && "$completed" -eq "$expected" ]]; then
      return
    fi

    wait_for_gpus
    mkdir -p "$run_dir"
    set +e
    "$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
      --config "$config" \
      --profile "$profile" \
      --execute \
      --gpus "$GPU_IDS" \
      --run-prefix "$prefix"
    local return_code=$?
    set -e
    echo "[recovery] campaign return code: $return_code"
    sleep "$POLL_SECONDS"
  done
}

mkdir -p "$CONFIRM_DIR"
echo "$$" > "$CONFIRM_DIR/recovery.pid"

run_until_complete "$CONFIRM_CONFIG" adaptive_confirmatory "$CONFIRM_PREFIX"

"$PYTHON" "$SCRIPT_DIR/analyze_adaptive_planning_campaign.py" \
  --campaign-dir "$CONFIRM_DIR" \
  --frozen-selection-csv "$SELECTION_CSV"

"$PYTHON" "$SCRIPT_DIR/build_adaptive_video_replay_config.py" \
  --analysis-dir "$CONFIRM_ANALYSIS" \
  --frozen-selection-csv "$SELECTION_CSV" \
  --base-config "$BASE_CONFIG" \
  --output "$VIDEO_CONFIG" \
  --selection-manifest "$VIDEO_SELECTION"

run_until_complete "$VIDEO_CONFIG" adaptive_video_replays "$VIDEO_PREFIX"

"$PYTHON" "$SCRIPT_DIR/summarize_adaptive_video_replays.py" \
  --campaign-dir "$VIDEO_DIR" \
  --selection-manifest "$VIDEO_SELECTION" \
  --output-dir "$VIDEO_OUTPUT"

"$PYTHON" "$SCRIPT_DIR/build_adaptive_planning_notebook.py"

echo "[recovery] adaptive confirmatory workflow complete"
