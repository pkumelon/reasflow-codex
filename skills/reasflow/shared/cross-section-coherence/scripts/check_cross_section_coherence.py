#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ACRONYM_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9 \-]{3,}?)\s*\(([A-Z]{2,})\)")
SECTION_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}")
LABEL_PATTERN = re.compile(r"\\label\{([^}]+)\}")
REF_PATTERN = re.compile(r"\\(?:ref|eqref|cref|Cref)\{([^}]+)\}")


def collect_tex_files(project_dir: Path, main_file: str) -> list[Path]:
    main_path = project_dir / main_file
    if not main_path.exists():
        return []

    visited: set[Path] = set()
    ordered: list[Path] = []

    def _walk(path: Path) -> None:
        resolved = path.resolve()
        if resolved in visited or not path.exists():
            return
        visited.add(resolved)
        ordered.append(path)
        content = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"\\(?:input|include)\{([^}]+)\}", content):
            ref = match.group(1).strip()
            child = project_dir / ref
            if not child.suffix:
                child = child.with_suffix(".tex")
            _walk(child)

    _walk(main_path)
    return ordered


def analyze(files: list[Path], terms: list[str]) -> dict[str, Any]:
    acronym_map: dict[str, set[str]] = {}
    label_counts: dict[str, list[str]] = {}
    refs: set[str] = set()
    section_titles: list[str] = []

    full_text = ""
    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        full_text += "\n" + text
        for section in SECTION_PATTERN.findall(text):
            section_titles.append(section.strip())
        for label in LABEL_PATTERN.findall(text):
            label_counts.setdefault(label.strip(), []).append(str(file_path))
        for ref in REF_PATTERN.findall(text):
            refs.add(ref.strip())
        for expansion, acronym in ACRONYM_PATTERN.findall(text):
            clean_expansion = re.sub(r"\s+", " ", expansion).strip().lower()
            acronym_map.setdefault(acronym.strip(), set()).add(clean_expansion)

    duplicate_labels = {
        label: sources for label, sources in label_counts.items() if len(sources) > 1
    }
    undefined_refs = sorted(ref for ref in refs if ref and ref not in label_counts)
    acronym_conflicts = {
        acronym: sorted(expansions)
        for acronym, expansions in acronym_map.items()
        if len(expansions) > 1
    }

    term_variant_counts: dict[str, dict[str, int]] = {}
    lower_text = full_text.lower()
    for term in terms:
        canonical = term.strip()
        if not canonical:
            continue
        hyphenated = canonical.replace(" ", "-").lower()
        spaced = canonical.replace("-", " ").lower()
        compact = canonical.replace("-", "").replace(" ", "").lower()
        term_variant_counts[canonical] = {
            "canonical_count": lower_text.count(canonical.lower()),
            "hyphenated_count": lower_text.count(hyphenated),
            "spaced_count": lower_text.count(spaced),
            "compact_count": lower_text.count(compact),
        }

    return {
        "section_titles": section_titles,
        "duplicate_labels": duplicate_labels,
        "undefined_refs": undefined_refs,
        "acronym_conflicts": acronym_conflicts,
        "term_variant_counts": term_variant_counts,
    }


def format_text(report: dict[str, Any]) -> str:
    lines = [
        "=== Cross Section Coherence Report ===",
        f"project_dir: {report['project_dir']}",
        f"main_file: {report['main_file']}",
        f"tex_files: {report['tex_file_count']}",
        f"sections: {len(report['analysis']['section_titles'])}",
        "",
        f"duplicate_labels: {len(report['analysis']['duplicate_labels'])}",
    ]
    for label, sources in list(report["analysis"]["duplicate_labels"].items())[:20]:
        lines.append(f"  {label}: {', '.join(sources[:3])}")
    if len(report["analysis"]["duplicate_labels"]) > 20:
        lines.append(f"  ... +{len(report['analysis']['duplicate_labels']) - 20} more")

    lines.append(f"undefined_refs: {len(report['analysis']['undefined_refs'])}")
    for ref in report["analysis"]["undefined_refs"][:20]:
        lines.append(f"  - {ref}")
    if len(report["analysis"]["undefined_refs"]) > 20:
        lines.append(f"  ... +{len(report['analysis']['undefined_refs']) - 20} more")

    lines.append(f"acronym_conflicts: {len(report['analysis']['acronym_conflicts'])}")
    for acronym, expansions in report["analysis"]["acronym_conflicts"].items():
        lines.append(f"  {acronym}: {', '.join(expansions)}")

    if report["analysis"]["term_variant_counts"]:
        lines.append("term_variant_counts:")
        for term, counts in report["analysis"]["term_variant_counts"].items():
            lines.append(
                f"  {term}: canonical={counts['canonical_count']}, hyphenated={counts['hyphenated_count']}, spaced={counts['spaced_count']}"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check cross-section coherence: labels/refs, acronym expansion consistency, and term variants."
    )
    parser.add_argument("--project-dir", default=".", help="Project directory containing TeX files.")
    parser.add_argument("--main-file", default="main.tex", help="Main TeX entry file.")
    parser.add_argument(
        "--term",
        action="append",
        default=[],
        dest="terms",
        help="Term to track for spelling/variant consistency. Repeatable.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        print(f"Error: project directory not found: {project_dir}", file=sys.stderr)
        return 1

    tex_files = collect_tex_files(project_dir, args.main_file)
    if not tex_files:
        print(f"Error: cannot find {args.main_file} under {project_dir}", file=sys.stderr)
        return 1

    analysis = analyze(tex_files, args.terms)
    report = {
        "project_dir": str(project_dir),
        "main_file": args.main_file,
        "tex_file_count": len(tex_files),
        "analysis": analysis,
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))

    failed = bool(analysis["duplicate_labels"] or analysis["undefined_refs"] or analysis["acronym_conflicts"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
