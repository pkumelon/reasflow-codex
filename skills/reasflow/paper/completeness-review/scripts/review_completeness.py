#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE),
    re.compile(r"\[insert [^\]]+\]", re.IGNORECASE),
    re.compile(r"to be added", re.IGNORECASE),
    re.compile(r"待补充"),
]
SECTION_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}")
CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
LOG_WARNING_PATTERNS = [
    (re.compile(r"Citation `[^']+' on page \d+ undefined"), "citation_undefined"),
    (re.compile(r"Reference `[^']+' on page \d+ undefined"), "reference_undefined"),
    (re.compile(r"There were undefined references"), "undefined_references"),
    (re.compile(r"There were undefined citations"), "undefined_citations"),
    (re.compile(r"Overfull \\hbox"), "overfull_hbox"),
    (re.compile(r"Underfull \\hbox"), "underfull_hbox"),
    (re.compile(r"Overfull \\vbox"), "overfull_vbox"),
    (re.compile(r"Underfull \\vbox"), "underfull_vbox"),
    (re.compile(r"Float too large for page"), "float_too_large"),
    (re.compile(r"Label .* multiply defined"), "duplicate_label"),
]


def collect_tex_files(project_dir: Path, main_file: str) -> list[Path]:
    main_path = project_dir / main_file
    if not main_path.exists():
        return []

    visited: set[Path] = set()
    ordered: list[Path] = []

    def _walk(tex_path: Path) -> None:
        resolved = tex_path.resolve()
        if resolved in visited or not tex_path.exists():
            return
        visited.add(resolved)
        ordered.append(tex_path)
        try:
            content = tex_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        for match in re.finditer(r"\\(?:input|include)\s*\{([^}]+)\}", content):
            child = match.group(1).strip()
            if not child.endswith(".tex"):
                child += ".tex"
            _walk(project_dir / child)

    _walk(main_path)
    return ordered


def collect_tex_content(tex_files: list[Path]) -> str:
    parts: list[str] = []
    for tex_file in tex_files:
        try:
            parts.append(tex_file.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
    return "\n".join(parts)


def detect_placeholders(tex_files: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for tex_file in tex_files:
        lines = tex_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern.search(stripped):
                    findings.append(
                        {
                            "file": str(tex_file),
                            "line": line_no,
                            "pattern": pattern.pattern,
                            "text": stripped[:220],
                        }
                    )
                    break
    return findings


def extract_section_titles(full_tex: str) -> list[str]:
    return [match.group(1).strip() for match in SECTION_PATTERN.finditer(full_tex)]


def check_required_sections(full_tex: str, titles: list[str]) -> list[str]:
    title_blob = "\n".join(titles).lower()
    missing: list[str] = []
    required_rules = [
        ("abstract", "\\begin{abstract}" in full_tex.lower() or "abstract" in title_blob),
        ("introduction", "introduction" in title_blob),
        ("conclusion", "conclusion" in title_blob),
        (
            "references",
            "\\bibliography{" in full_tex
            or "\\printbibliography" in full_tex
            or "\\begin{thebibliography}" in full_tex,
        ),
    ]
    for name, present in required_rules:
        if not present:
            missing.append(name)
    return missing


def parse_log_warnings(log_path: Path) -> dict[str, Any]:
    if not log_path.exists():
        return {"counts": {}, "samples": {}, "message": "No .log file found."}
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception as error:
        return {"counts": {}, "samples": {}, "message": f"Cannot read .log file: {error}"}

    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        for pattern, warning_type in LOG_WARNING_PATTERNS:
            if pattern.search(stripped):
                counts[warning_type] = counts.get(warning_type, 0) + 1
                bucket = samples.setdefault(warning_type, [])
                if len(bucket) < 3:
                    bucket.append(stripped[:220])
                break
    return {"counts": counts, "samples": samples, "message": "ok"}


def extract_cite_keys_from_text(text: str) -> set[str]:
    keys: set[str] = set()
    for match in CITE_PATTERN.finditer(text):
        for key in match.group(1).split(","):
            cleaned = key.strip()
            if cleaned:
                keys.add(cleaned)
    return keys


def extract_cite_keys_from_dir(directory: Path) -> set[str]:
    keys: set[str] = set()
    for tex_file in directory.rglob("*.tex"):
        try:
            content = tex_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        keys |= extract_cite_keys_from_text(content)
    return keys


def check_asset_citation_coverage(assets_dir: Path, project_dir: Path) -> dict[str, Any]:
    if not assets_dir.exists():
        return {
            "available": False,
            "message": f"assets directory not found: {assets_dir}",
            "asset_keys": [],
            "output_keys": [],
            "missing_keys": [],
            "added_keys": [],
            "scanned_dirs": [],
        }

    exclude_dirs = {"prover", "references"}
    asset_keys: set[str] = set()
    scanned_dirs: list[str] = []

    for child in sorted(assets_dir.iterdir()):
        if child.is_dir() and child.name not in exclude_dirs:
            child_keys = extract_cite_keys_from_dir(child)
            if child_keys:
                scanned_dirs.append(f"{child.name}/ ({len(child_keys)})")
                asset_keys |= child_keys

    for root_tex in assets_dir.glob("*.tex"):
        try:
            asset_keys |= extract_cite_keys_from_text(root_tex.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue

    output_keys = extract_cite_keys_from_dir(project_dir)
    missing_keys = sorted(asset_keys - output_keys)
    added_keys = sorted(output_keys - asset_keys)

    return {
        "available": True,
        "message": "ok",
        "asset_keys": sorted(asset_keys),
        "output_keys": sorted(output_keys),
        "missing_keys": missing_keys,
        "added_keys": added_keys,
        "scanned_dirs": scanned_dirs,
    }


def build_text_report(report: dict[str, Any]) -> str:
    lines = [
        "=== Completeness Review ===",
        f"project_dir: {report['project_dir']}",
        f"main_file: {report['main_file']}",
        f"tex_files: {report['tex_file_count']}",
        f"section_titles: {len(report['section_titles'])}",
        "",
        f"readiness: {report['readiness']}",
        "",
    ]

    if report["missing_required_sections"]:
        lines.append(
            f"missing_required_sections ({len(report['missing_required_sections'])}): "
            + ", ".join(report["missing_required_sections"])
        )
    else:
        lines.append("missing_required_sections: none")

    lines.append(f"placeholder_hits: {len(report['placeholder_hits'])}")
    for finding in report["placeholder_hits"][:10]:
        lines.append(f"  {finding['file']}:{finding['line']} {finding['text']}")
    if len(report["placeholder_hits"]) > 10:
        lines.append(f"  ... +{len(report['placeholder_hits']) - 10} more")

    lines.append("")
    lines.append("log_warning_counts:")
    if report["log_warnings"]["counts"]:
        for warning_type, count in sorted(
            report["log_warnings"]["counts"].items(),
            key=lambda item: (-item[1], item[0]),
        ):
            lines.append(f"  {warning_type}: {count}")
    else:
        lines.append(f"  none ({report['log_warnings']['message']})")

    lines.append("")
    coverage = report["asset_citation_coverage"]
    if coverage["available"]:
        lines.append(
            "asset_citation_coverage: "
            f"{len(coverage['asset_keys'])} asset keys, "
            f"{len(coverage['output_keys'])} output keys, "
            f"{len(coverage['missing_keys'])} missing"
        )
        if coverage["missing_keys"]:
            lines.append("missing_asset_citations:")
            for key in coverage["missing_keys"][:20]:
                lines.append(f"  - {key}")
            if len(coverage["missing_keys"]) > 20:
                lines.append(f"  ... +{len(coverage['missing_keys']) - 20} more")
    else:
        lines.append(f"asset_citation_coverage: skipped ({coverage['message']})")

    lines.append("")
    lines.append("must_fix_items:")
    for item in report["must_fix_items"]:
        lines.append(f"  - {item}")
    if not report["must_fix_items"]:
        lines.append("  - none")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Programmatic completeness review: placeholders, required sections, log warnings, and asset citation coverage."
    )
    parser.add_argument("--project-dir", default=".", help="Paper output directory.")
    parser.add_argument("--main-file", default="main.tex", help="Main TeX entry file.")
    parser.add_argument("--assets-dir", default="", help="Optional assets directory for citation coverage.")
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

    full_tex = collect_tex_content(tex_files)
    section_titles = extract_section_titles(full_tex)
    placeholder_hits = detect_placeholders(tex_files)
    missing_required_sections = check_required_sections(full_tex, section_titles)
    log_warnings = parse_log_warnings(project_dir / f"{Path(args.main_file).stem}.log")

    assets_dir = Path(args.assets_dir).resolve() if args.assets_dir else project_dir.parent / "assets"
    asset_coverage = check_asset_citation_coverage(assets_dir, project_dir)

    must_fix_items: list[str] = []
    if missing_required_sections:
        must_fix_items.append(
            "Missing required sections: " + ", ".join(missing_required_sections)
        )
    if placeholder_hits:
        must_fix_items.append(f"Found {len(placeholder_hits)} placeholder/TODO marker(s).")
    high_impact_warnings = sum(
        log_warnings["counts"].get(key, 0)
        for key in ("citation_undefined", "reference_undefined", "undefined_references", "undefined_citations", "duplicate_label")
    )
    if high_impact_warnings:
        must_fix_items.append(
            f"Log has {high_impact_warnings} undefined citation/reference or duplicate-label warning(s)."
        )
    missing_asset_cites = asset_coverage.get("missing_keys", [])
    if missing_asset_cites:
        must_fix_items.append(
            f"{len(missing_asset_cites)} citation key(s) appear in assets but are missing in output."
        )

    readiness = "ready" if not must_fix_items else "not-ready"
    report = {
        "project_dir": str(project_dir),
        "main_file": args.main_file,
        "tex_file_count": len(tex_files),
        "section_titles": section_titles,
        "missing_required_sections": missing_required_sections,
        "placeholder_hits": placeholder_hits,
        "log_warnings": log_warnings,
        "asset_citation_coverage": asset_coverage,
        "must_fix_items": must_fix_items,
        "readiness": readiness,
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(build_text_report(report))
    return 0 if readiness == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
