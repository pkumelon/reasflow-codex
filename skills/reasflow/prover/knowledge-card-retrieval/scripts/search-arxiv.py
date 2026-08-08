#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

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
    results: list[dict[str, object]] = []
    for entry in root.findall("atom:entry", ns):
        authors = [
            author.findtext("atom:name", default="", namespaces=ns)
            for author in entry.findall("atom:author", ns)
        ]
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
                break
        summary = entry.findtext("atom:summary", default="", namespaces=ns).strip()
        results.append(
            {
                "title": entry.findtext("atom:title", default="", namespaces=ns).strip(),
                "authors": [author for author in authors if author][:5],
                "abstract": summary[:500] + ("..." if len(summary) > 500 else ""),
                "arxiv_id": entry.findtext("atom:id", default="", namespaces=ns)
                .rstrip("/")
                .split("/")[-1],
                "published_date": entry.findtext(
                    "atom:published",
                    default="",
                    namespaces=ns,
                )[:10],
                "pdf_url": pdf_url,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()

    print(json.dumps(search_arxiv(args.query, args.max_results), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
