#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, List


TEXT_EXTENSIONS = {".yaml", ".yml", ".json", ".md", ".txt"}


def tokenize(query: str) -> List[str]:
    return [token for token in re.split(r"\W+", query.lower()) if token]


def extract_title(text: str, path: Path) -> str:
    patterns = [
        r"paper_title:\s*(.+)",
        r"method_name:\s*(.+)",
        r"title:\s*(.+)",
        r"^#\s+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip().strip('"')
    return path.stem


def score_text(text: str, terms: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(term) for term in terms)


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"root not found: {root}")

    terms = tokenize(args.query)
    results = []
    for path in iter_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        score = score_text(text, terms)
        if score <= 0:
            continue
        results.append(
            {
                "title": extract_title(text, path),
                "file_path": str(path.resolve()),
                "score": score,
                "matches": [term for term in terms if term in text.lower()],
            }
        )

    results.sort(key=lambda item: (-item["score"], item["title"].lower()))
    print(json.dumps(results[: args.top_k], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
