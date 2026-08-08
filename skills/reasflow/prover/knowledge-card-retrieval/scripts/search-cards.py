#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def score_card(card: dict, terms: list[str]) -> int:
    haystack = " ".join(
        [
            str(card.get("id", "")),
            str(card.get("type", "")),
            str(card.get("domain", "")),
            str(card.get("embedding_text", "")),
            " ".join(card.get("metadata", {}).get("tags", [])),
        ]
    ).lower()
    return sum(term in haystack for term in terms)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    catalog_path = Path(args.catalog).resolve()
    if not catalog_path.exists():
        raise SystemExit(f"catalog not found: {catalog_path}")

    cards = json.loads(catalog_path.read_text())
    terms = [term.lower() for term in args.query.split() if term.strip()]

    catalog_root = catalog_path.parent
    ranked = []
    for card in cards:
        score = score_card(card, terms)
        if score == 0:
            continue
        relative_path = Path(card.get("file_path", "").replace("\\", "/"))
        ranked.append(
            {
                "id": card.get("id"),
                "title": card.get("metadata", {}).get("title"),
                "type": card.get("type"),
                "domain": card.get("domain"),
                "score": score,
                "file_path": str((catalog_root / relative_path).resolve()),
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["id"] or ""))
    print(json.dumps(ranked[: args.top_k], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
