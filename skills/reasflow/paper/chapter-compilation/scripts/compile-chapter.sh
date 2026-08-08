#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  printf 'usage: %s <main.tex> <chapter.tex> [--keep] [--engine pdflatex|xelatex|lualatex]\n' "$0" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON:-python3}"
main_tex="$1"
chapter_tex="$2"
shift 2

project_dir="$(dirname "$main_tex")"
main_file="$(basename "$main_tex")"
chapter_file="$(basename "$chapter_tex")"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  printf 'python3 is required for compile-chapter.sh; if needed run: uv venv && uv pip install pymupdf\n' >&2
  exit 1
fi

exec "$python_bin" "$script_dir/compile_chapter.py" \
  --project-dir "$project_dir" \
  --main-file "$main_file" \
  --chapter "$chapter_file" \
  "$@"
