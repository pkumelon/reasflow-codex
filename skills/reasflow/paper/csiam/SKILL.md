---
name: csiam
description: Use when the manuscript targets CSIAM-AM and must follow its template, structure, citation, and proof-preservation rules
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

# CSIAM

## Overview
Use this skill when the active template or venue is CSIAM-AM. These constraints are hard venue requirements and must be passed from `paper` to `paper-subwriter` in chapter assignments.

## Core Rules
1. Keep `\documentclass[mathpazo]{csiam-am}` and do not swap the document class.
2. Preserve the expected paper order: abstract, AMS classification, keywords, introduction, optional related work, theory or method, experiments, conclusion, acknowledgments, bibliography.
3. Use `\cite{key}` with numbered references and keep `\bibliographystyle{plain}` unless the template already fixes it.
4. Include full theorem-like content and complete proofs from the assigned assets unless the user explicitly asks to shorten them.
5. Prefer `\ref`-style cross-references and keep theorem labels stable.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/paper/csiam"
```

## Helper Commands
Run deterministic CSIAM conformance checks:

```bash
python3 "$SKILL_ROOT/scripts/check_csiam_style.py" \
  --project-dir output/example-paper \
  --main-file main.tex \
  --format text
```

JSON mode:

```bash
python3 "$SKILL_ROOT/scripts/check_csiam_style.py" \
  --project-dir output/example-paper \
  --format json
```

Python env fallback:

```bash
uv run python "$SKILL_ROOT/scripts/check_csiam_style.py" --project-dir output/example-paper
```

## Expected Output
- required template items missing (document class, bibliography style)
- suggested metadata gaps (AMS code, keywords)
- CSIAM-specific style issues (`\thanks`, heading footnotes, `\cref` without setup)
- abstract/include-guard presence flags

## Template Path
The CSIAM class files are not bundled. Fetch them once per project:

```bash
bash "$SKILL_ROOT/scripts/fetch-csiam-template.sh" templates/csiam
```

PowerShell equivalent:

```powershell
& "$SKILL_ROOT\scripts\fetch-csiam-template.ps1" templates/csiam
```

This downloads `csiam-am.cls`, the official template, and the algorithmicx styles from the CSIAM journal site and CTAN. The pack keeps only project-agnostic files under `$SKILL_ROOT/assets/templates/csiam/` (`caption-csiam-am.cfg`, `main.tex`).

## Deliverables
- chapter or manuscript edits that preserve CSIAM structure
- explicit note when a source asset conflicts with CSIAM constraints
