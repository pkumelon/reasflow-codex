#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

SKIP_DIRS = {"__pycache__", ".git", "node_modules"}
KIND_BY_SUFFIX = {
    ".tex": "latex",
    ".bib": "bibtex",
    ".yaml": "metadata",
    ".yml": "metadata",
    ".md": "notes",
    ".txt": "notes",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".pdf": "image_or_pdf",
    ".eps": "image",
    ".svg": "image",
    ".json": "data",
    ".csv": "data",
    ".tsv": "data",
}


def size_to_human(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.1f}{unit}"
        value /= 1024.0
    return f"{size}B"


def hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def collect_assets(root: Path, with_hash: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        rel_path = file_path.relative_to(root)
        suffix = file_path.suffix.lower()
        stat = file_path.stat()
        entry = {
            "path": str(rel_path),
            "kind": KIND_BY_SUFFIX.get(suffix, "other"),
            "size_bytes": stat.st_size,
            "size_human": size_to_human(stat.st_size),
            "mtime_epoch": int(stat.st_mtime),
            "readable": os.access(file_path, os.R_OK),
        }
        if with_hash:
            try:
                entry["sha256_16"] = hash_file(file_path)
            except Exception:
                entry["sha256_16"] = "(unreadable)"
        entries.append(entry)
    return entries


def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, dict[str, Any]] = {}
    for entry in entries:
        bucket = by_kind.setdefault(entry["kind"], {"count": 0, "size_bytes": 0})
        bucket["count"] += 1
        bucket["size_bytes"] += entry["size_bytes"]
    for kind in by_kind:
        by_kind[kind]["size_human"] = size_to_human(by_kind[kind]["size_bytes"])
    return {
        "total_files": len(entries),
        "total_size_bytes": sum(e["size_bytes"] for e in entries),
        "total_size_human": size_to_human(sum(e["size_bytes"] for e in entries)),
        "by_kind": dict(sorted(by_kind.items(), key=lambda item: (-item[1]["count"], item[0]))),
    }


def format_text(root: Path, entries: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "=== Asset Inventory ===",
        f"root: {root}",
        f"total_files: {summary['total_files']}",
        f"total_size: {summary['total_size_human']} ({summary['total_size_bytes']} bytes)",
        "",
        "by_kind:",
    ]
    for kind, stats in summary["by_kind"].items():
        lines.append(f"  {kind:12s} {stats['count']:4d} file(s) {stats['size_human']}")

    lines.append("")
    lines.append("files:")
    for entry in entries:
        suffix = f" hash={entry['sha256_16']}" if "sha256_16" in entry else ""
        lines.append(
            f"  {entry['kind']:12s} {entry['size_human']:>8s} {entry['path']}{suffix}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory paper assets with path, type, and size summary."
    )
    parser.add_argument("--root", required=True, help="Assets root directory.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--with-hash", action="store_true", help="Include short sha256 hash per file.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: assets root not found: {root}", file=sys.stderr)
        return 1

    entries = collect_assets(root, args.with_hash)
    summary = summarize(entries)
    report = {"root": str(root), "summary": summary, "files": entries}

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(root, entries, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
