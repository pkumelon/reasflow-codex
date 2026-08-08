#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--catalog")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    default_catalog = script_dir.parent / "assets" / "knowledge-cards" / "catalog.json"
    catalog_path = Path(args.catalog).resolve() if args.catalog else default_catalog
    if not catalog_path.exists():
        raise SystemExit(f"catalog not found: {catalog_path}")

    cards = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_root = catalog_path.parent
    for card in cards:
        if card.get("id") != args.id:
            continue
        file_path = catalog_root / Path(card.get("file_path", "").replace("\\", "/"))
        if not file_path.exists():
            raise SystemExit(f"card file not found: {file_path}")
        print(file_path.read_text(encoding="utf-8"))
        return 0

    raise SystemExit(f"card id not found: {args.id}")


if __name__ == "__main__":
    raise SystemExit(main())
