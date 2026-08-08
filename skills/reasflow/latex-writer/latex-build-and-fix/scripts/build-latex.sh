#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON:-python3}"

project_dir="."
main_file="${1:-main.tex}"

if [ "$#" -gt 0 ]; then
  shift
fi

if [[ "$main_file" == */* ]]; then
  project_dir="$(dirname "$main_file")"
  main_file="$(basename "$main_file")"
fi

if ! command -v "$python_bin" >/dev/null 2>&1; then
  printf 'python3 is required for build-latex.sh; if needed run: uv venv && uv pip install pymupdf\n' >&2
  exit 1
fi

exec "$python_bin" "$script_dir/build_latex.py" \
  --project-dir "$project_dir" \
  --main-file "$main_file" \
  "$@"
