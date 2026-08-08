#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_SECTION_NUM = 7
DEFAULT_SUBSECTION_LEN = 700
DEFAULT_RAG_NUM = 60
DEFAULT_OUTLINE_REFERENCE_NUM = 1500
DEFAULT_MIN_CITATIONS = 45
DEFAULT_MIN_SURVEY_WORDS = 6000
DEFAULT_MIN_SURVEY_SUBSECTIONS = 36
DEFAULT_MIN_SURVEY_LINES = 450
DEFAULT_MIN_RELATED_CITATIONS = 15
DEFAULT_MIN_RELATED_WORDS = 650
DEFAULT_MIN_RELATED_SECTIONS = 3

CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
BIB_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)
LATEX_PREAMBLE_PATTERN = re.compile(
    r"^\s*\\(?:documentclass|usepackage|begin\{document\}|end\{document\}|bibliographystyle|bibliography)\b"
)
LATEX_CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)

_DB_INSTANCE: Any = None


def _query_tokens(text: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "for",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in stopwords
    }


class ExternalPaperDatabase:
    """Small retrieval adapter over survey/library artifacts."""

    def __init__(self, papers: list[dict[str, Any]]):
        self._papers: dict[str, dict[str, Any]] = {}
        self._ordered_ids: list[str] = []
        for index, raw in enumerate(papers):
            paper = normalize_external_paper(raw)
            paper_id = str(
                paper.get("id")
                or paper.get("paperId")
                or paper.get("paper_key")
                or f"external-{index}"
            )
            paper["id"] = paper_id
            paper.setdefault("abs", paper.get("abstract", ""))
            if paper_id in self._papers:
                continue
            self._papers[paper_id] = paper
            self._ordered_ids.append(paper_id)

    def _score(self, query: str, paper: dict[str, Any]) -> float:
        tokens = _query_tokens(query)
        if not tokens:
            return 0.0
        title = paper_title(paper)
        topics = paper.get("topics", [])
        topic_text = " ".join(topics) if isinstance(topics, list) else str(topics)
        haystack = " ".join(
            [
                title,
                title,
                title,
                str(paper.get("abs") or paper.get("abstract") or ""),
                topic_text,
                str(paper.get("strengths") or ""),
                str(paper.get("summary_markdown") or ""),
            ]
        ).lower()
        score = sum(1.0 for token in tokens if token in haystack)
        if query.lower() in haystack:
            score += 5.0
        citation_count = paper.get("citationCount") or paper.get("citation_count") or 0
        try:
            score += min(float(citation_count), 1000.0) / 10000.0
        except (TypeError, ValueError):
            pass
        return score

    def get_ids_from_query(
        self,
        query: str,
        num: int = 10,
        shuffle: bool = False,
    ) -> list[str]:
        ranked = sorted(
            self._ordered_ids,
            key=lambda paper_id: self._score(query, self._papers[paper_id]),
            reverse=True,
        )
        if not ranked:
            return []
        scored = [
            paper_id
            for paper_id in ranked
            if self._score(query, self._papers[paper_id]) > 0
        ]
        selected = scored or ranked
        if shuffle and len(selected) > 1:
            pivot = abs(hash(query)) % len(selected)
            selected = selected[pivot:] + selected[:pivot]
        return selected[:num]

    def get_paper_info_from_ids(self, paper_ids: list[str]) -> list[dict[str, Any]]:
        return [
            self._papers[paper_id]
            for paper_id in paper_ids
            if paper_id in self._papers
        ]

    def get_titles_from_citations(self, citations: list[str]) -> list[str]:
        title_to_id = {
            _normalize_title_for_match(paper_title(paper)): paper_id
            for paper_id, paper in self._papers.items()
        }
        resolved: list[str] = []
        for citation in citations:
            normalized = _normalize_title_for_match(citation)
            if normalized in title_to_id:
                resolved.append(title_to_id[normalized])
                continue
            matches = self.get_ids_from_query(citation, num=1, shuffle=False)
            resolved.append(matches[0] if matches else "")
        return resolved

    def format_papers_text(self, papers: list[dict], include_analysis: bool = True) -> str:
        return _format_papers_text_fallback(papers)


def load_prompt_templates():
    return _load_vendored_prompts()


_VENDORED_PROMPTS: Any = None


def _load_vendored_prompts():
    global _VENDORED_PROMPTS
    if _VENDORED_PROMPTS is not None:
        return _VENDORED_PROMPTS
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "reasflow_prompts_vendored", here / "prompts_vendored.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load vendored prompt templates")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _VENDORED_PROMPTS = module
    return module


def fill_prompt(template: str, paras: dict[str, str]) -> str:
    prompt = template
    for k, v in paras.items():
        prompt = prompt.replace(f"[{k}]", v)
    return prompt


def get_database(args: argparse.Namespace):
    global _DB_INSTANCE
    if _DB_INSTANCE is not None:
        return _DB_INSTANCE

    library_dir = getattr(args, "library_dir", "")
    if library_dir:
        workspace_root = resolve_workspace(getattr(args, "workspace", "."))
        external_papers = load_external_library_papers(workspace_root, library_dir)
        if external_papers:
            _DB_INSTANCE = ExternalPaperDatabase(external_papers)
            print(
                f"Using external survey library database: {library_dir} "
                f"({len(external_papers)} papers)",
                file=sys.stderr,
            )
            return _DB_INSTANCE

    raise RuntimeError(
        f"Survey paper library is empty at {library_dir or 'survey/library'}. "
        "Run the autosurvey-paper-retrieval skill first to populate the library, "
        "or pass --library-dir pointing at a directory with paper JSON files."
    )


def resolve_workspace(workspace: str) -> Path:
    return Path(workspace or ".").expanduser().resolve()


def resolve_path(workspace_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    resolved = (
        path.resolve() if path.is_absolute() else (workspace_root / path).resolve()
    )
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {raw_path}") from exc
    return resolved


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_cite_keys(tex_path: Path) -> set[str]:
    content = tex_path.read_text(encoding="utf-8")
    keys: set[str] = set()
    for match in CITE_PATTERN.finditer(content):
        for key in match.group(1).split(","):
            cleaned = key.strip()
            if cleaned:
                keys.add(cleaned)
    return keys


def parse_bib_keys(bib_path: Path) -> tuple[set[str], list[str]]:
    content = bib_path.read_text(encoding="utf-8")
    keys: set[str] = set()
    duplicates: list[str] = []
    for match in BIB_PATTERN.finditer(content):
        key = match.group(1).strip()
        if not key:
            continue
        if key in keys:
            duplicates.append(key)
            continue
        keys.add(key)
    return keys, duplicates


def parse_bib_entries(bib_path: Path) -> dict[str, dict[str, str]]:
    if not bib_path.exists():
        return {}
    content = bib_path.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", content, re.IGNORECASE):
        entry_start = match.start()
        next_match = re.search(r"\n\s*@", content[match.end() :])
        entry_end = (
            match.end() + next_match.start()
            if next_match
            else len(content)
        )
        raw_entry = content[entry_start:entry_end].strip()
        key = match.group(2).strip()
        fields: dict[str, str] = {
            "id": key,
            "bib_key": key,
            "entry_type": match.group(1).lower(),
            "raw_bibtex": raw_entry,
        }
        for field_match in re.finditer(
            r"\b([A-Za-z][A-Za-z0-9_-]*)\s*=\s*[\{\"]([^}\"]*)[\}\"]",
            raw_entry,
            re.DOTALL,
        ):
            field = field_match.group(1).lower()
            value = re.sub(r"\s+", " ", field_match.group(2)).strip()
            fields[field] = value
        if "authors" not in fields and "author" in fields:
            fields["authors"] = fields["author"]
        entries[key] = fields
    return entries


def merge_existing_cited_bib_entries(
    generated_bib: str,
    existing_bib_path: Path,
    cited_keys: set[str],
) -> str:
    if not existing_bib_path.exists() or not cited_keys:
        return generated_bib
    existing_entries = parse_bib_entries(existing_bib_path)
    generated_keys, _ = parse_bib_keys_from_content(generated_bib)
    extras: list[str] = []
    for key in sorted(cited_keys):
        if key in generated_keys:
            continue
        raw_entry = existing_entries.get(key, {}).get("raw_bibtex", "").strip()
        if raw_entry:
            extras.append(raw_entry)
    if not extras:
        return generated_bib
    merged = generated_bib.rstrip()
    if merged:
        merged += "\n\n"
    merged += "\n\n".join(extras)
    if not merged.endswith("\n"):
        merged += "\n"
    return merged


def parse_bib_keys_from_content(content: str) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    duplicates: list[str] = []
    for match in BIB_PATTERN.finditer(content):
        key = match.group(1).strip()
        if not key:
            continue
        if key in keys:
            duplicates.append(key)
            continue
        keys.add(key)
    return keys, duplicates


def sanitize_related_works(tex_content: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    kept_lines: list[str] = []

    for line in tex_content.splitlines():
        if LATEX_PREAMBLE_PATTERN.match(line):
            notes.append(f"removed preamble line: {line.strip()}")
            continue
        kept_lines.append(line)

    sanitized = "\n".join(kept_lines).strip()
    if not sanitized.endswith("\n"):
        sanitized += "\n"
    return sanitized, notes


def validate_tex_bib(tex_paths: list[Path], bib_path: Path) -> dict[str, Any]:
    cited_keys: set[str] = set()
    citations_by_file: dict[str, list[str]] = {}

    for tex_path in tex_paths:
        keys = sorted(parse_cite_keys(tex_path))
        cited_keys.update(keys)
        citations_by_file[str(tex_path)] = keys

    bib_keys, duplicate_keys = parse_bib_keys(bib_path)
    missing_keys = sorted(cited_keys - bib_keys)
    unused_keys = sorted(bib_keys - cited_keys)

    return {
        "tex_files": [str(path) for path in tex_paths],
        "bib_file": str(bib_path),
        "citations_by_file": citations_by_file,
        "cited_key_count": len(cited_keys),
        "bib_key_count": len(bib_keys),
        "missing_keys": missing_keys,
        "unused_keys": unused_keys,
        "duplicate_bib_keys": duplicate_keys,
        "ok": not missing_keys and not duplicate_keys,
    }


def validate_required_files(paths: list[Path]) -> dict[str, Any]:
    required_files = [str(path) for path in paths]
    missing_files = [str(path) for path in paths if not path.exists()]
    return {
        "required_files": required_files,
        "missing_files": missing_files,
        "ok": not missing_files,
    }


def extract_title_sections_descriptions(outline: str):
    title = ""
    sections: list[str] = []
    descriptions: list[str] = []
    lines = outline.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.lower().startswith("title:"):
            title = line[len("title:") :].strip()
        elif line.lower().startswith("section") and ":" in line:
            parts = line.split(":", 1)
            sections.append(parts[1].strip())
        elif line.lower().startswith("description") and ":" in line:
            parts = line.split(":", 1)
            descriptions.append(parts[1].strip())
    return title, sections, descriptions


def extract_subsections_subdescriptions(outline: str):
    subsections: list[str] = []
    sub_descriptions: list[str] = []
    lines = outline.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.lower().startswith("subsection") and ":" in line:
            parts = line.split(":", 1)
            subsections.append(parts[1].strip())
        elif line.lower().startswith("description") and ":" in line:
            parts = line.split(":", 1)
            sub_descriptions.append(parts[1].strip())
    return subsections, sub_descriptions


def chunk_papers(abstracts: list[str], titles: list[str], chunk_size: int = 30000):
    abs_chunks: list[list[str]] = []
    titles_chunks: list[list[str]] = []
    current_abs: list[str] = []
    current_titles: list[str] = []
    current_len = 0
    for title, abstract in zip(titles, abstracts):
        text = f"---\npaper_title: {title}\n\npaper_content:\n\n{abstract}\n"
        if current_len + len(text) > chunk_size and current_abs:
            abs_chunks.append(current_abs)
            titles_chunks.append(current_titles)
            current_abs = []
            current_titles = []
            current_len = 0
        current_abs.append(abstract)
        current_titles.append(title)
        current_len += len(text)
    if current_abs:
        abs_chunks.append(current_abs)
        titles_chunks.append(current_titles)
    return abs_chunks, titles_chunks


def parse_outline(outline_content: str) -> dict:
    lines = outline_content.strip().split("\n")
    sections: list[str] = []
    section_descriptions: list[str] = []
    subsections: list[list[str]] = []
    subsection_descriptions: list[list[str]] = []
    current_section_idx = -1
    current_subs: list[str] = []
    current_sub_descs: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or (
            stripped.startswith("#") and not stripped.startswith("### ")
        ):
            if current_section_idx >= 0:
                subsections.append(current_subs)
                subsection_descriptions.append(current_sub_descs)
            section_match = re.match(r"^#+\s+\d*\s*(.+)$", stripped)
            if section_match:
                if ":" in stripped:
                    parts = stripped.split(":", 1)
                    sections.append(
                        parts[0]
                        .rstrip()
                        .rstrip("#")
                        .rstrip()
                        .rstrip("0123456789.")
                        .strip()
                    )
                    section_descriptions.append(parts[1].strip())
                else:
                    sections.append(section_match.group(1).strip())
                    section_descriptions.append("")
                current_section_idx += 1
                current_subs = []
                current_sub_descs = []
        elif stripped.startswith("### "):
            if ":" in stripped:
                parts = stripped.split(":", 1)
                current_subs.append(
                    parts[0].replace("###", "").strip().lstrip("0123456789.").strip()
                )
                current_sub_descs.append(parts[1].strip())
            else:
                current_subs.append(
                    stripped.replace("###", "").strip().lstrip("0123456789.").strip()
                )
                current_sub_descs.append("")
        elif stripped.lower().startswith("description:") and current_section_idx >= 0:
            if current_subs:
                current_sub_descs[-1] = stripped[len("description:") :].strip()
            elif not section_descriptions[current_section_idx]:
                section_descriptions[current_section_idx] = stripped[
                    len("description:") :
                ].strip()

    if current_section_idx >= 0:
        subsections.append(current_subs)
        subsection_descriptions.append(current_sub_descs)

    return {
        "sections": sections,
        "section_descriptions": section_descriptions,
        "subsections": subsections,
        "subsection_descriptions": subsection_descriptions,
    }


def extract_citations(text: str) -> list[str]:
    pattern = re.compile(r"\[([^\]]+)\]")
    citations: list[str] = []
    seen = set()
    for match in pattern.finditer(text):
        for cite in match.group(1).split(";"):
            cite = cite.strip()
            if cite and cite not in seen:
                citations.append(cite)
                seen.add(cite)
    return citations


def replace_title_citations_with_numbers(
    text: str,
    citation_to_ref_num: dict[str, str],
) -> str:
    def replace_match(match: re.Match[str]) -> str:
        raw_group = match.group(1)
        parts = [part.strip() for part in raw_group.split(";") if part.strip()]
        if not parts:
            return match.group(0)
        ref_nums: list[str] = []
        for part in parts:
            ref_num = citation_to_ref_num.get(part)
            if not ref_num:
                return match.group(0)
            ref_nums.append(ref_num)
        return "[" + "; ".join(ref_nums) + "]"

    return re.sub(r"\[([^\]]+)\]", replace_match, text)


def generate_bibtex_key(paper: dict) -> str:
    authors = paper.get("authors", [])
    first_author = ""
    if authors:
        if isinstance(authors, list):
            first_author = authors[0] if authors else ""
        else:
            first_author = str(authors).split(",")[0].strip()
    first_author = re.sub(r"[^a-zA-Z]", "", first_author).lower()[:10]
    year = str(paper.get("year", "2024"))
    title_words = re.findall(r"[a-zA-Z]+", paper.get("title", ""))
    title_key = "".join(w.lower() for w in title_words[:3])
    return f"{first_author}{year}{title_key}"


def extract_bibtex_key(bibtex: str) -> str:
    if not bibtex or not isinstance(bibtex, str):
        return ""
    match = BIB_PATTERN.search(bibtex.strip())
    return match.group(1).strip() if match else ""


def _clean_arxiv_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id or "")


def _bibtex_field(bibtex: str, field: str) -> str:
    match = re.search(
        rf"\b{re.escape(field)}\s*=\s*[\{{\"]([^}}\"]+)[\}}\"]",
        bibtex or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _paper_arxiv_id(paper: dict) -> str:
    external_ids = paper.get("externalIds") or paper.get("external_ids") or {}
    if isinstance(external_ids, dict):
        arxiv_id = external_ids.get("ArXiv") or external_ids.get("arxiv") or ""
        if arxiv_id:
            return str(arxiv_id)
    return str(paper.get("id") or paper.get("arxiv_id") or "")


def _paper_year(paper: dict) -> str:
    for field in ("year", "date", "published", "publicationDate"):
        value = paper.get(field)
        if value:
            match = re.search(r"\d{4}", str(value))
            if match:
                return match.group(0)
    return "2024"


def _bibtex_describes_arxiv(bibtex: str, arxiv_id: str = "") -> bool:
    lower_bib = (bibtex or "").lower()
    journal = _bibtex_field(bibtex, "journal").lower()
    clean_id = _clean_arxiv_id(arxiv_id)
    return (
        "arxiv preprint" in lower_bib
        or journal in {"arxiv", "arxiv.org"}
        or journal.startswith("arxiv")
        or (clean_id and clean_id.lower() in lower_bib and "arxiv" in lower_bib)
    )


def _bibtex_has_published_venue(bibtex: str) -> bool:
    journal = _bibtex_field(bibtex, "journal").lower()
    booktitle = _bibtex_field(bibtex, "booktitle").lower()
    if booktitle:
        return True
    return bool(journal and "arxiv" not in journal)


def _remove_bibtex_fields(bibtex: str, fields: set[str]) -> str:
    cleaned = bibtex
    for field in fields:
        cleaned = re.sub(
            rf"\n\s*{re.escape(field)}\s*=\s*[\{{\"](?:[^}}\"]*)[\}}\"]\s*,?",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return cleaned


def _normalize_arxiv_preprint_bibtex(bibtex: str) -> str:
    journal = _bibtex_field(bibtex, "journal").lower()
    if journal.startswith("arxiv") or "arxiv preprint" in journal:
        cleaned = _remove_bibtex_fields(bibtex, {"journal"})
        return re.sub(r"^@\s*article", "@misc", cleaned, count=1, flags=re.IGNORECASE)
    return bibtex


def _repair_bibtex_mojibake(bibtex: str) -> str:
    value = str(bibtex or "")
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


def _is_arxiv_url(url: str) -> bool:
    return "arxiv.org" in (url or "").lower()


def _is_internal_reascholar_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "scholar.reaslab.io/api/papers/" in lowered


def _canonical_bib_url(paper: dict) -> str:
    doi = str(paper.get("doi") or (paper.get("externalIds") or {}).get("DOI") or "").strip()
    if doi.startswith("10."):
        return f"https://doi.org/{doi}"

    arxiv_id = _paper_arxiv_id(paper)
    if arxiv_id and re.search(r"\d{4}\.\d{4,5}", arxiv_id):
        return f"https://arxiv.org/abs/{_clean_arxiv_id(arxiv_id)}"

    url = str(paper.get("url") or "").strip()
    if not url or _is_internal_reascholar_url(url):
        return ""
    return url


def _bibtex_source_is_consistent(paper: dict, bibtex: str) -> bool:
    source = str(paper.get("best_citation_source") or "").lower()
    venue = str(paper.get("best_citation_venue") or "").lower()
    clean_id = _clean_arxiv_id(_paper_arxiv_id(paper)).lower()
    if clean_id and clean_id in (bibtex or "").lower():
        return True
    if _bibtex_describes_arxiv(bibtex, _paper_arxiv_id(paper)):
        return source in {"", "arxiv"} and ("arxiv" in venue or not venue)
    return True


def replace_bibtex_key(bibtex: str, new_key: str) -> str:
    return re.sub(
        r"(@\w+\s*\{\s*)([^,\s]+)",
        rf"\g<1>{new_key}",
        bibtex,
        count=1,
        flags=re.IGNORECASE,
    )


def _insert_bibtex_field(bibtex: str, field: str, value: str) -> str:
    if not value or _bibtex_field(bibtex, field):
        return bibtex
    insertion = f"  {field} = {{{value}}},\n"
    index = bibtex.rfind("}")
    if index == -1:
        return bibtex.rstrip() + "\n" + insertion
    prefix = bibtex[:index].rstrip()
    if prefix and not prefix.endswith(","):
        prefix += ","
    return prefix + "\n" + insertion + bibtex[index:]


def enrich_bibtex_entry(paper: dict, bibtex: str) -> str:
    enriched = _repair_bibtex_mojibake(bibtex.strip())
    enriched = _normalize_arxiv_preprint_bibtex(enriched)
    enriched = _insert_bibtex_field(enriched, "year", _paper_year(paper))
    has_published_venue = _bibtex_has_published_venue(enriched)
    canonical_url = _canonical_bib_url(paper)

    arxiv_id = _paper_arxiv_id(paper)
    if (
        arxiv_id
        and re.search(r"\d{4}\.\d{4,5}", arxiv_id)
        and not has_published_venue
    ):
        enriched = _insert_bibtex_field(enriched, "eprint", arxiv_id)
        enriched = _insert_bibtex_field(enriched, "archiveprefix", "arXiv")
        enriched = _insert_bibtex_field(enriched, "url", canonical_url)
    elif canonical_url and not (has_published_venue and _is_arxiv_url(canonical_url)):
        enriched = _insert_bibtex_field(enriched, "url", canonical_url)

    doi = paper.get("doi") or (paper.get("externalIds") or {}).get("DOI")
    if doi:
        enriched = _insert_bibtex_field(enriched, "doi", str(doi))
    return enriched


def is_weak_bibtex_key(key: str) -> bool:
    cleaned = (key or "").strip()
    return not cleaned or bool(re.fullmatch(r"\d+[a-z]?", cleaned))


def arxiv_id_to_bibtex(paper: dict, key: str) -> str:
    title = paper.get("title", "Untitled")
    authors = paper.get("authors", ["Unknown"])
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(",")]
    year = _paper_year(paper)
    author_str = " and ".join(authors)

    arxiv_id = _paper_arxiv_id(paper)
    url = _canonical_bib_url(paper)

    bib = f"@article{{{key},\n"
    bib += f"  title = {{{title}}},\n"
    bib += f"  author = {{{author_str}}},\n"
    bib += f"  year = {{{year}}},\n"
    if arxiv_id:
        bib += f"  eprint = {{{arxiv_id}}},\n"
        bib += f"  archiveprefix = {{arXiv}},\n"
    if url:
        bib += f"  url = {{{url}}},\n"
    bib += "}\n"
    return bib


def normalize_external_paper(raw: dict[str, Any]) -> dict[str, Any]:
    external_ids = raw.get("externalIds") or raw.get("external_ids") or {}
    if not isinstance(external_ids, dict):
        external_ids = {}
    authors = raw.get("authors") or []
    if isinstance(authors, list):
        author_names = [
            str(author.get("name") if isinstance(author, dict) else author).strip()
            for author in authors
        ]
        authors = [name for name in author_names if name]
    elif isinstance(authors, str):
        authors = [name.strip() for name in authors.split(",") if name.strip()]
    else:
        authors = []

    title = str(raw.get("title") or "").strip()
    paper_id = str(
        raw.get("id")
        or external_ids.get("ArXiv")
        or raw.get("paperId")
        or raw.get("paper_id")
        or title.lower()
    ).strip()
    abstract = str(raw.get("abs") or raw.get("abstract") or "").strip()
    return {
        "id": paper_id,
        "paperId": raw.get("paperId") or paper_id,
        "paper_key": raw.get("paper_key") or "",
        "title": title,
        "authors": authors,
        "year": raw.get("year") or raw.get("publicationDate") or raw.get("date") or "",
        "abs": abstract,
        "abstract": abstract,
        "s2_abstract": raw.get("s2_abstract") or "",
        "url": raw.get("url") or "",
        "externalIds": external_ids,
        "venue": raw.get("venue") or "",
        "citationCount": raw.get("citationCount") or raw.get("citation_count") or 0,
        "referenceCount": raw.get("referenceCount") or raw.get("reference_count") or 0,
        "publicationDate": raw.get("publicationDate") or "",
        "raw_bibtex": raw.get("raw_bibtex") or raw.get("bibtex") or "",
        "best_citation_bibtex": raw.get("best_citation_bibtex") or "",
        "best_citation_source": raw.get("best_citation_source") or "",
        "best_citation_venue": raw.get("best_citation_venue") or "",
        "source": raw.get("source") or "",
        "sources": raw.get("sources") or [],
        "topics": raw.get("topics") or [],
        "strengths": raw.get("strengths") or raw.get("summary_markdown") or "",
        "weaknesses": raw.get("weaknesses") or "",
        "summary_markdown": raw.get("summary_markdown") or "",
    }


def extract_external_papers(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [normalize_external_paper(item) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("paper"), dict):
        return [normalize_external_paper(payload["paper"])]
    if isinstance(payload.get("papers"), list):
        return [
            normalize_external_paper(item)
            for item in payload["papers"]
            if isinstance(item, dict)
        ]
    papers: list[dict[str, Any]] = []
    for key in ("citations", "references", "data"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("citingPaper"), dict):
                papers.append(normalize_external_paper(item["citingPaper"]))
            elif isinstance(item.get("citedPaper"), dict):
                papers.append(normalize_external_paper(item["citedPaper"]))
            else:
                papers.append(normalize_external_paper(item))
    if "title" in payload:
        papers.append(normalize_external_paper(payload))
    return papers


def load_external_library_papers(workspace_root: Path, library_dir_raw: str) -> list[dict[str, Any]]:
    library_dir = resolve_path(workspace_root, library_dir_raw)
    if not library_dir.exists():
        return []
    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(library_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for paper in extract_external_papers(payload):
            title = str(paper.get("title") or "").strip()
            if not title:
                continue
            identity = str(paper.get("id") or title.lower()).lower()
            if identity in seen:
                continue
            seen.add(identity)
            papers.append(paper)
    jsonl_path = library_dir / "paper_pool.jsonl"
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                paper = normalize_external_paper(json.loads(line))
            except json.JSONDecodeError:
                continue
            title = str(paper.get("title") or "").strip()
            if not title:
                continue
            identity = str(paper.get("id") or title.lower()).lower()
            if identity in seen:
                continue
            seen.add(identity)
            papers.append(paper)
    return papers


def select_bibtex_entry(paper: dict, fallback_key: str | None = None) -> tuple[str, str]:
    for field in ("raw_bibtex", "best_citation_bibtex"):
        bibtex = paper.get(field)
        if not bibtex or not isinstance(bibtex, str):
            continue
        if field == "best_citation_bibtex" and not _bibtex_source_is_consistent(
            paper, bibtex
        ):
            continue
        key = extract_bibtex_key(bibtex)
        if key and not is_weak_bibtex_key(key):
            return key, enrich_bibtex_entry(paper, bibtex)

    key = fallback_key or paper.get("bib_key") or generate_bibtex_key(paper)
    return str(key), enrich_bibtex_entry(paper, arxiv_id_to_bibtex(paper, str(key)))


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def count_related_sections(text: str) -> int:
    return len(
        re.findall(
            r"^\s*\\(?:section|subsection|paragraph)\s*\{",
            text,
            flags=re.MULTILINE,
        )
    )


def count_survey_subsections(text: str) -> int:
    return len(
        re.findall(
            r"^\s*###\s+",
            text,
            flags=re.MULTILINE,
        )
    )


def count_lines(text: str) -> int:
    return len(text.splitlines())


def normalize_reference_key_map(
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    key_map: dict[str, str] | None = None,
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    used: set[str] = set()
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num, {})
        selected_key, _ = select_bibtex_entry(paper)
        existing_key = (key_map or {}).get(ref_num)
        key = (
            existing_key
            if existing_key and not is_weak_bibtex_key(existing_key)
            else selected_key or paper.get("bib_key") or generate_bibtex_key(paper)
        )
        base_key = key
        counter = 1
        while key in used:
            counter += 1
            key = f"{base_key}{counter}"
        used.add(key)
        normalized[ref_num] = key
    return normalized


def _normalize_title_for_match(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def infer_key_map_from_existing_bib(
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    bib_path: Path,
) -> dict[str, str]:
    if not bib_path.exists():
        return {}
    bib_entries = parse_bib_entries(bib_path)
    entries_by_title = {
        _normalize_title_for_match(entry.get("title", "")): key
        for key, entry in bib_entries.items()
        if entry.get("title")
    }
    inferred: dict[str, str] = {}
    used: set[str] = set()
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num, {})
        title_key = _normalize_title_for_match(paper.get("title", ""))
        bib_key = entries_by_title.get(title_key)
        if not bib_key or bib_key in used:
            continue
        inferred[ref_num] = bib_key
        used.add(bib_key)
    return inferred


def render_bibtex(
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    key_map: dict[str, str],
) -> str:
    entries = []
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num, {})
        selected_key, bibtex = select_bibtex_entry(paper, key_map[ref_num])
        if selected_key != key_map[ref_num]:
            bibtex = replace_bibtex_key(bibtex, key_map[ref_num])
        entries.append(bibtex)
    bib_content = "\n".join(entries)
    if bib_content and not bib_content.endswith("\n"):
        bib_content += "\n"
    return bib_content


SURVEY_REFERENCES_HEADING_PATTERN = re.compile(
    r"\n{0,2}##\s+References\s*\n.*\Z",
    re.IGNORECASE | re.DOTALL,
)


def append_survey_references_section(
    survey_text: str,
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
) -> str:
    body = SURVEY_REFERENCES_HEADING_PATTERN.sub("", survey_text).rstrip()
    reference_lines: list[str] = []
    for ref_num, paper_id in sorted(
        reference_ids.items(),
        key=lambda item: int(item[0]) if str(item[0]).isdigit() else str(item[0]),
    ):
        paper = references_full.get(paper_id) or references_full.get(ref_num) or {}
        title = paper_title(paper)
        reference_lines.append(f"[{ref_num}] {title}")

    if not reference_lines:
        return body + ("\n" if body else "")
    return body + "\n\n## References\n\n" + "\n\n".join(reference_lines) + "\n"


def rewrite_latex_cite_keys(tex_content: str, key_replacements: dict[str, str]) -> str:
    if not key_replacements:
        return tex_content

    def replace_match(match: re.Match[str]) -> str:
        keys = [
            key_replacements.get(key.strip(), key.strip())
            for key in match.group(1).split(",")
            if key.strip()
        ]
        return match.group(0).replace(match.group(1), ",".join(keys), 1)

    return LATEX_CITE_PATTERN.sub(replace_match, tex_content)


def paper_title(paper: dict) -> str:
    return str(paper.get("title", "Untitled")).strip() or "Untitled"


def ordered_latex_cite_keys(text: str) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for match in LATEX_CITE_PATTERN.finditer(text):
        for key in match.group(1).split(","):
            cleaned = key.strip()
            if cleaned and cleaned not in seen:
                keys.append(cleaned)
                seen.add(cleaned)
    return keys


def migrate_opencode_citations_to_autosurvey_style(
    survey_text: str,
    survey_data: dict[str, Any],
    bib_path: Path,
) -> tuple[str, dict[str, str], dict[str, dict]]:
    bib_entries = parse_bib_entries(bib_path)
    cite_keys = ordered_latex_cite_keys(survey_text)
    if not cite_keys:
        cite_keys = [
            key
            for key in survey_data.get("citation_keys_used", [])
            if isinstance(key, str)
        ]
    if not cite_keys:
        cite_keys = [
            key for key in survey_data.get("bibliography_keys", []) if isinstance(key, str)
        ]

    reference_ids: dict[str, str] = {}
    references_full: dict[str, dict] = {}
    for key in cite_keys:
        if key not in bib_entries:
            continue
        ref_num = str(len(reference_ids) + 1)
        reference_ids[ref_num] = key
        references_full[key] = bib_entries[key]
    return survey_text, reference_ids, references_full


def render_fallback_related_works(
    topic: str,
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    key_map: dict[str, str],
    min_citations: int,
) -> str:
    items = [
        (ref_num, references_full.get(paper_id, {}), key_map[ref_num])
        for ref_num, paper_id in reference_ids.items()
        if paper_id in references_full and ref_num in key_map
    ]
    selected = items[: max(min_citations, min(len(items), DEFAULT_MIN_RELATED_CITATIONS))]
    if not selected:
        return "\\subsection{Related Work}\nNo resolved references were available.\n"

    def cite_block(slice_items: list[tuple[str, dict, str]]) -> str:
        return "\\citep{" + ",".join(key for _, _, key in slice_items) + "}"

    first = selected[: max(1, len(selected) // 3)]
    second = selected[max(1, len(selected) // 3) : max(2, 2 * len(selected) // 3)]
    third = selected[max(2, 2 * len(selected) // 3) :]
    if not second:
        second = first
    if not third:
        third = second

    return f"""\\subsection{{Foundational Methods and Problem Setting}}
Research on {topic} is anchored by methods that define the optimization setting, the communication model, and the sources of statistical or systems heterogeneity {cite_block(first)}. These papers provide the baseline vocabulary for comparing local update rules, server aggregation, drift control, and convergence assumptions.

\\subsection{{Efficiency, Robustness, and Theoretical Trade-offs}}
Subsequent work studies how to improve efficiency without weakening optimization guarantees {cite_block(second)}. The main synthesis issue is that communication reduction, memory reduction, personalization, and robustness often improve one resource axis while introducing new assumptions or bias terms.

\\subsection{{Open Gaps}}
The remaining gap is a unified account of how these mechanisms interact under realistic deployment constraints {cite_block(third)}. Existing results cover important pieces of the design space, but a complete related-work narrative should distinguish which papers address heterogeneity, which address resource limits, and which provide convergence guarantees under combined constraints.
"""


def ensure_final_survey_package(
    workspace_root: Path,
    survey_root_raw: str,
    related_root_raw: str,
    topic: str,
    min_survey_words: int = DEFAULT_MIN_SURVEY_WORDS,
    min_survey_subsections: int = DEFAULT_MIN_SURVEY_SUBSECTIONS,
    min_survey_lines: int = DEFAULT_MIN_SURVEY_LINES,
    min_related_citations: int = DEFAULT_MIN_RELATED_CITATIONS,
    min_related_words: int = DEFAULT_MIN_RELATED_WORDS,
    min_related_sections: int = DEFAULT_MIN_RELATED_SECTIONS,
    keep_intermediates: bool = False,
) -> dict[str, Any]:
    survey_root = resolve_path(workspace_root, survey_root_raw)
    related_root = resolve_path(workspace_root, related_root_raw)
    survey_root.mkdir(parents=True, exist_ok=True)
    related_root.mkdir(parents=True, exist_ok=True)

    survey_json_path = survey_root / "survey.json"
    survey_md_path = survey_root / "survey.md"
    survey_bib_path = survey_root / "references.bib"
    related_path = related_root / "related_works.tex"
    bib_path = related_root / "references.bib"
    key_map_path = related_root / "citation_key_map.json"

    if survey_json_path.exists():
        survey_data = json.loads(survey_json_path.read_text(encoding="utf-8"))
        survey_text = survey_data.get("survey", "")
        reference_ids = survey_data.get("reference") or {}
        references_full = survey_data.get("reference_full") or {}
    else:
        survey_text = survey_md_path.read_text(encoding="utf-8") if survey_md_path.exists() else ""
        reference_ids = {}
        references_full = {}
        survey_data = {
            "survey": survey_text,
            "reference": reference_ids,
            "reference_full": references_full,
        }

    if not reference_ids and bib_path.exists():
        survey_text, reference_ids, references_full = (
            migrate_opencode_citations_to_autosurvey_style(
                survey_text=survey_text,
                survey_data=survey_data,
                bib_path=bib_path,
            )
        )

    existing_key_map = (
        json.loads(key_map_path.read_text(encoding="utf-8"))
        if key_map_path.exists()
        else infer_key_map_from_existing_bib(reference_ids, references_full, bib_path)
    )
    key_map = normalize_reference_key_map(reference_ids, references_full, existing_key_map)
    key_replacements = {
        old_key: key_map[ref_num]
        for ref_num, old_key in existing_key_map.items()
        if ref_num in key_map and old_key != key_map[ref_num]
    }

    if not survey_text.strip():
        survey_text = f"# Survey on {topic}\n\nNo survey draft was generated.\n"

    survey_text = append_survey_references_section(
        survey_text,
        reference_ids,
        references_full,
    )
    survey_md_path.write_text(survey_text, encoding="utf-8")
    survey_data["survey"] = survey_text
    survey_data["reference"] = reference_ids
    survey_data["reference_full"] = references_full
    write_json(survey_json_path, survey_data)
    write_json(key_map_path, key_map)

    if reference_ids and references_full:
        rendered_bib = render_bibtex(reference_ids, references_full, key_map)
        cited_keys = parse_cite_keys(related_path) if related_path.exists() else set()
        bib_path.write_text(
            merge_existing_cited_bib_entries(rendered_bib, bib_path, cited_keys),
            encoding="utf-8",
        )
    elif not bib_path.exists():
        bib_path.write_text("", encoding="utf-8")
    survey_bib_path.write_text(bib_path.read_text(encoding="utf-8"), encoding="utf-8")

    if related_path.exists():
        sanitized, _ = sanitize_related_works(related_path.read_text(encoding="utf-8"))
        sanitized = rewrite_latex_cite_keys(sanitized, key_replacements)
        related_path.write_text(sanitized, encoding="utf-8")

    related_needs_fallback = not related_path.exists()
    if related_path.exists():
        existing_related = related_path.read_text(encoding="utf-8")
        related_needs_fallback = len(parse_cite_keys(related_path)) < min_related_citations
        if not existing_related.strip():
            related_needs_fallback = True

    if related_needs_fallback:
        related_path.write_text(
            render_fallback_related_works(
                topic, reference_ids, references_full, key_map, min_related_citations
            ),
            encoding="utf-8",
        )

    removed_intermediates: list[str] = []
    if not keep_intermediates:
        cleanup_targets = [
            *survey_root.glob("stage*.json"),
            *survey_root.glob("native_survey_prompt*.json"),
            *survey_root.glob("drafts*.json"),
            *survey_root.glob("sections*.json"),
            survey_root / "library",
            related_root / "rw_prompt.json",
            related_root / "citation_key_map.json",
            workspace_root / "pipeline_log.jsonl",
            related_root / "rw.tex",
            related_root / "ref.bib",
        ]
        for target in cleanup_targets:
            if not target.exists():
                continue
            if target.is_dir():
                for child in sorted(target.rglob("*"), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                target.rmdir()
            else:
                target.unlink()
            removed_intermediates.append(str(target))

    validation = validate_tex_bib([related_path], bib_path)
    required_report = validate_required_files(
        [
            survey_root / "survey.md",
            survey_root / "survey.json",
            survey_root / "references.bib",
            related_root / "related_works.tex",
            related_root / "references.bib",
        ]
    )
    final_survey_text = survey_md_path.read_text(encoding="utf-8")
    survey_words = count_words(final_survey_text)
    survey_subsections = count_survey_subsections(final_survey_text)
    survey_lines = count_lines(final_survey_text)
    related_text = related_path.read_text(encoding="utf-8") if related_path.exists() else ""
    related_words = count_words(related_text)
    related_sections = count_related_sections(related_text)
    cited_keys = validation["cited_key_count"]
    bib_keys = validation["bib_key_count"]
    quality_report = {
        "survey_min_words": min_survey_words,
        "survey_words_ok": survey_words >= min_survey_words,
        "survey_min_subsections": min_survey_subsections,
        "survey_subsections_ok": survey_subsections >= min_survey_subsections,
        "survey_min_lines": min_survey_lines,
        "survey_lines_ok": survey_lines >= min_survey_lines,
        "min_related_citations": min_related_citations,
        "related_citations_ok": cited_keys >= min_related_citations,
        "min_related_words": min_related_words,
        "related_words_ok": related_words >= min_related_words,
        "min_related_sections": min_related_sections,
        "related_sections_ok": related_sections >= min_related_sections,
        "references_ok": len(reference_ids) > 0,
        "bib_entries_ok": bib_keys > 0,
        "required_files_ok": required_report["ok"],
        "tex_bib_ok": validation["ok"],
    }
    quality_report["ok"] = all(
        value for key, value in quality_report.items() if key.endswith("_ok")
    )
    return {
        "survey_root": str(survey_root),
        "related_root": str(related_root),
        "survey_words": survey_words,
        "survey_subsections": survey_subsections,
        "survey_lines": survey_lines,
        "related_words": related_words,
        "related_sections": related_sections,
        "reference_count": len(reference_ids),
        "key_map": str(key_map_path),
        "validation": validation,
        "required_files": required_report,
        "quality": quality_report,
        "removed_intermediates": removed_intermediates,
    }


# --- Commands ---


def command_prepare_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)

    references_ids = db.get_ids_from_query(
        args.topic, num=args.reference_num, shuffle=True
    )
    references_infos = db.get_paper_info_from_ids(references_ids)
    references_titles = [r["title"] for r in references_infos]
    references_abs = [r["abs"] for r in references_infos]

    abs_chunks, titles_chunks = chunk_papers(
        references_abs, references_titles, args.chunk_size
    )

    prompt_entries = []
    for titles, abstracts in zip(titles_chunks, abs_chunks):
        papers_text = ""
        for title, abstract in zip(titles, abstracts):
            papers_text += (
                f"---\npaper_title: {title}\n\npaper_content:\n\n{abstract}\n"
            )
        papers_text += "---\n"
        prompt_text = fill_prompt(
            prompts.ROUGH_OUTLINE_PROMPT,
            {
                "PAPER LIST": papers_text,
                "TOPIC": args.topic,
                "SECTION NUM": str(args.section_num),
            },
        )
        prompt_entries.append({"prompt": prompt_text, "titles": titles})

    output = {
        "topic": args.topic,
        "section_num": args.section_num,
        "rag_num": args.rag_num,
        "stage": "rough_outline",
        "prompts": prompt_entries,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_merge_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    outlines_path = resolve_path(workspace_root, args.outlines_path)
    outlines_data = json.loads(outlines_path.read_text(encoding="utf-8"))
    outlines = outlines_data["outlines"]

    outline_texts = ""
    for i, o in enumerate(outlines):
        outline_texts += f"---\noutline_id: {i}\n\noutline_content:\n\n{o}\n"
    outline_texts += "---\n"

    prompt_text = fill_prompt(
        prompts.MERGING_OUTLINE_PROMPT,
        {
            "OUTLINE LIST": outline_texts,
            "TOPIC": outlines_data["topic"],
            "SECTION NUM": str(outlines_data["section_num"]),
        },
    )

    output = {
        "topic": outlines_data["topic"],
        "section_num": outlines_data["section_num"],
        "stage": "merge_outline",
        "prompt": prompt_text,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_prepare_subsection_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)

    section_outline_path = resolve_path(workspace_root, args.section_outline_path)
    section_outline = section_outline_path.read_text(encoding="utf-8")

    _, sections, descriptions = extract_title_sections_descriptions(section_outline)

    prompt_entries = []
    for section_name, section_desc in zip(sections, descriptions):
        references_ids = db.get_ids_from_query(
            section_desc, num=args.rag_num, shuffle=True
        )
        references_infos = db.get_paper_info_from_ids(references_ids)
        paper_texts = ""
        for r in references_infos:
            paper_texts += (
                f"---\npaper_title: {r['title']}\n\npaper_abstract:\n{r['abs']}\n"
            )
            topics = r.get("topics", [])
            if topics:
                paper_texts += f"\npaper_topics: {', '.join(topics)}\n"
        paper_texts += "---\n"

        prompt_text = fill_prompt(
            prompts.SUBSECTION_OUTLINE_PROMPT,
            {
                "OVERALL OUTLINE": section_outline,
                "SECTION NAME": section_name,
                "SECTION DESCRIPTION": section_desc,
                "TOPIC": args.topic,
                "PAPER LIST": paper_texts,
            },
        )
        prompt_entries.append({"prompt": prompt_text, "section": section_name})

    output = {
        "topic": args.topic,
        "stage": "subsection_outline",
        "section_outline": section_outline,
        "sections": sections,
        "descriptions": descriptions,
        "prompts": prompt_entries,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_prepare_edit_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    merged_path = resolve_path(workspace_root, args.merged_outline_path)
    merged_outline = merged_path.read_text(encoding="utf-8")

    prompt_text = fill_prompt(
        prompts.EDIT_FINAL_OUTLINE_PROMPT
        if hasattr(prompts, "EDIT_FINAL_OUTLINE_PROMPT")
        else prompts.SUBSECTION_OUTLINE_PROMPT,
        {
            "OVERALL OUTLINE": merged_outline,
        },
    )

    output = {
        "stage": "edit_final_outline",
        "prompt": prompt_text,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_merge_outline(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    section_outline_path = resolve_path(workspace_root, args.section_outline_path)
    section_outline = section_outline_path.read_text(encoding="utf-8")

    subsection_path = resolve_path(workspace_root, args.subsection_outlines_path)
    subsection_data = json.loads(subsection_path.read_text(encoding="utf-8"))
    sub_outlines = subsection_data["outlines"]

    _, sections, descriptions = extract_title_sections_descriptions(section_outline)

    res = ""
    title_match = re.search(r"Title:\s*(.+)", section_outline)
    if title_match:
        res += f"# {title_match.group(1).strip()}\n\n"

    for i, section in enumerate(sections):
        res += f"## {i + 1} {section}\nDescription: {descriptions[i]}\n\n"
        if i < len(sub_outlines):
            subs, sub_descs = extract_subsections_subdescriptions(sub_outlines[i])
            for j, sub in enumerate(subs):
                res += f"### {i + 1}.{j + 1} {sub}\nDescription: {sub_descs[j] if j < len(sub_descs) else ''}\n\n"

    output_path = resolve_path(workspace_root, args.output_path)
    ensure_parent(output_path)
    output_path.write_text(res, encoding="utf-8")
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_prepare_subsection_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)

    outline_path = resolve_path(workspace_root, args.outline_path)
    outline_content = outline_path.read_text(encoding="utf-8")
    parsed = parse_outline(outline_content)

    total_ids: list[str] = []
    for descriptions in parsed["subsection_descriptions"]:
        for d in descriptions:
            ids = db.get_ids_from_query(d, num=args.rag_num, shuffle=False)
            total_ids.extend(ids)
    total_infos = db.get_paper_info_from_ids(list(set(total_ids)))
    info_dic = {p["id"]: p for p in total_infos}

    section_entries: list[list[dict]] = []
    for i, section in enumerate(parsed["sections"]):
        subsection_prompts: list[dict] = []
        for j, desc in enumerate(parsed["subsection_descriptions"][i]):
            ids = db.get_ids_from_query(desc, num=args.rag_num, shuffle=False)
            papers = [info_dic[_] for _ in ids if _ in info_dic]
            paper_texts = (
                db.format_papers_text(papers, include_analysis=True)
                if hasattr(db, "format_papers_text")
                else _format_papers_text_fallback(papers)
            )

            writing_prompt = fill_prompt(
                prompts.SUBSECTION_WRITING_PROMPT,
                {
                    "OVERALL OUTLINE": outline_content,
                    "SUBSECTION NAME": parsed["subsections"][i][j],
                    "DESCRIPTION": desc,
                    "TOPIC": args.topic,
                    "PAPER LIST": paper_texts,
                    "SECTION NAME": section,
                    "WORD NUM": str(args.subsection_len),
                },
            )
            subsection_prompts.append(
                {
                    "writing_prompt": writing_prompt,
                    "paper_texts": paper_texts,
                    "subsection_name": parsed["subsections"][i][j],
                    "section_name": section,
                }
            )
        section_entries.append(subsection_prompts)

    output = {
        "topic": args.topic,
        "outline": outline_content,
        "parsed_outline": parsed,
        "stage": "subsection_writing",
        "sections": section_entries,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_sections": len(section_entries)},
            indent=2,
        )
    )
    return 0


def command_prepare_native_survey_data(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)

    outline_path = resolve_path(workspace_root, args.outline_path)
    outline_content = outline_path.read_text(encoding="utf-8")
    parsed = parse_outline(outline_content)

    query_parts = [args.topic]
    for descriptions in parsed["subsection_descriptions"]:
        query_parts.extend(d for d in descriptions if d)
    if not query_parts:
        query_parts = [args.topic]

    paper_ids: list[str] = []
    seen_ids: set[str] = set()
    per_query = max(5, min(args.rag_num, 25))
    for query in query_parts:
        try:
            ids = db.get_ids_from_query(query, num=per_query, shuffle=False)
        except Exception:
            ids = []
        for paper_id in ids:
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                paper_ids.append(paper_id)
        if len(paper_ids) >= args.max_papers:
            break

    paper_ids = paper_ids[: args.max_papers]
    paper_infos = db.get_paper_info_from_ids(paper_ids) if paper_ids else []
    external_papers = load_external_library_papers(workspace_root, args.library_dir)
    if external_papers:
        seen_titles = {paper_title(paper).lower() for paper in paper_infos}
        for paper in external_papers[: args.max_external_papers]:
            title = paper_title(paper).lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                paper_infos.append(paper)
    paper_list = (
        db.format_papers_text(paper_infos, include_analysis=True)
        if hasattr(db, "format_papers_text")
        else _format_papers_text_fallback(paper_infos)
    )

    min_words = args.min_words
    target_words = args.target_words
    prompt_text = f"""Write a complete academic survey in Markdown about "{args.topic}".

Use the outline and paper library below as the only citation source. Rely on your native long-form writing ability: produce the whole survey in one coherent pass, not subsection-by-subsection fragments.

Outline:
---
{outline_content}
---

Paper library:
---
{paper_list}
---

Requirements:
1. Output only Markdown survey content. Do not include a bibliography section and do not include process notes.
2. Write in English unless the user instructions explicitly require another language.
3. Target about {target_words} words and never go below {min_words} words. A shorter draft is incomplete and must be expanded before returning.
4. Preserve the outline's main section and subsection organization. Use a survey-style Markdown hierarchy: one # title, 5-7 ## main sections, and about 36-44 ### numbered subsections before the References section.
5. Every technical comparison or historical claim should be supported by citations from the paper library.
6. Citation format is title-bracket style using exact paper titles from the paper library: [Exact Paper Title] or [Exact Paper Title; Another Exact Paper Title].
7. Do not use BibTeX keys, author-year citations, Markdown [@key] citations, URLs, or invented paper titles in the survey.
8. Prefer dense synthesis: group related works by mechanism, assumptions, guarantees, and limitations rather than summarizing papers one by one.
9. Cover foundations, major method families, theoretical assumptions/results, empirical/deployment considerations, and open gaps.
10. Write each ### subsection as 3-5 readable paragraphs with connected prose, comparative claims, assumptions, limitations, and transitions. Prefer paragraph breaks over very long paragraphs so the final Markdown has dense line coverage, typically 450+ lines for a full survey.
11. Do not collapse the survey into only ## sections. A draft with fewer than 36 ### subsections is structurally incomplete.
12. Before returning, self-check the approximate word count, line count, and subsection count; expand thin sections until the draft is in the {min_words}-{target_words} word range, has at least 36 ### subsections, and is not a compact long-paragraph draft.
"""

    output = {
        "topic": args.topic,
        "outline": outline_content,
        "stage": "native_survey_writing",
        "paper_count": len(paper_infos),
        "paper_ids": paper_ids,
        "external_paper_count": len(external_papers),
        "prompt": prompt_text,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "num_papers": len(paper_infos),
                "num_external_papers": len(external_papers),
                "min_words": min_words,
                "target_words": target_words,
            },
            indent=2,
        )
    )
    return 0


def _format_papers_text_fallback(papers: list[dict]) -> str:
    texts = ""
    for p in papers:
        texts += f"---\npaper_title: {p.get('title', '')}\n\npaper_abstract:\n{p.get('abs', '')}\n"
        topics = p.get("topics", [])
        if topics:
            texts += f"\npaper_topics: {', '.join(topics)}\n"
        strengths = p.get("strengths", "")
        if strengths:
            texts += f"\npaper_strengths: {strengths}\n"
        weaknesses = p.get("weaknesses", "")
        if weaknesses:
            texts += f"\npaper_weaknesses: {weaknesses}\n"
    texts += "---\n"
    return texts


def command_prepare_citation_check_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    drafts_path = resolve_path(workspace_root, args.drafts_path)
    drafts_data = json.loads(drafts_path.read_text(encoding="utf-8"))

    prompt_entries: list[dict] = []
    for section in drafts_data.get("sections", []):
        for subsection in section:
            check_prompt = fill_prompt(
                prompts.CHECK_CITATION_PROMPT
                if hasattr(prompts, "CHECK_CITATION_PROMPT")
                else prompts.SUBSECTION_WRITING_PROMPT,
                {
                    "PAPER LIST": subsection.get("paper_texts", ""),
                    "SUBSECTION NAME": subsection.get("subsection_name", ""),
                    "TOPIC": args.topic,
                    "OVERALL OUTLINE": drafts_data.get("outline", ""),
                    "DESCRIPTION": "",
                    "SECTION NAME": subsection.get("section_name", ""),
                    "WORD NUM": "200",
                },
            )
            prompt_entries.append(
                {
                    "prompt": check_prompt,
                    "subsection_name": subsection.get("subsection_name", ""),
                    "draft": subsection.get("draft", ""),
                }
            )

    output = {
        "stage": "citation_check",
        "prompts": prompt_entries,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_prepare_lce_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    content_path = resolve_path(workspace_root, args.content_path)
    content_data = json.loads(content_path.read_text(encoding="utf-8"))
    subsections = content_data.get("subsections", [])

    prompt_entries: list[dict] = []
    for i, sub in enumerate(subsections):
        previous = subsections[i - 1]["content"] if i > 0 else ""
        following = subsections[i + 1]["content"] if i < len(subsections) - 1 else ""
        prompt_text = fill_prompt(
            prompts.LCE_PROMPT,
            {
                "TOPIC": args.topic,
                "PREVIOUS": previous,
                "SUBSECTION": sub.get("content", ""),
                "FOLLOWING": following,
            },
        )
        prompt_entries.append(
            {
                "prompt": prompt_text,
                "index": i,
                "subsection_name": sub.get("name", ""),
            }
        )

    output = {
        "stage": "lce",
        "prompts": prompt_entries,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_resolve_references(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)

    survey_path = resolve_path(workspace_root, args.survey_path)
    survey_content = survey_path.read_text(encoding="utf-8")

    citations = extract_citations(survey_content)
    if not citations:
        output = {
            "survey": survey_content,
            "reference": {},
            "reference_full": {},
        }
        output_path = resolve_path(workspace_root, args.output_path)
        write_json(output_path, output)
        print(
            json.dumps({"output_path": str(output_path), "num_citations": 0}, indent=2)
        )
        return 0

    ids = (
        db.get_titles_from_citations(citations)
        if hasattr(db, "get_titles_from_citations")
        else _resolve_citations_fallback(db, citations)
    )
    citation_to_ids = dict(zip(citations, ids))
    valid_ids = [v for v in citation_to_ids.values() if v]
    paper_infos = db.get_paper_info_from_ids(valid_ids) if valid_ids else []
    info_by_id = {p["id"]: p for p in paper_infos}

    citation_to_ref_num: dict[str, str] = {}
    references: dict[str, str] = {}
    references_full: dict[str, dict] = {}

    for cite, pid in citation_to_ids.items():
        if pid and pid in info_by_id:
            ref_num = str(len(references) + 1)
            citation_to_ref_num[cite] = ref_num
            references[ref_num] = pid
            references_full[pid] = info_by_id[pid]

    updated = replace_title_citations_with_numbers(survey_content, citation_to_ref_num)
    updated = append_survey_references_section(updated, references, references_full)

    output = {
        "survey": updated,
        "reference": references,
        "reference_full": references_full,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_references": len(references)},
            indent=2,
        )
    )
    return 0


def _resolve_citations_fallback(db, citations: list[str]) -> list[str]:
    ids: list[str] = []
    for cite in citations:
        try:
            found = db.get_ids_from_query(cite, num=1, shuffle=False)
            ids.append(found[0] if found else "")
        except Exception:
            ids.append("")
    return ids


def command_generate_bibtex(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    survey_json_path = resolve_path(workspace_root, args.survey_json)
    survey_data = json.loads(survey_json_path.read_text(encoding="utf-8"))
    references_full = survey_data.get("reference_full", {})
    reference_ids = survey_data.get("reference") or {
        str(index + 1): paper_id for index, paper_id in enumerate(references_full.keys())
    }
    key_map = normalize_reference_key_map(reference_ids, references_full)
    bib_content = render_bibtex(reference_ids, references_full, key_map)

    bib_output = resolve_path(workspace_root, args.bib_output)
    ensure_parent(bib_output)
    bib_output.write_text(bib_content, encoding="utf-8")

    if args.key_map_output:
        key_map_path = resolve_path(workspace_root, args.key_map_output)
        write_json(key_map_path, key_map)

    print(
        json.dumps(
            {"bib_output": str(bib_output), "num_entries": len(reference_ids)},
            indent=2,
        )
    )
    return 0


def command_assemble_survey(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    outline_path = resolve_path(workspace_root, args.outline_path)
    outline_content = outline_path.read_text(encoding="utf-8")
    parsed = parse_outline(outline_content)

    sections_dir = resolve_path(workspace_root, args.sections_dir)

    parts: list[str] = []
    for i, section in enumerate(parsed["sections"]):
        parts.append(f"\n## {section}\n")
        for j, sub in enumerate(parsed["subsections"][i]):
            sub_file = sections_dir / f"section_{i}" / f"subsection_{j}.md"
            if sub_file.exists():
                content = sub_file.read_text(encoding="utf-8")
                parts.append(f"\n### {sub}\n\n{content}\n")
            else:
                parts.append(f"\n### {sub}\n\n(No content generated)\n")

    survey_text = "\n".join(parts)

    output_path = resolve_path(workspace_root, args.output_path)
    ensure_parent(output_path)
    output_path.write_text(survey_text, encoding="utf-8")
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_prepare_related_works_data(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    survey_path = resolve_path(workspace_root, args.survey_path)
    survey_data = json.loads(survey_path.read_text(encoding="utf-8"))
    survey_text = survey_data.get("survey", "")
    references_full = survey_data.get("reference_full", {})
    reference_ids = survey_data.get("reference") or {
        str(index + 1): paper_id for index, paper_id in enumerate(references_full.keys())
    }

    key_map = normalize_reference_key_map(reference_ids, references_full)
    citation_key_map = ""
    for ref_num in reference_ids:
        bib_key = key_map[ref_num]
        citation_key_map += f"{ref_num} -> \\cite{{{bib_key}}}\n"

    paper_list = ""
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num) or {}
        paper_list += f"---\nReference {ref_num}: {paper.get('title', '')}\n"
        paper_list += f"Abstract: {paper.get('abs', '')}\n"
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            paper_list += f"Authors: {', '.join(authors)}\n"
        paper_list += "\n"
    paper_list += "---\n"

    prompt_text = f"""Write a Related Works section in LaTeX for a survey about "{args.topic}".

Here is the survey content for context:
---
{survey_text[:5000]}
---

Citation key mapping (use \\cite{{key}} format):
{citation_key_map}

Reference papers:
{paper_list}

Requirements:
1. Write in LaTeX using \\subsection{{}} for thematic categories.
2. Use \\citep{{}} and \\citet{{}} commands with the exact keys shown above.
3. Target at least {args.min_citations} citations.
4. Organize by theme, not paper-by-paper.
5. Highlight limitations and open gaps.
6. Output only the LaTeX content (no preamble, no \\documentclass).
7. Each subsection should have 2-3 paragraphs.
8. Write {args.min_words}-{args.max_words} words total and include at least 3 subsections unless the citation material is insufficient.
9. Match related-work density: 4-6 thematic subsections, 700-1000 words when enough references are available, and no overly terse bullet-like paragraphs.
10. When many references are provided, cite broadly: aim to use every mapped citation key at least once, and use multi-key citations such as \\citep{{key1,key2,key3}} for closely related papers.
11. Include one explicit future-direction paragraph using phrases such as "future work", "open problems", or "principled extensions".
12. For gap-motivated topics, explicitly state the motivating gap and distinguish algorithmic constraints from theoretical or topology/linear-speedup constraints.
"""

    output = {
        "stage": "related_works",
        "prompt": prompt_text,
        "citation_key_map": citation_key_map,
        "key_map": key_map,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_prepare_judge_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    survey_path = resolve_path(workspace_root, args.survey_path)
    survey_content = survey_path.read_text(encoding="utf-8")

    criteria = {
        "Coverage": {
            "Criterion Description": "Whether the survey covers the main aspects of the topic comprehensively.",
            "Score 1 Description": "Very poor coverage, missing most important aspects.",
            "Score 2 Description": "Poor coverage, missing several important aspects.",
            "Score 3 Description": "Moderate coverage, covers some aspects well but misses others.",
            "Score 4 Description": "Good coverage, covers most aspects well with minor gaps.",
            "Score 5 Description": "Excellent coverage, comprehensively covers all important aspects.",
        },
        "Structure": {
            "Criterion Description": "Whether the survey is well-organized with logical flow between sections.",
            "Score 1 Description": "Very poor structure, disorganized and hard to follow.",
            "Score 2 Description": "Poor structure, significant organizational issues.",
            "Score 3 Description": "Moderate structure, generally organized but with some issues.",
            "Score 4 Description": "Good structure, well-organized with minor issues.",
            "Score 5 Description": "Excellent structure, perfectly organized with clear logical flow.",
        },
        "Relevance": {
            "Criterion Description": "Whether the cited papers are relevant and properly support the survey claims.",
            "Score 1 Description": "Very poor relevance, most citations are irrelevant or unsupported.",
            "Score 2 Description": "Poor relevance, many citations are irrelevant or weakly supported.",
            "Score 3 Description": "Moderate relevance, some citations are irrelevant but most are okay.",
            "Score 4 Description": "Good relevance, most citations are relevant and well-used.",
            "Score 5 Description": "Excellent relevance, all citations are highly relevant and well-integrated.",
        },
    }

    prompt_entries: list[dict] = []
    for criterion_name, criterion_paras in criteria.items():
        all_paras = {
            "TOPIC": args.topic,
            "SURVEY": survey_content,
        }
        all_paras.update(criterion_paras)
        prompt_text = fill_prompt(prompts.CRITERIA_BASED_JUDGING_PROMPT, all_paras)
        prompt_entries.append({"criterion": criterion_name, "prompt": prompt_text})

    output = {"stage": "judge", "prompts": prompt_entries}

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_criteria": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    tex_paths = [resolve_path(workspace_root, tex_path) for tex_path in args.tex_files]
    bib_path = resolve_path(workspace_root, args.bib)
    report = validate_tex_bib(tex_paths, bib_path)
    required_report = None
    if args.survey_root:
        survey_root = resolve_path(workspace_root, args.survey_root)
        related_root = workspace_root / "related_works"
        required_report = validate_required_files(
            [
                survey_root / "survey.md",
                survey_root / "survey.json",
                survey_root / "references.bib",
                related_root / "related_works.tex",
                related_root / "references.bib",
            ]
        )

    if args.json:
        payload: dict[str, Any] = {"validation": report}
        if required_report is not None:
            payload["required_files"] = required_report
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"TeX files: {', '.join(report['tex_files'])}")
        print(f"Bib file: {report['bib_file']}")
        print(f"Cited keys: {report['cited_key_count']}")
        print(f"Bib keys: {report['bib_key_count']}")
        print(
            "Missing keys: "
            + (", ".join(report["missing_keys"]) if report["missing_keys"] else "none")
        )
        print(
            "Duplicate bib keys: "
            + (
                ", ".join(report["duplicate_bib_keys"])
                if report["duplicate_bib_keys"]
                else "none"
            )
        )
        print(
            "Unused keys: "
            + (", ".join(report["unused_keys"]) if report["unused_keys"] else "none")
        )
        if required_report is not None:
            print(
                "Missing required files: "
                + (
                    ", ".join(required_report["missing_files"])
                    if required_report["missing_files"]
                    else "none"
                )
            )

    required_ok = True if required_report is None else required_report["ok"]
    return 0 if report["ok"] and required_ok else 1


def command_finalize_package(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    report = ensure_final_survey_package(
        workspace_root=workspace_root,
        survey_root_raw=args.survey_root,
        related_root_raw=args.related_root,
        topic=args.topic,
        min_survey_words=args.min_survey_words,
        min_survey_subsections=args.min_survey_subsections,
        min_survey_lines=args.min_survey_lines,
        min_related_citations=args.min_related_citations,
        min_related_words=args.min_related_words,
        min_related_sections=args.min_related_sections,
        keep_intermediates=args.keep_intermediates,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Survey root: {report['survey_root']}")
        print(f"Related works root: {report['related_root']}")
        print(f"Survey words: {report['survey_words']}")
        print(f"Survey subsections: {report['survey_subsections']}")
        print(f"Survey lines: {report['survey_lines']}")
        print(f"References: {report['reference_count']}")
        print(f"Missing keys: {', '.join(report['validation']['missing_keys']) or 'none'}")
        print(
            "Duplicate bib keys: "
            + (", ".join(report["validation"]["duplicate_bib_keys"]) or "none")
        )
    return 0 if report["quality"]["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pure-data survey tools + prompt preparation (no LLM calls)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("--workspace", default=".")
        cmd.add_argument("--library-dir", default="survey/library")

    p = subparsers.add_parser("prepare-outline-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--section-num", type=int, default=DEFAULT_SECTION_NUM)
    p.add_argument("--reference-num", type=int, default=DEFAULT_OUTLINE_REFERENCE_NUM)
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)
    p.add_argument("--chunk-size", type=int, default=30000)

    p = subparsers.add_parser("merge-outline-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--outlines-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-subsection-outline-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--section-outline-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)

    p = subparsers.add_parser("prepare-edit-outline-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--merged-outline-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("merge-outline")
    p.add_argument("--workspace", default=".")
    p.add_argument("--section-outline-path", required=True)
    p.add_argument("--subsection-outlines-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-subsection-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--outline-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)
    p.add_argument("--subsection-len", type=int, default=DEFAULT_SUBSECTION_LEN)

    p = subparsers.add_parser("prepare-native-survey-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--outline-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)
    p.add_argument("--max-papers", type=int, default=DEFAULT_OUTLINE_REFERENCE_NUM)
    p.add_argument("--max-external-papers", type=int, default=50)
    p.add_argument("--min-words", type=int, default=DEFAULT_MIN_SURVEY_WORDS)
    p.add_argument("--target-words", type=int, default=7000)

    p = subparsers.add_parser("prepare-citation-check-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--drafts-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-lce-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--content-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("resolve-references")
    add_common(p)
    p.add_argument("--survey-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("generate-bibtex")
    p.add_argument("--workspace", default=".")
    p.add_argument("--survey-json", required=True)
    p.add_argument("--bib-output", required=True)
    p.add_argument("--key-map-output", default="")

    p = subparsers.add_parser("assemble-survey")
    p.add_argument("--workspace", default=".")
    p.add_argument("--outline-path", required=True)
    p.add_argument("--sections-dir", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-related-works-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--survey-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--max-words", type=int, default=1000)
    p.add_argument("--min-words", type=int, default=DEFAULT_MIN_RELATED_WORDS)
    p.add_argument("--min-citations", type=int, default=DEFAULT_MIN_CITATIONS)

    p = subparsers.add_parser("prepare-judge-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--survey-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("validate")
    p.add_argument("--workspace", default=".")
    p.add_argument("--tex", action="append", required=True, dest="tex_files")
    p.add_argument("--bib", required=True)
    p.add_argument("--survey-root", default="")
    p.add_argument("--json", action="store_true")

    p = subparsers.add_parser("finalize-package")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--survey-root", default="survey")
    p.add_argument("--related-root", default="related_works")
    p.add_argument("--min-survey-words", type=int, default=DEFAULT_MIN_SURVEY_WORDS)
    p.add_argument(
        "--min-survey-subsections",
        type=int,
        default=DEFAULT_MIN_SURVEY_SUBSECTIONS,
    )
    p.add_argument("--min-survey-lines", type=int, default=DEFAULT_MIN_SURVEY_LINES)
    p.add_argument(
        "--min-related-citations", type=int, default=DEFAULT_MIN_RELATED_CITATIONS
    )
    p.add_argument("--min-related-words", type=int, default=DEFAULT_MIN_RELATED_WORDS)
    p.add_argument(
        "--min-related-sections", type=int, default=DEFAULT_MIN_RELATED_SECTIONS
    )
    p.add_argument("--keep-intermediates", action="store_true")
    p.add_argument("--json", action="store_true")

    return parser


COMMANDS = {
    "prepare-outline-data": command_prepare_outline_data,
    "merge-outline-data": command_merge_outline_data,
    "prepare-subsection-outline-data": command_prepare_subsection_outline_data,
    "prepare-edit-outline-data": command_prepare_edit_outline_data,
    "merge-outline": command_merge_outline,
    "prepare-subsection-data": command_prepare_subsection_data,
    "prepare-native-survey-data": command_prepare_native_survey_data,
    "prepare-citation-check-data": command_prepare_citation_check_data,
    "prepare-lce-data": command_prepare_lce_data,
    "resolve-references": command_resolve_references,
    "generate-bibtex": command_generate_bibtex,
    "assemble-survey": command_assemble_survey,
    "prepare-related-works-data": command_prepare_related_works_data,
    "prepare-judge-data": command_prepare_judge_data,
    "validate": command_validate,
    "finalize-package": command_finalize_package,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        handler = COMMANDS.get(args.command)
        if handler:
            return handler(args)
        parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
