---
name: anti-hallucination-markers
description: Use when drafting introductions or abstracts that need explicit markers for unsupported claims, missing evidence, or scope drift
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

# Anti-Hallucination Markers

## Overview
Mark weak spots while drafting instead of letting them ship as confident prose. Unsupported novelty, performance, or scope claims should stay visibly flagged until evidence lands.

## Marker Set
- `[needs-citation]` for factual claims without a source
- `[needs-result]` for performance or ablation claims without experiment evidence
- `[scope-check]` for claims that overreach the actual setting
- `[terminology-check]` for wording that does not match the paper body
- `[remove-if-unproven]` for claims that may need deletion instead of repair

## Workflow
1. Draft the paragraph normally.
2. Tag every sentence that depends on evidence outside the current draft.
3. Resolve or delete marked claims before final polishing.
4. Remove markers only after the supporting section, figure, table, or citation is real.
5. Treat any remaining marker as a failed deliverable; markers are drafting aids, not acceptable final output.

## Deliverables
- marked-up intro or abstract draft
- evidence ledger for every flagged sentence
- deletion list for claims that stayed unsupported
