#!/usr/bin/env bash
set -euo pipefail

trap 'status=$?; echo "[surrogate-followup] failed at line $LINENO (exit=$status)" >&2' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}/bin/python"

SCREEN_PREFIX="${SURROGATE_SCREEN_PREFIX:-surrogate_screening_20260819}"
CONFIRM_PREFIX="${SURROGATE_CONFIRM_PREFIX:-surrogate_confirmatory_20260819}"
SCREEN_DRIVER_PID="${SURROGATE_SCREEN_DRIVER_PID:-}"
# Jobs are emitted as adjacent controls/surrogate pairs. Pairing GPU ids keeps
# the longer control jobs balanced after the shorter surrogate jobs finish.
GPU_IDS="${SURROGATE_GPU_IDS:-2,2,3,3,4,4,5,5,6,6,7,7,2,2,3,3,4,4,5,5,6,6,7,7}"
POLL_SECONDS="${SURROGATE_POLL_SECONDS:-60}"
CONFIRM_ROLLOUTS="${SURROGATE_CONFIRM_ROLLOUTS:-20}"
GPU_MAX_USED_MIB="${SURROGATE_GPU_MAX_USED_MIB:-12000}"
GPU_STABLE_POLLS="${SURROGATE_GPU_STABLE_POLLS:-2}"

BASE_CONFIG="${SURROGATE_BASE_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_surrogate_requery_screening.json}"
CONFIRM_CONFIG="${SURROGATE_CONFIRM_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_surrogate_requery_confirmatory.json}"
VIDEO_PREFIX="${SURROGATE_VIDEO_PREFIX:-surrogate_confirmatory_video_replays_20260819}"
VIDEO_CONFIG="${SURROGATE_VIDEO_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_surrogate_video_replays.json}"
VIDEO_SELECTION="${SURROGATE_VIDEO_SELECTION:-$PROJECT_ROOT/experiments/configs/libero_campaign_surrogate_video_replays.csv}"
VIDEO_OUTPUT="${SURROGATE_VIDEO_OUTPUT:-$PROJECT_ROOT/experiments/final_results_media/surrogate_confirmatory_20260819}"
SCREEN_DIR="$PROJECT_ROOT/experiments/campaigns/$SCREEN_PREFIX"
CONFIRM_DIR="$PROJECT_ROOT/experiments/campaigns/$CONFIRM_PREFIX"
SCREEN_ANALYSIS="$SCREEN_DIR/analysis/adaptive_summary"
SELECTION_CSV="$SCREEN_ANALYSIS/selected_for_confirmatory.csv"

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

expected_jobs() {
  "$PYTHON" - "$1" "$2" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
print(len(data["profiles"][sys.argv[2]]["jobs"]))
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

completed_count() {
  local directory="$1"
  local pattern="$2"
  if [[ ! -d "$directory" ]]; then
    echo 0
    return 0
  fi
  find "$directory" -maxdepth 1 -type f -name "$pattern" 2>/dev/null | wc -l
}

screen_driver_active() {
  [[ -n "$SCREEN_DRIVER_PID" ]] || return 0
  local command
  command="$(ps -o args= -p "$SCREEN_DRIVER_PID" 2>/dev/null || true)"
  [[ "$command" == *"run_libero_experiment_campaign.py"*"$SCREEN_PREFIX"* ]]
}

wait_for_screening() {
  echo "[surrogate-followup] waiting for $SCREEN_PREFIX"
  while true; do
    local status
    status="$(manifest_status "$SCREEN_DIR/manifest.json")"
    case "$status" in
      completed)
        return
        ;;
      failed)
        echo "[surrogate-followup] screening failed; confirmatory launch refused" >&2
        exit 1
        ;;
      running)
        if ! screen_driver_active; then
          echo "[surrogate-followup] screening driver is gone while manifest is running" >&2
          exit 1
        fi
        ;;
      *)
        echo "[surrogate-followup] unexpected screening status: $status" >&2
        exit 1
        ;;
    esac
    sleep "$POLL_SECONDS"
  done
}

gpu_snapshot() {
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu \
    --format=csv,noheader,nounits
}

gpus_have_capacity() {
  local snapshot="$1"
  local unique_gpus
  unique_gpus="$(tr ',' '\n' <<<"$GPU_IDS" | sed '/^$/d' | sort -u)"
  local gpu
  while read -r gpu; do
    local used
    used="$(awk -F',' -v target="$gpu" '
      {gsub(/ /, "", $1); gsub(/ /, "", $2); if ($1 == target) print $2}
    ' <<<"$snapshot")"
    if [[ -z "$used" || "$used" -gt "$GPU_MAX_USED_MIB" ]]; then
      return 1
    fi
  done <<<"$unique_gpus"
}

wait_for_gpus() {
  local stable=0
  while (( stable < GPU_STABLE_POLLS )); do
    local snapshot
    snapshot="$(gpu_snapshot)"
    if gpus_have_capacity "$snapshot"; then
      stable=$((stable + 1))
      echo "[surrogate-followup] GPU capacity $stable/$GPU_STABLE_POLLS"
    else
      stable=0
      echo "[surrogate-followup] waiting for GPU 2-7 capacity"
      echo "$snapshot"
    fi
    if (( stable < GPU_STABLE_POLLS )); then
      sleep "$POLL_SECONDS"
    fi
  done
}

run_campaign_until_complete() {
  local config="$1"
  local profile="$2"
  local prefix="$3"
  local label="$4"
  local run_dir="$PROJECT_ROOT/experiments/campaigns/$prefix"
  local expected
  expected="$(expected_strategy_runs "$config" "$profile")"
  while true; do
    local status completed
    status="$(manifest_status "$run_dir/manifest.json")"
    completed="$(completed_count "$run_dir/runs" '*__completed.json')"
    echo "[surrogate-followup] $label status=$status runs=$completed/$expected"
    if [[ "$status" == "completed" && "$completed" -eq "$expected" ]]; then
      return
    fi
    wait_for_gpus
    set +e
    "$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
      --config "$config" \
      --profile "$profile" \
      --execute \
      --run-prefix "$prefix" \
      --gpus "$GPU_IDS"
    local return_code=$?
    set -e
    echo "[surrogate-followup] $label runner return code=$return_code"
    sleep "$POLL_SECONDS"
  done
}

mkdir -p "$SCREEN_DIR"
echo "$$" >"$SCREEN_DIR/followup.pid"
wait_for_screening

screen_expected_jobs="$(expected_jobs "$BASE_CONFIG" surrogate_screening)"
screen_expected_runs="$(expected_strategy_runs "$BASE_CONFIG" surrogate_screening)"
screen_completed_jobs="$(completed_count "$SCREEN_DIR/completed" '*.json')"
screen_completed_runs="$(completed_count "$SCREEN_DIR/runs" '*__completed.json')"
echo "[surrogate-followup] screening jobs=$screen_completed_jobs/$screen_expected_jobs runs=$screen_completed_runs/$screen_expected_runs"
if [[ "$screen_completed_jobs" -ne "$screen_expected_jobs" || "$screen_completed_runs" -ne "$screen_expected_runs" ]]; then
  echo "[surrogate-followup] screening completion counts are inconsistent" >&2
  exit 1
fi

"$PYTHON" "$SCRIPT_DIR/analyze_adaptive_planning_campaign.py" \
  --campaign-dir "$SCREEN_DIR"

"$PYTHON" "$SCRIPT_DIR/build_surrogate_requery_confirmatory_config.py" \
  --base-config "$BASE_CONFIG" \
  --selection-csv "$SELECTION_CSV" \
  --output "$CONFIRM_CONFIG" \
  --max-rollouts "$CONFIRM_ROLLOUTS"

run_campaign_until_complete \
  "$CONFIRM_CONFIG" surrogate_confirmatory "$CONFIRM_PREFIX" confirmatory

"$PYTHON" "$SCRIPT_DIR/analyze_adaptive_planning_campaign.py" \
  --campaign-dir "$CONFIRM_DIR" \
  --frozen-selection-csv "$SELECTION_CSV"

set +e
"$PYTHON" "$SCRIPT_DIR/build_adaptive_video_replay_config.py" \
  --analysis-dir "$CONFIRM_DIR/analysis/adaptive_summary" \
  --frozen-selection-csv "$SELECTION_CSV" \
  --base-config "$BASE_CONFIG" \
  --output "$VIDEO_CONFIG" \
  --selection-manifest "$VIDEO_SELECTION"
video_config_status=$?
set -e

if [[ "$video_config_status" -eq 0 ]]; then
  run_campaign_until_complete \
    "$VIDEO_CONFIG" adaptive_video_replays "$VIDEO_PREFIX" video-replay
  "$PYTHON" "$SCRIPT_DIR/summarize_adaptive_video_replays.py" \
    --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$VIDEO_PREFIX" \
    --selection-manifest "$VIDEO_SELECTION" \
    --output-dir "$VIDEO_OUTPUT"
elif [[ "$video_config_status" -eq 3 ]]; then
  echo "[surrogate-followup] no discordant frozen outcomes; video replay skipped"
else
  echo "[surrogate-followup] video replay configuration failed" >&2
  exit "$video_config_status"
fi

"$PYTHON" "$SCRIPT_DIR/build_surrogate_requery_notebook.py"

echo "[surrogate-followup] screening, confirmatory, and video workflows complete"
