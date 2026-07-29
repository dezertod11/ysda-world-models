#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COSMOS_REPO="$PROJECT_ROOT/cosmos-policy"
COSMOS_VENV="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"

if [[ ! -x "$UV_BIN" ]]; then
  echo "uv is missing: $UV_BIN" >&2
  exit 1
fi

if [[ ! -f "$COSMOS_REPO/pyproject.toml" ]]; then
  echo "Cosmos Policy checkout is missing: $COSMOS_REPO" >&2
  exit 1
fi

"$UV_BIN" python install 3.10

export UV_PROJECT_ENVIRONMENT="$COSMOS_VENV"
cd "$COSMOS_REPO"
"$UV_BIN" sync --extra cu128 --group libero --python 3.10
"$UV_BIN" pip install --python "$COSMOS_VENV/bin/python" --editable "$PROJECT_ROOT/LIBERO-PRO"
"$UV_BIN" pip install --python "$COSMOS_VENV/bin/python" ipykernel
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/patch_robosuite_egl.py"

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

"$COSMOS_VENV/bin/python" -m ipykernel install --user \
  --name ysda-cosmos-policy-libero \
  --display-name "YSDA Cosmos Policy LIBERO (MLSpace Py3.10)"

source "$SCRIPT_DIR/mlspace_env.sh"
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/verify_mlspace_cosmos.py"

echo
echo "MLSpace Cosmos environment is ready."
echo "Activate with: source $SCRIPT_DIR/mlspace_env.sh"
