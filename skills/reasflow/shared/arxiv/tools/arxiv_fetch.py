#!/usr/bin/env python3
"""CLI helper for searching and downloading arXiv papers.

Used by the ``arxiv`` skill (skills/arxiv/SKILL.md).

Dependencies
------------
    pip install arxiv

Commands
--------
search    Search arXiv and print results as JSON.
download  Download a paper PDF by arXiv ID.

Examples
--------
    python3 tools/arxiv_fetch.py search "attention mechanism" --max 3
    python3 tools/arxiv_fetch.py download 2301.07041 --dir papers
"""

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

try:
    import arxiv
except ImportError:
    print("Error: 'arxiv' package not installed.", file=sys.stderr)
    print("Install with: pip install arxiv", file=sys.stderr)
    sys.exit(1)

_USER_AGENT = "arxiv-skill/1.0 (reasflow-codex)"
_MIN_PDF_BYTES = 10_240
_NEW_STYLE_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
_OLD_STYLE_ID_RE = re.compile(r"^[A-Za-z.-]+/\d{7}(v\d+)?$")


def _get_proxy() -> str | None:
    """Get proxy from environment variables."""
    for var in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        if var in os.environ:
            return os.environ[var]
    return None


def _normalize_id(arxiv_id: str) -> str:
    """Strip URL/version noise and return a clean arXiv ID."""
    value = arxiv_id.strip()
    if "/abs/" in value:
        value = value.split("/abs/", 1)[1]
    if value.startswith("id:"):
        value = value[3:]
    if "v" in value.split(".")[-1]:
        value = value.rsplit("v", 1)[0]
    return value


def _looks_like_arxiv_id(value: str) -> bool:
    """Return True when the input resembles a modern or legacy arXiv ID."""
    value = value.strip()
    return bool(_NEW_STYLE_ID_RE.match(value) or _OLD_STYLE_ID_RE.match(value))


def search(query: str, max_results: int = 10, start: int = 0) -> list[dict]:
    """Search arXiv and return a list of paper dictionaries.

    Uses the official arxiv library which handles retries, rate limiting,
    and connection pooling automatically.
    """
    query = query.strip()

    # Configure client with proxy if set
    proxy = _get_proxy()
    client_kwargs = {}
    if proxy:
        client_kwargs["proxies"] = {"http": proxy, "https": proxy}

    # Build search (offset is handled by client.results())
    if query.startswith("id:") or _looks_like_arxiv_id(query):
        arxiv_id = _normalize_id(query)
        search_obj = arxiv.Search(id_list=[arxiv_id])
    else:
        search_obj = arxiv.Search(
            query=query,
            max_results=max_results + start,  # Fetch more to support offset
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending,
        )

    # Convert results
    results = []
    client = arxiv.Client(**client_kwargs)
    for i, result in enumerate(client.results(search_obj)):
        if i < start:
            continue
        if len(results) >= max_results:
            break
        results.append({
            "id": result.entry_id.split("/abs/")[-1].split("v")[0],
            "title": result.title.replace("\n", " "),
            "authors": [author.name for author in result.authors],
            "abstract": result.summary.replace("\n", " "),
            "published": result.published.strftime("%Y-%m-%d") if result.published else "",
            "updated": result.updated.strftime("%Y-%m-%d") if result.updated else "",
            "categories": result.categories,
            "pdf_url": result.pdf_url,
            "abs_url": result.entry_id,
        })

    return results


def download(arxiv_id: str, output_dir: str = "papers", proxy: str | None = None) -> dict:
    """Download a paper PDF and return metadata about the saved file."""
    clean_id = _normalize_id(arxiv_id)
    safe_id = clean_id.replace("/", "_")

    dest_dir = Path(output_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{safe_id}.pdf"

    if dest.exists():
        return {
            "id": clean_id,
            "path": str(dest),
            "size_kb": dest.stat().st_size // 1024,
            "skipped": True,
        }

    # Use arxiv library to download
    proxy = proxy or _get_proxy()
    client_kwargs = {}
    if proxy:
        client_kwargs["proxies"] = {"http": proxy, "https": proxy}

    client = arxiv.Client(**client_kwargs)
    search_obj = arxiv.Search(id_list=[clean_id])
    paper = next(client.results(search_obj))

    for attempt in (1, 2):
        try:
            paper.download_pdf(dirpath=str(dest_dir), filename=f"{safe_id}.pdf")
            break
        except Exception as exc:
            if attempt == 1:
                time.sleep(2)
                continue
            raise RuntimeError(f"Failed to download {clean_id} after retries: {exc}")

    # Verify file size
    if not dest.exists():
        raise RuntimeError(f"Download failed, file not created: {dest}")
    file_size = dest.stat().st_size
    if file_size < _MIN_PDF_BYTES:
        dest.unlink()
        raise ValueError(
            f"Downloaded file is only {file_size} bytes - likely an error page"
        )

    return {
        "id": clean_id,
        "path": str(dest),
        "size_kb": file_size // 1024,
        "skipped": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search and download arXiv papers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search arXiv papers")
    search_parser.add_argument(
        "query",
        help="Search query or arXiv ID (bare ID or id:ARXIV_ID).",
    )
    search_parser.add_argument(
        "--max",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of results (default: 10).",
    )
    search_parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start offset for pagination (default: 0).",
    )

    download_parser = subparsers.add_parser("download", help="Download a paper PDF by arXiv ID")
    download_parser.add_argument(
        "id",
        help="arXiv paper ID, e.g. 2301.07041 or cs/0601001",
    )
    download_parser.add_argument(
        "--dir",
        default="papers",
        metavar="DIR",
        help="Output directory (default: papers).",
    )
    download_parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to sleep after download (default: 1.0).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "search":
        results = search(args.query, max_results=args.max, start=args.start)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.command == "download":
        result = download(args.id, output_dir=args.dir)
        if result.get("skipped"):
            print(json.dumps({**result, "message": "already exists, skipped"}, ensure_ascii=False))
        else:
            time.sleep(args.delay)
            print(json.dumps(result, ensure_ascii=False))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())