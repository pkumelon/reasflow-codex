---
name: chapter-compilation
description: Use when compiling a single chapter in isolation or checking chapter-local LaTeX regressions before handoff
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

# Chapter Compilation

## Overview
This skill restores the original paper-agent behavior: compile one chapter independently without waiting for unrelated chapters to be finished.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/paper/chapter-compilation"
```

## Helper Commands
Wrapper:

```bash
bash "$SKILL_ROOT/scripts/compile-chapter.sh" paper/main.tex paper/method.tex
```

Direct Python:

```bash
python3 "$SKILL_ROOT/scripts/compile_chapter.py" \
  --project-dir paper \
  --main-file main.tex \
  --chapter method.tex
```

Python env fallback:

```bash
uv run python "$SKILL_ROOT/scripts/compile_chapter.py" \
  --project-dir paper \
  --main-file main.tex \
  --chapter method.tex
```

## Output
The helper returns structured JSON with:
- `success`
- `pdf_path`
- `total_pages`
- `preview_images`
- `errors`
- `warnings`

## What The Helper Does
1. Extract preamble from `main.tex`.
2. Generate `_chapter_<name>.tex` with only the target `\input{...}`.
3. Compile via `latexmk` or manual engine plus BibTeX passes.
4. Parse compiler output into structured errors and warnings.
5. Render a small set of preview PNGs when local PDF tools are available.

## Deliverables
- isolated chapter compile status
- preview image paths for visual inspection when available
- explicit list of chapter-local errors to fix before handoff
