---
name: completeness-review
description: Use when judging whether a paper draft is complete enough to hand off, submit, or move into final polishing
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

# Completeness Review

## Overview
Completeness means every promised part of the paper exists and every major claim has visible support. Use deterministic checks before qualitative review.

## Helper Script
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/paper/completeness-review"`.

```bash
python3 "$SKILL_ROOT/scripts/review-manuscript.py" --project-dir paper --main-file main.tex
```

Then pair it with:

```bash
python3 "$REASFLOW_PRIVATE_SKILLS_ROOT/paper/check-asset-usage/scripts/check_asset_usage.py" \
  --assets-dir assets \
  --output-dir paper
```

## Checklist
1. Verify all required sections and appendices exist.
2. Confirm every contribution claim has supporting proof, experiment, or citation.
3. Check figure, table, bibliography, and asset coverage.
4. Mark what is missing, weak, or still placeholder text.

## Deliverables
- readiness verdict
- must-fix list before handoff
- optional polish list for later passes
