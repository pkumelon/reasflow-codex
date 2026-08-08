---
name: aaai
description: Use when the manuscript targets AAAI and must follow its template, structure, and citation rules
---

## Installed Root

Resolve the installed reasflow private skills root before running packaged scripts:

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

# AAAI

## Overview
Use this skill when the active template or venue is AAAI. These constraints are hard venue requirements and must be passed from `paper` to `paper-subwriter` in chapter assignments.

## Core Rules
1. Keep `\usepackage{aaai2026}` (or the current year's style) with `\pdfpagewidth`/`\pdfpageheight` from the template.
2. Use the anonymous submission form for initial drafts; switch to camera-ready when the paper is accepted.
3. Preserve the expected paper order from the template instructions and keep `\section*{Acknowledgments}` and the references as the template defines them.

## Template Path
The AAAI class files are not bundled. Fetch them once per project. Set the skill root first:

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/paper/aaai"
bash "$SKILL_ROOT/scripts/fetch-aaai-template.sh" templates/aaai
```

PowerShell equivalent:

```powershell
& "$REASFLOW_PRIVATE_SKILLS_ROOT\paper\aaai\scripts\fetch-aaai-template.ps1" templates/aaai
```

This downloads `aaai2026.sty`, `aaai2026.bst`, and `aaai2026.bib` from the AAAI Author Kit.

## Deliverables
- chapter or manuscript edits that preserve AAAI structure
- explicit note when a source asset conflicts with AAAI constraints
