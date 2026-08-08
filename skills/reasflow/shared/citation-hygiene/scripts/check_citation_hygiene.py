#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
BIB_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)
CLAIM_HINT_PATTERN = re.compile(
    r"\b(first(?![- ]order)|state[- ]of[- ]the[- ]art|outperform|significant(ly)?|novel|prove|superior)\b",
    re.IGNORECASE,
)
LITERATURE_CUE_PATTERN = re.compile(
    r"\b(?:prior|previous|existing|recent|foundational|classical|literature|studies|researchers|"
    r"methods?|approaches?|algorithms?|frameworks?|baselines?)\b.{0,180}\b(?:show|shows|shown|"
    r"demonstrate|demonstrates|establish|establishes|achieve|achieves|require|requires|rely|relies|"
    r"use|uses|suffer|suffers|lack|lacks|limit|limits|remain|remains|typically|often|widely|can|cannot)\b|"
    r"\b(?:has emerged|have emerged|widely (?:used|adopted)|line of work|body of work|"
    r"state[- ]of[- ]the[- ]art|no existing|most existing)\b",
    re.IGNORECASE,
)
FIRST_PERSON_CLAIM_PATTERN = re.compile(
    r"\b(?:we|our|this paper|this work)\s+(?:propose|introduce|develop|prove|show|establish|present|evaluate|study)\b",
    re.IGNORECASE,
)
ORGANIZATION_SENTENCE_PATTERN = re.compile(
    r"\b(?:the remainder of (?:this|the) paper|the rest of (?:this|the) paper|"
    r"(?:this|the) paper is organized as follows)\b",
    re.IGNORECASE,
)
UNRESOLVED_MARKER_PATTERN = re.compile(
    r"\[(?:needs-citation|needs-result|scope-check|terminology-check|remove-if-unproven)\]|\[VERIFY\s*:",
    re.IGNORECASE,
)
SECTION_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}")


def strip_comments(line: str) -> str:
    if "%" not in line:
        return line
    escaped = re.sub(r"\\%", "", line)
    comment_index = escaped.find("%")
    if comment_index < 0:
        return line
    return line[:comment_index]


def collect_tex_files(main_tex: Path) -> list[Path]:
    project_dir = main_tex.parent
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

    _walk(main_tex)
    return ordered


def parse_citations(tex_files: list[Path]) -> tuple[set[str], dict[str, list[str]]]:
    all_keys: set[str] = set()
    by_file: dict[str, list[str]] = {}
    for tex_file in tex_files:
        content = tex_file.read_text(encoding="utf-8", errors="replace")
        keys: set[str] = set()
        for match in CITE_PATTERN.finditer(content):
            for key in match.group(1).split(","):
                cleaned = key.strip()
                if cleaned:
                    keys.add(cleaned)
                    all_keys.add(cleaned)
        by_file[str(tex_file)] = sorted(keys)
    return all_keys, by_file


def parse_bib_keys(bib_paths: list[Path]) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    duplicates: list[str] = []
    for bib_path in bib_paths:
        content = bib_path.read_text(encoding="utf-8", errors="replace")
        for match in BIB_PATTERN.finditer(content):
            key = match.group(1).strip()
            if not key:
                continue
            if key in keys:
                duplicates.append(key)
            else:
                keys.add(key)
    return keys, sorted(set(duplicates))


def strip_tex_for_classification(sentence: str) -> str:
    text = CITE_PATTERN.sub("", sentence)
    text = SECTION_PATTERN.sub("", text)
    text = re.sub(r"\\[a-zA-Z*]+(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z*]+", "", text)
    text = re.sub(r"[$][^$]*[$]", " MATH ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_unsupported_claims(tex_files: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    current_section = "(unknown)"
    for tex_file in tex_files:
        content = tex_file.read_text(encoding="utf-8", errors="replace")
        clean_content = "\n".join(strip_comments(line) for line in content.splitlines())
        clean_content = re.sub(
            r"\\begin\{(?:equation|align|gather|multline|table|figure)\*?\}.*?"
            r"\\end\{(?:equation|align|gather|multline|table|figure)\*?\}",
            " ",
            clean_content,
            flags=re.DOTALL,
        )
        for paragraph_match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", clean_content, re.DOTALL):
            paragraph = paragraph_match.group(0).strip()
            if not paragraph:
                continue
            section_match = SECTION_PATTERN.search(paragraph)
            if section_match:
                current_section = section_match.group(1).strip()
            for sentence_match in re.finditer(
                r"(?:^|(?<=[.!?])\s+)(.*?)(?=(?<=[.!?])\s+(?=[A-Z\\])|\Z)",
                paragraph,
                re.DOTALL,
            ):
                sentence = sentence_match.group(1).strip()
                plain = strip_tex_for_classification(sentence)
                if (
                    len(plain.split()) < 6
                    or FIRST_PERSON_CLAIM_PATTERN.search(plain)
                    or ORGANIZATION_SENTENCE_PATTERN.search(plain)
                ):
                    continue
                has_claim_hint = bool(
                    CLAIM_HINT_PATTERN.search(plain) or LITERATURE_CUE_PATTERN.search(plain)
                )
                if not has_claim_hint or CITE_PATTERN.search(sentence):
                    continue
                absolute_offset = paragraph_match.start() + sentence_match.start(1)
                line_number = clean_content.count("\n", 0, absolute_offset) + 1
                findings.append(
                    {
                        "file": str(tex_file),
                        "line": line_number,
                        "section": current_section,
                        "text": plain[:300],
                    }
                )
    return findings


def detect_unresolved_markers(tex_files: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for tex_file in tex_files:
        for line_number, line in enumerate(
            tex_file.read_text(encoding="utf-8", errors="replace").splitlines(),
            start=1,
        ):
            for marker in UNRESOLVED_MARKER_PATTERN.finditer(line):
                findings.append(
                    {
                        "file": str(tex_file),
                        "line": line_number,
                        "marker": marker.group(0),
                        "text": line.strip()[:300],
                    }
                )
    return findings


def load_claim_contract(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded.get("organized_info"), dict):
        loaded = loaded["organized_info"]
    claims = loaded.get("citation_claims", []) if isinstance(loaded, dict) else []
    return [claim for claim in claims if isinstance(claim, dict)]


def validate_citation_trace(
    trace_path: Path | None,
    claims: list[dict[str, Any]],
    cited_keys: set[str],
) -> list[str]:
    if trace_path is None:
        return []
    loaded = json.loads(trace_path.read_text(encoding="utf-8"))
    trace = loaded.get("trace", loaded) if isinstance(loaded, dict) else {}
    items = trace.get("claims", []) if isinstance(trace, dict) else []
    if not isinstance(items, list):
        return ["citation trace must contain a claims list"]

    claim_by_id = {
        str(claim.get("claim_id", "")): claim
        for claim in claims
        if str(claim.get("claim_id", ""))
    }
    errors: list[str] = []
    if claims and cited_keys and not items:
        errors.append("citation trace must map cited source claims to verified keys")
    traced_key_set: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("citation trace entries must be objects")
            continue
        claim_id = str(item.get("claim_id", ""))
        if claim_id not in claim_by_id:
            errors.append(f"unknown claim_id in citation trace: {claim_id}")
            continue
        allowed_keys = {str(key) for key in claim_by_id[claim_id].get("bibtex_keys", [])}
        traced_keys = {str(key) for key in item.get("bibtex_keys", [])}
        traced_key_set.update(traced_keys)
        if not traced_keys or not traced_keys <= allowed_keys:
            errors.append(f"citation trace keys for {claim_id} violate the claim contract")
        if not traced_keys <= cited_keys:
            errors.append(f"citation trace keys for {claim_id} do not appear in the manuscript")
    untraced_keys = sorted(cited_keys - traced_key_set)
    if claims and untraced_keys:
        errors.append("cited keys missing from citation trace: " + ", ".join(untraced_keys))
    return errors


def format_text(report: dict[str, Any]) -> str:
    lines = [
        "=== Citation Hygiene Report ===",
        f"main_tex: {report['main_tex']}",
        f"tex_files: {report['tex_file_count']}",
        f"bib_files: {report['bib_file_count']}",
        f"cited_keys: {report['cited_key_count']}",
        f"bib_keys: {report['bib_key_count']}",
        "",
    ]
    if report["missing_keys"]:
        lines.append(f"missing_keys ({len(report['missing_keys'])}): {', '.join(report['missing_keys'])}")
    else:
        lines.append("missing_keys: none")
    if report["unused_keys"]:
        lines.append(f"unused_keys ({len(report['unused_keys'])}): {', '.join(report['unused_keys'])}")
    else:
        lines.append("unused_keys: none")
    if report["duplicate_bib_keys"]:
        lines.append(
            f"duplicate_bib_keys ({len(report['duplicate_bib_keys'])}): {', '.join(report['duplicate_bib_keys'])}"
        )
    else:
        lines.append("duplicate_bib_keys: none")

    lines.append("")
    lines.append(f"unsupported_claim_candidates: {len(report['unsupported_claim_candidates'])}")
    for finding in report["unsupported_claim_candidates"][:10]:
        lines.append(
            f"  {finding['file']}:{finding['line']} [{finding['section']}] {finding['text']}"
        )
    if len(report["unsupported_claim_candidates"]) > 10:
        lines.append(
            f"  ... +{len(report['unsupported_claim_candidates']) - 10} more"
        )
    lines.append("")
    lines.append(f"unresolved_markers: {len(report['unresolved_markers'])}")
    for finding in report["unresolved_markers"][:10]:
        lines.append(
            f"  {finding['file']}:{finding['line']} {finding['marker']} {finding['text']}"
        )
    lines.append(f"citation_trace_errors: {len(report['citation_trace_errors'])}")
    for error in report["citation_trace_errors"]:
        lines.append(f"  {error}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check citation hygiene: cite/bib consistency and unsupported claim hints."
    )
    parser.add_argument("--project-dir", default=".", help="Project directory containing main.tex.")
    parser.add_argument("--main-file", default="main.tex", help="Main TeX entry file.")
    parser.add_argument(
        "--bib",
        action="append",
        default=[],
        dest="bib_files",
        help="Explicit BibTeX file(s). If omitted, all *.bib under project-dir are scanned.",
    )
    parser.add_argument("--allow-unused", action="store_true", help="Do not fail on unused bib keys.")
    parser.add_argument("--strict", action="store_true", help="Fail on uncited literature claims, unresolved markers, or trace errors.")
    parser.add_argument("--claim-ledger", default="", help="organized_info.json containing citation_claims.")
    parser.add_argument("--trace-json", default="", help="Citation trace or writer citation_report.json.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    main_tex = project_dir / args.main_file
    if not main_tex.exists():
        print(f"Error: main TeX file not found: {main_tex}", file=sys.stderr)
        return 1

    tex_files = collect_tex_files(main_tex)
    if args.bib_files:
        bib_paths = [Path(path).resolve() for path in args.bib_files]
    else:
        bib_paths = sorted(project_dir.rglob("*.bib"))

    missing_bibs = [str(path) for path in bib_paths if not path.exists()]
    if missing_bibs:
        print(f"Error: missing bib file(s): {', '.join(missing_bibs)}", file=sys.stderr)
        return 1

    cited_keys, citations_by_file = parse_citations(tex_files)
    bib_keys, duplicate_keys = parse_bib_keys(bib_paths)
    missing_keys = sorted(cited_keys - bib_keys)
    unused_keys = sorted(bib_keys - cited_keys)
    unsupported_claims = detect_unsupported_claims(tex_files)
    unresolved_markers = detect_unresolved_markers(tex_files)
    claim_ledger_path = Path(args.claim_ledger).resolve() if args.claim_ledger else None
    trace_path = Path(args.trace_json).resolve() if args.trace_json else None
    try:
        citation_claims = load_claim_contract(claim_ledger_path)
        citation_trace_errors = validate_citation_trace(trace_path, citation_claims, cited_keys)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: could not read citation contract/trace: {exc}", file=sys.stderr)
        return 1

    report = {
        "main_tex": str(main_tex),
        "tex_file_count": len(tex_files),
        "bib_file_count": len(bib_paths),
        "citations_by_file": citations_by_file,
        "cited_key_count": len(cited_keys),
        "bib_key_count": len(bib_keys),
        "missing_keys": missing_keys,
        "unused_keys": unused_keys,
        "duplicate_bib_keys": duplicate_keys,
        "unsupported_claim_candidates": unsupported_claims,
        "unresolved_markers": unresolved_markers,
        "citation_contract_claim_count": len(citation_claims),
        "citation_trace_errors": citation_trace_errors,
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))

    failed = bool(missing_keys or duplicate_keys or (unused_keys and not args.allow_unused))
    if args.strict:
        failed = bool(
            failed
            or unsupported_claims
            or unresolved_markers
            or citation_trace_errors
            or (citation_claims and not cited_keys)
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
