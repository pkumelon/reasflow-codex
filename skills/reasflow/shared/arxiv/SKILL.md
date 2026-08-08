---
name: arxiv
description: Search, download, and summarize academic papers from arXiv. Use when user says "search arxiv", "download paper", "fetch arxiv", "arxiv search", "get paper pdf", or wants to find and save papers from arXiv to the local paper library.
argument-hint: [query-or-arxiv-id]
allowed-tools: Bash(*), Read, Write
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

# arXiv Paper Search & Download

Search topic or arXiv paper ID: $ARGUMENTS

## Constants

- **PAPER_DIR** - Local directory to save downloaded PDFs. Default: `papers/` in the current project directory.
- **MAX_RESULTS = 10** - Default number of search results.
- **PYTHON_RUNNER = python** - Use the current Python environment; prefer a project virtual environment when available.
- **FETCH_SCRIPT** - `tools/arxiv_fetch.py` in the skill directory (same level as SKILL.md), or relative to the current project. Fall back to inline Python if not found.
- **WIKI_SCRIPT** - `tools/research_wiki.py` in the skill directory (same level as SKILL.md), or relative to the current project.

> Overrides (append to arguments):
> - `/arxiv "attention mechanism" - max: 20` - return up to 20 results
> - `/arxiv "2301.07041" - download` - download a specific paper by ID
> - `/arxiv "query" - dir: literature/` - save PDFs to a custom directory
> - `/arxiv "query" - download: all` - download all result PDFs

## Workflow

### Step 1: Parse Arguments

Parse `$ARGUMENTS` for directives:

- **Query or ID**: main search term or a bare arXiv ID such as `2301.07041` or `cs/0601001`
- **`- max: N`**: override MAX_RESULTS (e.g., `- max: 20`)
- **`- dir: PATH`**: override PAPER_DIR (e.g., `- dir: literature/`)
- **`- download`**: download the first result's PDF after listing
- **`- download: all`**: download PDFs for all results

If the argument matches an arXiv ID pattern (`YYMM.NNNNN` or `category/NNNNNNN`), skip the search and go directly to Step 3.

### Step 2: Search arXiv

Ensure the helper dependency is available in the runtime Python environment:

```bash
python -m pip install arxiv
```

Locate the fetch script:

```bash
FETCH_SCRIPT="$REASFLOW_SKILLS_ROOT/arxiv/tools/arxiv_fetch.py"
```

**If FETCH_SCRIPT is found**, run:

```bash
python "$FETCH_SCRIPT" search "QUERY" --max MAX_RESULTS
```

**If FETCH_SCRIPT is not found**, fall back to inline Python:

```bash
python - <<'PYEOF'
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = "http://www.w3.org/2005/Atom"
query = urllib.parse.quote("QUERY")
url = (f"http://export.arxiv.org/api/query"
       f"?search_query={query}&start=0&max_results=MAX_RESULTS"
       f"&sortBy=relevance&sortOrder=descending")
with urllib.request.urlopen(url, timeout=30) as r:
    root = ET.fromstring(r.read())
papers = []
for entry in root.findall(f"{{{NS}}}entry"):
    aid = entry.findtext(f"{{{NS}}}id", "").split("/abs/")[-1].split("v")[0]
    title = (entry.findtext(f"{{{NS}}}title", "") or "").strip().replace("\n", " ")
    abstract = (entry.findtext(f"{{{NS}}}summary", "") or "").strip().replace("\n", " ")
    authors = [a.findtext(f"{{{NS}}}name", "") for a in entry.findall(f"{{{NS}}}author")]
    published = entry.findtext(f"{{{NS}}}published", "")[:10]
    cats = [c.get("term", "") for c in entry.findall(f"{{{NS}}}category")]
    papers.append({
        "id": aid,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "published": published,
        "categories": cats,
        "pdf_url": f"https://arxiv.org/pdf/{aid}.pdf",
        "abs_url": f"https://arxiv.org/abs/{aid}",
    })
print(json.dumps(papers, ensure_ascii=False, indent=2))
PYEOF
```

Present results as a table:

```text
| # | arXiv ID   | Title               | Authors        | Date       | Category |
|---|------------|---------------------|----------------|------------|----------|
| 1 | 2301.07041 | Attention Is All... | Vaswani et al. | 2017-06-12 | cs.LG    |
```

### Step 3: Fetch Details for a Specific ID

When a single paper ID is requested (either directly or from Step 2):

```bash
python "$SCRIPT" search "id:ARXIV_ID" --max 1
# or fallback:
python -c "
import urllib.request, xml.etree.ElementTree as ET
NS = 'http://www.w3.org/2005/Atom'
url = 'http://export.arxiv.org/api/query?id_list=ARXIV_ID'
with urllib.request.urlopen(url, timeout=30) as r:
    root = ET.fromstring(r.read())
# print full details ...
"
```

Display: title, all authors, categories, full abstract, published date, PDF URL, abstract URL.

### Step 4: Download PDFs

When download is requested, for each paper ID to download:

```bash
# Using fetch script:
python "$SCRIPT" download ARXIV_ID --dir PAPER_DIR

# Fallback:
mkdir -p PAPER_DIR && python -c "
import pathlib
import sys
import urllib.request

out = pathlib.Path('PAPER_DIR/ARXIV_ID.pdf')
if out.exists():
    print(f'Already exists: {out}')
    sys.exit(0)
req = urllib.request.Request(
    'https://arxiv.org/pdf/ARXIV_ID.pdf',
    headers={'User-Agent': 'arxiv-skill/1.0'},
)
with urllib.request.urlopen(req, timeout=60) as r:
    out.write_bytes(r.read())
print(f'Downloaded: {out} ({out.stat().st_size // 1024} KB)')
"
```

After each download:

- Confirm file size > 10 KB (reject smaller files - likely an error HTML page)
- Add a 1-second delay between consecutive downloads to avoid rate limiting
- Report: `Downloaded: papers/2301.07041.pdf (842 KB)`

### Step 5: Summarize

For each paper (downloaded or fetched by API):

```markdown
## [Title]

- **arXiv**: [ID] - [abs_url]
- **Authors**: [full author list]
- **Date**: [published]
- **Categories**: [cs.LG, cs.AI, ...]
- **Abstract**: [full abstract]
- **Key contributions** (extracted from abstract):
  - [contribution 1]
  - [contribution 2]
  - [contribution 3]
- **Local PDF**: papers/[ID].pdf (if downloaded)
```

### Step 6: Update Research Wiki (if active)

**Required when `research-wiki/` exists in the project**; skip silently
otherwise. After presenting results, ingest every paper returned by
this invocation (both the search hits shown and any downloaded PDFs)
into the wiki:

```
if [ -d research-wiki/ ]:
    WIKI_SCRIPT="$REASFLOW_SKILLS_ROOT/arxiv/tools/research_wiki.py"
    if [ -f "$WIKI_SCRIPT" ]; then
        for each arxiv_id in results:
            python "$WIKI_SCRIPT" ingest_paper research-wiki/ \
                --arxiv-id "<arxiv_id>"
    else
        echo "warning: research_wiki.py helper not found at $WIKI_SCRIPT; wiki ingest skipped" >&2
    fi
```

The helper handles metadata fetch, slug, dedup, page creation, index
rebuild, and log append in a single call — **do not handwrite
`papers/<slug>.md`**. Missed ingests can be backfilled later
with `python "$WIKI_SCRIPT" sync research-wiki/ --arxiv-ids <id1>,<id2>,...`.

### Step 7: Final Output

Summarize what was done:

- `Found N papers for "query"`
- `Downloaded: papers/2301.07041.pdf (842 KB)` (for each download)
- `Wiki-ingested N papers` (if `research-wiki/` was present)
- Any warnings (rate limit hit, file too small, already exists)

Suggest follow-up skills:

```text
/research-lit "topic"     - multi-source review: Zotero + Obsidian + local PDFs + web
/novelty-check "idea"     - verify your idea is novel against these papers
```

## Key Rules

- Always show the arXiv ID prominently - users need it for citations and reproducibility
- Verify downloaded PDFs: file must be > 10 KB; warn and delete if smaller
- Rate limit: wait 1 second between consecutive PDF downloads; retry once after 5 seconds on HTTP 429
- Never overwrite an existing PDF at the same path - skip it and report "already exists"
- Handle both arXiv ID formats: new (`2301.07041`) and old (`cs/0601001`)
- PAPER_DIR is created automatically if it does not exist
- Install Python packages with `python -m pip install <pkg>` and run Python scripts with `python`; prefer the project virtual environment when available
- If the arXiv API is unreachable, report the error clearly and suggest using `/research-lit` with `- sources: web` as a fallback
