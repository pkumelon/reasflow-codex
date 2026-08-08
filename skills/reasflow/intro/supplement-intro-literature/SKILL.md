---
name: supplement-intro-literature
description: Resolve missing or incomplete Introduction bibliography entries from organized citation claims, paper titles, arXiv IDs, or DOIs. Use when survey/references.bib lacks keys needed by the Intro claim ledger, when an Introduction needs an explicitly requested paper, or when ReaScholar and Semantic Scholar metadata must be merged into a verified source bibliography before drafting.
---

# Supplement Introduction Literature

Build a verified source bibliography before the Introduction writer runs. Query ReaScholar first; use Semantic Scholar for metadata enrichment or fallback. Preserve an auditable trace and never invent an unresolved entry.

## Resolve the installed root

```bash
REASFLOW_PRIVATE_SKILLS_ROOT="${REASFLOW_PRIVATE_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_PRIVATE_SKILLS_ROOT" ]; then
  if [ -d ./.codex/reasflow-skills ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$(pwd)/.codex/reasflow-skills"
  elif [ -d "$HOME/.codex/reasflow-skills" ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$HOME/.codex/reasflow-skills"
  else
    echo "reasflow private skills not found" >&2
    exit 1
  fi
fi
SUPPLEMENT_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/intro/supplement-intro-literature"
```

## Run the default supplementation workflow

Run after `intro/organized_info.json` exists and before preparing the writer task:

```bash
python3 "$SUPPLEMENT_ROOT/scripts/supplement-intro-literature.py" \
  --workspace . \
  --bib-input survey/references.bib \
  --bib-output intro/source_references.bib \
  --citation-json intro/organized_info.json \
  --trace-output intro/literature_retrieval.json
```

Omit `--bib-input` when the survey bibliography does not exist. The script copies one canonical entry per existing key, reports and removes duplicate input keys, looks up only absent candidates, and reports:

- claim keys missing before lookup;
- entries added from ReaScholar or Semantic Scholar;
- claim keys still unresolved after lookup;
- whether an S2 key is configured, without recording its value.

Use `intro/source_references.bib`, not the incomplete survey bibliography, as the writer's verified reference catalog.

## Source policy

1. Query ReaScholar first in `fast` mode.
2. Match title-only results conservatively; reject weak title matches.
3. For key-only recovery, combine the parsed key with its claim text, inspect up to five S2 candidates, and require author, year, title-hint, and claim-context agreement.
4. Reject ambiguous candidates. A search result is not an identity match merely because it is ranked first.
5. Fall back to Semantic Scholar when ReaScholar has no acceptable result.
6. Enrich a ReaScholar result with S2 metadata when an S2 key is available.
7. Preserve an upstream BibTeX key only after the returned paper identity is verified.
8. Leave unresolved keys in the trace. Exclude them from the writer contract instead of fabricating BibTeX.

Override the policy only when diagnosing a source:

```bash
python3 "$SUPPLEMENT_ROOT/scripts/supplement-intro-literature.py" \
  --workspace . \
  --source semantic_scholar \
  --paper "arXiv:1602.05629" \
  --bib-output intro/source_references.bib \
  --trace-output intro/literature_retrieval.json
```

Repeat `--paper` for user-requested titles, arXiv IDs, or DOIs. Never use a generic topic query to manufacture support for an already-written claim.

## Configure a Semantic Scholar key

Use unauthenticated S2 only for light fallback. When requests are rate-limited or repeated enrichment is needed, read [Semantic Scholar API key](references/semantic-scholar-api-key.md), help the user apply through the official form, and configure `SEMANTIC_SCHOLAR_API_KEY` outside the workspace. Accept `S2_API_KEY` only as a compatibility alias.

Never print, persist, or pass an API key in a command argument, prompt, trace, JSON, or BibTeX file.

## Required outputs

- `intro/source_references.bib`: verified superset used to prepare the writer contract;
- `intro/literature_retrieval.json`: source, query, match status, and unresolved-key trace.

Do not replace the final deterministic `intro/references.bib`; the Introduction finalizer creates that file from entries actually cited in the accepted draft.
