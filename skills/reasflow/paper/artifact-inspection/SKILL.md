---
name: artifact-inspection
description: Use when algorithm or experiment work needs typed inspection of CSV, JSON, JSONL, PDF, image, or text artifacts
---

## Installed Root

Resolve the installed reasflow-codex private skills root before running packaged scripts:

```bash
REASFLOW_PRIVATE_SKILLS_ROOT="${REASFLOW_PRIVATE_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_PRIVATE_SKILLS_ROOT" ]; then
  if [ -d ./.codex/reasflow-skills ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$(pwd)/.codex/reasflow-skills"
  elif [ -d "$HOME/.codex/reasflow-skills" ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$HOME/.codex/reasflow-skills"
  else
    echo "reasflow private skills not found in ./.codex/reasflow-skills or $HOME/.codex/reasflow-skills" >&2
    exit 1
  fi
fi
```

# Artifact Inspection

## Overview
This skill fills the gap left by the old typed `file_tools` helpers. Use it when Codex-native reads are not enough and you need structured previews for tables, PDFs, images, or long text artifacts.

Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/paper/artifact-inspection"`.

## Helper Script

```bash
python "$SKILL_ROOT/scripts/inspect-artifact.py" --path Alg_Exp/data/results.csv --preview-rows 5
python "$SKILL_ROOT/scripts/inspect-artifact.py" --path Alg_Exp/document/report.pdf
python "$SKILL_ROOT/scripts/inspect-artifact.py" --path Alg_Exp/picture/convergence.png
python "$SKILL_ROOT/scripts/inspect-artifact.py" --path Alg_Exp/code/algorithm.py --start-line 1 --end-line 120
```

Supported types:
- `.csv`
- `.json`
- `.jsonl`
- `.pdf`
- image formats: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.svg`
- fallback text/code files

## Notes
- For PDF support, install `pypdf` in `Alg_Exp/.venv` if needed.
- For image dimensions and modes, install `Pillow` if you want richer metadata.
- Use `--emit-base64` only when you truly need the raw image payload in the terminal output.

## Deliverables
- typed preview of the requested artifact
- note on missing Python dependencies when inspection requires them
