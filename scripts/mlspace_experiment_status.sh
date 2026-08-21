#!/usr/bin/env bash
set -euo pipefail

SSH_HOST="${MLSPACE_SSH_HOST:-mlspace-sr006}"
REMOTE_ROOT="${MLSPACE_PROJECT_ROOT:-/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP}"
REMOTE_PYTHON="${MLSPACE_COSMOS_PYTHON:-.venv-cosmos/bin/python}"

allocate_tty=0
for argument in "$@"; do
  if [[ "$argument" == "--watch" || "$argument" == --watch=* ]]; then
    allocate_tty=1
    break
  fi
done

printf -v quoted_root '%q' "$REMOTE_ROOT"
printf -v quoted_python '%q' "$REMOTE_PYTHON"
remote_command="cd $quoted_root && $quoted_python scripts/status_libero_campaign.py"
for argument in "$@"; do
  printf -v quoted_argument '%q' "$argument"
  remote_command+=" $quoted_argument"
done

if ((allocate_tty)); then
  exec ssh -t "$SSH_HOST" "$remote_command"
else
  exec ssh "$SSH_HOST" "$remote_command"
fi
