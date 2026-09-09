#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv-cosmos/bin/python"
CONFIG="$PROJECT_ROOT/experiments/configs/libero_campaign_frozen_h16_closed_loop.json"
MODEL_SHA="086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb"
MODE="${1:-smoke}"
GPUS="${FROZEN_H16_GPUS:-2,3,4,5}"
SMOKE_PREFIX="${FROZEN_H16_SMOKE_PREFIX:-frozen_h16_closed_loop_smoke_20260829}"
FULL_PREFIX="${FROZEN_H16_FULL_PREFIX:-frozen_h16_closed_loop_20260829}"
VIDEO_PREFIX="${FROZEN_H16_VIDEO_PREFIX:-frozen_h16_discordant_videos_20260829}"

run_campaign() {
  local profile="$1"
  local prefix="$2"
  "$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
    --config "$CONFIG" \
    --profile "$profile" \
    --run-prefix "$prefix" \
    --gpus "$GPUS" \
    --max-parallel 4 \
    --execute
}

case "$MODE" in
  smoke)
    run_campaign frozen_h16_closed_loop_smoke "$SMOKE_PREFIX"
    "$PYTHON" "$SCRIPT_DIR/verify_frozen_ranker_smoke.py" \
      --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$SMOKE_PREFIX" \
      --expected-model-sha "$MODEL_SHA"
    ;;
  full)
    run_campaign frozen_h16_closed_loop_full "$FULL_PREFIX"
    "$PYTHON" "$SCRIPT_DIR/analyze_frozen_ranker_closed_loop.py" \
      --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$FULL_PREFIX" \
      --output-dir "$PROJECT_ROOT/experiments/campaigns/$FULL_PREFIX/analysis/frozen_ranker_closed_loop" \
      --bootstrap-draws 5000 \
      --bootstrap-seed 20260829 \
      --expected-pairs-per-factor 120 \
      --expected-model-sha "$MODEL_SHA"
    ;;
  analyze)
    "$PYTHON" "$SCRIPT_DIR/analyze_frozen_ranker_closed_loop.py" \
      --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$FULL_PREFIX" \
      --output-dir "$PROJECT_ROOT/experiments/campaigns/$FULL_PREFIX/analysis/frozen_ranker_closed_loop" \
      --bootstrap-draws 5000 \
      --bootstrap-seed 20260829 \
      --expected-pairs-per-factor 120 \
      --expected-model-sha "$MODEL_SHA"
    ;;
  videos)
    FULL_ANALYSIS="$PROJECT_ROOT/experiments/campaigns/$FULL_PREFIX/analysis/frozen_ranker_closed_loop"
    VIDEO_CONFIG="$FULL_ANALYSIS/discordant_video_replay_config.json"
    "$PYTHON" "$SCRIPT_DIR/build_frozen_ranker_discordant_video_config.py" \
      --discordant-pairs "$FULL_ANALYSIS/discordant_pairs.csv" \
      --output-config "$VIDEO_CONFIG" \
      --selection-csv "$FULL_ANALYSIS/discordant_video_selection.csv" \
      --per-direction 5
    "$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
      --config "$VIDEO_CONFIG" \
      --profile frozen_h16_discordant_video_replays \
      --run-prefix "$VIDEO_PREFIX" \
      --gpus "$GPUS" \
      --max-parallel 4 \
      --execute
    "$PYTHON" "$SCRIPT_DIR/index_frozen_ranker_video_replays.py" \
      --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$VIDEO_PREFIX" \
      --output-dir "$PROJECT_ROOT/experiments/campaigns/$VIDEO_PREFIX/video_index" \
      --selection-csv "$FULL_ANALYSIS/discordant_video_selection.csv" \
      --primary-campaign-dir "$PROJECT_ROOT/experiments/campaigns/$FULL_PREFIX"
    ;;
  *)
    echo "Usage: $0 {smoke|full|analyze|videos}" >&2
    exit 2
    ;;
esac
