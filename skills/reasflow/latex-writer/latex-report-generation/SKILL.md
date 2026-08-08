---
name: latex-report-generation
description: Use when converting experiment or analysis outputs into LaTeX-ready tables, figures, and result narratives
---

## Installed Root

Resolve the installed reasflow-codex skills root before running packaged scripts:

```bash
REASFLOW_SKILLS_ROOT="${REASFLOW_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_SKILLS_ROOT" ]; then
  if [ -d ./.agents/skills ]; then
    REASFLOW_SKILLS_ROOT="$(pwd)/.agents/skills"
  elif [ -d "$HOME/.agents/skills" ]; then
    REASFLOW_SKILLS_ROOT="$HOME/.agents/skills"
  else
    echo "reasflow-codex skills not found in ./.agents/skills or $HOME/.agents/skills" >&2
    exit 1
  fi
fi
```

# LaTeX Report Generation

## Overview
Package results for the paper without losing the raw numbers behind them. Tables, figures, and prose should all point back to the same evidence.

## Workflow
1. Select the metrics and comparisons that answer the experiment question.
2. Generate tables and figure-ready summaries from validated results only.
3. Pair each artifact with caption points and caveats.
4. Keep source result paths next to every generated report asset.

## Deliverables
- LaTeX-ready table or figure spec
- caption bullets grounded in results
- source-path note for traceability
