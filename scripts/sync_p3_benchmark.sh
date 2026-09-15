#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_ROOT=/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP
SERVER=antonov-seg-tokens.ai0001053-01202@ssh-sr006-jupyter.ai.cloud.ru
CAMPAIGN="${P3_CAMPAIGN:-p3_benchmark_closure_20260914_v3}"
if [[ ! "$CAMPAIGN" =~ ^p3_benchmark_closure_20260914[a-zA-Z0-9_]*$ ]]; then
  echo 'Invalid campaign name' >&2
  exit 2
fi
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=2
  -o ControlMaster=auto -o ControlPath=/tmp/p3-codex-%C -o ControlPersist=600
  -p 2222 -i /home/alexander/.ssh/mlspace -o IdentitiesOnly=yes)
printf -v RSH '%q ' "${SSH[@]}"
DEST="$PROJECT_DIR/experiments/campaigns/$CAMPAIGN"
mkdir -p "$DEST"
case "${1:-}" in
  --status)
    exec "${SSH[@]}" "$SERVER" "cat '$REMOTE_ROOT/experiments/campaigns/$CAMPAIGN/sequence_status.json'"
    ;;
  --videos)
    FILTER=(--exclude='source/' --exclude='configs/' --exclude='*.npz' --exclude='*.tmp*')
    ;;
  '')
    FILTER=(--exclude='source/' --exclude='configs/' --exclude='*.npz' --exclude='*.mp4' --exclude='*.tmp*')
    ;;
  *) echo 'Usage: bash scripts/sync_p3_benchmark.sh [--status|--videos]' >&2; exit 2 ;;
esac
rsync -a --timeout=120 -e "$RSH" "${FILTER[@]}" \
  "$SERVER:$REMOTE_ROOT/experiments/campaigns/$CAMPAIGN/" "$DEST/"
