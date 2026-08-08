#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
REASCHOLAR_BASE_URL = os.getenv(
    "REASCHOLAR_BASE_URL", "https://scholar.reaslab.io"
).rstrip("/")
SEARCH_FIELDS = (
    "paperId,title,authors,year,abstract,citationCount,url,externalIds,"
    "venue,publicationDate"
)
PAPER_FIELDS = (
    "paperId,title,authors,year,abstract,citationCount,referenceCount,url,"
    "externalIds,venue,publicationDate,fieldsOfStudy,s2FieldsOfStudy"
)
EDGE_FIELDS = "paperId,title,authors,year,citationCount,url,externalIds,venue"
TIMEOUT_SECONDS = 30
REASCHOLAR_TIMEOUT_SECONDS = 12
MAX_RETRIES = 3
BIB_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)


def semantic_scholar_api_key() -> str:
    """Return the configured S2 key without exposing it in artifacts or logs."""
    return (
        os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
        or os.getenv("S2_API_KEY", "").strip()
    )


def repair_mojibake_text(text: str) -> str:
    value = str(text or "")
    replacements = {
        "â€“": "--",
        "â€”": "---",
        "âˆ’": "-",
        "Â ": " ",
        "Â": "",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    return value


def normalize_paper_id(raw: str) -> str:
    paper_id = raw.strip()
    if paper_id.lower().startswith("arxiv:"):
        return "arXiv:" + paper_id.split(":", 1)[1]
    if re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", paper_id):
        return f"arXiv:{paper_id}"
    if paper_id.startswith("10."):
        return f"DOI:{paper_id}"
    return paper_id


def request_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    filtered = {
        key: value for key, value in params.items() if value is not None and value != ""
    }
    query = urllib.parse.urlencode(filtered)
    url = f"{S2_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"

    headers = {"Accept": "application/json"}
    api_key = semantic_scholar_api_key()
    if api_key:
        headers["x-api-key"] = api_key

    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as resp:
                payload = resp.read().decode("utf-8")
                return json.loads(payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < MAX_RETRIES - 1:
                retry_after = exc.headers.get("Retry-After")
                wait_seconds = (
                    float(retry_after)
                    if retry_after and retry_after.replace(".", "", 1).isdigit()
                    else float(attempt + 1) * 2.0
                )
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(
                f"Semantic Scholar error {exc.code}: {body[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(float(attempt + 1) * 2.0)
                continue
            raise RuntimeError(f"Network error: {exc}") from exc

    raise RuntimeError("Semantic Scholar request failed after retries")


def post_reascholar_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{REASCHOLAR_BASE_URL}{path}"
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ReasFlow-Survey/1.0",
    }
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=REASCHOLAR_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_reascholar_json(
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = params or {}
    filtered = {
        key: value for key, value in params.items() if value is not None and value != ""
    }
    query = urllib.parse.urlencode(filtered)
    url = f"{REASCHOLAR_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ReasFlow-Survey/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=REASCHOLAR_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_arxiv_from_key(value: str) -> str:
    match = re.match(r"^(\d{4}\.\d{4,5})(?:v\d+)?(?:__|$)", value or "")
    return match.group(1) if match else ""


def canonical_paper_url(arxiv_id: str, doi: str) -> str:
    clean_doi = str(doi or "").strip()
    if clean_doi.startswith("10."):
        return f"https://doi.org/{clean_doi}"
    clean_arxiv = extract_arxiv_from_key(arxiv_id) or re.sub(
        r"v\d+$", "", str(arxiv_id or "").strip()
    )
    if clean_arxiv:
        return f"https://arxiv.org/abs/{clean_arxiv}"
    return ""


def split_reascholar_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return clean_authors(value)
    if isinstance(value, str):
        return [name.strip() for name in re.split(r";|\band\b", value) if name.strip()]
    return []


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def normalize_reascholar_paper(
    paper: dict[str, Any],
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail = detail or {}
    raw = paper.get("raw") if isinstance(paper.get("raw"), dict) else {}
    detail_raw = detail.get("raw") if isinstance(detail.get("raw"), dict) else {}
    layer1 = (
        detail_raw.get("layer1") if isinstance(detail_raw.get("layer1"), dict) else {}
    )
    survey = (
        detail_raw.get("survey") if isinstance(detail_raw.get("survey"), dict) else {}
    )
    display = detail.get("display") if isinstance(detail.get("display"), dict) else {}
    overview = display.get("overview") if isinstance(display.get("overview"), dict) else {}
    publication = (
        overview.get("publication") if isinstance(overview.get("publication"), dict) else {}
    )
    classification = (
        overview.get("classification")
        if isinstance(overview.get("classification"), dict)
        else {}
    )

    paper_key = first_text(
        paper.get("paper_key"),
        raw.get("paper_key") if isinstance(raw, dict) else "",
        detail.get("paper_key"),
    )
    arxiv_id = extract_arxiv_from_key(paper_key)
    external_ids: dict[str, Any] = {}
    if arxiv_id:
        external_ids["ArXiv"] = arxiv_id
    doi = first_text(
        paper.get("doi"),
        raw.get("doi"),
        layer1.get("doi"),
        survey.get("doi"),
    )
    if doi.startswith("10."):
        external_ids["DOI"] = doi

    links = paper.get("links") if isinstance(paper.get("links"), dict) else {}
    links = dict(links)
    if paper_key:
        links.setdefault(
            "reascholar_api",
            f"{REASCHOLAR_BASE_URL}/api/papers/{urllib.parse.quote(paper_key)}",
        )

    authors = split_reascholar_authors(
        paper.get("authors")
        or raw.get("authors")
        or layer1.get("authors")
        or survey.get("authors")
        or publication.get("authors")
    )
    year = (
        paper.get("year")
        or raw.get("year")
        or survey.get("year")
        or publication.get("year")
        or None
    )
    title = first_text(
        paper.get("title"),
        raw.get("title"),
        layer1.get("title"),
        survey.get("title"),
        detail.get("title"),
    )
    profile = first_text(
        overview.get("profile"),
        paper.get("profile"),
        raw.get("profile"),
        layer1.get("profile"),
        survey.get("summary"),
        paper.get("summary_markdown"),
        detail.get("summary_markdown"),
    )
    bibtex = repair_mojibake_text(
        first_text(publication.get("bibtex"), survey.get("bibtex"))
    )
    domain = paper.get("domain") if isinstance(paper.get("domain"), dict) else {}
    domain_name = first_text(
        domain.get("l2_name_en"),
        classification.get("l2_name_en"),
        domain.get("l1_name_en"),
        classification.get("l1_name_en"),
        paper.get("category"),
        raw.get("category"),
    )

    normalized = {
        "id": f"reascholar:{paper_key}" if paper_key else "",
        "paperId": f"reascholar:{paper_key}" if paper_key else "",
        "paper_key": paper_key,
        "title": title,
        "authors": authors,
        "year": year,
        "venue": first_text(publication.get("venue"), domain_name),
        "abstract": profile,
        "abs": profile,
        "citationCount": paper.get("citationCount") or 0,
        "referenceCount": paper.get("referenceCount") or 0,
        "url": canonical_paper_url(arxiv_id, doi),
        "externalIds": external_ids,
        "publicationDate": "",
        "raw_bibtex": bibtex,
        "best_citation_bibtex": bibtex,
        "best_citation_source": "reascholar" if bibtex else "",
        "best_citation_venue": "arxiv" if arxiv_id and bibtex else "",
        "source": "reascholar",
        "sources": ["reascholar"],
        "score": paper.get("score"),
        "summary_markdown": first_text(
            paper.get("summary_markdown"),
            detail.get("summary_markdown"),
        ),
        "topics": [domain_name] if domain_name else [],
        "strengths": first_text(
            paper.get("profile"),
            overview.get("profile"),
            paper.get("summary_markdown"),
        ),
        "weaknesses": "",
        "links": links,
    }
    return normalized


def merge_s2_metadata(
    primary: dict[str, Any],
    s2_paper: dict[str, Any],
) -> dict[str, Any]:
    if not s2_paper:
        return primary
    merged = dict(primary)
    for field in ("citationCount", "referenceCount", "publicationDate"):
        if not merged.get(field) and s2_paper.get(field):
            merged[field] = s2_paper.get(field)
    for field in ("venue", "url"):
        if not merged.get(field) and s2_paper.get(field):
            merged[field] = s2_paper.get(field)
    if not merged.get("abstract") and s2_paper.get("abstract"):
        merged["abstract"] = s2_paper.get("abstract")
        merged["abs"] = s2_paper.get("abstract")
    elif s2_paper.get("abstract"):
        merged["s2_abstract"] = s2_paper.get("abstract")
    if not merged.get("authors") and s2_paper.get("authors"):
        merged["authors"] = s2_paper.get("authors")
    if not merged.get("year") and s2_paper.get("year"):
        merged["year"] = s2_paper.get("year")

    external = merged.get("externalIds")
    if not isinstance(external, dict):
        external = {}
    s2_external = s2_paper.get("externalIds")
    if isinstance(s2_external, dict):
        external = {**s2_external, **external}
    merged["externalIds"] = external
    merged["semanticScholarPaperId"] = s2_paper.get("paperId", "")
    sources = merged.get("sources") if isinstance(merged.get("sources"), list) else []
    if "semantic_scholar" not in sources:
        sources = [*sources, "semantic_scholar"]
    merged["sources"] = sources
    merged["source"] = "+".join(sources) if sources else merged.get("source", "")
    return merged


def s2_lookup_paper(identifier: str) -> dict[str, Any] | None:
    if not identifier:
        return None
    try:
        payload = request_json(
            f"/paper/{urllib.parse.quote(normalize_paper_id(identifier), safe='')}",
            {"fields": PAPER_FIELDS},
        )
        return normalize_paper(payload)
    except Exception:
        return None


def s2_search(title: str, limit: int = 5) -> list[dict[str, Any]]:
    if not title:
        return []
    try:
        payload = request_json(
            "/paper/search",
            {
                "query": title,
                "limit": max(1, min(limit, 20)),
                "fields": PAPER_FIELDS,
            },
        )
    except Exception:
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return [normalize_paper(paper) for paper in data if isinstance(paper, dict)]


def s2_search_one(title: str) -> dict[str, Any] | None:
    papers = s2_search(title, limit=1)
    return papers[0] if papers else None


def supplement_with_s2(paper: dict[str, Any]) -> dict[str, Any]:
    external = (
        paper.get("externalIds") if isinstance(paper.get("externalIds"), dict) else {}
    )
    identifiers = []
    if external.get("ArXiv"):
        identifiers.append(f"arXiv:{external['ArXiv']}")
    if external.get("DOI"):
        identifiers.append(f"DOI:{external['DOI']}")
    identifiers.append(str(paper.get("title") or ""))

    s2_paper = None
    for identifier in identifiers:
        if not identifier:
            continue
        if identifier.startswith("arXiv:") or identifier.startswith("DOI:"):
            s2_paper = s2_lookup_paper(identifier)
        else:
            s2_paper = s2_search_one(identifier)
        if s2_paper:
            break
    return merge_s2_metadata(paper, s2_paper or {})


def fetch_reascholar_detail(paper_key: str) -> dict[str, Any]:
    if not paper_key:
        return {}
    try:
        return get_reascholar_json(
            f"/api/search/papers/{urllib.parse.quote(paper_key, safe='')}",
            {
                "include_markdown": "false",
                "include_prover": "false",
                "statement_limit": 6,
            },
        )
    except Exception:
        return {}


def search_reascholar(query: str, limit: int, mode: str) -> list[dict[str, Any]]:
    payload = post_reascholar_json(
        "/api/search",
        {
            "query": query,
            "top_k": max(1, min(limit, 100)),
            "mode": mode,
            "response_format": "structured",
        },
    )
    papers: list[dict[str, Any]] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict) or item.get("result_type") != "paper":
            continue
        paper_key = str(item.get("paper_key") or "")
        detail = fetch_reascholar_detail(paper_key)
        papers.append(normalize_reascholar_paper(item, detail))
    return papers


def find_reascholar_paper(paper_id: str, mode: str = "fast") -> dict[str, Any] | None:
    normalized_id = normalize_paper_id(paper_id)
    arxiv_match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", normalized_id)
    wanted_arxiv = arxiv_match.group(1) if arxiv_match else ""
    wanted_doi = normalized_id[4:] if normalized_id.startswith("DOI:") else ""
    try:
        candidates = search_reascholar(normalized_id, 5, mode)
    except Exception:
        candidates = []
    if not candidates:
        return None
    selected = candidates[0]
    if wanted_arxiv:
        for candidate in candidates:
            external = candidate.get("externalIds")
            if isinstance(external, dict) and external.get("ArXiv") == wanted_arxiv:
                selected = candidate
                break
        else:
            return None
    if wanted_doi:
        wanted_doi_lower = wanted_doi.lower()
        for candidate in candidates:
            external = candidate.get("externalIds")
            doi = ""
            if isinstance(external, dict):
                doi = str(external.get("DOI") or "")
            if doi.lower() == wanted_doi_lower:
                selected = candidate
                break
        else:
            return None
    detail = fetch_reascholar_detail(str(selected.get("paper_key") or ""))
    return normalize_reascholar_paper(selected, detail)


def clean_authors(authors: Any) -> list[str]:
    if not isinstance(authors, list):
        return []
    names: list[str] = []
    for author in authors:
        if isinstance(author, dict):
            name = str(author.get("name", "")).strip()
        else:
            name = str(author).strip()
        if name:
            names.append(name)
    return names


def normalize_paper(paper: dict[str, Any]) -> dict[str, Any]:
    external = paper.get("externalIds")
    if not isinstance(external, dict):
        external = {}
    return {
        "paperId": paper.get("paperId", ""),
        "title": paper.get("title", ""),
        "authors": clean_authors(paper.get("authors", [])),
        "year": paper.get("year"),
        "venue": paper.get("venue", ""),
        "abstract": paper.get("abstract", ""),
        "citationCount": paper.get("citationCount", 0),
        "referenceCount": paper.get("referenceCount", 0),
        "url": paper.get("url", ""),
        "externalIds": external,
        "publicationDate": paper.get("publicationDate", ""),
    }


def bib_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def key_slug(text: str, fallback: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    if not tokens:
        return fallback
    return tokens[0]


def build_bib_key(paper: dict[str, Any], used: set[str]) -> str:
    authors = paper.get("authors", [])
    first_author = key_slug(authors[0] if authors else "", "paper")
    year = str(paper.get("year") or "nd")
    first_word = key_slug(str(paper.get("title", "")), "work")
    base = f"{first_author}{year}{first_word}"
    key = base
    suffix = 1
    while key in used:
        suffix += 1
        key = f"{base}{suffix}"
    used.add(key)
    return key


def paper_to_bibtex(paper: dict[str, Any], used: set[str]) -> str:
    key = build_bib_key(paper, used)
    title = bib_escape(str(paper.get("title", "Untitled")))
    authors = paper.get("authors", [])
    author_field = (
        " and ".join([bib_escape(str(author)) for author in authors]) or "Unknown"
    )
    year = str(paper.get("year") or "")
    venue = bib_escape(str(paper.get("venue") or ""))
    url = str(paper.get("url") or "")
    external_raw = paper.get("externalIds")
    external: dict[str, Any]
    if isinstance(external_raw, dict):
        external = external_raw
    else:
        external = {}
    arxiv_id = str(external.get("ArXiv") or "")
    doi = str(external.get("DOI") or "")

    lines: list[str]
    if arxiv_id:
        lines = [
            f"@misc{{{key},",
            f"  title = {{{title}}},",
            f"  author = {{{author_field}}},",
        ]
        if year:
            lines.append(f"  year = {{{year}}},")
        lines.extend(
            [
                f"  eprint = {{{arxiv_id}}},",
                "  archiveprefix = {arXiv},",
            ]
        )
        if url:
            lines.append(f"  url = {{{bib_escape(url)}}},")
        lines.append("}")
        return "\n".join(lines)

    entry_type = "inproceedings" if venue else "article"
    lines = [
        f"@{entry_type}{{{key},",
        f"  title = {{{title}}},",
        f"  author = {{{author_field}}},",
    ]
    if year:
        lines.append(f"  year = {{{year}}},")
    if venue:
        field = "booktitle" if entry_type == "inproceedings" else "journal"
        lines.append(f"  {field} = {{{venue}}},")
    if doi:
        lines.append(f"  doi = {{{bib_escape(doi)}}},")
    if url:
        lines.append(f"  url = {{{bib_escape(url)}}},")
    lines.append("}")
    return "\n".join(lines)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def emit_json(payload: dict[str, Any], out: str | None) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    if out:
        path = Path(out)
        ensure_parent(path)
        path.write_text(body + "\n", encoding="utf-8")
        print(f"Wrote {out}")
        return
    print(body)


def paper_identity(paper: dict[str, Any]) -> str:
    paper_id = str(paper.get("paperId") or "").strip()
    if paper_id:
        return paper_id
    title = str(paper.get("title") or "").strip().lower()
    year = str(paper.get("year") or "")
    return f"{title}|{year}"


def append_jsonl(papers: list[dict[str, Any]], out: str | None) -> None:
    if not out:
        return
    path = Path(out)
    ensure_parent(path)

    seen: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(existing, dict):
                seen.add(paper_identity(existing))

    with path.open("a", encoding="utf-8") as handle:
        count = 0
        for paper in papers:
            identity = paper_identity(paper)
            if identity in seen:
                continue
            seen.add(identity)
            handle.write(json.dumps(paper, ensure_ascii=False) + "\n")
            count += 1
    print(f"Appended {count} records to {out}")


def extract_papers(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [normalize_paper(item) for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    if isinstance(payload.get("papers"), list):
        return [
            normalize_paper(item)
            for item in payload["papers"]
            if isinstance(item, dict)
        ]

    for key in ("citations", "references"):
        values = payload.get(key)
        if isinstance(values, list):
            return [normalize_paper(item) for item in values if isinstance(item, dict)]

    if "title" in payload and "authors" in payload:
        return [normalize_paper(payload)]

    data = payload.get("data")
    if isinstance(data, list):
        papers: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("citingPaper"), dict):
                papers.append(normalize_paper(item["citingPaper"]))
                continue
            if isinstance(item.get("citedPaper"), dict):
                papers.append(normalize_paper(item["citedPaper"]))
                continue
            papers.append(normalize_paper(item))
        return papers

    return []


def command_search(args: argparse.Namespace) -> int:
    papers: list[dict[str, Any]] = []
    source = args.source
    attempted: list[str] = []
    successful: list[str] = []
    supplemented = False
    if source in {"auto", "reascholar"}:
        attempted.append("reascholar")
        try:
            papers = search_reascholar(args.query, args.limit, args.reascholar_mode)
            if papers:
                successful.append("reascholar")
        except Exception as exc:
            if source == "reascholar":
                raise RuntimeError(f"ReaScholar search failed: {exc}") from exc
            papers = []

    if not papers and source in {"auto", "semantic_scholar"}:
        attempted.append("semantic_scholar")
        payload = request_json(
            "/paper/search",
            {
                "query": args.query,
                "limit": max(1, min(args.limit, 100)),
                "year": args.year_range,
                "fieldsOfStudy": args.fields_of_study,
                "fields": SEARCH_FIELDS,
            },
        )
        papers = [normalize_paper(item) for item in payload.get("data", [])]
        for paper in papers:
            paper["source"] = "semantic_scholar"
            paper["sources"] = ["semantic_scholar"]
        if papers:
            successful.append("semantic_scholar")

    if (
        papers
        and source in {"auto", "reascholar"}
        and not args.no_s2_supplement
        and semantic_scholar_api_key()
    ):
        papers = [supplement_with_s2(paper) for paper in papers]
        supplemented = True

    primary = successful[0] if successful else ""
    result = {
        "query": args.query,
        "count": len(papers),
        "papers": papers,
        "requested_source": source,
        "attempted_sources": attempted,
        "successful_sources": successful,
        "primary_source": primary,
        "source": primary,
        "supplement_source": "semantic_scholar" if supplemented else "",
    }
    emit_json(result, args.out)
    append_jsonl(papers, args.library_out)
    return 0


def command_paper(args: argparse.Namespace) -> int:
    paper = None
    source = args.source
    attempted: list[str] = []
    successful: list[str] = []
    supplemented = False
    if source in {"auto", "reascholar"}:
        attempted.append("reascholar")
        try:
            paper = find_reascholar_paper(args.paper_id, args.reascholar_mode)
            if paper:
                successful.append("reascholar")
        except Exception as exc:
            if source == "reascholar":
                raise RuntimeError(f"ReaScholar paper lookup failed: {exc}") from exc
            paper = None

    if paper is None and source in {"auto", "semantic_scholar"}:
        attempted.append("semantic_scholar")
        paper_id = normalize_paper_id(args.paper_id)
        payload = request_json(
            f"/paper/{urllib.parse.quote(paper_id, safe='')}", {"fields": PAPER_FIELDS}
        )
        paper = normalize_paper(payload)
        paper["source"] = "semantic_scholar"
        paper["sources"] = ["semantic_scholar"]
        successful.append("semantic_scholar")

    if paper is None:
        raise RuntimeError(f"Paper not found: {args.paper_id}")

    if (
        source in {"auto", "reascholar"}
        and not args.no_s2_supplement
        and semantic_scholar_api_key()
    ):
        paper = supplement_with_s2(paper)
        supplemented = True

    primary = successful[0] if successful else ""
    result = {
        "paper": paper,
        "requested_source": source,
        "attempted_sources": attempted,
        "successful_sources": successful,
        "primary_source": primary,
        "source": primary,
        "supplement_source": "semantic_scholar" if supplemented else "",
    }
    emit_json(result, args.out)
    append_jsonl([paper], args.library_out)
    return 0


def command_edge(args: argparse.Namespace, edge: str) -> int:
    paper_id = normalize_paper_id(args.paper_id)
    payload = request_json(
        f"/paper/{urllib.parse.quote(paper_id, safe='')}/{edge}",
        {"limit": max(1, min(args.limit, 100)), "fields": EDGE_FIELDS},
    )
    papers = extract_papers(payload)
    result = {
        "paper_id": paper_id,
        "count": len(papers),
        edge: papers,
        "source": "semantic_scholar",
    }
    emit_json(result, args.out)
    append_jsonl(papers, args.library_out)
    return 0


def command_bibtex(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    papers = extract_papers(payload)
    if not papers:
        raise RuntimeError("No papers found in input JSON")

    used: set[str] = set()
    if args.append and args.out:
        output = Path(args.out)
        if output.exists():
            existing = output.read_text(encoding="utf-8")
            used.update(match.group(1).strip() for match in BIB_PATTERN.finditer(existing))
    entries = [paper_to_bibtex(paper, used) for paper in papers]
    body = "\n\n".join(entries) + "\n"

    if args.out:
        output = Path(args.out)
        ensure_parent(output)
        mode = "a" if args.append else "w"
        with output.open(mode, encoding="utf-8") as handle:
            if mode == "a" and output.exists() and output.stat().st_size > 0:
                handle.write("\n")
            handle.write(body)
        print(f"Wrote {len(entries)} BibTeX entries to {args.out}")
        return 0

    print(body)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Survey-style literature retrieval helper backed by ReaScholar first, with Semantic Scholar supplement/fallback",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_source_args(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument(
            "--source",
            choices=["auto", "reascholar", "semantic_scholar"],
            default="auto",
            help="auto uses ReaScholar first and Semantic Scholar as supplement/fallback",
        )
        cmd.add_argument(
            "--reascholar-mode",
            default="fast",
            choices=["fast", "agent", "model", "algorithm", "theorem", "code"],
            help="ReaScholar search mode; fast is the default for reliable agent calls",
        )
        cmd.add_argument("--no-s2-supplement", action="store_true")

    search = subparsers.add_parser("search", help="Search papers by query")
    add_source_args(search)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--year-range", default="")
    search.add_argument("--fields-of-study", default="")
    search.add_argument("--out", default="")
    search.add_argument("--library-out", default="")

    paper = subparsers.add_parser("paper", help="Fetch one paper by ID")
    add_source_args(paper)
    paper.add_argument("--paper-id", required=True)
    paper.add_argument("--out", default="")
    paper.add_argument("--library-out", default="")

    citations = subparsers.add_parser("citations", help="Fetch citing papers")
    citations.add_argument("--paper-id", required=True)
    citations.add_argument("--limit", type=int, default=10)
    citations.add_argument("--out", default="")
    citations.add_argument("--library-out", default="")

    references = subparsers.add_parser("references", help="Fetch referenced papers")
    references.add_argument("--paper-id", required=True)
    references.add_argument("--limit", type=int, default=10)
    references.add_argument("--out", default="")
    references.add_argument("--library-out", default="")

    bibtex = subparsers.add_parser("bibtex", help="Convert retrieval JSON to BibTeX")
    bibtex.add_argument("--input", required=True)
    bibtex.add_argument("--out", default="")
    bibtex.add_argument("--append", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "search":
            return command_search(args)
        if args.command == "paper":
            return command_paper(args)
        if args.command == "citations":
            return command_edge(args, "citations")
        if args.command == "references":
            return command_edge(args, "references")
        if args.command == "bibtex":
            return command_bibtex(args)
        parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
