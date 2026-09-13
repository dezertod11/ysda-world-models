#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BASH_VERSION:-}" ]]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
elif [[ -n "${ZSH_VERSION:-}" ]]; then
  SCRIPT_PATH="${(%):-%N}"
else
  echo "Unsupported shell: use bash or zsh." >&2
  return 1 2>/dev/null || exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

export COSMOS_REPO="${COSMOS_REPO:-$PROJECT_ROOT/cosmos-policy}"

if [[ -z "${COSMOS_VENV:-}" ]]; then
  if [[ -x "$PROJECT_ROOT/.venv-cosmos/bin/python" ]]; then
    export COSMOS_VENV="$PROJECT_ROOT/.venv-cosmos"
  elif [[ -x "/home/alexander/venvs/cosmos_policy_libero/bin/python" ]]; then
    export COSMOS_VENV="/home/alexander/venvs/cosmos_policy_libero"
  else
    export COSMOS_VENV="$PROJECT_ROOT/.venv-cosmos"
  fi
fi

IS_MLSPACE=0
if [[ "$PROJECT_ROOT" == /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/* ]]; then
  IS_MLSPACE=1
fi

if [[ -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  if [[ "$IS_MLSPACE" == "1" ]]; then
    export CUDA_VISIBLE_DEVICES=2
  else
    export CUDA_VISIBLE_DEVICES=0
  fi
fi

if [[ "$IS_MLSPACE" == "1" && ",$CUDA_VISIBLE_DEVICES," == *,0,* && "${MLSPACE_ALLOW_GPU0:-0}" != "1" ]]; then
  echo "GPU 0 requires explicit authorization; use the idle-only campaign queue with --allow-gpu-zero." >&2
  return 2 2>/dev/null || exit 2
fi

if [[ -z "${MUJOCO_GL:-}" ]]; then
  if [[ "$IS_MLSPACE" == "1" ]]; then
    export MUJOCO_GL=egl
  else
    export MUJOCO_GL=glx
  fi
fi

export PYOPENGL_PLATFORM="${PYOPENGL_PLATFORM:-$MUJOCO_GL}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"

if [[ ! -x "$COSMOS_VENV/bin/python" ]]; then
  echo "Cosmos environment is missing: $COSMOS_VENV" >&2
  echo "Run scripts/setup_mlspace_cosmos.sh on MLSpace first." >&2
  return 1 2>/dev/null || exit 1
fi

SITE_PACKAGES="$("$COSMOS_VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
CUDA_NVRTC_ROOT="$SITE_PACKAGES/nvidia/cuda_nvrtc"
if [[ -d "$CUDA_NVRTC_ROOT" ]]; then
  export CUDA_HOME="${CUDA_HOME:-$CUDA_NVRTC_ROOT}"
fi

NVIDIA_LIBS=""
if [[ -d "$SITE_PACKAGES/nvidia" ]]; then
  NVIDIA_LIBS="$(find "$SITE_PACKAGES/nvidia" -maxdepth 3 -type d -name lib | paste -sd: -)"
fi
if [[ -n "$NVIDIA_LIBS" ]]; then
  export LD_LIBRARY_PATH="$NVIDIA_LIBS:${LD_LIBRARY_PATH:-}"
fi

export PYTHONPATH="$COSMOS_REPO${PYTHONPATH:+:$PYTHONPATH}"

source "$COSMOS_VENV/bin/activate"
