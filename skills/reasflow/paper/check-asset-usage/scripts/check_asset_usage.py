#!/usr/bin/env python3
"""Check whether paper assets are used in the manuscript output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", "cache", "node_modules"}
SCRIPT_LIKE_DIRS = {"code", "scripts", "temp", "data"}
CONTENT_EXTENSIONS = {
    ".tex",
    ".bib",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".eps",
    ".svg",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}


def trace_input_chain(main_tex: Path) -> set[Path]:
    compiled_files: set[Path] = set()
    project_dir = main_tex.parent

    def _trace(tex_path: Path) -> None:
        if tex_path in compiled_files or not tex_path.exists():
            return
        compiled_files.add(tex_path)
        content = tex_path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"\\(?:input|include)\{([^}]+)\}", content):
            ref = match.group(1).strip()
            candidate = project_dir / ref
            if not candidate.suffix:
                candidate = candidate.with_suffix(".tex")
            _trace(candidate)

    _trace(main_tex)
    return compiled_files


def collect_compiled_content(compiled_files: set[Path]) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in compiled_files
    )


def collect_graphics_refs(compiled_content: str) -> set[str]:
    refs: set[str] = set()
    for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", compiled_content):
        ref = match.group(1).strip()
        refs.add(ref)
        refs.add(Path(ref).name)
        refs.add(Path(ref).stem)
    return refs


def collect_labels(compiled_content: str) -> set[str]:
    return {
        match.group(1).strip()
        for match in re.finditer(r"\\label\{([^}]+)\}", compiled_content)
    }


def collect_cite_keys(compiled_content: str) -> set[str]:
    keys: set[str] = set()
    for match in re.finditer(
        r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear)\*?(?:\[[^\]]*\])?(?:\[[^\]]*\])?\{([^}]+)\}",
        compiled_content,
    ):
        for key in match.group(1).split(","):
            stripped = key.strip()
            if stripped:
                keys.add(stripped)
    return keys


def collect_bib_keys(bib_path: Path) -> set[str]:
    if not bib_path.exists():
        return set()
    return {
        match.group(1).strip()
        for match in re.finditer(
            r"@\w+\{(\S+?),", bib_path.read_text(encoding="utf-8", errors="replace")
        )
    }


def extract_asset_bib_keys(asset_file: Path) -> set[str]:
    content = asset_file.read_text(encoding="utf-8", errors="replace")
    if asset_file.suffix == ".bib":
        return {match.group(1).strip() for match in re.finditer(r"@\w+\{(\S+?),", content)}

    keys = {asset_file.stem}
    for match in re.finditer(r"(?:key|id|cite_key):\s*['\"]?(\S+)", content):
        keys.add(match.group(1).strip().rstrip("'\""))
    return keys


def extract_doc_signatures(doc_file: Path) -> list[str]:
    content = doc_file.read_text(encoding="utf-8", errors="replace")
    signatures: list[str] = []
    for match in re.finditer(r"^#+\s+(.+)", content, re.MULTILINE):
        title = match.group(1).strip()
        if len(title) > 10:
            signatures.append(title)
    for match in re.finditer(r"^\*\*(.+?)\*\*", content, re.MULTILINE):
        phrase = match.group(1).strip()
        if len(phrase) > 8:
            signatures.append(phrase)
    return signatures[:10]


def extract_tex_signatures(tex_path: Path) -> list[str]:
    content = tex_path.read_text(encoding="utf-8", errors="replace")
    signatures: list[str] = []
    for match in re.finditer(r"\\label\{([^}]+)\}", content):
        signatures.append(match.group(1).strip())
    for match in re.finditer(
        r"\\begin\{(?:lemma|theorem|proposition|corollary|definition|remark|assumption)\}\[([^\]]+)\]",
        content,
    ):
        signatures.append(re.sub(r"\$[^$]*\$", "", match.group(1)).strip())
    return [signature for signature in signatures if signature]


class UsageChecker:
    def __init__(self, assets_dir: Path, output_dir: Path, main_file: str):
        self.assets_dir = assets_dir
        self.output_dir = output_dir
        main_tex = output_dir / main_file
        self.compiled_files = trace_input_chain(main_tex) if main_tex.exists() else set()
        self.compiled_content = collect_compiled_content(self.compiled_files) if self.compiled_files else ""
        self.output_labels = collect_labels(self.compiled_content)
        self.graphics_refs = collect_graphics_refs(self.compiled_content)
        self.cite_keys = collect_cite_keys(self.compiled_content)
        self.output_bib_keys: set[str] = set()
        for bib_file in output_dir.rglob("*.bib"):
            self.output_bib_keys |= collect_bib_keys(bib_file)

    def is_used(self, asset_rel_path: Path) -> bool:
        asset_path = self.assets_dir / asset_rel_path
        suffix = asset_path.suffix.lower()
        if suffix == ".tex":
            for signature in extract_tex_signatures(asset_path):
                if signature in self.output_labels or signature.lower() in self.compiled_content.lower():
                    return True
            return False
        if suffix in IMAGE_EXTENSIONS:
            return asset_path.name in self.graphics_refs or asset_path.stem in self.graphics_refs
        if suffix in {".bib", ".yaml", ".yml"}:
            keys = extract_asset_bib_keys(asset_path)
            return bool(keys & self.output_bib_keys) or bool(keys & self.cite_keys)
        if suffix in {".md", ".txt"}:
            return any(
                signature.lower() in self.compiled_content.lower()
                for signature in extract_doc_signatures(asset_path)
            )
        return False


def collect_asset_files(assets_dir: Path) -> dict[str, dict[str, list[Path]]]:
    grouped: dict[str, dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))
    for file_path in sorted(assets_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in CONTENT_EXTENSIONS:
            continue
        rel = file_path.relative_to(assets_dir)
        parts = rel.parts
        if len(parts) == 1:
            grouped["(root)"]["(root)"].append(rel)
        elif len(parts) == 2:
            grouped[parts[0]]["(root)"].append(rel)
        else:
            grouped[parts[0]][parts[1]].append(rel)
    return grouped


def format_text_report(checker: UsageChecker, grouped: dict[str, dict[str, list[Path]]]) -> str:
    lines = [
        "=== Asset Usage Report ===",
        f"Assets: {checker.assets_dir}",
        f"Output: {checker.output_dir}",
        f"Compiled .tex chain: {len(checker.compiled_files)} files",
        "",
    ]

    total_files = 0
    total_used = 0
    for top_dir in sorted(grouped):
        sub_dirs = grouped[top_dir]
        dir_total = sum(len(files) for files in sub_dirs.values())
        dir_used = 0
        lines.append(f"--- {top_dir} ---")
        for sub_dir in sorted(sub_dirs):
            files = sub_dirs[sub_dir]
            missing = [file_path for file_path in files if not checker.is_used(file_path)]
            used = len(files) - len(missing)
            dir_used += used
            label = f"  {sub_dir + '/':14s} {used:2d}/{len(files):2d}"
            if sub_dir.lower() in SCRIPT_LIKE_DIRS and not used:
                label += "  [typically not referenced directly]"
            elif missing:
                missing_names = ", ".join(path.name for path in missing[:5])
                label += f"  MISSING: {missing_names}"
                if len(missing) > 5:
                    label += f", ... (+{len(missing) - 5} more)"
            else:
                label += "  OK"
            lines.append(label)
        total_files += dir_total
        total_used += dir_used
        lines.append("")

    usage_rate = (total_used / total_files * 100) if total_files else 0
    lines.insert(4, f"Overall: {total_used}/{total_files} files used ({usage_rate:.1f}%)")
    return "\n".join(lines)


def format_json_report(checker: UsageChecker, grouped: dict[str, dict[str, list[Path]]]) -> dict:
    directories = {}
    total = 0
    used_total = 0
    for top_dir, sub_dirs in grouped.items():
        entry = {"sub_directories": {}, "total": 0, "used": 0}
        for sub_dir, files in sub_dirs.items():
            missing = [str(path) for path in files if not checker.is_used(path)]
            used = len(files) - len(missing)
            entry["sub_directories"][sub_dir] = {
                "total": len(files),
                "used": used,
                "missing": missing,
            }
            entry["total"] += len(files)
            entry["used"] += used
        directories[top_dir] = entry
        total += entry["total"]
        used_total += entry["used"]
    return {
        "directories": directories,
        "overall": {
            "total": total,
            "used": used_total,
            "usage_rate": round((used_total / total * 100), 1) if total else 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check asset usage in paper output")
    parser.add_argument("--assets-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--main-file", default="main.tex")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    assets_dir = Path(args.assets_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not assets_dir.exists():
        print(f"missing assets directory: {assets_dir}", file=sys.stderr)
        return 1
    if not output_dir.exists():
        print(f"missing output directory: {output_dir}", file=sys.stderr)
        return 1

    grouped = collect_asset_files(assets_dir)
    checker = UsageChecker(assets_dir, output_dir, args.main_file)
    if args.format == "json":
        print(json.dumps(format_json_report(checker, grouped), ensure_ascii=False, indent=2))
    else:
        print(format_text_report(checker, grouped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
