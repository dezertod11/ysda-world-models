#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}/bin/python"

SCREEN_PREFIX="${ADAPTIVE_SCREEN_PREFIX:-adaptive_screening_20260813}"
CONFIRM_PREFIX="${ADAPTIVE_CONFIRM_PREFIX:-adaptive_confirmatory_20260813}"
THRESHOLD_PREFIX="${ADAPTIVE_THRESHOLD_PREFIX:-adaptive_regime_threshold_20260813}"
GPU_IDS="${ADAPTIVE_GPU_IDS:-2,3,4,5,6,7}"
POLL_SECONDS="${ADAPTIVE_POLL_SECONDS:-60}"
MAX_ROLLOUTS="${ADAPTIVE_CONFIRM_ROLLOUTS:-30}"
BASE_CONFIG="${ADAPTIVE_BASE_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_planning.json}"
CONFIRM_CONFIG="${ADAPTIVE_CONFIRM_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_confirmatory_frozen.json}"
VIDEO_PREFIX="${ADAPTIVE_VIDEO_PREFIX:-adaptive_confirmatory_video_replays_20260813}"
VIDEO_CONFIG="${ADAPTIVE_VIDEO_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_video_replays_frozen.json}"
VIDEO_SELECTION="${ADAPTIVE_VIDEO_SELECTION:-$PROJECT_ROOT/experiments/configs/libero_campaign_adaptive_video_replays_frozen.csv}"
VIDEO_OUTPUT="${ADAPTIVE_VIDEO_OUTPUT:-$PROJECT_ROOT/experiments/final_results_media/adaptive_confirmatory_20260813}"

SCREEN_DIR="$PROJECT_ROOT/experiments/campaigns/$SCREEN_PREFIX"
CONFIRM_DIR="$PROJECT_ROOT/experiments/campaigns/$CONFIRM_PREFIX"
SCREEN_MANIFEST="$SCREEN_DIR/manifest.json"
SCREEN_PID_FILE="$SCREEN_DIR/supervisor.pid"
SCREEN_ANALYSIS="$SCREEN_DIR/analysis/adaptive_summary"
THRESHOLD_DIR="$PROJECT_ROOT/experiments/campaigns/$THRESHOLD_PREFIX"

manifest_status() {
  "$PYTHON" - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
print(json.loads(path.read_text(encoding="utf-8")).get("status", "missing") if path.exists() else "missing")
PY
}

mkdir -p "$SCREEN_DIR"
echo "$$" > "$SCREEN_DIR/followup.pid"
echo "[followup] waiting for $SCREEN_PREFIX"
while true; do
  status="$(manifest_status "$SCREEN_MANIFEST")"
  case "$status" in
    completed)
      break
      ;;
    failed)
      echo "[followup] screening failed; refusing to start confirmatory" >&2
      exit 1
      ;;
  esac

  if [[ ! -s "$SCREEN_PID_FILE" ]]; then
    echo "[followup] missing screening PID file: $SCREEN_PID_FILE" >&2
    exit 1
  fi
  screen_pid="$(<"$SCREEN_PID_FILE")"
  screen_command="$(ps -o args= -p "$screen_pid" || true)"
  if [[ "$screen_command" != *"$SCREEN_PREFIX"* ]]; then
    echo "[followup] screening process $screen_pid is no longer active" >&2
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

threshold_status="$(manifest_status "$THRESHOLD_DIR/manifest.json")"
if [[ "$threshold_status" == "completed" ]]; then
  echo "[followup] threshold screening already completed: $THRESHOLD_DIR"
elif [[ "$threshold_status" == "running" ]]; then
  echo "[followup] threshold screening is already marked running; refusing duplicate launch" >&2
  exit 1
else
  mkdir -p "$THRESHOLD_DIR"
  echo "[followup] launching preregistered regime-threshold screening on GPUs $GPU_IDS"
  "$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
    --config "$BASE_CONFIG" \
    --profile adaptive_regime_threshold_screening \
    --execute \
    --gpus "$GPU_IDS" \
    --run-prefix "$THRESHOLD_PREFIX"
fi

echo "[followup] analyzing completed screening campaigns"
"$PYTHON" "$SCRIPT_DIR/analyze_adaptive_planning_campaign.py" \
  --campaign-dir "$SCREEN_DIR" \
  --additional-campaign-dir "$THRESHOLD_DIR"

SELECTION_CSV="$SCREEN_ANALYSIS/selected_for_confirmatory.csv"
"$PYTHON" "$SCRIPT_DIR/build_adaptive_confirmatory_config.py" \
  --base-config "$BASE_CONFIG" \
  --selection-csv "$SELECTION_CSV" \
  --output "$CONFIRM_CONFIG" \
  --max-rollouts "$MAX_ROLLOUTS"

echo "[followup] entering resumable confirmatory and video workflow"
ADAPTIVE_CONFIRM_PREFIX="$CONFIRM_PREFIX" \
ADAPTIVE_VIDEO_PREFIX="$VIDEO_PREFIX" \
ADAPTIVE_GPU_IDS="$GPU_IDS" \
ADAPTIVE_BASE_CONFIG="$BASE_CONFIG" \
ADAPTIVE_CONFIRM_CONFIG="$CONFIRM_CONFIG" \
ADAPTIVE_SELECTION_CSV="$SELECTION_CSV" \
ADAPTIVE_VIDEO_CONFIG="$VIDEO_CONFIG" \
ADAPTIVE_VIDEO_SELECTION="$VIDEO_SELECTION" \
ADAPTIVE_VIDEO_OUTPUT="$VIDEO_OUTPUT" \
  "$SCRIPT_DIR/resume_adaptive_confirmatory_until_complete.sh"
echo "[followup] complete"
