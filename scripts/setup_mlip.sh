#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-cpu}"
case "$mode" in
  cpu) torch_backend=cpu ;;
  cuda) torch_backend=auto ;;
  *) echo 'Usage: bash scripts/setup_mlip.sh cpu|cuda' >&2; exit 2 ;;
esac
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.python"
uv venv --python 3.12 --allow-existing .venv-mlip
uv pip install --python .venv-mlip/bin/python --torch-backend "$torch_backend" --reinstall-package torch 'fairchem-core==2.22.0'
uv pip install --python .venv-mlip/bin/python -e .
mkdir -p runs/setup
uv pip freeze --python .venv-mlip/bin/python > "runs/setup/requirements-mlip-${mode}.installed.txt"
.venv-mlip/bin/python -m cyp_pipeline doctor
