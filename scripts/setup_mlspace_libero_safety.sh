#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COSMOS_REPO="$PROJECT_ROOT/cosmos-policy"
COSMOS_VENV="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos-safety}"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
MICROMAMBA_BIN="${MICROMAMBA_BIN:-$HOME/.local/bin/micromamba}"
LIBERO_SAFETY_COMMIT="${LIBERO_SAFETY_COMMIT:-19ec8df23eedfbb9265bafd3e56495fcebfcfcd0}"
LIBERO_SAFETY_REPO="$PROJECT_ROOT/.external/LIBERO-Safety-$LIBERO_SAFETY_COMMIT"
ARCHIVE_DIR="$PROJECT_ROOT/.runtime/libero_safety/downloads"
ARCHIVE_PATH="$ARCHIVE_DIR/LIBERO-Safety-$LIBERO_SAFETY_COMMIT.tar.gz"
IMAGEMAGICK_PREFIX="${LIBERO_SAFETY_IMAGEMAGICK_PREFIX:-$PROJECT_ROOT/.runtime/libero_safety/imagemagick}"

if [[ ! -x "$UV_BIN" ]]; then
  echo "uv is missing: $UV_BIN" >&2
  exit 1
fi
if [[ ! -x "$MICROMAMBA_BIN" ]]; then
  echo "micromamba is missing: $MICROMAMBA_BIN" >&2
  exit 1
fi
if [[ ! -f "$COSMOS_REPO/pyproject.toml" ]]; then
  echo "Cosmos Policy checkout is missing: $COSMOS_REPO" >&2
  exit 1
fi

mkdir -p "$PROJECT_ROOT/.external" "$ARCHIVE_DIR"
if [[ ! -f "$LIBERO_SAFETY_REPO/.source_commit" ]]; then
  if [[ -e "$LIBERO_SAFETY_REPO" ]]; then
    echo "Refusing to replace existing unverified directory: $LIBERO_SAFETY_REPO" >&2
    exit 1
  fi
  curl --fail --location --retry 5 --continue-at - \
    "https://codeload.github.com/LIBERO-SAFETY/LIBERO-Safety/tar.gz/$LIBERO_SAFETY_COMMIT" \
    --output "$ARCHIVE_PATH"
  EXTRACT_DIR="$PROJECT_ROOT/.external/.extract-LIBERO-Safety-$LIBERO_SAFETY_COMMIT"
  if [[ -e "$EXTRACT_DIR" ]]; then
    echo "Temporary extraction directory already exists: $EXTRACT_DIR" >&2
    exit 1
  fi
  mkdir -p "$EXTRACT_DIR"
  tar -xzf "$ARCHIVE_PATH" --strip-components=1 -C "$EXTRACT_DIR"
  mv "$EXTRACT_DIR" "$LIBERO_SAFETY_REPO"
  printf '%s\n' "$LIBERO_SAFETY_COMMIT" >"$LIBERO_SAFETY_REPO/.source_commit"
fi

"$UV_BIN" python install 3.10
export UV_PROJECT_ENVIRONMENT="$COSMOS_VENV"
cd "$COSMOS_REPO"
"$UV_BIN" sync --extra cu128 --group libero --python 3.10
"$UV_BIN" pip install --python "$COSMOS_VENV/bin/python" --no-deps --editable "$LIBERO_SAFETY_REPO"
"$UV_BIN" pip install --python "$COSMOS_VENV/bin/python" --no-deps \
  --editable "$LIBERO_SAFETY_REPO/third_party/robosuite-1.4"
"$UV_BIN" pip install --python "$COSMOS_VENV/bin/python" "usd-core>=25.5" wand scikit-image ipykernel

if [[ ! -x "$IMAGEMAGICK_PREFIX/bin/magick" ]]; then
  "$MICROMAMBA_BIN" create --yes --prefix "$IMAGEMAGICK_PREFIX" \
    --override-channels --channel conda-forge imagemagick
fi

COSMOS_VENV="$COSMOS_VENV" "$COSMOS_VENV/bin/python" "$SCRIPT_DIR/patch_robosuite_egl.py"
"$COSMOS_VENV/bin/python" - <<'PY'
import shutil
from pathlib import Path

import robosuite

package_dir = Path(robosuite.__path__[0])
source = package_dir / "macros.py"
target = package_dir / "macros_private.py"
if source.exists() and not target.exists():
    shutil.copyfile(source, target)
    print(f"created {target}")
PY

RUNTIME_DIR="$PROJECT_ROOT/.runtime/libero_safety"
mkdir -p "$RUNTIME_DIR"
"$COSMOS_VENV/bin/python" - "$RUNTIME_DIR/libero_t5_embeddings.pkl" <<'PY'
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

target = Path(sys.argv[1])
if not target.exists():
    source = hf_hub_download(
        repo_id="nvidia/Cosmos-Policy-LIBERO-Predict2-2B",
        filename="libero_t5_embeddings.pkl",
        local_files_only=True,
    )
    shutil.copy2(source, target)
    print(f"created writable T5 cache: {target}")
PY

ASSETS_PARENT="${LIBERO_SAFETY_ASSETS_DIR:-/tmp/malnev_world_model_libero_safety_$LIBERO_SAFETY_COMMIT}"
ASSETS_PATH="$ASSETS_PARENT/assets"
ASSETS_READY="$ASSETS_PARENT/assets.ready"
if [[ "${LIBERO_SAFETY_SKIP_ASSETS:-0}" != "1" && ! -f "$ASSETS_READY" ]]; then
  echo "Downloading the public LIBERO-Safety asset archive. This is a large one-time download."
  ASSET_ARCHIVE="$(
    HF_HUB_OFFLINE=0 "$COSMOS_VENV/bin/hf" download \
      LIBERO-Safety/libero_safety_assets assets.zip --repo-type dataset
  )"
  mkdir -p "$ASSETS_PARENT"
  unzip -q -o "$ASSET_ARCHIVE" -d "$ASSETS_PARENT"
  {
    printf 'archive=%s\n' "$ASSET_ARCHIVE"
    printf 'completed_at=%s\n' "$(date -Iseconds)"
  } >"$ASSETS_READY"
fi

ASSETS_LINK="$LIBERO_SAFETY_REPO/libero/libero/assets"
if [[ -d "$ASSETS_PATH" ]]; then
  if [[ -e "$ASSETS_LINK" && ! -L "$ASSETS_LINK" ]]; then
    PARTIAL_PATH="$ASSETS_LINK.nfs-partial-$(date +%Y%m%d-%H%M%S)"
    echo "Moving the previous NFS asset directory to: $PARTIAL_PATH"
    mv "$ASSETS_LINK" "$PARTIAL_PATH"
  elif [[ -L "$ASSETS_LINK" ]]; then
    rm "$ASSETS_LINK"
  fi
  ln -s "$ASSETS_PATH" "$ASSETS_LINK"
fi

"$COSMOS_VENV/bin/python" -m ipykernel install --user \
  --name ysda-cosmos-policy-libero-safety \
  --display-name "YSDA Cosmos Policy LIBERO-Safety (MLSpace Py3.10)"

COSMOS_VENV="$COSMOS_VENV" source "$SCRIPT_DIR/cosmos_env_libero_safety.sh"
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/verify_mlspace_libero_safety.py" --simulator-smoke

echo
echo "LIBERO-Safety environment is ready."
echo "Activate with: COSMOS_VENV=$COSMOS_VENV source $SCRIPT_DIR/cosmos_env_libero_safety.sh"
