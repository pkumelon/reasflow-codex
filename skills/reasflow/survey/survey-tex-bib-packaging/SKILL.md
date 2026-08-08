---
name: survey-tex-bib-packaging
description: Use when producing survey and related-work LaTeX with synchronized references.bib
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

# Survey TeX and Bib Packaging

## Overview
Full survey deliveries should end as LaTeX plus BibTeX, not markdown-only drafts. Keep citation commands and bibliography keys synchronized before handoff.

This skill is the deterministic replacement for the cite/BibTeX validation slice of the upstream survey tooling. Pair it with native file inspection when you need to read or patch generated `.tex` files.

## Installed Paths
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/survey-tex-bib-packaging"` before invoking the packaged validator.

## Helper Script
- `python "$SKILL_ROOT/scripts/check-cite-bib.py" --tex survey/survey.tex --tex survey/related_works.tex --bib survey/references.bib`
- `python "$SKILL_ROOT/scripts/check-cite-bib.py" --tex survey/related_works.tex --bib survey/references.bib --json`

## Rules
1. Generate separate `.tex` and `.bib` files for full survey workflows.
2. Keep all `\\cite...{key}` usages aligned with BibTeX entry keys.
3. Use natbib-compatible citation commands (`\\citet`, `\\citep`, `\\citealp`) and avoid manually repeating author-year text.
4. Keep references.bib as the single source of citation truth for survey outputs.
5. Flag missing keys instead of inventing citations.

## Deliverables
- `survey/survey.tex`
- `survey/related_works.tex`
- `survey/references.bib`
- cite/bib validation report with missing or duplicate keys
