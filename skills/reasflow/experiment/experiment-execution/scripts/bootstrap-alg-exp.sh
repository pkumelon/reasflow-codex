#!/usr/bin/env bash
set -euo pipefail

workspace_root="${1:-$PWD}"
output_root="${2:-Alg_Exp}"
root="$workspace_root/$output_root"
venv_dir="$root/.venv"

mkdir -p \
  "$root/code" \
  "$root/data" \
  "$root/document" \
  "$root/picture" \
  "$root/logs" \
  "$root/cache" \
  "$root/temp" \
  "$root/latex" \
  "$root/scripts"

if [ ! -x "$venv_dir/bin/python" ] && [ ! -x "$venv_dir/Scripts/python.exe" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv "$venv_dir"
  else
    python3 -m venv "$venv_dir"
  fi
fi

cat <<MSG
Prepared workspace: $root
Virtual environment: $venv_dir
Recommended next commands:
  "$venv_dir/bin/python" -m pip install --upgrade pip
  "$venv_dir/bin/pip" install numpy scipy matplotlib pandas scikit-learn optuna pypdf
If bin/ paths do not exist on your platform, use Scripts/ equivalents.
If environment creation fails, install uv and rerun: uv venv "$venv_dir"
MSG
