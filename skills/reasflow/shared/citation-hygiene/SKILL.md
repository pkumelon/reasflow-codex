---
name: citation-hygiene
description: Use when checking citation coverage, unsupported claims, bibliography consistency, or missing attribution in research writing
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

# Citation Hygiene

## Overview
Enforce cite/bib consistency and flag claim-like lines that may need citations before submission.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/citation-hygiene"
```

## Helper Commands
Run cite/bib and claim checks:

```bash
python3 "$SKILL_ROOT/scripts/check_citation_hygiene.py" \
  --project-dir output/example-paper \
  --main-file main.tex \
  --format text
```

Allow unused BibTeX entries while still failing on missing cite keys:

```bash
python3 "$SKILL_ROOT/scripts/check_citation_hygiene.py" \
  --project-dir output/example-paper \
  --allow-unused \
  --format json
```

Strict Introduction check with claim provenance and the writer trace:

```bash
python3 "$SKILL_ROOT/scripts/check_citation_hygiene.py" \
  --project-dir intro \
  --main-file main.tex \
  --bib intro/references.bib \
  --claim-ledger intro/organized_info.json \
  --trace-json intro/citation_report.json \
  --allow-unused \
  --strict \
  --format json
```

Strict mode fails on sentence-level uncited literature claims, unresolved evidence markers, and invalid claim-to-citation trace entries in addition to cite/BibTeX consistency errors.

Python env fallback:

```bash
uv run "$SKILL_ROOT/scripts/check_citation_hygiene.py" \
  --project-dir output/example-paper --format text
```

## Expected Output
- missing citation keys (`\cite` in TeX but absent in `.bib`)
- duplicate BibTeX keys
- optional unused bib key list
- unsupported claim candidates (file + line + section)

## Deliverables
- unsupported-claim list
- bibliography cleanup list
- sections still missing citation coverage
