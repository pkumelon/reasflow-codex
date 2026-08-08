---
name: lemma-verification-workflow
description: Use when checking a proof draft for hidden assumptions, notation drift, invalid steps, or missing edge-case coverage
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

# Lemma Verification Workflow

## Overview
Verification is adversarial reading. Assume the proof is wrong until each transition, quantifier, and reused fact checks out.

## Checklist
1. Confirm the statement matches the intended assumptions.
2. Verify each implication uses a justified rule or cited result.
3. Check notation consistency and domain constraints.
4. Look for omitted edge cases and circular dependencies.

## Deliverables
- verified proof or failure report
- list of unsupported steps
- clarification requests for ambiguous notation
