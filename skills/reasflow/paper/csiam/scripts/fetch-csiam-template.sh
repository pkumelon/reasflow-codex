#!/usr/bin/env bash
set -euo pipefail

dest="${1:-templates/csiam}"
csiam_cls_url="https://admin.global-sci.org/uploads/ueditor/file/20240614/1718345545407042.cls"
csiam_tex_url="https://admin.global-sci.org/uploads/ueditor/file/20240513/1715569785769430.tex"
algorithmicx_urls=(
  "https://mirrors.tuna.tsinghua.edu.cn/CTAN/macros/latex/contrib/algorithmicx.zip"
  "https://mirror.easyname.at/ctan/macros/latex/contrib/algorithmicx.zip"
)
guidelines_url="https://journal.hep.com.cn/csiam-am/EN/guidelines"
ua="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

command -v unzip >/dev/null 2>&1 || { echo "missing required command: unzip" >&2; exit 1; }

download() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -A "$ua" "$1" -o "$2" 2>/dev/null
  elif command -v wget >/dev/null 2>&1; then
    wget -q -U "$ua" "$1" -O "$2" 2>/dev/null
  else
    return 1
  fi
}

mkdir -p "$dest"
download "$csiam_cls_url" "$dest/csiam-am.cls" || {
  echo "download failed: $csiam_cls_url" >&2
  echo "CSIAM class and template are also available from: $guidelines_url" >&2
  exit 1
}
download "$csiam_tex_url" "$dest/csiam-am-template.tex" || {
  echo "download failed: $csiam_tex_url" >&2
  echo "CSIAM class and template are also available from: $guidelines_url" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
for u in "${algorithmicx_urls[@]}"; do
  download "$u" "$tmp/algorithmicx.zip" && break
done
[ -s "$tmp/algorithmicx.zip" ] || { echo "download failed: algorithmicx (CTAN)" >&2; exit 1; }

unzip -o -q "$tmp/algorithmicx.zip" -d "$tmp"
cp "$tmp/algorithmicx/algcompatible.sty" "$tmp/algorithmicx/algorithmicx.sty" "$tmp/algorithmicx/algpseudocode.sty" "$dest/"

echo "CSIAM template ready: $dest"
