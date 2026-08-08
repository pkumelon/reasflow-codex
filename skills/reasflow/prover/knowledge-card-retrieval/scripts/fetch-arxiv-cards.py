#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import tarfile
import tempfile
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
ARXIV_API = "https://export.arxiv.org/api/query"


def search_arxiv(query: str, max_results: int) -> list[dict[str, object]]:
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    with urllib.request.urlopen(f"{ARXIV_API}?{params}", timeout=60) as response:
        xml_text = response.read().decode("utf-8")
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers = []
    for entry in root.findall("atom:entry", ns):
        arxiv_id = entry.findtext("atom:id", default="", namespaces=ns).rstrip("/").split("/")[-1]
        authors = [author.findtext("atom:name", default="", namespaces=ns) for author in entry.findall("atom:author", ns)]
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
                break
        papers.append(
            {
                "title": entry.findtext("atom:title", default="", namespaces=ns).strip(),
                "authors": [a for a in authors if a][:10],
                "abstract": entry.findtext("atom:summary", default="", namespaces=ns).strip(),
                "arxiv_id": arxiv_id,
                "published_date": entry.findtext("atom:published", default="", namespaces=ns)[:10],
                "pdf_url": pdf_url,
            }
        )
    return papers


def fetch_source_text(arxiv_id: str) -> str:
    try:
        with urllib.request.urlopen(f"https://arxiv.org/e-print/{arxiv_id}", timeout=60) as response:
            tar_bytes = response.read()
    except Exception:
        return ""

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tar_path = Path(tmpdir) / "src.tar"
            tar_path.write_bytes(tar_bytes)
            texts: list[str] = []
            with tarfile.open(tar_path, "r:*") as archive:
                archive.extractall(tmpdir)
            for pattern in ("*.tex", "*.bib", "*.bbl"):
                for file_path in Path(tmpdir).rglob(pattern):
                    texts.append(file_path.read_text(encoding="utf-8", errors="ignore"))
            return "\n\n".join(texts)[:120000]
    except Exception:
        return ""


def heuristic_yaml(paper: dict[str, object]) -> str:
    abstract = str(paper.get("abstract", "")).strip()
    advantages = []
    for sentence in re.split(r"(?<=[.!?])\s+", abstract):
        if any(token in sentence.lower() for token in ["converg", "stabil", "efficien", "improv", "robust"]):
            advantages.append(sentence.strip())
    body = {
        "knowledge_card": {
            "paper_title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "year": int(str(paper.get("published_date", "0000"))[:4] or 0),
            "venue": "arXiv preprint",
            "method_name": paper.get("title", ""),
            "algorithm_description": abstract,
            "pseudocode": "",
            "advantages_scenarios": advantages[:6],
            "datasets_used": [],
            "objective_function": {"description": ""},
            "baseline_algorithms": [],
            "experiments_performed": [],
            "key_results": [],
            "theoretical_contributions": [],
            "implementation_details": [],
            "limitations_future_work": [],
        }
    }
    return dump_yaml(body)


def render_scalar(value: object) -> str:
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


def yaml_lines(value: object, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
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
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}- {render_scalar(item)}")
        return lines
    return [f"{prefix}{render_scalar(value)}"]


def dump_yaml(document: dict[str, object]) -> str:
    return "\n".join(yaml_lines(document)) + "\n"


def llm_yaml(paper: dict[str, object], source_text: str, base_url: str, api_key: str, model: str) -> str:
    schema_prompt = textwrap.dedent(
        """
        Produce strictly valid YAML with this schema:
        knowledge_card:
          paper_title: <full title>
          authors: [<up to 10 authors>]
          year: <integer>
          venue: <venue short name>
          method_name: <main method name>
          algorithm_description: |
            <concise multi-paragraph description>
          pseudocode: |
            <algorithm-style pseudocode or high-level steps>
          advantages_scenarios: [<claims or applicable scenarios>]
          datasets_used: []
          objective_function:
            description: |
              <objective if available>
          baseline_algorithms: []
          experiments_performed: []
          key_results: []
          theoretical_contributions: []
          implementation_details: []
          limitations_future_work: []
        Rules:
        - Use only provided metadata, abstract, and source text.
        - If a field is unknown, leave it empty.
        - Output YAML only.
        """
    ).strip()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise academic assistant that outputs only YAML."},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "schema": schema_prompt,
                        "paper": paper,
                        "source_text": source_text[:60000],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    payload["stream"] = True
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "openai-python/1.0",
        },
        method="POST",
    )
    chunks = []
    with urllib.request.urlopen(request, timeout=180) as response:
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
    return "".join(chunks).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--max-results", type=int, default=3)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if not args.base_url or not args.api_key:
        raise SystemExit(
            "OPENAI_BASE_URL and OPENAI_API_KEY must be set "
            "(via environment or --base-url/--api-key) before running fetch-arxiv-cards"
        )

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    papers = search_arxiv(args.query, args.max_results)
    saved = []
    for paper in papers:
        arxiv_id = str(paper.get("arxiv_id", "unknown"))
        source_text = fetch_source_text(arxiv_id)
        try:
            content = llm_yaml(paper, source_text, args.base_url, args.api_key, args.model)
        except Exception:
            content = heuristic_yaml(paper)
        path = output_dir / f"{arxiv_id}.yaml"
        path.write_text(content + "\n", encoding="utf-8")
        saved.append({"arxiv_id": arxiv_id, "file": str(path), "title": paper.get("title")})

    print(json.dumps({"saved": saved}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
