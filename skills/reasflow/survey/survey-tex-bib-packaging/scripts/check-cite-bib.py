#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CITE_PATTERN = re.compile(
    r"\\[A-Za-z]*cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
BIB_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)


def parse_cite_keys(tex_path: Path) -> set[str]:
    content = tex_path.read_text(encoding="utf-8")
    keys: set[str] = set()
    for match in CITE_PATTERN.finditer(content):
        block = match.group(1)
        for key in block.split(","):
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that cite keys in TeX files match BibTeX entries",
    )
    parser.add_argument("--tex", action="append", required=True, dest="tex_files")
    parser.add_argument("--bib", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-unused", action="store_true")
    args = parser.parse_args()

    tex_paths = [Path(path) for path in args.tex_files]
    bib_path = Path(args.bib)

    for tex_path in tex_paths:
        if not tex_path.exists():
            raise SystemExit(f"TeX file not found: {tex_path}")
    if not bib_path.exists():
        raise SystemExit(f"Bib file not found: {bib_path}")

    cited_keys: set[str] = set()
    citations_by_file: dict[str, list[str]] = {}
    for tex_path in tex_paths:
        keys = sorted(parse_cite_keys(tex_path))
        cited_keys.update(keys)
        citations_by_file[str(tex_path)] = keys

    bib_keys, duplicate_keys = parse_bib_keys(bib_path)
    missing_keys = sorted(cited_keys - bib_keys)
    unused_keys = sorted(bib_keys - cited_keys)

    report = {
        "tex_files": [str(path) for path in tex_paths],
        "bib_file": str(bib_path),
        "citations_by_file": citations_by_file,
        "cited_key_count": len(cited_keys),
        "bib_key_count": len(bib_keys),
        "missing_keys": missing_keys,
        "unused_keys": unused_keys,
        "duplicate_bib_keys": duplicate_keys,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"TeX files: {', '.join(report['tex_files'])}")
        print(f"Bib file: {report['bib_file']}")
        print(f"Cited keys: {report['cited_key_count']}")
        print(f"Bib keys: {report['bib_key_count']}")
        if missing_keys:
            print(f"Missing keys ({len(missing_keys)}): {', '.join(missing_keys)}")
        else:
            print("Missing keys: none")
        if duplicate_keys:
            print(
                f"Duplicate bib keys ({len(duplicate_keys)}): {', '.join(duplicate_keys)}"
            )
        else:
            print("Duplicate bib keys: none")
        if args.allow_unused:
            if unused_keys:
                print(f"Unused keys ({len(unused_keys)}): {', '.join(unused_keys)}")
            else:
                print("Unused keys: none")

    failed = bool(missing_keys or duplicate_keys)
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
