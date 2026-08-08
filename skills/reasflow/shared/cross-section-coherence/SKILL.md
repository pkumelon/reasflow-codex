---
name: cross-section-coherence
description: Use when checking that terminology, notation, claims, and promises stay consistent across multiple paper sections
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

# Cross Section Coherence

## Overview
Read the compiled TeX chain as a single manuscript and surface hard coherence defects: duplicate labels, undefined refs, acronym conflicts, and inconsistent term spellings.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/cross-section-coherence"
```

## Helper Commands
Run coherence checks:

```bash
python3 "$SKILL_ROOT/scripts/check_cross_section_coherence.py" \
  --project-dir output/example-paper \
  --main-file main.tex \
  --term "federated learning" \
  --term "message norm" \
  --format text
```

JSON output for automation:

```bash
python3 "$SKILL_ROOT/scripts/check_cross_section_coherence.py" \
  --project-dir output/example-paper \
  --format json
```

Python env fallback:

```bash
uv run "$SKILL_ROOT/scripts/check_cross_section_coherence.py" \
  --project-dir output/example-paper --format text
```

## Expected Output
- duplicate label definitions and where they occur
- unresolved `\ref/\eqref/\cref` targets
- acronym long-form conflicts
- tracked term variant counts (space vs hyphen usage)

## Deliverables
- inconsistency list by section
- canonical wording decisions for shared terms
- final unresolved mismatch list
