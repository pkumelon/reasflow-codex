#!/usr/bin/env python3

import argparse
import base64
import json
import os
import re
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional


ARXIV_API_URL = "http://export.arxiv.org/api/query"
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query")
    parser.add_argument("--arxiv-id")
    parser.add_argument("--max-results", type=int, default=3)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metadata-file")
    parser.add_argument("--use-llm", choices=["yes", "no"], default="no")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


def fetch_arxiv_entries(query: str, max_results: int) -> List[Dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    with urllib.request.urlopen(f"{ARXIV_API_URL}?{params}") as response:
        payload = response.read()
    root = ET.fromstring(payload)
    entries: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NAMESPACE):
        entry_id = entry.findtext("atom:id", default="", namespaces=ATOM_NAMESPACE)
        arxiv_id = entry_id.rsplit("/", 1)[-1]
        authors = [
            author.findtext("atom:name", default="", namespaces=ATOM_NAMESPACE)
            for author in entry.findall("atom:author", ATOM_NAMESPACE)
        ]
        entries.append(
            {
                "paper_title": (entry.findtext("atom:title", default="", namespaces=ATOM_NAMESPACE) or "").strip(),
                "authors": [author for author in authors if author],
                "year": extract_year(entry.findtext("atom:published", default="", namespaces=ATOM_NAMESPACE)),
                "venue": "arXiv preprint",
                "method_name": (entry.findtext("atom:title", default="", namespaces=ATOM_NAMESPACE) or "").strip(),
                "algorithm_description": collapse_ws(
                    entry.findtext("atom:summary", default="", namespaces=ATOM_NAMESPACE) or ""
                ),
                "arxiv_id": arxiv_id,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            }
        )
    return entries


def fetch_arxiv_entries_by_id(arxiv_id: str) -> List[Dict[str, Any]]:
    cleaned = arxiv_id.strip()
    if not re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", cleaned):
        raise SystemExit(f"invalid arXiv id: {arxiv_id}")
    params = urllib.parse.urlencode({"id_list": cleaned})
    with urllib.request.urlopen(f"{ARXIV_API_URL}?{params}") as response:
        payload = response.read()
    root = ET.fromstring(payload)
    entries: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NAMESPACE):
        entry_id = entry.findtext("atom:id", default="", namespaces=ATOM_NAMESPACE)
        if entry_id.rstrip("/").split("/")[-1] != cleaned:
            continue
        authors = [
            author.findtext("atom:name", default="", namespaces=ATOM_NAMESPACE)
            for author in entry.findall("atom:author", ATOM_NAMESPACE)
        ]
        entries.append(
            {
                "paper_title": (entry.findtext("atom:title", default="", namespaces=ATOM_NAMESPACE) or "").strip(),
                "authors": [author for author in authors if author],
                "year": extract_year(entry.findtext("atom:published", default="", namespaces=ATOM_NAMESPACE)),
                "venue": "arXiv preprint",
                "method_name": (entry.findtext("atom:title", default="", namespaces=ATOM_NAMESPACE) or "").strip(),
                "algorithm_description": collapse_ws(
                    entry.findtext("atom:summary", default="", namespaces=ATOM_NAMESPACE) or ""
                ),
                "arxiv_id": cleaned,
                "pdf_url": f"https://arxiv.org/pdf/{cleaned}.pdf",
            }
        )
    if not entries:
        raise SystemExit(f"arXiv id not found: {cleaned}")
    return entries


def extract_year(published: str) -> Optional[int]:
    match = re.match(r"(\d{4})", published or "")
    return int(match.group(1)) if match else None


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_filename(title: str, arxiv_id: Optional[str]) -> str:
    base = arxiv_id or re.sub(r"\W+", "_", title).strip("_") or "knowledge_card"
    return f"{base}.yaml"


def heuristic_card(metadata: Dict[str, Any]) -> Dict[str, Any]:
    abstract = metadata.get("algorithm_description", "")
    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    advantages = [
        sentence.strip()
        for sentence in sentences
        if re.search(r"improv|converg|robust|efficient|scal|accelerat|reduce", sentence, re.IGNORECASE)
    ][:5]
    return {
        "knowledge_card": {
            "paper_title": metadata.get("paper_title", ""),
            "authors": metadata.get("authors", []),
            "year": metadata.get("year"),
            "venue": metadata.get("venue", "arXiv preprint"),
            "method_name": metadata.get("method_name", metadata.get("paper_title", "")),
            "algorithm_description": abstract,
            "pseudocode": "",
            "advantages_scenarios": advantages,
            "datasets_used": [],
            "objective_function": {"description": ""},
            "baseline_algorithms": [],
            "experiments_performed": [],
            "key_results": [],
            "theoretical_contributions": [],
            "implementation_details": [],
            "limitations_future_work": [],
            "source": {
                "arxiv_id": metadata.get("arxiv_id"),
                "pdf_url": metadata.get("pdf_url"),
            },
        }
    }


def call_llm(metadata: Dict[str, Any], base_url: str, api_key: str, model: str) -> Optional[str]:
    prompt_text = textwrap.dedent(
        f"""
        Convert this arXiv metadata into strictly valid YAML with a top-level key `knowledge_card`.
        Use only the supplied data. Leave unknown fields empty.
        Metadata JSON:
        {json.dumps(metadata, ensure_ascii=False)}
        Required fields:
        - paper_title
        - authors
        - year
        - venue
        - method_name
        - algorithm_description
        - pseudocode
        - advantages_scenarios
        - datasets_used
        - objective_function.description
        - baseline_algorithms
        - experiments_performed
        - key_results
        - theoretical_contributions
        - implementation_details
        - limitations_future_work
        - source.arxiv_id
        - source.pdf_url
        """
    ).strip()
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "stream": True,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "openai-python/1.0",
        },
        method="POST",
    )
    try:
        chunks = []
        with urllib.request.urlopen(request, timeout=60) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        chunks.append(delta)
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
        return "".join(chunks).strip() or None
    except Exception:
        return None


def render_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if re.search(r"[:#\-\[\]\{\}\n]", text):
        return json.dumps(text, ensure_ascii=False)
    return text


def yaml_lines(value: Any, indent: int = 0) -> List[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: List[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(yaml_lines(item, indent + 2))
            elif isinstance(item, str) and "\n" in item:
                lines.append(f"{prefix}{key}: |")
                for line in item.splitlines() or [""]:
                    lines.append(f"{' ' * (indent + 2)}{line}")
            else:
                lines.append(f"{prefix}{key}: {render_scalar(item)}")
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(item, indent + 2))
            elif isinstance(item, list):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}- {render_scalar(item)}")
        return lines
    return [f"{prefix}{render_scalar(value)}"]


def dump_yaml(document: Dict[str, Any]) -> str:
    return "\n".join(yaml_lines(document)) + "\n"


def parse_metadata_file(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return [payload]


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.use_llm == "yes" and (not args.base_url or not args.api_key):
        raise SystemExit(
            "--use-llm yes requires OPENAI_BASE_URL and OPENAI_API_KEY "
            "(via environment or --base-url/--api-key)"
        )

    papers: List[Dict[str, Any]] = []
    if args.metadata_file:
        papers = parse_metadata_file(Path(args.metadata_file).resolve())
    elif args.arxiv_id:
        papers = fetch_arxiv_entries_by_id(args.arxiv_id)
    elif args.query:
        papers = fetch_arxiv_entries(args.query, args.max_results)
    else:
        raise SystemExit("one of --query, --arxiv-id, or --metadata-file is required")

    written = []
    for paper in papers:
        card_doc = heuristic_card(paper)
        llm_yaml = None
        if args.use_llm == "yes":
            llm_yaml = call_llm(paper, args.base_url, args.api_key, args.model)
        filename = normalize_filename(
            paper.get("paper_title", "knowledge_card"),
            paper.get("arxiv_id"),
        )
        destination = output_dir / filename
        destination.write_text(llm_yaml or dump_yaml(card_doc), encoding="utf-8")
        written.append(
            {
                "paper_title": paper.get("paper_title"),
                "arxiv_id": paper.get("arxiv_id"),
                "file_path": str(destination),
                "used_llm": bool(llm_yaml),
            }
        )

    print(json.dumps({"written": written}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
